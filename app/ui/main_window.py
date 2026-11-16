"""主窗口 - 系统标题栏 + 侧边导航 + 内容区"""
import os
import sys
import time
import shutil
from datetime import datetime
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QStackedWidget, QStatusBar, QLabel,
    QSystemTrayIcon, QMenu, QApplication, QStyle,
    QMessageBox, QDialog, QCheckBox, QButtonGroup, QGroupBox,
    QRadioButton,
)
from PySide6.QtCore import Qt, QSize, QTimer, Signal
from PySide6.QtGui import QIcon, QAction, QCloseEvent, QPixmap, QColor

from app.core.task_manager import TaskManager
from app.config.settings import SettingsManager
from app.models import Room, RoomStatus, detect_platform
from app.utils.ffmpeg_helper import find_ffmpeg, check_ffmpeg_available
from app.utils.file_manager import open_file_location
from app.utils.file_naming import generate_recording_path, DEFAULT_TEMPLATE
from app.utils.history_manager import HistoryManager, RecordingHistory
from .live_tab import LiveTab
from .recording_tab import RecordingTab
from .settings_tab import SettingsTab
from .log_tab import LogTab
from .about_tab import AboutTab
from .add_room_dialog import AddRoomDialog


class MainWindow(QMainWindow):
    def __init__(self, config_dir: str, parent=None):
        super().__init__(parent)
        self._config_dir = config_dir
        # 兼容 PyInstaller 打包环境：打包后资源在 exe 同级的 _internal 目录下
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            self._project_root = os.path.join(exe_dir, "_internal")
        else:
            self._project_root = os.path.dirname(self._config_dir)
        self._icon_dir = os.path.join(self._project_root, "resources", "icons")

        # 配置和任务管理
        self._settings = SettingsManager(self._config_dir)
        self._ffmpeg_path = find_ffmpeg() or "ffmpeg"
        self._task_mgr = TaskManager(self._ffmpeg_path, self)
        self._history = HistoryManager(self._config_dir)
        self._rooms = []

        self.setWindowTitle("LiveRecord Studio")
        self.resize(1100, 700)
        self.setMinimumSize(800, 550)

        self._setup_ui()
        self._connect_signals()
        self._load_rooms()
        self._restore_window_state()

    def _setup_ui(self):
        # ===== 中央容器 =====
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ===== 左侧导航栏（垂直布局：图标上+文字下） =====
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(80)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # Logo区
        logo_widget = QWidget()
        logo_widget.setObjectName("sidebarLogo")
        logo_layout = QVBoxLayout(logo_widget)
        logo_layout.setContentsMargins(8, 16, 8, 12)
        logo_label = QLabel("LRS")
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #2B8AF5; "
            "border: none; background: transparent;"
        )
        logo_layout.addWidget(logo_label)
        sidebar_layout.addWidget(logo_widget)

        # 导航按钮容器（垂直排列，每个 = 图标上 + 文字下）
        self._nav_btns = []
        self._current_page = 0

        nav_items = [
            ("主页", os.path.join(self._icon_dir, "home.png")),
            ("录制", os.path.join(self._icon_dir, "record.png")),
            ("设置", os.path.join(self._icon_dir, "settings.png")),
            ("日志", os.path.join(self._icon_dir, "log.png")),
            ("关于", os.path.join(self._icon_dir, "info.png")),
        ]
        nav_container = QWidget()
        nav_container.setObjectName("navContainer")
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(8, 8, 8, 8)
        nav_layout.setSpacing(4)

        for idx, (text, icon_path) in enumerate(nav_items):
            btn = _NavButton(text, icon_path, idx == 0, self)
            btn.clicked.connect(lambda checked, i=idx: self._switch_page(i))
            nav_layout.addWidget(btn)
            self._nav_btns.append(btn)

        nav_layout.addStretch()
        sidebar_layout.addWidget(nav_container, 1)

        main_layout.addWidget(sidebar)

        # ===== 右侧内容区 =====
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # 内容栈
        self._stack = QStackedWidget()
        self._live_tab = LiveTab(self._icon_dir)
        self._recording_tab = RecordingTab(self._icon_dir)
        self._settings_tab = SettingsTab()
        self._log_tab = LogTab()
        self._about_tab = AboutTab()
        self._stack.addWidget(self._live_tab)
        self._stack.addWidget(self._recording_tab)
        self._stack.addWidget(self._settings_tab)
        self._stack.addWidget(self._log_tab)
        self._stack.addWidget(self._about_tab)

        right_layout.addWidget(self._stack, 1)
        main_layout.addWidget(right, 1)

        # ===== 状态栏 =====
        self._status_bar = QStatusBar()
        self._status_bar.setObjectName("appStatusBar")
        self.setStatusBar(self._status_bar)
        self._status_label = QLabel("就绪")
        self._monitor_label = QLabel("监测: 0")
        self._record_label = QLabel("录制: 0")
        self._disk_label = QLabel("")
        self._time_label = QLabel()
        self._status_bar.addWidget(self._status_label)
        self._status_bar.addPermanentWidget(self._monitor_label)
        self._status_bar.addPermanentWidget(self._record_label)
        self._status_bar.addPermanentWidget(self._disk_label)
        self._status_bar.addPermanentWidget(self._time_label)

        # 时间更新
        self._time_timer = QTimer(self)
        self._time_timer.timeout.connect(self._update_time)
        self._time_timer.start(1000)
        self._update_time()

        # ===== 系统托盘 =====
        self._setup_tray()

        # ===== 加载QSS =====
        self._load_style()

    def _setup_tray(self):
        tray_icon_path = os.path.join(self._icon_dir, "app_icon.png")
        icon = QIcon(tray_icon_path) if os.path.isfile(tray_icon_path) else self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlayback)
        self._tray = QSystemTrayIcon(icon, self)
        menu = QMenu(self)
        show_act = QAction("显示主窗口", self)
        show_act.triggered.connect(self._show_and_activate)
        menu.addAction(show_act)
        menu.addSeparator()
        start_all_act = QAction("开始全部监控", self)
        start_all_act.triggered.connect(self._start_all_monitor)
        menu.addAction(start_all_act)
        stop_all_act = QAction("停止全部", self)
        stop_all_act.triggered.connect(self._stop_all_and_notify)
        menu.addAction(stop_all_act)
        menu.addSeparator()
        quit_act = QAction("退出程序", self)
        quit_act.triggered.connect(self._force_quit)
        menu.addAction(quit_act)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_and_activate()

    def _show_and_activate(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _load_style(self):
        style_path = os.path.join(self._project_root, "app", "style.qss")
        if os.path.isfile(style_path):
            with open(style_path, 'r', encoding='utf-8') as f:
                self.setStyleSheet(f.read())

    def _connect_signals(self):
        self._live_tab._add_btn.clicked.connect(self._on_add_room)
        self._live_tab._del_btn.clicked.connect(self._live_tab.remove_selected)
        self._live_tab._refresh_btn.clicked.connect(self._refresh_rooms_display)
        self._live_tab._start_all_btn.clicked.connect(self._start_all_monitor)
        self._live_tab._stop_all_btn.clicked.connect(self._stop_all_and_notify)
        self._live_tab.open_folder_requested.connect(self._open_folder)
        self._live_tab.stop_monitor_requested.connect(self._stop_one)
        self._live_tab.remove_rooms_requested.connect(self._on_remove_rooms)
        self._live_tab.remove_single_requested.connect(self._on_remove_single)
        self._live_tab.room_name_updated.connect(self._on_room_name_updated)
        self._recording_tab.open_folder_requested.connect(self._open_folder)
        self._recording_tab.stop_recording_requested.connect(self._stop_one)
        self._recording_tab.history_clear_requested.connect(self._on_clear_history)
        self._settings_tab.settings_changed.connect(self._save_settings)
        self._task_mgr.room_status_changed.connect(self._on_status_changed)
        self._task_mgr.log_message.connect(self._on_log)
        self._task_mgr.recording_progress.connect(self._on_progress)
        self._task_mgr.recording_completed.connect(self._on_recording_completed)
        self._task_mgr.global_status_changed.connect(self._on_global_status)

    # ===== 窗口事件：关闭行为 =====

    def closeEvent(self, event: QCloseEvent):
        """点击窗口X按钮时的行为"""
        recording_count = self._task_mgr.active_recordings

        if recording_count > 0:
            # 有录制正在进行，阻止关闭
            reply = QMessageBox(
                QMessageBox.Icon.Warning,
                "确认退出",
                f"当前有 {recording_count} 个直播正在录制中。\n\n"
                "请先停止所有录制，再关闭程序。\n"
                "你可以在主页点击「停止全部」按钮。",
                QMessageBox.StandardButton.Ok,
                self,
            )
            reply.setWindowTitle("LiveRecord Studio")
            reply.setStyleSheet("")  # 使用全局样式
            reply.exec()
            event.ignore()
            return

        # 没有录制在进行，根据设置决定是否确认
        s = self._settings.settings
        if s.close_confirm:
            reply = QMessageBox(
                QMessageBox.Icon.Question,
                "确认退出",
                "确定要退出 LiveRecord Studio 吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                self,
            )
            reply.setWindowTitle("LiveRecord Studio")
            reply.setStyleSheet("")
            result = reply.exec()

            if result == QMessageBox.StandardButton.Yes:
                self._do_quit()
            else:
                event.ignore()
        else:
            self._do_quit()

    def _do_quit(self):
        """执行退出流程"""
        self._task_mgr.stop_all()
        self._tray.hide()
        self._save_window_state()
        QApplication.quit()

    def _force_quit(self):
        """从托盘菜单强制退出（跳过录制检查）"""
        if self._task_mgr.active_recordings > 0:
            reply = QMessageBox(
                QMessageBox.Icon.Warning,
                "警告",
                f"仍有 {self._task_mgr.active_recordings} 个录制正在进行！\n\n"
                "强制退出将中断所有录制。\n确定要强制退出吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                self,
            )
            reply.setWindowTitle("LiveRecord Studio")
            if reply.exec() != QMessageBox.StandardButton.Yes:
                return
        self._do_quit()

    # ===== 窗口事件：最小化行为 =====

    def changeEvent(self, event):
        """最小化时触发选择对话框"""
        if event.type() == event.Type.WindowStateChange:
            if self.windowState() & Qt.WindowState.WindowMinimized:
                self._handle_minimize()
        super().changeEvent(event)

    def _handle_minimize(self):
        """处理最小化行为"""
        s = self._settings.settings

        # 不再询问：直接执行上次选择
        if s.dont_ask_again:
            self._apply_minimize_action(s.minimize_action)
            return

        # 弹出选择对话框
        dialog = _MinimizeDialog(s.minimize_action, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            chosen_action = dialog.chosen_action
            dont_ask = dialog.dont_ask_again

            s.minimize_action = chosen_action
            s.dont_ask_again = dont_ask
            self._settings.save()

            self._apply_minimize_action(chosen_action)

    def _apply_minimize_action(self, action: str):
        """执行最小化操作"""
        if action == "tray":
            self.hide()
            # 系统托盘气泡提示
            self._tray.showMessage(
                "LiveRecord Studio",
                "程序已最小化到系统托盘，双击图标恢复窗口",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )
        # "taskbar" 是默认行为（showMinimized），不需要额外操作

    # ===== 窗口状态保存/恢复 =====

    def _save_window_state(self):
        s = self._settings.settings
        s.window_geometry = self.saveGeometry().data().decode('latin-1') if self.saveGeometry().data() else ""
        s.window_state = self.saveState().data().decode('latin-1') if self.saveState().data() else ""
        self._settings.save()

    def _restore_window_state(self):
        s = self._settings.settings
        if s.window_geometry:
            self.restoreGeometry(bytes(s.window_geometry, 'latin-1'))
        if s.window_state:
            self.restoreState(bytes(s.window_state, 'latin-1'))

    # ===== 业务逻辑 =====

    def _switch_page(self, index):
        self._stack.setCurrentIndex(index)
        self._current_page = index
        for i, btn in enumerate(self._nav_btns):
            btn.set_active(i == index)

    def _start_all_monitor(self):
        """开始全部监控"""
        # 检查 ffmpeg 可用性
        available, msg = check_ffmpeg_available()
        if not available:
            reply = QMessageBox(
                QMessageBox.Icon.Warning,
                "FFmpeg 未找到",
                f"{msg}\n\n录制功能将无法使用，请先安装 FFmpeg。",
                QMessageBox.StandardButton.Ok,
                self,
            )
            reply.setWindowTitle("LiveRecord Studio")
            reply.exec()
            return

        self._configure_task_manager()
        for room in self._rooms:
            if room.enabled:
                self._task_mgr.start_monitor(
                    room.url, room.quality.name,  # name 是英文 key "OD"
                    self._settings.record.loop_interval
                )
        self._status_label.setText("监控中...")

    def _stop_all_and_notify(self):
        """停止全部监控并通知"""
        self._task_mgr.stop_all()
        self._status_label.setText("已停止所有监控")
        self._on_log("info", "已停止所有监控和录制")

    def _configure_task_manager(self):
        r = self._settings.record
        proxy = r.proxy_addr if r.use_proxy else ""
        self._task_mgr.configure(r, proxy)

    def _on_add_room(self):
        try:
            dialog = AddRoomDialog(self._icon_dir, self)
            result = dialog.exec()
            if result == QDialog.DialogCode.Accepted:
                data = dialog.get_data()
                url = data.get("url", "").strip()
                # 去重检查
                if any(r.url == url for r in self._rooms):
                    self._on_log("warning", f"该直播间已存在: {url[:40]}")
                    return
                room = Room.from_dict(data)
                self._rooms.append(room)
                self._save_and_refresh()
                self._on_log("info", f"已添加直播间: {room.display_name}")
        except Exception as e:
            import traceback
            self._on_log("error", f"添加直播间失败: {e}")
            traceback.print_exc()

    def _on_remove_rooms(self, urls: list):
        """批量删除房间（由 LiveTab 信号触发）"""
        for url in urls:
            self._task_mgr.stop_monitor(url)
        self._rooms = [r for r in self._rooms if r.url not in urls]
        self._save_and_refresh()
        self._on_log("info", f"已删除 {len(urls)} 个直播间")

    def _on_remove_single(self, url: str):
        """右键删除单个房间"""
        room = next((r for r in self._rooms if r.url == url), None)
        name = room.display_name if room else url[:30]
        reply = QMessageBox(
            QMessageBox.Icon.Question,
            "确认删除",
            f"确定要删除直播间「{name}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            self,
        )
        reply.setWindowTitle("LiveRecord Studio")
        if reply.exec() != QMessageBox.StandardButton.Yes:
            return
        self._task_mgr.stop_monitor(url)
        self._rooms = [r for r in self._rooms if r.url != url]
        self._save_and_refresh()
        self._on_log("info", f"已删除直播间: {name}")

    def _on_room_name_updated(self, url: str, new_name: str):
        """监控检测到主播名后，保存到配置"""
        self._save_and_refresh()

    def _load_rooms(self):
        self._rooms = [Room.from_dict(d) for d in self._settings.get_rooms()]
        self._live_tab.set_rooms(self._rooms)
        self._settings_tab.load_settings(self._settings.settings)

    def _save_and_refresh(self):
        """保存房间数据到配置并刷新 UI 显示"""
        self._settings.settings.rooms = [r.to_dict() for r in self._rooms]
        self._settings.save()
        self._live_tab.set_rooms(self._rooms)

    def _refresh_rooms_display(self):
        """刷新按钮：仅刷新 UI 显示，不重新加载配置，不丢失运行时状态"""
        self._live_tab.set_rooms(self._rooms)

    def _save_settings(self):
        data = self._settings_tab.get_settings()
        r = self._settings.record
        r.save_path = data["save_path"]
        r.video_format = data["video_format"]
        r.quality = data["quality"]
        r.loop_interval = data["loop_interval"]
        r.auto_split = data["auto_split"]
        r.split_duration = data["split_duration"]
        r.convert_mp4 = data["convert_mp4"]
        r.use_proxy = data["use_proxy"]
        r.proxy_addr = data["proxy_addr"]
        r.filename_template = data.get("filename_template", "")
        p = self._settings.push
        p.enabled = data["push_enabled"]
        p.notify_on_live = data["notify_on_live"]
        p.notify_on_end = data["notify_on_end"]
        # 通用设置
        self._settings.settings.minimize_action = data.get("minimize_action", "ask")
        self._settings.settings.dont_ask_again = False  # 用户在设置页改了，重置不再询问
        self._settings.settings.close_confirm = data.get("close_confirm", True)
        self._settings.save()
        self._on_log("info", "设置已保存")

    def _on_status_changed(self, url, status, extra):
        # 二次校验：如果上报 recording 但实际无活跃录制，降级为 monitoring
        if status == "recording" and self._task_mgr.active_recordings == 0:
            status = "monitoring"
        self._live_tab.update_room_status(url, status, extra)
        if status == "recording" and extra:
            platform = detect_platform(url).value
            self._recording_tab.add_recording(url, extra, platform, start_time=time.time())
            # 更新房间的录制开始时间
            for room in self._rooms:
                if room.url == url:
                    room.record_start_time = time.time()
                    room.status = RoomStatus.RECORDING
                    break
        elif status in ("offline", "idle", "error"):
            self._recording_tab.remove_recording(url)
            # 下播时停止 ffmpeg 录制进程
            self._task_mgr.stop_recording(url)
            # 清理房间的录制状态
            for room in self._rooms:
                if room.url == url:
                    room.record_file = ""
                    room.record_start_time = 0
                    room.file_size = 0
                    break

    def _on_log(self, level, message):
        self._log_tab.append_log(level, message)

    def _on_progress(self, url, filename, size):
        for room in self._rooms:
            if room.url == url:
                room.file_size = size
                break
        self._recording_tab.update_recording(url, size)

    def _on_recording_completed(self, url, file_path, file_size, duration):
        """录制完成时记录历史"""
        room = next((r for r in self._rooms if r.url == url), None)
        record = RecordingHistory(
            url=url,
            anchor_name=room.display_name if room else "",
            title=room.anchor_name if room else "",
            platform=room.platform.value if room else "",
            quality=room.quality.value if room else "",
            file_path=file_path,
            file_size=file_size,
            duration=duration,
            end_time=time.time(),
            status="completed" if file_size > 0 else "error",
        )
        self._history.add_record(record)
        self._recording_tab.refresh_history(self._history.get_records())
        self._on_log("info", f"录制历史已记录: {os.path.basename(file_path)} ({record.file_size_str})")

    def _on_clear_history(self):
        """清空录制历史"""
        self._history.clear()
        self._recording_tab.refresh_history([])
        self._on_log("info", "录制历史已清空")

    def _on_global_status(self, status):
        self._monitor_label.setText(f"监测: {status.get('monitoring', 0)}")
        self._record_label.setText(f"录制: {status.get('recording', 0)}")
        # 更新磁盘空间
        try:
            save_path = self._settings.record.save_path
            if os.path.isdir(save_path):
                total, used, free = shutil.disk_usage(save_path)
                free_gb = free / (1024 ** 3)
                self._disk_label.setText(f"  磁盘剩余: {free_gb:.1f} GB")
                if free_gb < 5:
                    self._disk_label.setStyleSheet("color: #E74C3C; font-size: 12px; border: none;")
                else:
                    self._disk_label.setStyleSheet("color: #8E9AAF; font-size: 12px; border: none;")
            else:
                self._disk_label.setText("")
        except Exception:
            self._disk_label.setText("")

    def _open_folder(self, url):
        for room in self._rooms:
            if room.url == url:
                if room.record_file and os.path.isfile(room.record_file):
                    open_file_location(room.record_file)
                else:
                    folder = os.path.join(
                        self._settings.record.save_path,
                        room.platform.value,
                        room.display_name or "unknown"
                    )
                    if os.path.isdir(folder):
                        open_file_location(folder)
                    else:
                        # 尝试打开保存根目录
                        root = self._settings.record.save_path
                        if os.path.isdir(root):
                            open_file_location(root)
                        else:
                            self._on_log("warning", f"文件夹不存在: {folder}")
                break

    def _stop_one(self, url):
        self._task_mgr.stop_monitor(url)

    def _update_time(self):
        self._time_label.setText(datetime.now().strftime("%H:%M:%S"))


class _NavButton(QWidget):
    """自定义导航按钮 - 图标上 + 文字下"""
    clicked = Signal(bool)

    # 颜色常量（仅保留文本和边框用，图标不替换颜色）
    COLOR_NORMAL = "#8E9AAF"
    COLOR_HOVER = "#5A6F85"
    COLOR_ACTIVE_ICON = "#FFFFFF"
    COLOR_ACTIVE_BG = "#2B8AF5"
    COLOR_HOVER_BG = "#F0F4FA"

    def __init__(self, text, icon_path, active=False, parent=None):
        super().__init__(parent)
        self._text = text
        self._icon_path = icon_path
        self._active = active
        self.setFixedSize(64, 64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(text)
        self._setup_ui()
        self._update_style()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 6)
        layout.setSpacing(4)

        # 图标
        self._icon_label = QLabel()
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setFixedSize(40, 28)
        layout.addWidget(self._icon_label)

        # 文字
        self._text_label = QLabel(self._text)
        self._text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._text_label.setMinimumHeight(16)
        layout.addWidget(self._text_label)

    def set_active(self, active: bool):
        self._active = active
        self._update_style()

    def _update_style(self):
        if self._active:
            # 选中态：底部蓝色横线，文字蓝色
            self.setStyleSheet(
                "_NavButton { background: transparent; border: none; border-bottom: 3px solid #2B8AF5; }"
            )
            self._icon_label.setStyleSheet("border: none; background: transparent;")
            self._text_label.setStyleSheet(
                "color: #2B8AF5; font-size: 11px; font-weight: bold; border: none; background: transparent;"
            )
            self._set_icon_color()
        else:
            self.setStyleSheet(
                "_NavButton { background: transparent; border: none; border-bottom: 3px solid transparent; }"
            )
            self._icon_label.setStyleSheet("border: none; background: transparent;")
            self._text_label.setStyleSheet(
                "color: #A5B4CB; font-size: 11px; border: none; background: transparent;"
            )
            self._set_icon_color()

    def _set_icon_color(self):
        """加载 PNG 图标"""
        if self._icon_path and os.path.isfile(self._icon_path):
            pix = QPixmap(self._icon_path)
            if not pix.isNull():
                self._icon_label.setPixmap(pix.scaled(QSize(22, 22), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def enterEvent(self, event):
        if not self._active:
            self.setStyleSheet(
                "_NavButton { background: #F0F4FA; border-radius: 10px; border: none; }"
            )
            self._text_label.setStyleSheet(
                "color: #2B8AF5; font-size: 11px; border: none; background: transparent;"
            )
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._update_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(True)
        super().mousePressEvent(event)


class _MinimizeDialog(QDialog):
    """最小化方式选择对话框"""

    def __init__(self, current_action: str = "ask", parent=None):
        super().__init__(parent)
        self.setWindowTitle("LiveRecord Studio")
        self.setFixedSize(380, 280)
        self._chosen_action = current_action
        self._dont_ask = False
        self._setup_ui()

    @property
    def chosen_action(self) -> str:
        return self._chosen_action

    @property
    def dont_ask_again(self) -> bool:
        return self._dont_ask

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel("选择最小化方式")
        title.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #2C3E50; "
            "border: none; background: transparent;"
        )
        layout.addWidget(title)

        desc = QLabel("最小化窗口时，希望以哪种方式处理？")
        desc.setStyleSheet(
            "font-size: 13px; color: #8E9AAF; "
            "border: none; background: transparent;"
        )
        layout.addWidget(desc)

        # 选项
        self._btn_group = QButtonGroup(self)
        self._tray_radio = QRadioButton("最小化到系统托盘（推荐）")
        self._taskbar_radio = QRadioButton("最小化到任务栏")
        self._tray_radio.setStyleSheet("color: #2C3E50; font-size: 13px; border: none; background: transparent; spacing: 8px;")
        self._taskbar_radio.setStyleSheet("color: #2C3E50; font-size: 13px; border: none; background: transparent; spacing: 8px;")

        self._btn_group.addButton(self._tray_radio, 0)
        self._btn_group.addButton(self._taskbar_radio, 1)

        if self._chosen_action == "tray":
            self._tray_radio.setChecked(True)
        else:
            self._taskbar_radio.setChecked(True)

        layout.addWidget(self._tray_radio)
        layout.addWidget(self._taskbar_radio)

        layout.addSpacing(8)

        # 不再询问
        self._dont_ask_cb = QCheckBox("不再提示，记住我的选择")
        self._dont_ask_cb.setStyleSheet("color: #8E9AAF; font-size: 13px; border: none; background: transparent; spacing: 8px;")
        layout.addWidget(self._dont_ask_cb)

        layout.addStretch()

        # 确定按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._ok_btn = QPushButton("确定")
        self._ok_btn.setFixedSize(100, 36)
        self._ok_btn.setObjectName("primaryBtn")
        self._ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(self._ok_btn)
        layout.addLayout(btn_layout)

        # 选中变化时记录
        self._tray_radio.toggled.connect(self._on_tray_toggled)

    def _on_tray_toggled(self, checked):
        if checked:
            self._chosen_action = "tray"
        else:
            self._chosen_action = "taskbar"

    def _on_ok(self):
        self._dont_ask = self._dont_ask_cb.isChecked()
        self.accept()
