#!/usr/bin/env python3
"""Integration checks over the Mac's real LAN connection to the ESP32."""
import concurrent.futures
import argparse
import json
from pathlib import Path
import socket
import time
from urllib.parse import urlsplit
import httpx2 as httpx
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
access = json.loads((ROOT/'reports/access.json').read_text())
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--url', help='override saved OpenAI base URL')
args = parser.parse_args()
if args.url:
    access['base_url'] = args.url.rstrip('/')
url = access['base_url'].removesuffix('/v1')
http = httpx.Client(base_url=url, trust_env=False, timeout=120)
client = OpenAI(base_url=access['base_url'], api_key=access['api_key'], max_retries=0,
                http_client=httpx.Client(trust_env=False, timeout=120))
auth = {'Authorization':'Bearer '+access['api_key']}
payload = {'model':access['model'], 'messages':[{'role':'user','content':'Once upon a time'}],
           'max_tokens':32, 'temperature':0}
passed = []
report = {'passed':passed}

def check(name, condition):
    if not condition:
        raise AssertionError(name)
    passed.append(name)
    print('PASS', name, flush=True)

def health():
    result = http.get('/health')
    result.raise_for_status()
    return result.json()

def until(conn, marker):
    data = b''
    while marker not in data:
        part = conn.recv(4096)
        if not part:
            raise EOFError(repr(data))
        data += part
    return data

before = health()
check('LAN health reports local model and connected station', before['inference']=='on-device' and before['network']['connected'])
check('API requires authentication', http.get('/v1/models').status_code==401)
check('SDK lists installed model', client.models.list().data[0].id==access['model'])
started = time.monotonic()
response = client.chat.completions.create(**payload)
report['nonstream_wall_seconds'] = round(time.monotonic()-started,3)
reference = json.loads((ROOT/'tests/fixtures/reference.json').read_text())
text = response.choices[0].message.content
check('SDK chat output matches verified C reference', text==reference['output'])
check('SDK usage and length finish reason', response.usage.prompt_tokens==5 and response.usage.completion_tokens==32 and response.choices[0].finish_reason=='length')
report['response'] = response.model_dump()
report['benchmark'] = health()['last_inference']

chunks = list(client.chat.completions.create(**payload, stream=True, stream_options={'include_usage':True}))
stream_text = ''.join(c.choices[0].delta.content or '' for c in chunks if c.choices)
check('SDK SSE output matches nonstream', stream_text==text)
check('SSE assistant role and final finish reason', chunks[0].choices[0].delta.role=='assistant' and chunks[-2].choices[0].finish_reason=='length')
check('SSE final usage chunk', not chunks[-1].choices and chunks[-1].usage.total_tokens==37)
check('SSE one completion id across chunks', len({c.id for c in chunks})==1)
legacy = client.completions.create(model=access['model'], prompt='Once upon a time', max_tokens=32, temperature=0)
check('SDK legacy completions output', legacy.choices[0].text==text)
for streaming in (False, True):
    stopped = client.chat.completions.create(**payload, stop='named Lily', stream=streaming)
    if streaming:
        stop_chunks = list(stopped)
        stop_text = ''.join(c.choices[0].delta.content or '' for c in stop_chunks)
        reason = stop_chunks[-1].choices[0].finish_reason
    else:
        stop_text = stopped.choices[0].message.content
        reason = stopped.choices[0].finish_reason
    check('multi-token stop string, stream='+str(streaming), stop_text==text.split('named Lily')[0] and reason=='stop')

seeded = dict(payload, temperature=0.8, top_p=0.9, seed=12345, max_tokens=16)
a = client.chat.completions.create(**seeded).choices[0].message.content
b = client.chat.completions.create(**seeded).choices[0].message.content
check('sampling seed is reproducible', a==b)
report['sampled_output'] = a

for name, changes, expected in [
    ('unknown model', {'model':'missing'},404),
    ('empty message list', {'messages':[]},400),
    ('unsupported tools', {'tools':[]},400),
    ('output bound', {'max_tokens':257},400),
    ('invalid temperature', {'temperature':-1},400),
    ('invalid streaming type', {'stream':'true'},400),
    ('context overflow', {'messages':[{'role':'user','content':'中文汉字'*100}]},400),
    ('NUL prompt', {'messages':[{'role':'user','content':'\x00'}]},400),
    ('multiple completions', {'n':2},400),
    ('invalid stop type', {'stop':[123]},400),
    ('conflicting token limits', {'max_completion_tokens':32},400),
]:
    r = http.post('/v1/chat/completions',headers=auth,json=dict(payload,**changes))
    check('reject '+name, r.status_code==expected and 'error' in r.json())
bad = http.post('/v1/chat/completions',headers=dict(auth,**{'Content-Type':'application/json'}),content='{')
check('malformed JSON returns structured error',bad.status_code==400 and 'error' in bad.json())
check('unknown route', http.get('/unknown',headers=auth).status_code==404)

unicode_result = client.chat.completions.create(model=access['model'],messages=[{'role':'user','content':'你好🌍'}],max_tokens=4,temperature=0)
check('Unicode prompt can be tokenized and decoded', unicode_result.usage.completion_tokens==4)

# Authenticate and execute commands while the background inference thread works.
with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
    work = pool.submit(client.chat.completions.create, **dict(payload,max_tokens=128))
    with socket.create_connection((urlsplit(url).hostname,23),timeout=15) as conn:
        until(conn,b'login: ')
        conn.sendall((access['user']+'\r\n').encode())
        until(conn,b'Password: ')
        conn.sendall((access['password']+'\r\n').encode())
        check('shell login during inference',b'Welcome!' in until(conn,b'$ '))
        conn.sendall(b'pwd\r\n')
        check('shell command during inference',b'\r\n/home\r\n' in until(conn,b'$ '))
        conn.sendall(b'exit\r\n')
    check('inference completes alongside shell',len(work.result().choices)==1)

# An interrupted SSE client must release the generator and permit another request.
with http.stream('POST','/v1/chat/completions',headers=auth,json=dict(payload,stream=True,max_tokens=256)) as r:
    check('stream opens with SSE content type',r.status_code==200 and r.headers['content-type'].startswith('text/event-stream'))
    for line in r.iter_lines():
        if line.startswith('data:'):
            break
check('server recovers after streaming client disconnect',health()['status']=='ok')
after_disconnect = client.chat.completions.create(**dict(payload,max_tokens=4))
check('generation works after client disconnect',after_disconnect.usage.completion_tokens==4)
after = health()
check('ample free PSRAM after repeated requests',after['heap_free']>4_000_000)
report['health_after'] = after
report['sdk_version'] = __import__('openai').__version__
report['checks'] = len(passed)
(ROOT/'reports/llm-test.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('All',len(passed),'checks passed.',flush=True)
