#!/usr/bin/env python3
"""Build the Xtensa module using a configured or discovered Arduino toolchain."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
from project import ROOT

prefix = os.environ.get('ESP32_CROSS')
if not prefix:
    compiler = shutil.which('xtensa-esp32s3-elf-gcc')
    if compiler:
        prefix = compiler[:-3]
    else:
        candidates = []
        for base in (Path.home()/'Library/Arduino15', Path.home()/'.arduino15'):
            candidates.extend(base.glob('packages/esp32/tools/esp-x32/2601/bin/xtensa-esp32s3-elf-gcc'))
        if len(candidates) == 1:
            prefix = str(candidates[0])[:-3]
if not prefix or not Path(prefix+'gcc').exists() and not shutil.which(prefix+'gcc'):
    raise SystemExit('Install Arduino ESP32 core 3.3.8, or set ESP32_CROSS to /path/to/xtensa-esp32s3-elf-.')
if not (ROOT/'third_party/micropython/py/dynruntime.mk').exists():
    raise SystemExit('Run scripts/prepare.py --only source first.')
print('Compiler:', prefix+'gcc', flush=True)
subprocess.run(['make','-C',str(ROOT/'native'),'CROSS='+prefix,'PYTHON='+sys.executable],check=True)
