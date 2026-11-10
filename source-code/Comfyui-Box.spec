# -*- mode: python ; coding: utf-8 -*-
"""Comfyui-Box PyInstaller spec (onedir 模式)

- 入口: source-code/backend/main.py
- exe 图标: source-code/resource/img/logo/icon.ico
- 数据文件:
    source-code/resource -> resource     (onedir 下落到 _internal/resource，含图标/模型/默认配置模板)
    source-code/dist     -> dist         (onedir 下落到 _internal/dist，main.py 已做 _internal 回退)
- 依赖: pythonnet / webview 用 collect_all 收集 native 依赖
"""
import os
from PyInstaller.utils.hooks import collect_all

# SPECPATH 由 PyInstaller 注入，指向本 spec 所在目录（即 source-code），
# 因此换机器、换盘符、换 clone 位置都能直接打包，与 updater.spec 的取法保持一致。
ROOT = os.path.abspath(SPECPATH)
BACKEND = os.path.join(ROOT, 'backend')

pythonnet_datas, pythonnet_bins, pythonnet_hiddenimports = collect_all('pythonnet')
webview_datas, webview_bins, webview_hiddenimports = collect_all('webview')

a = Analysis(
    [os.path.join(BACKEND, 'main.py')],
    pathex=[BACKEND, ROOT],
    binaries=[*pythonnet_bins, *webview_bins],
    datas=[
        (os.path.join(ROOT, 'resource'), 'resource'),
        (os.path.join(ROOT, 'dist'), 'dist'),
    ],
    hiddenimports=[
        'pythonnet', 'clr',
        *pythonnet_hiddenimports,
        *webview_hiddenimports,
        'backend', 'backend.src',
    ],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Comfyui-Box',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # 先保留控制台便于排查打包问题；验证通过后改为 False 可隐藏黑窗口
    console=True,
    icon=os.path.join(ROOT, 'resource', 'img', 'logo', 'icon.ico'),
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Comfyui-Box',
)
