"""
用户数据层管理：首启初始化、目录迁移、清理。

设计文档见 docs/architecture/data-layout.md。

核心约束：
- 用户数据根在机器级目录（%LOCALAPPDATA%\\Comfyui-Box\\userdata 默认），
  不在项目目录内，因此换目录/换副本/重新 clone 都能读到同一份数据。
- 迁移只读源目录：不删除、不写标记，保留旧数据供回退。
- 加密密钥（data/secrets/ai_fernet.key）属于 data，随迁移一起搬；
  迁移完成后必须验证已落库的 API Key 能用新位置密钥解开。
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from backend.src.utils import paths
from backend.src.utils.logger import app_logger as logger

CATEGORY_KEYS: Tuple[str, ...] = ("data", "config", "backup", "lora_data")
BUSINESS_SUBDIRS: Tuple[str, ...] = ("data", "config", "backup", "lora_data")

# 进程启动时实际使用的用户数据根：用于判断指针变更是否需要重启
_PROCESS_START_ROOT: Optional[Path] = None
_job_lock = threading.Lock()
_job_state: Dict[str, Any] = {
    "running": False,
    "done": 0,
    "total": 0,
    "bytes_done": 0,
    "bytes_total": 0,
    "current": "",
    "result": None,
}


def _process_start_root() -> Path:
    global _PROCESS_START_ROOT
    if _PROCESS_START_ROOT is None:
        _PROCESS_START_ROOT = paths.get_user_data_root()
    return _PROCESS_START_ROOT


def _safe_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return {}


def _iter_files(root: Path) -> List[Path]:
    if not root.exists():
        return []
    return [p for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts]


def _dir_stats(root: Path) -> Dict[str, int]:
    files = _iter_files(root)
    return {"files": len(files), "bytes": sum(p.stat().st_size for p in files if p.exists())}


def _sha256(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _db_topic_count(db_path: Path) -> int:
    """只读统计 AI 对话话题数；失败返回 -1（不视为 0）。"""
    if not db_path.exists():
        return 0
    try:
        uri = f"file:{(db_path.as_posix())}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=2)
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM topics")
            return int(cursor.fetchone()[0])
        finally:
            conn.close()
    except sqlite3.Error:
        return -1


def collect_counts(root: Path | str) -> Dict[str, Any]:
    """
    统计用户数据根内的业务数据（迁移前后校验用）。

    Returns:
        dict：资产/分类/缩略图/提示词/工作流/对话/密钥等数量
    """
    root = Path(root)
    data_dir = root / "data"
    assets_file = data_dir / "gallery" / "assets.json"
    gallery = _safe_json(assets_file)
    assets = gallery.get("assets") if isinstance(gallery, dict) else None
    categories = gallery.get("categories") if isinstance(gallery, dict) else None

    prompt_dir = data_dir / "prompt"
    workflows_dir = data_dir / "workflows"
    db_path = data_dir / "ai_assistant.db"
    key_path = data_dir / "secrets" / "ai_fernet.key"
    config_dir = _source_config_dir(root)

    return {
        "root": str(root),
        "assets": len(assets) if isinstance(assets, list) else 0,
        "categories": len(categories) if isinstance(categories, list) else 0,
        "thumbnails": len(_iter_files(data_dir / "gallery" / "thumbnails")),
        "prompt_json": len(list(prompt_dir.glob("*.json"))) if prompt_dir.exists() else 0,
        "prompt_images": len(_iter_files(prompt_dir / "images")),
        "workflows_files": len(_iter_files(workflows_dir)),
        "db_exists": db_path.exists(),
        "db_bytes": db_path.stat().st_size if db_path.exists() else 0,
        "db_topics": _db_topic_count(db_path),
        "secret_key_exists": key_path.exists(),
        "secret_key_sha256": _sha256(key_path),
        "config_files": _dir_stats(config_dir)["files"],
        "backup_files": _dir_stats(root / "backup")["files"],
        "lora_files": _dir_stats(root / "lora_data")["files"],
        "data_stats": _dir_stats(data_dir),
        "config_stats": _dir_stats(config_dir),
        "backup_stats": _dir_stats(root / "backup"),
        "lora_stats": _dir_stats(root / "lora_data"),
    }


def _source_config_dir(source_root: Path) -> Path:
    """旧布局配置目录：打包态 <root>/config，开发态 <root>/backend/config。"""
    direct = source_root / "config"
    nested = source_root / "backend" / "config"
    if direct.exists():
        return direct
    return nested


def _source_category_dirs(source_root: Path) -> Dict[str, Optional[Path]]:
    return {
        "data": source_root / "data" if (source_root / "data").exists() else None,
        "config": _source_config_dir(source_root) if _source_config_dir(source_root).exists() else None,
        "backup": source_root / "backup" if (source_root / "backup").exists() else None,
        "lora_data": source_root / "lora_data" if (source_root / "lora_data").exists() else None,
    }


def detect_legacy_sources() -> List[Dict[str, Any]]:
    """
    检测旧布局中真正含有用户数据的目录（排除仅含随包默认文件的空壳）。

    Returns:
        list[dict]：{root, entries:[{kind,path,files,bytes}], counts}
    """
    project_root = paths.get_project_root()
    sources: List[Dict[str, Any]] = []

    entries = []
    for kind, path in paths.get_legacy_userdata_candidates():
        if not path.exists() or not path.is_dir():
            continue
        stats = _dir_stats(path)
        if stats["files"] == 0:
            continue
        entries.append({"kind": kind, "path": str(path), **stats})
    if not entries:
        return sources

    data_dir = project_root / "data"
    meaningful = False
    # 业务数据存在的判据：资产库/工作流/提示词有内容、对话非空、密钥存在、配置非默认
    if (data_dir / "gallery" / "assets.json").exists():
        meaningful = True
    if len(_iter_files(data_dir / "workflows")) > 0:
        meaningful = True
    if len(_iter_files(data_dir / "prompt" / "images")) > 0:
        meaningful = True
    if (data_dir / "secrets" / "ai_fernet.key").exists():
        meaningful = True
    topic_count = _db_topic_count(data_dir / "ai_assistant.db")
    if topic_count > 0:
        meaningful = True
    config_dir = _source_config_dir(project_root)
    if (config_dir / "settings.json").exists() or (config_dir / "environments.json").exists():
        meaningful = True
    if len(_iter_files(config_dir / "presets")) > 0:
        meaningful = True

    if meaningful:
        sources.append({
            "root": str(project_root),
            "entries": entries,
            "counts": collect_counts(project_root),
        })
    return sources


def get_userdata_status() -> Dict[str, Any]:
    """返回用户数据层状态，供首启弹窗与设置页使用。"""
    root = paths.get_user_data_root()
    start_root = _process_start_root()
    pointer_file = paths.get_userdata_pointer_file()
    pointer_target = None
    try:
        raw = pointer_file.read_text(encoding="utf-8").strip()
        pointer_target = raw or None
    except OSError:
        pointer_target = None

    counts = collect_counts(root)
    runtime_base, runtime_source, runtime_note = paths.resolve_runtime_dir()
    runtime_override = paths.get_runtime_data_override()
    return {
        "success": True,
        "root": str(root),
        "default_root": str(paths.get_default_user_data_root()),
        "source": paths.get_user_data_source(),
        "pointer_file": str(pointer_file),
        "pointer_target": pointer_target,
        "pointer_invalid": bool(pointer_target) and Path(pointer_target) != root,
        "initialized": paths.is_user_data_initialized(),
        "restart_required": root != start_root,
        "process_root": str(start_root),
        "project_root": str(paths.get_project_root()),
        "counts": counts,
        "fallback_reason": paths.get_user_data_resolution_note(),
        "runtime_dir": str(runtime_base),
        "runtime_default": str(paths.get_project_root()),
        "runtime_source": runtime_source,
        "runtime_override": str(runtime_override) if runtime_override else None,
        "runtime_note": runtime_note,
        "log_dir": str(paths.get_log_dir()),
        "cache_dir": str(paths.get_cache_dir()),
        "webview2_dir": str(paths.get_webview2_dir()),
        "legacy_sources": detect_legacy_sources(),
        "wipe_pending": (root / paths.WIPE_REQUEST_FILENAME).exists(),
    }


def _validate_root(path_value: str) -> Path:
    target = Path(path_value).expanduser()
    if not target.is_absolute():
        raise ValueError("数据目录必须是绝对路径")
    target = target.resolve()
    if target == paths.get_project_root().resolve():
        raise ValueError("数据目录不能是项目安装目录本身")
    target.mkdir(parents=True, exist_ok=True)
    probe = target / ".comfyui-box-write-test"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        raise ValueError(f"目录不可写: {target} ({exc})") from exc
    return target


def initialize_user_data(root: Optional[str] = None, adopt_existing: bool = True) -> Dict[str, Any]:
    """
    首启初始化：确认用户数据根并写入完成标记。

    Args:
        root: 自定义目录（绝对路径）；为空则使用当前解析结果（默认目录或已有指针）
        adopt_existing: 根目录已有内容时直接采纳，不覆盖

    说明：
        写入指针后**不在当前进程切换数据根**，避免半途读写两套路径；重启后生效。
    """
    start_root = _process_start_root()
    if root:
        target = _validate_root(root)
        paths.write_userdata_pointer(target)
        actual = target
        source = "pointer"
    else:
        actual = paths.get_user_data_root()
        source = paths.get_user_data_source()

    for sub in BUSINESS_SUBDIRS:
        (actual / sub).mkdir(parents=True, exist_ok=True)

    paths.mark_user_data_initialized(
        actual,
        {"source": source, "adopted_existing": bool(adopt_existing)},
    )
    logger.info("[用户数据] 已初始化: %s（来源 %s）", actual, source)

    status = get_userdata_status()
    if root:
        status.update({
            "root": str(actual),
            "source": source,
            "pointer_target": str(actual),
            "pointer_invalid": False,
            "initialized": True,
            "counts": collect_counts(actual),
            "process_root": str(start_root),
            "restart_required": actual != start_root,
        })
    else:
        status["restart_required"] = actual != start_root
    return status


def _carry_over_settings(old_root: Path, target: Path) -> None:
    """
    把旧数据根的 settings.json 带到新根（仅当新根还没有）。

    切换数据目录只是换位置，用户偏好不该丢：否则"不再提示"、代理、主题这类选择
    会在换目录后全部回到默认值，表现为"我每次都设置了，下次启动又恢复"。
    业务数据仍由 copy_current 决定是否迁移，这里只处理体积很小的配置文件。
    """
    source = Path(old_root) / "config" / "settings.json"
    destination = Path(target) / "config" / "settings.json"
    if destination.exists() or not source.exists():
        return
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        logger.info("[用户数据] 已继承旧目录的设置: %s", destination)
    except OSError as exc:
        logger.warning("[用户数据] 继承旧设置失败: %s", exc)


def set_user_data_root(root: str, copy_current: bool = False) -> Dict[str, Any]:
    """
    更改用户数据根（写机器级指针，重启后生效）。

    Args:
        root: 新目录绝对路径
        copy_current: 是否把当前根的数据复制过去（A→B 一键迁移）
    """
    target = _validate_root(root)
    old_root = paths.get_user_data_root()
    if target == old_root.resolve():
        return {"success": False, "error": "新目录与当前数据目录相同"}

    copied = None
    if copy_current:
        copied = _migrate_blocking(old_root, target)
        if not copied.get("success"):
            return {"success": False, "error": copied.get("error") or "迁移失败", "migration": copied}

    paths.write_userdata_pointer(target)
    paths.mark_user_data_initialized(target, {"source": "pointer"})
    # 只换位置、不复制业务数据时，仍要把用户偏好带过去，否则所有"不再提示"类
    # 选择都会重置，用户会反复看到已经关掉的弹窗。
    _carry_over_settings(old_root, target)
    logger.info("[用户数据] 数据目录已切换: %s（旧目录 %s），重启后生效", target, old_root)
    # 不重置解析缓存：当前进程继续使用旧目录，避免运行中读写两套路径
    status = get_userdata_status()
    status.update({
        "success": True,
        "root": str(target),
        "source": "pointer",
        "pointer_target": str(target),
        "pointer_invalid": False,
        "initialized": True,
        "counts": collect_counts(target),
        "process_root": str(old_root),
        "restart_required": True,
        "old_root": str(old_root),
        "migration": copied,
    })
    return status


def set_runtime_data_root(path_value: str) -> Dict[str, Any]:
    """
    设置运行数据目录（日志/缓存/WebView2 的父目录，重启后生效）。

    Args:
        path_value: 绝对路径；空字符串表示恢复默认（项目根目录）

    说明：
        该设置写入用户配置 config/settings.json → storage.runtimeDataDir，
        仅在用户明确选择时生效；默认仍是项目相对路径。当前进程的日志句柄与
        WebView2 数据目录不会热切换，因此需要重启。
    """
    value = (path_value or "").strip()
    if value:
        target = Path(value).expanduser()
        if not target.is_absolute():
            raise ValueError("运行数据目录必须是绝对路径")
        target = target.resolve()
        if target == paths.get_project_root().resolve():
            value = ""
        else:
            target.mkdir(parents=True, exist_ok=True)
            probe = target / ".comfyui-box-write-test"
            try:
                probe.write_text("ok", encoding="utf-8")
                probe.unlink()
            except OSError as exc:
                raise ValueError(f"目录不可写: {target} ({exc})") from exc
            value = str(target)

    from backend.src.core.settings_manager import SettingsManager

    result = SettingsManager().update_settings({
        paths.RUNTIME_DATA_SETTING_SECTION: {paths.RUNTIME_DATA_SETTING_KEY: value}
    })
    if not result.get("success"):
        return {"success": False, "error": result.get("message") or "保存运行数据目录失败"}

    # 清缓存让当前进程的读取立即反映新配置（日志文件句柄仍需重启才会切换）
    paths.reset_runtime_dir_cache()
    return {
        "success": True,
        "runtime_dir": str(paths.get_runtime_data_dir()),
        "runtime_source": paths.get_runtime_data_source(),
        "runtime_note": paths.get_runtime_data_resolution_note(),
        "settings_file": str(paths.get_settings_file()),
        "restart_required": True,
    }


def inspect_user_data_root(path_value: str) -> Dict[str, Any]:
    """检查目标目录是否已有业务数据（用于"仅切换"前的覆盖策略确认）。"""
    target = _validate_root(path_value)
    counts = collect_counts(target)
    return {
        "success": True,
        "path": str(target),
        "has_business": not _business_is_empty(target),
        "counts": counts,
    }


def _set_job(**kwargs) -> None:
    with _job_lock:
        _job_state.update(kwargs)


def _update_progress(done: int, current: str, bytes_done: int) -> None:
    with _job_lock:
        _job_state["done"] = done
        _job_state["current"] = current
        _job_state["bytes_done"] = bytes_done


def get_migration_status() -> Dict[str, Any]:
    """查询后台迁移任务进度。"""
    with _job_lock:
        return dict(_job_state)


def _total_stats(source_dirs: Dict[str, Optional[Path]]) -> Tuple[int, int]:
    total_files = 0
    total_bytes = 0
    for path in source_dirs.values():
        if path is None:
            continue
        stats = _dir_stats(path)
        total_files += stats["files"]
        total_bytes += stats["bytes"]
    return total_files, total_bytes


def _copy_tree(src: Path, dst: Path, on_file: Callable[[Path], None]) -> int:
    """复制目录内容到 dst（不覆盖已有文件），返回复制的文件数。"""
    copied = 0
    dst.mkdir(parents=True, exist_ok=True)
    for dirpath, _dirnames, filenames in os.walk(src):
        rel = Path(dirpath).relative_to(src)
        target_dir = dst / rel
        target_dir.mkdir(parents=True, exist_ok=True)
        for name in filenames:
            if "__pycache__" in Path(dirpath).parts:
                continue
            source_file = Path(dirpath) / name
            target_file = target_dir / name
            if target_file.exists():
                continue
            shutil.copy2(source_file, target_file)
            copied += 1
            on_file(source_file)
    return copied


def _merge_tree(
    src: Path,
    dst: Path,
    created_files: List[Path],
    created_dirs: List[Path],
    overwrite: bool,
) -> int:
    """
    把暂存目录合并到目标，记录新建路径用于回滚。

    overwrite=True 时覆盖目标已有文件（仅用于目标为全新用户数据根的场景）；
    否则只补充缺失文件，避免覆盖用户当前数据。
    """
    copied = 0
    dst.mkdir(parents=True, exist_ok=True)
    for dirpath, _dirnames, filenames in os.walk(src):
        rel = Path(dirpath).relative_to(src)
        target_dir = dst / rel
        if not target_dir.exists():
            target_dir.mkdir(parents=True, exist_ok=True)
            created_dirs.append(target_dir)
        for name in filenames:
            source_file = Path(dirpath) / name
            target_file = target_dir / name
            if target_file.exists() and not overwrite:
                continue
            if target_file.exists():
                if target_file not in created_files:
                    created_files.append(target_file)  # 覆盖已有文件时无法回滚原内容
            else:
                created_files.append(target_file)
            shutil.copy2(source_file, target_file)
            copied += 1
    return copied


def _rollback(created_files: List[Path], created_dirs: List[Path]) -> None:
    for path in reversed(created_files):
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass
    for path in sorted(created_dirs, key=lambda p: len(p.parts), reverse=True):
        try:
            if path.exists() and not any(path.iterdir()):
                path.rmdir()
        except OSError:
            pass


def _verify_fernet_key(data_dir: Path) -> Dict[str, Any]:
    """验证迁移后的密钥能解开数据库中已加密的 API Key。"""
    key_path = data_dir / "secrets" / "ai_fernet.key"
    db_path = data_dir / "ai_assistant.db"
    result = {"key_exists": key_path.exists(), "encrypted_keys": 0, "decrypted": 0, "failed": 0}

    if not db_path.exists():
        return result

    try:
        uri = f"file:{(db_path.as_posix())}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=2)
        try:
            rows = conn.execute("SELECT api_key FROM api_configs").fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return result

    encrypted_rows = [
        str(stored)[len("encrypted:"):] for (stored,) in rows
        if stored and str(stored).startswith("encrypted:")
    ]
    result["encrypted_keys"] = len(encrypted_rows)

    if not key_path.exists():
        # 数据库里有加密 Key 却没有密钥文件 → 迁移后永远解不开，必须判定失败
        result["failed"] = len(encrypted_rows)
        if encrypted_rows:
            result["error"] = "缺少加密密钥文件，API Key 无法解密"
        return result

    try:
        from cryptography.fernet import Fernet, InvalidToken
    except ImportError:  # pragma: no cover
        result["error"] = "cryptography 未安装，跳过密钥校验"
        return result
    key = key_path.read_bytes().strip()
    try:
        cipher = Fernet(key)
    except (ValueError, TypeError):
        result["error"] = "密钥文件格式无效"
        result["failed"] = len(encrypted_rows)
        return result

    for payload in encrypted_rows:
        try:
            cipher.decrypt(payload.encode("utf-8"))
            result["decrypted"] += 1
        except InvalidToken:
            result["failed"] += 1
    return result


def _counts_signature(counts: Dict[str, Any]) -> Dict[str, Any]:
    keys = (
        "assets", "categories", "thumbnails", "prompt_json", "prompt_images",
        "workflows_files", "db_bytes", "secret_key_sha256", "db_topics",
        "config_files", "backup_files", "lora_files",
    )
    return {k: counts.get(k) for k in keys}


def _business_is_empty(root: Path) -> bool:
    """判断目标根是否只有空默认库（无资产/无对话/无提示词/无工作流/无密钥）。"""
    counts = collect_counts(root)
    return (
        counts["assets"] == 0
        and counts["db_topics"] <= 0
        and counts["prompt_images"] == 0
        and counts["workflows_files"] == 0
        and not counts["secret_key_exists"]
        and counts["backup_files"] == 0
        and counts["lora_files"] == 0
    )


def _migrate_blocking(source_root: Path, target_root: Path, mark_job: bool = True) -> Dict[str, Any]:
    """执行迁移（同步）：复制到暂存 → 校验 → 合并到目标 → 校验 → 失败回滚。

    Args:
        mark_job: 是否在结束时把任务状态置为完成/失败。后台迁移由 start_migration
            在写完指针后再统一收尾，避免测试/UI 在指针写入前读到“已完成”。
    """
    source_root = Path(source_root).resolve()
    target_root = Path(target_root).resolve()
    if source_root == target_root:
        return {"success": False, "error": "源目录与目标目录相同"}

    source_dirs = _source_category_dirs(source_root)
    if not any(source_dirs.values()):
        return {"success": False, "error": f"源目录没有可迁移的用户数据: {source_root}"}

    source_counts = collect_counts(source_root)
    total_files, total_bytes = _total_stats(source_dirs)
    staging = target_root / f".migrating-{uuid.uuid4().hex[:8]}"
    staging.mkdir(parents=True, exist_ok=False)

    logger.info(
        "[迁移] 开始: %s -> %s（%d 个文件，%.1f MB）",
        source_root, target_root, total_files, total_bytes / 1024 / 1024,
    )
    _set_job(running=True, done=0, total=total_files, bytes_done=0,
             bytes_total=total_bytes, current="准备", result=None)

    copied = 0
    bytes_done = 0
    created_files: List[Path] = []
    created_dirs: List[Path] = []
    target_empty = _business_is_empty(target_root)
    try:
        for kind in CATEGORY_KEYS:
            src = source_dirs.get(kind)
            if src is None:
                continue
            _set_job(current=f"复制 {kind}")

            def _on_file(path: Path, _kind=kind) -> None:
                nonlocal copied, bytes_done
                copied += 1
                try:
                    bytes_done += path.stat().st_size
                except OSError:
                    pass
                _update_progress(copied, f"复制 {_kind}", bytes_done)

            _copy_tree(src, staging / kind, _on_file)

        # 暂存区校验：与源目录业务计数一致
        staging_counts = collect_counts(staging)
        mismatches = {
            key: (source_counts.get(key), staging_counts.get(key))
            for key in _counts_signature(source_counts)
            if source_counts.get(key) != staging_counts.get(key)
        }
        # 暂存目录没有 config/backup 时 config_stats 为空是正常的，不在签名内
        if mismatches:
            raise RuntimeError(f"暂存校验失败: {mismatches}")

        _set_job(current="写入目标目录")
        for kind in CATEGORY_KEYS:
            staged = staging / kind
            if not staged.exists():
                continue
            _merge_tree(staged, target_root / kind, created_files, created_dirs, overwrite=target_empty)

        dest_counts = collect_counts(target_root)
        if target_empty:
            dest_mismatches = {
                key: (source_counts.get(key), dest_counts.get(key))
                for key in _counts_signature(source_counts)
                if dest_counts.get(key) != source_counts.get(key)
            }
        else:
            # 目标已有数据时只补充缺失文件：要求源数据项在目标中至少同样齐全
            count_keys = (
                "assets", "categories", "thumbnails", "prompt_json",
                "prompt_images", "workflows_files", "config_files",
            )
            dest_mismatches = {
                key: (source_counts.get(key), dest_counts.get(key))
                for key in count_keys
                if dest_counts.get(key, 0) < source_counts.get(key, 0)
            }
            if source_counts.get("secret_key_exists") and not dest_counts.get("secret_key_exists"):
                dest_mismatches["secret_key_exists"] = (True, False)
        if dest_mismatches:
            raise RuntimeError(f"目标目录校验失败: {dest_mismatches}")

        key_check = _verify_fernet_key(target_root / "data")
        if key_check["failed"] > 0 or (
            key_check["encrypted_keys"] > 0 and key_check["decrypted"] < key_check["encrypted_keys"]
        ):
            raise RuntimeError(f"加密密钥校验失败，API Key 无法解密: {key_check}")

        marker = target_root / paths.LEGACY_MARKER_FILENAME
        marker.write_text(json.dumps({
            "migrated_from": str(source_root),
            "migrated_at": datetime.now().isoformat(timespec="seconds"),
            "source_counts": _counts_signature(source_counts),
            "dest_counts": _counts_signature(dest_counts),
            "key_verification": key_check,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        result = {
            "success": True,
            "source_root": str(source_root),
            "target_root": str(target_root),
            "copied_files": copied,
            "total_files": total_files,
            "copied_bytes": bytes_done,
            "source_counts": source_counts,
            "dest_counts": dest_counts,
            "key_verification": key_check,
            "skipped_existing": True,
        }
        if mark_job:
            _set_job(running=False, current="完成", result=result, done=total_files)
        logger.info("[迁移] 完成: %s 个文件；密钥校验 %s", copied, key_check)
        return result

    except Exception as exc:
        logger.error("[迁移] 失败: %s", exc, exc_info=True)
        _rollback(created_files, created_dirs)
        result = {"success": False, "error": str(exc), "source_root": str(source_root), "target_root": str(target_root)}
        if mark_job:
            _set_job(running=False, current="失败", result=result)
        return result
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def start_migration(source_root: str, target_root: Optional[str] = None) -> Dict[str, Any]:
    """
    启动后台迁移任务（源目录只读）。

    Args:
        source_root: 旧布局根目录（含 data/ 或 backend/config/）
        target_root: 目标用户数据根，默认当前根
    """
    source = Path(source_root).expanduser().resolve()
    target = Path(target_root).expanduser().resolve() if target_root else paths.get_user_data_root()
    with _job_lock:
        if _job_state["running"]:
            return {"success": False, "error": "已有迁移任务在进行中"}

    if not source.exists():
        return {"success": False, "error": f"源目录不存在: {source}"}
    try:
        _validate_root(str(target))
    except ValueError as exc:
        return {"success": False, "error": str(exc)}

    def _run() -> None:
        # 收尾（写指针/标记）完成后再把任务标记为结束，避免提前读到缺少 restart_required 的结果
        result = _migrate_blocking(source, target, mark_job=False)
        if not result or not result.get("success"):
            _set_job(running=False, current="失败", result=result)
            return
        # 迁移到新目录时必须同时写机器级指针，否则重启后仍回到默认目录
        if target.resolve() != paths.get_user_data_root().resolve():
            try:
                pointer = paths.write_userdata_pointer(target)
                paths.mark_user_data_initialized(target, {"source": "pointer", "migrated": True})
                result["pointer_written"] = str(pointer)
                result["restart_required"] = True
            except OSError as exc:
                result["success"] = False
                result["pointer_error"] = str(exc)
                result["error"] = f"数据已迁移，但无法写入数据目录指针：{exc}。请在设置页重新选择该目录。"
        _set_job(running=False, current="完成" if result.get("success") else "失败", result=result)

    _set_job(running=True, done=0, total=0, bytes_done=0, bytes_total=0,
             current="扫描源目录", result=None)
    threading.Thread(target=_run, name="userdata-migrate", daemon=True).start()
    return {"success": True, "message": "迁移已开始", "source_root": str(source), "target_root": str(target)}


def _delete_tree_contents(root: Path) -> Tuple[int, List[str]]:
    """删除目录内容（不删除目录本身），跳过被占用的文件。"""
    deleted = 0
    errors: List[str] = []
    if not root.exists():
        return deleted, errors
    for item in list(root.iterdir()):
        try:
            if item.is_dir():
                shutil.rmtree(item)
                deleted += 1
            else:
                item.unlink()
                deleted += 1
        except OSError as exc:
            errors.append(f"{item}: {exc}")
    return deleted, errors


def clean_cache_and_logs(scopes: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    清理缓存/日志（运行级目录，可安全删除，下次启动自动重建）。

    说明：
        只清理项目相对路径下的运行数据（<运行数据根>/cache、<运行数据根>/logs）；
        旧布局 <用户数据根>/cache、<用户数据根>/logs 原地保留，不删除、不搬迁。
    """
    scopes = scopes or ["cache", "logs"]
    result: Dict[str, Any] = {
        "success": True,
        "root": str(paths.get_user_data_root()),
        "runtime_dir": str(paths.resolve_runtime_dir()[0]),
        "cache_dir": str(paths.get_cache_dir()),
        "log_dir": str(paths.get_log_dir()),
        "deleted": {},
        "errors": [],
    }
    for scope in scopes:
        if scope == "cache":
            target = paths.get_cache_dir()
        elif scope == "logs":
            target = paths.get_log_dir()
        else:
            result["success"] = False
            result["errors"].append(f"未知清理范围: {scope}")
            continue
        deleted, errors = _delete_tree_contents(target)
        result["deleted"][scope] = deleted
        result["errors"].extend(errors)
    return result


