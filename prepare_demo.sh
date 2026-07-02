#!/usr/bin/env bash
# Prepare a reliable assessment demo in one command.
# Usage:
#   ./prepare_demo.sh          # refresh claims + simulations (keeps your uploads)
#   ./prepare_demo.sh --reset  # clean seed corpus + MPFS + claims + simulations
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt

RESET=false
if [[ "${1:-}" == "--reset" ]]; then
  RESET=true
fi

# Start server in background if not already running
if ! curl -sf http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
  echo "Starting server..."
  uvicorn app.main:app --port 8000 &
  SERVER_PID=$!
  trap 'kill $SERVER_PID 2>/dev/null || true' EXIT
  for i in {1..30}; do
    curl -sf http://127.0.0.1:8000/api/health >/dev/null 2>&1 && break
    sleep 0.5
  done
fi

URL="http://127.0.0.1:8000/api/demo/prepare"
if $RESET; then URL="${URL}?reset=true"; fi

echo "Preparing demo (reset=$RESET)..."
curl -sf -X POST "$URL" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('Steps:')
for s in d.get('steps', []):
    print('  •', s)
st = d.get('status', {})
print()
print('Demo ready:', 'YES ✓' if st.get('ready') else 'NO — check items below')
for k, v in st.get('checks', {}).items():
    mark = '✓' if v else '✗'
    print(f'  {mark} {k}')
print()
print(f\"Dollars caught: \${d.get('total_dollars_caught', 0):,.2f}\")
print(f\"Engine: {st.get('engine', '?')}\")
print()
print('Open http://127.0.0.1:8000')
"
