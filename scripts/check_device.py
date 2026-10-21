#!/usr/bin/env python3
"""Exercise the real ESP32 TCP server over its own AP IP, via USB control."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from project import serial_port

root = Path(__file__).resolve().parents[1]
access = json.loads((root / "reports/access.json").read_text())
source = "TEST_PASSWORD = %r\n" % access["password"]
source += (root / "tests/on_device.py").read_text()
port = serial_port(sys.argv[1] if len(sys.argv) > 1 else None)
with tempfile.NamedTemporaryFile("w", suffix=".py") as handle:
    handle.write(source)
    handle.flush()
    result = subprocess.run([str(root / ".venv/bin/mpremote"), "connect", port, "run", handle.name], timeout=90)
    raise SystemExit(result.returncode)
