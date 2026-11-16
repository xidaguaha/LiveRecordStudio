"""关于页面"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt


class AboutTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)

        logo = QLabel("LiveRecord Studio")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("font-size: 28px; font-weight: bold; color: #2B8AF5; border: none; background: transparent;")
        layout.addWidget(logo)

        ver = QLabel("v1.0.0")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setStyleSheet("font-size: 13px; color: #B0B8C4; border: none; background: transparent;")
        layout.addWidget(ver)

        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #E8ECF1; border: none; max-width: 200px;")
        layout.addWidget(sep)

        desc = QLabel("现代化多平台直播录制工具\n基于 streamget + FFmpeg + PySide6")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("font-size: 13px; color: #5A6F85; border: none; background: transparent;")
        layout.addWidget(desc)

        platforms = QLabel(
            "支持平台: 抖音 | TikTok | 快手 | 虎牙 | 斗鱼 | YY直播\n"
            "哔哩哔哩 | 小红书 | Twitch | YouTube | Bigo | 更多..."
        )
        platforms.setAlignment(Qt.AlignmentFlag.AlignCenter)
        platforms.setStyleSheet("font-size: 12px; color: #8E9AAF; border: none; background: transparent;")
        layout.addWidget(platforms)

        thanks = QLabel("流解析引擎: streamget by ihmily\n录制引擎: FFmpeg")
        thanks.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thanks.setStyleSheet("font-size: 11px; color: #B0B8C4; border: none; background: transparent; margin-top: 16px;")
        layout.addWidget(thanks)