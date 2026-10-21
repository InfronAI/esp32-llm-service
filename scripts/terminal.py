#!/usr/bin/env python3
"""Dependency-free Mac/Linux client for the ESP32 terminal."""
import argparse
import os
import select
import socket
import sys
import termios
import tty


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", nargs="?", default="192.168.4.1")
    parser.add_argument("--port", type=int, default=23)
    args = parser.parse_args()
    if not sys.stdin.isatty():
        parser.error("Run this client in an interactive terminal.")
    try:
        sock = socket.create_connection((args.host, args.port), timeout=10)
    except OSError as exc:
        parser.exit(1, "Connection failed: %s\nCheck the ESP32 IP and Wi-Fi connection.\n" % exc)
    sock.settimeout(None)
    fd = sys.stdin.fileno()
    previous = termios.tcgetattr(fd)
    print("Connected to %s:%s. Ctrl-] disconnects locally." % (args.host, args.port))
    try:
        tty.setraw(fd)
        while True:
            ready, _, _ = select.select([sock, fd], [], [])
            if sock in ready:
                data = sock.recv(4096)
                if not data:
                    break
                sys.stdout.buffer.write(data)
                sys.stdout.buffer.flush()
            if fd in ready:
                data = os.read(fd, 1024)
                if not data or b"\x1d" in data:
                    break
                sock.sendall(data)
    except (OSError, KeyboardInterrupt) as exc:
        sys.stdout.write("\r\nDisconnected: %s\r\n" % exc)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, previous)
        sock.close()
        print("\nConnection closed.")


if __name__ == "__main__":
    main()
