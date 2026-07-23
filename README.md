# LiveRecord Studio

多平台直播自动录制工具，基于 Python + PySide6 + FFmpeg。

## 功能特性

- **多平台支持**：Bilibili、快手、抖音、斗鱼、虎牙、YouTube 等主流直播平台
- **自动监控**：定时检测直播间状态，开播自动录制，下播自动停止
- **多房间并发**：同时监控多个直播间，独立录制互不干扰
- **画质选择**：原画 / 高清 / 标清可选
- **录制格式**：TS 流式录制（断电不丢数据），可选自动转码 MP4
- **录制历史**：信号记录 + 本地文件扫描双重验证，不丢失任何录制
- **Cookie 登录态**：每个直播间可单独设置 Cookie，支持需要登录的平台
- **Webhook 推送**：开播 / 下播自动推送通知到钉钉
- **系统托盘**：最小化到托盘，后台持续监控
- **文件管理**：录制历史中可直接打开文件所在目录、删除记录或删除文件

## 技术栈

| 组件 | 技术 |
|------|------|
| GUI | PySide6 (Qt6) |
| 流解析 | stream-gear |
| 录制 | FFmpeg (QProcess) |
| 打包 | PyInstaller |

## 快速开始

### 环境要求

- Python 3.10+
- FFmpeg 7.x（自动内置）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行

```bash
python main.py
```

### 打包

```bash
pyinstaller -y --distpath dist LiveRecordStudio.spec
```

## 项目结构

```
LiveRecordStudio/
├── main.py                    # 程序入口
├── requirements.txt           # Python 依赖
├── LiveRecordStudio.spec      # PyInstaller 打包配置
├── app/
│   ├── style.qss              # 全局样式表
│   ├── config/
│   │   └── settings.py        # 配置管理（JSON 持久化）
│   ├── core/
│   │   ├── recorder.py        # 录制引擎（QProcess + FFmpeg）
│   │   ├── monitor.py         # 直播监控（QThread 轮询）
│   │   ├── stream_parser.py   # 流地址解析（stream-gear）
│   │   └── task_manager.py    # 任务调度（监控/录制/转码）
│   ├── models/
│   │   └── room.py            # 房间数据模型
│   ├── ui/
│   │   ├── main_window.py     # 主窗口
│   │   ├── live_tab.py        # 直播间列表
│   │   ├── recording_tab.py   # 录制状态 + 历史记录
│   │   ├── settings_tab.py    # 设置页
│   │   ├── log_tab.py         # 运行日志
│   │   ├── about_tab.py       # 关于页
│   │   ├── add_room_dialog.py # 添加房间对话框
│   │   └── components.py      # 通用 UI 组件
│   └── utils/
│       ├── ffmpeg_helper.py   # FFmpeg 查找与管理
│       ├── file_manager.py    # 文件操作（打开目录等）
│       ├── file_naming.py     # 录制文件命名模板
│       └── history_manager.py # 录制历史持久化
```

## 使用说明

1. **添加直播间**：点击"添加直播间"按钮，粘贴直播间 URL
2. **启动监控**：点击"全部开始"或单独启用某个房间
3. **录制设置**：在设置页配置保存路径、画质、检测间隔等
4. **查看历史**：在录制页查看所有录制记录，支持打开文件、删除记录
5. **设置 Cookie**：右键直播间 → "设置 Cookie"（部分平台需要）

## 许可证

MIT License