# 模型选择与 ESP32-S3 的约束条件

[English](models.md) | **简体中文**

[文档索引](README.zh-CN.md) · [项目 README](../README.zh-CN.md) · [系统架构](architecture.zh-CN.md)

**ESP32-S3 并不局限于 TinyStories 260K。** 已有公开项目通过量化、Flash 映射、专门的模型结构和精简原生运行时，在单块 16 MB Flash / 8 MB PSRAM 板上运行更大的模型。能否运行取决于完整实现，没有统一的参数量上限。

本文于 **2026-10-21** 核对上游资料。本仓库实际部署并验证的只有 TinyStories 260K。其余候选均需要移植或更换固件，目前不能通过本服务的 `model` 字段切换；上游性能数据尚未由本项目复测。

## 1. 硬件预算

已验证板卡有两颗 240 MHz Xtensa LX7 核、512 KB 片内 SRAM、8 MB Octal PSRAM 和 16 MB Flash。片内 SRAM 还要供固件及网络使用；PSRAM 容量更大，但经外部存储接口和缓存访问。ESP-IDF 文档中的 32 MB 外部存储**虚拟地址范围**，不代表这块板子有 32 MB 物理内存。参见 [ESP32-S3 数据手册](https://www.espressif.com/sites/default/files/documentation/esp32-s3_datasheet_en.pdf)和 [ESP-IDF 外部 RAM 文档](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-guides/external-ram.html)。

| 约束 | 必须容纳或实现的内容 |
| --- | --- |
| Flash 容量与分区 | Bootloader、分区表、固件、NVS、文件系统、模型和分词器。16 MB 芯片并不等于可以存放 16 MB 权重。 |
| 可用 RAM | 常驻权重、KV cache、激活、logits、分词器、MicroPython 堆、网络、线程栈及分配余量。应在服务启动后测量空闲内存和最大连续可分配块。 |
| 上下文长度 | 注意力历史越长，KV 存储和每 token 的注意力计算越多；提示词与生成内容都占上下文。 |
| 词表 | Embedding、输出矩阵、logits 和分词器可能占小模型的大部分资源；大规模多语言词表也需要空间和计算。 |
| 算力与带宽 | 原生内核、Flash/PSRAM 访问、反量化和任务调度共同决定速度。双核不保证服务吞吐翻倍。 |
| 模型与运行时兼容 | 张量布局、量化格式、算子、分词器、RoPE、注意力头、输出权重共享和特殊 token 必须匹配。 |
| 应用资源 | Wi-Fi、HTTP/SSE、鉴权和 shell 会占用某些纯串口演示未包含的资源，需要在完整服务下重新验证稳定性。 |

### 权重大小只是起点

对于 `N` 个存储参数、每个权重 `b` bit：

```text
weight_bytes ≈ N × b / 8 + scales + zero_points + headers + alignment
RAM_needed = resident_weights + KV_cache + activations + logits
             + tokenizer + runtime/network/stacks + allocation_headroom
Flash_needed = firmware/partitions/filesystem + model_assets + other_files
```

即：权重还要加量化缩放因子、零点、文件头和对齐；RAM 还要加运行状态、分词器及服务开销；Flash 还要加固件、分区及其他文件。

下表是**裸权重理论下限**，使用十进制 MB（`1 MB = 1,000,000 字节`），不包含上述任何额外开销。`1 MiB = 1,048,576 字节`；候选列表采用精确字节数，避免上游 MB/MiB 写法混用。

| 参数量 | FP32 | INT8 | INT4 |
| --- | ---: | ---: | ---: |
| 1M | 4 MB | 1 MB | 0.5 MB |
| 3M | 12 MB | 3 MB | 1.5 MB |
| 15M | 60 MB | 15 MB | 7.5 MB |
| 30M | 120 MB | 30 MB | 15 MB |
| 100M | 400 MB | 100 MB | 50 MB |
| 1B | 4,000 MB | 1,000 MB | 500 MB |

按此计算，常规 100M 或十亿参数的 INT4 权重无法完整存入这块板的 16 MB Flash，也无法完整装入 8 MB PSRAM。外部存储、主机卸载或多板协同会改变系统前提。下文的 30.72M 案例依赖严格受限的实现，不代表任意 30M 模型都可运行。

### KV cache 可能超过剩余内存

对采用 MHA 或 GQA 的常规完整注意力：

```text
KV_bytes = 2 × layers × context_tokens × kv_heads × head_dim × bytes_per_KV_element
```

系数 2 对应 Key 和 Value。当前 260K 模型的 `layers=5`、`context=512`、`kv_heads=4`、`head_dim=8`，FP32 cache 每元素 4 字节：

```text
2 × 5 × 512 × 4 × 8 × 4 = 655,360 bytes = 640 KiB
```

完整原生运行状态为 **676,192 字节**，包含 KV cache 及其他缓冲区；权重文件另占 **1,056,540 字节**，尚未加 Python 分词器、HTTP 和 shell。上下文翻倍，这部分 KV 分配也翻倍。权重量化为 INT4 **不会自动量化 KV cache**；缓存精度需要单独实现和验证。当前模型数据可在 [native/module.c](../native/module.c)、[native/transformer.c](../native/transformer.c) 和[架构文档](architecture.zh-CN.md)中追溯。

### Flash 映射和模型结构会改变取舍

原生运行时可映射模型分区，直接从 Flash 读取权重，只将工作缓冲区或部分张量放进 RAM。这样省去完整的 RAM 副本，但仍消耗 Flash 容量、缓存和访问带宽，需要相应分区及运行时支持。当前 MicroPython 加载器会把整个权重文件读入 Python 持有的缓冲区。

Per-Layer Embeddings（**PLE，逐层嵌入**）将按 token 访问的大型可学习查表与较小的 Transformer 核心结合。因此，28.9M PLE 模型的每 token 计算量不等同于 28.9M 稠密 Transformer。[esp32-ai 的设计与实验](https://github.com/slvDev/esp32-ai/blob/52ebcbbd905270592c1d415efd1128d04d0fa365/RESULTS.md)介绍了这一差别。这里列出的 PLE 模型是独立训练的模型，并非十亿参数级的 Gemma 3n 权重。

## 2. 可选模型与仓库来源

**本项目已验证**：已在本项目的 MicroPython 服务中测试。**仅上游验证**：链接作者报告在 ESP32-S3 上运行，本项目尚未集成和复测。大小指部署权重文件，不是总内存或完整安装大小。

| 模型 / 适用任务 | 部署权重 | 验证情况与上下文 | 模型来源 | ESP32 推理实现 |
| --- | --- | --- | --- | --- |
| **TinyStories 260K**，英文故事续写 | FP32；**1,056,540 B** | **本项目已验证**；512 token 上下文；记录的 32 token API 测试约 **29.88 token/s** | [260K 模型系列](https://huggingface.co/karpathy/tinyllamas/tree/main/stories260K)；精确版本及校验值见[清单](../models/manifest.json) | [本项目](../native/transformer.c)，改编自 [doryiii/esp32-llm](https://github.com/doryiii/esp32-llm/tree/c6c647f7bfbb74efd2bbfd9a1725da4a903589f4) |
| **TinyStories 3.3M**，英文故事续写 | INT8；**3,352,576 B**，`stories3M-q80.bin`；搭配 `tok4096.bin` | **仅上游验证**；作者报告 8 MB PSRAM 上约 **12 token/s** | [量化权重与分词器](https://github.com/doryiii/esp32-llm/tree/c6c647f7bfbb74efd2bbfd9a1725da4a903589f4/spiffs_data) | [INT8 内核 `llm8.c`](https://github.com/doryiii/esp32-llm/blob/c6c647f7bfbb74efd2bbfd9a1725da4a903589f4/main/llm8.c) 及其 ESP-IDF 固件 |
| **Barista 8.9M**，英文意式咖啡故障问答 | INT4 PLE；**4,600,186 B** | **仅上游验证**；128 token 上下文；纯串口基准为每秒 **16.60 个输出片段** | [slvDev/esp32-ai-barista](https://huggingface.co/slvDev/esp32-ai-barista) | [esp32-ai Barista 固件](https://github.com/slvDev/esp32-ai/tree/52ebcbbd905270592c1d415efd1128d04d0fa365/firmware/esp32_barista) |
| **Stories15M / 15.2M**，英文故事续写 | INT4；**7,857,568 B**（约 7.49 MiB） | **仅上游验证**；256 token 上下文；作者报告约 **2.54–2.96 token/s** | [原始 `stories15M.bin`](https://huggingface.co/karpathy/tinyllamas/tree/main)；[INT4 导出及权重](https://github.com/imFARSI/NanoMind-S3/tree/c8a4f8e1c325fe7a4c3a99aacfe54289090fe9aa) | [NanoMind-S3 ESP-IDF 固件](https://github.com/imFARSI/NanoMind-S3/tree/c8a4f8e1c325fe7a4c3a99aacfe54289090fe9aa/firmware)，双核及 Flash 映射 |
| **esp32-ai TinyStories 28.9M**，英文故事续写 | INT4 PLE；**14,912,348 B** | **仅上游验证**；256 token 上下文；模型卡报告串口约 **9.88 token/s** | [slvDev/esp32-ai-tinystories](https://huggingface.co/slvDev/esp32-ai-tinystories) | [esp32-ai TinyStories 固件](https://github.com/slvDev/esp32-ai/tree/52ebcbbd905270592c1d415efd1128d04d0fa365/firmware/esp32_tinystories) |
| **record42 / 30.72M**，英文故事续写 | INT4，分组 128，FP16 缩放因子；**16,101,008 B**（约 15.36 MiB） | **仅上游验证**；192 token 上下文；作者报告端到端约 **0.95 token/s** | [原始 `stories42M.bin`](https://huggingface.co/karpathy/tinyllamas/tree/main)；通过 [record42 项目](https://github.com/JARACH-209/esp32-30.7M/tree/0ee74541ac7a0e7e4ebe1bc85ade2717abb7ec89)裁剪并打包 | [esp32-30.7M](https://github.com/JARACH-209/esp32-30.7M/tree/0ee74541ac7a0e7e4ebe1bc85ade2717abb7ec89)，自定义 Flash 布局和部分 PSRAM 驻留 |

**这些速度不能作为同条件性能排名。** 固件、上下文、提示词长度、输出词表、采样及计时范围均不同。本项目统计包含提示词处理和采样，Mac HTTP 往返另行计时；Barista 生成受限输出类别（“片段”），与 TinyStories 的 token 单位不同。参见[本项目验证](validation.zh-CN.md)、[Barista 基准](https://github.com/slvDev/esp32-ai/blob/52ebcbbd905270592c1d415efd1128d04d0fa365/firmware/esp32_barista/README.md)和各上游 README。

### 各候选需要的改造

| 候选 | 必要改动及关键限制 |
| --- | --- |
| TinyStories 3.3M | 移植或采用 INT8 内核、量化文件解析及 4096 词表分词器；重算运行状态并为 Wi-Fi/shell 留内存。由于与当前内核同源，适合作为首次集成实验，这是工程判断，并非已完成支持。 |
| Barista 8.9M | 需要 PLE 内核和 `tokenizer.json`、`vocab.json`、`layout.json`。输入、输出词表不同，输出类别必须映射回输入 token ID；只适合 ASCII 英文咖啡问题，输出词表受限，不是通用或中文助手。 |
| Stories15M | 需要 NanoMind 的量化格式、Flash 映射及双核运行时。256 token 的 FP32 KV cache 单独就有 **3,538,944 B**，计算式为 `2 × 6 × 256 × 6 × 48 × 4`。加入网络服务后，要重新验证串口演示的内存预算。 |
| esp32-ai TinyStories 28.9M | 需要 PLE 算子、分词资产、张量驻留策略及适当的 Flash 分区。约 25M 参数为查表，稠密核心约 0.56M；模型是故事续写模型，没有聊天指令训练。 |
| record42 / 30.72M | 将 Stories42M 的词表从 32,000 裁到 10,600，得到改变后的 30.72M 权重，并非原始 42M 模型。模型包几乎占满 16 MiB Flash，上游使用 **512 KiB 应用分区**，无法通过替换当前 MicroPython 模型文件完成安装。 |

文件大小来源：[doryiii 资产](https://github.com/doryiii/esp32-llm/tree/c6c647f7bfbb74efd2bbfd9a1725da4a903589f4/spiffs_data)、[NanoMind 资产](https://github.com/imFARSI/NanoMind-S3/tree/c8a4f8e1c325fe7a4c3a99aacfe54289090fe9aa)、[esp32-ai 下载校验值](https://github.com/slvDev/esp32-ai/blob/52ebcbbd905270592c1d415efd1128d04d0fa365/scripts/fetch_model.sh)和 [record42 README](https://github.com/JARACH-209/esp32-30.7M/blob/0ee74541ac7a0e7e4ebe1bc85ade2717abb7ec89/README.md)。固定版本链接用于保留本文依据，不代表 `scripts/prepare.py` 会下载这些候选。

## 3. 格式兼容和模型能力是不同约束

`.bin` 后缀不能证明格式兼容。GGUF、Hugging Face Transformers checkpoint 和 llama2.c 导出可能使用不同文件头、布局、分词器和算子；同样标为 INT4 的文件，也可能有不同的分组、缩放、打包和混合精度规则。运行时必须明确支持对应格式；文件足够小不代表 ESP32-S3 就能运行桌面推理程序。

当前 [native/module.c](../native/module.c)检查固定 FP32 文件大小、模型配置、对齐和状态长度；[device/llm.py](../device/llm.py)与 [device/api.py](../device/api.py)也包含分词器及模型元数据假设。将其他权重改名为 `stories260K.bin`、只修改 API 的 `model` 名称或放松文件头检查，都不能实现新模型支持。

参数量也不决定任务适用性。故事模型是英文续写模型，Barista 是狭窄领域的英文问答模型。上述资料均未证明这块板子具有通用中文聊天、编码代理或工具调用能力。HTTP 格式兼容能暴露模型输出，但无法补足训练中不存在的能力。

## 4. 移植与验收流程

1. **确定任务与延迟目标。** 按实际训练任务和语言覆盖选择模型；评估新候选时保留 260K 作为已验证基线。
2. **固定完整资产。** 记录权重及分词器版本、字节数、SHA-256、转换命令和上游许可证；需要时包含词表映射及聊天模板。
3. **核算完整资源。** 包含量化缩放、KV 精度及上下文、分词器、激活、网络、shell 和固件分区；测量连续可分配 RAM，不能将标称 PSRAM 全部分给权重。
4. **实现匹配的后端。** 移植解析器、算子、量化内核、分词、解码及停止逻辑。采用 Flash 映射或 ESP-IDF/Arduino 替代固件时，还需更新启动、部署和恢复方案。
5. **验证数值行为。** 对照同一导出模型的独立主机实现，比较 token ID 与 logits；量化路径需明确数值和质量容差，不能要求与不同 FP32 权重逐位一致。
6. **集成并验证服务。** 更新元数据和 token 限制，测试 JSON/SSE、鉴权、停止词、取消、重复请求、堆余量、shell 响应和重启恢复；在开启网络时测量首 token 与端到端吞吐。
7. **发布逐模型支持记录。** 完成真实设备验证后，再加入清单、部署方法、基准条件及中英文文档。更换固件应先执行[备份与恢复流程](installation.zh-CN.md)。

当前下载和部署脚本仍只安装已验证的 260K 后端。本文补充选型资料，不改变正在运行的板子，也不表示服务已支持多模型切换。
