from dataclasses import dataclass, field
from enum import Enum
import time


class RoomStatus(Enum):
    IDLE = "idle"           # 空闲/未监控
    MONITORING = "monitoring"  # 监测中
    RECORDING = "recording"    # 录制中
    OFFLINE = "offline"        # 直播间离线/未开播
    ERROR = "error"            # 错误


class Platform(Enum):
    DOUYIN = "抖音"
    TIKTOK = "TikTok"
    KUAISHOU = "快手"
    HUYA = "虎牙"
    DOUYU = "斗鱼"
    YY = "YY直播"
    BILIBILI = "哔哩哔哩"
    XIAOHONGSHU = "小红书"
    TWITCH = "Twitch"
    YOUTUBE = "YouTube"
    # ... 更多平台
    UNKNOWN = "未知"


# URL域名到平台的映射
DOMAIN_MAP = {
    "live.douyin.com": Platform.DOUYIN,
    "www.douyin.com": Platform.DOUYIN,
    "live.kuaishou.com": Platform.KUAISHOU,
    "www.huya.com": Platform.HUYA,
    "www.douyu.com": Platform.DOUYU,
    "live.bilibili.com": Platform.BILIBILI,
    "live.xiaohongshu.com": Platform.XIAOHONGSHU,
    "www.twitch.tv": Platform.TWITCH,
    "www.youtube.com": Platform.YOUTUBE,
    "www.yy.com": Platform.YY,
    # 添加更多
}


class Quality(Enum):
    OD = "原画"
    UHD = "超清"
    HD = "高清"
    SD = "标清"
    LD = "流畅"


def detect_platform(url: str) -> Platform:
    """从URL自动识别平台"""
    from urllib.parse import urlparse
    try:
        domain = urlparse(url).hostname or ""
        for pattern, platform in DOMAIN_MAP.items():
            if pattern in domain:
                return platform
    except Exception:
        pass
    return Platform.UNKNOWN


@dataclass
class Room:
    url: str
    anchor_name: str = ""
    custom_name: str = ""  # 用户自定义名称（优先显示）
    quality: Quality = Quality.OD
    platform: Platform = Platform.UNKNOWN
    status: RoomStatus = RoomStatus.IDLE
    enabled: bool = True
    record_file: str = ""  # 当前录制文件路径
    record_start_time: float = 0  # 录制开始时间戳
    file_size: int = 0  # 当前文件大小(字节)
    error_msg: str = ""
    last_check: float = 0  # 上次检测时间

    def __post_init__(self):
        if self.platform == Platform.UNKNOWN:
            self.platform = detect_platform(self.url)

    @property
    def display_name(self) -> str:
        """显示名称：优先自定义名，其次主播名，最后平台+序号"""
        return self.custom_name or self.anchor_name or f"{self.platform.value}直播间"

    @property
    def record_duration(self) -> str:
        """录制时长格式化"""
        if self.record_start_time <= 0:
            return "--:--:--"
        elapsed = int(time.time() - self.record_start_time)
        h, m, s = elapsed // 3600, elapsed % 3600 // 60, elapsed % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    @property
    def file_size_str(self) -> str:
        """文件大小格式化"""
        if self.file_size <= 0:
            return "--"
        size = self.file_size  # 使用临时变量，避免修改原始值
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "anchor_name": self.anchor_name,
            "custom_name": self.custom_name,
            "quality": self.quality.value,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Room":
        quality_str = d.get("quality", "原画")
        quality = Quality.OD  # 默认值
        if isinstance(quality_str, Quality):
            quality = quality_str
        elif isinstance(quality_str, str):
            # 先按枚举值（中文）匹配
            for q in Quality:
                if q.value == quality_str:
                    quality = q
                    break
            else:
                # 再按枚举名（英文 key）匹配
                try:
                    quality = Quality[quality_str]
                except KeyError:
                    pass
        return cls(
            url=d["url"],
            anchor_name=d.get("anchor_name", ""),
            custom_name=d.get("custom_name", ""),
            quality=quality,
            enabled=d.get("enabled", True),
        )