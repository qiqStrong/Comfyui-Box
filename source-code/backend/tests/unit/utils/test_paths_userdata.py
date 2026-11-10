"""
用户数据根 / 运行数据根定位测试

覆盖：机器级指针 > 默认目录 > 临时降级；指针失效提示；显式 override 注入；用户级目录派生；
运行数据（日志/缓存/WebView2）项目相对路径；项目目录不可写时的告警与降级；单一指针。
全部通过 monkeypatch 隔离真实环境，不读取进程环境变量。
"""

import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[3]
_SOURCE_ROOT = _BACKEND_DIR.parent
for _p in (str(_BACKEND_DIR), str(_SOURCE_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from backend.src.utils import paths  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_machine_dirs(monkeypatch, tmp_path):
    """把 LOCALAPPDATA 与项目根指向临时目录，并固定为 dev 环境。"""
    from backend.src.core import deploy_env

    local = tmp_path / "localappdata"
    local.mkdir(parents=True, exist_ok=True)
    install = tmp_path / "install"
    install.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr(paths, "get_project_root", lambda: install)
    deploy_env.set_env_override("dev")
    paths.reset_user_data_root_cache()
    paths.reset_runtime_dir_cache()
    yield install
    deploy_env.set_env_override(None)
    paths.reset_user_data_root_cache()
    paths.reset_runtime_dir_cache()


def test_default_root_and_source(tmp_path):
    """dev 环境默认根带 .dev 后缀，避免开发时落到 prod 的 userdata。"""
    expected = Path(__import__("os").environ["LOCALAPPDATA"]) / paths.APP_NAME / "userdata.dev"
    assert paths.get_user_data_root() == expected.resolve()
    assert paths.get_user_data_source() == "default"
    assert paths.get_default_user_data_root() == expected


def test_prod_keeps_original_locations(_isolate_machine_dirs):
    """prod 的文件名与目录名必须一字不改，否则发布版升级后数据会"消失"。"""
    from backend.src.core import deploy_env

    install = _isolate_machine_dirs
    deploy_env.set_env_override("prod")
    try:
        local = Path(__import__("os").environ["LOCALAPPDATA"]) / paths.APP_NAME
        assert paths.get_userdata_pointer_file() == local / "userdata.location"
        assert paths.get_default_user_data_root() == local / "userdata"
        assert paths.get_log_dir("comfyui") == install / "logs" / "comfyui"
        assert paths.get_cache_dir("marketplace") == install / "cache" / "marketplace"
        assert paths.get_webview2_dir() == (install / "webview2").resolve()
    finally:
        deploy_env.set_env_override("dev")


def test_explicit_override_is_used(tmp_path):
    """自动化测试通过显式参数注入目录，不依赖进程环境变量。"""
    custom = tmp_path / "custom-root"
    root, source, note = paths.resolve_user_root(override=custom)
    assert root == custom.resolve()
    assert source == "override"
    assert note is None
    assert paths.get_user_data_root(override=custom) == custom.resolve()


def test_pointer_used_when_no_override(tmp_path):
    custom = tmp_path / "pointer-root"
    paths.write_userdata_pointer(custom)
    paths.reset_user_data_root_cache()
    assert paths.get_user_data_root() == custom.resolve()
    assert paths.get_user_data_source() == "pointer"
    assert paths.get_user_data_resolution_note() is None


def test_invalid_pointer_falls_back_to_default_with_note(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("file, not dir", encoding="utf-8")
    paths.write_userdata_pointer(blocker / "cannot-create")
    paths.reset_user_data_root_cache()
    assert paths.get_user_data_root() == paths.get_default_user_data_root().resolve()
    assert paths.get_user_data_source() == "default"
    note = paths.get_user_data_resolution_note()
    assert note and "原数据目录不可用" in note


def test_fallback_to_temp_when_default_unwritable(monkeypatch, tmp_path):
    blocker = tmp_path / "blocked-default"
    blocker.write_text("file, not dir", encoding="utf-8")
    fake_temp = tmp_path / "temp"
    fake_temp.mkdir()
    monkeypatch.setattr(paths, "get_default_user_data_root", lambda: blocker)
    monkeypatch.setattr(paths.tempfile, "gettempdir", lambda: str(fake_temp))
    paths.reset_user_data_root_cache()

    root, source, note = paths.resolve_user_root()
    assert source == "fallback"
    assert root == (fake_temp / paths.APP_NAME / "userdata").resolve()
    assert note and "默认目录不可写" in note


def test_user_level_dirs_derived_from_root(tmp_path):
    root = paths.get_user_data_root()
    assert paths.get_data_dir("gallery") == root / "data" / "gallery"
    assert paths.get_config_dir("presets") == root / "config" / "presets"
    assert paths.get_backup_dir() == root / "backup"
    assert paths.get_lora_data_dir() == root / "lora_data"
    assert paths.get_settings_file() == root / "config" / "settings.json"
    for path in (
        paths.get_data_dir("gallery"),
        paths.get_config_dir("presets"),
        paths.get_backup_dir(),
        paths.get_lora_data_dir(),
    ):
        assert path.exists()


def test_runtime_dirs_follow_project_relative_paths(_isolate_machine_dirs):
    """日志/缓存/WebView2 落在项目目录下的环境子目录，而不是用户数据根。"""
    install = _isolate_machine_dirs
    root = paths.get_user_data_root()
    assert paths.get_log_dir("comfyui") == install / "run" / "dev" / "logs" / "comfyui"
    assert paths.get_cache_dir("marketplace") == install / "run" / "dev" / "cache" / "marketplace"
    assert paths.get_webview2_dir() == (install / "run" / "dev" / "webview2").resolve()
    assert paths.get_runtime_data_source() == "project"
    assert paths.get_runtime_data_resolution_note() is None
    for path in (
        paths.get_log_dir("comfyui"),
        paths.get_cache_dir("marketplace"),
        paths.get_webview2_dir(),
    ):
        assert path.exists()
        assert root not in path.parents


def test_runtime_override_from_settings(_isolate_machine_dirs, tmp_path):
    """设置页指定 storage.runtimeDataDir 后，日志/缓存/WebView2 跟随该目录。"""
    import json

    override = tmp_path / "runtime-override"
    settings_file = paths.get_settings_file()
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps({"storage": {"runtimeDataDir": str(override)}}, ensure_ascii=False),
        encoding="utf-8",
    )
    paths.reset_runtime_dir_cache()

    assert paths.get_runtime_data_source() == "override"
    assert paths.get_log_dir() == override / "logs"
    assert paths.get_cache_dir() == override / "cache"
    assert paths.get_webview2_dir() == (override / "webview2").resolve()


def test_unwritable_project_falls_back_to_temp_with_note(monkeypatch, tmp_path):
    """项目目录不可写时降级到临时目录，并返回明确告警（不静默写 AppData）。"""
    blocker = tmp_path / "readonly-project"
    blocker.write_text("file, not dir", encoding="utf-8")
    fake_temp = tmp_path / "temp"
    fake_temp.mkdir()
    monkeypatch.setattr(paths, "get_project_root", lambda: blocker)
    monkeypatch.setattr(paths.tempfile, "gettempdir", lambda: str(fake_temp))
    paths.reset_runtime_dir_cache()

    root, source, note = paths.resolve_runtime_dir()
    assert source == "fallback"
    assert root == (
        fake_temp / paths.APP_NAME / f"{paths.RUNTIME_DATA_FALLBACK_DIRNAME}.dev"
    ).resolve()
    assert note and "运行数据目录不可写" in note
    assert paths.get_machine_app_dir().resolve() not in root.parents


def test_single_userdata_pointer_no_profiles(_isolate_machine_dirs):
    """用户数据只有一个机器级指针；按环境区分靠文件名后缀，不靠子目录。"""
    assert paths.USERDATA_POINTER_FILENAME == "userdata.location"
    pointer = paths.get_userdata_pointer_file()
    assert pointer.parent == paths.get_machine_app_dir()
    assert pointer.name == "userdata.location.dev"
    assert "profiles" not in pointer.parts


def test_system_level_paths_do_not_follow_user_root(tmp_path):
    assert paths.get_project_root() not in paths.get_user_data_root().parents
    assert paths.get_mingit_dir().is_relative_to(paths.get_project_root())


def test_write_and_clear_pointer(tmp_path):
    custom = tmp_path / "moving-root"
    pointer = paths.write_userdata_pointer(custom)
    assert pointer.read_text(encoding="utf-8") == str(custom.resolve())
    paths.clear_userdata_pointer()
    assert not pointer.exists()
    assert paths.get_user_data_source() == "default"


def test_legacy_candidates_point_to_install_root():
    candidates = dict(paths.get_legacy_userdata_candidates())
    assert candidates["data"] == paths.get_project_root() / "data"
    assert candidates["backup"] == paths.get_project_root() / "backup"
    # 配置模板已统一迁到 resource/config，属随包只读资源，不再作为旧用户数据候选
    assert "config" not in candidates


def test_resource_dirs_resolve_under_source_code():
    resource_root = paths.get_resource_dir()
    assert resource_root.name == "resource"
    assert resource_root.is_absolute()
    assert paths.get_resource_logo_dir() == resource_root / "img" / "logo"
    assert paths.get_resource_icons_dir() == resource_root / "img" / "icons"
    assert paths.get_resource_qr_dir() == resource_root / "img" / "qr"
    assert paths.get_resource_avatars_dir() == resource_root / "img" / "avatars"
    assert paths.get_resource_models_dir() == resource_root / "models"
    assert paths.get_resource_config_dir() == resource_root / "config"
    assert paths.get_nsfw_model_path() == resource_root / "models" / "nsfw.onnx"


def test_shipped_resource_files_exist_in_repo():
    """随包资源必须真实存在于仓库，否则打包后会静默降级为默认图标/无模型。"""
    resource_root = _SOURCE_ROOT / "resource"
    assert (resource_root / "img" / "logo" / "icon.ico").is_file()
    assert (resource_root / "img" / "logo" / "icon.png").is_file()
    assert (resource_root / "img" / "logo" / "app-icon.png").is_file()
    assert (resource_root / "img" / "logo" / "favicon.ico").is_file()
    assert (resource_root / "models" / "nsfw.onnx").is_file()
    assert (resource_root / "config" / "default_config.json").is_file()
