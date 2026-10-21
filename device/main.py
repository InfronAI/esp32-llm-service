import time
import sys

# A short recovery window lets mpremote interrupt a broken application over USB.
time.sleep(2)
try:
    import json
    import net
    import _thread
    import llm
    import api
    net.setup()
    with open('/settings.json') as handle:
        config = json.load(handle)
    model = llm.Model()
    _thread.stack_size(32768)
    _thread.start_new_thread(api.serve, (model, config))
except Exception as exc:
    sys.print_exception(exc)
    print('LLM service failed to start; shell remains available for repair.')

try:
    import shell
    shell.serve()
except Exception as exc:
    sys.print_exception(exc)
    print("Shell stopped. USB MicroPython REPL remains available.")
