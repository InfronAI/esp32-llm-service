# HTTP API and examples

**English** | [简体中文](api.zh-CN.md)

The base URL is `http://<ESP32_IP>:8000/v1`; the model ID is `tinystories-260k`. Read the key from local `reports/access.json` and send `Authorization: Bearer <key>`. The health endpoint has no `/v1` prefix and does not require authentication.

## curl

```sh
export ESP32_IP=192.168.1.50
export ESP32_API_KEY='REPLACE_WITH_YOUR_LOCAL_KEY'

curl --noproxy '*' "http://$ESP32_IP:8000/health"
curl --noproxy '*' "http://$ESP32_IP:8000/v1/models" \
  -H "Authorization: Bearer $ESP32_API_KEY"
```

Non-streaming generation:

```sh
curl --noproxy '*' "http://$ESP32_IP:8000/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ESP32_API_KEY" \
  -d '{"model":"tinystories-260k","messages":[{"role":"user","content":"Once upon a time"}],"max_tokens":32,"temperature":0}'
```

SSE streaming; `-N` disables curl output buffering:

```sh
curl -N --noproxy '*' "http://$ESP32_IP:8000/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ESP32_API_KEY" \
  -d '{"model":"tinystories-260k","messages":[{"role":"user","content":"Once upon a time"}],"max_tokens":64,"temperature":0,"stream":true,"stream_options":{"include_usage":true}}'
```

SSE uses `data: <JSON>` separated by blank lines. The assistant role arrives first, followed by content deltas and a finish reason. With include_usage enabled, an additional usage chunk has empty choices; `data: [DONE]` ends the stream.

The text completion endpoint:

```sh
curl --noproxy '*' "http://$ESP32_IP:8000/v1/completions" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ESP32_API_KEY" \
  -d '{"model":"tinystories-260k","prompt":"Once upon a time","max_tokens":32,"temperature":0}'
```

## Official OpenAI SDK

The project pins SDK 3.35.1, whose HTTP implementation depends on httpx2. Use the SDK's exported client class without depending directly on the transport package name:

```python
import json
from openai import OpenAI, DefaultHttpxClient

with open('reports/access.json') as handle:
    access = json.load(handle)
client = OpenAI(
    base_url=access['base_url'],
    api_key=access['api_key'],
    http_client=DefaultHttpxClient(trust_env=False, timeout=120),
    max_retries=0,
)
result = client.chat.completions.create(
    model='tinystories-260k',
    messages=[{'role':'user','content':'Once upon a time'}],
    max_tokens=32, temperature=0,
)
print(result.choices[0].message.content)
print(result.usage)
```

A runnable streaming client is provided as `scripts/chat.py`:

```sh
.venv/bin/python scripts/chat.py 'Once upon a time' --tokens 64
.venv/bin/python scripts/chat.py --url http://192.168.4.1:8000/v1
```

## Supported behavior

| Parameter or feature | Behavior |
| --- | --- |
| `model` | `tinystories-260k`; compatibility alias `esp32-llm` |
| `messages` | 1–16 plain-text messages; user/assistant/system/developer roles accepted |
| Prompt construction | All content joined in order with two newlines; no chat role template |
| `prompt` | `/v1/completions` accepts one string |
| `max_tokens` / `max_completion_tokens` | Default 64, range 1–256; cannot both be set |
| Context | Prompt including BOS plus output budget must fit within 512 tokens; otherwise 400 |
| `temperature` | 0–2, default 0.8; zero selects greedy decoding |
| `top_p` | Greater than zero and at most 1, default 0.9; implemented minimum is 0.000001 |
| `seed` | 0–4294967295; fixed seeds reproduce sampling; 0 and 1 share the initial state |
| `stop` | Up to four nonempty strings, each at most 64 UTF-8 bytes; matched text is omitted |
| `stream` | Boolean; SSE and `stream_options.include_usage` supported |
| `n` | Only 1 |
| penalties / logprobs / store | Only zero penalties, disabled logprobs, and disabled store |
| `user` / `metadata` | Accepted but not stored; no effect on generation |

Headers are limited to 4096 bytes, request bodies to 8192 bytes, and prompts to 1536 UTF-8 bytes. Bodies require Content-Length; chunked request bodies are unsupported. Connections close after the response; there is no keep-alive.

Tools/function calling, image/audio content, JSON schemas, embeddings, the Responses API, training, and file uploads are unsupported. Unknown parameters return an explicit error. The [alternative model list](models.md) is selection guidance, not additional IDs accepted by this API.

## Responses and errors

Non-streaming responses include `id`, `object`, `created`, `model`, `choices`, and `usage`. The finish reason is `length` when the output budget is exhausted and `stop` at an EOS/BOS boundary or matched stop string. Completion-token usage includes sampled terminal tokens or content hidden by stop matching; it is not the token count obtained by retokenizing visible text.

| Status | Common cause |
| --- | --- |
| 200 | Success |
| 400 | Invalid parameters, JSON, context length, or Content-Type |
| 401 | Missing or incorrect key |
| 404 | Unknown model or route |
| 405 | Generation endpoint called without POST |
| 413 | Header or body exceeds its limit |
| 500 | On-board runtime error; inspect USB logs |

Errors use `{"error":{"message":"...","type":"...","param":null,"code":"..."}}`; optional fields may be omitted for internal errors. A runtime busy check exists, but the HTTP loop itself is sequential. Concurrent requests usually queue, so do not rely on 429 for concurrency control.

`/health` reports model capacity, network state, free heap, cumulative requests, and the latest inference statistics. `tokens_per_second` divides sampled token count by generation time including prompt processing; it is not decode-only throughput. `created` comes from the RTC, which deployment sets; power loss can require resynchronization.

The format follows OpenAI Docs for [Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) and [streaming events](https://developers.openai.com/api/reference/resources/chat/subresources/completions/streaming-events). This page and the source define the implemented subset.
