# Validation methods and recorded measurements

**English** | [简体中文](validation.zh-CN.md)

## Test layers

| Layer | Command | Device required? |
| --- | --- | --- |
| Python syntax | `.venv/bin/python -m compileall -q device scripts tests` | No |
| Configuration / download integrity | `.venv/bin/python -m unittest discover -s tests -p 'test_host.py'` | No |
| Documentation and publication content | `.venv/bin/python scripts/check_repo.py` | No |
| Independent C reference | `.venv/bin/python scripts/check_native.py --reference-only` | No; local model files required |
| Native inference comparison | `.venv/bin/python scripts/check_native.py --port <port>` | Yes, USB |
| End-to-end API | `.venv/bin/python scripts/check_llm.py` | Yes, reachable LAN |
| Shell loopback | `.venv/bin/python scripts/check_device.py <port>` | Yes, USB controls on-board TCP |

Once enabled, the [CI template](../ci/host-checks.yml) runs the first four categories in GitHub Actions. It includes neither ESP32 simulation nor physical-board tests. Initial publishing credentials lacked workflow permission, so the template remains in `ci/` and does not run automatically. See [activation instructions](../ci/README.md). USB tests pause the network application; `check_native.py` restarts automatically, while the original shell test requires `mpremote connect <port> reset` afterward.

## Independent reference

`tests/reference_run.c` preserves the upstream karpathy/llama2.c implementation; `reference_tokens.c` only provides a JSON output entry point. The fixed prompt is `Once upon a time`, with temperature zero and 32 output tokens. The verified fixture is `tests/fixtures/reference.json`.

Device checks compare prompt token IDs, 32 output token IDs, the first 512-element logit vector, and SHA-256 hashes for weights and tokenizer. Floating-point tolerance is `1e-4`. This checks actual execution of tokenization, weight mapping, matrix multiplication, RoPE, and attention.

## API coverage

The 34 LAN checks cover authentication, model listing, official SDK JSON/SSE calls, usage and finish reasons, stop strings spanning tokens, fixed seeds, legacy completions, invalid JSON/parameters, Unicode input, recovery after a streaming client disconnects, and shell login/commands during inference.

Scripts read private `reports/access.json` and write results to the same directory. Use `--url` to override the API address temporarily. Automated shell tests assume the default username `esp32`.

## Hardware results from 2026-10-21

Recorded on ESP32-S3 rev 0.2 / 240 MHz / 16 MB Flash / 8 MB Octal PSRAM, running MicroPython 1.29.0:

- Independent reference: all 32 tokens matched; maximum absolute logit error approximately `8.45e-6`.
- Model and tokenizer: SHA-256 matched the manifest.
- Native generation: 5-token prompt and 32-token output in 1.092 seconds; first token at 116 ms.
- On-board generation during HTTP testing: the same lengths in 1.071 seconds, about 29.88 tokens/s; full Mac request about 1.70 seconds.
- 128-token generation: about 25.67 tokens/s.
- All 34 SDK/LAN and 30 original shell checks passed; Wi-Fi and API recovery after restart was verified.

The [sanitized machine-readable record](validation/2026-10-21.json) retains checks and performance data while omitting personal network details, device identifiers, and credentials. USB was not reconnected during publication preparation. These are prior physical-device measurements, not new results from documentation checks.

Speed includes prompt processing and sampling, not just decoding. Context length, sampling, network conditions, and compiler changes can affect results. One matching fixture is not a comprehensive model quality evaluation. Alternative models in the [selection guide](models.md) have upstream evidence only and are outside this hardware validation record.
