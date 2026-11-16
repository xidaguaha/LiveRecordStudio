"""
全局任务调度管理器 - 协调Monitor和Recorder
"""
import os
import time
from PySide6.QtCore import QObject, Signal, QTimer
from loguru import logger
from app.core.monitor import MonitorWorker
from app.core.recorder import Recorder


class TaskManager(QObject):
    """全局录制任务管理"""

    # 信号
    room_status_changed = Signal(str, str, str)   # (url, status, extra)
    log_message = Signal(str, str)                # (level, msg)
    recording_progress = Signal(str, str, int)     # (url, filename, size)
    recording_completed = Signal(str, str, int, int)  # (url, file_path, file_size, duration)
    disk_warning = Signal(float)                   # remaining_gb
    global_status_changed = Signal(dict)           # {monitoring, recording, disk, proxy}

    def __init__(self, ffmpeg_path: str, parent=None):
        super().__init__(parent)
        self._ffmpeg_path = ffmpeg_path
        self._monitors = {}   # url -> MonitorWorker
        self._recorders = {}  # url -> Recorder
        self._room_data = {}  # url -> stream_data
        self._proxy = ""
        self._record_settings = None
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._update_global_status)
        self._status_timer.setInterval(3000)

    def configure(self, record_settings, proxy=""):
        """配置录制参数"""
        self._record_settings = record_settings
        self._proxy = proxy

    def start_monitor(self, url: str, quality: str = "OD", interval: int = 120):
        """启动单个房间的监控"""
        if url in self._monitors:
            return  # 已在监控

        worker = MonitorWorker(url, quality, interval)
        worker.set_proxy(self._proxy)

        # 连接信号
        worker.status_changed.connect(self._on_status_changed)
        worker.stream_found.connect(self._on_stream_found)
        worker.error_occurred.connect(self._on_error)
        worker.log_message.connect(self.log_message.emit)

        self._monitors[url] = worker
        worker.start()
        self.log_message.emit("info", f"已开始监控: {url[:40]}")
        self._status_timer.start()

    def stop_monitor(self, url: str):
        """停止单个房间的监控和录制"""
        monitor = self._monitors.pop(url, None)
        if monitor:
            monitor.stop()

        recorder = self._recorders.pop(url, None)
        if recorder:
            recorder.stop_recording()

        self._room_data.pop(url, None)
        self.log_message.emit("info", f"已停止监控: {url[:40]}")

    def stop_all(self):
        """停止所有"""
        for url in list(self._monitors.keys()):
            self.stop_monitor(url)
        self._status_timer.stop()

    def stop_recording(self, url: str):
        """仅停止录制，继续监控"""
        recorder = self._recorders.pop(url, None)
        if recorder:
            recorder.stop_recording()
        self.log_message.emit("info", f"已停止录制: {url[:40]}")

    @property
    def active_monitors(self) -> int:
        return sum(1 for m in self._monitors.values() if m.isRunning())

    @property
    def active_recordings(self) -> int:
        return sum(1 for r in self._recorders.values() if r.is_recording)

    def _on_status_changed(self, url, status, extra):
        self.room_status_changed.emit(url, status, extra)

    def _on_stream_found(self, url, stream_data):
        """发现直播，启动录制"""
        self._room_data[url] = stream_data

        # 如果已在录制，先停掉旧的
        if url in self._recorders and self._recorders[url].is_recording:
            self._recorders[url].stop_recording()

        # 确定输出路径（使用文件命名模板）
        if self._record_settings:
            from app.utils.file_naming import generate_recording_path, DEFAULT_TEMPLATE
            template = getattr(self._record_settings, 'filename_template', '') or DEFAULT_TEMPLATE
            output = generate_recording_path(
                save_root=self._record_settings.save_path,
                template=template,
                platform=stream_data.get('platform', '未知'),
                owner=stream_data.get('anchor_name', 'unknown'),
                title=stream_data.get('title', ''),
                quality=stream_data.get('quality', ''),
                ext=self._record_settings.video_format,
            )
        else:
            output = f"recording_{int(time.time())}.ts"

        # 获取流URL
        stream_url = stream_data.get('m3u8_url') or stream_data.get('flv_url', '')
        if not stream_url:
            self.log_message.emit("error", f"无可用流地址: {url[:40]}")
            return

        # 创建并启动录制器
        recorder = Recorder(self._ffmpeg_path, self)
        recorder.recording_started.connect(lambda url, fp: self.log_message.emit("info", f"开始录制: {os.path.basename(fp)}"))
        recorder.recording_error.connect(lambda url, e: self.log_message.emit("error", f"录制错误: {e}"))
        recorder.file_size_changed.connect(lambda url, size: self.recording_progress.emit(url, "", size))

        # 记录开始时间
        start_time = time.time()

        def _on_recording_finished(url, code):
            self.log_message.emit("info", f"录制结束(code={code}): {url[:40]}")
            # 获取文件大小
            file_size = 0
            if os.path.isfile(output):
                file_size = os.path.getsize(output)
            duration = int(time.time() - start_time)
            self.recording_completed.emit(url, output, file_size, duration)

        recorder.recording_finished.connect(_on_recording_finished)

        recorder.start_recording(
            url=url,
            stream_url=stream_url,
            output_path=output,
            fmt=self._record_settings.video_format if self._record_settings else "ts",
            proxy=self._proxy,
            split_duration=self._record_settings.split_duration if self._record_settings and self._record_settings.auto_split else 0,
        )

        self._recorders[url] = recorder
        self.log_message.emit("info", f"开始录制: {stream_data.get('anchor_name', '')}")

    def _on_error(self, url, error_msg):
        self.log_message.emit("error", f"监控异常 {url[:40]}: {error_msg}")

    def _update_global_status(self):
        """定时更新全局状态"""
        status = {
            "monitoring": self.active_monitors,
            "recording": self.active_recordings,
        }
        self.global_status_changed.emit(status)