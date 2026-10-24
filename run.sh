#!/usr/bin/env bash
# One command for the Hack Day demo. Uses a local venv and an uncommon port.
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -q -r requirements.txt

PORT="${PORT:-47231}"
echo "H-ELP → http://127.0.0.1:${PORT}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
