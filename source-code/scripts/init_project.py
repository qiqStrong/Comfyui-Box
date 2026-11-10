"""
Comfyui-Box 项目初始化脚本
一次性创建所有必要的文件夹和 __init__.py 文件
"""

from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 定义需要创建的目录结构
DIRECTORIES = [
    # 后端目录
    "backend/resources",
    "backend/src/core/config",
    "backend/src/core/env",
    "backend/src/core/installer",
    "backend/src/core/manager",
    "backend/src/core/utils",
    "backend/src/bridge/controllers",
    "backend/src/services/comfyui_process",
    "backend/src/services/websocket_proxy",
    "backend/src/services/file_system",
    "backend/tests",
    
    # 前端目录
    "frontend/src/lib",
    "frontend/src/components/ui",
    "frontend/src/components/layout",
    "frontend/src/components/business",
    "frontend/src/services",
    "frontend/src/stores",
    "frontend/src/pages",
    "frontend/src/hooks",
    "frontend/src/utils",
    "frontend/src/types",
    "frontend/src/styles",
    "resource/img/logo",
    "resource/img/icons",
    "resource/img/qr",
    "resource/img/avatars",
    "resource/models",
    "resource/config",
    
    # 文档目录
    "docs",
    
    # 构建目录
    "dist",
    "build",
]

# 需要创建 __init__.py 的 Python 包目录
PYTHON_PACKAGES = [
    "backend/src",
    "backend/src/core",
    "backend/src/core/config",
    "backend/src/core/env",
    "backend/src/core/installer",
    "backend/src/core/manager",
    "backend/src/core/utils",
    "backend/src/bridge",
    "backend/src/bridge/controllers",
    "backend/src/services",
    "backend/src/services/comfyui_process",
    "backend/src/services/websocket_proxy",
    "backend/src/services/file_system",
    "backend/tests",
]


def create_directories():
    """创建所有必要的目录"""
    print("📁 创建项目目录结构...")
    
    for directory in DIRECTORIES:
        dir_path = PROJECT_ROOT / directory
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ {directory}")
    
    print(f"\n✅ 成功创建 {len(DIRECTORIES)} 个目录")


def create_init_files():
    """创建所有 Python 包的 __init__.py 文件"""
    print("\n📝 创建 __init__.py 文件...")
    
    for package in PYTHON_PACKAGES:
        init_file = PROJECT_ROOT / package / "__init__.py"
        if not init_file.exists():
            init_file.write_text('"""Package initialization."""\n', encoding='utf-8')
            print(f"  ✓ {package}/__init__.py")
    
    print(f"\n✅ 成功创建 {len(PYTHON_PACKAGES)} 个 __init__.py 文件")


def create_gitignore():
    """创建 .gitignore 文件"""
    print("\n📝 创建 .gitignore 文件...")
    
    gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
.venv/
venv/
ENV/
env/

# Node
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
.pnpm-debug.log*

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Build
dist/
build/
*.spec

# Env
.env
.env.local

# Logs
*.log
"""
    
    gitignore_file = PROJECT_ROOT / ".gitignore"
    gitignore_file.write_text(gitignore_content, encoding='utf-8')
    print("  ✓ .gitignore")


def main():
    """主函数"""
    print("=" * 60)
    print("Comfyui-Box 项目初始化")
    print("=" * 60)
    
    create_directories()
    create_init_files()
    create_gitignore()
    
    print("\n" + "=" * 60)
    print("✅ 项目初始化完成！")
    print("=" * 60)
    print("\n下一步：")
    print("1. 初始化前端项目：cd frontend && npm create vite@latest . -- --template react-ts")
    print("2. 创建 Python 虚拟环境：python -m venv .venv")
    print("3. 激活虚拟环境：.venv\\Scripts\\activate (Windows)")
    print("4. 安装后端依赖：pip install -r backend/requirements.txt")


if __name__ == "__main__":
    main()
