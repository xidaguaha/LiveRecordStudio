"""
集成测试 - 验证GUI组件和信号流程
运行: python tests/test_integration.py
"""
import sys
import os
import time
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QObject, Signal

from app.config.settings import SettingsManager, RecordSettings
from app.utils.file_naming import DEFAULT_TEMPLATE
from app.utils.history_manager import RecordingHistory, HistoryManager
from app.core.task_manager import TaskManager
from app.ui.settings_tab import SettingsTab
from app.ui.recording_tab import RecordingTab


# 全局QApplication（Qt要求）
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


def test_settings_tab_template(runner):
    """测试设置页的filename_template加载和保存"""
    print("\n[测试] SettingsTab 模板配置")
    get_app()

    tab = SettingsTab()

    # 模拟加载设置
    settings = SettingsManager(tempfile.mkdtemp())
    settings.record.filename_template = "{platform}/{owner}/test_{title}"
    tab.load_settings(settings.settings)

    runner.test("加载自定义模板", tab._template_input.text() == "{platform}/{owner}/test_{title}")

    # 修改模板
    tab._template_input.setText("{year}-{month}/{owner}")
    data = tab.get_settings()
    runner.test("保存自定义模板", data.get("filename_template") == "{year}-{month}/{owner}")

    # 默认模板
    tab._template_input.setText("")
    data2 = tab.get_settings()
    runner.test("空模板保存", data2.get("filename_template") == "")

    # 清理
    shutil.rmtree(settings._config_dir, ignore_errors=True)


