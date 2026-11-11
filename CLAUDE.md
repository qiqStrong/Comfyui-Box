# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Last verified**: 2026-11-10（资源目录统一到 `source-code/resource/`、`frontend/public/` 取消、运行数据移出版本控制；其余条目按 2026-11-01 核对结果保留）。文中路径、命令与版本号均以实际命令输出核实；无法用命令验证的性能/体验类描述已标注"未核实"。
> 结构/版本类信息以本文件为唯一来源；产品功能介绍以根目录 `README.md` 为唯一来源，`source-code/README.md` 只做源码目录导航。

## 项目概述

Comfyui-Box 是一个为 ComfyUI 设计的现代化管理平台（仅支持 Windows），采用 React 19 前端 + Python 后端（pywebview 桌面应用）架构。核心目标是治理和优化 ComfyUI 生态：环境管理、版本控制、插件市场、依赖管理、AI 助手、工作流解析等。

**技术栈：**
- **前端**: React 19（`frontend/package.json`: `react ^19.2.0`）, TypeScript, Vite 7, TailwindCSS, Zustand, React Router, Radix UI
- **后端**: Python **3.12.x**（`backend/requirements.txt` 第 2 行注释声明 `# Python 3.12.x`，无 `python_requires` 元数据），pywebview `>=6.0,<7.0`, Flask, aiohttp, psutil
  - 本机开发环境为 Python 3.12.3；3.13+ 未验证（`GPUtil 1.4.0` 依赖 `distutils`，需额外安装 `setuptools`；`pythonnet` 存在兼容风险）
- **Git**: 不在仓库/发布包内自带可执行文件。首次启动由 `backend/main.py` 的 Bootstrap 窗口引导：自动下载 MinGit（`src/utils/mingit_downloader.py`: `DEFAULT_VERSION = "2.53.0.2"`）或使用用户已有的系统 Git
  - 仓库内的 `backend/MinGit-2.53.0-64-bit/` 只有 181 个配置/文档文件（`git ls-files` 计数），**不含 `git.exe`**；`build_exe.spec` 与 `build_scripts/*.ps1` 中也没有 MinGit 打包逻辑

## 关键构建命令

### 开发环境

**系统前置（Windows）**：需要 .NET 8 Desktop Runtime、Edge WebView2 Runtime、VC++ 2015-2022 x64 运行库；缺任一项 `preflight` 预检会弹窗，极端情况下进不去主界面。

**版本要求**：Python **3.12.x**（本机 3.12.3，`backend/requirements.txt:2` 注释声明）；Node 需满足 Vite 7 的 `^20.19.0 || >=22.12.0`（23.x 等奇数列会触发 EBADENGINE 警告）。

```bash
# 前端开发
cd source-code/frontend
npm ci               # 按 package-lock.json 精确安装（推荐）
npm install          # 安装/更新依赖
npm run dev          # 开发服务器
npm run build        # 生产构建（产物输出到 source-code/dist/）
npm run lint         # ESLint 检查
npm run test:run     # 单次运行 Vitest（CI/验收用）
npm run test         # Vitest watch 模式（本地开发）
npm run test:ui      # Vitest UI 模式
npm run test:coverage  # 覆盖率报告

# 后端开发（需要 Python 3.12.x，本机使用 3.12.3）
cd source-code/backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 后端测试
pip install -r requirements-test.txt
python -m pytest                    # 运行所有测试
python -m pytest tests/unit         # 单元测试
python -m pytest tests/integration  # 集成测试
python -m pytest -v -s              # 详细输出
python -m pytest -k "test_name"     # 运行特定测试
pytest --cov=src --cov-report=html  # 覆盖率报告

# 运行主应用（默认 dev 环境：端口 5002）
# 首次运行或前端改动后，必须先构建前端（产物在 source-code/dist/）
cd source-code/frontend
npm run build
cd ../backend
python main.py

# 显式指定环境（可选：dev / test / prod）
python main.py --env test
# 或使用环境变量
set COMFYUI_BOX_ENV=test
python main.py
```

### 生产构建

```powershell
# build.ps1 / quick_build.ps1 都位于 source-code/ 目录（仓库根目录没有这两个脚本）
cd source-code
.\build.ps1 -Version "1.0.2"

# build.ps1 支持的参数（见 source-code/build.ps1 param 块）：
# -Version       指定版本号，缺省时读 source-code/comfyui_box_version.py 的 __version__
# -SkipFrontend  跳过前端构建
# -SkipClean     跳过清理
# -SkipTests     跳过测试
# -VerboseOutput 详细输出

# quick_build.ps1 没有任何参数（Get-Command 实测 Parameters 数量为 0），只能交互式使用
.\quick_build.ps1

# 构建产物位于 source-code/build_scripts/打包产物_<版本号>/
```

> **生产构建前置**：`build_scripts/构建.ps1:36` 固定使用 `source-code\.venv`，缺失时 `exit 1`。首次打包前先建该环境并装好依赖：
>
> ```powershell
> cd source-code
> python -m venv .venv
> .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
> .\.venv\Scripts\python.exe -m pip install pyinstaller
> ```

