# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['d:\\project\\python\\yto_wechart\\message_bridge\\.\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('d:\\project\\python\\yto_wechart\\message_bridge\\config.py', '.'), ('d:\\project\\python\\yto_wechart\\message_bridge\\logger.py', '.'), ('d:\\project\\python\\yto_wechart\\message_bridge\\services', 'services'), ('d:\\project\\python\\yto_wechart\\message_bridge\\models', 'models'), ('d:\\project\\python\\yto_wechart\\message_bridge\\handlers', 'handlers'), ('d:\\project\\python\\yto_wechart\\message_bridge\\logs', 'logs')],
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
    name='main',
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
