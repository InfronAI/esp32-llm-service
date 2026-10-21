"""Small, single-session Wi-Fi shell for MicroPython on ESP32."""
import os
import sys
import gc
import time
import socket
import select
import io
import json
import hashlib
import binascii
import machine
import network

SETTINGS = "/settings.json"
PROTECTED = ("/boot.py", "/main.py", "/shell.py", "/net.py", "/llm.py", "/api.py",
             "/tinyllm_native.mpy", "/models/stories260K.bin", "/models/tok512.bin", SETTINGS)
STARTED = time.ticks_ms()
COMMANDS = "help ls pwd cd cat echo touch mkdir rmdir rm cp mv uname hostname whoami uptime free df ifconfig wifi python passwd clear reboot exit"
HELP = """ESP32 Shell commands:
  ls [-l] [-a] [path]         list files
  pwd | cd [directory]       show/change directory (home: /home)
  cat file ...               display text files
  echo text [> file]         print or write text (also supports >>)
  touch file | mkdir dir     create file/directory
  rm file | rmdir dir        remove file/empty directory
  cp source dest | mv a b    copy/move a file
  uname [-a] | hostname      system information
  whoami | uptime | free     user, uptime, heap memory
  df | ifconfig | wifi       storage and Wi-Fi status
  python -c 'code'           execute MicroPython code
  python file.py            execute a MicroPython script
  python                    single-line Python console; exit() returns
  passwd                    change shell login password
  clear | reboot | exit     clear screen/restart/log out
Editing: Backspace, Up/Down history, Tab command completion, Ctrl-U.
Ctrl-C cancels input; Ctrl-D logs out. Python supports Ctrl-C interruption.
No pipes, globbing, background jobs, bash, apt or Linux executables.
"""


def password_hash(salt, password):
    return binascii.hexlify(hashlib.sha256((salt + password).encode()).digest()).decode()


def split_line(line):
    tokens, buf, quote, escaped, started = [], "", None, False, False
    for ch in line:
        if escaped:
            buf += ch
            escaped = False
        elif ch == "\\" and quote != "'":
            escaped = True
            started = True
        elif quote:
            if ch == quote:
                quote = None
            else:
                buf += ch
        elif ch in "\"'":
            quote = ch
            started = True
        elif ch.isspace():
            if started:
                tokens.append(buf)
                buf, started = "", False
        elif ch in "|&;<>" and ch != ">":
            raise ValueError("pipes, chaining and input redirection are not supported")
        elif ch == ">":
            if started:
                tokens.append(buf)
                buf, started = "", False
            if tokens and tokens[-1] == ">":
                tokens[-1] = ">>"
            else:
                tokens.append(">")
        else:
            buf += ch
            started = True
    if escaped or quote:
        raise ValueError("unfinished quote or escape")
    if started:
        tokens.append(buf)
    return tokens


