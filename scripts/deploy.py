#!/usr/bin/env python3
"""Install the shell and local LLM service; preserve settings unless requested."""
import argparse
import datetime
import hashlib
import json
from mpremote.transport_serial import SerialTransport
from project import ROOT, serial_port

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--port', help='USB serial port; auto-selects a single Espressif USB device')
parser.add_argument('--settings', action='store_true', help='replace board credentials with local settings.json')
parser.add_argument('--models', action='store_true', help='install and verify model weights and tokenizer')
args = parser.parse_args()
files = [(ROOT/'device'/name, '/'+name) for name in ('boot.py','net.py','shell.py','llm.py','api.py')]
files.append((ROOT/'native/tinyllm_native.mpy', '/tinyllm_native.mpy'))
if args.models:
    manifest = json.loads((ROOT/'models/manifest.json').read_text())
    for name, entry in manifest['weights_and_tokenizer'].items():
        path = ROOT/'models'/name
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError('Model checksum mismatch: ' + name)
        files.append((path, '/models/'+name))
if args.settings:
    files.append((ROOT/'device/settings.json', '/settings.json'))
files.append((ROOT/'device/main.py', '/main.py'))
for path, _ in files:
    if not path.is_file():
        parser.error('Missing file: '+str(path)+'; complete prepare/build/configure first.')
transport = SerialTransport(serial_port(args.port))
resetting = False
try:
    transport.enter_raw_repl()
    if args.models:
        transport.exec("import os\ntry:\n os.mkdir('/models')\nexcept OSError:\n pass")
    for source, dest in files:
        data = source.read_bytes()
        expected = hashlib.sha256(data).digest()
        try:
            current = transport.fs_hashfile(dest, 'sha256', chunk_size=8192)
        except OSError:
            current = None
        if current == expected:
            print('Unchanged:', dest, flush=True)
            continue
        transport.fs_writefile(dest, data, chunk_size=4096)
        if transport.fs_hashfile(dest, 'sha256', chunk_size=8192) != expected:
            raise RuntimeError('Board checksum mismatch: ' + dest)
        print('Verified:', dest, len(data), 'bytes', flush=True)
    now = datetime.datetime.now(datetime.timezone.utc)
    rtc = (now.year, now.month, now.day, now.weekday(), now.hour, now.minute, now.second, 0)
    transport.exec('import machine; machine.RTC().datetime(%r)' % (rtc,))
    transport.exec_raw_no_follow('import machine; machine.reset()')
    resetting = True
    print('Restarting ESP32; allow up to 30 seconds for Wi-Fi and model startup.')
finally:
    try:
        transport.close()
    except OSError:
        if not resetting:
            raise
