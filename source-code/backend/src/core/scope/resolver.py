"""
数据范围解析层。

真源：``<userdata>/config/environments.json`` 中的 ``packages`` / ``data_spaces`` /
``current_package_id``，以及每个环境上的 ``package_id`` / ``data_space_id`` /
``scope_overrides``。业务开关只是 scopeMap 的 UI 投影，不额外维护第二套开关配置。

旧配置兼容：缺少上述字段时按「默认包 + 旧版用户数据空间」自动补全，读取永不报错。
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ...utils.logger import app_logger as logger

# 每类业务数据的物理子路径（相对数据空间根）。
CATEGORY_SPECS: Dict[str, Dict[str, Any]] = {
    "gallery": {
        "label": "资产库",
        "subpath": "data/gallery",
        "default_mode": "global",
        "switchable": True,
        "is_file": False,
    },
    "prompts": {
        "label": "提示词库",
        "subpath": "data/prompt",
        "default_mode": "global",
        "switchable": True,
        "is_file": False,
    },
    "ai": {
        "label": "AI 对话",
        "subpath": "data/ai_assistant.db",
        "default_mode": "global",
        "switchable": True,
        "is_file": True,
    },
    "workflows": {
        "label": "工作流",
        "subpath": "data/workflows",
        "default_mode": "private",
        "switchable": True,
        "is_file": False,
        "root_native": True,
    },
    "lora": {
        "label": "LoRA 数据",
        "subpath": "lora_data",
        "default_mode": "private",
        "switchable": True,
        "is_file": False,
    },
}

SWITCHABLE_CATEGORIES: Tuple[str, ...] = tuple(
    key for key, spec in CATEGORY_SPECS.items() if spec.get("switchable")
)

# 旧版默认包首次建立时使用：保持现有行为（LoRA/资产/提示词/AI 继续读旧数据根）。
LEGACY_PACKAGE_DEFAULTS = {
    "gallery": "global",
    "prompts": "global",
    "ai": "global",
    "workflows": "private",
    "lora": "global",
}

DEFAULT_PACKAGE_ID = "pkg_default"
DEFAULT_PACKAGE_NAME = "默认包"
LEGACY_SPACE_ID = "ds_legacy"
LEGACY_SPACE_NAME = "旧版用户数据"

_epoch_lock = threading.RLock()
_epoch_counter = 0
_scope_epochs: Dict[str, int] = {}


# ---------------------------------------------------------------------------
# 配置读取
# ---------------------------------------------------------------------------

def _load_config() -> Dict[str, Any]:
    """读取环境注册表（失败时返回空配置，调用方自行兜底）。"""
    try:
        from ..env.environment_config_manager import EnvironmentConfigManager

        return EnvironmentConfigManager().load_config() or {}
    except Exception as exc:  # pragma: no cover - 兜底分支
        logger.debug(f"[scope] 读取注册表失败：{exc}")
        return {}


def _user_root() -> Path:
    from ...utils.paths import get_user_data_root

    return Path(get_user_data_root())


def _root_id(env: Dict[str, Any]) -> str:
    return str(env.get("id") or env.get("name") or "")


def _new_space_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


# ---------------------------------------------------------------------------
# 注册表补全（旧配置兼容）
# ---------------------------------------------------------------------------

def _pick_default_package_id(config: Dict[str, Any], packages: List[Dict[str, Any]]) -> str:
    current = config.get("current_package_id")
    if current and any(p.get("id") == current for p in packages):
        return current
    for pkg in packages:
        if pkg.get("is_default"):
            return str(pkg.get("id"))
    return str(packages[0].get("id")) if packages else DEFAULT_PACKAGE_ID


def _root_private_path(env: Dict[str, Any]) -> str:
    """计算某根默认私有数据空间路径（只计算，不创建、不迁移）。"""
    env_type = str(env.get("env_type") or env.get("envType") or "portable")
    desktop_path = env.get("desktop_data_path") or env.get("desktopDataPath")
    if env_type == "desktop" and desktop_path:
        return str(Path(str(desktop_path)) / "comfyui-box")
    comfy_path = env.get("path")
    if comfy_path:
        return str(Path(str(comfy_path)) / "user" / "comfyui-box")
    return str(_user_root() / "spaces" / _root_id(env))


def normalize_registry(config: Dict[str, Any]) -> bool:
    """
    就地补全注册表字段，返回是否有改动。

    规则：
    - 无 packages / data_spaces 时，建立默认包与旧版用户数据空间；
    - 默认包的全局空间指向旧版用户数据根（零搬迁）；
    - 每个环境补 package_id / data_space_id / scope_overrides；
    - 缺失的私有空间记录自动补建（只建记录，目录按需创建）。
    """
    if not isinstance(config, dict):
        return False

    changed = False
    spaces: List[Dict[str, Any]] = list(config.get("data_spaces") or [])
    packages: List[Dict[str, Any]] = list(config.get("packages") or [])

    user_root = str(_user_root())
    legacy_space = next((s for s in spaces if s.get("id") == LEGACY_SPACE_ID), None)
    if legacy_space is None:
        legacy_space = {
            "id": LEGACY_SPACE_ID,
            "name": LEGACY_SPACE_NAME,
            "path": user_root,
            "layout": "legacy",
            "is_global": True,
            "created_at": _now(),
        }
        spaces.append(legacy_space)
        changed = True

    if not packages:
        packages = [
            {
                "id": DEFAULT_PACKAGE_ID,
                "name": DEFAULT_PACKAGE_NAME,
                "is_default": True,
                "global_space_id": LEGACY_SPACE_ID,
                "scope_defaults": dict(LEGACY_PACKAGE_DEFAULTS),
                "created_at": _now(),
            }
        ]
        changed = True

    # 补全包字段
    for pkg in packages:
        if not pkg.get("id"):
            pkg["id"] = DEFAULT_PACKAGE_ID
            changed = True
        if "is_default" not in pkg:
            pkg["is_default"] = False
            changed = True
        if not pkg.get("global_space_id"):
            pkg["global_space_id"] = LEGACY_SPACE_ID
            changed = True
        defaults = pkg.get("scope_defaults")
        if not isinstance(defaults, dict):
            defaults = {}
            pkg["scope_defaults"] = defaults
            changed = True
        for category, spec in CATEGORY_SPECS.items():
            if category not in defaults:
                # 默认包沿用旧行为；其他包使用推荐默认值
                if pkg.get("id") == DEFAULT_PACKAGE_ID and pkg.get("is_default"):
                    defaults[category] = LEGACY_PACKAGE_DEFAULTS.get(category, spec["default_mode"])
                else:
                    defaults[category] = spec["default_mode"]
                changed = True

    package_ids = {str(p.get("id")) for p in packages}
    current_package_id = _pick_default_package_id(config, packages)
    if config.get("current_package_id") != current_package_id:
        config["current_package_id"] = current_package_id
        changed = True

    # 补全环境绑定
    for env in config.get("environments") or []:
        if not isinstance(env, dict):
            continue
        env_id = _root_id(env)
        package_id = env.get("package_id")
        if not package_id or package_id not in package_ids:
            env["package_id"] = current_package_id
            changed = True
            package_id = current_package_id

        overrides = env.get("scope_overrides")
        if not isinstance(overrides, dict):
            env["scope_overrides"] = {}
            changed = True

        space_id = env.get("data_space_id")
        if not space_id or not any(s.get("id") == space_id for s in spaces):
            space_id = f"ds_root_{env_id}" if env_id else _new_space_id("ds_root")
            env["data_space_id"] = space_id
            changed = True

        if not any(s.get("id") == space_id for s in spaces):
            spaces.append(
                {
                    "id": space_id,
                    "name": f"{env.get('name') or env_id} 私有空间",
                    "path": _root_private_path(env),
                    "layout": "custom",
                    "package_id": package_id,
                    "is_global": False,
                    "created_at": _now(),
                }
            )
            changed = True

    if changed:
        config["packages"] = packages
        config["data_spaces"] = spaces
    return changed


def get_registry_snapshot(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """返回注册表快照（已补全），供矩阵 / manifest 使用。"""
    cfg = dict(config or _load_config())
    normalize_registry(cfg)
    return cfg


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------

def _context(config: Dict[str, Any], root_id: Optional[str]) -> Tuple[Optional[Dict], Dict[str, Dict], Optional[Dict]]:
    packages = {str(p.get("id")): p for p in config.get("packages") or [] if p.get("id")}
    spaces = {str(s.get("id")): s for s in config.get("data_spaces") or [] if s.get("id")}
    envs = config.get("environments") or []
    if root_id:
        env = next((e for e in envs if _root_id(e) == str(root_id)), None)
    else:
        current_id = config.get("current_environment_id")
        env = next((e for e in envs if _root_id(e) == str(current_id)), None)
        if env is None and envs:
            env = envs[0]
    pkg = None
    if env:
        pkg = packages.get(str(env.get("package_id")))
    if pkg is None:
        current_pkg = config.get("current_package_id") or DEFAULT_PACKAGE_ID
        pkg = packages.get(str(current_pkg))
    if pkg is None and packages:
        pkg = next(iter(packages.values()))
    return pkg, spaces, env


def _category_path_from_space(space: Dict[str, Any], category: str) -> Path:
    spec = CATEGORY_SPECS[category]
    return Path(str(space.get("path"))).joinpath(*spec["subpath"].split("/"))


def _workflow_runtime() -> Dict[str, Any]:
    """读取旧版工作流配置（用于 use_global_path 兼容映射）。"""
    try:
        from ..config import WorkflowConfigManager

        return WorkflowConfigManager().load_config() or {}
    except Exception:
        return {}


def _resolve_workflow_path(
    mode: str,
    space: Optional[Dict[str, Any]],
    env: Optional[Dict[str, Any]],
    space_id: Optional[str],
) -> Path:
    wf_cfg = _workflow_runtime()
    if mode == "global":
        global_path = wf_cfg.get("global_path")
        if global_path:
            return Path(str(global_path))
        # 兼容旧行为：全局开关打开但未指定目录时，仍使用当前根的原生工作流目录
        env_paths = wf_cfg.get("env_paths") or {}
        if env is not None:
            env_id = _root_id(env)
            if env_id and env_paths.get(env_id):
                return Path(str(env_paths[env_id]))
            comfy_path = env.get("path")
            if comfy_path:
                return Path(str(comfy_path)) / "user" / "default" / "workflows"
        return _user_root() / "workflows"
    if mode == "private" and env is not None:
        env_paths = wf_cfg.get("env_paths") or {}
        env_id = _root_id(env)
        if env_id and env_paths.get(env_id):
            return Path(str(env_paths[env_id]))
        comfy_path = env.get("path")
        if comfy_path:
            return Path(str(comfy_path)) / "user" / "default" / "workflows"
        return _user_root() / "workflows"
    if space is not None:
        return Path(str(space.get("path"))) / "workflows"
    return _user_root() / "workflows"


def _has_explicit_workflow_override(env: Optional[Dict[str, Any]]) -> bool:
    if not env:
        return False
    overrides = env.get("scope_overrides") or {}
    return "workflows" in overrides


def resolve_scope(
    category: str,
    root_id: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    解析某类数据在指定根（缺省为当前环境）下的物理落点。

    Returns:
        {
          category, mode, space_id, space_path, path, source,
          is_file, exists, epoch, note
        }
    """
    if category not in CATEGORY_SPECS:
        raise ValueError(f"未知数据类别：{category}")

    cfg = config if config is not None else _load_config()
    normalize_registry(cfg)
    pkg, spaces, env = _context(cfg, root_id)
    spec = CATEGORY_SPECS[category]
    epoch = get_scope_epoch(category, root_id)

    if env is None or pkg is None:
        # 无注册表/无环境：回退旧路径，保证读取不报错
        legacy = _user_root().joinpath(*spec["subpath"].split("/"))
        return {
            "category": category,
            "mode": "legacy",
            "space_id": LEGACY_SPACE_ID,
            "space_path": str(_user_root()),
            "path": str(legacy),
            "source": "fallback",
            "is_file": bool(spec.get("is_file")),
            "exists": legacy.exists(),
            "epoch": epoch,
            "note": "未找到环境注册表，使用旧版用户数据路径",
        }

    overrides = env.get("scope_overrides") or {}
    entry = overrides.get(category) if isinstance(overrides.get(category), dict) else None

    source = "override"
    mode = None
    space_id = None
    if entry:
        mode = entry.get("mode")
        space_id = entry.get("space_id")
    if not mode:
        # 工作流旧开关兼容：未显式写 scope 时按 use_global_path 推导
        if category == "workflows":
            wf_cfg = _workflow_runtime()
            if not _has_explicit_workflow_override(env) and wf_cfg.get("use_global_path"):
                mode = "global"
                source = "legacy_alias"
        if not mode:
            defaults = pkg.get("scope_defaults") or {}
            mode = defaults.get(category) or spec["default_mode"]
            source = "package_default"
    if mode not in ("global", "private", "custom"):
        mode = spec["default_mode"]
        source = "package_default"

    if mode == "global":
        space_id = str(pkg.get("global_space_id") or LEGACY_SPACE_ID)
    elif mode == "private":
        space_id = str(env.get("data_space_id") or f"ds_root_{_root_id(env)}")
    elif mode == "custom":
        space_id = str(space_id or env.get("data_space_id"))

    space = spaces.get(space_id)
    if mode != "private" and space is None and space_id == LEGACY_SPACE_ID:
        space = {"id": LEGACY_SPACE_ID, "path": str(_user_root()), "layout": "legacy"}
    if space is None:
        # 引用失效：降级为私有空间并标注
        space_id = str(env.get("data_space_id") or f"ds_root_{_root_id(env)}")
        space = spaces.get(space_id)
        mode = "private"
        source = "invalid_reference"

    if category == "workflows":
        path = _resolve_workflow_path(mode, space, env, space_id)
    elif space is None:
        path = _user_root().joinpath(*spec["subpath"].split("/"))
    else:
        path = _category_path_from_space(space, category)

    return {
        "category": category,
        "mode": mode,
        "space_id": space_id,
        "space_path": str(space.get("path")) if space else str(_user_root()),
        "path": str(path),
        "source": source,
        "is_file": bool(spec.get("is_file")),
        "exists": path.exists(),
        "epoch": epoch,
        "note": "",
    }


