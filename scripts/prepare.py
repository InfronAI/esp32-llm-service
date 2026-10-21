#!/usr/bin/env python3
"""Fetch pinned firmware, model assets and native-module build sources."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request
from project import ROOT


def verified_download(url, destination, expected, offline=False):
    destination = Path(destination)
    if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() == expected:
        print('Verified:', destination.name)
        return
    if offline:
        raise RuntimeError('Missing or corrupt asset: '+str(destination))
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix+'.part')
    try:
        with urllib.request.urlopen(url, timeout=60) as response, temporary.open('wb') as output:
            while chunk := response.read(65536):
                output.write(chunk)
        if hashlib.sha256(temporary.read_bytes()).hexdigest() != expected:
            raise RuntimeError('SHA-256 mismatch: '+destination.name)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    print('Downloaded and verified:', destination.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', choices=('all','firmware','models','source'), default='all')
    parser.add_argument('--offline', action='store_true', help='verify existing assets without network access')
    args = parser.parse_args()
    firmware = json.loads((ROOT/'firmware/manifest.json').read_text())
    if args.only in ('all','firmware'):
        verified_download(firmware['url'], ROOT/'firmware'/firmware['filename'], firmware['sha256'], args.offline)
    if args.only in ('all','models'):
        manifest = json.loads((ROOT/'models/manifest.json').read_text())
        for name, entry in manifest['weights_and_tokenizer'].items():
            url = 'https://raw.githubusercontent.com/doryiii/esp32-llm/'+manifest['source_commit']+'/spiffs_data/'+name
            verified_download(url, ROOT/'models'/name, entry['sha256'], args.offline)
    if args.only in ('all','source'):
        source = ROOT/'third_party/micropython'
        if not source.exists():
            if args.offline:
                raise RuntimeError('Missing MicroPython source')
            source.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['git','clone','--depth','1','--branch','v'+firmware['version'],
                            'https://github.com/micropython/micropython.git',str(source)],check=True)
        revision = subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
        if revision != firmware['micropython_commit']:
            raise RuntimeError('MicroPython source revision mismatch; use the pinned v1.29.0 checkout')
        if subprocess.check_output(['git','-C',str(source),'status','--porcelain','--untracked-files=no'],text=True).strip():
            raise RuntimeError('MicroPython source has tracked changes; use a clean checkout')
        print('Verified MicroPython source:', revision)


if __name__ == '__main__':
    main()
