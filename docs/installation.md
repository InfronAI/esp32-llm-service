# 安装、配置与恢复

前提是完成[开发环境](setup.md)。USB 维护通过串口访问物理板子，维护期间会中断现有网络应用。

## 1. 找到目标板

```sh
.venv/bin/python -m serial.tools.list_ports -v
export ESP32_PORT=/dev/cu.usbmodemXXXX
.venv/bin/python -m esptool --chip esp32s3 --port "$ESP32_PORT" flash-id
```

原生 USB 的 Espressif VID 为 `303A`。不要根据文档里的示例端口盲选设备。部署脚本可自动选择唯一 Espressif USB 设备；连接多个设备时要求显式 `--port`。USB-UART 桥接板可能使用其他 VID，需手动指定。

不能进入 ROM 下载器时，按住 BOOT，按下并松开 RESET，再松开 BOOT。重新列出串口，因为 ROM 和应用模式的端口可能不同。

本项目首次安装的旧固件也可通过以下 1200-baud touch 进入下载模式；它依赖旧固件支持，不是所有板子的通用方法：

```sh
.venv/bin/python - "$ESP32_PORT" <<'PY'
import sys, time, serial
with serial.Serial(sys.argv[1], 1200) as port:
    port.dtr = False
    time.sleep(0.2)
PY
```

## 2. 备份原固件

确认 Flash 为 16 MB 后，备份整个地址空间：

```sh
mkdir -p backups
.venv/bin/python -m esptool --chip esp32s3 --port "$ESP32_PORT" --baud 921600 --after watchdog-reset read-flash 0 0x1000000 backups/original.bin
shasum -a 256 backups/original.bin > backups/original.bin.sha256
```

其他容量要调整长度。备份可能含设备原有凭据，保存在被忽略的 `backups/` 内。本项目实际首次备份文件名包含日期；仓库教程使用 `original.bin` 作为新安装的示例名。

## 3. 安装固件

首先运行 `.venv/bin/python scripts/prepare.py --only firmware`。清单绑定版本、文件名及 SHA-256。

**以下操作擦除已有固件和用户文件。正常代码更新使用部署脚本，无需执行这一段。**

```sh
.venv/bin/python -m esptool --chip esp32s3 --port "$ESP32_PORT" --after no-reset erase-flash
.venv/bin/python -m esptool --chip esp32s3 --port "$ESP32_PORT" --baud 921600 --after watchdog-reset write-flash 0 firmware/ESP32_GENERIC_S3-SPIRAM_OCT-20260824-v1.29.0.bin
.venv/bin/python -m serial.tools.list_ports -v
```

在已验证板子上，刷写后普通 reset 曾停留在下载模式，`watchdog-reset` 可正常启动。若串口发生变化，更新 `ESP32_PORT`。

检查 MicroPython 和 PSRAM：

```sh
.venv/bin/mpremote connect "$ESP32_PORT" exec 'import sys, gc, os; print(sys.version); print(os.uname()); gc.collect(); print(gc.mem_free())'
```

8 MB PSRAM 板在未加载应用时应能看到数 MB 的 Python 堆；本项目初始堆约 8.3 MB。明显不足时先核对 PSRAM 型号与固件变体。

## 4. 配置与模型

```sh
.venv/bin/python scripts/prepare.py
.venv/bin/python scripts/build_native.py
.venv/bin/python scripts/configure.py --ssid 'YOUR_2.4G_WIFI'
```

Wi-Fi 密码交互输入；其余凭据随机生成。不要把密码作为 shell 命令参数传入。新安装配置生成器不覆盖已有配置，修改现有板子应保留并编辑原文件。

### 配置字段

| `device/settings.json` 字段 | 含义 |
| --- | --- |
| `ssid` / `wifi_password` | 板子创建的 WPA2 热点名称和密码 |
| `sta_ssid` / `sta_password` | 板子接入的 2.4 GHz Wi-Fi |
| `user` | shell 登录名，生成器默认 `esp32` |
| `salt` / `password_hash` | shell 的随机盐及 SHA-256(salt + password) |
| `port` | shell TCP 端口，默认 23 |
| `api_key` | HTTP Bearer 密钥 |
| `api_port` | HTTP 端口，默认 8000 |

热点固定为 `192.168.4.1/24`；STA 使用 DHCP。代码将网络主机名设为 `esp32-llm`，但不保证路由器提供同名 DNS/mDNS 解析，因此示例采用 IP。

shell 密码散列是简化认证机制，缺少密码学 KDF 的慢哈希保护。Wi-Fi 密码和 API Key 需要明文供设备使用。已认证 shell 能执行任意 MicroPython，具备整板管理能力。使用可信局域网，不要直接端口映射到公网。

## 5. 部署

```sh
.venv/bin/python scripts/deploy.py --port "$ESP32_PORT" --models --settings
```

写入清单：`boot.py`、`net.py`、`shell.py`、`llm.py`、`api.py`、`tinyllm_native.mpy`、两个模型文件、`settings.json`，最后写入 `main.py`。每个文件在板上做 SHA-256 校验；相同内容跳过。脚本设置 RTC UTC 后重启。

这是逐文件更新，不是双分区 OTA；传输中断时可能需要通过 USB 重跑部署。用户 `/home` 文件保留。`device/welcome.txt` 是可选说明文件，不影响服务启动。

## 6. 获取地址与验证

可直连板子热点，再运行 `./connect.command`；输入 `reports/access.json` 中的用户名和 shell 密码，执行 `ifconfig` 查看 LAN IP。也可从路由器 DHCP 列表获取地址。

```sh
.venv/bin/python scripts/configure.py --host-only 192.168.1.50
.venv/bin/python scripts/chat.py 'Once upon a time' --tokens 32
.venv/bin/python scripts/check_llm.py
```

`--host-only` 只修改 Mac 客户端文件，不重置密钥或 Wi-Fi。单次临时地址可用 `scripts/chat.py --url http://192.168.4.1:8000/v1`。

USB 日志可用 `mpremote connect "$ESP32_PORT" repl` 查看；按板上 RESET 观察启动，Ctrl-] 退出。进入 REPL 维护可能中断主程序，结束后执行 `mpremote connect "$ESP32_PORT" reset`。

## 7. 恢复备份

仅在确定要撤销当前系统时执行，恢复会覆盖整个 Flash，包括后来创建的文件：

```sh
shasum -a 256 -c backups/original.bin.sha256
.venv/bin/python -m esptool --chip esp32s3 --port "$ESP32_PORT" --baud 921600 --after watchdog-reset write-flash 0 backups/original.bin
```

先核对目标串口和备份校验结果。项目不包含个人设备的原始 Flash 备份。
