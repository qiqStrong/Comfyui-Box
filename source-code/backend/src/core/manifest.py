"""
索引文件（manifest）导出 / 导入。

定位：manifest 是**快照**，不是真源。导入后写回 ``environments.json`` 注册表，
默认不改变机器级 ``userdata.location`` 指针。

安全边界：
- 密钥、API Key、加密材料、环境变量值绝不写入文件（只记录变量名）；
- 导入前备份注册表与指针，应用失败自动回滚；
- manifest 中的目录不存在时按只读失效引用导入，不自动创建/复制数据。
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils import paths
from ..utils.logger import app_logger as logger
from .scope import CATEGORY_SPECS, normalize_registry

MANIFEST_KIND = "comfyui-box-manifest"
SCHEMA_VERSION = 2
SPACE_MARKER_FILENAME = ".comfyui-box-space.json"


def _app_version() -> str:
    try:
        from comfyui_box_version import __version__

        return str(__version__)
    except Exception:
        return "unknown"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return {}


def _sha256_file(path: Path, max_bytes: int = 50 * 1024 * 1024) -> Optional[str]:
    if not path.exists() or path.is_dir():
        return None
    try:
        if path.stat().st_size > max_bytes:
            return None
        digest = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _canonical(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _read_space_marker(space_path: Path) -> Optional[Dict[str, Any]]:
    marker = space_path / SPACE_MARKER_FILENAME
    if not marker.exists():
        return None
    data = _safe_json(marker)
    return data if isinstance(data, dict) else None


def _env_var_names(raw: str) -> List[str]:
    """从多行 ``KEY=VALUE`` 中只提取变量名，绝不导出值。"""
    names: List[str] = []
    for line in str(raw or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key:
            names.append(key)
    return names


def _space_counts(space_path: Path) -> Dict[str, Any]:
    """统计某个数据空间内各业务类别的存在性与数量（导入预览用）。"""
    result: Dict[str, Any] = {}
    if not space_path.exists():
        return {cat: {"exists": False, "items": 0} for cat in CATEGORY_SPECS}

    for category, spec in CATEGORY_SPECS.items():
        path = space_path.joinpath(*spec["subpath"].split("/"))
        entry: Dict[str, Any] = {"path": str(path), "exists": path.exists()}
        if category == "gallery":
            assets = _safe_json(path / "assets.json")
            entry["items"] = len(assets.get("assets") or []) if isinstance(assets, dict) else 0
            entry["thumbnails"] = len(list((path / "thumbnails").glob("*"))) if (path / "thumbnails").exists() else 0
            entry["checksum"] = _sha256_file(path / "assets.json")
        elif category == "prompts":
            entry["items"] = len(list(path.glob("*.json"))) if path.exists() else 0
            entry["checksum"] = _sha256_file(path / "prompts.json")
        elif category == "ai":
            entry["items"] = 1 if path.exists() else 0
            entry["bytes"] = path.stat().st_size if path.exists() else 0
        elif category == "workflows":
            entry["items"] = len([p for p in path.rglob("*") if p.is_file()]) if path.exists() else 0
        elif category == "lora":
            models = _safe_json(path / "models.json")
            entry["items"] = len(models.get("models") or []) if isinstance(models, dict) else 0
            entry["checksum"] = _sha256_file(path / "models.json")
        result[category] = entry
    return result


def _sanitize_environment(env: Dict[str, Any], space_counts: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """导出环境关键参数；剥离环境变量值与任何可能的密钥字段。"""
    config = env.get("config") or {}
    general = config.get("general") or {}
    acceleration = config.get("acceleration") or {}
    launch_keys = (
        "port",
        "listen",
        "listen_address",
        "base_directory",
        "input_directory",
        "output_directory",
        "temp_directory",
        "user_directory",
        "extra_model_paths_config",
        "preview_method",
        "preview_size",
        "disable_all_custom_nodes",
        "enable_manager",
        "compute_device",
        "vram_mode",
        "use_cpu",
        "use_gpu_only",
        "reserve_vram",
        "unet_precision",
        "vae_precision",
        "text_enc_precision",
        "attention_type",
        "disable_xformers",
        "disable_smart_memory",
        "force_channels_last",
        "cache_lru",
        "deterministic",
        "fast_mode",
        "cuda_malloc",
        "enable_cors",
        "verbose",
        "disable_metadata",
        "geek_mode",
    )
    return {
        "id": env.get("id"),
        "name": env.get("name"),
        "alias": env.get("alias"),
        "path": env.get("path"),
        "version": env.get("version") or "",
        "env_type": env.get("envType") or env.get("env_type") or "portable",
        "desktop_data_path": env.get("desktopDataPath") or env.get("desktop_data_path") or "",
        "python_path": general.get("python_path") or "",
        "pip_path": general.get("pip_path") or "",
        "git_path": general.get("git_path") or "",
        "launch": {key: acceleration.get(key) for key in launch_keys if key in acceleration},
        # 只保留变量名，绝不包含值
        "env_var_names": _env_var_names(config.get("advanced_env_vars") or ""),
        "package_id": env.get("package_id"),
        "data_space_id": env.get("data_space_id"),
        "scope_overrides": env.get("scope_overrides") or {},
    }


def export_manifest() -> Dict[str, Any]:
    """导出当前注册表快照（JSON 可序列化）。"""
    from ..core.env.environment_config_manager import EnvironmentConfigManager

    config = EnvironmentConfigManager().load_config()
    normalize_registry(config)

    spaces = []
    for space in config.get("data_spaces") or []:
        space_path = Path(str(space.get("path") or ""))
        marker = _read_space_marker(space_path) if space_path.exists() else None
        spaces.append(
            {
                "id": space.get("id"),
                "name": space.get("name"),
                "path": space.get("path"),
                "layout": space.get("layout") or "custom",
                "package_id": space.get("package_id"),
                "is_global": bool(space.get("is_global")),
                "marker": marker,
                "counts": _space_counts(space_path),
            }
        )

    space_counts = {s["id"]: s.get("counts") or {} for s in spaces}

    roots = [
        _sanitize_environment(env, space_counts)
        for env in (config.get("environments") or [])
        if isinstance(env, dict)
    ]

    payload: Dict[str, Any] = {
        "kind": MANIFEST_KIND,
        "schema_version": SCHEMA_VERSION,
        "app_version": _app_version(),
        "exported_at": _now_iso(),
        "pointers": {
            "userdata_root": str(paths.get_user_data_root()),
            "userdata_pointer_file": str(paths.get_userdata_pointer_file()),
            "userdata_source": paths.get_user_data_source(),
        },
        "default_package_id": config.get("current_package_id"),
        "current_environment_id": config.get("current_environment_id"),
        "packages": config.get("packages") or [],
        "data_spaces": spaces,
        "roots": roots,
        "secrets_included": False,
    }
    payload["integrity"] = {
        "algorithm": "sha256",
        "digest": hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest(),
    }
    return payload


# ---------------------------------------------------------------------------
# 校验 / 预览
# ---------------------------------------------------------------------------

def validate_manifest(data: Any) -> Dict[str, Any]:
    """校验 manifest 结构与完整性，返回 {valid, errors, warnings}。"""
    errors: List[str] = []
    warnings: List[str] = []
    if not isinstance(data, dict):
        return {"valid": False, "errors": ["manifest 必须是 JSON 对象"], "warnings": []}
    if data.get("kind") != MANIFEST_KIND:
        errors.append("不是 ComfyUI-Box 索引文件（kind 不匹配）")
    version = data.get("schema_version")
    if not isinstance(version, int) or version < 1:
        errors.append("缺少有效的 schema_version")
    elif version > SCHEMA_VERSION:
        errors.append(f"索引版本过新（{version} > {SCHEMA_VERSION}），请升级应用")
    for key in ("packages", "data_spaces", "roots"):
        if not isinstance(data.get(key), list):
            errors.append(f"缺少或非法的字段：{key}")

    integrity = data.get("integrity") or {}
    digest = integrity.get("digest")
    if digest:
        clone = {k: v for k, v in data.items() if k != "integrity"}
        actual = hashlib.sha256(_canonical(clone).encode("utf-8")).hexdigest()
        if actual != digest:
            errors.append("索引内容校验失败（integrity 不一致），文件可能被修改")
    else:
        warnings.append("索引未包含 integrity 校验值")

    spaces = data.get("data_spaces") or []
    ids = [s.get("id") for s in spaces if isinstance(s, dict)]
    if len(ids) != len(set(ids)):
        errors.append("data_spaces 存在重复 id")
    if not data.get("default_package_id"):
        warnings.append("未声明 default_package_id")
    return {"valid": not errors, "errors": errors, "warnings": warnings}


def _normalize_path(path: str | Path) -> str:
    try:
        return os.path.normcase(str(Path(path).resolve()))
    except Exception:
        return os.path.normcase(str(path))


def preview_import(data: Dict[str, Any]) -> Dict[str, Any]:
    """导入影响预览：逐空间/根给出 ok/missing/conflict 状态与数量。"""
    validation = validate_manifest(data)
    if not validation["valid"]:
        return {"success": False, "validation": validation, "items": [], "summary": {}}

    from ..core.env.environment_config_manager import EnvironmentConfigManager

    config = EnvironmentConfigManager().load_config()
    normalize_registry(config)
    local_spaces = {str(s.get("id")): s for s in config.get("data_spaces") or []}
    local_envs = {str(e.get("id")): e for e in config.get("environments") or []}
    local_paths = {_normalize_path(s.get("path")): str(s.get("id")) for s in local_spaces.values()}

    items: List[Dict[str, Any]] = []
    summary = {"ok": 0, "missing": 0, "conflict": 0, "roots_ok": 0, "roots_missing": 0, "roots_conflict": 0}

    for space in data.get("data_spaces") or []:
        space_id = str(space.get("id"))
        path = Path(str(space.get("path") or ""))
        status = "ok"
        reason = ""
        if not path.exists():
            status = "missing"
            reason = "目录不存在"
        else:
            marker = _read_space_marker(path)
            if marker and str(marker.get("space_id")) != space_id:
                status = "conflict"
                reason = f"目录标记指向其他空间：{marker.get('space_id')}"
            elif local_spaces.get(space_id) and _normalize_path(local_spaces[space_id].get("path")) != _normalize_path(path):
                status = "conflict"
                reason = "同一空间 id 在本机指向不同路径"
            elif local_paths.get(_normalize_path(path)) not in (None, space_id):
                status = "conflict"
                reason = f"该目录已被本机空间 {local_paths[_normalize_path(path)]} 使用"
        summary[status] += 1
        items.append(
            {
                "kind": "space",
                "id": space_id,
                "name": space.get("name"),
                "path": str(path),
                "status": status,
                "reason": reason,
                "counts": space.get("counts") or {},
            }
        )

    for root in data.get("roots") or []:
        root_id = str(root.get("id"))
        path = Path(str(root.get("path") or ""))
        status = "ok"
        reason = ""
        local = local_envs.get(root_id)
        if not path.exists():
            status = "missing"
            reason = "ComfyUI 目录不存在，将导入为只读失效引用"
        elif local and _normalize_path(local.get("path")) != _normalize_path(path):
            status = "conflict"
            reason = "同一环境 id 在本机指向不同路径"
        else:
            duplicate = next(
                (
                    str(e.get("id"))
                    for e in local_envs.values()
                    if str(e.get("id")) != root_id and _normalize_path(e.get("path")) == _normalize_path(path)
                ),
                None,
            )
            if duplicate:
                status = "conflict"
                reason = f"该 ComfyUI 路径已被环境 {duplicate} 使用"
        key = "roots_" + status
        summary[key] += 1
        items.append(
            {
                "kind": "root",
                "id": root_id,
                "name": root.get("name"),
                "path": str(path),
                "status": status,
                "reason": reason,
            }
        )

    return {
        "success": True,
        "validation": validation,
        "items": items,
        "summary": summary,
        "packages": data.get("packages") or [],
        "secrets_included": bool(data.get("secrets_included")),
        "message": "导入只写配置与引用，不会复制或迁移真实数据。",
    }


# ---------------------------------------------------------------------------
# 导入
# ---------------------------------------------------------------------------

def _backup_registry() -> Optional[Path]:
    """备份 environments.json 与指针内容，返回备份目录（失败返回 None）。"""
    config_file = Path(paths.get_config_dir()) / "environments.json"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path(paths.get_user_data_root()) / "backup" / f"manifest_import_{stamp}"
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        if config_file.exists():
            shutil.copy2(config_file, backup_dir / "environments.json")
        pointer = paths.get_userdata_pointer_file()
        pointer_state = {"exists": pointer.exists(), "content": None}
        if pointer.exists():
            pointer_state["content"] = pointer.read_text(encoding="utf-8", errors="replace")
        (backup_dir / "pointer.json").write_text(
            json.dumps(pointer_state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return backup_dir
    except Exception as exc:
        logger.error(f"[manifest] 备份注册表失败：{exc}")
        return None


def _restore_backup(backup_dir: Optional[Path]) -> None:
    if not backup_dir:
        return
    config_file = Path(paths.get_config_dir()) / "environments.json"
    try:
        backup_config = backup_dir / "environments.json"
        if backup_config.exists():
            shutil.copy2(backup_config, config_file)
        pointer_state_file = backup_dir / "pointer.json"
        if pointer_state_file.exists():
            state = _safe_json(pointer_state_file)
            pointer = paths.get_userdata_pointer_file()
            if state.get("exists") and state.get("content"):
                pointer.parent.mkdir(parents=True, exist_ok=True)
                pointer.write_text(str(state["content"]), encoding="utf-8")
            elif pointer.exists():
                pointer.unlink()
        logger.warning("[manifest] 导入失败，已回滚注册表与指针")
    except Exception as exc:
        logger.error(f"[manifest] 回滚失败：{exc}")


def import_manifest(data: Dict[str, Any], options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    导入 manifest。

    options:
        overwrite: 冲突项是否覆盖（默认 False）
        update_pointer: 是否切换 userdata.location 指针（默认 False，需显式确认）
        selected_space_ids / selected_root_ids / selected_package_ids: 部分导入
    """
    options = options or {}
    preview = preview_import(data)
    if not preview.get("success"):
        return {"success": False, "preview": preview, "error": "索引校验失败"}

    overwrite = bool(options.get("overwrite"))
    update_pointer = bool(options.get("update_pointer"))
    selected_spaces = set(options.get("selected_space_ids") or [])
    selected_roots = set(options.get("selected_root_ids") or [])
    selected_packages = set(options.get("selected_package_ids") or [])

    from ..core.env.environment_config_manager import EnvironmentConfigManager

    manager = EnvironmentConfigManager()
    backup_dir = _backup_registry()
    if backup_dir is None:
        return {"success": False, "error": "无法备份现有注册表，已中止导入"}

    applied = {"packages": 0, "data_spaces": 0, "roots": 0, "skipped": 0}
    try:
        config = manager.load_config()
        normalize_registry(config)

        items_by_id = {str(item.get("id")): item for item in preview["items"]}

        # 1. 包
        packages = list(config.get("packages") or [])
        package_ids = {str(p.get("id")) for p in packages}
        for pkg in data.get("packages") or []:
            pkg_id = str(pkg.get("id"))
            if selected_packages and pkg_id not in selected_packages:
                continue
            if pkg_id in package_ids:
                if not overwrite:
                    applied["skipped"] += 1
                    continue
                packages = [p for p in packages if str(p.get("id")) != pkg_id]
            packages.append(dict(pkg))
            applied["packages"] += 1
        config["packages"] = packages

        # 2. 数据空间
        spaces = {str(s.get("id")): dict(s) for s in config.get("data_spaces") or []}
        for space in data.get("data_spaces") or []:
            space_id = str(space.get("id"))
            if selected_spaces and space_id not in selected_spaces:
                continue
            status = items_by_id.get(space_id, {}).get("status")
            if status == "conflict" and not overwrite:
                applied["skipped"] += 1
                continue
            record = {k: v for k, v in space.items() if k != "counts"}
            # 导入只保留引用与标记；缺失目录按失效引用记录，不创建目录
            spaces[space_id] = record
            applied["data_spaces"] += 1
        config["data_spaces"] = list(spaces.values())

        # 3. 环境（根）
        envs = {str(e.get("id")): dict(e) for e in config.get("environments") or []}
        for root in data.get("roots") or []:
            root_id = str(root.get("id"))
            if selected_roots and root_id not in selected_roots:
                continue
            status = items_by_id.get(root_id, {}).get("status")
            if status == "conflict" and not overwrite:
                applied["skipped"] += 1
                continue
            existing = envs.get(root_id, {})
            general = dict(existing.get("config", {}).get("general") or {})
            general.update(
                {
                    "python_path": root.get("python_path") or general.get("python_path", ""),
                    "pip_path": root.get("pip_path") or general.get("pip_path", ""),
                    "git_path": root.get("git_path") or general.get("git_path", ""),
                    "comfyui_path": root.get("path") or general.get("comfyui_path", ""),
                }
            )
            acceleration = dict(existing.get("config", {}).get("acceleration") or {})
            acceleration.update(root.get("launch") or {})
            # 环境变量值不属于索引内容，导入时保持为空，仅保留变量名供人工确认
            advanced_names = root.get("env_var_names") or []
            env_record = {
                **existing,
                "id": root_id,
                "name": root.get("name") or existing.get("name") or root_id,
                "alias": root.get("alias") or root.get("name") or existing.get("alias") or root_id,
                "path": root.get("path") or existing.get("path") or "",
                "version": root.get("version") or existing.get("version") or "",
                "envType": root.get("env_type") or existing.get("envType") or "portable",
                "desktopDataPath": root.get("desktop_data_path") or existing.get("desktopDataPath") or "",
                "package_id": root.get("package_id") or existing.get("package_id"),
                "data_space_id": root.get("data_space_id") or existing.get("data_space_id"),
                "scope_overrides": root.get("scope_overrides") or existing.get("scope_overrides") or {},
                "config": {
                    **(existing.get("config") or {}),
                    "general": general,
                    "acceleration": acceleration,
                    "advanced_env_vars": "",
                    "advanced_env_var_names": advanced_names,
                },
            }
            envs[root_id] = env_record
            applied["roots"] += 1
        config["environments"] = list(envs.values())

        if not config.get("current_environment_id") and config["environments"]:
            config["current_environment_id"] = str(config["environments"][0].get("id"))
        if not config.get("current_package_id") and config.get("packages"):
            config["current_package_id"] = str(config["packages"][0].get("id"))

        normalize_registry(config)
        manager.save_config(config)

        pointer_changed = False
        pointer_note = "未更改 userdata.location 指针（默认策略）"
        if update_pointer:
            manifest_root = (data.get("pointers") or {}).get("userdata_root")
            if not manifest_root:
                pointer_note = "索引未声明用户数据根，指针保持不变"
            elif paths.is_test_mode():
                pointer_note = "测试隔离模式下拒绝修改机器级指针，保持不变"
            else:
                paths.write_userdata_pointer(Path(manifest_root))
                pointer_changed = True
                pointer_note = f"已将指针切换到：{manifest_root}"

        return {
            "success": True,
            "applied": applied,
            "skipped": applied["skipped"],
            "backup_dir": str(backup_dir),
            "pointer_changed": pointer_changed,
            "pointer_note": pointer_note,
            "preview": preview,
            "message": "索引已导入；缺失目录以只读失效引用保存，未复制任何真实数据。",
        }
    except Exception as exc:
        logger.error(f"[manifest] 导入失败：{exc}", exc_info=True)
        _restore_backup(backup_dir)
        return {"success": False, "error": str(exc), "backup_dir": str(backup_dir), "rolled_back": True}