def request_business_wipe() -> Dict[str, Any]:
    """
    请求清空业务数据（data/config/backup/lora_data）。

    文件写入在下次启动时、任何模块打开数据文件之前执行，避免运行时句柄/内存状态
    导致"删了又被写回"。
    """
    root = paths.get_user_data_root()
    flag = root / paths.WIPE_REQUEST_FILENAME
    payload = {"requested_at": datetime.now().isoformat(timespec="seconds"), "requested_by_pid": os.getpid()}
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.warning("[用户数据] 已登记清空请求，下次启动执行: %s", flag)
    return {"success": True, "restart_required": True, "flag": str(flag), "root": str(root)}


def apply_pending_wipe() -> Dict[str, Any]:
    """启动时执行待清空请求（必须在数据模块初始化前调用）。"""
    root = paths.get_user_data_root()
    flag = root / paths.WIPE_REQUEST_FILENAME
    if not flag.exists():
        return {"applied": False}
    result: Dict[str, Any] = {"applied": True, "root": str(root), "deleted": {}, "errors": []}
    for sub in BUSINESS_SUBDIRS:
        deleted, errors = _delete_tree_contents(root / sub)
        result["deleted"][sub] = deleted
        result["errors"].extend(errors)
    try:
        flag.unlink()
    except OSError as exc:
        result["errors"].append(f"{flag}: {exc}")
    logger.warning("[用户数据] 已按请求清空业务数据: %s", result)

    # 密钥 cipher 缓存必须在清空后失效
    try:
        from backend.src.core.ai.secret_store import reset_cipher_cache
        reset_cipher_cache()
    except Exception:  # pragma: no cover
        pass
    return result
