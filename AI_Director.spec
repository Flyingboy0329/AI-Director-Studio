# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

PROJ_ROOT = Path(os.path.abspath(".")).resolve()
code_dir = str(PROJ_ROOT / "03_Code")

hiddenimports = [
    'faster_whisper',
    'ctranslate2',
    'huggingface_hub',
    'torch',
    'numpy',
    'cv2',
    'pyautogui',
    'pyperclip',
    'psutil',
    'watchdog',
    'pipeline.director_decision',
    'bridge.auto_injector',
    'ai.audio_analyzer',
    'ai.video_extract',
    'ai.vision_analyzer',
    'config_manager',
    'path_utils'
]

datas = []
try:
    datas += collect_data_files('faster_whisper')
    datas += collect_data_files('ctranslate2')
except Exception:
    pass

datas += [
    ('resolve_lua', 'resolve_lua'),
    ('01_Project/app_icon.png', '01_Project'),
]

a = Analysis(
    ['03_Code/app_gui.py'],
    pathex=[code_dir, str(PROJ_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'IPython', 'notebook', 'pytest'],
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
    name='AI_Director_Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # 關閉 UPX 耗時壓縮，大幅縮減封裝時間
    console=False,      # 關閉 CMD 黑色視窗，純淨視窗啟動
    icon='01_Project/app_icon.ico' if (PROJ_ROOT / "01_Project/app_icon.ico").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,          # 提速關鍵
    upx_exclude=[],
    name='AI_Director_Studio',
)
