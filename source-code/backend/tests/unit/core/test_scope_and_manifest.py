"""
数据范围开关（scopeMap）与索引文件（manifest）单元测试。

覆盖：
- 旧配置自动补全（packages / data_spaces / 环境绑定）与默认解析；
- 开关切换（global/private/custom）不迁移数据、epoch 递增；
- 旧工作流 use_global_path 兼容映射；
- manifest 导出不含密钥/环境变量值、导入预览（缺失/冲突）、导入备份与指针不变；
- 首启引导分支（无注册表 / 指针失效 / 正常）；
- 命令行测试隔离覆盖不写机器级指针。
"""

import json
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[3]
_SOURCE_ROOT = _BACKEND_DIR.parent
for _p in (str(_BACKEND_DIR), str(_SOURCE_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from backend.src.core.env.environment_config_manager import EnvironmentConfigManager  # noqa: E402
from backend.src.core import manifest as manifest_module  # noqa: E402
from backend.src.core import scope as scope_module  # noqa: E402
from backend.src.core.scope import resolver as scope_resolver  # noqa: E402
from backend.src.core.config.workflow_config import WorkflowConfigManager  # noqa: E402
from backend.src.utils import paths  # noqa: E402


@pytest.fixture
def workspace(monkeypatch, tmp_path):
    """把用户数据根、配置目录固定到临时目录，并重置配置管理器单例。"""
    root = (tmp_path / "userdata").resolve()
    config_dir = root / "config"
    config_dir.mkdir(parents=True)
    comfy_a = (tmp_path / "comfyA").resolve()
    comfy_b = (tmp_path / "comfyB").resolve()
    (comfy_a / "user" / "default" / "workflows").mkdir(parents=True)
    (comfy_b / "user" / "default" / "workflows").mkdir(parents=True)

    monkeypatch.setattr(paths, "get_user_data_root", lambda override=None: root)
    monkeypatch.setattr(paths, "get_config_dir", lambda subdir=None: config_dir / subdir if subdir else config_dir)
    monkeypatch.setattr(paths, "get_user_data_source", lambda override=None: "override")

    EnvironmentConfigManager._instance = None
    manager = EnvironmentConfigManager(str(config_dir))
    base_config = {
        "version": "1.0.0",
        "environments": [
            {
                "id": "envA",
                "name": "环境 A",
                "alias": "环境 A",
                "path": str(comfy_a),
                "envType": "portable",
                "config": {"general": {}, "acceleration": {"port": 8188}, "advanced_env_vars": ""},
            },
            {
                "id": "envB",
                "name": "环境 B",
                "alias": "环境 B",
                "path": str(comfy_b),
                "envType": "portable",
                "config": {"general": {}, "acceleration": {"port": 8189}, "advanced_env_vars": ""},
            },
        ],
        "current_environment_id": "envA",
    }
    manager.save_config(base_config)

    # 重置 scope epoch（测试间隔离）
    scope_resolver._scope_epochs.clear()
    scope_resolver._epoch_counter = 0

    yield {
        "root": root,
        "config_dir": config_dir,
        "manager": manager,
        "comfy_a": comfy_a,
        "comfy_b": comfy_b,
    }

    EnvironmentConfigManager._instance = None


def _load(manager: EnvironmentConfigManager) -> dict:
    return manager.load_config()


def test_legacy_registry_autofill_and_default_resolution(workspace):
    """旧环境配置读取后自动补默认包/空间，默认解析保持旧行为。"""
    cfg = _load(workspace["manager"])
    root = workspace["root"]

    assert cfg["current_package_id"] == "pkg_default"
    assert any(p["id"] == "pkg_default" and p.get("is_default") for p in cfg["packages"])

    legacy_space = next(s for s in cfg["data_spaces"] if s["id"] == "ds_legacy")
    assert Path(legacy_space["path"]) == root

    for env in cfg["environments"]:
        assert env["package_id"] == "pkg_default"
        assert env["data_space_id"].startswith("ds_root_")
        assert isinstance(env["scope_overrides"], dict)

    gallery = scope_module.resolve_scope("gallery", root_id="envA", config=cfg)
    assert gallery["mode"] == "global"
    assert Path(gallery["path"]) == root / "data" / "gallery"

    workflows = scope_module.resolve_scope("workflows", root_id="envA", config=cfg)
    assert workflows["mode"] == "private"
    assert Path(workflows["path"]) == workspace["comfy_a"] / "user" / "default" / "workflows"


def test_scope_switch_private_does_not_migrate_and_epoch_changes(workspace):
    """切换只改读取路径；旧数据原位保留；epoch 递增。"""
    root = workspace["root"]
    legacy_assets = root / "data" / "gallery" / "assets.json"
    legacy_assets.parent.mkdir(parents=True, exist_ok=True)
    legacy_assets.write_text('{"assets": [{"id": "a1"}]}', encoding="utf-8")

    before = scope_module.get_scope_epoch("gallery", root_id="envA")
    resolved = scope_module.set_scope("gallery", "private", root_id="envA")
    after = scope_module.get_scope_epoch("gallery", root_id="envA")

    assert resolved["mode"] == "private"
    assert Path(resolved["path"]).parts[:3] == Path(workspace["comfy_a"]).parts[:3]
    assert "comfyui-box" in resolved["path"]
    assert not (Path(resolved["path"]) / "assets.json").exists()
    assert legacy_assets.exists(), "切换后旧数据必须原位保留"
    assert after > before

    restored = scope_module.set_scope("gallery", "global", root_id="envA")
    assert restored["mode"] == "global"
    assert Path(restored["path"]) == root / "data" / "gallery"
    assert scope_module.get_scope_epoch("gallery", root_id="envA") > after


def test_workflow_use_global_path_compat(workspace, monkeypatch):
    """旧开关 true → global；false → private，行为不变。"""
    wf = WorkflowConfigManager(str(workspace["config_dir"]))
    global_dir = workspace["root"] / "shared_workflows"
    global_dir.mkdir(parents=True, exist_ok=True)
    wf.save_config({"use_global_path": True, "global_path": str(global_dir), "env_paths": {}})

    resolved = scope_module.resolve_scope("workflows", root_id="envA")
    assert resolved["mode"] == "global"
    assert resolved["source"] == "legacy_alias"
    assert Path(resolved["path"]) == global_dir

    wf.save_config({"use_global_path": False, "global_path": str(global_dir), "env_paths": {}})
    resolved_private = scope_module.resolve_scope("workflows", root_id="envA")
    assert resolved_private["mode"] == "private"
    assert Path(resolved_private["path"]) == workspace["comfy_a"] / "user" / "default" / "workflows"


def test_manifest_export_excludes_secrets_and_env_values(workspace):
    """密钥 / API Key / 环境变量值绝不入 manifest，只保留变量名。"""
    cfg = _load(workspace["manager"])
    cfg["environments"][0]["config"]["advanced_env_vars"] = "OPENAI_API_KEY=sk-very-secret\nHF_TOKEN=hf-secret"
    workspace["manager"].save_config(cfg)

    exported = manifest_module.export_manifest()
    text = json.dumps(exported, ensure_ascii=False)

    assert "sk-very-secret" not in text
    assert "hf-secret" not in text
    assert exported["secrets_included"] is False
    root_entry = next(r for r in exported["roots"] if r["id"] == "envA")
    assert "OPENAI_API_KEY" in root_entry["env_var_names"]
    assert "HF_TOKEN" in root_entry["env_var_names"]


def test_manifest_preview_missing_and_conflict(workspace, monkeypatch):
    """缺失目录 → missing；同一空间 id 指向不同路径 → conflict。"""
    exported = manifest_module.export_manifest()

    # 缺失：把空间路径改成不存在的目录
    missing = dict(exported)
    missing["data_spaces"] = [dict(s) for s in exported["data_spaces"]]
    missing["data_spaces"][0]["path"] = str(workspace["root"] / "does-not-exist")
    missing.pop("integrity", None)
    preview = manifest_module.preview_import(missing)
    assert preview["success"] is True
    assert any(i["status"] == "missing" for i in preview["items"])
    assert preview["summary"]["missing"] >= 1

    # 冲突：索引中同一空间 id 指向另一个已存在目录（本机仍指向原路径）
    local = _load(workspace["manager"])
    other = workspace["root"] / "other-space"
    other.mkdir(parents=True, exist_ok=True)
    conflict_manifest = manifest_module.export_manifest()
    conflict_manifest["data_spaces"] = [dict(s) for s in conflict_manifest["data_spaces"]]
    local_space_id = str(local["data_spaces"][0]["id"])
    target = next(s for s in conflict_manifest["data_spaces"] if s["id"] == local_space_id)
    assert Path(local["data_spaces"][0]["path"]) != other
    target["path"] = str(other)
    conflict_manifest.pop("integrity", None)
    preview_conflict = manifest_module.preview_import(conflict_manifest)
    assert any(i["status"] == "conflict" for i in preview_conflict["items"])


def test_manifest_import_backs_up_and_keeps_pointer(workspace, monkeypatch):
    """导入：备份注册表、缺失目录按失效引用保存、默认不改指针。"""
    pointer_file = workspace["root"] / "pointer.txt"
    pointer_file.write_text(str(workspace["root"]), encoding="utf-8")
    monkeypatch.setattr(paths, "get_userdata_pointer_file", lambda: pointer_file)

    exported = manifest_module.export_manifest()
    exported["data_spaces"][0]["path"] = str(workspace["root"] / "missing-space")
    exported.pop("integrity", None)

    result = manifest_module.import_manifest(exported, {"overwrite": False, "update_pointer": False})
    assert result["success"] is True
    assert result["pointer_changed"] is False
    assert Path(result["backup_dir"]).exists()
    assert (Path(result["backup_dir"]) / "environments.json").exists()
    assert pointer_file.read_text(encoding="utf-8") == str(workspace["root"])

    cfg = _load(workspace["manager"])
    assert any(Path(s["path"]) == workspace["root"] / "missing-space" for s in cfg["data_spaces"])
    # 不创建缺失目录
    assert not (workspace["root"] / "missing-space").exists()


def test_onboarding_branches(workspace, monkeypatch, tmp_path):
    """无注册表且无旧数据 → 新建/导入；指针失效 → 只读引导；正常 → normal。"""
    config_file = workspace["config_dir"] / "environments.json"
    if config_file.exists():
        config_file.unlink()

    pointer_file = tmp_path / "pointer.txt"
    monkeypatch.setattr(paths, "get_userdata_pointer_file", lambda: pointer_file)

    state = manifest_module.get_onboarding_state()
    assert state["mode"] == "new_or_import"
    assert state["needs_onboarding"] is True

    pointer_file.write_text(str(tmp_path / "gone"), encoding="utf-8")
    state_invalid = manifest_module.get_onboarding_state()
    assert state_invalid["mode"] == "readonly_relocate"
    assert state_invalid["pointer_invalid"] is True

    pointer_file.unlink()
    workspace["manager"].save_config({"version": "1.0.0", "environments": [], "current_environment_id": None})
    state_normal = manifest_module.get_onboarding_state()
    assert state_normal["mode"] == "normal"


def test_cli_runtime_override_keeps_pointer_untouched(tmp_path, monkeypatch):
    """命令行覆盖只对本次进程生效；机器级指针文件内容不变。"""
    pointer_file = tmp_path / "pointer.txt"
    pointer_file.write_text("ORIGINAL", encoding="utf-8")
    monkeypatch.setattr(paths, "get_userdata_pointer_file", lambda: pointer_file)

    isolated = (tmp_path / "isolated-userdata").resolve()
    paths.configure_runtime_overrides(user_data_dir=isolated, instance_name="test-instance")
    try:
        root, source, _note = paths.resolve_user_root()
        assert root == isolated
        assert source == "cli_override"
        assert paths.get_runtime_instance_name("Comfyui-Box") == "test-instance"
        assert paths.is_test_mode() is True
        assert pointer_file.read_text(encoding="utf-8") == "ORIGINAL"

        from backend.src.core import deploy_env
        from backend.src.utils.test_isolation import guard_write

        # dev 用 --user-data-dir 起自己的沙箱时要能正常写入，
        # 不能因为"本次是隔离实例"就把开发环境一起锁死。
        assert deploy_env.is_write_guard_enabled() is False
        assert guard_write("安装插件") is None

        # 只有 --test-mode 或 test 环境才拒绝写真实 ComfyUI 根
        deploy_env.set_write_guard_override(True)
        try:
            assert guard_write("安装插件") is not None
        finally:
            deploy_env.set_write_guard_override(False)
    finally:
        paths._runtime_user_root = None
        paths._runtime_instance_name = None
        paths._runtime_test_mode = False
        paths._reset_root_cache()
