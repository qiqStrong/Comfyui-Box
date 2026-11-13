# Comfyui-Box 自动打包脚本
# 用途: 自动化构建前端、打包后端、创建发布包
# 使用方法: .\build.ps1 -Version "1.0.2"

param(
    [Parameter(Mandatory=$false)]
    [string]$Version = "",
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipFrontend = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipClean = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipTests = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$VerboseOutput = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$ShowConsole = $false
)

# 设置错误处理
$ErrorActionPreference = "Stop"

# 导入公共函数库
. "$PSScriptRoot\构建工具库.ps1"

# 获取项目根目录（build_scripts 的父目录）
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$FrontendDir = Join-Path $ProjectRoot "frontend"
$BackendDir = Join-Path $ProjectRoot "backend"
$TempDistDir = Join-Path $ProjectRoot "dist"  # 临时 dist 目录（前端构建输出）
$VenvDir = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

# 如果未指定版本号，从 VERSION 文件读取
if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = Get-ProjectVersion
    Write-ColorOutput "从 VERSION 文件读取版本号: $Version" "Cyan"
}

# 构建产物目录
$BuildOutputDir = Join-Path $PSScriptRoot "打包产物_$Version"
$DistDir = Join-Path $BuildOutputDir "dist"
$BuildDir = Join-Path $BuildOutputDir "build"

# 检查命令是否存在
function Test-Command {
    param([string]$Command)
    $null = Get-Command $Command -ErrorAction SilentlyContinue
    return $?
}

# 显示构建信息
Write-ColorOutput @"

╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║              Comfyui-Box 自动打包脚本                      ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝

"@ "Cyan"

Write-Info "版本: $Version"
Write-Info "项目根目录: $ProjectRoot"
Write-Info "构建产物目录: $BuildOutputDir"
Write-Info "跳过前端构建: $SkipFrontend"
Write-Info "跳过清理: $SkipClean"
Write-Info "跳过测试: $SkipTests"
Write-Host ""

# 记录开始时间
$StartTime = Get-Date

