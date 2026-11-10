"""
打包前检查脚本
检查所有导入路径是否正确，避免打包后出现 ModuleNotFoundError
"""

import sys
from pathlib import Path
import re
import logging

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

# 预检只验证导入能否成功，不需要运行期日志。
# 这里先挂一个空处理器，避免 utils.logger 在导入时往 stderr 打
# 「尚未通过 setup_logger() 初始化」告警——构建脚本开着
# $ErrorActionPreference = "Stop"，任何 stderr 输出都会被当成致命错误中断打包。
logging.getLogger("Comfyui-Box").addHandler(logging.NullHandler())

print("=" * 60)
print("打包前检查")
print("=" * 60)

errors = []
warnings = []

# 检查 1: 验证 backend/__init__.py 存在
print("\n[检查 1] 验证包结构...")
backend_init = Path("backend/__init__.py")
if backend_init.exists():
    print("   ✓ backend/__init__.py 存在")
else:
    errors.append("backend/__init__.py 不存在")
    print("   ✗ backend/__init__.py 不存在")

# 检查 2: 扫描所有 Python 文件，查找错误的导入路径
print("\n[检查 2] 扫描导入路径...")
backend_src_dir = Path("backend/src")
problematic_imports = []

for py_file in backend_src_dir.rglob("*.py"):
    if "__pycache__" in str(py_file):
        continue
    
    content = py_file.read_text(encoding="utf-8")
    lines = content.split("\n")
    
    for line_num, line in enumerate(lines, 1):
        # 检查是否使用了 "from src." 的导入
        if re.match(r"^\s*from\s+src\.", line):
            problematic_imports.append({
                "file": str(py_file),
                "line": line_num,
                "content": line.strip()
            })

if problematic_imports:
    errors.append(f"发现 {len(problematic_imports)} 个错误的导入路径")
    print(f"   ✗ 发现 {len(problematic_imports)} 个错误的导入路径:")
    for item in problematic_imports[:5]:  # 只显示前 5 个
        print(f"      {item['file']}:{item['line']}")
        print(f"      {item['content']}")
else:
    print("   ✓ 未发现错误的导入路径")

# 检查 3: 验证关键模块可以导入
print("\n[检查 3] 验证关键模块导入...")
critical_modules = [
    "backend",
    "backend.src",
    "backend.src.bridge.api",
    "backend.src.core.config",
    "backend.src.core.env.environment_manager",
    "backend.src.utils.version_utils",
    "backend.src.utils.config_utils",
]

import_errors = []
for module in critical_modules:
    try:
        __import__(module)
        print(f"   ✓ {module}")
    except Exception as e:
        import_errors.append(f"{module}: {e}")
        print(f"   ✗ {module}: {e}")

if import_errors:
    errors.extend(import_errors)

# 检查 4: 验证前端构建产物
print("\n[检查 4] 验证前端构建产物...")
dist_dir = Path("dist")
index_html = dist_dir / "index.html"

if not dist_dir.exists():
    warnings.append("dist 目录不存在，需要先构建前端")
    print("   ⚠ dist 目录不存在")
elif not index_html.exists():
    warnings.append("dist/index.html 不存在，需要先构建前端")
    print("   ⚠ dist/index.html 不存在")
else:
    files = list(dist_dir.rglob("*"))
    file_count = len([f for f in files if f.is_file()])
    print(f"   ✓ 前端构建产物存在 ({file_count} 个文件)")

# 检查 5: 验证 .spec 文件
print("\n[检查 5] 验证 .spec 文件...")
spec_file = Path("build_exe.spec")
if spec_file.exists():
    spec_content = spec_file.read_text(encoding="utf-8")
    
    # 检查是否包含必要的 hiddenimports
    required_imports = [
        "backend",
        "backend.src",
        "webview",
    ]
    
    missing_imports = []
    for imp in required_imports:
        if f"'{imp}'" not in spec_content:
            missing_imports.append(imp)
    
    if missing_imports:
        warnings.append(f".spec 文件可能缺少 hiddenimports: {', '.join(missing_imports)}")
        print(f"   ⚠ 可能缺少 hiddenimports: {', '.join(missing_imports)}")
    else:
        print("   ✓ .spec 文件配置正常")
else:
    errors.append("build_exe.spec 不存在")
    print("   ✗ build_exe.spec 不存在")

# 总结
print("\n" + "=" * 60)
print("检查结果")
print("=" * 60)

if errors:
    print(f"\n❌ 发现 {len(errors)} 个错误:")
    for i, error in enumerate(errors, 1):
        print(f"   {i}. {error}")
    print("\n请修复以上错误后再进行打包！")
    sys.exit(1)
elif warnings:
    print(f"\n⚠️  发现 {len(warnings)} 个警告:")
    for i, warning in enumerate(warnings, 1):
        print(f"   {i}. {warning}")
    print("\n可以继续打包，但建议先处理警告。")
else:
    print("\n✅ 所有检查通过，可以开始打包！")

print("=" * 60)
