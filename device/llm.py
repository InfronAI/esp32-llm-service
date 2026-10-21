"""TinyStories 260K: native C Transformer with Python BPE and sampling."""
import array
import struct
import math
import os
import time
import gc
import tinyllm_native

MODEL_ID = 'tinystories-260k'
CONTEXT = 512


class Tokenizer:
    def __init__(self, path='/models/tok512.bin'):
        self.vocab = []
        self.scores = []
        with open(path, 'rb') as handle:
            self.max_length = struct.unpack('<i', handle.read(4))[0]
            for _ in range(512):
                score, size = struct.unpack('<fi', handle.read(8))
                if size < 0 or size > 128:
                    raise ValueError('invalid tokenizer')
                self.scores.append(score)
                self.vocab.append(handle.read(size))
        self.lookup = {piece: i for i, piece in enumerate(self.vocab)}

    def encode(self, text):
        tokens = [1]
        if text:
            tokens.append(self.lookup[b' '])
        for char in text:
            raw = char.encode('utf-8')
            token = self.lookup.get(raw)
            if token is None:
                tokens.extend(value + 3 for value in raw)
            else:
                tokens.append(token)
        while True:
            best, best_id, best_pos = -1e10, -1, -1
            for i in range(len(tokens) - 1):
                candidate = self.lookup.get(self.vocab[tokens[i]] + self.vocab[tokens[i+1]])
                if candidate is not None and self.scores[candidate] > best:
                    best, best_id, best_pos = self.scores[candidate], candidate, i
            if best_pos < 0:
                return tokens
            tokens[best_pos:best_pos+2] = [best_id]

    def decode(self, previous, token):
        piece = self.vocab[token]
        if previous == 1 and piece.startswith(b' '):
            piece = piece[1:]
        if piece.startswith(b'<0x') and piece.endswith(b'>'):
            return bytes([int(piece[3:5], 16)])
        return piece


class Model:
    def __init__(self):
        self.tokenizer = Tokenizer()
        size = os.stat('/models/stories260K.bin')[6]
        self.weights = bytearray(size)
        with open('/models/stories260K.bin', 'rb') as handle:
            if handle.readinto(self.weights) != size:
                raise ValueError('incomplete checkpoint')
        self.state = array.array('f', bytearray(4*tinyllm_native.state_size(self.weights)))
        self.logits = memoryview(self.state)[-512:]
        self.requests = 0
        self.generated_tokens = 0
        self.last_stats = None
        self.busy = False
        gc.collect()
        print('Loaded', MODEL_ID, 'weights', size, 'state', len(self.state)*4, 'free heap', gc.mem_free())

    def sample(self, temperature, top_p, rng):
        logits = self.logits
        if temperature == 0:
            return max(range(512), key=lambda i: logits[i])
        maximum = max(logits)
        scores = [math.exp((value-maximum)/temperature) for value in logits]
        order = sorted(range(512), key=lambda i: scores[i], reverse=True)
        limit = sum(scores) * top_p
        total, end = 0.0, 0
        for i in order:
            total += scores[i]
            end += 1
            if total >= limit:
                break
        value = rng[0]
        value ^= (value << 13) & 0xffffffff
        value ^= value >> 17
        value ^= (value << 5) & 0xffffffff
        rng[0] = value & 0xffffffff
        target = (rng[0] / 4294967296.0) * total
        cumulative = 0.0
        for i in order[:end]:
            cumulative += scores[i]
            if cumulative >= target:
                return i
        return order[end-1]

    def generate(self, tokens, max_tokens, temperature, top_p, seed):
        """Yield decoded bytes; update counts after consuming or closing generator."""
        if self.busy:
            raise RuntimeError('model is busy')
        self.busy = True
        started = time.ticks_ms()
        count = 0
        first_token_ms = None
        reason = 'length'
        rng = [seed or 1]
        try:
            token = tokens[0]
            for position in range(len(tokens) + max_tokens - 1):
                tinyllm_native.forward(self.weights, self.state, token, position)
                if position < len(tokens)-1:
                    token = tokens[position+1]
                    time.sleep_ms(1)
                    continue
                following = self.sample(temperature, top_p, rng)
                count += 1
                if first_token_ms is None:
                    first_token_ms = time.ticks_diff(time.ticks_ms(), started)
                if following in (1, 2):
                    reason = 'stop'
                    break
                yield self.tokenizer.decode(token, following)
                token = following
                time.sleep_ms(1)
        finally:
            elapsed = time.ticks_diff(time.ticks_ms(), started)
            self.last_stats = {'prompt_tokens': len(tokens), 'completion_tokens': count,
                               'total_tokens': len(tokens)+count, 'elapsed_ms': elapsed,
                               'first_token_ms': first_token_ms, 'finish_reason': reason,
                               'tokens_per_second': round(count*1000/max(elapsed, 1), 2)}
            self.requests += 1
            self.generated_tokens += count
            self.busy = False
            gc.collect()
