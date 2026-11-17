# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all

def collect_dir(src, dst):
    res = []
    if os.path.exists(src):
        for root, dirs, files in os.walk(src):
            for f in files:
                full_src = os.path.join(root, f)
                rel_dir = os.path.relpath(root, src)
                full_dst = dst if rel_dir == '.' else os.path.join(dst, rel_dir)
                res.append((full_src, full_dst))
    return res

datas = collect_dir('vlc', 'vlc') + collect_dir('assets', 'assets')
binaries = []
hiddenimports = ['cv2', 'PIL', 'numpy', 'winreg', 'ctypes']

tmp_ret = collect_all('PyQt6')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

tmp_ret = collect_all('cv2')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'pytest'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FluentMediaPlayer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/logo.ico',
    version='file_version_info.txt',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='FluentMediaPlayer',
)
