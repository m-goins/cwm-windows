#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Config resolution: CWM_CONFIG_PATH env var > ~/.config/cwm/config.json
DEFAULT_CONFIG="${HOME}/.config/cwm/config.json"
CONFIG_PATH="${CWM_CONFIG_PATH:-$DEFAULT_CONFIG}"

if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "Config not found: $CONFIG_PATH" >&2
  echo "Create ~/.config/cwm/config.json or set CWM_CONFIG_PATH." >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

source .venv/bin/activate

if ! python -c "import textual, httpx" >/dev/null 2>&1; then
  pip install -q -e .
fi

args=("$@")
if [[ " ${args[*]} " != *" --config "* ]]; then
  args=(--config "$CONFIG_PATH" "${args[@]}")
fi

echo "Starting cwm"
echo "Config: $CONFIG_PATH"
exec python -m cwm "${args[@]}"
