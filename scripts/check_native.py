#!/usr/bin/env python3
"""Compare the C reference and optional physical ESP32 against the golden fixture."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from project import ROOT, serial_port

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--port')
parser.add_argument('--reference-only', action='store_true', help='run on the host without connecting to USB')
args = parser.parse_args()
reports = ROOT/'reports'
reports.mkdir(exist_ok=True)
subprocess.run(['cc','-O3','-ffp-contract=off',str(ROOT/'tests/reference_tokens.c'),
                '-o',str(reports/'reference-tokens'),'-lm'],check=True)
raw = subprocess.check_output([str(reports/'reference-tokens'),str(ROOT/'models/stories260K.bin'),
                               str(ROOT/'models/tok512.bin'),'Once upon a time','32'],text=True)
reference = json.loads(raw)
fixture = json.loads((ROOT/'tests/fixtures/reference.json').read_text())
for key in ('prompt_tokens','generated_tokens'):
    if reference[key] != fixture[key]:
        raise AssertionError('Reference mismatch: '+key)
(reports/'reference-tokens.json').write_text(json.dumps(reference,indent=2)+'\n')
print('Host C reference: tokenizer and all 32 greedy tokens match.',flush=True)
if args.reference_only:
    raise SystemExit(0)

port = serial_port(args.port)
try:
    result = subprocess.run([sys.executable,'-m','mpremote','connect',port,'run',
                              str(ROOT/'tests/native_on_device.py')],capture_output=True,text=True,timeout=120)
    (reports/'native-test.log').write_text(result.stdout+result.stderr)
    result.check_returncode()
    board = json.loads(next(line.split('=',1)[1] for line in result.stdout.splitlines()
                            if line.startswith('NATIVE_RESULT=')))
    error = max(abs(a-b) for a,b in zip(board['first_logits'],reference['first_logits']))
    manifest = json.loads((ROOT/'models/manifest.json').read_text())['weights_and_tokenizer']
    checks = {'tokenizer_match':board['prompt_tokens']==reference['prompt_tokens'],
              'all_32_greedy_tokens_match':board['generated_tokens']==reference['generated_tokens'],
              'weights_checksum':board['weights_sha256']==manifest['stories260K.bin']['sha256'],
              'tokenizer_checksum':board['tokenizer_sha256']==manifest['tok512.bin']['sha256']}
    if not all(checks.values()) or error >= 0.0001:
        raise AssertionError('Native inference mismatch: '+str(checks)+'; logit error='+str(error))
    board['verification'] = dict(checks,max_logit_abs_error=error)
    (reports/'native-test.json').write_text(json.dumps(board,indent=2)+'\n')
    print('Physical ESP32: reference and checksums match; max logit error:',error)
    print('Performance:',board['stats'])
finally:
    subprocess.run([sys.executable,'-m','mpremote','connect',port,'reset'],check=True,timeout=20)
