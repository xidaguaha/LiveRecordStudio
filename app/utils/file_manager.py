import os
import re
import time
from datetime import datetime


def sanitize_filename(name: str) -> str:
    """清理文件名，移除非法字符"""
    # 移除Windows非法字符
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', name)
    # 移除emoji和特殊Unicode
    name = re.sub(r'[\U00010000-\U0010ffff]', '', name)
    # 去除首尾空格和点
    name = name.strip(' .')
    return name or "unnamed"


def generate_output_path(
    save_root: str,
    platform: str,
    anchor_name: str,
    title: str = "",
    fmt: str = "ts",
    by_date: bool = True,
) -> str:
    """生成录制文件保存路径"""
    safe_anchor = sanitize_filename(anchor_name) or "unknown"

    if by_date:
        today = datetime.now().strftime("%Y-%m-%d")
        dir_path = os.path.join(save_root, platform, safe_anchor, today)
    else:
        dir_path = os.path.join(save_root, platform, safe_anchor)

    os.makedirs(dir_path, exist_ok=True)

    timestamp = datetime.now().strftime("%H%M%S")
    safe_title = sanitize_filename(title) if title else ""
    if safe_title:
        filename = f"{safe_title}_{timestamp}.{fmt}"
    else:
        filename = f"live_{timestamp}.{fmt}"

    return os.path.join(dir_path, filename)


def get_file_size(path: str) -> int:
    """获取文件大小"""
    try:
        return os.path.getsize(path)
    except (OSError, FileNotFoundError):
        return 0


def open_file_location(path: str):
    """打开文件所在文件夹"""
    if not os.path.isfile(path):
        # 如果文件不存在，打开目录
        folder = os.path.dirname(path) or path
        if not os.path.isdir(folder):
            return
        path = folder
    import subprocess
    if os.name == 'nt':
        subprocess.run(['explorer', '/select,', os.path.normpath(path)], check=False)
    elif os.name == 'posix':
        subprocess.run(['xdg-open', os.path.dirname(path)], check=False)