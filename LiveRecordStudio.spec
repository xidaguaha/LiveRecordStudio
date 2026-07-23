# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.pyw'],
    pathex=[],
    binaries=[],
    datas=[('ffmpeg', 'ffmpeg'), ('resources', 'resources'), ('app/style.qss', 'app')],
    hiddenimports=['app.ui.main_window', 'app.ui.live_tab', 'app.ui.recording_tab', 'app.ui.settings_tab', 'app.ui.log_tab', 'app.ui.about_tab', 'app.ui.add_room_dialog', 'app.core.monitor', 'app.core.recorder', 'app.core.stream_parser', 'app.core.task_manager', 'app.config.settings', 'app.models.room', 'app.utils.ffmpeg_helper', 'app.utils.file_manager', 'app.utils.file_naming', 'app.utils.history_manager', 'PySide6.QtSvg'],
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
    name='LiveRecordStudio',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LiveRecordStudio',
)
