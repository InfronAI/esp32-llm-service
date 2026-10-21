"""Bounded, local OpenAI Chat/Completions subset; no inference backend calls."""
import socket
import json
import time
import os
import gc
import binascii
import net
from llm import MODEL_ID, CONTEXT

MAX_BODY = 8192
MAX_HEADERS = 4096
MAX_OUTPUT = 256
EPOCH_DELTA = 946684800 if time.gmtime(0)[0] == 2000 else 0


class APIError(Exception):
    def __init__(self, message, status=400, code='invalid_request_error'):
        self.message, self.status, self.code = message, status, code


def encoded(value):
    return json.dumps(value).encode('utf-8')


def send_json(conn, status, obj):
    body = encoded(obj)
    names = {200:'OK', 400:'Bad Request', 401:'Unauthorized', 404:'Not Found',
             405:'Method Not Allowed', 408:'Request Timeout', 413:'Payload Too Large',
             429:'Too Many Requests', 500:'Internal Server Error', 503:'Service Unavailable'}
    header = 'HTTP/1.1 %d %s\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: %d\r\nConnection: close\r\n\r\n' % (status, names.get(status, 'Error'), len(body))
    conn.sendall(header.encode())
    conn.sendall(body)


def read_request(conn):
    raw = b''
    while b'\r\n\r\n' not in raw:
        data = conn.recv(512)
        if not data:
            raise APIError('Incomplete HTTP headers')
        raw += data
        if len(raw) > MAX_HEADERS + 512:
            raise APIError('HTTP headers exceed 4096 bytes', 413)
    head, body = raw.split(b'\r\n\r\n', 1)
    if len(head) > MAX_HEADERS:
        raise APIError('HTTP headers exceed 4096 bytes', 413)
    try:
        lines = head.decode().split('\r\n')
        method, path, version = lines[0].split()
        if version not in ('HTTP/1.0', 'HTTP/1.1'):
            raise ValueError()
        headers = {}
        for line in lines[1:]:
            key, value = line.split(':', 1)
            key = key.strip().lower()
            if key in headers:
                raise ValueError()
            headers[key] = value.strip()
        if 'transfer-encoding' in headers:
            raise APIError('Chunked request bodies are not supported')
        length = int(headers.get('content-length', '0'))
    except (ValueError, UnicodeError):
        raise APIError('Malformed HTTP request')
    if length < 0 or length > MAX_BODY:
        raise APIError('Request body limit is 8192 bytes', 413)
    while len(body) < length:
        data = conn.recv(min(1024, length-len(body)))
        if not data:
            raise APIError('Incomplete request body')
        body += data
    return method, path.split('?', 1)[0], headers, body[:length]


