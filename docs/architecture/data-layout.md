# 数据分层与落点：一次讲清楚

> 目标：用户数据在同一台电脑上唯一一份（源码版与发布版共用）；日志、缓存、WebView2
> 等运行数据放在项目相对路径；系统资源随安装包；换目录、换副本、重新 clone 都能继续使用。
> 旧布局的数据原地保留，不做删除或搬迁。

---

## 一、三层判据

| 层级 | 判据 | 典型内容 | 存放位置 |
| --- | --- | --- | --- |
| **系统级** | 随安装包分发，删除项目目录即消失，可由安装包/构建重建 | `dist/`、`backend/`、MinGit、`default_config.json`、`version.json`、`tools/` | 安装目录（源码版 `source-code/`） |
| **用户级** | 用户创作或不可逆（业务数据、配置、密钥、备份） | 资产库、提示词、工作流、AI 对话、`settings.json`、`environments.json`、`ai_fernet.key`、`backup/`、`lora_data/` | **机器级用户数据根**（默认 `%LOCALAPPDATA%\Comfyui-Box\userdata`） |
| **运行级** | 可重新生成、可安全清理的运行产物 | `logs/`、`cache/`、WebView2 用户数据 | **项目相对路径**（发布版安装根 / 源码版 `source-code/`） |

判断顺序：能否重建 → 重建代价 → 删了能否找回。
缩略图与 LoRA 扫描数据虽然可重建，但代价高，因此归入用户级并随迁移一起搬；
日志/缓存可随时重建，归运行级，不进用户数据根。

---

## 二、目录结构

### 2.1 用户数据根（机器级，唯一一份）

默认位置：`%LOCALAPPDATA%\Comfyui-Box\userdata`（可在设置页更改）。

```
<userdata>\
├── data\                 # 业务数据
│   ├── gallery\assets.json
│   ├── gallery\thumbnails\*.webp
│   ├── prompt\*.json + images\
│   ├── workflows\*.json
│   ├── system_prompts.json / active_system_prompts.json
│   ├── snapshot_metadata.json
│   ├── ai_assistant.db
│   └── secrets\ai_fernet.key
├── config\               # 用户配置（settings/environments/modules/lora/presets…）
├── backup\               # 救援快照
├── lora_data\            # LoRA 扫描结果与预览
├── .initialized          # 首启完成标记
└── .migrated-from-userdata.json  # 迁移记录（只在目标侧写）
```

用户数据根**不包含** `cache/`、`logs/`、WebView2 数据；这三类在运行数据根。

### 2.2 运行数据根（项目相对路径）

默认值：

- 发布版（onedir）：`<exe 所在安装根>\`
- 源码版：`source-code\`
- dev / test 环境额外追加 `run\<env>\` 子目录（`run\dev`、`run\test`），
  prod 不加子目录，保持原路径不变。

```
<运行数据根>\
├── logs\                 # 运行日志（含 comfyui\ 子日志）
├── cache\                # 市场/翻译/扫描/更新等缓存
└── webview2\             # WebView2 用户数据（下载路径等偏好）
```

定位优先级（`resolve_runtime_dir`）：

1. 用户设置 `storage.runtimeDataDir`（设置页"运行数据目录"，绝对路径）
2. 项目根目录（发布版安装根 / 源码版 `source-code/`）
3. 项目根不可写（如装进 Program Files）→ `%TEMP%\Comfyui-Box\runtime-data`，
   并把降级原因通过状态接口返回给设置页**明确告警**；不会静默丢日志/缓存

默认值始终是项目相对路径；只有用户主动设置或目录不可写时才会改变。
旧 `<userdata>/logs`、`<userdata>/cache` 原地保留，不删除、不搬迁。

### 2.3 系统级资源

统一放在 `source-code/resource/`（随安装包分发，纳入版本控制）：

```
resource\
├── img\logo\      icon.ico · icon.png · app-icon.png · favicon.ico
├── img\icons\     平台图标（tg / github / app 设计备选）
├── img\qr\        赞助与社群二维码
├── img\avatars\   推荐关注头像
├── models\        nsfw.onnx
└── config\        deploy.json · default_config.json · modules.json
                   lora_config.json · folder_shortcuts.json · core_nodes.json · presets\
