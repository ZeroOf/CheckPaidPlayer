# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['check_keyword.py'],
    pathex=[],
    binaries=[
        (r'C:\Users\Will\.conda\envs\python_toturial\Library\bin\ffi.dll', '.'),
        (r'C:\Users\Will\.conda\envs\python_toturial\Library\bin\libcrypto-3-x64.dll', '.'),
        (r'C:\Users\Will\.conda\envs\python_toturial\Library\bin\libssl-3-x64.dll', '.'),
        (r'C:\Users\Will\.conda\envs\python_toturial\Library\bin\tk86t.dll', '.'),
        (r'C:\Users\Will\.conda\envs\python_toturial\Library\bin\tcl86t.dll', '.'),
        (r'C:\Users\Will\.conda\envs\python_toturial\Library\bin\zstd.dll', '.'),
        (r'C:\Users\Will\.conda\envs\python_toturial\Library\bin\liblzma.dll', '.'),
        (r'C:\Users\Will\.conda\envs\python_toturial\Library\bin\libexpat.dll', '.'),
        (r'C:\Users\Will\.conda\envs\python_toturial\Library\bin\libmpdec-4.dll', '.'),
        (r'C:\Users\Will\.conda\envs\python_toturial\Library\bin\LIBBZ2.dll', '.'),
    ],
    datas=[
        (r'H:\Program Files\Tesseract-OCR\*.exe', 'tesseract'),
        (r'H:\Program Files\Tesseract-OCR\*.dll', 'tesseract'),
        (r'H:\Program Files\Tesseract-OCR\tessdata\*', 'tesseract/tessdata'),
    ],
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
    a.binaries,
    a.datas,
    [],
    name='PlayerMonitor',
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
)