class Terminal:
    def __init__(self, conn):
        self.conn = conn
        self.history = []
        self.skip_lf = False
        self.conn.settimeout(60)

    def write(self, text):
        data = text.replace("\r\n", "\n").replace("\n", "\r\n").encode()
        self.conn.sendall(data)

    def char(self):
        data = self.conn.recv(1)
        if not data:
            raise EOFError()
        # Ignore/reject Telnet options; the bundled client uses raw TCP.
        if data == b"\xff":
            op = self.conn.recv(1)
            if op in (b"\xfb", b"\xfc", b"\xfd", b"\xfe"):
                opt = self.conn.recv(1)
                if op in (b"\xfb", b"\xfd"):
                    self.conn.sendall(b"\xff" + (b"\xfe" if op == b"\xfb" else b"\xfc") + opt)
            return b""
        return data

    def readline(self, prompt="", secret=False, history=False):
        self.write(prompt)
        buf = bytearray()
        pos = len(self.history)
        saved = b""
        while True:
            ch = self.char()
            if not ch:
                continue
            if self.skip_lf:
                self.skip_lf = False
                if ch in (b"\n", b"\x00"):
                    continue
            if ch in (b"\r", b"\n"):
                self.skip_lf = ch == b"\r"
                self.write("\n")
                line = bytes(buf).decode("utf-8")
                if history and line and (not self.history or self.history[-1] != line):
                    self.history.append(line)
                    self.history = self.history[-20:]
                return line
            if ch == b"\x04" and not buf:
                raise EOFError()
            if ch == b"\x03":
                self.write("^C\n" + prompt)
                buf = bytearray()
                continue
            if ch in (b"\x7f", b"\x08") and buf:
                # Delete an entire UTF-8 code point.
                end = len(buf) - 1
                while end > 0 and buf[end] & 0xC0 == 0x80:
                    end -= 1
                buf = buf[:end]
                if not secret:
                    self.write("\b \b")
            elif ch == b"\x15":
                if not secret:
                    self.write("\r\x1b[2K" + prompt)
                buf = bytearray()
            elif ch == b"\x1b":
                first = self.char()
                if first != b"[":
                    continue
                code = self.char()
                if code in (b"A", b"B") and history and not secret:
                    if pos == len(self.history):
                        saved = bytes(buf)
                    pos = max(0, min(len(self.history), pos + (-1 if code == b"A" else 1)))
                    buf = bytearray(self.history[pos].encode() if pos < len(self.history) else saved)
                    self.write("\r\x1b[2K" + prompt + bytes(buf).decode())
                elif code in (b"1", b"2", b"3", b"4", b"5", b"6"):
                    self.char()
            elif ch == b"\t" and history and not secret:
                prefix = bytes(buf).decode()
                matches = [c for c in COMMANDS.split() if c.startswith(prefix)]
                if len(matches) == 1:
                    addition = matches[0][len(prefix):] + " "
                    buf.extend(addition.encode())
                    self.write(addition)
                elif matches:
                    self.write("\n" + "  ".join(matches) + "\n" + prompt + prefix)
            elif ch[0] >= 32 and ch != b"\x7f" and len(buf) < 1024:
                buf.extend(ch)
                if not secret:
                    self.conn.sendall(ch)


class PythonStream(io.IOBase):
    """Temporary dupterm stream: prints and Ctrl-C for Python execution."""
    def __init__(self, terminal):
        self.terminal = terminal
        self.poll = select.poll()
        self.poll.register(terminal.conn, select.POLLIN)
        self.last_cr = False

    def write(self, data):
        output = bytearray()
        for value in data:
            if value == 10 and not self.last_cr:
                output.append(13)
            output.append(value)
            self.last_cr = value == 13
        self.terminal.conn.sendall(output)
        return len(data)

    def readinto(self, buf):
        if not self.poll.poll(0):
            return None
        data = self.terminal.conn.recv(len(buf))
        buf[:len(data)] = data
        return len(data)

    def ioctl(self, request, arg):
        if request == 3:
            return (1 if self.poll.poll(0) else 0) | 4
        return 0


