# -*- encoding: utf-8 -*-
"""
LiveRecord Studio - 无控制台入口
Windows 下双击此文件启动不会打开命令行窗口
"""
import sys
import os


def get_app_root():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


_APP_ROOT = get_app_root()
if _APP_ROOT not in sys.path:
    sys.path.insert(0, _APP_ROOT)

from main import main

if __name__ == '__main__':
    main()
