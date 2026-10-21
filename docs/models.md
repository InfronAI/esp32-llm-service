# Model choices and ESP32-S3 constraints

**English** | [简体中文](models.zh-CN.md)

[Documentation index](README.md) · [Project README](../README.md) · [Architecture](architecture.md)

**ESP32-S3 is not limited to TinyStories 260K.** Public projects report larger models on a single 16 MB Flash / 8 MB PSRAM board by combining quantization, Flash mapping, specialized architectures, and small native runtimes. The limit depends on the whole implementation, not parameter count alone.

This guide was checked against upstream sources on **2026-10-21**. Only TinyStories 260K has been deployed and verified in this repository. Every other candidate below requires integration work or replacement firmware; none is currently selectable through this service's `model` field. Upstream measurements have not been reproduced here.

## 1. Hardware budget

The verified board has two Xtensa LX7 cores running at 240 MHz, 512 KB of internal SRAM, 8 MB Octal PSRAM, and 16 MB Flash. Internal SRAM must also serve firmware and networking. PSRAM provides more capacity but is accessed through an external-memory interface and cache. ESP-IDF's documented 32 MB external-memory **virtual address range** does not mean this board has 32 MB of physical RAM. See the [ESP32-S3 datasheet](https://www.espressif.com/sites/default/files/documentation/esp32-s3_datasheet_en.pdf) and [ESP-IDF external RAM guide](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-guides/external-ram.html).

| Constraint | What must fit or be implemented |
| --- | --- |
| Flash capacity and partitions | Bootloader, partition table, firmware, NVS, filesystem, model, and tokenizer. A 16 MB chip does not provide 16 MB exclusively for weights. |
| Available RAM | Resident weights, KV cache, activations, logits, tokenizer, MicroPython heap, networking, thread stacks, and allocation headroom. Measure free memory and the largest contiguous allocation after service startup. |
| Context length | Longer attention history grows KV storage and per-token attention work. Prompt and generated tokens both consume context. |
| Vocabulary | Embedding/output matrices, logits, and tokenizer tables can dominate a small model; a large multilingual vocabulary is not free. |
| Compute and bandwidth | Native kernels, Flash/PSRAM access, dequantization, and scheduling determine throughput. A second core does not guarantee twice the service throughput. |
| Model/runtime compatibility | Tensor layout, quantization format, operators, tokenizer, RoPE, attention heads, tied output weights, and special tokens must match the engine. |
| Application budget | Wi-Fi, HTTP/SSE, authentication, and the shell consume resources absent from some serial-only demos. Recheck stability with the complete service running. |

### Weight storage is only the starting point

For `N` stored parameters at `b` bits per weight:

```text
weight_bytes ≈ N × b / 8 + scales + zero_points + headers + alignment
RAM_needed = resident_weights + KV_cache + activations + logits
             + tokenizer + runtime/network/stacks + allocation_headroom
Flash_needed = firmware/partitions/filesystem + model_assets + other_files
```

The following are **raw weight lower bounds**, in decimal MB (`1 MB = 1,000,000 bytes`). They exclude every overhead above. `1 MiB = 1,048,576 bytes`; byte counts in the candidate table avoid upstream MB/MiB ambiguity.

| Parameters | FP32 | INT8 | INT4 |
| --- | ---: | ---: | ---: |
| 1M | 4 MB | 1 MB | 0.5 MB |
| 3M | 12 MB | 3 MB | 1.5 MB |
| 15M | 60 MB | 15 MB | 7.5 MB |
| 30M | 120 MB | 30 MB | 15 MB |
| 100M | 400 MB | 100 MB | 50 MB |
| 1B | 4,000 MB | 1,000 MB | 500 MB |

These calculations explain why ordinary 100M or billion-parameter INT4 checkpoints cannot be stored wholly in this board's 16 MB Flash or loaded wholly into its 8 MB PSRAM. External storage, host offloading, or multiple boards would change the system assumptions. The reported 30.72M example below is a highly constrained implementation, not a general 30M compatibility guarantee.

### KV cache can be larger than the remaining RAM

For conventional full attention with MHA or GQA:

```text
KV_bytes = 2 × layers × context_tokens × kv_heads × head_dim × bytes_per_KV_element
```

The factor 2 accounts for keys and values. In the current 260K model, `layers=5`, `context=512`, `kv_heads=4`, `head_dim=8`, and FP32 cache elements use 4 bytes:

```text
2 × 5 × 512 × 4 × 8 × 4 = 655,360 bytes = 640 KiB
```

The full native state is **676,192 bytes**, including that cache and other buffers. The weight file adds **1,056,540 bytes**, before the Python tokenizer, HTTP, and shell allocations. Doubling context doubles this KV allocation. Quantizing weights to INT4 does **not** automatically quantize the KV cache; cache precision requires separate implementation and validation. These current-model values are traceable to [native/module.c](../native/module.c), [native/transformer.c](../native/transformer.c), and the [architecture guide](architecture.md).

### Flash mapping and model architecture change the tradeoffs

