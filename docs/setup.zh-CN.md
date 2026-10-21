# 开发平台与环境准备

[English](setup.md) | **简体中文**

本项目已在 Apple Silicon Mac 上完成构建、USB 烧录和 LAN 调用。主机 CI 模板面向 Linux，用于验证 Python 工具和 C 参考实现，当前尚未启用；Linux USB 部署没有本项目的实机验证记录。

## 硬件

先阅读[硬件采购与连接教程](hardware.zh-CN.md)。准备 ESP32-S3、USB 数据线、稳定供电和 2.4 GHz WPA2 网络。已验证板卡为 16 MB Flash、8 MB Octal PSRAM。USB 供电线不一定支持数据；串口列表只有蓝牙或 debug-console 时先检查线材和 USB 接口。

`esptool flash-id` 可核对 Flash 容量；板卡标识、启动信息和实际内存用于确认 PSRAM 类型。Octal PSRAM 使用 `ESP32_GENERIC_S3-SPIRAM_OCT` 固件。[MicroPython 官方下载页](https://micropython.org/download/ESP32_GENERIC_S3/)明确区分普通与 Octal SPIRAM 变体。

## Mac 工具

安装 [Homebrew](https://brew.sh/) 后执行：

```sh
xcode-select --install
brew install python@3.11 git arduino-cli
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Xcode Command Line Tools 提供 `cc` 和 `make`；若已安装，保留现有版本即可。

| 依赖 | 本项目用途 |
| --- | --- |
| esptool 5.6.0 | ROM 下载模式检测、备份、擦除和刷写 |
| mpremote 1.29.0 / pyserial | USB REPL、传文件、执行板上测试 |
| ar 1.0.1 / pyelftools 0.33 | MicroPython 原生模块链接 |
| openai 3.35.1 / httpx2 2.16.0 | 官方 SDK 兼容性测试和流式示例 |
| Arduino ESP32 core 3.3.8 | 提供 Xtensa ESP32-S3 GCC 交叉编译器 |

```sh
arduino-cli core update-index --additional-urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli core install esp32:esp32@3.3.8 --additional-urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli core list
```

使用固定 core 版本，以重现已验证工具链。[Arduino CLI 官方文档](https://docs.arduino.cc/arduino-cli/commands-reference/arduino-cli_core_install)说明 `PACKAGER:ARCH@VERSION` 和 `--additional-urls` 用法。

Mac 默认编译器路径形如：

```text
~/Library/Arduino15/packages/esp32/tools/esp-x32/2601/bin/xtensa-esp32s3-elf-gcc
```

构建脚本自动发现此路径；自定义安装位置可通过 `ESP32_CROSS` 指定编译器前缀。这里不需要 Arduino IDE GUI，也不需要编写 Arduino sketch。

## 下载与校验

```sh
.venv/bin/python scripts/prepare.py
.venv/bin/python scripts/prepare.py --offline
.venv/bin/python scripts/build_native.py
```

`--only firmware|models|source` 可单独准备一类资源。现有资源校验通过时直接复用；下载先写临时文件，SHA-256 正确后替换目标文件，失败保留原文件。MicroPython checkout 要与固定 commit 一致且没有 tracked 修改。

生成目录 `third_party/`、模型 `.bin`、固件 `.bin`、`.venv/` 和原生 `.mpy` 都被 Git 忽略，源码清单和下载器进入仓库。

## 网络与代理

下载依赖使用主机正常网络环境。调用 ESP32 时绕过代理：curl 使用 `--noproxy '*'`，SDK 使用 `DefaultHttpxClient(trust_env=False)`。若校园/企业网络启用了客户端隔离，即使同一 SSID 也可能无法直连；可改用板子热点验证。

ESP32-S3 不支持 5 GHz Wi-Fi。配置 SSID 要包含准确空格、大小写和后缀，以实际 2.4 GHz 广播名称为准。

## 检查结果

```sh
.venv/bin/python -m pip check
.venv/bin/python -m serial.tools.list_ports -v
.venv/bin/python scripts/check_native.py --reference-only
```

最后一项在 Mac 编译并运行独立 C 参考实现，不会连接或修改 ESP32。后续操作见[安装文档](installation.zh-CN.md)。