```

`dist/`、`backend/`、内置 MinGit、`version.json` 随安装包分发；
`version.json` 在打包时放入 `_internal/`，离线也能展示当前构建的更新说明。

`core_nodes.json`（312 个内置节点定义）是系统资源而非用户数据：优先读
`<userdata>/data/core_nodes.json`（用户可覆盖），缺失时回退 `resource/config/core_nodes.json`。

### 2.4 两种运行形态落点

| 数据 | 源码版（`source-code\`） | 发布版（onedir 安装根） |
| --- | --- | --- |
| 业务/配置/备份/LoRA | `<userdata>\data|config|backup|lora_data` | 同左（共用同一份） |
| 日志 | `source-code\run\<env>\logs\` | `<install_root>\logs\` |
| 缓存 | `source-code\run\<env>\cache\` | `<install_root>\cache\` |
| WebView2 | `source-code\run\<env>\webview2\` | `<install_root>\webview2\` |
| 系统资源 | `source-code\resource\` | `<install_root>\_internal\resource\` |

> 用户数据按**部署环境**分开：`userdata.location`（prod）、`userdata.location.dev`、
> `userdata.location.test` 三个独立指针，互不影响。
> 源码运行默认走 dev，打包产物由 `sys.frozen` 强制走 prod，因此开发调试不会碰到
> 用户真实使用的数据。

---

## 三、逐项清单

| 路径 | 层级 | 可重建 | 迁移必搬 | 可安全删除 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `data/gallery/assets.json` | 用户 | 否 | 是 | 否 | 资产、分类、收藏 |
| `data/gallery/thumbnails/*.webp` | 用户（高成本缓存） | 可但代价高 | 是 | 否 | 迁移时一起搬 |
| `data/prompt/*.json`、`prompt/images` | 用户 | 否 | 是 | 否 | 提示词库 |
| `data/workflows/*.json` | 用户 | 否 | 是 | 否 | 工作流元数据 |
| `data/system_prompts.json`、`active_system_prompts.json` | 用户 | 否 | 是 | 否 | AI 系统提示词 |
| `data/snapshot_metadata.json` | 用户 | 否 | 是 | 否 | 快照元数据 |
| `data/ai_assistant.db` | 用户 | 否 | 是 | 否 | AI 对话 / API Key |
| `data/secrets/ai_fernet.key` | 用户（最不能丢） | 否 | **是** | 否 | 解密数据库 API Key |
| `config/settings.json` | 用户 | 可默认重建 | 是 | 否 | 用户设置 |
| `config/environments.json`、`workflow_config.json`、`search_config.json`、`preset_index.json` | 用户 | 否 | 是 | 否 | 业务配置 |
| `config/modules.json`、`lora_config.json`、`folder_shortcuts.json` | 用户 | 可重建（丢选择） | 是 | 否 | 业务配置 |
| `config/presets/**` | 用户 | 否 | 是 | 否 | 用户预设 |
| `backup/*.zip` | 用户 | 否 | 是 | 确认后手动 | 救援快照 |
| `lora_data/**` | 用户（高成本缓存） | 是（重新扫描） | 是 | 是 | LoRA 扫描结果 |
| `logs/**` | 运行 | 是 | 否 | 是 | 项目相对路径 |
| `cache/**` | 运行 | 是 | 否 | 是 | 项目相对路径 |
| `webview2/**` | 运行 | 是 | 否 | 是 | 项目相对路径 |
| `default_config.json` | 系统 | 是 | 否 | 否 | 随包默认值 |
| `dist/`、`_internal/` | 系统 | 是（构建） | 否 | 是（需重建） | 前端构建与运行时 |
| `.venv`、`node_modules` | 系统 | 是（安装依赖） | 否 | 是 | 开发依赖 |
| `tools/`、MinGit、`models/*.onnx` | 系统 | 是 | 否 | 否 | 随安装包 |
| `version.json` | 系统 | 是 | 否 | 否 | 随包分发的发布元数据 |

---

## 四、用户数据根定位

1. 机器级指针 `%LOCALAPPDATA%\Comfyui-Box\userdata.location<env 后缀>`（一行纯文本，绝对路径）
   - prod：`userdata.location`
   - dev：`userdata.location.dev`
   - test：`userdata.location.test`
2. 默认目录 `%LOCALAPPDATA%\Comfyui-Box\userdata<env 后缀>`
3. 默认目录不可写 → `%TEMP%\Comfyui-Box\userdata`，并把原因返回给 UI

指针失效（目录被移动/删除/不可写）时不会静默新建空库：回退默认目录并在界面提示原因。

指针在机器级目录而不是项目内，复制/删除项目都不会带走它。

---

## 五、部署环境隔离（dev / test / prod）

真源：`source-code/resource/config/deploy.json`，唯一读取入口
`backend/src/core/deploy_env.py`。判定优先级（高 → 低）：

1. `sys.frozen` 为真 → 强制 `prod`（打包产物永远是 prod）
2. 启动参数 `--env <name>`
3. 环境变量 `COMFYUI_BOX_ENV`
4. `deploy.json` 的 `current_env`
5. 默认 `dev`

配置采用"公共段 + 环境差异段"覆盖：`defaults` 与 `environments.<env>` 深度合并，
所以新增环境只需补差异项。

| 项 | dev | test | prod |
| --- | --- | --- | --- |
| HTTP 端口 | 5002 | 5001 | 5000 |
| 单实例锁名 | `Comfyui-Box-dev` | `Comfyui-Box-test` | `Comfyui-Box` |
| AppUserModelID | `Comfyui-Box.Desktop.dev` | `Comfyui-Box.Desktop.test` | `Comfyui-Box.Desktop` |
| 运行数据子目录 | `run/dev` | `run/test` | 无 |
| 用户数据指针 | `userdata.location.dev` | `userdata.location.test` | `userdata.location` |
| 写保护 | 关 | 开 | 关 |
| 开发版更新源 | 开 | 关 | 关 |

端口为严格模式：被占用时直接弹原生错误框退出，不静默换端口。

`prod` 的文件名、目录名、默认路径与改造前完全一致，**零迁移**。

---

## 六、dev / test 场景化假数据

工具：`source-code/scripts/dev_fixtures.py`（仅 dev / test，拒绝 prod）。

```
python scripts/dev_fixtures.py list                                        # 场景与变体目录
python scripts/dev_fixtures.py seed  --env dev                             # 默认 typical
python scripts/dev_fixtures.py seed  --env dev --scenario edge             # 全量边界数据
python scripts/dev_fixtures.py seed  --env dev --only workflow \
                                    --variant workflow=edge                # 只播种工作流边界
python scripts/dev_fixtures.py clean --env dev                             # 清理并还原
python scripts/dev_fixtures.py status --env dev                            # 查看登记情况
```

三层模型（`scripts/fixtures/registry.py`）：

| 概念 | 含义 |
| --- | --- |
| 域 | 一类数据，一个 fixture 模块：`state` / `comfyui` / `workflow` / `gallery` / `prompt` / `lora` / `assistant` |
| 变体 | 该域的完整数据集：`basic` / `edge` / `stress` / `empty` |
| 场景 | 各域变体的组合：`typical` / `edge` / `stress` / `empty` / `degraded` |

改哪个功能就只播种哪个域。边界样本按真实代码分支设计，工作流变体的对照表写在
`scripts/fixtures/workflows.py` 模块顶部（多插件依赖 / 未知节点 / 虚拟节点 / 空图 /
大图 / 损坏 JSON / 顶层非对象 / API 格式 / 子图 / 嵌套目录 / 超长文件名）。

产物与约束：

- 所有文件落在 `<数据根>/fixtures/`，`.fixture_manifest.json` 逐条登记。
- 覆盖既有文件前先备份到 `<数据根>/fixtures/backup/`，`clean` 原样还原；
  由 fixture 自己创建的文件不备份，`clean` 直接删除。
- 清单 `domains` 段记录每个域上一次的产物，切换变体时先回收再写入，
  不会出现两套数据混在一起。
- 假 ComfyUI 是独立目录骨架（`main.py` + `comfy/` + `custom_nodes/` + `models/`
  + `user/default/workflows/`），带一个本地裸仓库当 `origin`，全程离线。
  `degraded` 变体故意缺 `custom_nodes` 与 git 仓库，用于验证异常提示。
- 资产库把媒体文件真正放进 `<数据根>/fixtures/library/<分类>/`，由扫描器建索引；
  图片内嵌 `workflow` PNG 文本块，用于验证元数据解析链路。
- 不写入真实 ComfyUI 路径，不写入 prod 指针。

---

## 七、迁移时做什么

入口：首启弹窗的"迁移旧数据"、设置页的"迁移到新目录 / 更改目录（迁移当前数据）"。

1. **源目录只读**：只读取旧布局根（`data`、`config` 或 `backend/config`、`backup`、`lora_data`），
   不删除、不写标记、不改文件。
2. **复制到暂存区**：在目标根下建 `.migrating-<id>/`，先复制到暂存，避免直接污染目标。
3. **校验源数据**：资产数、分类数、缩略图数、提示词 JSON/图片数、工作流文件数、
   配置/备份/LoRA 文件数、数据库字节数与话题数、密钥 SHA-256。
4. **合并策略**：目标为空库时覆盖空默认文件；目标已有数据时只补缺失文件，不覆盖已有文件。
5. **复核**：目标计数应与源一致（或至少齐全），并执行密钥校验——用目标
   `data/secrets/ai_fernet.key` 解密 `ai_assistant.db` 中所有 `encrypted:` 开头的 API Key；
   有加密 Key 却缺密钥或解密失败 → 判定失败。
6. **失败回滚**：删除本次新建/覆盖的文件与暂存区；目标原有数据不受影响。
7. **成功后的指针**：迁移到新目录时，同时写入机器级指针，确保下次启动进入新目录；
   旧目录保持原样，由用户自行决定是否删除。
8. **重启生效**：迁移/切换后当前进程不切换数据根，必须重启应用。
9. **迁移范围不含运行数据**：`cache/`、`logs/`、`webview2/` 不参与迁移，旧位置原地保留。

---

## 八、设置页

设置 → 数据目录，包含两块：

### 7.1 用户数据目录

- 只读展示当前根、来源（默认 / 用户指定 / 临时降级）、计数。
- 按钮：复制路径、打开目录、刷新、更改目录、迁移到新目录、迁移旧数据、
  清理缓存与日志、清空业务数据（二次确认，重启后执行）。

### 7.2 运行数据目录（日志 / 缓存 / WebView2）

- 展示当前运行数据根、来源（项目目录 / 用户指定 / 临时降级）与三类子路径。
- 按钮：更改运行数据目录、恢复默认（项目目录）、打开目录。
- 项目目录不可写时展示黄色告警条，说明降级原因；更改后需重启应用。
- 该设置写入用户配置 `storage.runtimeDataDir`，默认空值表示项目相对路径。

### 7.3 清理缓存与日志

只清理运行数据根下的 `cache/`、`logs/` 内容；旧 `<userdata>/cache|logs` 不删除、不搬迁。

---

## 九、WebView2 说明

- WebView2 的用户数据目录参数只接受**绝对路径**；`get_webview2_dir()` 返回
  `<运行数据根>/webview2` 的绝对路径（`resolve()` 后）。
- 默认仍是项目相对路径（发布版安装根 / 源码版 `source-code/`）。
- 安装目录不可写时随运行数据根一起降级到 `%TEMP%\Comfyui-Box\runtime-data\webview2`，
  设置页会显示告警；用户也可在设置页把运行数据目录改到其他可写位置。
- 若运行在含非 ASCII 字符的目录且 WebView2 初始化异常，可在设置页把运行数据目录
  指定为纯 ASCII 可写目录（这是最小可行替代，不会静默回到 AppData）。

---

## 十、代码入口

- `backend/src/utils/paths.py`：所有路径的唯一出口
  （`resolve_user_root`、`resolve_runtime_dir`、`get_data_dir`、`get_config_dir`、
  `get_backup_dir`、`get_lora_data_dir`、`get_cache_dir`、`get_log_dir`、
  `get_webview2_dir`、`get_resource_*_dir`、旧布局候选）。
- `backend/src/core/deploy_env.py`：部署环境真源（端口 / 锁名 / AUMID / 运行子目录 /
  指针后缀 / 写保护 / 数据源开关）。
- `backend/src/core/userdata/manager.py`：状态、首启初始化、迁移、运行目录设置、清理。
- `backend/src/bridge/api.py`：`userdata_*` 桥接 API（含 `userdata_set_runtime_dir`）。
- 前端：`components/settings/DataStorageSettings.tsx`、`components/settings/DataDirSetupDialog.tsx`。
- 启动顺序：`main.py` 先解析 `--env` → 单例检查 → `apply_pending_wipe()` → 数据模块初始化。

### 自动化测试

- `tests/unit/utils/test_paths_userdata.py`：用户数据根定位、运行数据项目相对路径、
  设置覆盖、不可写降级、单一指针、prod 路径不变。
- `tests/unit/core/test_userdata_manager.py`：迁移/回滚/密钥校验、运行目录清理、
  旧 `<userdata>/cache|logs` 保留。
- `tests/unit/core/test_deploy_env.py`：环境判定优先级、公共段合并、prod 参数不变。
- `tests/unit/core/test_userdata_settings_carryover.py`：切换数据目录时继承旧配置。
