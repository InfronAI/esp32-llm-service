# 原生推理模块构建

完整首次安装见 [README](README.md)，开发机准备见 [docs/setup.md](docs/setup.md)。

```sh
.venv/bin/python scripts/prepare.py
.venv/bin/python scripts/build_native.py
```

构建脚本查找 `ESP32_CROSS`、PATH 中的 `xtensa-esp32s3-elf-gcc`，或 macOS/Linux Arduino 数据目录中的 `esp-x32/2601`。其他目录可显式指定：

```sh
ESP32_CROSS=/path/to/bin/xtensa-esp32s3-elf- .venv/bin/python scripts/build_native.py
```

注意前缀最后的连字符。`scripts/build_native.sh` 是同一个构建入口的 shell 包装。

## 固定版本

| 部件 | 固定值 |
| --- | --- |
| MicroPython | v1.29.0，commit `0fd6c573ea815774668bbb16b8e197c8822368b2` |
| 模型及原始内核 | doryiii/esp32-llm，commit `c6c647f7bfbb74efd2bbfd9a1725da4a903589f4` |
| Arduino ESP32 core | 3.3.8，使用其 `esp-x32/2601` 工具链 |
| 模块格式 | Xtensa windowed ABI，MicroPython native `.mpy` |
| 编译参数 | `-O3 -ffp-contract=off -fno-math-errno` |
| 动态链接选项 | `ARCH=xtensawin`、`LINK_RUNTIME=1` |

`LINK_RUNTIME=1` 链入浮点数学运行库；`ar` 和 `pyelftools` 是 MicroPython 动态链接工具的 Python 依赖。不需要构建整个 MicroPython 固件。

源码中 `native/module.c` 严格检查权重头、缓冲区大小、对齐、token 范围和上下文位置；当前只接受本项目 260K 布局。`native/transformer.c` 使用四路浮点累加的矩阵乘法，沿用 llama2.c 的 RMSNorm、RoPE、注意力、SwiGLU 和分类器。模型状态由 Python 持有，保证 C 调用期间缓冲区有效。

产物 `native/tinyllm_native.mpy` 属于本地构建文件，不进入 Git。升级固件或编译器后要重建并在板上重新验证，不能假定 `.mpy` 跨 ABI 通用。

## 验证

主机参考验证不需要板子：

```sh
.venv/bin/python scripts/check_native.py --reference-only
```

板上验证会暂停网络服务，测试后脚本自动重启：

```sh
.venv/bin/python scripts/check_native.py --port /dev/cu.usbmodemXXXX
```

它比较独立 `tests/reference_run.c` 的分词、32 个贪心 token、首步 512 维 logits 和权重 SHA-256。允许 logits 最大绝对误差小于 `1e-4`。当前实测为约 `8.45e-6`。结果写入被忽略的 `reports/`。

发布前在主机运行：

```sh
.venv/bin/python -m compileall -q device scripts tests
.venv/bin/python -m unittest discover -s tests -p 'test_host.py'
.venv/bin/python scripts/check_repo.py
```