版本号唯一来源：`source-code/comfyui_box_version.py`（当前 `__version__ = "V1.0.0"`），缺省回落值 `"V1.0.0"`（`build_scripts/构建工具库.ps1:93-117`）。**不存在名为 `VERSION` 的文件。**

## 架构设计

### 1. 前端架构 (`source-code/frontend/`)

```
frontend/
├── src/
│   ├── pages/          # 页面组件（与侧边栏菜单一一对应）
│   ├── components/     # 可复用 UI 组件
│   ├── contexts/       # React Context（全局状态）
│   ├── stores/         # Zustand store
│   ├── utils/          # 工具函数（另有 types/、mocks/、test/）
│   ├── hooks/          # 自定义 React hooks
│   ├── api/            # 部分后端桥接封装（现有 3 个模块：dependencyApi / githubApi / workflow）
│   ├── services/       # 另一部分封装（bridge / pluginService / PluginAPIService / pluginMarketplaceService / versionApi）
│   ├── router/         # 路由配置
│   ├── i18n/           # 国际化配置
│   └── lib/            # 工具函数库
├── main.tsx            # 主窗口入口
└── floating-main.tsx   # 浮动窗口入口（独立应用）
```

**关键约定：**
- **页面与路由**：每个 `pages/` 下的文件对应一个路由，路由配置在 `router/` 中集中管理
- **API 调用**：通过 `window.pywebview.api.<method>()` 调用后端。现状是**未完全收敛**：`src/` 下（排除 `__tests__`）有 64 个文件、268 处直接引用 `window.pywebview.api`（`grep -rln` 实测），封装分散在 `api/`（3 个模块）与 `services/`（5 个模块）两处。新增调用请放进 `api/` 或 `services/`，不要在组件里直接摸 `window`。
- **状态管理**：全局状态使用 Zustand，局部状态优先使用 React hooks
- **样式规范**：TailwindCSS utility-first，避免内联样式，复用 `components/ui/` 下的基础组件

### 2. 后端架构 (`source-code/backend/`)

```
backend/
├── src/
│   ├── bridge/         # 前端桥接层
│   │   ├── api.py      # 暴露给前端的主 API 类（`class Api`）
│   │   └── controllers/  # 业务逻辑控制器
│   ├── core/           # 核心业务层
│   │   ├── env/        # 环境管理（EnvironmentManager 核心）
│   │   ├── plugin/     # 插件管理
│   │   ├── ai/         # AI 服务（多模型支持）
│   │   ├── dependency/ # 依赖分析与冲突检测
│   │   ├── cache/      # 缓存服务
│   │   └── config/     # 配置管理器
│   ├── utils/          # 工具函数（logger, file_ops, etc.）
│   └── gallery/        # 资产库（图片 NSFW 检测、瀑布流）
├── main.py             # 应用入口（含首次启动的 Git/MinGit Bootstrap 引导）
├── MinGit-2.53.0-64-bit/  # 仅配置与文档骨架，**不含 git.exe**；可执行文件由 Bootstrap 下载或指向系统 Git
├── resource/           # 随包只读资源（入库，三环境共用）
│   ├── img/logo/       # icon.ico / icon.png / app-icon.png / favicon.ico
│   ├── img/icons/      # tg-icon、github-mark、icons/app/（设计备选图）
│   ├── img/qr/         # sponsor-qr、tg-qr
│   ├── img/avatars/    # AI 平台头像
│   ├── models/         # nsfw.onnx
│   └── config/         # default_config.json 等随包默认模板（只读）
└── tests/              # 测试套件
```

**资源引用规则**：Python 侧统一经 `src/utils/paths.py` 的 `get_resource_dir()` 及派生函数（`get_resource_logo_dir` / `get_resource_icons_dir` / `get_resource_qr_dir` / `get_resource_avatars_dir` / `get_resource_models_dir` / `get_resource_config_dir`）；前端侧经 Vite `publicDir`（指向 `../resource/img`）以 `/logo/...` 等稳定 URL 引用。禁止在 `backend/`、仓库根另立图片或模型文件。

**关键约定：**
- **API 暴露规则**：`src/bridge/api.py` 的 `class Api` 中仅公开方法暴露给前端，私有属性以 `_` 开头（pywebview 序列化限制）
- **环境管理**：`EnvironmentManager` 是核心，负责 ComfyUI 环境的扫描、验证、配置和启动
- **控制器职责**：`controllers/` 层处理业务逻辑，`core/` 层是纯业务服务，避免循环依赖
- **日志规范**：使用 `backend.src.utils.logger` 的 `app_logger`，支持 emoji 自动替换（Windows 控制台兼容）

### 3. 数据流架构

```
前端组件
   ↓ (window.pywebview.api.method())
api.py 的 class Api（路由层）
   ↓
Controller（业务逻辑层）
   ↓
Core Service（核心服务层）
   ↓
File/Git/Process（系统层）
```

**示例（按实际代码核对）：**
- 用户点击"启动 ComfyUI" → 前端 `window.pywebview.api.start_comfyui(env_id)` → `api.py:2816 start_comfyui()`（逻辑写在 `Api` 里，用 `self.__init_process_manager()` 起 `ProcessManager`）→ 子进程
  - `EnvironmentController` 负责环境增删改查/预设/扫描等方法，**没有** `start_comfy()`
