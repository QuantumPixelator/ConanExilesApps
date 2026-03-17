#!/usr/bin/env bash
set -euo pipefail

# Move to repo root (script lives in scripts/)
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Create a venv if missing and install requirements
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  if [ -f requirements.txt ]; then
    .venv/bin/python -m pip install -r requirements.txt
  fi
fi

# Activate and run the app
source .venv/bin/activate
python main.pyw "$@"
