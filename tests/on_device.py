"""Run on the ESP32, with TEST_PASSWORD injected by scripts/check_device.py.

Exercises actual TCP sockets on the AP interface, not the Mac's Wi-Fi radio.
The server runs on the main interpreter thread, as in normal boot.
"""
import _thread
import time
import socket
import json
import os
import sys
import shell

# Clean only this suite's own scratch directory after an interrupted run.
try:
    for name in os.listdir('/home/shell-test'):
        os.remove('/home/shell-test/' + name)
    os.rmdir('/home/shell-test')
except OSError:
    pass

finished = False
results = []
failure = None


def until(sock, marker):
    data = b""
    while not data.endswith(marker):
        chunk = sock.recv(2048)
        if not chunk:
            raise AssertionError("unexpected EOF: %r" % data)
        data += chunk
        if len(data) > 32768:
            raise AssertionError("response too long")
    return data


def check(label, passed):
    if not passed:
        raise AssertionError(label)
    results.append(label)


def login(password, fail=False):
    conn = socket.socket()
    conn.settimeout(15)
    conn.connect(("192.168.4.1", 23))
    until(conn, b"login: ")
    conn.sendall(b"esp32\r\n")
    until(conn, b"Password: ")
    conn.sendall(password.encode() + b"\r\n")
    response = until(conn, b"login: " if fail else b"$ ")
    check("password is not echoed", password.encode() not in response)
    return conn, response


def command(conn, text):
    conn.sendall(text.encode() + b"\r\n")
    return until(conn, b"$ ")


def client():
    global finished, failure
    conn = None
    time.sleep(2)
    try:
        conn, output = login("incorrect-password", fail=True)
        check("incorrect password rejected", b"Login incorrect" in output)
        conn.close()
        conn, output = login(TEST_PASSWORD)
        check("authenticated shell", b"Welcome!" in output)
        check("home directory", b"\r\n/home\r\n" in command(conn, "pwd"))
        check("system identity", b"ESP32-S3" in command(conn, "uname -a"))
        check("PSRAM available", b"free" in command(conn, "free"))
        check("filesystem status", b"available" in command(conn, "df"))
        check("AP configuration", b"192.168.4.1" in command(conn, "ifconfig"))
        command(conn, "mkdir shell-test")
        command(conn, "cd shell-test")
        command(conn, 'echo "hello ESP32" > first.txt')
        command(conn, 'echo "second line" >> first.txt')
        check("write, append and read", b"hello ESP32\r\nsecond line\r\n" in command(conn, "cat first.txt"))
        command(conn, "cp first.txt second.txt")
        check("copy", b"hello ESP32\r\n" in command(conn, "cat second.txt"))
        command(conn, "mv second.txt moved.txt")
        check("rename and list", b"moved.txt" in command(conn, "ls -l"))
        check("self-copy rejected", b"same" in command(conn, "cp first.txt first.txt"))
        check("system file guard", b"protected" in command(conn, "echo bad > /main.py"))
        check("quoted arguments", b"hello world\r\n" in command(conn, 'echo "hello world"'))
        output = command(conn, 'python -c "print(2 + 3)"')
        assert b"\r\n5\r\n" in output, repr(output)
        check("Python stdout", True)
        check("Python persistent namespace", b"\r\n42\r\n" in command(conn, 'python -c "answer=42; print(answer)"'))
        check("Python exceptions recover", b"ZeroDivisionError" in command(conn, 'python -c "print(1/0)"'))
        # Timer notification must interrupt running user Python on the main thread.
        conn.sendall(b'python -c "while True: pass"\r\n')
        time.sleep_ms(300)
        conn.sendall(b"\x03")
        check("Ctrl-C interrupts Python", b"KeyboardInterrupt" in until(conn, b"$ "))
        conn.sendall(b"python\r\n")
        until(conn, b">>> ")
        conn.sendall(b"6 * 7\r\n")
        check("interactive Python expression", b"\r\n42\r\n" in until(conn, b">>> "))
        conn.sendall(b"exit()\r\n")
        until(conn, b"$ ")
        conn.sendall(b"pw\t\r\n")
        check("Tab completion", b"/home/shell-test\r\n" in until(conn, b"$ "))
        command(conn, "echo history-ok")
        conn.sendall(b"\x1b[A\r\n")
        check("history recall", b"history-ok\r\n" in until(conn, b"$ "))
        conn.sendall(b"echo backspacX\x7fe\r\n")
        check("Backspace editing", b"\r\nbackspace\r\n" in until(conn, b"$ "))
        command(conn, "rm first.txt")
        command(conn, "rm moved.txt")
        command(conn, "cd ..")
        command(conn, "rmdir shell-test")
        check("file cleanup", b"shell-test" not in command(conn, "ls"))
        command(conn, 'echo "reboot-persistence-check" > persistence.txt')
        conn.sendall(b"exit\r\n")
        until(conn, b"Bye.\r\n")
        conn.close()
        conn, output = login(TEST_PASSWORD)
        check("logout and reconnect", b"Welcome!" in output)
        conn.sendall(b"passwd\r\n")
        until(conn, b"characters): ")
        conn.sendall((TEST_PASSWORD + "x\r\n").encode())
        until(conn, b"Repeat password: ")
        conn.sendall((TEST_PASSWORD + "x\r\n").encode())
        check("password change saved", b"Password updated" in until(conn, b"$ "))
        conn.sendall(b"exit\r\n")
        until(conn, b"Bye.\r\n")
        conn.close()
        conn, output = login(TEST_PASSWORD + "x")
        check("new password authenticates", b"Welcome!" in output)
        conn.sendall(b"passwd\r\n")
        until(conn, b"characters): ")
        conn.sendall((TEST_PASSWORD + "\r\n").encode())
        until(conn, b"Repeat password: ")
        conn.sendall((TEST_PASSWORD + "\r\n").encode())
        check("original password restored", b"Password updated" in until(conn, b"$ "))
        conn.close()
    except BaseException as exc:
        failure = repr(exc)
        sys.print_exception(exc)
    finally:
        if conn:
            conn.close()
        finished = True


_thread.stack_size(16 * 1024)
_thread.start_new_thread(client, ())
shell.serve(lambda: finished)
time.sleep_ms(200)
print(json.dumps({"passed": results, "failure": failure}))
assert failure is None, failure