- 插件市场列表 → `MarketplaceControllerBridge.search_plugins()`（`bridge/controllers/marketplace_controller_bridge.py:114`）→ `core/marketplace/marketplace_controller.py` → `CacheManager`（**文件缓存**，`cache_manager.py:26`）→ `PluginDataFetcher`（网络）
  - 实测只有"文件缓存 + 网络"两级；`grep -rn "三级缓存" backend/src` 无命中

## 关键模块说明

### 环境管理 (`core/env/`)
负责 ComfyUI 环境的全生命周期管理：
- **EnvironmentManager**: 主入口，协调扫描、验证、启动
- **EnvironmentScanner**: 自动检测目录下的 ComfyUI 安装
- **EnvironmentValidator**: 验证环境有效性（Python、Git、依赖）
- **LaunchArgsBuilder**: 构建启动参数（支持 Flux 预设、极客模式）
- **DependencyDetector**: 检测 Python/PyTorch/CUDA 版本

### 插件管理 (`core/plugin/`)
- **PluginManager**: 安装、更新、启用/禁用插件（`plugin_manager.py`）
- 同目录还有 `dependency_checker.py` / `dependency_manager.py` / `git_permission_fixer.py` / `plugin_backup.py` / `plugin_scanner.py` 等

### 依赖分析 (`core/dependency/`)
- **DependencyAnalyzer**: 分析 Python 依赖树和版本冲突（`dependency_analyzer.py`）
- **ConflictDetector**: 检测并标记依赖冲突（`conflict_detector.py`）

