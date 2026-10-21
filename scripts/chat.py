#!/usr/bin/env python3
"""Stream a story from the ESP32 using the official OpenAI Python SDK."""
import argparse
import json
from pathlib import Path
from openai import OpenAI
import httpx2 as httpx

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('prompt', nargs='?', default='Once upon a time')
parser.add_argument('--url', help='override base URL, e.g. http://192.168.4.1:8000/v1')
parser.add_argument('--tokens', type=int, default=64)
args = parser.parse_args()
access = json.loads((Path(__file__).resolve().parents[1]/'reports/access.json').read_text())
client = OpenAI(base_url=args.url or access['base_url'], api_key=access['api_key'], timeout=120, max_retries=0,
                http_client=httpx.Client(trust_env=False, timeout=120))
print(args.prompt, end='', flush=True)
stream = client.chat.completions.create(model=access['model'], messages=[{'role':'user','content':args.prompt}],
    max_tokens=args.tokens, temperature=0, stream=True, stream_options={'include_usage':True})
for chunk in stream:
    if chunk.choices:
        print(chunk.choices[0].delta.content or '', end='', flush=True)
print()
