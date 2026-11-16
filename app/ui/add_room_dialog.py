"""添加直播间对话框"""
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QFormLayout, QSizePolicy
)
from PySide6.QtCore import Qt


class AddRoomDialog(QDialog):
    def __init__(self, icon_dir: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加直播间")
        self.setWindowFlags(
            self.windowFlags()
            & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self.setMinimumWidth(480)
        self.setMinimumHeight(260)
        self._icon_dir = icon_dir
        self._setup_ui()
        # 居中显示
        if parent:
            geo = self.geometry()
            parent_geo = parent.geometry()
            x = parent_geo.x() + (parent_geo.width() - geo.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - geo.height()) // 2
            self.move(x, y)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel("添加新的直播间")
        title.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #2C3E50; "
            "border: none; background: transparent;"
        )
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # 直播间地址
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("https://live.douyin.com/xxx")
        self._url_input.setMinimumHeight(32)
        form.addRow("直播间地址:", self._url_input)

        # 显示名称
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("可选，自定义显示名称")
        self._name_input.setMinimumHeight(32)
        form.addRow("显示名称:", self._name_input)

        # 画质选择
        self._quality_combo = QComboBox()
        self._quality_combo.addItems(["原画", "蓝光", "超清", "高清", "标清", "流畅"])
        self._quality_combo.setCurrentIndex(0)
        self._quality_combo.setMinimumHeight(32)
        form.addRow("画质选择:", self._quality_combo)

        layout.addLayout(form)
        layout.addStretch()

        # 按钮区
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setMinimumHeight(36)
        cancel_btn.setMinimumWidth(80)
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QPushButton("添加")
        ok_btn.setObjectName("primaryBtn")
        ok_btn.setMinimumHeight(36)
        ok_btn.setMinimumWidth(80)
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

    def get_data(self) -> dict:
        """返回用户输入的数据"""
        return {
            "url": self._url_input.text().strip(),
            "anchor_name": "",
            "custom_name": self._name_input.text().strip(),
            "quality": self._quality_combo.currentText(),
            "enabled": True,
        }