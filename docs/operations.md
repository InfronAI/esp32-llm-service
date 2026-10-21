# Shell, maintenance, and troubleshooting

**English** | [简体中文](operations.zh-CN.md)

## Log in to the shell

```sh
./connect.command 192.168.1.50
# When connected directly to the board AP:
./connect.command
```

The client defaults to `192.168.4.1:23` and needs only the system Python standard library. Use the username and password in local `reports/access.json`; passwords are not echoed. Ctrl-] disconnects the client and `exit` leaves the shell. Login times out after 60 seconds; an authenticated session has a 15-minute idle timeout.

```sh
help
uname -a
free
df
ifconfig
mkdir demo
cd demo
echo "hello ESP32" > hello.txt
cat hello.txt
python -c "print(2 + 3)"
passwd
reboot
```

Files live under `/home`. The shell supports `cp`, `mv`, `rm`, `rmdir`, append redirection `>>`, arrow-key history, Tab completion, and Ctrl-U. `python` opens a single-line MicroPython console; `exit()` returns to the shell. Ctrl-C interrupts user Python with assistance from hardware Timer 0.

This MCU shell has no Linux processes, Bash, apt, pipes, or executable ELF user programs. Authenticated users can execute arbitrary MicroPython; system-file write protection prevents accidental edits.

## Update code and configuration

```sh
.venv/bin/python scripts/deploy.py
.venv/bin/python scripts/deploy.py --port /dev/cu.usbmodemXXXX
```

By default, deployment preserves board settings, models, and `/home`. Add `--settings` after changing configuration, and `--models` for initial installation or model repair. Regenerating configuration would change credentials, so the generator refuses to overwrite existing files.

After shell `passwd`, export board settings before editing other options to avoid overwriting the new password with an old copy:

```sh
.venv/bin/mpremote connect /dev/cu.usbmodemXXXX fs cp :settings.json device/settings.json
.venv/bin/mpremote connect /dev/cu.usbmodemXXXX reset
```

Also update the shell password in local `reports/access.json` for automated login tests. Keep the API key and AP password consistent between the two configuration files.

To change only the client IP:

```sh
.venv/bin/python scripts/configure.py --host-only 192.168.1.50
```

## Troubleshooting

| Symptom | Check or action |
| --- | --- |
| No serial port | Try a data cable, inspect `serial.tools.list_ports -v`, use BOOT/RESET, and close other serial programs |
| Port changed after flashing | Detect it again; application and ROM USB modes can use different paths |
| Wi-Fi network not found | Check the exact 2.4 GHz SSID; a 5 GHz-only AP cannot be used |
| LAN access fails | Check DHCP address, client isolation, Mac routes, and proxies; test through the direct AP |
| curl returns proxy HTML | Add `--noproxy '*'`; use Python `trust_env=False` |
| 401 | Use the board's API key; check whether local settings changed without deployment |
| 400 context limit | Shorten the prompt or output budget to fit 512 tokens total |
| Output is not a Chinese assistant answer | The model continues English stories; use an English story prefix |
| invalid .mpy / incompatible architecture | Confirm MicroPython 1.29.0 and Xtensa ABI; rebuild the native module |
| MemoryError | Confirm 8 MB Octal PSRAM and SPIRAM_OCT firmware; check user-script allocations |
| Inference failure / API absent | Inspect USB traceback and verify model files, native module, and settings; the shell can still help repair files |
| Concurrent calls are slow or health waits | HTTP is sequential; reduce concurrency, stream output, and increase client timeout |
| HTTP disappears after USB testing | Run `mpremote connect <port> reset` to resume startup |
| Incorrect created timestamp | Power loss can reset the RTC; deployment sets host UTC time again |

## Backups and network boundaries

See [restore a backup](installation.md#7-restore-a-backup). Keep Flash backups, Wi-Fi passwords, and access configuration local. Git ignores `backups/`, `reports/`, `device/settings.json`, and `.env`.

The shell uses plaintext TCP and the API uses HTTP Bearer authentication. WPA2 protects the wireless link but does not provide end-to-end TLS. Use the service on a trusted LAN. The AP provides device access without forwarding Internet traffic. Once running, the board can be disconnected from the development host and kept on stable power.
