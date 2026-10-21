# Installation, configuration, and recovery

**English** | [简体中文](installation.zh-CN.md)

Complete [environment setup](setup.md) first. USB maintenance accesses the physical board through its serial port and interrupts the running network application.

## 1. Identify the target board

```sh
.venv/bin/python -m serial.tools.list_ports -v
export ESP32_PORT=/dev/cu.usbmodemXXXX
.venv/bin/python -m esptool --chip esp32s3 --port "$ESP32_PORT" flash-id
```

Espressif's native USB VID is `303A`. Use the detected device, not a copied example port. Deployment auto-selects a single Espressif USB device; with multiple devices, pass `--port`. USB-UART bridges may have other VIDs and require explicit selection.

If ROM download mode is unavailable, hold BOOT, press and release RESET, then release BOOT. List ports again: ROM and application modes can use different device paths.

The board's previous firmware also supported this 1200-baud touch sequence. It depends on the existing firmware and is not universal:

```sh
.venv/bin/python - "$ESP32_PORT" <<'PY'
import sys, time, serial
with serial.Serial(sys.argv[1], 1200) as port:
    port.dtr = False
    time.sleep(0.2)
PY
```

## 2. Back up the original firmware

After confirming 16 MB Flash, back up the entire address space:

```sh
mkdir -p backups
.venv/bin/python -m esptool --chip esp32s3 --port "$ESP32_PORT" --baud 921600 --after watchdog-reset read-flash 0 0x1000000 backups/original.bin
shasum -a 256 backups/original.bin > backups/original.bin.sha256
```

Adjust the length for other capacities. Backups may contain existing device credentials; keep them in ignored `backups/`. The original project backup used a dated filename; this tutorial uses `original.bin` as an example for a new installation.

## 3. Install firmware

First run `.venv/bin/python scripts/prepare.py --only firmware`. The manifest pins the version, filename, and SHA-256.

**The following commands erase existing firmware and user files. Use the deployment script for routine code updates instead.**

```sh
.venv/bin/python -m esptool --chip esp32s3 --port "$ESP32_PORT" --after no-reset erase-flash
.venv/bin/python -m esptool --chip esp32s3 --port "$ESP32_PORT" --baud 921600 --after watchdog-reset write-flash 0 firmware/ESP32_GENERIC_S3-SPIRAM_OCT-20260824-v1.29.0.bin
.venv/bin/python -m serial.tools.list_ports -v
```

On the verified board, an ordinary reset sometimes left the chip in download mode; `watchdog-reset` booted correctly. Update `ESP32_PORT` if the port changes.

Check MicroPython and available memory:

```sh
.venv/bin/mpremote connect "$ESP32_PORT" exec 'import sys, gc, os; print(sys.version); print(os.uname()); gc.collect(); print(gc.mem_free())'
```

An 8 MB PSRAM board should expose several MB of Python heap before loading the application; the initial heap here was approximately 8.3 MB. If substantially less is available, check the PSRAM type and firmware variant.

## 4. Configure the device and prepare the model

```sh
.venv/bin/python scripts/prepare.py
.venv/bin/python scripts/build_native.py
.venv/bin/python scripts/configure.py --ssid 'YOUR_2.4G_WIFI'
```

Enter the Wi-Fi password interactively; other credentials are generated randomly. Avoid passwords in shell command arguments. The new-installation generator refuses to overwrite existing files. Preserve and edit existing configuration when maintaining an installed board.

### Configuration fields

| Field in `device/settings.json` | Meaning |
| --- | --- |
| `ssid` / `wifi_password` | Name and password of the board's WPA2 access point |
| `sta_ssid` / `sta_password` | 2.4 GHz Wi-Fi network joined by the board |
| `user` | Shell login name; generator default is `esp32` |
| `salt` / `password_hash` | Random salt and SHA-256(salt + password) for shell login |
| `port` | Shell TCP port, default 23 |
| `api_key` | HTTP Bearer key |
| `api_port` | HTTP port, default 8000 |

The AP uses `192.168.4.1/24`; STA uses DHCP. The code sets hostname `esp32-llm`, but DNS/mDNS resolution depends on the network and is not guaranteed, so examples use IP addresses.

Shell password hashing is a simple authentication mechanism without a slow password KDF. Wi-Fi passwords and the API key must remain available in plaintext to the device. An authenticated shell can execute arbitrary MicroPython and administer the board. Use a trusted LAN rather than public Internet port forwarding.

## 5. Deploy

```sh
.venv/bin/python scripts/deploy.py --port "$ESP32_PORT" --models --settings
```

Deployment writes `boot.py`, `net.py`, `shell.py`, `llm.py`, `api.py`, `tinyllm_native.mpy`, two model assets, and `settings.json`, then writes `main.py` last. Every file is SHA-256 checked on the board; unchanged content is skipped. The script sets the RTC to UTC and restarts the board.

This is a file-by-file update, not dual-partition OTA. An interrupted transfer may require rerunning USB deployment. User files in `/home` are preserved. `device/welcome.txt` is optional explanatory text and does not affect startup.

## 6. Find the address and verify

Connect directly to the board AP and run `./connect.command`. Log in using the username and shell password from `reports/access.json`, then run `ifconfig` to find the LAN IP. Alternatively, inspect the router's DHCP list.

```sh
.venv/bin/python scripts/configure.py --host-only 192.168.1.50
.venv/bin/python scripts/chat.py 'Once upon a time' --tokens 32
.venv/bin/python scripts/check_llm.py
```

`--host-only` changes the Mac client file without resetting credentials or Wi-Fi. For a temporary address, use `scripts/chat.py --url http://192.168.4.1:8000/v1`.

View USB logs with `mpremote connect "$ESP32_PORT" repl`; press RESET on the board to observe startup and Ctrl-] to exit. REPL maintenance can interrupt the main application. Finish with `mpremote connect "$ESP32_PORT" reset`.

## 7. Restore a backup

Use this only when reverting the installed system. Restoration overwrites the entire Flash, including files created since the backup:

```sh
shasum -a 256 -c backups/original.bin.sha256
.venv/bin/python -m esptool --chip esp32s3 --port "$ESP32_PORT" --baud 921600 --after watchdog-reset write-flash 0 backups/original.bin
```

Check the target port and backup checksum first. Personal device backups are not included in the repository.
