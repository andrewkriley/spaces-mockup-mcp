#!/usr/bin/env bash
# Start the HTTP door on loopback. For Cursor / Claude Desktop, prefer:
#   python3 server.py --stdio
set -euo pipefail
cd "$(dirname "$0")"
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
export MCP_BEARER_TOKEN="${MCP_BEARER_TOKEN:-local-dev}"
export LISTEN="${LISTEN:-127.0.0.1:8080}"
export DATASET_PATH="${DATASET_PATH:-$PWD/dataset.json}"
exec python3 server.py "$@"
