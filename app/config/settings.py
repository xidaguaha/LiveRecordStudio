import json
import os
import threading
from typing import Any, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class RecordSettings:
    save_path: str = ""  # 默认在程序目录下的 Recordings
    video_format: str = "ts"  # ts/mkv/flv/mp4
    quality: str = "OD"  # OD/UHD/HD/SD/LD
    auto_split: bool = False
    split_duration: int = 3600  # 秒
    convert_mp4: bool = False
    h264_reencode: bool = False
    proxy_addr: str = ""
    use_proxy: bool = False
    proxy_platforms: list = field(default_factory=list)
    loop_interval: int = 120  # 检测间隔秒
    max_threads: int = 5
    filename_template: str = "{platform}/{owner}/{year}-{month}-{date} {hour}-{min}-{sec} {title}"


@dataclass
class PushSettings:
    enabled: bool = False
    channels: list = field(default_factory=list)
    dingtalk_webhook: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    bark_url: str = ""
    ntfy_url: str = ""
    pushplus_token: str = ""
    email_host: str = ""
    email_port: int = 465
    email_user: str = ""
    email_pass: str = ""
    email_receivers: str = ""
    notify_on_live: bool = True
    notify_on_end: bool = True


@dataclass
class AppSettings:
    record: RecordSettings = field(default_factory=RecordSettings)
    push: PushSettings = field(default_factory=PushSettings)
    rooms: list = field(default_factory=list)  # Room.to_dict() 的列表
    window_geometry: str = ""
    window_state: str = ""
    minimize_action: str = "ask"  # ask / tray / taskbar
    dont_ask_again: bool = False
    close_confirm: bool = True  # 关闭时是否始终确认
    auto_start_monitor: bool = False  # 启动时自动开始监控
    notify_on_live: bool = True  # 开播时系统托盘通知
    webhook_secret: str = ""  # Webhook 签名密钥
    webhook_body: str = ""  # Webhook 请求体模板


class SettingsManager:
    """JSON配置管理器"""

    DEFAULT_FILENAME = "settings.json"

    def __init__(self, config_dir: str):
        self._config_dir = config_dir
        self._filepath = os.path.join(config_dir, self.DEFAULT_FILENAME)
        self._lock = threading.Lock()
        os.makedirs(config_dir, exist_ok=True)
        self._settings = AppSettings()
        self.load()

    @property
    def settings(self) -> AppSettings:
        return self._settings

    @property
    def record(self) -> RecordSettings:
        return self._settings.record

    @property
    def push(self) -> PushSettings:
        return self._settings.push

    def load(self):
        """从JSON文件加载配置"""
        if not os.path.isfile(self._filepath):
            # 初始化默认保存路径
            self._settings.record.save_path = os.path.join(self._config_dir, "Recordings")
            os.makedirs(self._settings.record.save_path, exist_ok=True)
            return
        try:
            with self._lock:
                with open(self._filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # 解析record
                if "record" in data:
                    for k, v in data["record"].items():
                        if hasattr(self._settings.record, k):
                            setattr(self._settings.record, k, v)
                # 解析push
                if "push" in data:
                    for k, v in data["push"].items():
                        if hasattr(self._settings.push, k):
                            setattr(self._settings.push, k, v)
                # 解析rooms
                if "rooms" in data:
                    self._settings.rooms = data["rooms"]
                # 解析窗口状态
                if "window_geometry" in data:
                    self._settings.window_geometry = data["window_geometry"]
                if "window_state" in data:
                    self._settings.window_state = data["window_state"]
                # 解析用户偏好
                if "minimize_action" in data:
                    self._settings.minimize_action = data["minimize_action"]
                if "dont_ask_again" in data:
                    self._settings.dont_ask_again = data["dont_ask_again"]
                if "close_confirm" in data:
                    self._settings.close_confirm = data["close_confirm"]
                if "auto_start_monitor" in data:
                    self._settings.auto_start_monitor = data["auto_start_monitor"]
                if "notify_on_live" in data:
                    self._settings.notify_on_live = data["notify_on_live"]
                if "webhook_secret" in data:
                    self._settings.webhook_secret = data["webhook_secret"]
                if "webhook_body" in data:
                    self._settings.webhook_body = data["webhook_body"]
                # 默认保存路径（如果配置的路径不存在则回退到默认）
                if not self._settings.record.save_path or not os.path.isdir(self._settings.record.save_path):
                    self._settings.record.save_path = os.path.join(self._config_dir, "Recordings")

                # 确保保存路径目录存在
                if self._settings.record.save_path:
                    os.makedirs(self._settings.record.save_path, exist_ok=True)
        except (json.JSONDecodeError, KeyError, TypeError, FileNotFoundError) as e:
            print(f"配置加载失败: {e}")

        # 无论配置文件是否存在，都确保保存路径有效
        if not self._settings.record.save_path or not os.path.isdir(self._settings.record.save_path):
            self._settings.record.save_path = os.path.join(self._config_dir, "Recordings")
        if self._settings.record.save_path:
            os.makedirs(self._settings.record.save_path, exist_ok=True)

    def save(self):
        """保存配置到JSON文件"""
        try:
            with self._lock:
                data = {
                    "record": asdict(self._settings.record),
                    "push": asdict(self._settings.push),
                    "rooms": self._settings.rooms,
                    "window_geometry": self._settings.window_geometry,
                    "window_state": self._settings.window_state,
                    "minimize_action": self._settings.minimize_action,
                    "dont_ask_again": self._settings.dont_ask_again,
                    "close_confirm": self._settings.close_confirm,
                    "auto_start_monitor": self._settings.auto_start_monitor,
                    "notify_on_live": self._settings.notify_on_live,
                    "webhook_secret": self._settings.webhook_secret,
                    "webhook_body": self._settings.webhook_body,
                }
                with open(self._filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"配置保存失败: {e}")

    def add_room(self, room_dict: dict):
        self._settings.rooms.append(room_dict)
        self.save()

    def remove_room(self, url: str):
        self._settings.rooms = [r for r in self._settings.rooms if r.get("url") != url]
        self.save()

    def update_room(self, url: str, updates: dict):
        for room in self._settings.rooms:
            if room.get("url") == url:
                room.update(updates)
                break
        self.save()

    def get_rooms(self) -> list:
        return list(self._settings.rooms)