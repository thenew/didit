# -*- mode: python ; coding: utf-8 -*-
# Build: pyinstaller Didit.spec
# Bundles the pngquant binary from this folder; the app uses it before any
# system-installed pngquant.
import os

if not os.access('pngquant', os.X_OK):
    raise SystemExit("pngquant binary missing (or not executable) next to Didit.spec")

a = Analysis(
    ['didit.py'],
    pathex=[],
    binaries=[('pngquant', '.')],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Didit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=['pngquant'],
    name='Didit',
)
app = BUNDLE(
    coll,
    name='Didit.app',
    icon='icon.icns',
    bundle_identifier='local.didit.app',
)
