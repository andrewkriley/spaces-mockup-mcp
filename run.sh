#!/usr/bin/env bash
# Start the HTTP door on loopback. MCP_BEARER_TOKEN is required.
# Optional single-client stdio: .venv/bin/python server.py --stdio
set -euo pipefail
cd "$(dirname "$0")"
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
if [[ -z "${MCP_BEARER_TOKEN:-}" ]]; then
  echo "run.sh: MCP_BEARER_TOKEN is required (copy .env.example to .env)" >&2
  exit 1
fi
export MCP_BEARER_TOKEN
export LISTEN="${LISTEN:-127.0.0.1:8080}"
export DATASET_PATH="${DATASET_PATH:-$PWD/dataset.json}"
if [[ -x .venv/bin/python ]]; then
  exec .venv/bin/python server.py "$@"
fi
exec python3 server.py "$@"
