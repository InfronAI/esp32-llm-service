# HTTP API 与调用示例

[English](api.md) | **简体中文**

Base URL 为 `http://<ESP32_IP>:8000/v1`，模型 ID 为 `tinystories-260k`。Key 从本机 `reports/access.json` 读取，使用 `Authorization: Bearer <key>`。健康检查的地址不含 `/v1`，且不要求 Key。

## curl

```sh
export ESP32_IP=192.168.1.50
export ESP32_API_KEY='REPLACE_WITH_YOUR_LOCAL_KEY'

curl --noproxy '*' "http://$ESP32_IP:8000/health"
curl --noproxy '*' "http://$ESP32_IP:8000/v1/models" \
  -H "Authorization: Bearer $ESP32_API_KEY"
```

普通生成：

```sh
curl --noproxy '*' "http://$ESP32_IP:8000/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ESP32_API_KEY" \
  -d '{"model":"tinystories-260k","messages":[{"role":"user","content":"Once upon a time"}],"max_tokens":32,"temperature":0}'
```

SSE 流式生成，`-N` 关闭 curl 输出缓冲：

```sh
curl -N --noproxy '*' "http://$ESP32_IP:8000/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ESP32_API_KEY" \
  -d '{"model":"tinystories-260k","messages":[{"role":"user","content":"Once upon a time"}],"max_tokens":64,"temperature":0,"stream":true,"stream_options":{"include_usage":true}}'
```

SSE 使用 `data: <JSON>` 和空行分隔，先返回 assistant role，再返回内容 delta，最后返回 finish reason；开启 include_usage 时追加一个空 choices 的 usage chunk，随后为 `data: [DONE]`。

基础文本续写接口：

```sh
curl --noproxy '*' "http://$ESP32_IP:8000/v1/completions" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ESP32_API_KEY" \
  -d '{"model":"tinystories-260k","prompt":"Once upon a time","max_tokens":32,"temperature":0}'
```

## 官方 OpenAI SDK

项目固定使用 3.35.1，其 HTTP 实现依赖 httpx2。下面使用 SDK 导出的客户端类，避免直接依赖传输库名称：

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

可直接运行的流式示例是 `scripts/chat.py`：

```sh
.venv/bin/python scripts/chat.py 'Once upon a time' --tokens 64
.venv/bin/python scripts/chat.py --url http://192.168.4.1:8000/v1
```

## 支持范围

| 参数或特性 | 行为 |
| --- | --- |
| `model` | `tinystories-260k`；兼容别名 `esp32-llm` |
| `messages` | 1–16 条纯文本消息，role 可为 user/assistant/system/developer |
| 提示词构造 | 顺序连接所有 content，中间两个换行；没有聊天 role 模板 |
| `prompt` | `/v1/completions` 接受单个字符串 |
| `max_tokens` / `max_completion_tokens` | 默认 64，范围 1–256；两者不能同时设置 |
| context | 提示词含 BOS 与输出预算合计最多 512 token；超出返回 400 |
| `temperature` | 0–2，默认 0.8；0 为贪心选择 |
| `top_p` | 大于 0 且不大于 1，默认 0.9；实现最小接受值为 0.000001 |
| `seed` | 0–4294967295，固定 seed 可复现采样；0 与 1 使用相同初始状态 |
| `stop` | 最多 4 个非空字符串，每个最多 64 UTF-8 字节，匹配内容不返回 |
| `stream` | 布尔值；支持 SSE 和 `stream_options.include_usage` |
| `n` | 仅 1 |
| penalties / logprobs / store | 仅接受零 penalty、关闭 logprobs 和关闭 store |
| `user` / `metadata` | 接受但不存储，不影响生成 |

请求头最多 4096 字节，请求体最多 8192 字节，提示词最多 1536 UTF-8 字节。请求体需有 Content-Length，chunked request body 不支持。响应完成后关闭连接，没有 keep-alive。

不支持 tools/function calling、图像或音频 content、JSON schema、embedding、Responses API、模型训练或文件上传。未知参数明确返回错误。[其他模型列表](models.zh-CN.md)仅供选型，不代表本 API 接受那些模型 ID。

## 响应与错误

普通响应包含 `id`、`object`、`created`、`model`、`choices` 和 `usage`。生成达到预算时 finish reason 为 `length`，遇到 EOS/BOS 边界或 stop 字符串时为 `stop`。completion token 计数包含实际采样到的终止 token 或被 stop 隐藏的内容，不等于可见字符串重新分词的长度。

| 状态 | 常见原因 |
| --- | --- |
| 200 | 请求成功 |
| 400 | 参数、JSON、上下文或 Content-Type 不合法 |
| 401 | Key 缺失或不匹配 |
| 404 | 模型或路由不存在 |
| 405 | 生成端点未使用 POST |
| 413 | HTTP 头或请求体超限 |
| 500 | 板上运行时错误；查看 USB 日志 |

错误使用 `{"error":{"message":"...","type":"...","param":null,"code":"..."}}` 结构；服务器内部错误的可选字段可能省略。运行时有 busy 检查，但 HTTP 主循环本身是串行的；正常并发请求通常排队，不能依赖 429 来做并发控制。

`/health` 返回模型容量、网络状态、剩余堆、累计请求数和最近一次推理统计。`tokens_per_second` 计算为采样 token 数 / 包含提示词处理的生成总时间，不能当成剔除 prefill 的纯 decode 速度。`created` 来自板载 RTC；部署时校时，断电后可能需要重新校时。

接口格式依据 OpenAI Docs 的 [Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) 和[流式事件](https://developers.openai.com/api/reference/resources/chat/subresources/completions/streaming-events)。实际兼容范围以本页和源码为准。
