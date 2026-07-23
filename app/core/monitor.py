"""
直播状态监控线程 - 定时检测直播间开播状态
"""
import time
from PySide6.QtCore import QThread, Signal
from loguru import logger


class MonitorWorker(QThread):
    """单个直播间的监控工作线程"""

    # 信号
    status_changed = Signal(str, str, str)  # (url, status, extra_info)
    stream_found = Signal(str, dict)         # (url, stream_data)
    error_occurred = Signal(str, str)        # (url, error_msg)
    log_message = Signal(str, str)           # (level, message)

    def __init__(self, url: str, quality: str = "OD", interval: int = 120, parent=None):
        super().__init__(parent)
        self._url = url
        self._quality = quality
        self._interval = max(interval, 10)  # 最少10秒
        self._running = True
        self._paused = False
        self._parser = None  # 延迟初始化
        self._proxy = ""
        self._cookie = ""
        self._was_live = False  # 上一次检测的直播状态，用于检测状态翻转

    def set_proxy(self, proxy: str):
        self._proxy = proxy

    def set_cookie(self, cookie: str):
        self._cookie = cookie

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def stop(self):
        self._running = False
        self.wait(5000)  # 等待线程结束

    def run(self):
        """主循环：定时检测直播状态"""
        from app.core.stream_parser import StreamParser
        self._parser = StreamParser(proxy=self._proxy, cookie=self._cookie)

        # 保存原始 URL 副本，防止 streamget 库内部修改 self._url
        original_url = self._url

        self.log_message.emit("info", f"[{original_url[:30]}] 开始监控...")
        self.status_changed.emit(original_url, "monitoring", "")

        while self._running:
            if self._paused:
                time.sleep(1)
                continue

            try:
                # 调用流解析
                data = self._parser.fetch_stream_data_sync(original_url, self._quality)

                if data is None:
                    self.status_changed.emit(original_url, "error", "")
                    self.log_message.emit("warning", f"[{original_url[:30]}] 获取直播数据失败(返回None)")
                    # 注意：不修改 _was_live，避免网络波动导致录制中断
                elif data.get("is_live", False):
                    is_new_live = not self._was_live
                    self._was_live = True
                    anchor_name = data.get("anchor_name", "") or ""
                    title = data.get("title") or ""
                    # 先发 live 状态（带主播名），让 UI 更新显示
                    self.status_changed.emit(original_url, "live", anchor_name)
                    # 仅在从未开播→开播的状态翻转时触发录制
                    if is_new_live:
                        self.log_message.emit("info", f"[{original_url[:30]}] 检测到开播: {anchor_name} | {title[:30]}")
                        self.stream_found.emit(original_url, data)
                    else:
                        self.log_message.emit("debug", f"[{original_url[:30]}] 直播中（持续监控）: {anchor_name}")
                else:
                    was_live = self._was_live
                    self._was_live = False
                    self.status_changed.emit(original_url, "offline", data.get("anchor_name", "") if data else "")
                    if was_live:
                        self.log_message.emit("info", f"[{original_url[:30]}] 直播已结束: {data.get('anchor_name', '') if data else ''}")
                    else:
                        self.log_message.emit("debug", f"[{original_url[:30]}] 未开播")

            except Exception as e:
                self.error_occurred.emit(original_url, str(e))
                self.log_message.emit("error", f"[{original_url[:30]}] 监控异常: {type(e).__name__}: {e}")

            # 等待下一次检测
            for _ in range(int(self._interval)):
                if not self._running:
                    break
                if self._paused:
                    time.sleep(1)
                else:
                    time.sleep(1)

        self.log_message.emit("info", f"[{original_url[:30]}] 监控已停止")
        self.status_changed.emit(original_url, "idle", "")