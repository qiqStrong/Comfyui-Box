"""
切换用户数据目录时的配置继承测试。

回归：换数据目录只写指针、不复制 settings.json，导致用户「不再提示」、代理、
主题等选择全部重置，表现为弹窗反复出现、设置了却不生效。
"""

import json
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[3]
_SOURCE_ROOT = _BACKEND_DIR.parent
for _p in (str(_BACKEND_DIR), str(_SOURCE_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.src.core.userdata.manager import _carry_over_settings  # noqa: E402


def _write_settings(root: Path, payload: dict) -> Path:
    target = root / "config" / "settings.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return target


def test_settings_carried_when_target_empty(tmp_path):
    """新目录没有配置时，继承旧目录的 settings.json。"""
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    new_root.mkdir()
    _write_settings(old_root, {"warnings": {"systemProxyDetected": False}})

    _carry_over_settings(old_root, new_root)

    copied = json.loads((new_root / "config" / "settings.json").read_text(encoding="utf-8"))
    assert copied["warnings"]["systemProxyDetected"] is False


def test_existing_target_settings_kept(tmp_path):
    """新目录已有配置时不覆盖，避免冲掉用户在目标目录做过的选择。"""
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    _write_settings(old_root, {"warnings": {"systemProxyDetected": False}})
    _write_settings(new_root, {"warnings": {"systemProxyDetected": True}})

    _carry_over_settings(old_root, new_root)

    kept = json.loads((new_root / "config" / "settings.json").read_text(encoding="utf-8"))
    assert kept["warnings"]["systemProxyDetected"] is True


def test_missing_source_is_noop(tmp_path):
    """旧目录没有配置时静默跳过，不抛异常。"""
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    new_root.mkdir()

    _carry_over_settings(old_root, new_root)

    assert not (new_root / "config" / "settings.json").exists()
