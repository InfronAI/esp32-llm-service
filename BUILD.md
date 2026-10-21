# Build the native inference module

**English** | [简体中文](BUILD.zh-CN.md)

See the [README](README.md) for a complete installation and [setup guide](docs/setup.md) for host tools.

```sh
.venv/bin/python scripts/prepare.py
.venv/bin/python scripts/build_native.py
```

The build script checks `ESP32_CROSS`, `xtensa-esp32s3-elf-gcc` on PATH, and `esp-x32/2601` in the macOS/Linux Arduino data directories. For another installation path, set the compiler prefix explicitly:

```sh
ESP32_CROSS=/path/to/bin/xtensa-esp32s3-elf- .venv/bin/python scripts/build_native.py
```

Keep the trailing hyphen in the prefix. `scripts/build_native.sh` wraps the same build entry point.

## Pinned versions

| Component | Pinned value |
| --- | --- |
| MicroPython | v1.29.0, commit `0fd6c573ea815774668bbb16b8e197c8822368b2` |
| Model and original kernel | doryiii/esp32-llm, commit `c6c647f7bfbb74efd2bbfd9a1725da4a903589f4` |
| Arduino ESP32 core | 3.3.8, supplying the `esp-x32/2601` toolchain |
| Module format | Xtensa windowed ABI, MicroPython native `.mpy` |
| Compiler flags | `-O3 -ffp-contract=off -fno-math-errno` |
| Dynamic linking | `ARCH=xtensawin`, `LINK_RUNTIME=1` |

`LINK_RUNTIME=1` links the floating-point math runtime. `ar` and `pyelftools` are Python dependencies of MicroPython's dynamic linking tools. Building the entire MicroPython firmware is unnecessary.

`native/module.c` checks the weight header, buffer size, alignment, token range, and context position. It currently accepts only the project's fixed 260K layout. `native/transformer.c` uses matrix multiplication with four floating-point accumulators and retains llama2.c's RMSNorm, RoPE, attention, SwiGLU, and classifier. Python owns model state so buffers remain valid during C calls.

The output, `native/tinyllm_native.mpy`, is a local build artifact excluded from Git. Rebuild and revalidate on the board after changing firmware or compiler versions; `.mpy` files are not universally portable across ABIs.

## Verification

The host reference check does not require a board:

```sh
.venv/bin/python scripts/check_native.py --reference-only
```

The device check pauses network services and automatically restarts the board afterward:

```sh
.venv/bin/python scripts/check_native.py --port /dev/cu.usbmodemXXXX
```

It compares tokenization, 32 greedy output tokens, the first 512-element logit vector, and weight SHA-256 against the independent `tests/reference_run.c`. Maximum absolute logit error must be below `1e-4`; the recorded result is approximately `8.45e-6`. Reports are written to the ignored `reports/` directory.

Before publishing, run the host checks:

```sh
.venv/bin/python -m compileall -q device scripts tests
.venv/bin/python -m unittest discover -s tests -p 'test_host.py'
.venv/bin/python scripts/check_repo.py
```
