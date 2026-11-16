"""设置页面 - 包含录制/网络/推送/通用设置"""
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QSpinBox, QCheckBox, QPushButton, QGroupBox, QFormLayout,
    QScrollArea, QFileDialog, QButtonGroup, QRadioButton
)
from PySide6.QtCore import Qt, Signal


class SettingsTab(QWidget):
    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(20)

        # ========== 录制设置 ==========
        record_group = QGroupBox("录制设置")
        record_form = QFormLayout(record_group)
        record_form.setSpacing(14)
        record_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        path_layout = QHBoxLayout()
        self._path_input = QLineEdit()
        self._path_input.setReadOnly(True)
        browse_btn = QPushButton("浏览...")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._browse_path)
        path_layout.addWidget(self._path_input, 1)
        path_layout.addWidget(browse_btn)
        record_form.addRow("保存路径:", path_layout)

        self._format_combo = QComboBox()
        self._format_combo.addItems(["ts", "mkv", "flv", "mp4"])
        record_form.addRow("视频格式:", self._format_combo)

        self._quality_combo = QComboBox()
        self._quality_combo.addItems(["原画(OD)", "超清(UHD)", "高清(HD)", "标清(SD)", "流畅(LD)"])
        record_form.addRow("默认画质:", self._quality_combo)

        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(10, 3600)
        self._interval_spin.setValue(120)
        self._interval_spin.setSuffix(" 秒")
        record_form.addRow("检测间隔:", self._interval_spin)

        self._split_check = QCheckBox("启用分段录制")
        self._split_spin = QSpinBox()
        self._split_spin.setRange(300, 7200)
        self._split_spin.setValue(3600)
        self._split_spin.setSuffix(" 秒")
        self._split_spin.setEnabled(False)
        self._split_check.toggled.connect(self._split_spin.setEnabled)
        split_layout = QHBoxLayout()
        split_layout.addWidget(self._split_check)
        split_layout.addWidget(self._split_spin)
        record_form.addRow("分段:", split_layout)

        self._convert_check = QCheckBox("录制完成后自动转码为MP4")
        record_form.addRow("转码:", self._convert_check)

        # 文件命名模板
        self._template_input = QLineEdit()
        self._template_input.setPlaceholderText("{platform}/{owner}/{year}-{month}-{date} {hour}-{min}-{sec} {title}")
        template_hint = QLabel("占位符: {platform} {owner} {title} {year} {month} {date} {hour} {min} {sec}")
        template_hint.setStyleSheet("color: #8E9AAF; font-size: 11px; border: none; background: transparent;")
        template_layout = QVBoxLayout()
        template_layout.setSpacing(4)
        template_layout.addWidget(self._template_input)
        template_layout.addWidget(template_hint)
        record_form.addRow("命名模板:", template_layout)

        layout.addWidget(record_group)

        # ========== 网络设置 ==========
        network_group = QGroupBox("网络设置")
        network_form = QFormLayout(network_group)
        network_form.setSpacing(14)

        self._proxy_check = QCheckBox("使用代理")
        self._proxy_input = QLineEdit()
        self._proxy_input.setPlaceholderText("http://127.0.0.1:7890")
        self._proxy_input.setEnabled(False)
        self._proxy_check.toggled.connect(self._proxy_input.setEnabled)
        proxy_layout = QHBoxLayout()
        proxy_layout.addWidget(self._proxy_check)
        proxy_layout.addWidget(self._proxy_input, 1)
        network_form.addRow("代理:", proxy_layout)

        layout.addWidget(network_group)

        # ========== 消息推送 ==========
        push_group = QGroupBox("消息推送")
        push_form = QFormLayout(push_group)
        push_form.setSpacing(14)
        self._push_check = QCheckBox("启用消息推送")
        push_form.addRow("开关:", self._push_check)
        self._notify_live_check = QCheckBox("开播时推送")
        self._notify_end_check = QCheckBox("关播时推送")
        notify_layout = QHBoxLayout()
        notify_layout.addWidget(self._notify_live_check)
        notify_layout.addWidget(self._notify_end_check)
        push_form.addRow("通知:", notify_layout)
        layout.addWidget(push_group)

        # ========== 通用设置 ==========
        general_group = QGroupBox("通用设置")
        general_form = QFormLayout(general_group)
        general_form.setSpacing(14)

        # 最小化行为
        self._minimize_btn_group = QButtonGroup(self)
        self._minimize_tray_radio = QRadioButton("最小化到系统托盘（推荐）")
        self._minimize_taskbar_radio = QRadioButton("最小化到任务栏")
        self._minimize_ask_radio = QRadioButton("每次询问")
        self._minimize_btn_group.addButton(self._minimize_tray_radio, 0)
        self._minimize_btn_group.addButton(self._minimize_taskbar_radio, 1)
        self._minimize_btn_group.addButton(self._minimize_ask_radio, 2)

        minimize_layout = QVBoxLayout()
        minimize_layout.setSpacing(8)
        minimize_layout.addWidget(self._minimize_tray_radio)
        minimize_layout.addWidget(self._minimize_taskbar_radio)
        minimize_layout.addWidget(self._minimize_ask_radio)
        general_form.addRow("最小化行为:", minimize_layout)

        # 开机自启动（预留，暂不可用）
        self._auto_start_check = QCheckBox("开机自动启动（开发中）")
        self._auto_start_check.setEnabled(False)
        general_form.addRow("启动:", self._auto_start_check)

        # 关闭行为
        self._close_confirm_check = QCheckBox("关闭时确认（始终弹出确认对话框）")
        general_form.addRow("关闭:", self._close_confirm_check)

        layout.addWidget(general_group)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._save_btn = QPushButton("保存设置")
        self._save_btn.setFixedHeight(40)
        self._save_btn.setFixedWidth(120)
        self._save_btn.setObjectName("primaryBtn")
        self._save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(self._save_btn)
        layout.addLayout(btn_layout)

        scroll.setWidget(container)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _browse_path(self):
        path = QFileDialog.getExistingDirectory(self, "选择保存路径")
        if path:
            self._path_input.setText(path)

    def load_settings(self, settings):
        r = settings.record
        self._path_input.setText(r.save_path)
        idx = self._format_combo.findText(r.video_format)
        if idx >= 0: self._format_combo.setCurrentIndex(idx)
        quality_map = {"OD": 0, "UHD": 1, "HD": 2, "SD": 3, "LD": 4}
        idx = quality_map.get(r.quality, 0)
        if 0 <= idx < self._quality_combo.count():
            self._quality_combo.setCurrentIndex(idx)
        self._interval_spin.setValue(r.loop_interval)
        self._split_check.setChecked(r.auto_split)
        self._split_spin.setValue(r.split_duration)
        self._convert_check.setChecked(r.convert_mp4)
        self._proxy_check.setChecked(r.use_proxy)
        self._proxy_input.setText(r.proxy_addr)
        self._template_input.setText(getattr(r, 'filename_template', ''))
        p = settings.push
        self._push_check.setChecked(p.enabled)
        self._notify_live_check.setChecked(p.notify_on_live)
        self._notify_end_check.setChecked(p.notify_on_end)

        # 最小化行为
        minimize_action = getattr(settings, 'minimize_action', 'ask')
        if minimize_action == "tray":
            self._minimize_tray_radio.setChecked(True)
        elif minimize_action == "taskbar":
            self._minimize_taskbar_radio.setChecked(True)
        else:
            self._minimize_ask_radio.setChecked(True)

        # 关闭确认
        self._close_confirm_check.setChecked(getattr(settings, 'close_confirm', True))

    def get_settings(self) -> dict:
        quality_map = {0: "OD", 1: "UHD", 2: "HD", 3: "SD", 4: "LD"}

        # 最小化行为
        if self._minimize_tray_radio.isChecked():
            minimize_action = "tray"
        elif self._minimize_taskbar_radio.isChecked():
            minimize_action = "taskbar"
        else:
            minimize_action = "ask"

        return {
            "save_path": self._path_input.text(),
            "video_format": self._format_combo.currentText(),
            "quality": quality_map.get(self._quality_combo.currentIndex(), "OD"),
            "loop_interval": self._interval_spin.value(),
            "auto_split": self._split_check.isChecked(),
            "split_duration": self._split_spin.value(),
            "convert_mp4": self._convert_check.isChecked(),
            "use_proxy": self._proxy_check.isChecked(),
            "proxy_addr": self._proxy_input.text(),
            "filename_template": self._template_input.text(),
            "push_enabled": self._push_check.isChecked(),
            "notify_on_live": self._notify_live_check.isChecked(),
            "notify_on_end": self._notify_end_check.isChecked(),
            "minimize_action": minimize_action,
            "close_confirm": self._close_confirm_check.isChecked(),
        }

    def _on_save(self):
        self.settings_changed.emit()
