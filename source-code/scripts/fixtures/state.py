"""用户数据根的初始状态：首启标记与 settings.json。

不处理这两项，应用每次启动都会弹「选择数据保存位置」和「检测到系统代理」，
弹框会挡住全部点击，页面验证无法进行。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from . import context
from .context import Manifest


def _marker_payload() -> Dict:
    return {
        "initialized_at": context.now_iso(),
        "source": "fixture",
        "adopted_existing": True,
    }


def _write_marker(manifest: Manifest) -> bool:
    marker = context.user_root() / ".initialized"
    if marker.exists():
        return False
    manifest.record(marker)
    marker.write_text(
        json.dumps(_marker_payload(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return True


def _write_settings(manifest: Manifest) -> bool:
    """确保 settings.json 存在，并关掉两个首启弹框。

    Returns:
        True 表示本次新建了文件，False 表示只是就地修正既有文件。
    """
    from backend.src.core.settings_manager import SettingsManager

    path = Path(context.config_dir()) / "settings.json"
    created = not path.exists()

    if created:
        config = SettingsManager().get_default_config()
    else:
        config = context.read_json(path)

    warnings = config.setdefault("warnings", {})
    warnings["systemProxyDetected"] = False
    warnings["devVersionWarning"] = False
    config["closeBehavior"] = {"action": "exit", "dontAskAgain": True}

    if created:
        path.parent.mkdir(parents=True, exist_ok=True)
        manifest.record(path)
    else:
        manifest.backup(path)

    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return created


def seed(manifest: Manifest) -> Dict:
    """补齐首启状态，返回哪些项是本次新建的。"""
    return {
        "marker_created": _write_marker(manifest),
        "settings_created": _write_settings(manifest),
    }
