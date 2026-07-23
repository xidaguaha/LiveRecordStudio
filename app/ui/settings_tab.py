"""设置页面 - 包含录制/网络/通用设置"""
import os
import json
import time
import hmac
import hashlib
import base64
import urllib.request
import urllib.error
import urllib.parse
import winreg
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QSpinBox, QCheckBox, QPushButton, QGroupBox, QFormLayout,
    QScrollArea, QFileDialog, QButtonGroup, QRadioButton, QMenu
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

        self._convert_check = QCheckBox("录制完成后自动转码为MP4（删除原文件）")
        record_form.addRow("转码:", self._convert_check)

        # 文件命名模板
        template_label = QLabel("命名模板:")
        template_top = QHBoxLayout()
        template_top.setSpacing(6)
        self._template_input = QLineEdit()
        self._template_input.setPlaceholderText("{platform}/{owner}/{year}-{month}-{date} {hour}-{min}-{sec} {title}")
        template_top.addWidget(self._template_input, 1)
        # 占位符按钮
        self._template_btn = QPushButton("插入")
        self._template_btn.setFixedWidth(50)
        self._template_btn.setFixedHeight(32)
        self._template_btn.clicked.connect(self._show_template_menu)
        template_top.addWidget(self._template_btn)
        record_form.addRow(template_label, template_top)

        template_hint = QLabel(
            "占位符: {platform} {owner} {title} {year} {month} {date} {hour} {min} {sec}"
        )
        template_hint.setStyleSheet("color: #8E9AAF; font-size: 11px; border: none; background: transparent;")
        template_layout = QVBoxLayout()
        template_layout.setSpacing(2)
        template_layout.addLayout(template_top)
        template_layout.addWidget(template_hint)
        record_form.addRow("", template_layout)

        layout.addWidget(record_group)

        # ========== 网络设置 ==========
        network_group = QGroupBox("网络设置")
        network_form = QFormLayout(network_group)
        network_form.setSpacing(14)

        self._proxy_check = QCheckBox("使用代理")
        self._proxy_input = QLineEdit()
        self._proxy_input.setPlaceholderText("http://127.0.0.1:7890 或 socks5://127.0.0.1:7890")
        self._proxy_input.setEnabled(False)
        self._proxy_check.toggled.connect(self._proxy_input.setEnabled)
        proxy_layout = QHBoxLayout()
        proxy_layout.addWidget(self._proxy_check)
        proxy_layout.addWidget(self._proxy_input, 1)
        network_form.addRow("代理:", proxy_layout)

        layout.addWidget(network_group)

        # ========== 推送设置 ==========
        push_group = QGroupBox("推送设置（Webhook）")
        push_form = QFormLayout(push_group)
        push_form.setSpacing(14)

        self._push_live_check = QCheckBox("检测到开播时推送")
        self._push_end_check = QCheckBox("直播结束时推送")
        push_events_layout = QVBoxLayout()
        push_events_layout.setSpacing(6)
        push_events_layout.addWidget(self._push_live_check)
        push_events_layout.addWidget(self._push_end_check)
        push_form.addRow("推送事件:", push_events_layout)

        self._webhook_url_input = QLineEdit()
        self._webhook_url_input.setPlaceholderText("https://example.com/webhook 或 留空使用钉钉机器人")
        push_form.addRow("Webhook URL:", self._webhook_url_input)

        self._webhook_secret_input = QLineEdit()
        self._webhook_secret_input.setPlaceholderText("签名密钥（可选，钉钉机器人加签时使用）")
        push_form.addRow("签名密钥:", self._webhook_secret_input)

        self._webhook_body_input = QLineEdit()
        self._webhook_body_input.setPlaceholderText('{"text": "{event} - {anchor}"}')
        self._webhook_body_input.setToolTip(
            'POST 请求体模板，支持变量:\n'
            '{event} = 开播/下播\n'
            '{anchor} = 主播名\n'
            '{platform} = 平台名\n'
            '{url} = 直播间链接\n'
            '{title} = 直播标题\n'
            '{time} = 当前时间'
        )
        push_form.addRow("请求体模板:", self._webhook_body_input)

        self._webhook_test_btn = QPushButton("发送测试推送")
        self._webhook_test_btn.setFixedHeight(32)
        self._webhook_test_btn.clicked.connect(self._test_webhook)
        push_form.addRow("", self._webhook_test_btn)

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

        # 开机自启动
        self._auto_start_check = QCheckBox("开机自动启动")
        self._auto_start_check.setChecked(self._is_auto_start_enabled())
        general_form.addRow("启动:", self._auto_start_check)

        # 关闭行为
        self._close_confirm_check = QCheckBox("关闭时确认")
        general_form.addRow("关闭:", self._close_confirm_check)

        # 启动时自动监控
        self._auto_monitor_check = QCheckBox("启动软件后自动开始监控所有启用的直播间")
        general_form.addRow("自动监控:", self._auto_monitor_check)

        # 开播系统通知
        self._notify_live_check = QCheckBox("检测到开播时发送系统通知")
        general_form.addRow("开播通知:", self._notify_live_check)

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

    @staticmethod
    def _is_auto_start_enabled() -> bool:
        """检查注册表中是否已设置开机自启动"""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_READ
            )
            value, _ = winreg.QueryValueEx(key, "LiveRecordStudio")
            winreg.CloseKey(key)
            return bool(value and os.path.isfile(value))
        except (FileNotFoundError, OSError):
            return False

    @staticmethod
    def set_auto_start(enable: bool):
        """设置或取消开机自启动"""
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        if enable:
            # 使用当前 exe 的完整路径
            import sys
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                exe_path = os.path.abspath(sys.argv[0])
            winreg.SetValueEx(key, "LiveRecordStudio", 0, winreg.REG_SZ, exe_path)
        else:
            try:
                winreg.DeleteValue(key, "LiveRecordStudio")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)

    def _show_template_menu(self):
        """显示占位符插入菜单"""
        menu = QMenu(self)
        placeholders = [
            ("{platform}", "平台名"),
            ("{owner}", "主播名"),
            ("{title}", "直播标题"),
            ("{year}", "年"),
            ("{month}", "月"),
            ("{date}", "日"),
            ("{hour}", "时"),
            ("{min}", "分"),
            ("{sec}", "秒"),
            ("/", "路径分隔符"),
        ]
        for var, desc in placeholders:
            action = menu.addAction(f"{var}  ({desc})")
            action.setData(var)
        action = menu.exec(self._template_btn.mapToGlobal(self._template_btn.rect().bottomLeft()))
        if action:
            text = action.data()
            line_edit = self._template_input
            cursor = line_edit.cursorPosition()
            line_edit.insert(text)

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

        # 最小化行为
        minimize_action = getattr(settings, 'minimize_action', 'ask')
        if minimize_action == "tray":
            self._minimize_tray_radio.setChecked(True)
        elif minimize_action == "taskbar":
            self._minimize_taskbar_radio.setChecked(True)
        else:
            self._minimize_ask_radio.setChecked(True)

        self._close_confirm_check.setChecked(getattr(settings, 'close_confirm', True))
        self._auto_monitor_check.setChecked(getattr(settings, 'auto_start_monitor', False))
        self._notify_live_check.setChecked(getattr(settings, 'notify_on_live', True))
        # Webhook 推送
        push = getattr(settings, 'push', None)
        if push:
            self._push_live_check.setChecked(getattr(push, 'notify_on_live', True))
            self._push_end_check.setChecked(getattr(push, 'notify_on_end', False))
            self._webhook_url_input.setText(getattr(push, 'dingtalk_webhook', '') or '')
        self._webhook_secret_input.setText(getattr(settings, 'webhook_secret', '') or '')
        self._webhook_body_input.setText(getattr(settings, 'webhook_body', '') or '')
        self._auto_start_check.setChecked(self._is_auto_start_enabled())

    def get_settings(self) -> dict:
        quality_map = {0: "OD", 1: "UHD", 2: "HD", 3: "SD", 4: "LD"}

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
            "minimize_action": minimize_action,
            "close_confirm": self._close_confirm_check.isChecked(),
            "auto_start": self._auto_start_check.isChecked(),
            "auto_start_monitor": self._auto_monitor_check.isChecked(),
            "notify_on_live": self._notify_live_check.isChecked(),
            "push_enabled": self._push_live_check.isChecked() or self._push_end_check.isChecked(),
            "push_notify_live": self._push_live_check.isChecked(),
            "push_notify_end": self._push_end_check.isChecked(),
            "webhook_url": self._webhook_url_input.text().strip(),
            "webhook_secret": self._webhook_secret_input.text().strip(),
            "webhook_body": self._webhook_body_input.text().strip(),
        }

    @staticmethod
    def send_webhook(url, secret, body_template, event, anchor, platform, room_url, title=""):
        """发送 Webhook 推送（静态方法，也可被其他模块调用）"""
        if not url:
            return
        try:
            now = time.strftime('%Y-%m-%d %H:%M:%S')
            body_str = (body_template or '{"text": "{event} - {anchor} [{platform}]"}').format(
                event=event, anchor=anchor, platform=platform, url=room_url,
                title=title or "", time=now,
            )
            # 钉钉加签
            headers = {"Content-Type": "application/json; charset=utf-8"}
            if secret:
                ts = str(round(time.time() * 1000))
                sign_str = f"{ts}\n{secret}"
                hmac_code = hmac.new(
                    secret.encode("utf-8"), sign_str.encode("utf-8"), hashlib.sha256
                ).digest()
                sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
                sep = "&" if "?" in url else "?"
                url = f"{url}{sep}timestamp={ts}&sign={sign}"

            data = body_str.encode("utf-8")
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
            return True
        except Exception as e:
            return str(e)

    def _test_webhook(self):
        url = self._webhook_url_input.text().strip()
        if not url:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "提示", "请先填写 Webhook URL")
            return
        secret = self._webhook_secret_input.text().strip()
        body = self._webhook_body_input.text().strip()
        result = self.send_webhook(url, secret, body, "测试", "测试主播", "抖音", "https://example.com", "测试标题")
        if result is True:
            self._webhook_test_btn.setText("推送成功!")
            self._webhook_test_btn.setStyleSheet(
                "background: #27AE60; color: white; border-radius: 6px; font-size: 12px;"
            )
        else:
            self._webhook_test_btn.setText(f"失败: {result}")
            self._webhook_test_btn.setStyleSheet(
                "background: #E74C3C; color: white; border-radius: 6px; font-size: 12px;"
            )
        from PySide6.QtCore import QTimer
        QTimer.singleShot(3000, self._reset_test_btn)

    def _reset_test_btn(self):
        self._webhook_test_btn.setText("发送测试推送")
        self._webhook_test_btn.setStyleSheet("")

    def _on_save(self):
        self.settings_changed.emit()