def numeric(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
        raise APIError('%s must be between %s and %s' % (name, low, high))
    return value


def validate(body, chat, model):
    try:
        req = json.loads(body)
    except (ValueError, UnicodeError):
        raise APIError('Invalid JSON body')
    if not isinstance(req, dict):
        raise APIError('Request body must be an object')
    allowed = ('model','messages','prompt','max_tokens','max_completion_tokens','temperature',
               'top_p','seed','stream','stream_options','stop','n','user','store','metadata',
               'frequency_penalty','presence_penalty','logprobs')
    for key in req:
        if key not in allowed:
            raise APIError('Unsupported parameter: ' + key)
    if req.get('model') not in (MODEL_ID, 'esp32-llm'):
        raise APIError('Unknown model; use ' + MODEL_ID, 404, 'model_not_found')
    if req.get('n', 1) != 1:
        raise APIError('Only n=1 is supported')
    if req.get('frequency_penalty', 0) != 0 or req.get('presence_penalty', 0) != 0 or req.get('logprobs'):
        raise APIError('Penalties and logprobs are not supported')
    if req.get('store', False):
        raise APIError('Response storage is not supported')
    if chat:
        messages = req.get('messages')
        if not isinstance(messages, list) or not 1 <= len(messages) <= 16:
            raise APIError('messages must contain 1 to 16 text messages')
        pieces = []
        for message in messages:
            if not isinstance(message, dict) or message.get('role') not in ('user','assistant','system','developer') or not isinstance(message.get('content'), str):
                raise APIError('Only text user/assistant/system/developer messages are supported')
            pieces.append(message['content'])
        # This is a base continuation model, with no trained chat role tokens.
        prompt = '\n\n'.join(pieces)
    else:
        prompt = req.get('prompt')
        if not isinstance(prompt, str):
            raise APIError('prompt must be a string')
    if len(prompt.encode()) > 1536:
        raise APIError('Prompt exceeds 1536 UTF-8 bytes; context is 512 tokens')
    if '\x00' in prompt:
        raise APIError('NUL characters are not supported in prompts')
    if 'max_tokens' in req and 'max_completion_tokens' in req:
        raise APIError('Set only one token limit')
    limit = req.get('max_completion_tokens', req.get('max_tokens', 64))
    if type(limit) is not int or not 1 <= limit <= MAX_OUTPUT:
        raise APIError('max_tokens must be an integer from 1 to 256')
    temperature = numeric(req.get('temperature', 0.8), 'temperature', 0, 2)
    top_p = numeric(req.get('top_p', 0.9), 'top_p', 0.000001, 1)
    seed = req.get('seed', int.from_bytes(os.urandom(4), 'little'))
    if type(seed) is not int or not 0 <= seed <= 0xffffffff:
        raise APIError('seed must be an unsigned 32-bit integer')
    stream = req.get('stream', False)
    if type(stream) is not bool:
        raise APIError('stream must be a boolean')
    options = req.get('stream_options') or {}
    if not isinstance(options, dict) or any(key != 'include_usage' for key in options) or type(options.get('include_usage', False)) is not bool:
        raise APIError('Only stream_options.include_usage is supported')
    stops = req.get('stop') or []
    if isinstance(stops, str):
        stops = [stops]
    if not isinstance(stops, list) or len(stops) > 4 or any(not isinstance(s, str) or not 1 <= len(s.encode()) <= 64 for s in stops):
        raise APIError('stop must contain up to four nonempty strings of at most 64 bytes')
    tokens = model.tokenizer.encode(prompt)
    if len(tokens)+limit > CONTEXT:
        raise APIError('Context limit is 512 tokens: prompt uses %d, requested output %d' % (len(tokens), limit))
    return tokens, limit, temperature, top_p, seed, stream, options.get('include_usage', False), [s.encode() for s in stops]


class UTF8:
    def __init__(self):
        self.pending = b''

    def decode(self, raw, final=False):
        raw = self.pending + raw
        self.pending = b''
        result, i = [], 0
        while i < len(raw):
            first = raw[i]
            size = 1 if first < 0x80 else 2 if 0xc2 <= first <= 0xdf else 3 if 0xe0 <= first <= 0xef else 4 if 0xf0 <= first <= 0xf4 else 0
            if size and i+size > len(raw) and not final:
                self.pending = raw[i:]
                break
            try:
                if not size or i+size > len(raw):
                    raise ValueError()
                piece = raw[i:i+size].decode('utf-8')
            except (UnicodeError, ValueError):
                result.append('\ufffd')
                i += 1
            else:
                result.append(piece)
                i += size
        return ''.join(result)


def completion(conn, body, chat, model):
    tokens, limit, temperature, top_p, seed, stream, include_usage, stops = validate(body, chat, model)
    ident = 'chatcmpl-' + binascii.hexlify(os.urandom(8)).decode()
    created = time.time() + EPOCH_DELTA
    if model.busy:
        raise APIError('One generation at a time is supported', 429, 'rate_limit_error')
    base = {'id': ident, 'created': created, 'model': MODEL_ID,
            'object': 'chat.completion.chunk' if chat and stream else 'chat.completion' if chat else 'text_completion'}
    def event(choices, usage=None):
        obj = dict(base)
        obj['choices'] = choices
        if include_usage:
            obj['usage'] = usage
        conn.sendall(b'data: ' + encoded(obj) + b'\n\n')

    output = []
    def deliver(text):
        if not text:
            return
        if stream:
            choice = {'index': 0, 'finish_reason': None, 'logprobs': None}
            choice['delta' if chat else 'text'] = {'content': text} if chat else text
            event([choice])
        else:
            output.append(text)

    if stream:
        conn.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: text/event-stream; charset=utf-8\r\nCache-Control: no-cache\r\nConnection: close\r\n\r\n')
        if chat:
            event([{'index': 0, 'delta': {'role':'assistant','content':''}, 'finish_reason':None, 'logprobs':None}])
    generator = model.generate(tokens, limit, temperature, top_p, seed)
    decoder = UTF8()
    pending = b''
    keep = max([len(s) for s in stops] + [1]) - 1
    stopped = False
    try:
        for raw in generator:
            pending += raw
            found = [pending.find(stop) for stop in stops if stop in pending]
            if found:
                deliver(decoder.decode(pending[:min(found)], final=True))
                pending = b''
                stopped = True
                break
            available = len(pending)-keep
            if available > 0:
                deliver(decoder.decode(pending[:available]))
                pending = pending[available:]
        if not stopped:
            deliver(decoder.decode(pending, final=True))
    finally:
        generator.close()
    stats = model.last_stats
    finish = 'stop' if stopped else stats['finish_reason']
    stats['finish_reason'] = finish
    usage = {key: stats[key] for key in ('prompt_tokens','completion_tokens','total_tokens')}
    if stream:
        choice = {'index': 0, 'finish_reason': finish, 'logprobs': None}
        choice['delta' if chat else 'text'] = {} if chat else ''
        event([choice])
        if include_usage:
            event([], usage)
        conn.sendall(b'data: [DONE]\n\n')
    else:
        choice = {'index':0, 'finish_reason':finish, 'logprobs':None}
        choice['message' if chat else 'text'] = {'role':'assistant','content':''.join(output)} if chat else ''.join(output)
        base['choices'], base['usage'] = [choice], usage
        send_json(conn, 200, base)
    print('LLM request:', stats)


def serve(model, config):
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(('0.0.0.0', config.get('api_port', 8000)))
    listener.listen(2)
    print('Local LLM API ready: http://%s:%d/v1' % (net.status()['ip'], config.get('api_port', 8000)))
    while True:
        conn, peer = listener.accept()
        conn.settimeout(5)
        try:
            method, path, headers, body = read_request(conn)
            if method == 'GET' and path == '/health':
                send_json(conn, 200, {'status':'ok', 'inference':'on-device', 'engine':'native-c-llama2',
                    'model':MODEL_ID, 'parameters':260032, 'context_length':CONTEXT,
                    'max_output_tokens':MAX_OUTPUT, 'heap_free':gc.mem_free(), 'network':net.status(),
                    'requests':model.requests, 'last_inference':model.last_stats,
                    'capabilities':{'streaming':True, 'tools':False, 'vision':False, 'chat_trained':False},
                    'prompt_format':'message text joined with two newlines; TinyStories continuation'})
                continue
            if headers.get('authorization') != 'Bearer ' + config['api_key']:
                raise APIError('Invalid or missing API key', 401, 'invalid_api_key')
            if method == 'GET' and path == '/v1/models':
                send_json(conn, 200, {'object':'list', 'data':[{'id':MODEL_ID, 'object':'model', 'created':0, 'owned_by':'local-esp32'}]})
            elif path in ('/v1/chat/completions', '/v1/completions'):
                if method != 'POST':
                    raise APIError('Use POST for this endpoint', 405)
                if headers.get('content-type','').split(';')[0].strip().lower() != 'application/json':
                    raise APIError('Content-Type must be application/json')
                completion(conn, body, path == '/v1/chat/completions', model)
            else:
                raise APIError('Unknown endpoint', 404)
        except APIError as exc:
            try:
                send_json(conn, exc.status, {'error':{'message':exc.message, 'type':exc.code, 'param':None, 'code':exc.code}})
            except OSError:
                pass
        except OSError as exc:
            print('HTTP client disconnected/timed out:', exc)
        except Exception as exc:
            import sys
            sys.print_exception(exc)
            try:
                send_json(conn, 500, {'error':{'message':'Local inference failure', 'type':'server_error', 'code':'server_error'}})
            except OSError:
                pass
        finally:
            conn.close()
            gc.collect()