class Shell:
    def __init__(self, terminal, config, ap):
        self.term, self.config, self.ap = terminal, config, ap
        self.cwd = "/home"
        self.output = None
        self.namespace = {"__name__": "__main__"}

    def path(self, name):
        if name == "~":
            name = "/home"
        elif name.startswith("~/"):
            name = "/home/" + name[2:]
        parts = []
        for part in (name if name.startswith("/") else self.cwd + "/" + name).split("/"):
            if part == "..":
                if parts:
                    parts.pop()
            elif part and part != ".":
                parts.append(part)
        return "/" + "/".join(parts)

    def writable(self, name):
        path = self.path(name)
        if path in PROTECTED or path == "/":
            raise ValueError("system file protected; use USB mpremote for maintenance")
        return path

    def emit(self, text=""):
        if self.output:
            self.output.write(str(text) + "\n")
        else:
            self.term.write(str(text) + "\n")

    def run_python(self, code):
        os.chdir(self.cwd)
        self.term.conn.settimeout(5)
        stream = PythonStream(self.term)
        previous = os.dupterm(stream)
        timer = machine.Timer(0)
        try:
            timer.init(period=50, mode=machine.Timer.PERIODIC, callback=os.dupterm_notify)
            exec(code, self.namespace)
        except (Exception, KeyboardInterrupt) as exc:
            sys.print_exception(exc)
        finally:
            timer.deinit()
            os.dupterm(previous)
            self.term.conn.settimeout(900)
            os.chdir("/")
            gc.collect()

    def execute(self, line):
        args = split_line(line)
        if not args:
            return True
        cmd, args = args[0], args[1:]
        redir = next((i for i, arg in enumerate(args) if arg in (">", ">>")), -1)
        if redir >= 0:
            if cmd not in ("echo", "cat") or redir != len(args) - 2:
                raise ValueError("use echo/cat ... > file or >> file")
            dest = self.writable(args[-1])
            if cmd == "cat" and dest in [self.path(a) for a in args[:redir]]:
                raise ValueError("input and output must be different files")
            self.output = open(dest, "a" if args[redir] == ">>" else "w")
            args = args[:redir]
        try:
            return self.dispatch(cmd, args)
        finally:
            if self.output:
                self.output.close()
                self.output = None

    def dispatch(self, cmd, args):
        if cmd == "help":
            self.emit(HELP)
        elif cmd == "pwd":
            self.emit(self.cwd)
        elif cmd == "cd":
            path = self.path(args[0] if args else "/home")
            if not os.stat(path)[0] & 0x4000:
                raise ValueError("not a directory")
            self.cwd = path
        elif cmd == "ls":
            flags = "".join(a[1:] for a in args if a.startswith("-"))
            paths = [a for a in args if not a.startswith("-")]
            target = self.path(paths[0] if paths else ".")
            for name in sorted(os.listdir(target)):
                if name.startswith(".") and "a" not in flags:
                    continue
                stat = os.stat(target.rstrip("/") + "/" + name)
                isdir = bool(stat[0] & 0x4000)
                label = name + ("/" if isdir else "")
                self.emit(("%s %8d %s" % ("d" if isdir else "-", stat[6], label)) if "l" in flags else label)
        elif cmd == "cat":
            if not args:
                raise ValueError("usage: cat file ...")
            for name in args:
                with open(self.path(name)) as handle:
                    while True:
                        data = handle.read(256)
                        if not data:
                            break
                        if self.output:
                            self.output.write(data)
                        else:
                            self.term.write(data)
        elif cmd == "echo":
            self.emit(" ".join(args))
        elif cmd in ("touch", "mkdir", "rmdir", "rm"):
            if len(args) != 1 or args[0].startswith("-"):
                raise ValueError("usage: " + cmd + " path (no flags)")
            path = self.writable(args[0])
            if cmd == "touch":
                open(path, "a").close()
            else:
                {"mkdir": os.mkdir, "rmdir": os.rmdir, "rm": os.remove}[cmd](path)
        elif cmd in ("cp", "mv"):
            if len(args) != 2:
                raise ValueError("usage: " + cmd + " source destination")
            source, dest = self.path(args[0]), self.writable(args[1])
            try:
                if os.stat(dest)[0] & 0x4000:
                    dest = self.writable(dest + "/" + source.rsplit("/", 1)[-1])
            except OSError:
                pass
            if source == dest:
                raise ValueError("source and destination are the same")
            if cmd == "mv":
                os.rename(self.writable(args[0]), dest)
            else:
                with open(source, "rb") as src, open(dest, "wb") as dst:
                    while True:
                        data = src.read(512)
                        if not data:
                            break
                        dst.write(data)
        elif cmd == "uname":
            self.emit(" ".join(os.uname()))
        elif cmd == "hostname":
            self.emit("esp32")
        elif cmd == "whoami":
            self.emit(self.config["user"])
        elif cmd == "uptime":
            self.emit("up %d seconds" % (time.ticks_diff(time.ticks_ms(), STARTED) // 1000))
        elif cmd == "free":
            gc.collect()
            self.emit("MicroPython heap: used %d bytes, free %d bytes" % (gc.mem_alloc(), gc.mem_free()))
        elif cmd == "df":
            stat = os.statvfs("/")
            self.emit("Filesystem: total %d KiB, used %d KiB, available %d KiB" % (stat[0]*stat[2]//1024, stat[0]*(stat[2]-stat[3])//1024, stat[0]*stat[4]//1024))
        elif cmd in ("ifconfig", "wifi"):
            self.emit("AP: %s  WPA2  channel %s" % (self.config["ssid"], self.ap.config("channel")))
            self.emit("IP %s  mask %s  gateway %s  DNS %s" % self.ap.ifconfig())
            self.emit("MAC " + ":".join("%02x" % b for b in self.ap.config("mac")))
            self.emit("Connected stations: %d" % len(self.ap.status("stations")))
            sta = network.WLAN(network.WLAN.IF_STA)
            self.emit("STA: %s  connected=%s  IP=%s" % (self.config.get('sta_ssid', ''), sta.isconnected(), sta.ifconfig()[0]))
        elif cmd == "python":
            if not args:
                self.emit("Single-line MicroPython console. exit() returns to shell.")
                while True:
                    code = self.term.readline(">>> ", history=True)
                    if code.strip() in ("exit()", "quit()"):
                        break
                    # Compile in single mode to echo expression values.
                    self.run_python(compile(code, "<console>", "single"))
            elif args[0] == "-c" and len(args) == 2:
                self.run_python(args[1])
            elif len(args) == 1:
                with open(self.path(args[0])) as handle:
                    self.run_python(handle.read())
            else:
                raise ValueError("usage: python [-c 'code' | file.py]")
        elif cmd == "passwd":
            first = self.term.readline("New password (8+ characters): ", secret=True)
            second = self.term.readline("Repeat password: ", secret=True)
            if len(first) < 8 or first != second:
                raise ValueError("passwords must match and contain at least 8 characters")
            updated = dict(self.config)
            updated["salt"] = binascii.hexlify(os.urandom(16)).decode()
            updated["password_hash"] = password_hash(updated["salt"], first)
            with open(SETTINGS + ".new", "w") as handle:
                json.dump(updated, handle)
            os.rename(SETTINGS + ".new", SETTINGS)
            self.config.update(updated)
            self.emit("Password updated.")
        elif cmd == "clear":
            self.term.write("\x1b[2J\x1b[H")
        elif cmd == "reboot":
            self.emit("Rebooting; reconnect in a few seconds.")
            time.sleep_ms(150)
            machine.reset()
        elif cmd in ("exit", "logout"):
            self.emit("Bye.")
            return False
        else:
            self.emit("%s: command not found; type help" % cmd)
        return True

    def session(self):
        self.term.write("\nESP32 Shell / MicroPython\n")
        for attempt in range(3):
            user = self.term.readline("login: ")
            password = self.term.readline("Password: ", secret=True)
            if user == self.config["user"] and password_hash(self.config["salt"], password) == self.config["password_hash"]:
                break
            time.sleep(2)
            self.term.write("Login incorrect.\n")
        else:
            return
        self.term.conn.settimeout(900)
        self.emit("Welcome! Type help. Your files are in /home.")
        while True:
            line = self.term.readline("%s@esp32:%s$ " % (self.config["user"], self.cwd), history=True)
            try:
                if not self.execute(line):
                    break
            except (OSError, ValueError, IndexError, SyntaxError) as exc:
                self.emit("error: %s" % exc)
            gc.collect()


def serve(stop=None):
    with open(SETTINGS) as handle:
        config = json.load(handle)
    try:
        os.mkdir("/home")
    except OSError:
        pass
    import net
    ap = net.setup()
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("0.0.0.0", config.get("port", 23)))
    listener.listen(1)
    listener.settimeout(1)
    print("ESP32 Shell ready: %s at 192.168.4.1:%d" % (config["ssid"], config.get("port", 23)))
    while stop is None or not stop():
        try:
            conn, peer = listener.accept()
        except OSError:
            continue
        try:
            Shell(Terminal(conn), config, ap).session()
        except (OSError, EOFError, UnicodeError):
            pass
        except Exception as exc:
            sys.print_exception(exc)
        finally:
            # Drain a trailing LF after CRLF input before close, so lwIP sends
            # the final message instead of resetting a socket with unread data.
            try:
                conn.settimeout(0.1)
                conn.recv(1024)
            except OSError:
                pass
            conn.close()
            os.chdir("/")
            gc.collect()
    listener.close()
