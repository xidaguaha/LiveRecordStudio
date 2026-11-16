"""
综合测试脚本 - 验证 LiveRecordStudio 核心功能
运行: python tests/test_all.py
"""
import sys
import os
import time
import tempfile
import shutil
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.room import Room, RoomStatus, Quality, Platform, detect_platform
from app.config.settings import SettingsManager, AppSettings
from app.utils.ffmpeg_helper import find_ffmpeg, check_ffmpeg_available, build_ffmpeg_command
from app.utils.file_manager import generate_output_path
from app.utils.file_naming import format_filename, generate_recording_path, DEFAULT_TEMPLATE
from app.utils.history_manager import RecordingHistory, HistoryManager
from app.core.stream_parser import StreamParser, get_platform_class


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


def test_room_model(runner):
    print("\n[测试] Room 模型")
    r1 = Room.from_dict({'url': 'https://live.douyin.com/123', 'quality': 'OD', 'custom_name': '测试', 'enabled': True})
    runner.test("from_dict 创建", r1.url == 'https://live.douyin.com/123')
    runner.test("quality 解析", r1.quality == Quality.OD)
    runner.test("display_name", r1.display_name == '测试')

    r2 = Room.from_dict({'url': 'https://live.bilibili.com/456', 'quality': '原画'})
    runner.test("中文 quality", r2.quality == Quality.OD)
    runner.test("B站平台", r2.platform == Platform.BILIBILI)

    r3 = Room.from_dict(r1.to_dict())
    runner.test("往返序列化", r3.url == r1.url and r3.quality == r1.quality)


def test_settings_manager(runner):
    print("\n[测试] SettingsManager")
    tmp = tempfile.mkdtemp()
    try:
        mgr = SettingsManager(tmp)
        runner.test("默认路径存在", os.path.isdir(mgr.record.save_path))

        mgr.settings.rooms = [{'url': 'https://live.douyin.com/1', 'quality': 'OD', 'enabled': True}]
        mgr.save()

        mgr2 = SettingsManager(tmp)
        runner.test("房间加载", len(mgr2.get_rooms()) == 1)

        # 无效路径回退
        cfg = os.path.join(tmp, 'settings.json')
        with open(cfg, 'w', encoding='utf-8') as f:
            import json
            json.dump({'record': {'save_path': 'C:\\nonexistent\\path'}}, f)
        mgr3 = SettingsManager(tmp)
        runner.test("无效路径回退", os.path.isdir(mgr3.record.save_path))
    finally:
        shutil.rmtree(tmp)


def test_ffmpeg(runner):
    print("\n[测试] FFmpeg")
    path = find_ffmpeg()
    runner.test("找到 ffmpeg", path is not None and os.path.isfile(path))
    runner.test("内嵌 ffmpeg", 'LiveRecordStudio' in path or 'liveRecordStudio' in path.lower())

    avail, msg = check_ffmpeg_available()
    runner.test("ffmpeg 可用", avail, msg)

    cmd = build_ffmpeg_command('http://test.m3u8', 'out.ts')
    runner.test("命令含 -y", '-y' in cmd)
    runner.test("命令含输入", 'http://test.m3u8' in cmd)


def test_file_naming(runner):
    print("\n[测试] 文件命名模板")
    from datetime import datetime

    # 基本占位符
    result = format_filename(
        "{platform}/{owner}/{year}-{month}-{date} {title}",
        platform="抖音", owner="测试主播", title="直播标题",
        start_time=datetime(2024, 6, 1, 12, 30, 45)
    )
    runner.test("基本占位符", "抖音" in result and "测试主播" in result and "2024-06-01" in result)

    # 非法字符清理
    result2 = format_filename("{title}", title="测试<>:|标题")
    runner.test("非法字符清理", "<" not in result2 and ">" not in result2)

    # 完整路径生成
    tmp = tempfile.mkdtemp()
    try:
        path = generate_recording_path(
            tmp, DEFAULT_TEMPLATE,
            platform="抖音", owner="主播A", title="测试直播",
            ext="ts", start_time=datetime(2024, 6, 1, 12, 30, 45)
        )
        runner.test("路径生成", os.path.isabs(path) and path.endswith('.ts'))
        runner.test("目录创建", os.path.isdir(os.path.dirname(path)))

        # 重复文件自动编号（先创建空文件触发编号）
        open(path, 'a').close()
        path2 = generate_recording_path(
            tmp, DEFAULT_TEMPLATE,
            platform="抖音", owner="主播A", title="测试直播",
            ext="ts", start_time=datetime(2024, 6, 1, 12, 30, 45)
        )
        runner.test("自动编号", path != path2 and "_1" in path2)
    finally:
        shutil.rmtree(tmp)


