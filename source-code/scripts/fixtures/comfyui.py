"""构造一个假 ComfyUI 安装，并在 environments.json 里注册它。

假安装只满足"目录形态"：有 main.py、comfy/、custom_nodes/、models/、
user/default/workflows/。不包含可执行的推理代码，也不连接任何真实环境。
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Dict, List

from . import context
from .context import FIXTURE_TAG, Manifest

FIXTURE_ENV_ID = "f1c7a000-0000-4000-8000-000000000001"
FIXTURE_ENV_ALIAS = f"{FIXTURE_TAG} 假 ComfyUI"
FIXTURE_COMFYUI_VERSION = "0.3.40"

TITLE = "ComfyUI 环境"

VARIANTS = {
    "base": "完整假安装：main.py / comfy 包 / 3 个插件 / 5 个模型 / 本地 git 仓库",
    "degraded": "残缺环境：无 python 路径、无 custom_nodes、无 git，验证异常提示",
}

# 假插件：(目录名, 展示用仓库地址, 是否禁用)
FAKE_PLUGINS: List[tuple] = [
    ("ComfyUI-Manager", "https://github.com/ltdrdata/ComfyUI-Manager", False),
    ("ComfyUI-Impact-Pack", "https://github.com/ltdrdata/ComfyUI-Impact-Pack", False),
    ("ComfyUI-WD14-Tagger", "https://github.com/pythongosssss/ComfyUI-WD14-Tagger", True),
]

# 假模型文件：(相对 models/ 的路径, 大小 KB)
FAKE_MODEL_FILES: List[tuple] = [
    ("checkpoints/fixture-sdxl-base.safetensors", 4096),
    ("checkpoints/fixture-sd15.safetensors", 2048),
    ("loras/fixture-detail-tweaker.safetensors", 144),
    ("loras/fixture-film-grain.safetensors", 96),
    ("vae/fixture-vae-ft-mse.safetensors", 320),
]

_MAIN_PY = '''"""假 ComfyUI 入口，仅用于 dev/test 页面验证。"""


def main() -> None:
    raise SystemExit("这是 fixture 生成的假 ComfyUI，不能真正启动")


if __name__ == "__main__":
    main()
'''

_PLUGIN_INIT = '''"""假插件节点注册，仅用于 dev/test 页面验证。"""

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
WEB_DIRECTORY = "./web"
'''

_PLUGIN_REQUIREMENTS = "numpy>=1.24\npillow>=10.0\n"


def _write(path: Path, text: str, manifest: Manifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest.record(path)
    path.write_text(text, encoding="utf-8")


def _write_binary(path: Path, size_kb: int, manifest: Manifest) -> None:
    """写出占位模型文件：SAFETENSORS 头 + 填充零，保证大小真实。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest.record(path)
    header = b"\x00" * 8 + b'{"__metadata__":{"format":"pt"}}'
    padding = b"\x00" * max(0, size_kb * 1024 - len(header))
    path.write_bytes(header + padding)


def _build_plugins(root: Path, manifest: Manifest) -> None:
    for name, remote, disabled in FAKE_PLUGINS:
        dir_name = f"{name}.disabled" if disabled else name
        plugin_dir = root / "custom_nodes" / dir_name
        _write(plugin_dir / "__init__.py", _PLUGIN_INIT, manifest)
        _write(plugin_dir / "requirements.txt", _PLUGIN_REQUIREMENTS, manifest)
        _write(
            plugin_dir / "README.md",
            f"# {FIXTURE_TAG} {name}\n\n假插件，仅用于界面验证。\n\n来源占位：{remote}\n",
            manifest,
        )


def _build_models(root: Path, manifest: Manifest) -> None:
    for relative, size_kb in FAKE_MODEL_FILES:
        _write_binary(root / "models" / relative, size_kb, manifest)
    for sub in ("clip", "controlnet", "embeddings", "upscale_models"):
        (root / "models" / sub).mkdir(parents=True, exist_ok=True)


def _init_git_repo(root: Path, manifest: Manifest) -> None:
    """给假安装建一个最小 git 仓库。

    版本管理页读取当前环境的 git 信息，没有仓库会直接报
    ``fatal: not a git repository``；只有本地仓库又会报"远程分支不存在"。
    因此这里额外建一个本地裸仓库当 origin，全程离线，不访问网络。
    """
    git = shutil.which("git")
    if not git:
        return
    git_dir = root / ".git"
    if git_dir.exists():
        return

    remote_dir = context.fixtures_dir() / "remote" / "comfyui.git"
    remote_dir.parent.mkdir(parents=True, exist_ok=True)

    commands = [
        [git, "init", "-q"],
        [git, "-C", str(root), "config", "user.email", "fixture@local"],
        [git, "-C", str(root), "config", "user.name", "fixture"],
        [git, "-C", str(root), "add", "-A"],
        [git, "-C", str(root), "commit", "-q", "-m", f"{FIXTURE_TAG} 假 ComfyUI 初始提交"],
        [git, "-C", str(root), "tag", f"v{FIXTURE_COMFYUI_VERSION}"],
        [git, "init", "-q", "--bare", str(remote_dir)],
        [git, "-C", str(root), "remote", "add", "origin", str(remote_dir)],
        [git, "-C", str(root), "push", "-q", "-u", "origin", "HEAD:master"],
        [git, "-C", str(root), "push", "-q", "--tags", "origin"],
        [git, "-C", str(root), "remote", "set-head", "origin", "master"],
    ]
    for command in commands:
        try:
            subprocess.run(command, cwd=str(root), check=True,
                           timeout=60, capture_output=True)
        except (subprocess.SubprocessError, OSError):
            return
    manifest.record(git_dir)
    manifest.record(remote_dir)


