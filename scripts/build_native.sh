#!/bin/sh
set -eu
TASK_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec "$TASK_ROOT/.venv/bin/python" "$TASK_ROOT/scripts/build_native.py"
