"""
文件命名模板系统 - 支持占位符的文件路径生成
参考 biliLive-tools 的文件命名规则
"""
import os
import re
from datetime import datetime
from typing import Optional


# Windows 非法字符
_ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _sanitize(name) -> str:
    """清理文件名中的非法字符"""
    if not name:
        return 'unknown'
    name = str(name)
    name = _ILLEGAL_CHARS.sub('_', name)
    name = name.strip('. ')
    if not name:
        name = 'unknown'
    return name


def format_filename(
    template: str,
    platform: str = "",
    owner: str = "",
    title: str = "",
    quality: str = "",
    channel_id: str = "",
    start_time: Optional[datetime] = None,
) -> str:
    """
    根据模板生成文件名/路径
    
    占位符:
        {platform}   - 平台名称
        {owner}      - 主播名称
        {title}      - 直播标题
        {quality}    - 画质
        {channelId}  - 房间号/频道ID
        {year}       - 年份 (4位)
        {month}      - 月份 (01-12)
        {date}       - 日期 (01-31)
        {hour}       - 小时 (00-23)
        {min}        - 分钟 (00-59)
        {sec}        - 秒 (00-59)
        {ms}         - 毫秒 (000-999)
    """
    if start_time is None:
        start_time = datetime.now()

    # 提取房间号（从 URL 或传入的 channel_id）
    room_id = channel_id or ""

    placeholders = {
        "platform": _sanitize(platform),
        "owner": _sanitize(owner),
        "title": _sanitize(title),
        "quality": _sanitize(quality),
        "channelId": _sanitize(room_id),
        "year": start_time.strftime("%Y"),
        "month": start_time.strftime("%m"),
        "date": start_time.strftime("%d"),
        "hour": start_time.strftime("%H"),
        "min": start_time.strftime("%M"),
        "sec": start_time.strftime("%S"),
        "ms": start_time.strftime("%f")[:3],
    }

    result = template
    for key, value in placeholders.items():
        result = result.replace(f"{{{key}}}", value)

    # 清理路径中的多余斜杠和非法字符
    result = os.path.normpath(result)
    return result


def generate_recording_path(
    save_root: str,
    template: str,
    platform: str = "",
    owner: str = "",
    title: str = "",
    quality: str = "",
    channel_id: str = "",
    ext: str = "ts",
    start_time: Optional[datetime] = None,
) -> str:
    """
    生成完整的录制文件路径
    
    Args:
        save_root: 保存根目录
        template: 文件命名模板（相对路径）
        platform, owner, title, quality, channel_id: 占位符数据
        ext: 文件扩展名（不含点）
        start_time: 录制开始时间
    
    Returns:
        完整的绝对文件路径
    """
    formatted = format_filename(
        template,
        platform=platform,
        owner=owner,
        title=title,
        quality=quality,
        channel_id=channel_id,
        start_time=start_time,
    )

    # 确保有扩展名
    if not formatted.lower().endswith(f".{ext.lower()}"):
        formatted = f"{formatted}.{ext}"

    full_path = os.path.join(save_root, formatted)
    
    # 确保目录存在
    dir_path = os.path.dirname(full_path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)

    # 如果文件已存在，添加序号
    if os.path.exists(full_path):
        base, extension = os.path.splitext(full_path)
        counter = 1
        while os.path.exists(full_path):
            full_path = f"{base}_{counter}{extension}"
            counter += 1

    return full_path


# 默认模板
DEFAULT_TEMPLATE = "{platform}/{owner}/{year}-{month}-{date} {hour}-{min}-{sec} {title}"
