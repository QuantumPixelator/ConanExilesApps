#!/usr/bin/env bash
set -euo pipefail

# Usage: ./scripts/build_unix.sh
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python -m pip install --upgrade pip
pip install pyinstaller
if [ -f requirements.txt ]; then
  pip install -r requirements.txt
fi

pyinstaller --onefile --noconsole --name ConanExilesModManager main.pyw

echo "Built: dist/$(ls dist | head -n1)"