### AI 助手 (`core/ai/`)
已注册的 Provider（`providers/factory.py` 的 `_providers`）：`openai`、`xflow`、`iflow`、`custom-openai`（以上复用 `OpenAIProvider`）、`spark`（讯飞星火）、`volcengine`（火山引擎）、`zhipu`（智谱）、`ollama`。
**没有 Anthropic/Claude 原生 Provider**；Claude 只能通过兼容 OpenAI 接口的中转服务接入。
- **AIService**: 统一 AI 调用接口（`ai_service.py`）
- **providers/**: 各模型的适配器（BaseProvider 继承）
- **search/**: 联网搜索（`search_manager.py`: DuckDuckGo 始终可用，Google 需 api_key + search_engine_id，Tavily 需 api_key）
- **DocumentProcessor**: 文档/图片分析（`document_processor.py`）
- **SecretStore**: 服务商 API Key 的加解密入口（`secret_store.py`）。每个安装实例在启动时生成/读取自己的 Fernet 密钥（`data/secrets/ai_fernet.key`），**没有内置公共密钥**；详见「开发注意事项 8. 密钥与敏感数据」

### 缓存系统 (`core/cache/`)
`CacheService`（`cache_service.py:33`）是**缓存统计与清理**服务，公开方法只有 `get_cache_stats / get_all_cache_stats / clear_cache / clear_all_caches / get_cache_types`，**没有 `get()` 读取接口**。
- 管理 5 类缓存：`version / translation / plugin / update / marketplace`（`CacheType`, `cache_service.py:24-31`），落在 `get_cache_dir()` 下（translation 用 `translation_cache.db`）
- 真正的"读取缓存 → 回源网络"逻辑在 `core/marketplace/`（`CacheManager` + `PluginDataFetcher`），是文件缓存 + 网络两级

## 开发注意事项

### 1. 添加新功能时
- **前端页面**：在 `pages/` 下添加 `.tsx` 文件，在 `router/` 注册路由
- **后端 API**：在 `src/bridge/api.py` 的 `class Api` 中添加公开方法（非私有），在 `controllers/` 实现逻辑
- **测试**：前端在组件同目录加 `.test.tsx`，后端在 `tests/` 下添加 `test_*.py`

### 2. Git 操作
Git 可执行文件由首次启动的 Bootstrap 引导获得（下载 MinGit 或复用系统 Git），统一通过 `get_git_executable()`（`src/utils/git_config.py`）解析，不要直接调用 `subprocess`。
业务侧用 `GitManager`（`src/core/git_manager.py`）的方法，注意它**没有** `clone()` / `checkout_branch()`：
```python
from backend.src.core.git_manager import GitManager
git_manager = GitManager(repo_path)
git_manager.get_versions(version_type='stable')   # 版本列表
git_manager.switch_version(version_id)            # 切换稳定版/开发版
git_manager.rollback_to_commit(commit_hash)       # 回退到指定提交
git_manager.get_branches() / git_manager.switch_branch(branch_name)
```
（另有 `src/utils/git_manager.py`，是 MinGit/系统 Git 的**可用性检测**，与上面的 `GitManager` 类不同名同义，别混用。）

### 3. 进程管理
ComfyUI 启动使用 `ProcessManager`（`src/core/process_manager.py`），自动处理端口冲突、进程检测、日志捕获。实际签名：
```python
process_manager.start(python_path, comfyui_path, args=None, env_config=None)  # -> Dict
```

### 4. 依赖冲突处理
`DependencyAnalyzer` 与 `ConflictDetector` 位于 **`core/dependency/`**（不在 `core/plugin/`）：
- 冲突分级实测为 `'critical' | 'warning' | 'info'`（`conflict_detector.py:299-329`、`models.py:69`），没有 `error` 等级
- `_generate_suggestion()` 生成修复建议

### 5. 国际化
- 前端：在 `i18n/locales/` 下添加翻译（中英文必备）
- 使用 `react-i18next` 的 `useTranslation` hook

### 6. 构建与打包
- PyInstaller 配置（均在 `source-code/`）：`build_exe.spec`（发布版，`console=False`）、`build_exe_debug.spec`（调试版，`console=True`）、`backend/updater/updater.spec`（更新器，由 `build_scripts/构建.ps1:300` 调用）
  - 仓库根还有个 `Comfyui-Box.spec`（`console=True`），在 `build_scripts/*.ps1` 中**没有任何引用**（`grep -rn "\.spec" build_scripts/` 实测）
- 构建脚本（`source-code/build.ps1` → `build_scripts/构建.ps1`）会自动：
  1. 构建前端 → 产出到 `source-code/dist/`（`构建.ps1:35` 的 `$TempDistDir`）
  2. 打包后端 → PyInstaller 生成 exe
  3. 合并产物 → `source-code/build_scripts/打包产物_<版本号>/`
- 注意：**构建脚本不打包 MinGit**，Git 由应用首次启动的 Bootstrap 引导下载或复用系统 Git

### 7. 构建产物与版本控制（重要）

**原则：构建产物不入库，发布包通过构建脚本 / Releases 分发。**

- 以下路径均为生成物，**不要提交**：
  - `source-code/dist/`：前端构建输出，同时是开发模式下后端托管的目录
  - `source-code/build/`、`source-code/backend/{build,dist}/`：PyInstaller 中间产物 / 输出
  - `source-code/frontend/coverage/`、`source-code/frontend/tsconfig.tsbuildinfo`
- 构建相关文件只保留源码、`package-lock.json`、`resource/` 随包静态资源和测试；运行数据与本地配置一律不入库。
- 克隆后首次运行后端前，必须先 `cd source-code/frontend && npm run build`；否则 `main.py` 找不到 `dist/index.html`，无法进入主界面。
- 修改静态资源请改 `source-code/resource/`（`img/logo`、`img/icons`、`img/qr`、`img/avatars`、`models`、`config`），不要改 `dist/` 下的拷贝（会被下次构建覆盖）。Vite 的 `publicDir` 已指向 `../resource/img`，构建时原样复制到 `dist` 根，因此前端引用写作 `/logo/...`、`/icons/...`、`/qr/...`、`/avatars/...`。
- 如果历史提交中已跟踪构建产物，用 `git rm -r --cached <路径>` 移出版本控制（保留本地文件），然后提交；不要用不带 `--cached` 的 `git rm`。
- **不要用 `git ls-files -ci --exclude-standard` 批量清理**：仓库中有刻意强制跟踪的依赖与配置（如 `backend/lib/webview2_netcore/*.dll`），批量操作会误删。只清理上列构建产物路径。
- 防回归：提交前可用 `git ls-files -- 'source-code/dist/**' 'source-code/build/**' 'source-code/frontend/coverage/**' 'source-code/frontend/tsconfig.tsbuildinfo'` 检查，输出必须为空。

### 8. 密钥与敏感数据（AI 服务商 API Key）

**原则：密钥只在本机可解密，桥接层只传掩码，日志不落明文。**

- **本机密钥**：`SecretStore`（`backend/src/core/ai/secret_store.py`）在首次使用时生成 `data/secrets/ai_fernet.key`（路径由 `get_data_dir("secrets")` 解析，随安装位置变化），写入用 `mkstemp` + `fsync` + `os.replace` 原子替换，并尽力收紧权限（Windows `icacls /inheritance:r /grant:r "<user>:F"`、POSIX `0o600`）。
  - 该文件**绝不入库**：`source-code/.gitignore` 中已显式忽略 `data/secrets/`。
  - 代码里不再有硬编码 Fernet key。`secret_store.LEGACY_KEY` 只服务于历史数据迁移（读旧密文），不再用于新写入。
- **存储**：`api_configs.api_key` 列存 `encrypted:<token>`（前缀常量 `secret_store.ENCRYPTED_PREFIX`）。`ConfigManager._migrate_api_keys()` 在首次初始化时一次性把旧密钥的密文/明文改写为本机密钥密文；改写前先备份 `ai_assistant.db.bak_prekey_<时间戳>`，解不开的行列原样保留并在返回值 `failed` 中计数。该迁移幂等（重复执行不产生第二次备份、不改动已迁移行）。
  - 读取侧走 `ConfigManager._decrypt_api_key_for_read()`：某行密钥解不开（本机密钥文件被删/被换）时只把该行当作"未配置密钥"（`api_key=""`、`has_api_key=False`），不让 `list_configs()` 整体返回空列表。
- **桥接契约**：`ai_list_configs` / `ai_get_config_detail` 只返回 `APIConfigEntity.to_masked_dict()`（`api_key_masked` + `has_api_key`，**不含 `api_key`**）。需要真实密钥的操作（`ai_test_connection`、`ai_get_available_models`）由 `AIController._hydrate_api_key_from_store()` 按 `config_id` 在服务端补齐，前端不回传明文。
  - 新增返回配置对象的桥接方法时，用 `to_masked_dict()`，不要用 `to_dict()`（后者含明文 `api_key`，仅限服务端内部使用）。
  - 前端在编辑态保留空输入框（不回显掩码），提交时若 `api_key` 为空或形似掩码，后端沿用已保存的密钥。
- **日志**：打印 provider 配置前必须过 `security_utils.mask_api_key()`（`ai_service.py`、`ai_controller.py` 已按此处理）；`secret_store.mask_api_key()` 是 UI/桥接用的 `前3******后4`，两者用途不同、不要混用。
- **导出/导入**：`export_configs` 导出的是本机密钥密文，**换机后无法解密**。`import_configs` 会先解密再用本机密钥重新加密；解不开的配置仍然导入（其余字段保留），但密钥清空并在 `errors` 中提示用户重填。
- **仍未覆盖**：联网搜索 Provider 的 api_key 是明文存储的 —— `SearchConfig`（`core/ai/search/search_config.py:51`）写到 `get_config_dir()/search_config.json`（开发环境实测 `source-code/backend/config/search_config.json`，已被 `source-code/.gitignore:271` 忽略，不入库），且生效的 `ai_get_search_config`（`ai_controller.py:2452`；同名方法在 `:1066` 另有一份定义，被前者遮蔽）把该配置原样回传前端。LoRA 模型的 CivitAI key 接口同样未审计。这两处不属于本次整改范围，改动需另行立项。

### 9. 本机 HTTP 服务的安全边界（`utils/http_server.py`）

**原则：只监听回环、只服务白名单来源、URL 片段拼路径必须先收敛。**

- **绑定**：`find_available_port()`、`_run_server()`、`get_url()` 统一使用模块常量 `LOOPBACK_HOST = "127.0.0.1"`，不监听对外网卡；改端口逻辑时不要引入 `0.0.0.0`。
- **CORS**：`ALLOWED_CORS_ORIGINS` 只放行 `http://127.0.0.1[:port]` 与 `http://localhost[:port]` 的 `Origin`；其它来源拿不到 `Access-Control-Allow-Origin`（整改前是 `CORS(app)`，等于向任意网页开放本机文件读取）。
- **静态路径收敛**：所有用 URL 片段拼文件路径的路由（`/<path:path>`、`/images/<filename>`、`/prompt/images/<filename>`、`/lora/preview/<model_id>/<filename>`）都必须先过 `_resolve_within(base_dir, relative)`：
  - 拒绝 NUL、反斜杠、前导 `/`、盘符前缀（`C:` 等）、`.`/`..` 段、空段，以及 `resolve()` 后落在 `base_dir` 之外的结果（含软链接逃逸）。
  - **注意 `Path(base) / "C:/Windows/win.ini"` 会直接变成那个绝对路径**——这是整改前可复现的任意文件读；新增路由时不要直接 `base / url_fragment`。
  - 越界与不存在统一返回 `NOT_FOUND_BODY`（`"Not Found"`）404，不回显入参；500 一律返回 `INTERNAL_ERROR_BODY`，异常详情只进日志。
  - 未知但合法的前端路由仍回退 `index.html`（SPA 路由需要），只有越界请求才禁止回退。
- **仍按原样返回的**：`/gallery/thumbnail|asset/<asset_id>` 走数据库查 `asset_id`，不拼接 URL 片段；但其 `file_path` 来自库内的绝对路径，若怀疑数据库被篡改需另行评估。

### 10. 更新包的安全边界（`backend/updater/updater.py`、`core/updater/update_controller.py`）

**原则：更新包按不可信输入处理；完整性校验不通过就不下载，路径校验不通过就一个字节都不写。**

- **强制 SHA256（官方通道）**：`UpdateController.download_update()` 在下载前检查 `version.json` 的 `file_hash`，必须是 64 位十六进制（`_is_valid_sha256()`）；缺失或格式错误直接返回失败且**不调用** `UpdateDownloader.download()`。配置了 dev 更新源（`UpdateChecker.dev_token`）时允许缺省，但提供了同样会传给下载器校验。
  - 发布 `version.json` 时必须提供 `file_hash`，否则官方通道用户将无法下载更新。
- **解压前整体校验**：`_extract_update()` 先遍历 `zf.infolist()` 完成全部校验，再进入第二遍写盘，任何一个成员非法都会在写盘前中止：
  - 成员路径经 `_member_relative_path()`：拒绝 NUL、反斜杠、前导 `/`、盘符前缀、`.`/`..`/空段；再经 `_safe_extract_target()` 用 `resolve()` + `is_relative_to()` 收敛到目标目录内（含软链接逃逸）。
  - 上限：`MAX_ARCHIVE_MEMBERS = 50000`、`MAX_SINGLE_FILE_BYTES = 1 GiB`、`MAX_TOTAL_EXTRACT_BYTES = 8 GiB`；声明体积和实际写入量都会检查（声明值可伪造）。
  - 正常更新包根目录为 `Comfyui-Box/`（`EXPECTED_ROOT`），剥离前缀后不得为空。
- **不要退回旧写法**：`target_dir / member` 配合 `zf.open(member)` 在 Windows 上可被 `../../x`、`C:/Windows/x`、反斜杠成员写出目标目录。
- 修改这两处后跑 `pytest tests/unit/core/updater/test_update_hardening.py`（该测试用桩替换 `pythonnet`/`webview`，不会初始化 .NET 运行时）。

### 11. 部署环境与数据隔离（调试必读）

采用 SpringBoot 风格的多环境配置，由 `backend/src/core/deploy_env.py` 唯一判定：
- 基础配置：`resource/config/deploy.json`
- 环境差异：`resource/config/deploy-{env}.json`（dev / test / prod）

| 环境 | 端口 | 单实例锁名 | 用途 | 运行数据 |
|---|---|---|---|---|
| dev | 5002 | `Comfyui-Box-dev` | 本地改动，开发自测 | `source-code/logs/`、`source-code/cache/` |
| test | 5001 | `Comfyui-Box-test` | Git 最新代码，全量测试 | `source-code/logs/`、`source-code/cache/` |
| prod | 5000 | `Comfyui-Box` | 打包 exe，用户实际使用 | exe 安装目录的 `logs/`、`cache/` |

- **判定优先级**：`--env` 参数 ＞ `COMFYUI_BOX_ENV` 环境变量 ＞ `deploy.json` 的 `active_env` ＞ dev（默认）
- **不再根据 sys.frozen 强制判定**：打包后也可以运行 dev/test 环境用于调试
- **端口固定，占用即报错**，不自动探测空闲端口
- **数据目录**：用户数据根由用户首次启动选择（保存在 `settings.json`），运行数据（日志/缓存）在项目根下
- 启动日志首行：`env=dev(config) port=5002 instance=Comfyui-Box-dev ...`
- 改完跑 `pytest tests/unit/core/test_deploy_env.py`

### 12. 开发模式运行期事实

- **首次启动落盘**：用户级数据（资产库、提示词、工作流、AI 对话、密钥、`settings.json`）写入当前环境的数据根；运行级日志/缓存/WebView2 写入上表对应目录。
- **Git 来源**：仓库内 `backend/MinGit-2.53.0-64-bit/` 不含 `git.exe`（被 `source-code/.gitignore` 的 `*.exe` 忽略），运行期按“内置 MinGit → 系统 Git → 否决”回退（`utils/git_manager.py`）。

### 13. 启动实例的收尾责任（强制）

为验证而启动的应用实例，**谁开的谁关**，验证一结束就收尾，不得留在后台占着窗口和端口。

- **正常关闭优先**：用应用自身的 `closeApp` 流程（窗口关闭 / `WM_CLOSE`），日志里要出现 `[closeApp] 执行完毕`，退出码 0。
- **强制结束要声明**：正常关闭无效时才 `taskkill`，并在回复里明确写“已强杀、退出码非 0”，不能把强杀说成正常退出。
- **说“正在运行”前必须现场核实**：用端口监听 + 窗口枚举确认，不能沿用几分钟前的结论。实例被关掉后要主动更正，而不是让用户自己发现。
- **用户的发布版实例一律不动**：5000 端口、进程名 `Comfyui-Box.exe`。开发实例固定 5002，测试固定 5001，绝不占用 5000。
- 一次验证只保留**一个**实例；需要换环境时先关旧的再开新的，避免多实例同时写同一份配置。

### 14. dev / test 场景化假数据（`source-code/scripts/dev_fixtures.py`）

需要在 dev 或 test 环境验证页面时，用这个工具生成可识别的假数据，**不要手工往数据根里塞文件**。

```bash
cd source-code
backend/.venv/Scripts/python.exe scripts/dev_fixtures.py list                     # 看场景与变体
backend/.venv/Scripts/python.exe scripts/dev_fixtures.py seed  --env dev
backend/.venv/Scripts/python.exe scripts/dev_fixtures.py seed  --env dev --scenario edge
backend/.venv/Scripts/python.exe scripts/dev_fixtures.py seed  --env dev --only workflow --variant workflow=edge
backend/.venv/Scripts/python.exe scripts/dev_fixtures.py clean --env dev
backend/.venv/Scripts/python.exe scripts/dev_fixtures.py status --env dev
```

**三层模型**（`scripts/fixtures/registry.py`）：

- **域**：一类数据，对应一个 fixture 模块——`state` / `comfyui` / `workflow` / `gallery` / `prompt` / `lora` / `assistant`
- **变体**：该域的一种完整数据集，统一命名 `basic`（正常）/ `edge`（边界）/ `stress`（大批量）/ `empty`（空集）
- **场景**：各域变体的组合，一次把环境调成某种验证状态

| 场景 | 用途 |
| --- | --- |
| `typical` | 日常开发与全页面走查 |
| `edge` | 各域边界/脏数据，验证容错与降级 |
| `stress` | 大批量数据，验证列表性能与布局 |
| `empty` | 全部空集，验证空状态 |
| `degraded` | 环境残缺（无 Python、无插件目录），验证异常提示 |

改一个功能就用 `--only <域> --variant <域>=<变体>`，只播种相关的域，信号强、副作用小。
**边界样本必须对应真实代码分支**，不是凑数量：工作流 `edge` 的每个文件在
`scripts/fixtures/workflows.py` 顶部都有对照表，写明它覆盖哪条分支。

约束：

- **只支持 dev / test**，`--env prod` 直接抛错，不写入任何字节。
- 所有产物落在 `<数据根>/fixtures/`，逐条登记在 `.fixture_manifest.json`；`clean` 按清单删除并还原备份。
- 覆盖既有文件前备份到 `<数据根>/fixtures/backup/`；由 fixture 自己创建的文件不备份（否则 `clean` 会把假数据"还原"回去）。
- 清单里的 `domains` 段记录每个域上一次的产物，**切换变体时先回收再写入**，不会留下两套数据混杂。
- **资产库不能只写 `assets.json`**：页面打开时会用 `libraryPath` 重扫磁盘，不在库目录内的资产会被全部删除。
- 绝不指向真实 ComfyUI 路径，绝不写 prod 指针。


## 测试策略

- **前端测试**：Vitest 4 + Testing Library；`npm run test` 是 watch 模式，CI/一次性验证用 `npm run test:run`
- **后端测试**：pytest，配置在 `backend/pyproject.toml`（`testpaths = ["tests"]`，`addopts = -v --strict-markers --tb=short -s --color=yes`）
  - 已注册标记：`property`、`unit`、`integration`、`manual`、`diagnostic`、`slow`（`pyproject.toml:20-26`）
  - 想换输出格式需覆盖 addopts：`python -m pytest -o addopts="" -q tests/unit`
  - `pytest-asyncio` 1.4.1 默认 strict 模式：`async def test_*` 必须带 `@pytest.mark.asyncio`，否则报错
- **属性测试**：hypothesis（`requirements-test.txt`）
- **测试环境**：`backend/tox.ini` 提供 `py312` / `coverage` / `unit` / `integration` / `properties` 环境
- **CI/CD**：仓库根 `.github/workflows/` 共 5 个 workflow：`quality.yml`（质量门禁）、`update-version.yml`、`update_nodes.yml`、`update_comfyui_release.yml`、`sync_pytorch_versions.yml`。
  - `quality.yml` 由 `push`/`pull_request`（`main`、`develop`）与手动触发，并发组按 workflow+ref 取消旧任务。
    - **阻断项**：前端 `npx tsc --noEmit`（本地实测 0 错误）；后端 `pytest tests/unit`（本地实测 166 passed / 2 skipped）。
    - **报告项（`continue-on-error: true`）**：前端 `npm run lint`（2026-11-01 实测 811 errors / 1252 warnings）、`npm run test:run`（548 failed / 1244 passed / 4 skipped）。基线未清零前不阻断合并；清理到 0 后删除对应 `continue-on-error` 即可转为门禁。**不要**用删除测试、扩大 ignore 或 `|| true` 的方式制造绿色。
  - 后端 job 使用 `windows-latest`（应用仅支持 Windows，且含 `os.name == "nt"` 的 ACL 用例），通过 `PYTHONPATH=<repo>/source-code` 与 `working-directory: source-code/backend` 运行。
  - 仓库根 `.github/workflows/` 之外还有 `source-code/.github/workflows/update-version.yml`：GitHub 只识别仓库根目录，该文件是**无效副本**（与根目录同名文件内容一致），修改版本号同步逻辑时只改根目录那份。
  - 原先的 `source-code/.github/workflows/lint.yml` 已删除（其 `working-directory: frontend` 在本仓库不存在对应路径，从未生效）。

## 调试技巧

### 前端调试
- 在浏览器 DevTools 中可直接调用后端：`window.pywebview.api.<method>()`
- Vite 开发服务器支持 HMR，修改代码即时生效
- 开发模式下后端托管的是 `source-code/dist/`，改完前端需重新 `npm run build` 才能在桌面窗口看到效果

### 后端调试
- ~~`main.py` 的 `SIMULATE_FROZEN` 开关~~ 已删除：它算出的路径与开发分支完全相同，只在日志里说谎，容易误导排障。判断"是否打包"只看 `sys.frozen`。
- **日志位置**：源码版 `source-code/run/<env>/logs/comfyui-box_<YYYYMMDD_HHMMSS>.log`（prod 为 `source-code/logs/`）；发布版 `<安装根>\logs\...`。
  - 目录由 `src/utils/paths.py` 的 `get_log_dir()`（运行数据根下的 `logs/`，运行数据根默认是项目根）决定，`src/utils/logger.py:415-417` 调用；写入用自定义 `DateRotatingFileHandler`（`logger.py:258`、`:455`）
  - 运行数据根可用设置 `storage.runtimeDataDir` 覆盖（设置页“运行数据目录”）；项目目录不可写时降级到 `%TEMP%\Comfyui-Box\runtime-data`，并在设置页告警
  - 缓存（`cache/`）与 WebView2 用户数据（`webview2/`）与日志同源，均在运行数据根下；旧 `<用户数据根>/logs|cache` 原地保留，不删除、不搬迁
  - 清理策略：按数量保留 10 个（`cleanup_old_logs_by_count`, `logger.py:186`）或按天数保留 30 天（`cleanup_old_logs`, `logger.py:103`）
  - 不存在 `data/logs/app.log` 这个路径
- 使用 `app_logger.debug()` 输出调试信息

### 常见问题
1. **端口占用**：默认端口 8188（`src/core/env/environment_manager.py:88`），检查是否被占用，前端会显示冲突提示
2. **Git 不可用**：`backend/MinGit-2.53.0-64-bit/` 只有配置骨架、没有 `git.exe`；实际 Git 由首次启动的 Bootstrap 窗口下载 MinGit 2.53.0.2 或指定系统 Git，路径通过 `src/utils/git_config.py:20 get_git_executable()` 解析
3. **依赖冲突**：使用 `依赖管理` 页面的冲突检测功能排查

## 代码风格

- **Python**: 遵循 PEP 8，使用类型提示（Type Hints）
- **TypeScript**: 严格模式（`strict: true`），避免 `any` 类型
- **命名约定**:
  - Python: snake_case（函数/变量），PascalCase（类）
  - TypeScript: camelCase（函数/变量），PascalCase（组件/类型）
- **文档字符串**: Python 函数必须有 docstring，复杂逻辑加注释说明

### 强制禁令（提交前逐条自查，违反即返工）

以下五类写法在本仓库**一律禁止**，不接受"先这样、以后改"。

**1. 禁止命名随意**
- 禁用无意义标识符：`a`、`b`、`c`、`temp`、`tmp`、`data`、`data1`、`obj`、`res`、`info`、`flag`（除非是极短作用域的循环下标 `i/j`）。
- 禁止同一文件内混用命名风格（如 `getUserData` 与 `get_user_data` 并存）。Python 用 snake_case，TypeScript 用 camelCase，组件与类型用 PascalCase。
- 函数名必须"见名知意"：动词 + 名词，如 `resolve_user_data_root()`，不得用 `handle()`、`process()`、`do_stuff()`。
- 布尔值以 `is_` / `has_` / `can_` / `should_` 开头。

**2. 禁止格式混乱**
- 缩进统一：Python 4 空格，TypeScript 2 空格，禁止混用 Tab。
- 单行长度上限：Python 120 字符，TypeScript 120 字符；超长必须换行。
- 一行只写一条语句，禁止 `a = 1; b = 2` 这类挤压写法（TypeScript 的 `for` 头部除外）。
- 逻辑块之间必须空行分隔：函数之间空两行（Python）/ 一行（TypeScript），`import` 组与代码体之间空一行。
- 提交前必须过格式化工具，不得手工凑格式。

**3. 禁止逻辑堆砌**
- 单函数长度上限 **50 行**，超出必须拆分。
- 嵌套深度上限 **4 层**，超出用早返回（early return）或提取子函数展平。
- 一个函数只做一件事。出现"既读配置又算路径又写日志又发网络请求"即为职责不清，必须拆分。
- 修改一处会牵动全身的代码视为设计缺陷，重构后再提交。

**4. 禁止注释失职**
- 必须解释 **为什么**，而不是复述代码在做什么。`# 自增 i` 这类注释一律删除。
- 公开函数必须有 docstring，说明用途、参数、返回值、异常与副作用。
- 注释与代码不一致时，以代码为准并立即修正注释；过期注释比没有注释更有害。
- 涉及安全边界（路径收敛、密钥、外部输入）与业务规则（保留策略、重试次数）的位置必须有注释说明依据。

**5. 禁止重复与硬编码**
- 同一段逻辑出现两次即提取函数，出现三次即提取模块。
- 禁止魔法数字与魔法字符串散落：端口、超时、重试次数、路径片段、上限值一律定义为模块级常量并命名。
- 禁止在多个文件里重复拼接同一路径：路径统一由 `src/utils/paths.py` 解析，资源根统一由 `get_resource_dir()` 及其派生函数提供。
- 禁止复制粘贴式"改一个变量"的新函数，改用参数化。

**资源与路径的硬性约定（配合 `resource/` 目录规范）**
- 随包只读资源只放在 `source-code/resource/` 下，禁止在 `backend/`、`frontend/public/`、仓库根另立图片/图标/模型文件。
- 新增资源引用时，Python 侧必须走 `paths.get_resource_*()`，TypeScript 侧必须走 `/img/` 下的稳定 URL，禁止手写相对路径穿透目录。
- `source-code/data/`、`source-code/logs|cache|webview2|lora_data/` 是运行期产物，**一律不入库**；不要把示例数据、默认数据放进这些目录充当随包资源。
- 例外：仓库根目录的 `version.json`、`comfyui_api_nodes.json`、`comfyui_releases.json`、`pytorch_mapping.json` 是对外公开的 GitHub raw 端点（`https://raw.githubusercontent.com/qiqStrong/Comfyui-Box/main/<file>`），已被已发布客户端与 CI 引用，**位置不可变更**。