def build_fake_install(manifest: Manifest, degraded: bool = False) -> Path:
    """创建假 ComfyUI 目录树，返回其根路径。

    Args:
        degraded: 为 True 时故意缺胳膊少腿——不建 custom_nodes、不建 git 仓库，
            用于验证环境页/依赖页在残缺环境下的提示。
    """
    root = context.fake_comfyui_dir()
    if root.exists():
        manifest.record(root)

    _write(root / "main.py", _MAIN_PY, manifest)
    _write(
        root / "comfyui_version.py",
        f'__version__ = "{FIXTURE_COMFYUI_VERSION}"\n',
        manifest,
    )
    _write(root / "comfy" / "__init__.py", f'"""假 comfy 包（{FIXTURE_TAG}）。"""\n', manifest)
    if not degraded:
        _build_plugins(root, manifest)
    _build_models(root, manifest)
    (root / "output").mkdir(parents=True, exist_ok=True)
    (root / "input").mkdir(parents=True, exist_ok=True)
    if not degraded:
        _init_git_repo(root, manifest)
    return root


def _fixture_environment(comfyui_root: Path, degraded: bool = False) -> Dict:
    """构造 environments.json 里的一条环境记录。"""
    python_exe = context.SOURCE_CODE_DIR / "backend" / ".venv" / "Scripts" / "python.exe"
    has_python = python_exe.exists() and not degraded
    timestamp = context.now_iso()
    return {
        "id": FIXTURE_ENV_ID,
        "name": f"fixture-comfyui-{FIXTURE_COMFYUI_VERSION}",
        "alias": FIXTURE_ENV_ALIAS,
        "path": str(comfyui_root),
        "version": FIXTURE_COMFYUI_VERSION,
        "versionInfo": {
            "commitHash": f"v{FIXTURE_COMFYUI_VERSION}",
            "isDev": False,
            "lastUpdated": timestamp,
        },
        "config": {
            "general": {
                "comfyui_path": str(comfyui_root),
                "python_path": str(python_exe) if has_python else "",
                "pip_path": str(python_exe.parent / "pip.exe") if has_python else "",
                "git_path": "",
            },
            "acceleration": {
                "enabled": False,
                "backend": "unknown",
                "port": 8188,
                "reserve_vram": 0.5,
                "args": "",
            },
            "folder_shortcuts": [],
            "advanced_env_vars": "",
        },
        "is_default": True,
        "dependencies": {
            "python": "3.12.3",
            "pytorch": "2.5.1+cu121",
            "cuda": "12.1",
            "sageattention": "",
            "flash_attention": "",
            "triton": "",
            "xformers": "",
        },
        "model_path_configs": [
            {
                "name": "fixture-default",
                "basePath": str(comfyui_root / "models"),
                "isDefault": True,
                "paths": {},
            }
        ],
        "envType": "portable",
        "desktopDataPath": "",
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def register_environment(manifest: Manifest, comfyui_root: Path,
                         degraded: bool = False) -> Dict:
    """把假环境写入 environments.json，并设为当前环境。"""
    config_file = context.config_dir() / "environments.json"
    registry = context.read_json(
        config_file,
        {"version": "1.0.0", "environments": [], "current_environment_id": None},
    )

    environments = [
        item for item in registry.get("environments", [])
        if item.get("id") != FIXTURE_ENV_ID
    ]
    environments.append(_fixture_environment(comfyui_root, degraded=degraded))

    registry["environments"] = environments
    registry["current_environment_id"] = FIXTURE_ENV_ID
    registry.setdefault("packages", [])
    registry.setdefault("data_spaces", [])

    context.write_json(config_file, registry, manifest)
    return registry


def seed(manifest: Manifest, variant: str = "base") -> Dict:
    """入口：建目录 + 注册环境。"""
    if variant not in VARIANTS:
        raise ValueError(f"未知 ComfyUI 变体: {variant}")

    degraded = variant == "degraded"
    root = build_fake_install(manifest, degraded=degraded)
    register_environment(manifest, root, degraded=degraded)
    return {
        "variant": variant,
        "comfyui_root": str(root),
        "environment_id": FIXTURE_ENV_ID,
        "plugins": 0 if degraded else len(FAKE_PLUGINS),
        "model_files": len(FAKE_MODEL_FILES),
        "degraded": degraded,
    }
