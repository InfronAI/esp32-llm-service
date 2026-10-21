import json, hashlib, binascii, gc
import llm, tinyllm_native

def digest(path):
    result = hashlib.sha256()
    with open(path, 'rb') as handle:
        while True:
            part = handle.read(8192)
            if not part:
                break
            result.update(part)
    return binascii.hexlify(result.digest()).decode()

model = llm.Model()
prompt = model.tokenizer.encode('Once upon a time')
for position, token in enumerate(prompt):
    tinyllm_native.forward(model.weights, model.state, token, position)
first_logits = list(model.logits)
generated = []
for i in range(32):
    following = model.sample(0, 1, [1])
    generated.append(following)
    if following in (1, 2):
        break
    if i < 31:
        tinyllm_native.forward(model.weights, model.state, following, len(prompt)+i)
output = b''.join(model.generate(prompt, 32, 0, 1, 1)).decode()
print('NATIVE_RESULT=' + json.dumps({'prompt_tokens':prompt, 'first_logits':first_logits,
    'generated_tokens':generated, 'output':output, 'stats':model.last_stats,
    'weights_sha256':digest('/models/stories260K.bin'),
    'tokenizer_sha256':digest('/models/tok512.bin'), 'heap_free':gc.mem_free()}))
