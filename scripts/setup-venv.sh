#!/usr/bin/env bash
# Create .venv and install Ruff for lint + format.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/ruff --version
echo "venv ready. Run: .venv/bin/ruff check . && .venv/bin/python test_server.py"
