"""录制状态面板 - 实时录制 + 历史记录"""
import os
import time
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QMenu
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QCursor


class RecordingCard(QWidget):
    """单个录制卡片"""
    stop_clicked = Signal(str)
    open_folder_clicked = Signal(str)

    def __init__(self, url: str, name: str, platform: str, start_time: float = 0, parent=None):
        super().__init__(parent)
        self._url = url
        self._name = name
        self._platform = platform
        self._start_time = start_time
        self._file_size = 0
        self._setup_ui()

    def _setup_ui(self):
        self.setObjectName("recordingCard")
        self.setFixedHeight(64)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        # 左侧信息区（垂直居中堆叠）
        info = QVBoxLayout()
        info.setSpacing(2)
        info.setContentsMargins(0, 0, 0, 0)

        top = QHBoxLayout()
        top.setSpacing(8)
        name_label = QLabel(self._name)
        name_label.setStyleSheet("color: #2C3E50; font-size: 14px; font-weight: 500; border: none; background: transparent;")
        platform_label = QLabel(self._platform)
        platform_label.setStyleSheet(
            "background: #F0F4FA; color: #2B8AF5; font-size: 11px; "
            "border: none; border-radius: 4px; padding: 1px 6px;"
        )
        self._recording_indicator = QLabel("REC")
        self._recording_indicator.setStyleSheet(
            "color: #E74C3C; font-size: 11px; font-weight: bold; border: none; background: transparent;"
        )
        top.addWidget(name_label)
        top.addWidget(platform_label)
        top.addWidget(self._recording_indicator)
        info.addLayout(top)

        mid = QHBoxLayout()
        mid.setSpacing(16)
        self._start_time_label = QLabel()
        self._start_time_label.setStyleSheet("color: #8E9AAF; font-size: 12px; border: none; background: transparent;")
        self._duration_label = QLabel("录制时长: --:--:--")
        self._duration_label.setStyleSheet("color: #2B8AF5; font-size: 12px; font-weight: 500; border: none; background: transparent;")
        self._size_label = QLabel("文件大小: --")
        self._size_label.setStyleSheet("color: #8E9AAF; font-size: 12px; border: none; background: transparent;")
        mid.addWidget(self._start_time_label)
        mid.addWidget(self._duration_label)
        mid.addWidget(self._size_label)
        info.addLayout(mid)

        layout.addLayout(info, 1)

        # 右侧按钮（垂直居中）
        folder_btn = QPushButton("打开文件夹")
        folder_btn.setObjectName("blueToolBtn")
        folder_btn.setFixedHeight(28)
        folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        folder_btn.clicked.connect(lambda: self.open_folder_clicked.emit(self._url))
        stop_btn = QPushButton("停止录制")
        stop_btn.setObjectName("redToolBtn")
        stop_btn.setFixedHeight(28)
        stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        stop_btn.clicked.connect(lambda: self.stop_clicked.emit(self._url))
        layout.addWidget(folder_btn)
        layout.addWidget(stop_btn)

        if self._start_time > 0:
            dt = datetime.fromtimestamp(self._start_time)
            self._start_time_label.setText(f"开始于: {dt.strftime('%H:%M:%S')}")

    def update_info(self, file_size: int):
        self._file_size = file_size
        size = file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                size_str = f"{size:.1f} {unit}"
                break
            size /= 1024
        else:
            size_str = f"{size:.1f} TB"
        self._size_label.setText(f"文件大小: {size_str}")

    def update_duration(self):
        if self._start_time <= 0:
            return
        elapsed = int(time.time() - self._start_time)
        h, m, s = elapsed // 3600, elapsed % 3600 // 60, elapsed % 60
        self._duration_label.setText(f"录制时长: {h:02d}:{m:02d}:{s:02d}")


