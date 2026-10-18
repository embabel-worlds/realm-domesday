#!/usr/bin/env bash
#
# Ground truth to answer surface in one command: every view, the question battery, the app in a
# real browser and against a stub, and the parser against Open Domesday. Exits non-zero on any
# failure. Run after any change to scripts/, types/, views/, reference/ or apps/.
#
#   EMBABEL_AUTH='Bearer …' tests/verify.sh [base-url]
set -euo pipefail
cd "$(dirname "$0")/.."
BASE=${1:-http://localhost:11043}
: "${EMBABEL_AUTH:?set EMBABEL_AUTH to the Authorization header value}"
PY=.cache/venv/bin/python
[ -x "$PY" ] || { echo "run scripts/build.sh first (it creates .cache/venv)"; exit 2; }

echo "== views";             "$PY" tests/test_views.py "$BASE"
echo "== questions";         "$PY" tests/ask_battery.py "$BASE"
echo "== app, live";         (cd tests/browser && [ -d node_modules ] || npm install --silent; node live.mjs "$BASE" --ask)
echo "== app, stubbed";      (cd tests/browser && node stub.mjs)
echo "== figures vs Open Domesday"; "$PY" tests/check_against_opendomesday.py 450
