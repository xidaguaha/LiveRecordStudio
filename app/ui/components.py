"""通用UI组件"""
import os
from PySide6.QtWidgets import (
    QLabel, QWidget, QHBoxLayout, QPushButton
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon


class StatusIndicator(QWidget):
    """带彩色圆点的状态标签"""
    COLORS = {
        "recording": "#2B8AF5",    # 蓝色 - 录制中
        "live": "#27AE60",         # 绿色 - 直播中（等待录制启动）
        "monitoring": "#F39C12",   # 橙色 - 监测中
        "offline": "#B0B8C4",      # 灰色 - 未开播
        "idle": "#B0B8C4",         # 浅灰 - 空闲
        "error": "#E74C3C",        # 红色 - 错误
        "disabled": "#D0D8E4",     # 浅灰 - 禁用
    }
    TEXT_MAP = {
        "recording": "录制中",
        "live": "直播中",
        "monitoring": "监测中",
        "offline": "未开播",
        "idle": "空闲",
        "error": "错误",
        "disabled": "已禁用",
    }

    def __init__(self, status: str = "idle", parent=None):
        super().__init__(parent)
        self._status = status
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        color = self.COLORS.get(self._status, "#B0B8C4")
        self._dot = QLabel()
        self._dot.setFixedSize(8, 8)
        self._dot.setStyleSheet(f"background: {color}; border-radius: 4px; border: none;")
        self._label = QLabel(self.TEXT_MAP.get(self._status, ""))
        self._label.setStyleSheet(f"color: {color}; font-size: 12px; border: none; background: transparent;")
        layout.addWidget(self._dot)
        layout.addWidget(self._label)
        layout.addStretch()
        self.setFixedSize(80, 22)

    def set_status(self, status: str):
        self._status = status
        color = self.COLORS.get(status, "#B0B8C4")
        self._dot.setStyleSheet(f"background: {color}; border-radius: 4px; border: none;")
        self._label.setText(self.TEXT_MAP.get(status, ""))
        self._label.setStyleSheet(f"color: {color}; font-size: 12px; border: none; background: transparent;")


class IconButton(QPushButton):
    """带SVG图标的按钮"""
    def __init__(self, icon_path: str, tooltip: str = "", size: int = 32, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        self.setObjectName("iconBtn")
        if os.path.isfile(icon_path):
            self.setIcon(QIcon(icon_path))
            self.setIconSize(QSize(size - 8, size - 8))

    def set_icon(self, icon_path: str):
        if os.path.isfile(icon_path):
            self.setIcon(QIcon(icon_path))