import os
import shutil
import subprocess
import platform
import sys
from typing import Optional


def _get_project_root() -> str:
    """获取项目根目录（兼容开发和打包环境）"""
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        # PyInstaller --onedir 模式下，资源在 _internal 子目录下
        internal_dir = os.path.join(exe_dir, "_internal")
        if os.path.isdir(internal_dir):
            return internal_dir
        return exe_dir
    # 从 app/utils/ffmpeg_helper.py 向上两级到项目根
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def find_ffmpeg() -> Optional[str]:
    """查找ffmpeg路径（优先项目内嵌版本）"""

    # 1. 打包环境：exe 同级的 ffmpeg/bin/ffmpeg.exe
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        embedded = os.path.join(exe_dir, "ffmpeg", "bin", "ffmpeg.exe")
        if os.path.isfile(embedded):
            return embedded

    # 2. 开发环境：项目根目录下的 ffmpeg/bin/ffmpeg.exe
    root = _get_project_root()
    embedded = os.path.join(root, "ffmpeg", "bin", "ffmpeg.exe")
    if os.path.isfile(embedded):
        return embedded

    # 3. PATH中查找
    path = shutil.which("ffmpeg")
    if path:
        return path

    # 4. 常见安装位置
    if platform.system() == "Windows":
        candidates = [
            os.path.expandvars(r"%PROGRAMFILES%\FFmpeg\bin\ffmpeg.exe"),
            os.path.expandvars(r"%PROGRAMFILES(x86)%\FFmpeg\bin\ffmpeg.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\FFmpeg\bin\ffmpeg.exe"),
            os.path.expandvars(r"%USERPROFILE%\scoop\apps\ffmpeg\current\bin\ffmpeg.exe"),
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c

    return None


def build_ffmpeg_command(
    stream_url: str,
    output_path: str,
    fmt: str = "ts",
    proxy: str = "",
    user_agent: str = None,
    rw_timeout: int = 30,
    split_duration: int = 0,
) -> list:
    """构建ffmpeg录制命令"""
    cmd = ["ffmpeg", "-y"]

    # 超时
    cmd.extend(["-rw_timeout", str(rw_timeout * 1000000)])

    # User-Agent
    ua = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    cmd.extend(["-user_agent", ua])

    # 代理
    if proxy:
        cmd.extend(["-http_proxy", proxy])

    # 输入流
    cmd.extend(["-i", stream_url])

    # 录制时长（分段）
    if split_duration > 0:
        cmd.extend(["-t", str(split_duration)])

    # 编码：直接拷贝
    cmd.extend(["-c", "copy"])

    # 输出
    cmd.extend(["-f", fmt, output_path])

    return cmd


def build_convert_command(
    input_path: str,
    output_path: str,
    reencode: bool = False,
) -> list:
    """构建转码MP4命令"""
    cmd = ["ffmpeg", "-y", "-i", input_path]
    if reencode:
        cmd.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "23", "-c:a", "aac"])
    else:
        cmd.extend(["-c", "copy"])
    cmd.append(output_path)
    return cmd


def check_ffmpeg_available() -> tuple:
    """检查ffmpeg是否可用，返回 (bool, message)"""
    path = find_ffmpeg()
    if path:
        try:
            result = subprocess.run(
                [path, "-version"], capture_output=True, text=True, timeout=5
            )
            version = result.stdout.split('\n')[0] if result.stdout else ""
            return True, f"FFmpeg 已安装 ({version})"
        except Exception:
            return True, f"FFmpeg 路径: {path}"
    return False, "未找到 FFmpeg，请先安装 FFmpeg 并添加到系统 PATH"