try {
    # ============================================
    # 步骤 1: 环境检查
    # ============================================
    Write-Step "步骤 1/8: 环境检查"
    
    # 运行打包前检查
    Write-Info "运行打包前检查..."
    Push-Location $ProjectRoot
    try {
        & $VenvPython "pre_build_check.py"
        if ($LASTEXITCODE -ne 0) {
            Write-Error-Custom "打包前检查失败，请修复错误后重试"
            exit 1
        }
        Write-Success "打包前检查通过"
    } finally {
        Pop-Location
    }
    Write-Host ""
    
    # 检查 Node.js
    if (-not $SkipFrontend) {
        if (Test-Command "node") {
            $NodeVersion = node --version
            Write-Success "Node.js 已安装: $NodeVersion"
        } else {
            Write-Error-Custom "Node.js 未安装，请先安装 Node.js"
            exit 1
        }
        
        # 检查 npm
        if (Test-Command "npm") {
            $NpmVersion = npm --version
            Write-Success "npm 已安装: $NpmVersion"
        } else {
            Write-Error-Custom "npm 未安装"
            exit 1
        }
    }
    
    # 检查 Python 虚拟环境
    if (Test-Path $VenvDir) {
        Write-Success "Python 虚拟环境已存在"
    } else {
        Write-Error-Custom "Python 虚拟环境不存在: $VenvDir"
        Write-Info "请先运行: python -m venv .venv"
        exit 1
    }
    
    # 检查 PyInstaller
    $PyInstallerCheck = & $VenvPython -m pip show pyinstaller 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "PyInstaller 已安装"
    } else {
        Write-Error-Custom "PyInstaller 未安装"
        Write-Info "请先运行: .venv\Scripts\activate ; pip install pyinstaller"
        exit 1
    }
    
    # ============================================
    # 步骤 2: 清理旧文件
    # ============================================
    if (-not $SkipClean) {
        Write-Step "步骤 2/8: 清理旧文件"
        
        # 清理构建产物目录
        if (Test-Path $BuildOutputDir) {
            Write-Info "清理构建产物目录..."
            Remove-Item -Path $BuildOutputDir -Recurse -Force
            Write-Success "构建产物目录已清理"
        }
        
        # 清理临时 dist 目录
        if (Test-Path $TempDistDir) {
            Write-Info "清理临时 dist 目录..."
            Remove-Item -Path $TempDistDir -Recurse -Force
            Write-Success "临时 dist 目录已清理"
        }
    } else {
        Write-Step "步骤 2/8: 清理旧文件 (已跳过)"
    }
    
    # 创建构建产物目录
    if (-not (Test-Path $BuildOutputDir)) {
        New-Item -ItemType Directory -Path $BuildOutputDir -Force | Out-Null
        Write-Info "创建构建产物目录: $BuildOutputDir"
    }
    
    # ============================================
    # 步骤 3: 运行测试
    # ============================================
    if (-not $SkipTests) {
        Write-Step "步骤 3/8: 运行测试"
        
        Write-Info "运行 UTF-8 编码测试..."
        Push-Location $ProjectRoot
        try {
            $Utf8TestFile = "backend\tests\test_utf8_encoding.py"
            if (-not (Test-Path $Utf8TestFile)) {
                Write-Warning-Custom "UTF-8 编码测试脚本不存在，跳过"
            } else {
                & $VenvPython $Utf8TestFile
                if ($LASTEXITCODE -eq 0) {
                    Write-Success "UTF-8 编码测试通过"
                } else {
                    Write-Warning-Custom "UTF-8 编码测试失败，但继续构建"
                }
            }
        } catch {
            Write-Warning-Custom "测试执行出错: $_"
        } finally {
            Pop-Location
        }
    } else {
        Write-Step "步骤 3/8: 运行测试 (已跳过)"
    }
    
    # ============================================
    # 步骤 4: 构建前端
    # ============================================
    if (-not $SkipFrontend) {
        Write-Step "步骤 4/8: 构建前端"
        
        Push-Location $FrontendDir
        try {
            if (-not (Test-Path "node_modules")) {
                Write-Info "安装前端依赖..."
                npm install
                if ($LASTEXITCODE -ne 0) {
                    throw "npm install 失败"
                }
                Write-Success "前端依赖安装完成"
            }
            
            Write-Info "构建前端项目..."
            $npmResult = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "cd /d `"$FrontendDir`" && npm run build" -NoNewWindow -Wait -PassThru
            if ($npmResult.ExitCode -ne 0) {
                throw "前端构建失败"
            }
            Write-Success "前端构建完成"
            
            # 检查构建产物
            if (Test-Path $TempDistDir) {
                $Files = Get-ChildItem -Path $TempDistDir -Recurse -File
                Write-Success "前端构建产物: $($Files.Count) 个文件"
            } else {
                throw "前端构建产物不存在"
            }
        } finally {
            Pop-Location
        }
    } else {
        Write-Step "步骤 4/8: 构建前端 (已跳过)"
        
        # 检查前端构建产物是否存在
        if (-not (Test-Path $TempDistDir)) {
            Write-Error-Custom "前端构建产物不存在，无法继续"
            Write-Info "请先运行前端构建或移除 -SkipFrontend 参数"
            exit 1
        }
    }
    
    # ============================================
    # 步骤 5: 打包后端
    # ============================================
    Write-Step "步骤 5/8: 打包后端"
    
    Push-Location $ProjectRoot

    # 临时修改 deploy.json 的 active_env 为 prod（打包后必须运行在生产环境）
    $DeployConfigPath = Join-Path $ProjectRoot "resource\config\deploy.json"
    $OriginalDeployConfig = $null

    try {
        Write-Info "激活虚拟环境并运行 PyInstaller..."

        # 使用虚拟环境中的 pyinstaller
        $PyInstaller = Join-Path $VenvDir "Scripts\pyinstaller.exe"

        if (-not (Test-Path $PyInstaller)) {
            throw "PyInstaller 可执行文件不存在: $PyInstaller"
        }

        # 根据 ShowConsole 参数选择 spec 文件
        if ($ShowConsole) {
            $SpecFile = "build_exe_debug.spec"
            Write-Info "使用调试版本配置 (显示控制台窗口)"
        } else {
            $SpecFile = "build_exe.spec"
            Write-Info "使用生产版本配置 (隐藏控制台窗口)"
        }

        # 设置环境变量，让 PyInstaller 输出到指定目录
        $env:DISTPATH = $DistDir
        $env:BUILDPATH = $BuildDir

        # 备份并修改 deploy.json 的 active_env 为 prod
        $OriginalDeployConfig = Get-Content $DeployConfigPath -Raw -Encoding UTF8
        try {
            $DeployConfig = $OriginalDeployConfig | ConvertFrom-Json
            $DeployConfig.active_env = "prod"
            $DeployConfig | ConvertTo-Json -Depth 10 | Set-Content $DeployConfigPath -Encoding UTF8 -NoNewline
            Write-Info "已临时设置 deploy.json 的 active_env 为 prod"
        } catch {
            Write-Warning "修改 deploy.json 失败: $_，使用原始配置继续"
            $OriginalDeployConfig = $null  # 标记为未修改，跳过恢复
        }

        # 运行 PyInstaller
        # PowerShell 会把原生命令写到 stderr 的日志当作错误记录，在 $ErrorActionPreference=Stop 下会误判为构建失败，
        # 因此这里显式合并输出并转发为普通日志，最终只以退出码判断结果
        $PrevErrorAction = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            & $PyInstaller $SpecFile --clean --distpath $DistDir --workpath $BuildDir 2>&1 | ForEach-Object { Write-Host $_ }
            $PyInstallerExitCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $PrevErrorAction
        }

        if ($PyInstallerExitCode -ne 0) {
            throw "PyInstaller 打包失败"
        }

        Write-Success "后端打包完成"
        
        # 检查生成的 exe（onedir 模式下在 Comfyui-Box 子目录中）
        $ExePath = Join-Path $DistDir "Comfyui-Box\Comfyui-Box.exe"
        if (Test-Path $ExePath) {
            $ExeSize = (Get-Item $ExePath).Length / 1MB
            Write-Success "生成的 exe 文件: Comfyui-Box.exe ($([math]::Round($ExeSize, 2)) MB)"
            
            # 显示目录结构
            $ComfyuiBoxDir = Join-Path $DistDir "Comfyui-Box"
            $AllFiles = Get-ChildItem -Path $ComfyuiBoxDir -Recurse -File
            $TotalSize = ($AllFiles | Measure-Object -Property Length -Sum).Sum / 1MB
            Write-Info "打包目录包含 $($AllFiles.Count) 个文件，总大小 $([math]::Round($TotalSize, 2)) MB"
        } else {
            throw "exe 文件未生成"
        }
    } finally {
        # 恢复 deploy.json 的原始配置（无论成功失败）
        if ($null -ne $OriginalDeployConfig) {
            try {
                $OriginalDeployConfig | Set-Content $DeployConfigPath -Encoding UTF8 -NoNewline
                Write-Info "已恢复 deploy.json 的原始配置"
            } catch {
                Write-Warning "恢复 deploy.json 失败: $_"
            }
        }
        Pop-Location
    }
    
    # ============================================
    # 步骤 5.5: 打包更新器
    # ============================================
    Write-Step "步骤 5.5/8: 打包更新器"
    
    Push-Location $ProjectRoot
    try {
        $UpdaterSpecFile = "backend\updater\updater.spec"
        $UpdaterDistDir = Join-Path $BuildOutputDir "updater_dist"
        
        if (Test-Path $UpdaterSpecFile) {
            Write-Info "打包 Comfyui-BoxUpdater_v1.0.exe..."
            
            $PrevErrorAction = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            try {
                & $PyInstaller $UpdaterSpecFile --clean --distpath $UpdaterDistDir --workpath (Join-Path $BuildDir "updater") 2>&1 | ForEach-Object { Write-Host $_ }
                $UpdaterExitCode = $LASTEXITCODE
            } finally {
                $ErrorActionPreference = $PrevErrorAction
            }
            
            if ($UpdaterExitCode -eq 0) {
                $UpdaterExe = Join-Path $UpdaterDistDir "Comfyui-BoxUpdater_v1.0.exe"
                if (Test-Path $UpdaterExe) {
                    $TargetDir = Join-Path $DistDir "Comfyui-Box"
                    Copy-Item $UpdaterExe $TargetDir -Force
                    Write-Success "Comfyui-BoxUpdater_v1.0.exe 已复制到发布目录"
                    Remove-Item $UpdaterDistDir -Recurse -Force
                    Write-Info "已清理中间目录: updater_dist"
                } else {
                    Write-Warning-Custom "Comfyui-BoxUpdater_v1.0.exe 未生成，跳过"
                }
            } else {
                Write-Warning-Custom "更新器打包失败，跳过"
            }
        } else {
            Write-Info "未找到更新器配置文件，跳过"
        }
    } catch {
        Write-Warning-Custom "打包更新器时出错: $_"
    } finally {
        Pop-Location
    }
    
    # ============================================
    # 步骤 6: 创建发布包（优化版）
    # ============================================
    Write-Step "步骤 6/8: 创建发布包"
    
    try {
        $Result = New-ReleasePackage `
            -DistDir $DistDir `
            -Version $Version `
            -OutputDir $BuildOutputDir `
            -VerboseOutput:$VerboseOutput
        
        # 保存结果供后续使用
        $ZipPath = $Result.ZipPath
        $ZipName = $Result.ZipName
        $ZipSize = $Result.ZipSize
        
    } catch {
        Write-Error-Custom "发布包创建失败"
        Write-Host ""
        Write-ColorOutput "详细错误信息:" "Yellow"
        Write-Host $_
        Write-Host ""
        Write-Host "Stack Trace:" -ForegroundColor Yellow
        Write-Host $_.ScriptStackTrace -ForegroundColor Gray
        Write-Host ""
        throw
    }
    
    # ============================================
    # 步骤 7: 生成构建报告
    # ============================================
    Write-Step "步骤 7/8: 生成构建报告"
    
    $EndTime = Get-Date
    $Duration = $EndTime - $StartTime
    
    # 收集文件信息
    $OnedirPath = Join-Path $DistDir "Comfyui-Box"
    if (Test-Path $OnedirPath) {
        # onedir 模式
        $ExePath = Join-Path $OnedirPath "Comfyui-Box.exe"
    } else {
        # onefile 模式
        $ExePath = Join-Path $DistDir "Comfyui-Box.exe"
    }
    $ExeSize = (Get-Item $ExePath).Length / 1MB
    # ZipSize 已经从 New-ReleasePackage 返回
    
    # 生成报告
    $ReportPath = Join-Path $BuildOutputDir "build_report.txt"
    $Report = @"
Comfyui-Box 构建报告
==================

构建信息
--------
版本: $Version
构建时间: $($EndTime.ToString('yyyy-MM-dd HH:mm:ss'))
构建耗时: $([math]::Round($Duration.TotalSeconds, 2)) 秒

构建选项
--------
跳过前端构建: $SkipFrontend
跳过清理: $SkipClean
跳过测试: $SkipTests

构建产物
--------
exe 文件: Comfyui-Box.exe ($([math]::Round($ExeSize, 2)) MB)
发布包: $ZipName ($([math]::Round($ZipSize, 2)) MB)

文件路径
--------
构建产物目录: $BuildOutputDir
exe 路径: $ExePath
发布包路径: $ZipPath

系统信息
--------
操作系统: $([System.Environment]::OSVersion.VersionString)
PowerShell 版本: $($PSVersionTable.PSVersion)
Node.js 版本: $(if (-not $SkipFrontend) { node --version } else { "未检查" })
Python 版本: $(& $VenvPython --version)

构建状态
--------
✓ 构建成功

"@
    
    $Report | Out-File -FilePath $ReportPath -Encoding UTF8
    Write-Success "构建报告已保存: build_report.txt"
    
    # 显示摘要
    Write-ColorOutput @"

╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║                    构建成功！                             ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝

"@ "Green"
    
    Write-Info "版本: $Version"
    Write-Info "构建产物目录: $BuildOutputDir"
    Write-Info "exe 文件: Comfyui-Box.exe ($([math]::Round($ExeSize, 2)) MB)"
    Write-Info "发布包: $ZipName ($([math]::Round($ZipSize, 2)) MB)"
    Write-Info "构建耗时: $([math]::Round($Duration.TotalSeconds, 2)) 秒"
    Write-Host ""
    
    Write-ColorOutput "下一步操作:" "Yellow"
    Write-Host "  1. 测试 exe: $ExePath"
    Write-Host "  2. 查看报告: $ReportPath"
    Write-Host "  3. 发布包: $ZipPath"
    Write-Host ""
    
} catch {
    Write-ColorOutput @"

╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║                    构建失败！                             ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝

"@ "Red"
    
    Write-Error-Custom "错误信息: $_"
    Write-Host ""
    Write-ColorOutput "请检查以上错误信息并修复后重试" "Yellow"
    Write-Host ""
    
    exit 1
}
