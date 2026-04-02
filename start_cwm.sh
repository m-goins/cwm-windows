#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

DEFAULT_CONFIG="/home/mgoins/cwaudit/configurations/api_configs/config.json"
CONFIG_PATH="${CWM_CONFIG_PATH:-$DEFAULT_CONFIG}"
LOG_DIR="${CWM_LOG_DIR:-$SCRIPT_DIR/logs}"
export CWM_LOG_PATH="${CWM_LOG_PATH:-$LOG_DIR/cwm.log}"
mkdir -p "$LOG_DIR"

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
echo "Log: $CWM_LOG_PATH"
exec python -m cwm "${args[@]}"
