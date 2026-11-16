"""
录制历史管理 - 持久化录制记录
"""
import os
import json
import time
from dataclasses import dataclass, asdict
from typing import List, Optional
from datetime import datetime


@dataclass
class RecordingHistory:
    """单次录制记录"""
    url: str = ""
    anchor_name: str = ""
    title: str = ""
    platform: str = ""
    quality: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    file_path: str = ""
    file_size: int = 0
    duration: int = 0  # 秒
    status: str = ""  # completed / error / interrupted

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "RecordingHistory":
        return cls(**d)

    @property
    def start_time_str(self) -> str:
        if self.start_time:
            return datetime.fromtimestamp(self.start_time).strftime("%Y-%m-%d %H:%M:%S")
        return ""

    @property
    def end_time_str(self) -> str:
        if self.end_time:
            return datetime.fromtimestamp(self.end_time).strftime("%Y-%m-%d %H:%M:%S")
        return ""

    @property
    def duration_str(self) -> str:
        if self.duration:
            h = self.duration // 3600
            m = (self.duration % 3600) // 60
            s = self.duration % 60
            if h > 0:
                return f"{h}:{m:02d}:{s:02d}"
            return f"{m}:{s:02d}"
        return ""

    @property
    def file_size_str(self) -> str:
        size = self.file_size
        if size >= 1024 ** 3:
            return f"{size / (1024 ** 3):.2f} GB"
        elif size >= 1024 ** 2:
            return f"{size / (1024 ** 2):.2f} MB"
        elif size >= 1024:
            return f"{size / 1024:.2f} KB"
        return f"{size} B"


class HistoryManager:
    """录制历史管理器"""

    def __init__(self, config_dir: str):
        self._filepath = os.path.join(config_dir, "recording_history.json")
        self._records: List[RecordingHistory] = []
        self._load()

    def _load(self):
        """从文件加载历史记录"""
        if not os.path.isfile(self._filepath):
            return
        try:
            with open(self._filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                self._records = [RecordingHistory.from_dict(r) for r in data]
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            print(f"历史记录加载失败: {e}")

    def save(self):
        """保存历史记录到文件"""
        try:
            records = [r.to_dict() for r in self._records]
            with open(self._filepath, 'w', encoding='utf-8') as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"历史记录保存失败: {e}")

    def add_record(self, record: RecordingHistory):
        """添加一条记录"""
        self._records.insert(0, record)  # 新记录放前面
        # 限制最多 10000 条
        if len(self._records) > 10000:
            self._records = self._records[:10000]
        self.save()

    def remove_record(self, index: int):
        """删除指定索引的记录"""
        if 0 <= index < len(self._records):
            self._records.pop(index)
            self.save()

    def clear(self):
        """清空所有记录"""
        self._records.clear()
        self.save()

    def get_records(self) -> List[RecordingHistory]:
        """获取所有记录"""
        return list(self._records)

    def get_total_size(self) -> int:
        """获取所有录制文件的总大小"""
        return sum(r.file_size for r in self._records if r.status == "completed")

    def get_total_duration(self) -> int:
        """获取所有录制文件的总时长（秒）"""
        return sum(r.duration for r in self._records if r.status == "completed")

    def get_stats(self) -> dict:
        """获取统计信息"""
        completed = [r for r in self._records if r.status == "completed"]
        return {
            "total_count": len(self._records),
            "completed_count": len(completed),
            "total_size": self.get_total_size(),
            "total_duration": self.get_total_duration(),
        }
