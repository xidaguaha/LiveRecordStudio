"""
流解析引擎 - 封装streamget库获取直播流（多平台支持）
"""
import asyncio
from typing import Optional
from urllib.parse import urlparse
from loguru import logger

# 域名 -> (平台类, 平台中文名) 的映射
_PLATFORM_MAP = {}


def _build_platform_map():
    """延迟构建平台映射，避免导入时加载所有类"""
    if _PLATFORM_MAP:
        return
    from streamget import (
        DouyinLiveStream, BilibiliLiveStream, HuyaLiveStream,
        DouyuLiveStream, KwaiLiveStream, TwitchLiveStream,
        YoutubeLiveStream, YYLiveStream, RedNoteLiveStream,
        TikTokLiveStream, BigoLiveStream,
    )
    mapping = {
        # 抖音
        "live.douyin.com": (DouyinLiveStream, "抖音"),
        "www.douyin.com": (DouyinLiveStream, "抖音"),
        # TikTok
        "www.tiktok.com": (TikTokLiveStream, "TikTok"),
        "live.tiktok.com": (TikTokLiveStream, "TikTok"),
        # 快手
        "live.kuaishou.com": (KwaiLiveStream, "快手"),
        # 虎牙
        "www.huya.com": (HuyaLiveStream, "虎牙"),
        # 斗鱼
        "www.douyu.com": (DouyuLiveStream, "斗鱼"),
        # B站
        "live.bilibili.com": (BilibiliLiveStream, "哔哩哔哩"),
        # 小红书
        "live.xiaohongshu.com": (RedNoteLiveStream, "小红书"),
        # Twitch
        "www.twitch.tv": (TwitchLiveStream, "Twitch"),
        # YouTube
        "www.youtube.com": (YoutubeLiveStream, "YouTube"),
        # YY
        "www.yy.com": (YYLiveStream, "YY直播"),
        # Bigo
        "www.bigo.tv": (BigoLiveStream, "Bigo"),
    }
    _PLATFORM_MAP.update(mapping)


def get_platform_class(url: str):
    """根据URL返回对应的平台类和中文名，未匹配返回None"""
    _build_platform_map()
    try:
        domain = urlparse(url).hostname or ""
    except Exception:
        return None
    for pattern, entry in _PLATFORM_MAP.items():
        if pattern in domain:
            return entry
    # 尝试在所有 key 中做模糊匹配
    for pattern, entry in _PLATFORM_MAP.items():
        if domain.endswith(pattern) or pattern.endswith(domain):
            return entry
    return None


class StreamParser:
    """直播流解析器，封装streamget库，支持多平台"""

    def __init__(self, proxy: str = "", cookie: str = ""):
        self._proxy = proxy
        self._cookie = cookie
        self._streamer = None
        self._platform_name = ""

    async def fetch_stream_data(self, url: str, quality: str = "OD") -> Optional[dict]:
        """
        获取直播流数据
        返回: {"is_live": bool, "anchor_name": str, "m3u8_url": str, "flv_url": str, "title": str, "platform": str}
        如果获取失败返回None
        """
        # 识别平台
        platform_info = get_platform_class(url)
        if not platform_info:
            logger.warning(f"不支持的平台: {url}")
            return None

        StreamerClass, platform_name = platform_info
        self._platform_name = platform_name
        self._streamer = StreamerClass(
            proxy_addr=self._proxy or None,
            cookies=self._cookie or None,
        )

        try:
            # 第一步：获取页面数据
            data = await self._streamer.fetch_web_stream_data(url)
            if not data:
                logger.warning(f"获取直播间数据失败: {url}")
                return None

            # 第二步：获取流地址
            stream_obj = await self._streamer.fetch_stream_url(data, quality)
            if not stream_obj:
                logger.warning(f"获取流地址失败: {url}")
                return None

            result = {
                "is_live": getattr(stream_obj, 'is_live', False),
                "anchor_name": getattr(stream_obj, 'anchor_name', ''),
                "m3u8_url": getattr(stream_obj, 'm3u8_url', ''),
                "flv_url": getattr(stream_obj, 'flv_url', ''),
                "title": getattr(stream_obj, 'title', ''),
                "platform": getattr(stream_obj, 'platform', '') or platform_name,
            }

            logger.info(f"解析成功: {result['anchor_name']} is_live={result['is_live']}")
            return result

        except Exception as e:
            logger.error(f"流解析异常 {url}: {e}")
            return None

    def fetch_stream_data_sync(self, url: str, quality: str = "OD") -> Optional[dict]:
        """同步版本（用于QThread等非async上下文）"""
        try:
            return asyncio.run(self.fetch_stream_data(url, quality))
        except Exception as e:
            logger.error(f"流解析同步异常: {e}")
            return None