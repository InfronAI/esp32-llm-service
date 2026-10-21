"""Shared host-side paths and explicit, unambiguous USB selection."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def serial_port(requested=None):
    if requested:
        return requested
    from serial.tools.list_ports import comports
    ports = [p.device for p in comports()
             if p.vid == 0x303A and not p.device.startswith('/dev/tty.')]
    if len(ports) != 1:
        raise SystemExit('Expected one Espressif USB device; found %d. '
                         'Connect the board or specify --port explicitly.' % len(ports))
    return ports[0]