def test_platform_detection(runner):
    print("\n[测试] 平台识别")
    tests = [
        ('https://live.douyin.com/123', '抖音'),
        ('https://live.bilibili.com/456', '哔哩哔哩'),
        ('https://www.huya.com/789', '虎牙'),
        ('https://www.douyu.com/abc', '斗鱼'),
        ('https://live.kuaishou.com/u/def', '快手'),
        ('https://www.twitch.tv/ghi', 'Twitch'),
        ('https://unknown.com/123', None),
    ]
    for url, expected in tests:
        info = get_platform_class(url)
        actual = info[1] if info else None
        runner.test(f"识别 {url[:25]}", actual == expected)


def test_stream_parser(runner):
    print("\n[测试] 流解析")
    async def do_test():
        parser = StreamParser()
        url = 'https://live.douyin.com/996301780973'
        result = await parser.fetch_stream_data(url, 'OD')
        runner.test("解析返回数据", result is not None)
        if result:
            runner.test("有主播名", bool(result.get('anchor_name')))
            runner.test("平台正确", result.get('platform') == '抖音')
            # 不强制要求 is_live=True，因为直播间可能下播
    asyncio.run(do_test())


def test_recording_history(runner):
    print("\n[测试] 录制历史")
    tmp = tempfile.mkdtemp()
    try:
        mgr = HistoryManager(tmp)

        # 添加记录
        r = RecordingHistory(
            url='https://live.douyin.com/123',
            anchor_name='主播A',
            title='测试直播',
            platform='抖音',
            start_time=time.time(),
            end_time=time.time() + 3600,
            file_path='/tmp/test.ts',
            file_size=1024 * 1024 * 100,
            duration=3600,
            status='completed'
        )
        mgr.add_record(r)
        runner.test("添加记录", len(mgr.get_records()) == 1)

        # 统计
        stats = mgr.get_stats()
        runner.test("统计总数", stats['total_count'] == 1)
        runner.test("统计完成数", stats['completed_count'] == 1)

        # 格式化属性
        record = mgr.get_records()[0]
        runner.test("时长格式化", record.duration_str == "1:00:00")
        runner.test("大小格式化", "MB" in record.file_size_str)
        runner.test("时间格式化", len(record.start_time_str) == 19)

        # 删除
        mgr.remove_record(0)
        runner.test("删除记录", len(mgr.get_records()) == 0)

        # 持久化
        mgr.add_record(r)
        mgr2 = HistoryManager(tmp)
        runner.test("持久化加载", len(mgr2.get_records()) == 1)
    finally:
        shutil.rmtree(tmp)


def test_end_to_end(runner):
    print("\n[测试] 端到端流程")
    tmp = tempfile.mkdtemp()
    try:
        # 1. 创建配置
        settings = SettingsManager(tmp)
        runner.test("配置初始化", os.path.isdir(settings.record.save_path))

        # 2. 添加房间
        room = Room.from_dict({'url': 'https://live.douyin.com/test', 'quality': 'OD'})
        settings.settings.rooms = [room.to_dict()]
        settings.save()

        # 3. 重新加载验证
        settings2 = SettingsManager(tmp)
        loaded_room = Room.from_dict(settings2.get_rooms()[0])
        runner.test("房间持久化", loaded_room.url == room.url)

        # 4. 生成录制路径
        path = generate_recording_path(
            settings2.record.save_path, DEFAULT_TEMPLATE,
            platform=loaded_room.platform.value,
            owner=loaded_room.display_name,
            title="测试标题",
            ext="ts"
        )
        runner.test("路径生成", path.endswith('.ts') and os.path.isdir(os.path.dirname(path)))

        # 5. 记录历史
        history = HistoryManager(tmp)
        record = RecordingHistory(
            url=loaded_room.url,
            anchor_name=loaded_room.display_name,
            platform=loaded_room.platform.value,
            file_path=path,
            start_time=time.time(),
            status='completed'
        )
        history.add_record(record)
        runner.test("历史记录", len(history.get_records()) == 1)
    finally:
        shutil.rmtree(tmp)


def main():
    runner = TestRunner()
    test_room_model(runner)
    test_settings_manager(runner)
    test_ffmpeg(runner)
    test_file_naming(runner)
    test_platform_detection(runner)
    test_stream_parser(runner)
    test_recording_history(runner)
    test_end_to_end(runner)
    ok = runner.summary()
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
