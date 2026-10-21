# Development platform and environment setup

**English** | [简体中文](setup.zh-CN.md)

This project has been built, flashed over USB, and called over LAN from an Apple Silicon Mac. The host CI template targets Linux for Python tools and the C reference implementation, but is not enabled. Linux USB deployment has no physical-device validation record in this project.

## Hardware

Start with the [hardware shopping and connection guide](hardware.md). You need an ESP32-S3, USB data cable, stable power, and a 2.4 GHz WPA2 network. The verified configuration is 16 MB Flash and 8 MB Octal PSRAM. A charging cable may lack data wires; if the port list only contains Bluetooth or debug-console entries, check the cable and connector.

`esptool flash-id` checks Flash capacity. Use module markings, boot information, and actual memory availability to identify PSRAM. Octal PSRAM requires the `ESP32_GENERIC_S3-SPIRAM_OCT` firmware. The [official MicroPython download page](https://micropython.org/download/ESP32_GENERIC_S3/) distinguishes the standard and Octal SPIRAM variants.

## Mac tools

After installing [Homebrew](https://brew.sh/), run:

```sh
xcode-select --install
brew install python@3.11 git arduino-cli
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Xcode Command Line Tools supply `cc` and `make`. Keep an existing installation if already available.

| Dependency | Purpose in this project |
| --- | --- |
| esptool 5.6.0 | ROM download mode, backup, erase, and flashing |
| mpremote 1.29.0 / pyserial | USB REPL, file transfer, and device tests |
| ar 1.0.1 / pyelftools 0.33 | MicroPython native module linking |
| openai 3.35.1 / httpx2 2.16.0 | Official SDK compatibility checks and streaming examples |
| Arduino ESP32 core 3.3.8 | Xtensa ESP32-S3 GCC cross compiler |

```sh
arduino-cli core update-index --additional-urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli core install esp32:esp32@3.3.8 --additional-urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli core list
```

The pinned core version reproduces the verified toolchain. The [Arduino CLI documentation](https://docs.arduino.cc/arduino-cli/commands-reference/arduino-cli_core_install) describes `PACKAGER:ARCH@VERSION` and `--additional-urls`.

The default compiler location on macOS resembles:

```text
~/Library/Arduino15/packages/esp32/tools/esp-x32/2601/bin/xtensa-esp32s3-elf-gcc
```

The build script discovers this path automatically. For custom paths, use `ESP32_CROSS` to set the compiler prefix. No Arduino IDE GUI or sketch is required for this project.

## Downloads and integrity checks

```sh
.venv/bin/python scripts/prepare.py
.venv/bin/python scripts/prepare.py --offline
.venv/bin/python scripts/build_native.py
```

Use `--only firmware|models|source` to prepare one asset group. Existing verified assets are reused. Downloads go to temporary files and replace the destination only after SHA-256 verification; failures preserve the previous file. The MicroPython checkout must match the pinned commit and have no tracked modifications.

Generated `third_party/`, model `.bin` files, firmware `.bin` files, `.venv/`, and native `.mpy` files are ignored by Git. Source manifests and download scripts are versioned.

## Networking and proxies

Dependency downloads use the host's normal network configuration. Bypass proxies when calling the ESP32: use curl `--noproxy '*'` or SDK `DefaultHttpxClient(trust_env=False)`. Campus or corporate client isolation may prevent communication even on the same SSID; use the board's direct AP to isolate network problems.

ESP32-S3 Wi-Fi uses 2.4 GHz, not 5 GHz. Copy the exact broadcast SSID, including spaces, case, and suffixes.

## Check the environment

```sh
.venv/bin/python -m pip check
.venv/bin/python -m serial.tools.list_ports -v
.venv/bin/python scripts/check_native.py --reference-only
```

The last command compiles and executes the independent C reference on the Mac without connecting to or modifying the ESP32. Continue with [installation](installation.md).