class RecordingTab(QWidget):
    open_folder_requested = Signal(str)
    stop_recording_requested = Signal(str)
    history_clear_requested = Signal()
    delete_record_requested = Signal(int)       # 删除历史记录（索引）
    delete_file_requested = Signal(int, str)    # 删除文件（索引, 文件路径）

    def __init__(self, icon_dir: str = "", parent=None):
        super().__init__(parent)
        self._icon_dir = icon_dir
        self._cards = {}
        self._setup_ui()
        self._duration_timer = QTimer(self)
        self._duration_timer.timeout.connect(self._refresh_durations)
        self._duration_timer.setInterval(1000)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # ===== 正在录制区域 =====
        header = QHBoxLayout()
        title = QLabel("正在录制")
        title.setStyleSheet("color: #2C3E50; font-size: 18px; font-weight: bold; border: none; background: transparent;")
        header.addWidget(title)
        self._count_label = QLabel("")
        self._count_label.setStyleSheet("color: #2B8AF5; font-size: 13px; font-weight: bold; border: none; background: transparent;")
        header.addWidget(self._count_label)
        header.addStretch()
        layout.addLayout(header)

        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #E8ECF1; border: none;")
        layout.addWidget(sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setMinimumHeight(100)  # 确保至少能显示一个完整卡片
        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(8)
        self._container_layout.addStretch()
        scroll.setWidget(self._container)
        layout.addWidget(scroll, 1)

        # ===== 录制历史区域 =====
        hist_header = QHBoxLayout()
        hist_title = QLabel("录制历史")
        hist_title.setStyleSheet("color: #2C3E50; font-size: 18px; font-weight: bold; border: none; background: transparent;")
        hist_header.addWidget(hist_title)
        self._hist_count = QLabel("")
        self._hist_count.setStyleSheet("color: #8E9AAF; font-size: 13px; border: none; background: transparent;")
        hist_header.addWidget(self._hist_count)
        hist_header.addStretch()
        self._clear_hist_btn = QPushButton("清空历史")
        self._clear_hist_btn.setObjectName("redToolBtn")
        self._clear_hist_btn.setFixedHeight(28)
        self._clear_hist_btn.clicked.connect(self._on_clear_history)
        hist_header.addWidget(self._clear_hist_btn)
        layout.addLayout(hist_header)

        sep2 = QLabel()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet("background: #E8ECF1; border: none;")
        layout.addWidget(sep2)

        self._history_table = QTableWidget()
        self._history_table.setColumnCount(7)
        self._history_table.setHorizontalHeaderLabels([
            "主播", "平台", "标题", "时长", "大小", "时间", "操作"
        ])
        header = self._history_table.horizontalHeader()
        # 主播、平台、标题允许拉伸
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # 主播
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # 标题
        # 其他列固定或自适应内容
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # 平台
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # 时长
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # 大小
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # 时间
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(6, 120)  # 操作列固定120px
        self._history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._history_table.setAlternatingRowColors(True)
        self._history_table.verticalHeader().setDefaultSectionSize(44)
        self._history_table.verticalHeader().setVisible(False)
        layout.addWidget(self._history_table, 2)

    def add_recording(self, url: str, name: str, platform: str, start_time: float = 0):
        if url in self._cards:
            return
        card = RecordingCard(url, name, platform, start_time)
        card.stop_clicked.connect(self.stop_recording_requested.emit)
        card.open_folder_clicked.connect(self.open_folder_requested.emit)
        self._container_layout.insertWidget(self._container_layout.count() - 1, card)
        self._cards[url] = card
        self._update_count()
        if not self._duration_timer.isActive() and self._cards:
            self._duration_timer.start()

    def remove_recording(self, url: str):
        card = self._cards.pop(url, None)
        if card:
            self._container_layout.removeWidget(card)
            card.deleteLater()
        self._update_count()
        if not self._cards:
            self._duration_timer.stop()

    def update_recording(self, url: str, file_size: int):
        card = self._cards.get(url)
        if card:
            card.update_info(file_size)

    def refresh_history(self, records: list):
        """刷新历史记录表格"""
        self._history_table.setRowCount(len(records))
        for i, r in enumerate(records):
            # 主播
            item0 = QTableWidgetItem(r.anchor_name or "未知")
            item0.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._history_table.setItem(i, 0, item0)
            # 平台
            item1 = QTableWidgetItem(r.platform or "-")
            item1.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._history_table.setItem(i, 1, item1)
            # 标题
            item2 = QTableWidgetItem(r.title or "-")
            self._history_table.setItem(i, 2, item2)
            # 时长
            item3 = QTableWidgetItem(r.duration_str or "-")
            item3.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._history_table.setItem(i, 3, item3)
            # 大小
            item4 = QTableWidgetItem(r.file_size_str or "-")
            item4.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._history_table.setItem(i, 4, item4)
            # 时间
            item5 = QTableWidgetItem(r.start_time_str or "-")
            item5.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._history_table.setItem(i, 5, item5)
            # 操作 - 打开 + 删除
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(4, 0, 4, 0)
            btn_layout.setSpacing(6)
            open_btn = QPushButton("打开")
            open_btn.setFixedSize(50, 26)
            open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            open_btn.setStyleSheet("font-size: 11px; padding: 0px 6px; border-radius: 4px; border: 1px solid #DEE2E8; background: white; color: #2C3E50;")
            open_btn.clicked.connect(lambda checked, fp=r.file_path: self._open_file(fp))
            btn_layout.addWidget(open_btn)
            del_btn = QPushButton("删除")
            del_btn.setFixedSize(50, 26)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setStyleSheet("font-size: 11px; padding: 0px 6px; border-radius: 4px; border: 1px solid #E74C3C; background: white; color: #E74C3C;")
            del_btn.clicked.connect(lambda checked, idx=i, fp=r.file_path: self._on_delete_clicked(idx, fp))
            btn_layout.addWidget(del_btn)
            btn_layout.addStretch()
            self._history_table.setCellWidget(i, 6, btn_widget)
        self._hist_count.setText(f"({len(records)})" if records else "")

    def _open_file(self, file_path: str):
        if file_path and os.path.isfile(file_path):
            from app.utils.file_manager import open_file_location
            open_file_location(file_path)
        else:
            QMessageBox.information(self, "提示", "文件不存在或已被删除")

    def _on_delete_clicked(self, index: int, file_path: str):
        """点击删除按钮，弹出选择菜单"""
        menu = QMenu(self)
        act_record = menu.addAction("仅删除记录")
        act_file = menu.addAction("删除记录和文件")
        action = menu.exec(QCursor.pos())
        if action == act_record:
            self.delete_record_requested.emit(index)
        elif action == act_file:
            self.delete_file_requested.emit(index, file_path)

    def _on_clear_history(self):
        reply = QMessageBox.question(
            self, "确认清空", "确定要清空所有录制历史吗？\n（不会删除实际文件）",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.history_clear_requested.emit()

    def _refresh_durations(self):
        for card in self._cards.values():
            card.update_duration()

    def _update_count(self):
        count = len(self._cards)
        self._count_label.setText(f"({count})" if count > 0 else "")
