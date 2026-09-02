#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[test]'

printf '\nInstalled: %s\n' "$(command -v file-bridge-mcp)"
printf 'Smoke test:\n'
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | file-bridge-mcp
printf '%s\n' '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | file-bridge-mcp
