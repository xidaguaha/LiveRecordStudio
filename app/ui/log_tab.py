"""日志面板"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QPlainTextEdit, QComboBox
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCharFormat, QColor
from datetime import datetime


class LogTab(QWidget):
    LEVEL_COLORS = {
        "info": "#2C3E50",
        "warning": "#E67E22",
        "error": "#E74C3C",
        "debug": "#B0B8C4",
    }
    FILTER_MAP = {"全部": "all", "信息": "info", "警告": "warning", "错误": "error"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._max_lines = 5000
        self._auto_scroll = True
        self._all_logs = []  # 存储所有日志: [(level, message, timestamp), ...]
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        title = QLabel("日志")
        title.setStyleSheet("color: #2C3E50; font-size: 18px; font-weight: bold; border: none; background: transparent;")
        toolbar.addWidget(title)
        toolbar.addStretch()

        self._filter_combo = QComboBox()
        self._filter_combo.addItems(["全部", "信息", "警告", "错误"])
        self._filter_combo.setFixedWidth(100)
        self._filter_combo.setFixedHeight(32)
        self._filter_combo.currentTextChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self._filter_combo)

        self._auto_scroll_btn = QPushButton("自动滚动: 开")
        self._auto_scroll_btn.setFixedHeight(32)
        self._auto_scroll_btn.setCheckable(True)
        self._auto_scroll_btn.setChecked(True)
        self._auto_scroll_btn.toggled.connect(self._on_auto_scroll)
        toolbar.addWidget(self._auto_scroll_btn)

        self._clear_btn = QPushButton("清空")
        self._clear_btn.setFixedHeight(32)
        self._clear_btn.clicked.connect(self._on_clear)
        toolbar.addWidget(self._clear_btn)
        layout.addLayout(toolbar)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(self._max_lines)
        layout.addWidget(self._log, 1)

    def append_log(self, level: str, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._all_logs.append((level, message, timestamp))

        # 超过上限时裁剪
        if len(self._all_logs) > self._max_lines:
            self._all_logs = self._all_logs[-self._max_lines:]

        # 检查当前过滤条件
        current = self.FILTER_MAP.get(self._filter_combo.currentText(), "all")
        if current != "all" and level != current:
            return

        color = self.LEVEL_COLORS.get(level, "#2C3E50")
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        self._log.setCurrentCharFormat(fmt)
        self._log.appendPlainText(f"[{timestamp}] [{level.upper()}] {message}")
        if self._auto_scroll:
            sb = self._log.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _on_filter_changed(self, text: str):
        """过滤条件改变时，用存储的日志重建显示"""
        target = self.FILTER_MAP.get(text, "all")
        self._log.clear()
        for level, message, timestamp in self._all_logs:
            if target != "all" and level != target:
                continue
            color = self.LEVEL_COLORS.get(level, "#2C3E50")
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            self._log.setCurrentCharFormat(fmt)
            self._log.appendPlainText(f"[{timestamp}] [{level.upper()}] {message}")
        if self._auto_scroll:
            sb = self._log.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _on_clear(self):
        self._all_logs.clear()
        self._log.clear()

    def _on_auto_scroll(self, checked):
        self._auto_scroll = checked
        self._auto_scroll_btn.setText(f"自动滚动: {'开' if checked else '关'}")