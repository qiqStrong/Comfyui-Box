"""部署环境配置（dev / test / prod）。

采用 SpringBoot 风格的多环境配置：
- deploy.json：基础配置（所有环境公共字段）
- deploy-dev.json：开发环境差异
- deploy-test.json：测试环境差异
- deploy-prod.json：生产环境差异

启动时通过 --env 参数、环境变量 COMFYUI_BOX_ENV 或 deploy.json 的 active_env 选择。
不再根据 sys.frozen 强制判定环境，打包后也可以运行 dev/test 环境用于调试。

端口约定：
- dev = 5002
- test = 5001
- prod = 5000
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from backend.src.utils.config_utils import deep_merge
from backend.src.utils.logger import app_logger as logger

ENV_DEV = "dev"
ENV_TEST = "test"
ENV_PROD = "prod"
VALID_ENVS = (ENV_DEV, ENV_TEST, ENV_PROD)

DEFAULT_ENV = ENV_DEV

# 环境变量名
ENV_VARIABLE = "COMFYUI_BOX_ENV"

# 配置文件名
BASE_CONFIG_FILENAME = "deploy.json"
ENV_CONFIG_PATTERN = "deploy-{env}.json"

# 端口合法区间
_MIN_PORT = 1
_MAX_PORT = 65535

# 内置兜底配置（仅在所有配置文件都缺失时使用）
_BUILTIN_FALLBACK: Dict[str, Any] = {
    "active_env": DEFAULT_ENV,
    "http": {"host": "127.0.0.1", "strict_port": True},
    "app_user_model_id": "Comfyui-Box.Desktop",
    "data_sources": {"dev_updates": False, "test_fixtures": False},
    "write_guard": False,
}

_env_override: Optional[str] = None
_env_name_cache: Optional[str] = None
_merged_config_cache: Optional[Dict[str, Any]] = None
_base_config_cache: Optional[Dict[str, Any]] = None
_runtime_write_guard: bool = False


def _config_dir() -> Path:
    """配置目录路径（避免与 paths 循环依赖）"""
    from backend.src.utils.paths import get_resource_config_dir
    return get_resource_config_dir()


def _load_json(filename: str, fallback: Optional[Dict] = None) -> Dict[str, Any]:
    """读取配置文件，缺失或损坏时返回 fallback"""
    path = _config_dir() / filename
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            logger.warning(f"[部署环境] {path} 顶层不是对象，忽略")
            return fallback or {}
        return data
    except FileNotFoundError:
        if fallback is not None:
            logger.warning(f"[部署环境] 未找到 {path}，使用默认值")
        return fallback or {}
    except (OSError, ValueError) as exc:
        logger.error(f"[部署环境] 读取 {path} 失败（{exc}），忽略")
        return fallback or {}


def _normalize_env(raw: str) -> str:
    """校验环境名"""
    value = str(raw).strip().lower()
    if value not in VALID_ENVS:
        raise ValueError(f"未知部署环境 {raw!r}，合法值: {', '.join(VALID_ENVS)}")
    return value


def _resolve_env_name() -> str:
    """按优先级判定当前环境"""
    # 1. 命令行覆盖（最高优先级）
    if _env_override:
        return _normalize_env(_env_override)

    # 2. 环境变量
    from_variable = os.environ.get(ENV_VARIABLE, "").strip()
    if from_variable:
        return _normalize_env(from_variable)

    # 3. 基础配置文件的 active_env
    base = _load_base_config()
    from_file = base.get("active_env")
    if isinstance(from_file, str) and from_file.strip():
        return _normalize_env(from_file)

    # 4. 兜底 dev
    return DEFAULT_ENV


def _load_base_config() -> Dict[str, Any]:
    """加载基础配置（deploy.json）"""
    global _base_config_cache
    if _base_config_cache is not None:
        return _base_config_cache
    _base_config_cache = _load_json(BASE_CONFIG_FILENAME, _BUILTIN_FALLBACK)
    return _base_config_cache


def get_env_name() -> str:
    """当前部署环境名（dev / test / prod）"""
    global _env_name_cache
    if _env_name_cache is None:
        _env_name_cache = _resolve_env_name()
    return _env_name_cache


def _invalidate_path_caches() -> None:
    """环境变了，paths 里按环境派生的缓存必须失效"""
    try:
        from backend.src.utils import paths
    except Exception:
        return
    paths.reset_user_data_root_cache()
    paths.reset_runtime_dir_cache()


def set_env_override(env: Optional[str]) -> None:
    """注入命令行 --env 覆盖值"""
    global _env_override
    _env_override = _normalize_env(env) if env else None
    reset_cache()


def reset_cache() -> None:
    """清空缓存（切换环境或测试时调用）"""
    global _env_name_cache, _merged_config_cache, _base_config_cache
    _env_name_cache = None
    _merged_config_cache = None
    _base_config_cache = None
    _invalidate_path_caches()


def is_dev() -> bool:
    return get_env_name() == ENV_DEV


def is_test() -> bool:
    return get_env_name() == ENV_TEST


def is_prod() -> bool:
    return get_env_name() == ENV_PROD


def get_deploy_config() -> Dict[str, Any]:
    """基础配置 + 环境差异配置合并后的结果"""
    global _merged_config_cache
    if _merged_config_cache is not None:
        return _merged_config_cache

    base = _load_base_config()
    env = get_env_name()
    env_config = _load_json(ENV_CONFIG_PATTERN.format(env=env))

    merged = deep_merge(base, env_config)
    merged["env"] = env
    _merged_config_cache = merged
    return merged


def get(key: str, default: Any = None) -> Any:
    """按点号路径取值，例如 get("http.port")"""
    node: Any = get_deploy_config()
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def get_port() -> int:
    """当前环境的固定端口"""
    value = get("http.port")
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"环境 {get_env_name()!r} 未配置整数端口: {value!r}")
    if not _MIN_PORT <= value <= _MAX_PORT:
        raise ValueError(f"端口 {value} 超出合法范围 {_MIN_PORT}-{_MAX_PORT}")
    return value


def get_host() -> str:
    """监听地址"""
    return str(get("http.host") or "127.0.0.1")


def is_strict_port() -> bool:
    """端口被占用时是否直接报错"""
    return bool(get("http.strict_port", True))


def get_instance_name() -> str:
    """单实例锁名基名"""
    return str(get("instance.name") or "Comfyui-Box")


def get_app_user_model_id() -> str:
    """任务栏分组 ID"""
    return str(get("app_user_model_id") or "Comfyui-Box.Desktop")


def get_runtime_subdir() -> str:
    """运行数据（日志/缓存/WebView2）的环境子目录"""
    return str(get("runtime_subdir") or "").strip().strip("/\\")


def is_dev_updates_enabled() -> bool:
    """dev 专用更新源是否参与解析"""
    return bool(get("data_sources.dev_updates", False))


def is_test_fixtures_enabled() -> bool:
    """test 专用夹具是否参与解析"""
    return bool(get("data_sources.test_fixtures", False))


def is_write_guard_enabled() -> bool:
    """是否拒绝对真实 ComfyUI 根的写操作"""
    return _runtime_write_guard or bool(get("write_guard", False))


def set_write_guard_override(enabled: bool) -> None:
    """命令行 --test-mode 强制开启只读保护"""
    global _runtime_write_guard
    _runtime_write_guard = bool(enabled)


def get_env_source() -> str:
    """环境判定来源（cli / env_var / config / default）"""
    if _env_override:
        return "cli"
    if os.environ.get(ENV_VARIABLE, "").strip():
        return "env_var"
    from_file = _load_base_config().get("active_env")
    if isinstance(from_file, str) and from_file.strip():
        return "config"
    return "default"


def describe() -> str:
    """一行环境摘要，用于启动日志"""
    return (
        f"env={get_env_name()}({get_env_source()}) port={get_port()} "
        f"instance={get_instance_name()} aumid={get_app_user_model_id()} "
        f"runtime_subdir={get_runtime_subdir() or '(默认)'}"
    )
