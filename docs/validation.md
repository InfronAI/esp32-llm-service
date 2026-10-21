# 验证方法与实测记录

## 测试分层

| 层次 | 命令 | 是否需要设备 |
| --- | --- | --- |
| Python 语法 | `.venv/bin/python -m compileall -q device scripts tests` | 否 |
| 配置/下载完整性 | `.venv/bin/python -m unittest discover -s tests -p 'test_host.py'` | 否 |
| 文档与发布内容 | `.venv/bin/python scripts/check_repo.py` | 否 |
| 独立 C 参考 | `.venv/bin/python scripts/check_native.py --reference-only` | 否，需要本机模型文件 |
| 原生推理对照 | `.venv/bin/python scripts/check_native.py --port <port>` | 是，USB |
| 端到端 API | `.venv/bin/python scripts/check_llm.py` | 是，可互通 LAN |
| shell 回环 | `.venv/bin/python scripts/check_device.py <port>` | 是，USB 控制板内 TCP |

[CI 模板](../ci/host-checks.yml)启用后在 GitHub Actions 执行前四类检查，不包含 ESP32 仿真或物理板测试。当前发布凭据没有 workflow 权限，因此模板保存在 `ci/`，尚未自动运行。启用方法见 [ci/README.md](../ci/README.md)。USB 测试会暂停网络程序；`check_native.py` 自动重启，旧 shell 测试结束后需手动 `mpremote connect <port> reset`。

## 独立参考

`tests/reference_run.c` 保存上游 karpathy/llama2.c 的参考实现，`reference_tokens.c` 只是输出 JSON 的入口。固定提示词 `Once upon a time`，temperature 0，32 个输出 token；已验证样本保存在 `tests/fixtures/reference.json`。

板上测试比较提示词 token IDs、32 个输出 token IDs、首步 512 维 logits，并检查权重和分词器 SHA-256。浮点允许误差阈值 `1e-4`。这一比较同时覆盖了分词、权重映射、矩阵乘法、RoPE 与注意力的实际执行结果。

## API 覆盖

34 项 LAN 检查包括：鉴权、模型列表、官方 SDK 普通与 SSE 调用、usage 与 finish reason、跨 token stop 字符串、固定 seed、legacy completions、非法 JSON 与参数、Unicode 输入、流式客户端断开后的恢复、推理期间 shell 登录和执行命令。

脚本读取私有 `reports/access.json`，结果写入同目录。通过 `--url` 临时更改 API 地址。shell 的自动测试用户假定为默认 `esp32`。

## 2026-10-21 硬件结果

在 ESP32-S3 rev 0.2 / 240 MHz / 16 MB Flash / 8 MB Octal PSRAM，MicroPython 1.29.0 上完成：

- 独立参考：32 token 完全相同，最大 logits 绝对误差约 `8.45e-6`。
- 模型与分词器：SHA-256 匹配清单。
- 原生生成：5 token 提示词生成 32 token 用时 1.092 秒，首 token 116 ms。
- HTTP 测试内的板上生成：同一长度用时 1.071 秒，约 29.88 token/s；Mac 完整调用约 1.70 秒。
- 128 token 生成：约 25.67 token/s。
- SDK/LAN 34 项、原 shell 30 项均通过，重启后 Wi-Fi 和 API 自动恢复已验证。

[脱敏机器可读记录](validation/2026-10-21.json)保留检查项目与性能数据；省略个人网络、设备标识和凭据。发布整理时未重新连接 USB，因此这些是此前完成的真实硬件记录，不是本次文档检查新产生的测试结果。

速度统计含提示词处理与采样，不是单纯 decode 吞吐。改变上下文、采样、网络环境或编译器均可能改变结果。单个样例一致不代表全面的模型质量评测。
