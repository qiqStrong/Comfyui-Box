"""版本号同步脚本

单一事实来源: source-code/comfyui_box_version.py
同步目标:
- version.json (仓库根)
- frontend/package.json
"""

import json
import re
import sys
from pathlib import Path


def get_project_root() -> Path:
    """获取项目根目录"""
    return Path(__file__).resolve().parent.parent.parent


def get_source_version() -> str:
    """从 comfyui_box_version.py 读取版本号"""
    version_file = get_project_root() / "source-code" / "comfyui_box_version.py"
    content = version_file.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
    if not match:
        raise ValueError(f"无法从 {version_file} 解析版本号")
    return match.group(1)


def sync_version_json(version: str) -> None:
    """同步到 version.json（仅更新 version 字段，保留其余内容）"""
    version_json = get_project_root() / "version.json"
    if not version_json.exists():
        print(f"跳过 {version_json}：文件不存在")
        return

    data = json.loads(version_json.read_text(encoding="utf-8"))
    if data.get("version") == version:
        print(f"✓ {version_json.name} 已是 {version}")
        return

    data["version"] = version
    version_json.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"✓ {version_json.name}: {data.get('version', '(未知)')} → {version}")


def sync_package_json(version: str) -> None:
    """同步到 frontend/package.json"""
    package_json = get_project_root() / "source-code" / "frontend" / "package.json"
    if not package_json.exists():
        print(f"跳过 {package_json}：文件不存在")
        return

    # 去掉 V 前缀，npm 版本号不带 V
    npm_version = version.lstrip("Vv")

    data = json.loads(package_json.read_text(encoding="utf-8"))
    old_version = data.get("version")
    if old_version == npm_version:
        print(f"✓ {package_json.name} 已是 {npm_version}")
        return

    data["version"] = npm_version
    package_json.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"✓ {package_json.name}: {old_version} → {npm_version}")


def main() -> int:
    try:
        version = get_source_version()
        print(f"单一事实来源: comfyui_box_version.py = {version}\n")

        sync_version_json(version)
        sync_package_json(version)

        print(f"\n✅ 版本号同步完成")
        return 0
    except Exception as e:
        print(f"❌ 同步失败: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
