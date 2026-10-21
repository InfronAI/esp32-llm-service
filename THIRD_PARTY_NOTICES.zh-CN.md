# 第三方来源与许可证

[English](THIRD_PARTY_NOTICES.md) | **简体中文**

仓库 MIT 许可证适用于本项目原创代码和文档。上游声明予以保留；它不会重新授权下载的模型权重、固件或工具链。

| 组件 | 来源 / 可追溯信息 | 许可证及处理方式 |
| --- | --- | --- |
| Transformer C 实现 | [doryiii/esp32-llm](https://github.com/doryiii/esp32-llm/tree/c6c647f7bfbb74efd2bbfd9a1725da4a903589f4) 的 `main/llm.c` 和 `main/llm.h`，源自 karpathy/llama2.c | Andrej（2023）和 Dory（2026）的 MIT 声明保留在 `native/transformer.c` 和 `.h` |
| 独立参考实现 | [karpathy/llama2.c/run.c](https://github.com/karpathy/llama2.c/blob/master/run.c)，于 2026-10-21 获取，保存为 `tests/reference_run.c` | [MIT 许可证](tests/LICENSE.llama2.c) |
| MicroPython 固件与构建源码 | [MicroPython](https://github.com/micropython/micropython/tree/v1.29.0)，精确 commit 见 `firmware/manifest.json` | [MicroPython 许可证](https://github.com/micropython/micropython/blob/v1.29.0/LICENSE)；下载到被忽略的本机目录 |
| TinyStories 260K 权重及分词器 | `models/manifest.json` 固定 doryiii/esp32-llm 的版本；上游模型系列为 [karpathy/tinyllamas](https://huggingface.co/karpathy/tinyllamas) | 下载时验证 SHA-256；模型条款以上游为准，源码仓库不包含权重 |
| Xtensa 编译器与运行库 | Espressif Arduino ESP32 core 3.3.8 / esp-x32 2601 | 单独安装，遵循各自 GCC 运行库 / C 库条款；编译后的 `.mpy` 为本机构建产物 |
| Python 主机工具 | `requirements.txt` 中的固定版本包 | 单独安装，遵循各包许可证 |

原生适配修改了内存分配归属、固定 checkpoint 布局检查，使用可移植的四累加器矩阵乘法，并暴露两个 MicroPython 原生函数。独立参考代码用于正确性对照，不作为板上实现。

[模型选型文档](docs/models.zh-CN.md)链接的其他项目仅供研究；其代码、权重和训练数据未随本仓库分发。移植时应分别核对所选资产的上游许可。
