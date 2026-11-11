"""fixture 运行上下文：环境守卫、路径解析、写入登记与回滚。

这里是唯一的路径来源。业务模块不要自己拼路径，一律从这里取，
避免 fixture 写错位置污染 prod。
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# source-code/ 目录（backend 包的父级），导入后端模块需要它在 sys.path 上
SOURCE_CODE_DIR = Path(__file__).resolve().parents[2]

# 所有 fixture 记录统一前缀，便于人工识别
FIXTURE_TAG = "[FIXTURE]"

# 允许的环境
ALLOWED_ENVS = ("dev", "test")

MANIFEST_FILENAME = ".fixture_manifest.json"
BACKUP_DIRNAME = "backup"
FIXTURES_DIRNAME = "fixtures"


class FixtureError(RuntimeError):
    """fixture 拒绝执行时抛出。"""


def activate_env(env: str) -> str:
    """把当前进程切到指定部署环境。

    Args:
        env: 目标环境名。

    Returns:
        规范化后的环境名。

    Raises:
        FixtureError: 环境非法，或目标为 prod。
    """
    normalized = (env or "").strip().lower()
    if normalized == "prod":
        raise FixtureError("fixture 绝不允许写入 prod 环境")
    if normalized not in ALLOWED_ENVS:
        raise FixtureError(f"未知环境 {env!r}，只支持 {ALLOWED_ENVS}")

    # 必须在导入后端模块之前设置，deploy_env 在首次导入时判定
    os.environ["COMFYUI_BOX_ENV"] = normalized
    if str(SOURCE_CODE_DIR) not in sys.path:
        sys.path.insert(0, str(SOURCE_CODE_DIR))
    return normalized


def _paths():
    """延迟导入 paths 模块，确保环境变量已生效。"""
    from backend.src.utils import paths

    return paths


def user_root() -> Path:
    """当前环境的数据根。"""
    return Path(_paths().get_user_data_root())


def config_dir() -> Path:
    return Path(_paths().get_config_dir())


def data_dir() -> Path:
    return Path(_paths().get_data_dir())


def gallery_dir() -> Path:
    return Path(_paths().get_scope_category_dir("gallery"))


def prompt_dir() -> Path:
    return Path(_paths().get_prompt_data_dir())


def prompt_images_dir() -> Path:
    return Path(_paths().get_prompt_images_dir())


def lora_dir() -> Path:
    return Path(_paths().get_lora_data_dir())


def workflows_dir() -> Path:
    """工作流元数据目录（<data>/workflows，存 *_metadata.json）。"""
    return data_dir() / "workflows"


def comfyui_workflows_dir() -> Path:
    """假 ComfyUI 的工作流目录，工作流页实际扫描的位置。"""
    return fake_comfyui_dir() / "user" / "default" / "workflows"


def comfyui_models_dir() -> Path:
    return fake_comfyui_dir() / "models"


def fixtures_dir() -> Path:
    """fixture 自建资产（假 ComfyUI、生成的图片）的落点。"""
    return user_root() / FIXTURES_DIRNAME


def fake_comfyui_dir() -> Path:
    return fixtures_dir() / "comfyui"


def images_dir() -> Path:
    return fixtures_dir() / "images"


def manifest_path() -> Path:
    return fixtures_dir() / MANIFEST_FILENAME


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Manifest:
    """记录 fixture 写过什么，供 clean 精确回滚。

    结构::

        {
          "env": "dev",
          "created_at": "...",
          "paths": ["<绝对路径>", ...],
          "backups": {"<原始绝对路径>": "<备份绝对路径>"},
          "domains": {"workflow": ["<本次该域创建的绝对路径>", ...]}
        }

    ``domains`` 用于切换场景时精确回收上一个变体的产物——
    例如从 ``edge`` 换到 ``basic``，边界样本必须消失，否则两种数据混在一起，
    场景就失去意义了。
    """

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else manifest_path()
        self._data = {
            "env": "",
            "created_at": now_iso(),
            "paths": [],
            "backups": {},
            "domains": {},
        }

    def load(self) -> "Manifest":
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise FixtureError(f"清单文件损坏，无法安全清理: {self.path} ({exc})")
        return self

    def exists(self) -> bool:
        return self.path.exists()

    @property
    def env(self) -> str:
        return self._data.get("env", "")

    def set_env(self, env: str) -> None:
        self._data["env"] = env

    def record(self, path: Path) -> None:
        """登记一个由 fixture 创建或覆盖的路径（幂等）。"""
        text = str(Path(path).resolve())
        if text not in self._data["paths"]:
            self._data["paths"].append(text)

    def backup(self, path: Path) -> Optional[Path]:
        """覆盖前备份原文件；原文件不存在时返回 None。

        注意：如果该路径本身就是 fixture 上次创建的，再次 seed 时**不能**备份，
        否则备份下来的是 fixture 自己的产物，clean 时会把假数据"还原"回去。
        """
        source = Path(path)
        if not source.exists():
            return None
        key = str(source.resolve())
        existing = self._data["backups"].get(key)
        if existing and Path(existing).exists():
            return Path(existing)
        if key in self._data["paths"]:
            # 上一次 seed 由 fixture 创建，原始内容已不存在
            return None

        target = self.path.parent / BACKUP_DIRNAME / f"{len(self._data['backups']):03d}_{source.name}"
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            shutil.copy2(source, target)
        self._data["backups"][key] = str(target.resolve())
        return target

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def domain_files(self, domain: str) -> List[str]:
        """上一次该域创建的文件列表。"""
        return list(self._data.get("domains", {}).get(domain, []))

    def set_domain_files(self, domain: str, paths) -> None:
        self._data.setdefault("domains", {})[domain] = [
            str(Path(item).resolve()) for item in paths
        ]

    def cleanup(self) -> dict:
        """删除登记过的路径，并还原备份。

        Returns:
            {"removed": n, "restored": n, "missing": n}
        """
        removed = 0
        missing = 0
        for raw in sorted(self._data.get("paths", []), reverse=True):
            target = Path(raw)
            if not target.exists():
                missing += 1
                continue
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
            else:
                target.unlink(missing_ok=True)
            removed += 1

        restored = 0
        for original, backup in self._data.get("backups", {}).items():
            source = Path(backup)
            destination = Path(original)
            if not source.exists():
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, destination, dirs_exist_ok=True)
            else:
                shutil.copy2(source, destination)
            restored += 1

        if self.path.exists():
            self.path.unlink()

        # fixtures 目录是 fixture 专用命名空间，清理后整体移除
        fixtures_root = self.path.parent
        if fixtures_root.exists():
            shutil.rmtree(fixtures_root, ignore_errors=True)

        return {"removed": removed, "restored": restored, "missing": missing}


def write_json(path: Path, payload: dict, manifest: Manifest) -> None:
    """带备份的 JSON 落盘。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest.backup(path)
    manifest.record(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path, default: Optional[dict] = None) -> dict:
    """读取 JSON，缺失或损坏时返回默认值。"""
    path = Path(path)
    if not path.exists():
        return dict(default or {})
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(default or {})


def prune_empty_dirs(root: Path) -> int:
    """自底向上删除空目录（含 root 自身若为空）。返回删除数量。"""
    root = Path(root)
    if not root.exists() or not root.is_dir():
        return 0
    removed = 0
    for directory in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if directory.is_dir() and not any(directory.iterdir()):
            try:
                directory.rmdir()
                removed += 1
            except OSError:
                pass
    return removed


def reset_domain(manifest: Manifest, domain: str, prune_root: Optional[Path] = None) -> int:
    """回收该域上一次创建的全部产物，供切换变体时使用。

    Args:
        manifest: 当前清单。
        domain: 域名（与 registry 中的 key 一致）。
        prune_root: 删除文件后顺手清理空目录的根。

    Returns:
        删除的文件/目录数量。
    """
    removed = 0
    for raw in manifest.domain_files(domain):
        target = Path(raw)
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
            removed += 1
        elif target.is_file():
            target.unlink(missing_ok=True)
            removed += 1
    manifest.set_domain_files(domain, [])
    if prune_root is not None:
        prune_empty_dirs(prune_root)
    return removed
