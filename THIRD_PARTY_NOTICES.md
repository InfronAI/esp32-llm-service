# Third-party sources and licenses

The repository's MIT license applies to its original project code and documentation. Upstream notices are retained; it does not relicense downloaded model weights, firmware, or toolchains.

| Component | Source / provenance | License and handling |
| --- | --- | --- |
| Transformer C implementation | [doryiii/esp32-llm](https://github.com/doryiii/esp32-llm/tree/c6c647f7bfbb74efd2bbfd9a1725da4a903589f4), `main/llm.c` and `main/llm.h`; derived from karpathy/llama2.c | MIT notices for Andrej (2023) and Dory (2026) retained in `native/transformer.c` and `.h` |
| Independent reference | [karpathy/llama2.c/run.c](https://github.com/karpathy/llama2.c/blob/master/run.c), retrieved 2026-10-21; vendored as `tests/reference_run.c` | [MIT license](tests/LICENSE.llama2.c) |
| MicroPython firmware and build sources | [MicroPython](https://github.com/micropython/micropython/tree/v1.29.0), exact commit in `firmware/manifest.json` | [MicroPython license](https://github.com/micropython/micropython/blob/v1.29.0/LICENSE); downloaded into ignored local paths |
| TinyStories 260K weights and tokenizer | Fixed doryiii/esp32-llm commit in `models/manifest.json`; upstream model family [karpathy/tinyllamas](https://huggingface.co/karpathy/tinyllamas) | Downloaded with SHA-256 verification; consult upstream model terms. Weights are not included in this source repository |
| Xtensa compiler and runtime | Espressif Arduino ESP32 core 3.3.8 / esp-x32 2601 | Installed separately; respective GCC runtime / C library terms apply. Compiled `.mpy` files are local build artifacts |
| Python host tools | Pinned packages in `requirements.txt` | Installed separately, under their respective package licenses |

The native adaptation changes allocation ownership, validates a fixed checkpoint layout, uses a portable four-accumulator matrix multiplication, and exposes two MicroPython native functions. The independent reference is used for correctness checks rather than as the board implementation.
