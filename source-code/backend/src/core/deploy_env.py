"""部署环境真源（dev / test / prod）。

三种环境是**构建期固化的身份**，不是运行时随手切换的开关：

- ``dev``  —— 源码直接运行，开发自测。端口 5002。
- ``test`` —— 源码运行，对「待发布代码」做全流程验证。端口 5001。
- ``prod`` —— PyInstaller 打包产物，用户实际在用的那份 exe。端口 5000。

判定优先级（从高到低）：

1. ``sys.frozen`` 为真 → 强制 ``prod``。
   发布版不能让最终用户改配置把 exe 降级成开发态，否则会直接读到生产数据。
2. 命令行 ``--env``（由 ``main.py`` 解析后注入本模块）。
3. 环境变量 ``COMFYUI_BOX_ENV``。
4. ``deploy.json`` 的 ``current_env``。
5. 兜底 ``dev``。

配置采用「公共段 + 环境差异段」：``defaults`` 放三环境共用值，
``environments.<env>`` 只写差异项，同名键递归覆盖。这避免三份配置 90% 重复。

**本文件只允许放系统参数**（端口、实例名、AUMID、运行数据子目录、数据源开关、
写保护）。用户数据目录由用户在界面选择，系统只负责按环境记住那个选择，
绝不在配置里写死任何数据路径。
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from backend.src.utils.config_utils import deep_merge
from backend.src.utils.logger import app_logger as logger

ENV_DEV = "dev"
ENV_TEST = "test"
ENV_PROD = "prod"
VALID_ENVS = (ENV_DEV, ENV_TEST, ENV_PROD)

DEFAULT_ENV = ENV_DEV

# 覆盖用的环境变量名：CI 或临时排障时不必改文件
ENV_VARIABLE = "COMFYUI_BOX_ENV"

# 部署配置文件名（位于 resource/config/ 下，随包分发）
DEPLOY_CONFIG_FILENAME = "deploy.json"

# 端口合法区间：低于 1024 需要管理员权限，高于 65535 非法
_MIN_PORT = 1
_MAX_PORT = 65535

# 配置文件缺失时的最小兜底：宁可让应用起来并告警，也不要因为漏打一个文件
# 就整机不可用。端口与 prod 身份必须与 deploy.json 保持一致。
_BUILTIN_FALLBACK: Dict[str, Any] = {
    "current_env": DEFAULT_ENV,
    "defaults": {
        "http": {"host": "127.0.0.1", "strict_port": True},
        "instance": {"name": "Comfyui-Box"},
        "app_user_model_id": "Comfyui-Box.Desktop",
        "runtime_subdir": "",
        "data_sources": {"dev_updates": False, "test_fixtures": False},
        "write_guard": False,
    },
    "environments": {
        ENV_DEV: {
            "http": {"port": 5002},
            "instance": {"name": "Comfyui-Box-dev"},
            "app_user_model_id": "Comfyui-Box.Desktop.dev",
            "runtime_subdir": "run/dev",
            "data_sources": {"dev_updates": True},
        },
        ENV_TEST: {
            "http": {"port": 5001},
            "instance": {"name": "Comfyui-Box-test"},
            "app_user_model_id": "Comfyui-Box.Desktop.test",
            "runtime_subdir": "run/test",
            "data_sources": {"test_fixtures": True},
            "write_guard": True,
        },
        ENV_PROD: {
            "http": {"port": 5000},
            "instance": {"name": "Comfyui-Box"},
            "app_user_model_id": "Comfyui-Box.Desktop",
            "runtime_subdir": "",
            "data_sources": {"dev_updates": False, "test_fixtures": False},
            "write_guard": False,
        },
    },
}

_env_override: Optional[str] = None
_env_name_cache: Optional[str] = None
_merged_config_cache: Optional[Dict[str, Any]] = None
_raw_config_cache: Optional[Dict[str, Any]] = None
_runtime_write_guard: bool = False


def _config_file() -> Path:
    """部署配置文件的绝对路径（函数内导入 paths，避免与 paths 循环依赖）。"""
    from backend.src.utils.paths import get_resource_config_dir

    return get_resource_config_dir() / DEPLOY_CONFIG_FILENAME


def _load_raw() -> Dict[str, Any]:
    """读取 deploy.json 原始内容；缺失或损坏时退回内置兜底并告警。"""
    global _raw_config_cache
    if _raw_config_cache is not None:
        return _raw_config_cache

    path = _config_file()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning(f"[部署环境] 未找到 {path}，改用内置兜底配置")
        _raw_config_cache = _BUILTIN_FALLBACK
        return _raw_config_cache
    except (OSError, ValueError) as exc:
        logger.error(f"[部署环境] 读取 {path} 失败（{exc}），改用内置兜底配置")
        _raw_config_cache = _BUILTIN_FALLBACK
        return _raw_config_cache

    if not isinstance(data, dict):
        logger.error(f"[部署环境] {path} 顶层不是对象，改用内置兜底配置")
        _raw_config_cache = _BUILTIN_FALLBACK
        return _raw_config_cache

    _raw_config_cache = data
    return _raw_config_cache


def _normalize_env(raw: str) -> str:
    """校验环境名；非法值直接报错，避免拼错后静默落到 dev。"""
    value = str(raw).strip().lower()
    if value not in VALID_ENVS:
        raise ValueError(f"未知部署环境 {raw!r}，合法值: {', '.join(VALID_ENVS)}")
    return value


def _resolve_env_name() -> str:
    """按优先级链判定当前环境。"""
    if getattr(sys, "frozen", False):
        return ENV_PROD
    if _env_override:
        return _normalize_env(_env_override)

    from_variable = os.environ.get(ENV_VARIABLE, "").strip()
    if from_variable:
        return _normalize_env(from_variable)

    from_file = _load_raw().get("current_env")
    if isinstance(from_file, str) and from_file.strip():
        return _normalize_env(from_file)
    return DEFAULT_ENV


def get_env_name() -> str:
    """当前部署环境名（dev / test / prod）。"""
    global _env_name_cache
    if _env_name_cache is None:
        _env_name_cache = _resolve_env_name()
    return _env_name_cache


def _invalidate_path_caches() -> None:
    """
    环境变了，paths 里按环境派生的缓存必须一起失效。

    否则同一个进程内切换环境后，用户数据根与运行数据根会继续指向旧环境的目录。
    函数内导入 + 容错：paths 导入本模块时可能尚未完成初始化。
    """
    try:
        from backend.src.utils import paths
    except Exception:  # 导入期调用，paths 可能还没就绪
        return
    paths.reset_user_data_root_cache()
    paths.reset_runtime_dir_cache()


def set_env_override(env: Optional[str]) -> None:
    """注入命令行 ``--env`` 覆盖值；传 None 表示清除。"""
    global _env_override
    _env_override = _normalize_env(env) if env else None
    reset_cache()


def reset_cache() -> None:
    """清空缓存（切换环境或测试时调用）。"""
    global _env_name_cache, _merged_config_cache, _raw_config_cache
    _env_name_cache = None
    _merged_config_cache = None
    _raw_config_cache = None
    _invalidate_path_caches()


def is_dev() -> bool:
    return get_env_name() == ENV_DEV


def is_test() -> bool:
    return get_env_name() == ENV_TEST


def is_prod() -> bool:
    return get_env_name() == ENV_PROD


def get_deploy_config() -> Dict[str, Any]:
    """公共段 + 当前环境差异段合并后的配置。"""
    global _merged_config_cache
    if _merged_config_cache is not None:
        return _merged_config_cache

    raw = _load_raw()
    env = get_env_name()
    defaults = raw.get("defaults")
    environments = raw.get("environments")

    if not isinstance(defaults, dict) or not isinstance(environments, dict):
        raise ValueError("deploy.json 必须包含 defaults 与 environments 两个对象")
    section = environments.get(env)
    if not isinstance(section, dict):
        raise ValueError(f"deploy.json 未定义环境 {env!r}")

    merged = deep_merge(defaults, section)
    merged["env"] = env
    _merged_config_cache = merged
    return merged


def get(key: str, default: Any = None) -> Any:
    """按点号路径取值，例如 ``get("http.port")``。"""
    node: Any = get_deploy_config()
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def get_port() -> int:
    """当前环境的固定端口。缺失或越界时报错，绝不静默换端口。"""
    value = get("http.port")
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"deploy.json 未为环境 {get_env_name()!r} 配置整数端口: {value!r}")
    if not _MIN_PORT <= value <= _MAX_PORT:
        raise ValueError(f"端口 {value} 超出合法范围 {_MIN_PORT}-{_MAX_PORT}")
    return value


def get_host() -> str:
    """监听地址；本服务只服务本机窗口，默认回环。"""
    return str(get("http.host") or "127.0.0.1")


def is_strict_port() -> bool:
    """端口被占用时是否直接报错（True）还是向后探测（False）。"""
    return bool(get("http.strict_port", True))


def get_instance_name() -> str:
    """单实例锁名基名。不同环境不同名，才能同机并存。"""
    return str(get("instance.name") or "Comfyui-Box")


def get_app_user_model_id() -> str:
    """任务栏分组 ID。不同环境不同值，否则三个实例会在任务栏合并成一个图标。"""
    return str(get("app_user_model_id") or "Comfyui-Box.Desktop")


def get_runtime_subdir() -> str:
    """运行数据（日志/缓存/WebView2）的环境子目录；空串表示沿用现有位置。"""
    return str(get("runtime_subdir") or "").strip().strip("/\\")


def is_dev_updates_enabled() -> bool:
    """dev 专用更新源是否参与解析（prod 必须为 False）。"""
    return bool(get("data_sources.dev_updates", False))


def is_test_fixtures_enabled() -> bool:
    """test 专用夹具是否参与解析（prod 必须为 False）。"""
    return bool(get("data_sources.test_fixtures", False))


def is_write_guard_enabled() -> bool:
    """是否拒绝对真实 ComfyUI 根的写操作。"""
    return _runtime_write_guard or bool(get("write_guard", False))


def set_write_guard_override(enabled: bool) -> None:
    """
    命令行 ``--test-mode`` 强制开启只读保护，优先级高于配置值。

    单独提供这个覆盖而不是复用 ``paths.is_test_mode()``：后者表示"本次是隔离实例"，
    dev 用 ``--user-data-dir`` 起沙箱时也会为真，拿它做写保护会把开发环境也锁死。
    """
    global _runtime_write_guard
    _runtime_write_guard = bool(enabled)


def get_env_source() -> str:
    """
    环境判定来源，用于日志与排障。

    返回 frozen / cli / env_var / config / default 之一。打包后看到 prod 时，
    source=frozen 说明是代码硬兜底生效，而不是某个配置文件写错了。
    """
    if getattr(sys, "frozen", False):
        return "frozen"
    if _env_override:
        return "cli"
    if os.environ.get(ENV_VARIABLE, "").strip():
        return "env_var"
    from_file = _load_raw().get("current_env")
    if isinstance(from_file, str) and from_file.strip():
        return "config"
    return "default"


def describe() -> str:
    """一行环境摘要，用于启动日志与排障。"""
    return (
        f"env={get_env_name()}({get_env_source()}) port={get_port()} "
        f"instance={get_instance_name()} aumid={get_app_user_model_id()} "
        f"runtime_subdir={get_runtime_subdir() or '(默认)'}"
    )
