"""
部署环境真源测试。

覆盖：判定优先级（frozen 强制 prod > --env > 环境变量 > 配置文件 > 默认）、
公共段与差异段合并、未知环境报错、prod 关键参数不变、端口严格化。
全部通过 monkeypatch 与显式 override 隔离，不依赖本机真实环境。
"""

import socket
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[3]
_SOURCE_ROOT = _BACKEND_DIR.parent
for _p in (str(_BACKEND_DIR), str(_SOURCE_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from backend.src.core import deploy_env  # noqa: E402
from backend.src.utils import http_server  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch):
    """每个用例都从干净的默认状态开始。"""
    monkeypatch.delenv(deploy_env.ENV_VARIABLE, raising=False)
    deploy_env.set_env_override(None)
    deploy_env.set_write_guard_override(False)
    yield
    deploy_env.set_env_override(None)
    deploy_env.set_write_guard_override(False)


def test_default_env_is_dev():
    """源码运行且无任何覆盖时落到 dev，端口 5002。"""
    assert deploy_env.get_env_name() == "dev"
    assert deploy_env.get_port() == 5002


def test_cli_override_wins_over_config_file():
    deploy_env.set_env_override("test")
    assert deploy_env.get_env_name() == "test"
    assert deploy_env.get_port() == 5001
    assert deploy_env.get_env_source() == "cli"


def test_env_variable_wins_over_config_file(monkeypatch):
    monkeypatch.setenv(deploy_env.ENV_VARIABLE, "test")
    deploy_env.reset_cache()
    assert deploy_env.get_env_name() == "test"
    assert deploy_env.get_env_source() == "env_var"


def test_frozen_forces_prod_even_with_override(monkeypatch):
    """打包产物恒为 prod：外部传 --env dev 也不能把 exe 降级成开发态。"""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    deploy_env.set_env_override("dev")
    try:
        assert deploy_env.get_env_name() == "prod"
        assert deploy_env.get_env_source() == "frozen"
    finally:
        # 显式恢复，避免 fixture teardown 在 frozen 状态下解析 resource 路径
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        deploy_env.set_env_override(None)


def test_unknown_env_raises():
    with pytest.raises(ValueError, match="未知部署环境"):
        deploy_env.set_env_override("staging")


def test_public_section_merged_with_env_section():
    """差异段只覆盖同名键，公共段的其余键必须保留。"""
    deploy_env.set_env_override("dev")
    config = deploy_env.get_deploy_config()
    assert config["http"]["port"] == 5002          # 来自 dev 段
    assert config["http"]["strict_port"] is True   # 来自 defaults
    assert config["http"]["host"] == "127.0.0.1"   # 来自 defaults
    assert config["instance"]["name"] == "Comfyui-Box-dev"


def test_prod_parameters_unchanged():
    """prod 的端口、实例名、AUMID、运行数据子目录必须保持历史值。"""
    deploy_env.set_env_override("prod")
    assert deploy_env.get_port() == 5000
    assert deploy_env.get_instance_name() == "Comfyui-Box"
    assert deploy_env.get_app_user_model_id() == "Comfyui-Box.Desktop"
    assert deploy_env.get_runtime_subdir() == ""
    assert deploy_env.is_dev_updates_enabled() is False
    assert deploy_env.is_test_fixtures_enabled() is False
    assert deploy_env.is_write_guard_enabled() is False


def test_dev_and_test_have_distinct_identity():
    """三个环境在端口、锁名、AUMID 上必须两两不同，才能同机并存。"""
    identities = []
    for env in ("dev", "test", "prod"):
        deploy_env.set_env_override(env)
        identities.append(
            (deploy_env.get_port(), deploy_env.get_instance_name(), deploy_env.get_app_user_model_id())
        )
    assert len(set(identities)) == 3


def test_test_env_enables_write_guard():
    deploy_env.set_env_override("test")
    assert deploy_env.is_write_guard_enabled() is True


def test_write_guard_override_beats_config():
    deploy_env.set_env_override("dev")
    assert deploy_env.is_write_guard_enabled() is False
    deploy_env.set_write_guard_override(True)
    assert deploy_env.is_write_guard_enabled() is True


def test_strict_port_rejects_occupied_port():
    """严格模式下端口被占用必须报错，不能悄悄换端口。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as holder:
        holder.bind(("127.0.0.1", 0))
        holder.listen(1)
        busy_port = holder.getsockname()[1]

        assert http_server.is_port_available(busy_port) is False

        server = http_server.StaticFileServer.__new__(http_server.StaticFileServer)
        with pytest.raises(RuntimeError, match="已被占用"):
            server._resolve_port(busy_port, strict_port=True)


def test_non_strict_port_falls_back():
    """非严格模式保留旧的自动探测行为，换到别的端口。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as holder:
        holder.bind(("127.0.0.1", 0))
        holder.listen(1)
        busy_port = holder.getsockname()[1]

        server = http_server.StaticFileServer.__new__(http_server.StaticFileServer)
        assert server._resolve_port(busy_port, strict_port=False) != busy_port
