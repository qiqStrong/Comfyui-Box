# -*- mode: python ; coding: utf-8 -*-
"""
Updater.exe 打包配置

用于打包独立更新器程序（GUI 版本）
"""

import os
from pathlib import Path

block_cipher = None

project_root = Path(SPECPATH).parent.parent

a = Analysis(
    [str(project_root / 'backend' / 'updater' / 'updater.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        # 更新器界面 logo：与主应用共用 resource 资源树，避免重复存放
        (str(project_root / 'resource' / 'img' / 'logo' / 'app-icon.png'), 'resource/img/logo'),
    ],
    hiddenimports=[
        'webview',
        'webview.platforms',
        'webview.platforms.winforms',
        'clr',
        'System',
        'System.Windows.Forms',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'PIL',
        'cv2',
        'torch',
        'tensorflow',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# .NET 8: 确保 pywebview lib 目录里是 netcoreapp3.0 版本的 WebView2 DLL
import shutil as _shutil
import os as _os
_netcore_dir = str(project_root / 'backend' / 'lib' / 'webview2_netcore')
_webview_lib = str(project_root / '.venv' / 'Lib' / 'site-packages' / 'webview' / 'lib')

if _os.path.isdir(_webview_lib) and _os.path.isdir(_netcore_dir):
    for _dll in ['Microsoft.Web.WebView2.Core.dll', 'Microsoft.Web.WebView2.WinForms.dll']:
        _src = _os.path.join(_netcore_dir, _dll)
        _dst = _os.path.join(_webview_lib, _dll)
        if _os.path.exists(_src):
            _shutil.copy2(_src, _dst)
            print(f"[updater.spec] .NET 8: copied netcoreapp3.0 {_dll}")
    for _f in _os.listdir(_webview_lib):
        if _f.endswith('.bak'):
            _os.remove(_os.path.join(_webview_lib, _f))

a.binaries = [item for item in a.binaries if not item[0].endswith('.bak')]
a.datas = [item for item in a.datas if not item[0].endswith('.bak')]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Comfyui-BoxUpdater_v1.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    # runtime_tmpdir: 指定 onefile 解压的临时目录
    # None 会使用系统默认 %TEMP%\_MEIxxxxx，可能因路径冲突导致
    # "Failed to create parent directory structure" 错误
    # 使用固定子目录名避免冲突
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / 'resource' / 'img' / 'logo' / 'icon.ico'),
)
