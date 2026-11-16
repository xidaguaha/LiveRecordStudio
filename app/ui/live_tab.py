"""直播间列表页 - 卡片式布局 + 右键菜单 + 选择机制"""
import os
import webbrowser
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QStackedLayout, QFrame, QMenu, QSizePolicy, QMessageBox,
    QApplication, QScrollArea
)
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QClipboard
from app.models import Room, RoomStatus, Platform, detect_platform
from .components import StatusIndicator, IconButton


class RoomRowWidget(QWidget):
    """单行直播间卡片"""
    open_folder_clicked = Signal(str)
    stop_clicked = Signal(str)
    right_click_requested = Signal(object, str)  # (position, url)

    def __init__(self, room: Room, parent=None):
        super().__init__(parent)
        self._url = room.url
        self._selected = False
        self._setup_ui(room)

    def _setup_ui(self, room: Room):
        self.setObjectName("roomRow")
        self.setFixedHeight(60)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(16)

        self._status = StatusIndicator(room.status.value if room.status else "idle")

        self._platform_label = QLabel()
        self._platform_label.setFixedWidth(60)
        self._platform_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._platform_label.setStyleSheet(
            "background: #F0F4FA; color: #2B8AF5; font-size: 12px; "
            "border: none; border-radius: 4px; padding: 2px 8px;"
        )

        self._name_label = QLabel()
        self._name_label.setStyleSheet(
            "color: #2C3E50; font-size: 14px; font-weight: 500; "
            "border: none; background: transparent;"
        )

        self._url_label = QLabel()
        self._url_label.setStyleSheet(
            "color: #B0B8C4; font-size: 11px; border: none; background: transparent;"
        )

        self._quality_label = QLabel()
        self._quality_label.setFixedWidth(50)
        self._quality_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._quality_label.setStyleSheet(
            "color: #8E9AAF; font-size: 12px; border: none; background: transparent;"
        )

        # 操作按钮区
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        self._folder_btn = QPushButton("  打开文件夹")
        self._folder_btn.setObjectName("blueToolBtn")
        self._folder_btn.setFixedHeight(32)
        self._folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._folder_btn.clicked.connect(lambda: self.open_folder_clicked.emit(self._url))

        self._stop_btn = QPushButton("  停止")
        self._stop_btn.setObjectName("redToolBtn")
        self._stop_btn.setFixedHeight(32)
        self._stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stop_btn.clicked.connect(lambda: self.stop_clicked.emit(self._url))

        btn_layout.addWidget(self._folder_btn)
        btn_layout.addWidget(self._stop_btn)

        layout.addWidget(self._status)
        layout.addWidget(self._platform_label)
        layout.addWidget(self._name_label, 1)
        layout.addWidget(self._url_label, 2)
        layout.addWidget(self._quality_label)
        layout.addLayout(btn_layout)

    def set_selected(self, selected: bool):
        self._selected = selected
        if selected:
            self.setObjectName("roomRowSelected")
            self.setStyleSheet("")  # 刷新让 QSS 重新应用
        else:
            self.setObjectName("roomRow")
            self.setStyleSheet("")

    def mousePressEvent(self, event):
        """单击选中，右键弹出菜单"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.set_selected(not self._selected)
        elif event.button() == Qt.MouseButton.RightButton:
            self.right_click_requested.emit(event.globalPos(), self._url)
        super().mousePressEvent(event)


class LiveTab(QWidget):
    """直播间管理标签页 — 纯 UI 展示层，不持有业务数据"""

    open_folder_requested = Signal(str)
    stop_monitor_requested = Signal(str)
    remove_rooms_requested = Signal(list)  # 要删除的 url 列表
    remove_single_requested = Signal(str)  # 右键删除单个
    room_name_updated = Signal(str, str)   # (url, new_name) 主播名更新

    def __init__(self, icon_dir: str = "", parent=None):
        super().__init__(parent)
        self._icon_dir = icon_dir
        self._rooms = []
        self._rows = {}  # url -> RoomRowWidget
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # 顶部工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._add_btn = QPushButton("  添加直播间")
        self._add_btn.setObjectName("greenToolBtn")
        self._add_btn.setFixedHeight(36)
        self._add_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self._del_btn = QPushButton("  删除选中")
        self._del_btn.setObjectName("redToolBtn")
        self._del_btn.setFixedHeight(36)
        self._del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._del_btn.setEnabled(False)

        self._start_all_btn = QPushButton("  开始监控全部")
        self._start_all_btn.setObjectName("blueToolBtn")
        self._start_all_btn.setFixedHeight(36)
        self._start_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self._stop_all_btn = QPushButton("  停止全部")
        self._stop_all_btn.setObjectName("redToolBtn")
        self._stop_all_btn.setFixedHeight(36)
        self._stop_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self._refresh_btn = QPushButton("  刷新")
        self._refresh_btn.setObjectName("blueToolBtn")
        self._refresh_btn.setFixedHeight(36)
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        toolbar.addWidget(self._add_btn)
        toolbar.addWidget(self._del_btn)
        toolbar.addWidget(self._start_all_btn)
        toolbar.addWidget(self._stop_all_btn)
        toolbar.addStretch()
        toolbar.addWidget(self._refresh_btn)
        layout.addLayout(toolbar)

        # 列表 + 空状态
        self._stack_widget = QWidget()
        self._stacked = QStackedLayout(self._stack_widget)

        # 房间列表容器（可滚动）
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch()

        self._list_scroll = QScrollArea()
        self._list_scroll.setWidgetResizable(True)
        self._list_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._list_scroll.setWidget(self._list_container)
        self._stacked.addWidget(self._list_scroll)

        # 空状态
        empty = QWidget()
        empty_layout = QVBoxLayout(empty)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(12)
        empty_icon = QLabel("暂无直播间")
        empty_icon.setStyleSheet(
            "color: #B0B8C4; font-size: 20px; font-weight: 500; "
            "border: none; background: transparent;"
        )
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint = QLabel("点击上方「添加直播间」按钮开始添加")
        hint.setStyleSheet(
            "color: #D0D8E4; font-size: 13px; border: none; background: transparent;"
        )
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_icon)
        empty_layout.addWidget(hint)
        self._stacked.addWidget(empty)

        self._stacked.setCurrentIndex(1)
        layout.addWidget(self._stack_widget, 1)

    def set_rooms(self, rooms: list):
        """设置房间列表（由 MainWindow 调用，数据源唯一）"""
        self._rooms = list(rooms)
        self._refresh_list()

    def get_selected_urls(self) -> list:
        """获取当前选中的 URL 列表"""
        return [url for url, row in self._rows.items() if row._selected]

    def remove_selected(self):
        """删除选中的直播间（带确认弹窗），通过信号通知 MainWindow 处理"""
        selected_urls = self.get_selected_urls()
        if not selected_urls:
            return

        count = len(selected_urls)
        if count == 1:
            room = next((r for r in self._rooms if r.url in selected_urls), None)
            name = room.display_name if room else selected_urls[0]
            msg = f"确定要删除直播间「{name}」吗？"
        else:
            msg = f"确定要删除选中的 {count} 个直播间吗？"

        reply = QMessageBox(
            QMessageBox.Icon.Question,
            "确认删除",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            self,
        )
        reply.setWindowTitle("LiveRecord Studio")
        if reply.exec() != QMessageBox.StandardButton.Yes:
            return

        # 通知 MainWindow 删除（MainWindow 统一处理数据 + 保存 + 回调 set_rooms）
        self.remove_rooms_requested.emit(selected_urls)

    def _refresh_list(self):
        """刷新列表（清除旧行，重建）"""
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._rows.clear()

        has_selected = False
        for room in self._rooms:
            row = RoomRowWidget(room)
            row._platform_label.setText(room.platform.value)
            row._name_label.setText(room.display_name)
            url_short = room.url if len(room.url) <= 40 else room.url[:37] + "..."
            row._url_label.setText(url_short)
            row._url_label.setToolTip(room.url)
            row._quality_label.setText(room.quality.value)
            row._status.set_status(room.status.value if room.status else "idle")

            # 信号连接
            row.open_folder_clicked.connect(self.open_folder_requested.emit)
            row.stop_clicked.connect(self.stop_monitor_requested.emit)
            row.right_click_requested.connect(self._show_context_menu)

            self._list_layout.insertWidget(self._list_layout.count() - 1, row)
            self._rows[room.url] = row
            if row._selected:
                has_selected = True

        # 更新删除按钮状态
        self._del_btn.setEnabled(has_selected)

        if len(self._rooms) > 0:
            self._stacked.setCurrentIndex(0)
        else:
            self._stacked.setCurrentIndex(1)

    def _show_context_menu(self, pos: QPoint, url: str):
        """显示右键菜单"""
        menu = QMenu(self)

        room = next((r for r in self._rooms if r.url == url), None)
        display_name = room.display_name if room else url[:30]

        copy_url_act = menu.addAction("复制直播间地址")
        open_in_browser_act = menu.addAction("在浏览器中打开")
        menu.addSeparator()
        open_folder_act = menu.addAction("打开录制文件夹")
        stop_act = menu.addAction("停止监控此直播间")
        delete_act = menu.addAction("删除此直播间")
        menu.addSeparator()
        select_all_act = menu.addAction("全选")
        deselect_all_act = menu.addAction("取消全选")

        action = menu.exec(pos)
        if action is None:
            return

        if action == copy_url_act:
            clipboard = QApplication.clipboard()
            clipboard.setText(url)
        elif action == open_in_browser_act:
            webbrowser.open(url)
        elif action == open_folder_act:
            self.open_folder_requested.emit(url)
        elif action == stop_act:
            self.stop_monitor_requested.emit(url)
        elif action == delete_act:
            self.remove_single_requested.emit(url)
        elif action == select_all_act:
            for row in self._rows.values():
                row.set_selected(True)
            self._del_btn.setEnabled(bool(self._rows))
        elif action == deselect_all_act:
            for row in self._rows.values():
                row.set_selected(False)
            self._del_btn.setEnabled(False)

    def update_room_status(self, url: str, status: str, extra: str = ""):
        row = self._rows.get(url)
        if row:
            row._status.set_status(status)
        name_updated = False
        for room in self._rooms:
            if room.url == url:
                try:
                    room.status = RoomStatus(status)
                except ValueError:
                    room.status = RoomStatus.IDLE
                if extra and not room.anchor_name:
                    room.anchor_name = extra
                    name_updated = True
                    # 同步更新行上的显示名
                    if row:
                        row._name_label.setText(room.display_name)
                break
        if name_updated:
            self.room_name_updated.emit(url, extra)