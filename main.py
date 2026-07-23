# -*- encoding: utf-8 -*-
"""
LiveRecord Studio - 现代化多平台直播录制工具
入口文件
"""
import os
import sys

# Windows: 隐藏控制台窗口（避免双击 .py 文件时弹出黑框）
if sys.platform == 'win32':
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


def get_app_root():
    """获取应用根目录（兼容开发环境和PyInstaller打包环境）"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


_APP_ROOT = get_app_root()
if _APP_ROOT not in sys.path:
    sys.path.insert(0, _APP_ROOT)

# 配置目录：打包环境直接用 AppData，避免权限问题
if getattr(sys, 'frozen', False):
    _CONFIG_DIR = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'LiveRecordStudio', 'config')
else:
    _CONFIG_DIR = os.path.join(_APP_ROOT, "config")
os.makedirs(_CONFIG_DIR, exist_ok=True)


def main():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFont

    app = QApplication(sys.argv)
    app.setApplicationName("LiveRecord Studio")
    app.setApplicationDisplayName("LiveRecord Studio")
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QFont("Microsoft YaHei", 10))

    from app.ui.main_window import MainWindow
    window = MainWindow(_CONFIG_DIR)
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
