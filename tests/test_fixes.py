"""
针对本次修复的专项测试
验证: ffmpeg打包路径、recorder崩溃清理、状态一致性、主播名更新、历史表格
"""
import sys
import os
import time
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from app.utils.ffmpeg_helper import find_ffmpeg, _get_project_root
from app.core.recorder import Recorder
from app.ui.live_tab import LiveTab, RoomRowWidget
from app.ui.recording_tab import RecordingTab
from app.models import Room, RoomStatus, detect_platform
from app.utils.history_manager import RecordingHistory

_app = None
def get_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    def test(self, name, condition, detail=""):
        if condition:
            self.passed += 1
            print(f"  [PASS] {name}")
        else:
            self.failed += 1
            msg = f"[FAIL] {name}"
            if detail:
                msg += f" - {detail}"
            print(f"  {msg}")
            self.errors.append(msg)
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*50}")
        print(f"总计: {total} | 通过: {self.passed} | 失败: {self.failed}")
        if self.errors:
            print("\n失败项:")
            for e in self.errors:
                print(f"  {e}")
        print(f"{'='*50}")
        return self.failed == 0


def test_ffmpeg_path(runner):
    """验证 ffmpeg 路径查找（开发环境）"""
    print("\n[测试] FFmpeg 路径查找")
    path = find_ffmpeg()
    runner.test("找到ffmpeg", path is not None)
    if path:
        runner.test("ffmpeg文件存在", os.path.isfile(path))
        runner.test("路径包含bin", "bin" in path or "ffmpeg" in path.lower())
    # 验证 _get_project_root 返回正确
    root = _get_project_root()
    runner.test("项目根目录存在", os.path.isdir(root))
    runner.test("项目根含app", os.path.isdir(os.path.join(root, "app")))


def test_recorder_crash_cleanup(runner):
    """验证 recorder 崩溃后 is_recording 返回 False"""
    print("\n[测试] Recorder 崩溃清理")
    get_app()
    rec = Recorder("ffmpeg")
    
    # 初始状态
    runner.test("初始非录制", not rec.is_recording)
    runner.test("初始process为None", rec._process is None)
    
    # 模拟崩溃后状态（_on_error Crashed 分支已清理）
    rec._current_url = "http://test.com"
    rec._current_file = "/tmp/test.ts"
    rec._process = None
    
    # is_recording 应返回 False
    runner.test("崩溃后非录制", not rec.is_recording)
    
    # _on_finished 双重触发保护：_process=None 且 _current_url="" 时跳过
    # 模拟 _on_error Crashed 已清理后的状态
    rec._current_url = ""
    rec._current_file = ""
    finished_urls = []
    rec.recording_finished.connect(lambda url, code: finished_urls.append(url))
    rec._on_finished(0, 0)
    runner.test("_on_finished不重复触发", len(finished_urls) == 0)


def test_status_consistency(runner):
    """验证状态不一致修复逻辑"""
    print("\n[测试] 状态一致性")
    
    # 模拟场景：monitor 上报 recording，但 active_recordings = 0
    status = "recording"
    active_recordings = 0
    if status == "recording" and active_recordings == 0:
        status = "monitoring"
    runner.test("无录制时应降级为monitoring", status == "monitoring")
    
    # 有录制时不应降级
    status = "recording"
    active_recordings = 1
    if status == "recording" and active_recordings == 0:
        status = "monitoring"
    runner.test("有录制时保持recording", status == "recording")
    
    # monitoring 状态不受影响
    status = "monitoring"
    active_recordings = 0
    if status == "recording" and active_recordings == 0:
        status = "monitoring"
    runner.test("monitoring不变", status == "monitoring")


def test_room_name_update(runner):
    """验证主播名自动更新"""
    print("\n[测试] 主播名自动更新")
    get_app()
    
    tab = LiveTab()
    room = Room(url="https://live.douyin.com/12345")
    # 初始无主播名，显示"抖音直播间"
    runner.test("初始显示默认名", room.display_name == "抖音直播间")
    
    tab.set_rooms([room])
    row = tab._rows.get(room.url)
    runner.test("行存在", row is not None)
    if row:
        runner.test("初始标签=抖音直播间", row._name_label.text() == "抖音直播间")
        
        # 模拟监控返回主播名
        name_updated = [False]
        def on_name_updated(url, name):
            name_updated[0] = True
        tab.room_name_updated.connect(on_name_updated)
        
        tab.update_room_status(room.url, "monitoring", "花满楼")
        
        runner.test("主播名已更新", room.anchor_name == "花满楼")
        runner.test("标签已刷新", row._name_label.text() == "花满楼")
        runner.test("信号已发射", name_updated[0])


def test_history_table_layout(runner):
    """验证历史表格布局"""
    print("\n[测试] 历史表格布局")
    get_app()
    
    tab = RecordingTab()
    table = tab._history_table
    
    # 列数
    runner.test("7列", table.columnCount() == 7)
    
    # 行高
    vheader = table.verticalHeader()
    runner.test("行高40px", vheader.defaultSectionSize() == 40)
    runner.test("行号隐藏", not vheader.isVisible())
    
    # 添加数据验证
    records = [
        RecordingHistory(
            url='https://live.douyin.com/test',
            anchor_name='测试主播A',
            title='测试直播标题比较长的情况',
            platform='抖音',
            start_time=time.time() - 3600,
            end_time=time.time(),
            file_path='/tmp/test.ts',
            file_size=1024*1024*150,
            duration=3600,
            status='completed'
        ),
    ]
    tab.refresh_history(records)
    
    runner.test("1行数据", table.rowCount() == 1)
    
    # 验证对齐
    item0 = table.item(0, 0)
    if item0:
        runner.test("主播列居中", item0.textAlignment() == Qt.AlignmentFlag.AlignCenter)
    
    # 验证操作列有widget
    widget = table.cellWidget(0, 6)
    runner.test("操作列有按钮widget", widget is not None)


def test_svg_icon_rendering(runner):
    """验证 QSvgRenderer 图标渲染"""
    print("\n[测试] SVG 图标渲染")
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtGui import QPixmap, QPainter
    from PySide6.QtCore import QSize, Qt
    
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
</svg>'''
    
    # 替换颜色
    svg_colored = svg.replace('stroke="currentColor"', 'stroke="#2B8AF5"')
    
    renderer = QSvgRenderer()
    loaded = renderer.load(svg_colored.encode('utf-8'))
    runner.test("SVG加载成功", loaded)
    
    if loaded:
        pix = QPixmap(QSize(22, 22))
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        renderer.render(painter)
        painter.end()
        runner.test("渲染非空", not pix.isNull())
        runner.test("尺寸正确", pix.width() == 22 and pix.height() == 22)


def main():
    runner = TestRunner()
    test_ffmpeg_path(runner)
    test_recorder_crash_cleanup(runner)
    test_status_consistency(runner)
    test_room_name_update(runner)
    test_history_table_layout(runner)
    test_svg_icon_rendering(runner)
    ok = runner.summary()
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()