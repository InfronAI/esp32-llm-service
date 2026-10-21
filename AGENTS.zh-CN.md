# 仓库开发约定

[English](AGENTS.md) | **简体中文**

- 修改部署行为前，先阅读 README.md 和 docs/ 中的相关文档。
- 目标硬件：16 MB Flash、8 MB Octal PSRAM 的 ESP32-S3，MicroPython 1.29.0。原生模块使用 Xtensa windowed ABI，只接受固定的 260K 模型布局。
- 凭据保存在被忽略的 device/settings.json 与 reports/access.json。新安装使用 scripts/configure.py。不得发布设备备份、真实密码、盐、密码散列或 API Key。
- 使用项目 .venv。主机检查：`python -m unittest discover -s tests -p 'test_host.py'`、`python scripts/check_repo.py`，下载模型后执行 `python scripts/check_native.py --reference-only`。
- 固件刷写会覆盖板上状态，应与 scripts/deploy.py 的文件更新区分。首次安装前核对 USB 目标并保留备份；硬件操作遵循用户当前授权。
- USB REPL 测试会中断网络服务。测试后重启板子，并报告是否有真实硬件可用。
- shell 保持在主解释器线程，以便 Ctrl-C 中断用户 Python。HTTP 服务在后台线程运行，每次处理一个请求。
- 原生内核变更要与独立 C 参考实现对照，不得用固定回复或未经要求的远程模型替代真实推理。
- 明确 API 限制：TinyStories 续写、512 token 上下文、256 token 输出，不支持工具、视觉、embeddings 或 Responses API。
- 默认 Markdown 文档使用英文，配套简体中文版采用同目录 `.zh-CN.md` 文件，双向提供语言切换。更新时同步两种语言的命令、型号、限制和验证状态；上游候选不等于本项目已实现支持。
