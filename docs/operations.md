# 命令行、维护与故障排查

## 登录 shell

```sh
./connect.command 192.168.1.50
# 直连板子热点时：
./connect.command
```

客户端默认访问 `192.168.4.1:23`，仅依赖系统 Python 标准库。使用本机 `reports/access.json` 中的用户名与密码，密码不回显。Ctrl-] 断开客户端，`exit` 退出 shell。登录超时 60 秒，登录后空闲超时 15 分钟。

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

文件保存在 `/home`。支持 `cp`、`mv`、`rm`、`rmdir`、追加重定向 `>>`、方向键历史、Tab 补全和 Ctrl-U。`python` 进入单行 MicroPython 控制台，`exit()` 返回 shell。Ctrl-C 可中断用户 Python，使用硬件 Timer 0 辅助通知。

这是 MCU shell，没有 Linux 进程、Bash、apt、管道或可执行 ELF 用户程序。已认证用户可以运行任意 MicroPython；系统文件写保护用于避免误操作。

## 更新代码与配置

```sh
.venv/bin/python scripts/deploy.py
.venv/bin/python scripts/deploy.py --port /dev/cu.usbmodemXXXX
```

默认保留板子配置、模型与 `/home`。只在修改配置后加 `--settings`，修复或首次安装模型时加 `--models`。重新生成配置会改变凭据，因此生成器拒绝覆盖已有文件。

执行 shell `passwd` 后，先导出板上的配置再编辑其他设置，防止旧文件覆盖新密码：

```sh
.venv/bin/mpremote connect /dev/cu.usbmodemXXXX fs cp :settings.json device/settings.json
.venv/bin/mpremote connect /dev/cu.usbmodemXXXX reset
```

本机 `reports/access.json` 的 shell 密码也需同步更新，供自动测试登录。API Key 与热点密码各自在两个配置文件中保持一致。

仅变更客户端 IP：

```sh
.venv/bin/python scripts/configure.py --host-only 192.168.1.50
```

## 常见问题

| 现象 | 检查与处理 |
| --- | --- |
| 找不到串口 | 换数据线，查看 `serial.tools.list_ports -v`，尝试 BOOT/RESET，关闭占用串口的软件 |
| 刷写后端口变了 | 重新检测；应用和 ROM USB 模式可使用不同设备节点 |
| ESP32 扫描不到 Wi-Fi | 核对准确的 2.4 GHz SSID；5 GHz 热点不可用 |
| LAN 无法访问 | 检查 DHCP 地址、客户端隔离、Mac 路由和代理；用直连热点验证 |
| curl 返回代理 HTML | 加 `--noproxy '*'`；Python 设置 `trust_env=False` |
| 401 | 使用板上配置的 API Key；检查是否只修改了本机配置而未部署 |
| 400 context limit | 缩短提示词或输出预算，合计最多 512 token |
| 返回内容不是中文助手回答 | 模型是英文故事续写基础模型，改用英文故事前缀 |
| invalid .mpy / incompatible architecture | 核对 MicroPython 1.29.0、Xtensa ABI，重建原生模块 |
| MemoryError | 确认 8 MB Octal PSRAM 与 SPIRAM_OCT 固件，检查用户脚本内存占用 |
| inference failure / API 没启动 | 查看 USB traceback；校验模型文件、原生模块和配置；shell 仍可用于修复 |
| 并发调用慢或 health 等待 | HTTP 串行处理；减少并发，使用流式输出并增加客户端超时 |
| USB 测试后 HTTP 消失 | 运行 `mpremote connect <port> reset` 恢复启动流程 |
| created 时间不对 | RTC 断电后可能失准；重新部署会设置主机 UTC 时间 |

## 备份与网络边界

固件恢复步骤见[安装文档](installation.md#7-恢复备份)。Flash 备份、Wi-Fi 密码和访问配置只保存在本机。仓库忽略 `backups/`、`reports/`、`device/settings.json`、`.env`。

shell 使用明文 TCP，API 使用 HTTP Bearer Key；WPA2 保护无线链路，但没有端到端 TLS。服务适用于可信局域网。热点仅提供设备访问，不转发互联网。板子运行后可断开开发机，只保留稳定供电。
