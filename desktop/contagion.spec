# -*- mode: python ; coding: utf-8 -*-
# Build from the `ash-project` directory:
#   pip install -r requirements.txt -r desktop/requirements-build.txt
#   pyinstaller desktop/contagion.spec
#
# Prefer building on a Mac that already has Bloomberg + xbbg working if you want
# live data inside the bundle; otherwise the UI runs but "Run Analysis" will fail
# until Bloomberg Python deps are available on that machine.

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).resolve().parent.parent

block_cipher = None

_extra_datas = []
_extra_binaries = []
_hidden = []
for pkg in ("streamlit", "altair", "pandas", "numpy"):
    try:
        ds, bins, hidden = collect_all(pkg)
        _extra_datas += ds
        _extra_binaries += bins
        _hidden += hidden
    except Exception:
        pass

# Optional: Bloomberg (only if installed in the build environment)
for pkg in ("xbbg", "blpapi"):
    try:
        ds, bins, hidden = collect_all(pkg)
        _extra_datas += ds
        _extra_binaries += bins
        _hidden += hidden
    except Exception:
        pass

datas = [
    (str(ROOT / "app.py"), "."),
    (str(ROOT / "contagion"), "contagion"),
    (str(ROOT / "design"), "design"),
    (str(ROOT / ".streamlit"), ".streamlit"),
]
datas += _extra_datas

a = Analysis(
    [str(Path(SPECPATH).parent / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=_extra_binaries,
    datas=datas,
    hiddenimports=_hidden
    + [
        "contagion",
        "contagion.analysis",
        "contagion.data",
        "contagion.models",
        "contagion.readthrough",
        "contagion.report",
        "contagion.pencil_design",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ContagionReadThrough",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ContagionReadThrough",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="ContagionReadThrough.app",
        bundle_identifier="com.contagion.readthrough.desktop",
        info_plist={
            "NSHighResolutionCapable": True,
            "CFBundleName": "Contagion Read-Through",
            "CFBundleDisplayName": "Contagion Read-Through",
            "CFBundleExecutable": "ContagionReadThrough",
        },
    )
