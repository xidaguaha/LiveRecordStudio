"""
全局任务调度管理器 - 协调Monitor和Recorder
"""
import os
import time
import subprocess
from PySide6.QtCore import QObject, Signal, QTimer, QThread
from loguru import logger
from app.core.monitor import MonitorWorker
from app.core.recorder import Recorder


class _ConvertThread(QThread):
    """后台转码线程（可取消）"""
    log = Signal(str, str)
    finished = Signal(str, str, bool)  # (input_path, output_path, success)

    def __init__(self, ffmpeg_path, input_path, output_path, parent=None):
        super().__init__(parent)
        self._ffmpeg_path = ffmpeg_path
        self._input = input_path
        self._output = output_path
        self._cancelled = False
        self._proc = None

    def cancel(self):
        """取消转码"""
        self._cancelled = True
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()

    def run(self):
        cmd = [
            self._ffmpeg_path, '-y',
            '-i', self._input,
            '-c:v', 'copy', '-c:a', 'copy',
            '-bsf:a', 'aac_adtstoasc',
            '-movflags', '+faststart',
            self._output,
        ]
        self.log.emit("info", f"开始转码: {os.path.basename(self._output)}")
        try:
            # 用 DEVNULL 避免 stderr pipe 死锁（ffmpeg 进度输出量极大）
            self._proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                self._proc.wait(timeout=3600)
            except subprocess.TimeoutExpired:
                self._proc.terminate()
                self.log.emit("warning", "转码超时，已终止")
            if self._cancelled:
                self.log.emit("info", "转码已取消")
                # 清理可能产生的不完整 MP4
                if os.path.isfile(self._output):
                    try:
                        os.remove(self._output)
                    except OSError:
                        pass
                self.finished.emit(self._input, self._output, False)
                return
            if self._proc.returncode == 0 and os.path.isfile(self._output):
                sz = os.path.getsize(self._output)
                self.log.emit("info", f"转码完成: {sz/1024/1024:.1f}MB")
                self.finished.emit(self._input, self._output, True)
            else:
                self.log.emit("error", f"转码失败 (code={self._proc.returncode})")
                self.finished.emit(self._input, self._output, False)
        except Exception as e:
            self.log.emit("error", f"转码异常: {e}")
            self.finished.emit(self._input, self._output, False)


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
        self._convert_threads = []  # 活跃的转码线程
        self._proxy = ""
        self._record_settings = None
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._update_global_status)
        self._status_timer.setInterval(3000)

    def configure(self, record_settings, proxy=""):
        """配置录制参数"""
        self._record_settings = record_settings
        self._proxy = proxy

    def start_monitor(self, url: str, quality: str = "OD", interval: int = 120, cookie: str = ""):
        """启动单个房间的监控"""
        if url in self._monitors:
            return  # 已在监控

        worker = MonitorWorker(url, quality, interval)
        worker.set_proxy(self._proxy)
        if cookie:
            worker.set_cookie(cookie)
            self.log_message.emit("debug", f"使用 Cookie 监控: {url[:40]}")

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

    def is_monitoring(self) -> bool:
        """是否有正在运行的监控"""
        return len(self._monitors) > 0

    def cancel_all_converts(self):
        """取消所有正在进行的转码"""
        count = 0
        for t in list(self._convert_threads):
            if t.isRunning():
                t.cancel()
                count += 1
        return count

    @property
    def active_converts(self) -> int:
        return sum(1 for t in self._convert_threads if t.isRunning())

    def stop_recording(self, url: str):
        """仅停止录制，继续监控"""
        recorder = self._recorders.pop(url, None)
        if recorder:
            recorder.stop_recording()
        self.log_message.emit("info", f"已停止录制: {url[:40]}")

    def stop_recording_by_file(self, file_path: str):
        """停止正在写入指定文件的录制，并取消相关转码"""
        file_path = os.path.normpath(file_path)
        # 停止录制
        for url, recorder in list(self._recorders.items()):
            if os.path.normpath(recorder._current_file) == file_path:
                recorder.stop_recording()
                self._recorders.pop(url, None)
                self.log_message.emit("info", f"已停止录制(文件被删除): {url[:40]}")
                break
        # 取消转码
        for thread in list(self._convert_threads):
            if (os.path.normpath(thread._input) == file_path or
                os.path.normpath(thread._output) == file_path):
                thread.cancel()
                self.log_message.emit("info", f"已取消转码(文件被删除)")

    @property
    def active_monitors(self) -> int:
        return sum(1 for m in self._monitors.values() if m.isRunning())

    @property
    def active_recordings(self) -> int:
        return sum(1 for r in self._recorders.values() if r.is_recording)

    def _on_status_changed(self, url, status, extra):
        # 下播时自动停止录制
        if status == "offline" and url in self._recorders and self._recorders[url].is_recording:
            self.log_message.emit("info", f"检测到下播，停止录制: {extra}")
            self._recorders[url].stop_recording()
        self.room_status_changed.emit(url, status, extra)

    def _on_stream_found(self, url, stream_data):
        """发现直播，启动录制"""
        # 使用原始 URL（防止 streamget 内部重定向修改 URL）
        url = stream_data.get("url") or url
        self._room_data[url] = stream_data

        # 如果已在录制，先停掉旧的
        if url in self._recorders and self._recorders[url].is_recording:
            self._recorders[url].stop_recording()

        # 获取流URL
        stream_url = stream_data.get('m3u8_url') or stream_data.get('flv_url', '')
        if not stream_url:
            self.log_message.emit("error", f"无可用流地址: {url[:40]}")
            return

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
                ext='ts',  # 统一使用 TS 容器
            )
        else:
            output = f"recording_{int(time.time())}.ts"

        anchor_name = stream_data.get('anchor_name', '')

        # 创建并启动录制器
        recorder = Recorder(self._ffmpeg_path, self)
        recorder.recording_started.connect(lambda u, fp: (
            self.log_message.emit("info", f"开始录制: {os.path.basename(fp)}"),
            self.room_status_changed.emit(u, "recording", anchor_name),
        ))
        recorder.recording_error.connect(lambda u, e: self.log_message.emit("error", f"录制错误: {e}"))
        recorder.file_size_changed.connect(lambda u, size: self.recording_progress.emit(u, "", size))

        # 记录开始时间
        start_time = time.time()

        def _on_recording_finished(u, code):
            self.log_message.emit("info", f"录制结束(code={code}): {u[:40]}")
            # 从 _recorders 中清理（避免残留）
            if u in self._recorders:
                del self._recorders[u]
                self.log_message.emit("debug", f"已清理 recorder: {u[:40]}")
            file_size = 0
            if os.path.isfile(output):
                file_size = os.path.getsize(output)
            duration = int(time.time() - start_time)
            self.recording_completed.emit(u, output, file_size, duration)

            # 自动转码 MP4
            if self._record_settings and self._record_settings.convert_mp4 and file_size > 0:
                if output.lower().endswith(('.ts', '.mkv', '.flv')):
                    mp4_path = os.path.splitext(output)[0] + '.mp4'
                    thread = _ConvertThread(self._ffmpeg_path, output, mp4_path, self)
                    thread.log.connect(self.log_message.emit)
                    self._convert_threads.append(thread)

                    def _on_convert_done(src, dst, success):
                        self._convert_threads = [t for t in self._convert_threads if t is not thread]
                        if success:
                            try:
                                os.remove(src)
                                self.log_message.emit("info", f"已删除源文件: {os.path.basename(src)}")
                                # 更新历史记录中的文件路径
                                self.recording_completed.emit(u, dst, os.path.getsize(dst), duration)
                            except OSError as e:
                                self.log_message.emit("warning", f"删除源文件失败: {e}")
                        thread.deleteLater()

                    thread.finished.connect(_on_convert_done)
                    thread.start()

        recorder.recording_finished.connect(_on_recording_finished)

        recorder.start_recording(
            url=url,
            stream_url=stream_url,
            output_path=output,
            fmt="mpegts",  # 统一使用 mpegts（TS）输出，FLV容器无法正确流式写入直播数据
            proxy=self._proxy,
            split_duration=self._record_settings.split_duration if self._record_settings and self._record_settings.auto_split else 0,
        )

        self._recorders[url] = recorder
        self.log_message.emit("info", f"开始录制: {anchor_name}")

    def _on_error(self, url, error_msg):
        self.log_message.emit("error", f"监控异常 {url[:40]}: {error_msg}")

    def _update_global_status(self):
        """定时更新全局状态"""
        status = {
            "monitoring": self.active_monitors,
            "recording": self.active_recordings,
        }
        self.global_status_changed.emit(status)