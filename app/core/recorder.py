"""
录制引擎 - 使用QProcess管理ffmpeg子进程
"""
import os
from PySide6.QtCore import QObject, Signal, QProcess
from loguru import logger


class Recorder(QObject):
    """单个录制任务管理"""

    # 信号
    recording_started = Signal(str, str)     # (url, file_path)
    recording_finished = Signal(str, int)    # (url, exit_code)
    recording_error = Signal(str, str)       # (url, error_msg)
    file_size_changed = Signal(str, int)      # (url, size_bytes)

    def __init__(self, ffmpeg_path: str, parent=None):
        super().__init__(parent)
        self._ffmpeg_path = ffmpeg_path
        self._process: QProcess = None
        self._current_url = ""
        self._current_file = ""

    @property
    def is_recording(self) -> bool:
        return self._process is not None and self._process.state() == QProcess.ProcessState.Running

    def start_recording(
        self,
        url: str,
        stream_url: str,
        output_path: str,
        fmt: str = "ts",
        proxy: str = "",
        split_duration: int = 0,
    ):
        """开始录制"""
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        self._current_url = url
        self._current_file = output_path

        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

        # 连接信号
        self._process.started.connect(self._on_started)
        self._process.finished.connect(self._on_finished)
        self._process.readyReadStandardOutput.connect(self._on_output)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.errorOccurred.connect(self._on_error)

        # 构建命令
        cmd = self._build_command(stream_url, output_path, fmt, proxy, split_duration)
        logger.info(f"启动录制: {cmd}")

        # 启动ffmpeg
        working_dir = os.path.dirname(output_path)
        self._process.setWorkingDirectory(working_dir)
        self._process.start(self._ffmpeg_path, cmd)

    def stop_recording(self):
        """停止录制（先优雅退出，超时后强制终止）"""
        if self._process and self._process.state() == QProcess.ProcessState.Running:
            logger.info(f"停止录制: {self._current_url}")
            # 关闭 stdin，让 ffmpeg 自然结束
            self._process.closeWriteChannel()
            # 给 ffmpeg 10秒优雅退出（等文件 flush）
            if not self._process.waitForFinished(10000):
                logger.warning(f"ffmpeg 未响应，发送 terminate: {self._current_url}")
                self._process.terminate()
                if not self._process.waitForFinished(5000):
                    logger.warning(f"ffmpeg 强制 kill: {self._current_url}")
                    self._process.kill()

    def _build_command(self, stream_url, output_path, fmt, proxy, split_duration):
        """构建ffmpeg命令参数（不含ffmpeg自身路径）"""
        args = ["-y"]
        args.extend(["-rw_timeout", "5000000"])  # 5秒读写超时

        if proxy:
            args.extend(["-http_proxy", proxy])

        args.extend(["-i", stream_url])

        if split_duration > 0:
            args.extend(["-t", str(split_duration)])

        args.extend(["-c", "copy"])
        args.extend(["-f", fmt, output_path])

        return args

    def _on_started(self):
        logger.info(f"录制已启动: {self._current_file}")
        self.recording_started.emit(self._current_url, self._current_file)

    def _on_finished(self, exit_code, exit_status):
        # 崩溃时 _on_error 已清理，此处安全跳过
        if self._process is None and not self._current_url:
            return
        url = self._current_url
        file_path = self._current_file
        logger.info(f"录制结束: {file_path}, exit_code={exit_code}")
        self.recording_finished.emit(url, exit_code)
        self._process = None
        self._current_url = ""
        self._current_file = ""

    def _on_output(self):
        """ffmpeg输出（可用于解析进度）"""
        if self._process:
            output = self._process.readAllStandardOutput().data().decode('utf-8', errors='replace').strip()
            if output:
                logger.debug(f"ffmpeg stdout: {output[:200]}")
                # 更新文件大小
                try:
                    size = os.path.getsize(self._current_file)
                    self.file_size_changed.emit(self._current_url, size)
                except OSError:
                    pass

    def _on_stderr(self):
        """ffmpeg错误输出"""
        if self._process:
            err = self._process.readAllStandardError().data().decode('utf-8', errors='replace').strip()
            if err:
                logger.warning(f"ffmpeg stderr: {err[:500]}")

    def _on_error(self, error):
        error_msg = {
            QProcess.ProcessError.FailedToStart: "启动失败(FFmpeg未找到或无权限)",
            QProcess.ProcessError.Crashed: "进程崩溃",
            QProcess.ProcessError.Timedout: "超时",
            QProcess.ProcessError.WriteError: "写入错误",
            QProcess.ProcessError.ReadError: "读取错误",
            QProcess.ProcessError.UnknownError: "未知错误"
        }.get(error, "未知错误")
        logger.error(f"录制错误: {error_msg}")
        self.recording_error.emit(self._current_url, error_msg)
        # 崩溃后立即清理引用，否则 is_recording 会永远返回 True
        # finished 信号也会触发，但 _on_finished 会安全处理 None
        if error == QProcess.ProcessError.Crashed:
            self._process = None
            self._current_url = ""
            self._current_file = ""