def _ensure_space_marker(resolved: Dict[str, Any]) -> None:
    """
    为非旧版数据空间写入目录标记，供 manifest 导入时识别「路径存在但 id 不符」。

    旧版用户数据根不加标记，避免触碰现有数据。
    """
    space_id = str(resolved.get("space_id") or "")
    space_path = Path(str(resolved.get("space_path") or ""))
    if not space_id or space_id == LEGACY_SPACE_ID or not space_path.exists():
        return
    marker = space_path / ".comfyui-box-space.json"
    if marker.exists():
        return
    try:
        marker.write_text(
            json.dumps({"space_id": space_id, "marker_version": 1}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.debug(f"[scope] 写入空间标记失败 {marker}：{exc}")


def resolve_category_path(category: str, root_id: Optional[str] = None) -> Path:
    """便捷方法：直接返回物理路径并确保目录存在（文件类只保证父目录）。"""
    resolved = resolve_scope(category, root_id=root_id)
    path = Path(resolved["path"])
    try:
        if resolved["is_file"]:
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            path.mkdir(parents=True, exist_ok=True)
        _ensure_space_marker(resolved)
    except Exception as exc:
        logger.warning(f"[scope] 创建目录失败 {path}：{exc}")
    return path


# ---------------------------------------------------------------------------
# 绑定写入与 epoch
# ---------------------------------------------------------------------------

def _epoch_key(package_id: str, root_id: str, category: str) -> str:
    return f"{package_id}:{root_id}:{category}"


def get_scope_epoch(category: str, root_id: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> int:
    """返回 scope 版本号；绑定变化后递增，调用方用它作为缓存键的一部分。"""
    cfg = config if config is not None else _load_config()
    normalize_registry(cfg)
    pkg, _spaces, env = _context(cfg, root_id)
    package_id = str((pkg or {}).get("id") or DEFAULT_PACKAGE_ID)
    env_id = _root_id(env) if env else ""
    if env_id:
        return int(_scope_epochs.get(_epoch_key(package_id, env_id, category), 0))
    return int(_scope_epochs.get(f"global:{category}", 0))


def bump_scope_epoch(category: str, package_id: str, root_id: str) -> int:
    """递增 scope 版本号并返回新值。"""
    global _epoch_counter
    with _epoch_lock:
        _epoch_counter += 1
        key = _epoch_key(package_id, root_id, category)
        _scope_epochs[key] = _epoch_counter
        if not root_id:
            _scope_epochs[f"global:{category}"] = _epoch_counter
        return _epoch_counter


def set_scope(
    category: str,
    mode: str,
    root_id: Optional[str] = None,
    space_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    写入某根某类数据的 scope 绑定。

    不迁移任何数据；只更新注册表并递增 epoch。
    工作流同时写回旧开关 ``use_global_path``，保持旧设置界面行为一致。
    """
    if category not in SWITCHABLE_CATEGORIES:
        raise ValueError(f"该数据类别不支持切换：{category}")
    if mode not in ("global", "private", "custom"):
        raise ValueError(f"非法 scope 模式：{mode}")

    from ..env.environment_config_manager import EnvironmentConfigManager

    manager = EnvironmentConfigManager()
    config = manager.load_config()
    normalize_registry(config)
    _pkg, spaces, env = _context(config, root_id)
    if env is None:
        raise ValueError("未找到目标环境")

    if mode == "custom":
        if not space_id or space_id not in spaces:
            raise ValueError("custom 模式需要有效的 space_id")
        space = spaces[space_id]
        if str(space.get("package_id") or env.get("package_id")) != str(env.get("package_id")):
            raise ValueError("不能绑定到其他包的数据空间")

    overrides = env.setdefault("scope_overrides", {})
    overrides[category] = {"mode": mode, "space_id": space_id if mode == "custom" else None, "updated_at": _now()}
    manager.save_config(config)

    if category == "workflows":
        _sync_workflow_legacy_flag(mode == "global")

    package_id = str(env.get("package_id") or DEFAULT_PACKAGE_ID)
    bump_scope_epoch(category, package_id, _root_id(env))
    return resolve_scope(category, root_id=_root_id(env), config=config)


def _sync_workflow_legacy_flag(use_global_path: bool) -> None:
    """把 scope 绑定投影回旧工作流开关，避免两套界面互相打架。"""
    try:
        from ..config import WorkflowConfigManager

        wf = WorkflowConfigManager()
        cfg = wf.load_config() or {}
        if bool(cfg.get("use_global_path")) != bool(use_global_path):
            cfg["use_global_path"] = bool(use_global_path)
            wf.save_config(cfg)
    except Exception as exc:
        logger.warning(f"[scope] 同步工作流旧开关失败：{exc}")


def bind_environment(config: Dict[str, Any], env: Dict[str, Any], package_id: Optional[str] = None) -> Dict[str, Any]:
    """为新环境写入默认包与私有空间绑定（由环境创建/导入流程调用）。"""
    normalize_registry(config)
    env_id = _root_id(env)
    env.setdefault("package_id", package_id or config.get("current_package_id") or DEFAULT_PACKAGE_ID)
    env.setdefault("scope_overrides", {})
    space_id = env.get("data_space_id")
    spaces = list(config.get("data_spaces") or [])
    if not space_id or not any(s.get("id") == space_id for s in spaces):
        space_id = f"ds_root_{env_id}"
        env["data_space_id"] = space_id
        spaces.append(
            {
                "id": space_id,
                "name": f"{env.get('name') or env_id} 私有空间",
                "path": _root_private_path(env),
                "layout": "custom",
                "package_id": env.get("package_id"),
                "is_global": False,
                "created_at": _now(),
            }
        )
        config["data_spaces"] = spaces
    return env


def remove_environment_binding(config: Dict[str, Any], env_id: str) -> None:
    """移除环境时清理其私有空间记录（不删除任何真实文件）。"""
    spaces = list(config.get("data_spaces") or [])
    remaining_envs = [_root_id(e) for e in config.get("environments") or [] if _root_id(e) != env_id]
    kept = []
    for space in spaces:
        space_id = str(space.get("id"))
        if space_id.startswith("ds_root_"):
            owner = space_id[len("ds_root_"):]
            if owner == env_id and owner not in remaining_envs:
                continue
        kept.append(space)
    config["data_spaces"] = kept


# ---------------------------------------------------------------------------
# 影响面预览 / 设置页矩阵
# ---------------------------------------------------------------------------

def _count_items(path: Path, is_file: bool) -> Optional[int]:
    try:
        if is_file:
            return 1 if path.exists() else 0
        if not path.exists():
            return 0
        return sum(1 for item in path.iterdir() if item.is_file() or item.is_dir())
    except Exception:
        return None


def preview_scope_change(
    category: str,
    mode: str,
    root_id: Optional[str] = None,
    space_id: Optional[str] = None,
) -> Dict[str, Any]:
    """切换前影响面：当前路径 / 目标路径 / 目标是否存在 / 不自动迁移声明。"""
    if category not in SWITCHABLE_CATEGORIES:
        raise ValueError(f"该数据类别不支持切换：{category}")
    current = resolve_scope(category, root_id=root_id)

    # 临时构造目标解析，不落盘
    cfg = _load_config()
    normalize_registry(cfg)
    _pkg, spaces, env = _context(cfg, root_id)
    if env is None:
        raise ValueError("未找到目标环境")
    overrides = env.setdefault("scope_overrides", {})
    previous = dict(overrides.get(category) or {})
    overrides[category] = {"mode": mode, "space_id": space_id}
    target = resolve_scope(category, root_id=_root_id(env), config=cfg)
    if previous:
        overrides[category] = previous
    else:
        overrides.pop(category, None)

    return {
        "success": True,
        "category": category,
        "mode": mode,
        "current": {
            "mode": current["mode"],
            "path": current["path"],
            "items": _count_items(Path(current["path"]), current["is_file"]),
        },
        "target": {
            "space_id": target["space_id"],
            "path": target["path"],
            "exists": target["exists"],
            "items": _count_items(Path(target["path"]), target["is_file"]),
        },
        "auto_migration": False,
        "message": "切换只改变读取路径，不会迁移或清除任何现有数据；原路径数据保持原位。",
    }


def get_scope_matrix() -> Dict[str, Any]:
    """设置页统一矩阵数据：类别 × 根，以及包 / 空间元信息。"""
    cfg = get_registry_snapshot()
    roots = []
    values: Dict[str, Dict[str, Any]] = {}
    for env in cfg.get("environments") or []:
        env_id = _root_id(env)
        roots.append(
            {
                "id": env_id,
                "name": env.get("name") or env_id,
                "path": env.get("path") or "",
                "package_id": env.get("package_id"),
                "data_space_id": env.get("data_space_id"),
            }
        )
        values[env_id] = {}
        for category in SWITCHABLE_CATEGORIES:
            resolved = resolve_scope(category, root_id=env_id, config=cfg)
            values[env_id][category] = {
                "mode": resolved["mode"],
                "space_id": resolved["space_id"],
                "path": resolved["path"],
                "source": resolved["source"],
                "exists": resolved["exists"],
                "epoch": resolved["epoch"],
            }

    return {
        "success": True,
        "categories": [
            {
                "key": key,
                "label": spec["label"],
                "default_mode": spec["default_mode"],
            }
            for key, spec in CATEGORY_SPECS.items()
            if spec.get("switchable")
        ],
        "roots": roots,
        "packages": cfg.get("packages") or [],
        "data_spaces": cfg.get("data_spaces") or [],
        "values": values,
        "current_environment_id": cfg.get("current_environment_id"),
        "current_package_id": cfg.get("current_package_id"),
        "non_switchable": [
            {"key": "models", "label": "模型目录", "reason": "按根原生目录读取，仅通过共享模型目录引用共享"},
            {"key": "plugins", "label": "插件与插件安装目录", "reason": "与 ComfyUI 根绑定，切换会造成运行失败"},
            {"key": "deps", "label": "依赖/版本/Python/端口", "reason": "环境运行参数，必须按根隔离"},
            {"key": "secrets", "label": "密钥与加密材料", "reason": "系统级安全材料，不随业务数据切换"},
            {"key": "settings", "label": "界面/语言/主题", "reason": "系统级用户体验设置"},
            {"key": "update_cache", "label": "更新缓存", "reason": "系统级共享缓存"},
        ],
    }
