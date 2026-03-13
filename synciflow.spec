# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

try:
    # When PyInstaller executes a .spec it may not define __file__.
    project_root = Path(__file__).resolve().parent  # type: ignore[name-defined]
except Exception:
    project_root = Path.cwd()
src_root = project_root / "src"

datas = [
    (str(src_root / "synciflow" / "frontend"), "synciflow/frontend"),
]

hiddenimports = (
    collect_submodules("synciflow")
    + collect_submodules("synciflow.cli")
    + [
        "synciflow.cli.main",
        "synciflow.cli.smart",
        "selenium.webdriver.chrome.webdriver",
    ]
)


a = Analysis(
    ['synciflow_entry.py'],
    pathex=[str(src_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    a.binaries,
    a.datas,
    [],
    name='synciflow',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/synciflow.ico",
)
