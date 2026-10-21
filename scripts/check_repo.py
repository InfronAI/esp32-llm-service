#!/usr/bin/env python3
"""Check publishable paths, Markdown links, syntax, and accidental private values."""
import ast
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote
from project import ROOT

listed = subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=ROOT)
paths = sorted({Path(p.decode()) for p in listed.split(b'\0') if p})
failures = []
private_values = set()
for filename in ('device/settings.json','reports/access.json'):
    path = ROOT/filename
    if path.exists():
        data = json.loads(path.read_text())
        for key in ('api_key','password','wifi_password','sta_password','password_hash','salt','sta_ssid'):
            value = data.get(key)
            if isinstance(value,str) and len(value) >= 8:
                private_values.add(value)

for relative in paths:
    path = ROOT/relative
    name = relative.as_posix()
    if not path.is_file():
        failures.append(name+': tracked path missing')
        continue
    if name.startswith(('reports/','backups/','.venv/','third_party/')) or name=='device/settings.json' or path.suffix in ('.bin','.mpy','.pyc'):
        failures.append(name+': private/generated path included')
        continue
    try:
        source = path.read_text()
    except UnicodeDecodeError:
        failures.append(name+': unexpected binary file')
        continue
    if any(value in source for value in private_values):
        failures.append(name+': matches a private configuration value')
    if re.search(r'esp32-[a-f0-9]{32}',source) or str(Path.home())+'/' in source:
        failures.append(name+': embedded local credential or absolute home path')
    if path.suffix=='.py':
        try:
            ast.parse(source,filename=name)
        except SyntaxError as exc:
            failures.append(name+': '+str(exc))
    if path.suffix=='.md':
        # Ignore fenced examples; check actual relative document/file links.
        visible = re.sub(r'```.*?```','',source,flags=re.S)
        for target in re.findall(r'\]\(([^)]+)\)',visible):
            target=target.strip('<>').split('#',1)[0]
            if not target or '://' in target or target.startswith('mailto:'):
                continue
            if not (path.parent/unquote(target)).exists():
                failures.append(name+': broken relative link '+target)

for private in ('device/settings.json','reports/access.json','backups/original.bin','models/stories260K.bin','native/tinyllm_native.mpy'):
    if subprocess.run(['git','check-ignore','-q','--no-index',private],cwd=ROOT).returncode:
        failures.append(private+': missing ignore rule')

if failures:
    raise SystemExit('\n'.join(failures))
print('Repository checks passed:',len(paths),'source/document files; no private values found.')
