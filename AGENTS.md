# Working on this repository

- Read README.md and the relevant document in docs/ before changing deployment behavior.
- Target: ESP32-S3 with 16 MB flash and 8 MB octal PSRAM, MicroPython 1.29.0. The native module is Xtensa windowed ABI and accepts only the pinned 260K model layout.
- Keep credentials in ignored device/settings.json and reports/access.json. Use scripts/configure.py for new installations. Never publish device backups, real passwords, salts, hashes or API keys.
- Use the project .venv. Host checks: `python -m unittest discover -s tests -p 'test_host.py'`, `python scripts/check_repo.py`, and `python scripts/check_native.py --reference-only` after model download.
- Firmware flashing erases board state; distinguish it from updating files with scripts/deploy.py. Check the selected USB device and preserve a backup before a first installation. Follow the user's current authorization for hardware operations.
- USB REPL tests interrupt network services. Reset the board after testing and report whether physical hardware was available.
- Keep the shell on the main interpreter thread so Ctrl-C can interrupt user Python. The HTTP service runs in a background thread and handles one request at a time.
- Check native changes against the independent C reference. Do not replace real model inference with canned responses or an unrequested remote backend.
- Document API limitations: TinyStories continuation, 512-token context, 256-token output, no tools, vision, embeddings or Responses API.
