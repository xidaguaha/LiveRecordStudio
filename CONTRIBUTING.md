# 贡献指南

感谢您对 LiveRecordStudio 的关注！欢迎通过以下方式参与贡献。

## 提交 Issue

- **Bug 报告**：请说明操作系统、Python 版本、复现步骤、预期与实际行为，并附上日志（日志标签页可查看）。
- **功能建议**：请说明使用场景与期望效果。

## 提交 Pull Request

1. Fork 本仓库并创建特性分支：
   ```bash
   git checkout -b feature/your-feature
   ```
2. 开发并自测：
   - 遵循现有代码风格（中文注释、类型标注）。
   - 如涉及核心逻辑（`app/core/`），请在 `tests/` 中补充或更新测试。
3. 提交 PR，描述清楚改动内容与动机。

## 新增平台支持

平台解析基于 [streamget](https://github.com/ihmily/streamget) 库。若该库已支持目标平台，只需在 `app/core/stream_parser.py` 的 `_build_platform_map()` 中添加域名映射即可。

## 注意事项

- 请勿在代码或提交中包含个人令牌、Cookie、本机路径等敏感信息。
- 提交前请确认 `git status` 中没有构建产物（`build/`、`dist/`、`*.exe` 等）。
