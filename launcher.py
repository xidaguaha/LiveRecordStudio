# -*- encoding: utf-8 -*-
"""
启动脚本 - 自动定位Python并启动主程序
双击此exe即可启动LiveRecordStudio
"""
import os
import sys
import subprocess


def get_app_dir():
    """获取真实的应用目录（兼容PyInstaller打包）"""
    if getattr(sys, 'frozen', False):
        # PyInstaller打包后，sys.executable是exe路径
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))


def find_python():
    """查找可用的Python（需有PySide6/streamget/loguru）"""
    # 1. 常见安装路径
    candidates = [
        r"C:\Python311\python.exe",
        r"C:\Python310\python.exe",
        r"C:\Python39\python.exe",
        r"C:\Python38\python.exe",
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    # 2. PATH中的python
    return "python"


def show_error(title, msg):
    """弹窗显示错误"""
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title, msg)
    except Exception:
        input(f"[{title}] {msg}\n按回车退出...")


def main():
    app_dir = get_app_dir()
    main_py = os.path.join(app_dir, "main.py")

    if not os.path.isfile(main_py):
        show_error("启动失败", f"找不到 main.py 文件\n请确保启动器与 main.py 在同一目录\n当前目录: {app_dir}")
        return 1

    python_exe = find_python()

    if not os.path.isfile(python_exe):
        show_error("启动失败", f"找不到Python环境\n请安装Python 3.10+并安装依赖:\npip install PySide6 streamget loguru")
        return 1

    # 启动主程序
    cmd = [python_exe, main_py]
    try:
        proc = subprocess.Popen(cmd, cwd=app_dir)
        # 等待一小段时间看是否立即崩溃
        try:
            proc.wait(timeout=3)
            # 如果3秒内就退出了，说明有报错
            if proc.returncode != 0:
                show_error("启动失败", f"程序异常退出(代码{proc.returncode})\n请检查Python环境是否安装了所有依赖:\nPySide6, streamget, loguru")
                return 1
        except subprocess.TimeoutExpired:
            pass  # 程序正常运行中，超时是正常的
    except Exception as e:
        show_error("启动失败", f"无法启动程序\nPython: {python_exe}\n错误: {e}")
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