A native runtime can map a model partition and read weights from Flash, retaining only working buffers or selected tensors in RAM. This avoids a full RAM copy, but still consumes Flash capacity, cache, and bandwidth. It requires a suitable partition layout and runtime; the current MicroPython loader reads the full weight file into a Python-owned buffer.

Per-Layer Embeddings (**PLE**) use large learned lookup tables accessed by token, alongside a much smaller Transformer core. Consequently, a 28.9M PLE model need not perform the same work as a dense 28.9M Transformer. The [esp32-ai design and results](https://github.com/slvDev/esp32-ai/blob/52ebcbbd905270592c1d415efd1128d04d0fa365/RESULTS.md) describe this distinction. PLE models listed here are independently trained models; they are not the billion-parameter Gemma 3n checkpoint.

## 2. Candidate models and repositories

**Included** means tested with this project's MicroPython service. **Upstream only** means the linked author reports ESP32-S3 execution; this repository has not integrated or tested it. Sizes below describe deployment weight files, not total RAM or total installation size.

| Model / intended use | Deployment weights | Evidence and context | Model source | ESP32 runtime |
| --- | --- | --- | --- | --- |
| **TinyStories 260K**, English story continuation | FP32; **1,056,540 B** | **Included**; 512-token context; about **29.88 tokens/s** in the recorded 32-token API run | [260K model family](https://huggingface.co/karpathy/tinyllamas/tree/main/stories260K); exact asset revision and hashes in [manifest](../models/manifest.json) | [This project](../native/transformer.c), adapted from [doryiii/esp32-llm](https://github.com/doryiii/esp32-llm/tree/c6c647f7bfbb74efd2bbfd9a1725da4a903589f4) |
| **TinyStories 3.3M**, English story continuation | INT8; **3,352,576 B**, `stories3M-q80.bin`; paired with `tok4096.bin` | **Upstream only**; author reports about **12 tokens/s** with 8 MB PSRAM | [Quantized assets](https://github.com/doryiii/esp32-llm/tree/c6c647f7bfbb74efd2bbfd9a1725da4a903589f4/spiffs_data) | [INT8 engine `llm8.c`](https://github.com/doryiii/esp32-llm/blob/c6c647f7bfbb74efd2bbfd9a1725da4a903589f4/main/llm8.c) and its ESP-IDF firmware |
| **Barista 8.9M**, English espresso troubleshooting | INT4 PLE; **4,600,186 B** | **Upstream only**; 128-token context; **16.60 output pieces/s**, serial-only benchmark | [slvDev/esp32-ai-barista](https://huggingface.co/slvDev/esp32-ai-barista) | [esp32-ai Barista firmware](https://github.com/slvDev/esp32-ai/tree/52ebcbbd905270592c1d415efd1128d04d0fa365/firmware/esp32_barista) |
| **Stories15M / 15.2M**, English story continuation | INT4; **7,857,568 B** (about 7.49 MiB) | **Upstream only**; 256-token context; author reports about **2.54–2.96 tokens/s** | [Base `stories15M.bin`](https://huggingface.co/karpathy/tinyllamas/tree/main); [INT4 export and weights](https://github.com/imFARSI/NanoMind-S3/tree/c8a4f8e1c325fe7a4c3a99aacfe54289090fe9aa) | [NanoMind-S3 ESP-IDF firmware](https://github.com/imFARSI/NanoMind-S3/tree/c8a4f8e1c325fe7a4c3a99aacfe54289090fe9aa/firmware), dual-core and Flash-mapped |
| **esp32-ai TinyStories 28.9M**, English story continuation | INT4 PLE; **14,912,348 B** | **Upstream only**; 256-token context; model card reports **9.88 tokens/s** over serial | [slvDev/esp32-ai-tinystories](https://huggingface.co/slvDev/esp32-ai-tinystories) | [esp32-ai TinyStories firmware](https://github.com/slvDev/esp32-ai/tree/52ebcbbd905270592c1d415efd1128d04d0fa365/firmware/esp32_tinystories) |
| **record42 / 30.72M**, English story continuation | INT4, group 128, FP16 scales; **16,101,008 B** (about 15.36 MiB) | **Upstream only**; 192-token context; author reports about **0.95 tokens/s** end to end | [Base `stories42M.bin`](https://huggingface.co/karpathy/tinyllamas/tree/main); trimmed and packed with the [record42 project](https://github.com/JARACH-209/esp32-30.7M/tree/0ee74541ac7a0e7e4ebe1bc85ade2717abb7ec89) | [esp32-30.7M](https://github.com/JARACH-209/esp32-30.7M/tree/0ee74541ac7a0e7e4ebe1bc85ade2717abb7ec89), custom Flash layout and partial PSRAM staging |

**Do not rank these speeds as a controlled benchmark.** Firmware, context, prompt length, output vocabulary, sampling, and timing boundaries differ. This project's rate includes prompt processing and sampling, while the Mac HTTP round trip is measured separately. Barista emits restricted output classes (“pieces”), not the same tokens as TinyStories. See [our validation](validation.md), [Barista's benchmark](https://github.com/slvDev/esp32-ai/blob/52ebcbbd905270592c1d415efd1128d04d0fa365/firmware/esp32_barista/README.md), and the linked upstream READMEs.

### What each alternative would require

| Candidate | Required changes and important limitations |
| --- | --- |
| TinyStories 3.3M | Port or adopt the INT8 engine, its quantized checkpoint parser, and 4096-entry tokenizer. Recompute state allocation and reserve memory for Wi-Fi/shell. Its upstream lineage makes it a useful first integration experiment; this is an engineering assessment, not a completed port. |
| Barista 8.9M | Use the PLE engine plus `tokenizer.json`, `vocab.json`, and `layout.json`. Input and output alphabets differ, so output classes must map back to input token IDs. It accepts ASCII espresso questions with a restricted output vocabulary; it is not a general assistant or a Chinese model. |
| Stories15M | Use the NanoMind quantization/export format, Flash mapping, and dual-core runtime. Its 256-token FP32 KV cache alone is **3,538,944 B**, calculated as `2 × 6 × 256 × 6 × 48 × 4`. A serial demo's memory budget must be rechecked after adding network services. |
| esp32-ai TinyStories 28.9M | Adopt PLE operators, tokenizer assets, tensor staging, and a suitable Flash partition. Roughly 25M parameters are lookup tables, while the dense core is about 0.56M. It is a story model without chat instruction training. |
| record42 / 30.72M | The original Stories42M vocabulary is trimmed from 32,000 to 10,600; this is a changed 30.72M checkpoint, not the unmodified 42M model. The model pack nearly fills 16 MiB Flash, and upstream uses a **512 KiB application partition**. This is not a file swap into the current MicroPython installation. |

Sources for artifact sizes: [doryiii assets](https://github.com/doryiii/esp32-llm/tree/c6c647f7bfbb74efd2bbfd9a1725da4a903589f4/spiffs_data), [NanoMind assets](https://github.com/imFARSI/NanoMind-S3/tree/c8a4f8e1c325fe7a4c3a99aacfe54289090fe9aa), [esp32-ai download pins](https://github.com/slvDev/esp32-ai/blob/52ebcbbd905270592c1d415efd1128d04d0fa365/scripts/fetch_model.sh), and the [record42 README](https://github.com/JARACH-209/esp32-30.7M/blob/0ee74541ac7a0e7e4ebe1bc85ade2717abb7ec89/README.md). These pinned links preserve the source snapshots used for this guide; they are not additional downloads performed by `scripts/prepare.py`.

## 3. Formats and capabilities are separate constraints

A `.bin` extension does not identify a compatible format. A GGUF file, a Hugging Face Transformers checkpoint, and a llama2.c export may contain different headers, layouts, tokenizers, and operators. Likewise, two “INT4” files may use different grouping, scales, packing, or mixed-precision tensors. The engine must explicitly implement the chosen format. ESP32-S3 does not run a desktop inference runtime merely because the weight file is small enough.

Current [native/module.c](../native/module.c) validates a fixed FP32 file size, configuration, alignment, and state buffer. [device/llm.py](../device/llm.py) and [device/api.py](../device/api.py) also carry tokenizer and model metadata assumptions. Renaming another checkpoint to `stories260K.bin`, changing only the API `model` name, or loosening the header check cannot add support.

Model size also does not determine task suitability. The story models are English continuation models; Barista is a narrow English question-answering model. None of the cited evidence establishes general Chinese chat, coding-agent performance, or tool calling on this board. HTTP compatibility can expose a model's output, but cannot supply capabilities absent from its training.

## 4. Integration and acceptance checklist

1. **Choose the task and latency target.** Select a model for its actual training and language coverage. Preserve the current 260K backend as the verified reference while evaluating a candidate.
2. **Freeze the artifact set.** Record model and tokenizer revisions, byte sizes, SHA-256 values, conversion command, and upstream licenses. Include vocabulary mappings or chat templates where required.
3. **Calculate the complete budget.** Include scales, KV precision/context, tokenizer, activations, networking, shell, and firmware partitions. Measure available contiguous RAM; do not allocate all nominal PSRAM to weights.
4. **Implement a matching backend.** Port the parser, operators, quantization kernels, tokenization, decoding, and termination logic. Flash mapping or an ESP-IDF/Arduino replacement firmware also requires a revised boot, deployment, and recovery plan.
5. **Validate numerical behavior.** Compare tokenizer IDs and logits with an independent host implementation of the same exported model. Quantized paths need a stated numerical/quality tolerance; do not demand exact equality to unrelated FP32 weights.
6. **Integrate and verify the service.** Update metadata and token limits, then test JSON/SSE, authentication, stop strings, cancellation, repeated requests, heap headroom, shell responsiveness, and restart recovery. Measure first-token latency and end-to-end throughput with networking enabled.
7. **Publish a model-specific support record.** Add the manifest, deployment instructions, benchmark conditions, and English/Chinese documentation only after actual device verification. Changing firmware starts with the [backup and recovery procedure](installation.md).

The current download/deployment scripts continue to install the verified 260K backend only. This document expands the selection guidance without changing the running board or claiming multi-model support.