# ---------------------------------------------------------------------------
# 首启引导
# ---------------------------------------------------------------------------

def get_onboarding_state() -> Dict[str, Any]:
    """首启兜底状态：无注册表/无旧数据 → 引导新建或导入；指针失效 → 只读引导。"""
    config_file = Path(paths.get_config_dir()) / "environments.json"
    config_exists = config_file.exists()
    config: Dict[str, Any] = {}
    if config_exists:
        config = _safe_json(config_file)
    environments = config.get("environments") or []

    user_root = Path(paths.get_user_data_root())
    # 用户确认过数据目录就会写入 .initialized 标记，这是"已完成引导"的唯一可靠信号。
    # 不能用 environments.json 判断：那个文件要等用户添加 ComfyUI 环境才创建，
    # 拿它当条件会让用户点完"使用此目录"后每次启动仍然弹引导。
    initialized = paths.is_user_data_initialized(user_root)
    legacy_markers = [
        user_root / "data" / "gallery" / "assets.json",
        user_root / "data" / "prompt" / "prompts.json",
        user_root / "data" / "ai_assistant.db",
        user_root / "lora_data" / "models.json",
    ]
    has_legacy_data = any(p.exists() for p in legacy_markers)

    pointer_file = paths.get_userdata_pointer_file()
    pointer_target: Optional[str] = None
    try:
        pointer_target = pointer_file.read_text(encoding="utf-8").strip() or None
    except OSError:
        pointer_target = None
    pointer_invalid = bool(pointer_target) and not Path(pointer_target).exists()

    if pointer_invalid:
        mode = "readonly_relocate"
    elif not initialized and not config_exists and not has_legacy_data:
        mode = "new_or_import"
    else:
        mode = "normal"

    return {
        "success": True,
        "mode": mode,
        "needs_onboarding": mode != "normal",
        "config_exists": config_exists,
        "environment_count": len(environments),
        "has_legacy_data": has_legacy_data,
        "userdata_root": str(user_root),
        "pointer_file": str(pointer_file),
        "pointer_target": pointer_target,
        "pointer_invalid": pointer_invalid,
        "initialized": initialized,
        "runtime_isolated": paths.is_test_mode(),
        "message": {
            "new_or_import": "未检测到环境注册表与旧数据，请选择「新建」或「导入索引」。",
            "readonly_relocate": "用户数据目录指针失效，应用处于只读引导，请重新定位目录。",
            "normal": "数据目录正常。",
        }.get(mode, ""),
    }