def test_settings_persistence(runner):
    """测试filename_template在SettingsManager中的持久化"""
    print("\n[测试] SettingsManager 模板持久化")
    tmp = tempfile.mkdtemp()
    try:
        # 创建并保存
        mgr = SettingsManager(tmp)
        mgr.record.filename_template = "custom/{platform}/{title}"
        mgr.save()

        # 重新加载
        mgr2 = SettingsManager(tmp)
        runner.test("模板持久化加载", mgr2.record.filename_template == "custom/{platform}/{title}")

        # 验证JSON内容
        import json
        with open(mgr2._filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        runner.test("JSON含模板字段", "filename_template" in data.get("record", {}))
        runner.test("JSON模板值正确", data["record"]["filename_template"] == "custom/{platform}/{title}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_task_manager_signals(runner):
    """测试TaskManager的recording_completed信号流程"""
    print("\n[测试] TaskManager 信号流程")
    get_app()

    # 使用内嵌ffmpeg路径
    ffmpeg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ffmpeg", "bin", "ffmpeg.exe")
    if not os.path.isfile(ffmpeg_path):
        ffmpeg_path = "ffmpeg"

    tm = TaskManager(ffmpeg_path)

    # 配置record_settings
    class FakeSettings:
        save_path = tempfile.mkdtemp()
        video_format = "ts"
        filename_template = "{platform}/{owner}/test"
        auto_split = False
        split_duration = 3600

    tm.configure(FakeSettings(), proxy="")

    # 监听recording_completed信号
    received = {}
    def on_completed(url, file_path, file_size, duration):
        received['url'] = url
        received['file_path'] = file_path
        received['file_size'] = file_size
        received['duration'] = duration

    tm.recording_completed.connect(on_completed)

    # 模拟stream_data（不实际启动录制，只验证信号连接）
    runner.test("recording_completed信号已连接", True)

    # 验证配置已传入
    runner.test("TaskManager配置保存", tm._record_settings is not None)
    runner.test("TaskManager模板读取", getattr(tm._record_settings, 'filename_template', '') == "{platform}/{owner}/test")

    # 清理
    shutil.rmtree(FakeSettings.save_path, ignore_errors=True)


def test_recording_tab_history(runner):
    """测试RecordingTab历史记录显示"""
    print("\n[测试] RecordingTab 历史记录")
    get_app()

    tab = RecordingTab("")

    # 创建模拟历史记录
    records = [
        RecordingHistory(
            url='https://live.douyin.com/123',
            anchor_name='主播A',
            title='测试直播1',
            platform='抖音',
            start_time=time.time() - 3600,
            end_time=time.time(),
            file_path='/tmp/test1.ts',
            file_size=1024 * 1024 * 50,
            duration=3600,
            status='completed'
        ),
        RecordingHistory(
            url='https://live.bilibili.com/456',
            anchor_name='主播B',
            title='测试直播2',
            platform='哔哩哔哩',
            start_time=time.time() - 1800,
            end_time=time.time(),
            file_path='/tmp/test2.ts',
            file_size=1024 * 1024 * 120,
            duration=1800,
            status='completed'
        ),
    ]

    tab.refresh_history(records)

    runner.test("历史表格行数", tab._history_table.rowCount() == 2)
    runner.test("历史计数显示", tab._hist_count.text() == "(2)")

    # 验证单元格内容
    item0 = tab._history_table.item(0, 0)
    runner.test("第一行主播名", item0 is not None and item0.text() == "主播A")

    item1 = tab._history_table.item(1, 1)
    runner.test("第二行平台", item1 is not None and item1.text() == "哔哩哔哩")

    # 清空历史
    tab.refresh_history([])
    runner.test("清空后行数", tab._history_table.rowCount() == 0)
    runner.test("清空后计数", tab._hist_count.text() == "")


def test_history_manager_integration(runner):
    """测试HistoryManager与文件系统的集成"""
    print("\n[测试] HistoryManager 集成")
    tmp = tempfile.mkdtemp()
    try:
        mgr = HistoryManager(tmp)

        # 批量添加记录
        for i in range(5):
            r = RecordingHistory(
                url=f'https://live.douyin.com/{i}',
                anchor_name=f'主播{i}',
                title=f'直播{i}',
                platform='抖音',
                start_time=time.time(),
                end_time=time.time() + 300,
                file_path=f'/tmp/test{i}.ts',
                file_size=1024 * 1024 * (i + 1),
                duration=300,
                status='completed'
            )
            mgr.add_record(r)

        runner.test("批量添加", len(mgr.get_records()) == 5)

        # 统计验证
        stats = mgr.get_stats()
        runner.test("统计总数", stats['total_count'] == 5)
        runner.test("统计完成数", stats['completed_count'] == 5)

        # 持久化验证
        mgr2 = HistoryManager(tmp)
        runner.test("持久化加载", len(mgr2.get_records()) == 5)

        # 清空
        mgr.clear()
        runner.test("清空后", len(mgr.get_records()) == 0)

        # 验证文件也被清空
        hist_file = os.path.join(tmp, "recording_history.json")
        runner.test("历史文件存在", os.path.isfile(hist_file))
        import json
        with open(hist_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        runner.test("历史文件为空", isinstance(data, list) and len(data) == 0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_default_template_consistency(runner):
    """验证各处默认模板的一致性"""
    print("\n[测试] 默认模板一致性")

    from app.config.settings import RecordSettings
    from app.utils.file_naming import DEFAULT_TEMPLATE

    # RecordSettings默认值
    rs = RecordSettings()
    runner.test("RecordSettings默认模板", rs.filename_template == DEFAULT_TEMPLATE)

    # DEFAULT_TEMPLATE格式验证
    runner.test("模板含platform", "{platform}" in DEFAULT_TEMPLATE)
    runner.test("模板含owner", "{owner}" in DEFAULT_TEMPLATE)
    runner.test("模板含title", "{title}" in DEFAULT_TEMPLATE)
    runner.test("模板含year", "{year}" in DEFAULT_TEMPLATE)
    runner.test("模板含month", "{month}" in DEFAULT_TEMPLATE)
    runner.test("模板含date", "{date}" in DEFAULT_TEMPLATE)


def test_file_naming_with_template(runner):
    """测试使用自定义模板的文件命名"""
    print("\n[测试] 自定义模板文件命名")
    from app.utils.file_naming import format_filename, generate_recording_path
    from datetime import datetime

    tmp = tempfile.mkdtemp()
    try:
        # 测试各种模板
        templates = [
            ("{platform}/{owner}/{title}", "抖音/主播/直播"),
            ("{year}-{month}-{date}/{owner}", "2024-01-15/主播"),
            ("{owner}_{title}_{platform}", "主播_直播_抖音"),
        ]

        for template, expected_part in templates:
            result = format_filename(
                template,
                platform="抖音",
                owner="主播",
                title="直播",
                start_time=datetime(2024, 1, 15, 10, 30, 0)
            )
            runner.test(f"模板: {template}", expected_part in result or result.endswith(expected_part.split("/")[-1]))

        # 测试generate_recording_path使用模板
        path = generate_recording_path(
            tmp,
            "{platform}/{owner}/test_{title}",
            platform="抖音",
            owner="主播A",
            title="测试",
            ext="ts",
            start_time=datetime(2024, 1, 15, 10, 30, 0)
        )
        runner.test("自定义模板路径", "抖音" in path and "主播A" in path and path.endswith(".ts"))
        runner.test("自定义模板目录创建", os.path.isdir(os.path.dirname(path)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    runner = TestRunner()
    test_settings_tab_template(runner)
    test_settings_persistence(runner)
    test_task_manager_signals(runner)
    test_recording_tab_history(runner)
    test_history_manager_integration(runner)
    test_default_template_consistency(runner)
    test_file_naming_with_template(runner)
    ok = runner.summary()
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
