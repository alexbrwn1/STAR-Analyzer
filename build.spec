# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for STAR Analyzer.

Build with: pyinstaller build.spec

This creates a single-file executable (~20-35 MB) that includes:
- Python runtime
- Tkinter GUI
- openpyxl for Excel export
"""

import sys
from pathlib import Path

block_cipher = None

# Get the project root directory
spec_dir = Path(SPECPATH)
src_dir = spec_dir / 'src'

# Check for icon
icon_path = spec_dir / 'resources' / 'icon.ico'
icon_file = str(icon_path) if icon_path.exists() else None

a = Analysis(
    [str(src_dir / 'main.py')],
    pathex=[str(src_dir)],
    binaries=[],
    datas=[
        # Include core and gui packages
        (str(src_dir / 'core'), 'core'),
        (str(src_dir / 'gui'), 'gui'),
    ],
    hiddenimports=[
        'openpyxl',
        'openpyxl.cell._writer',
        'openpyxl.workbook.external_link.external',
        'core',
        'core.data_models',
        'core.parser',
        'core.file_discovery',
        'core.exporters',
        'gui',
        'gui.app',
        'gui.import_dialog',
        'gui.data_viewer',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'cv2',
        'pytest',
        'setuptools',
        'wheel',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='STAR_Analyzer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Use UPX compression if available
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window (GUI app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)
