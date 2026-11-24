#!/usr/bin/env bash
#
# Ground truth to answer surface in one command. Exits non-zero on any failure; the last line on
# success is exactly `ALL CHECKS PASS`. Run after any change to scripts/, types/, views/, reference/
# or apps/.
#
#   APPLIANCE=http://localhost:11043 AUTH=user:pass tests/verify.sh
#   EMBABEL_AUTH='Basic …' tests/verify.sh [base-url]          (the older spelling still works)
#
# Always:
#   L1+L2  every view through the appliance's invoke endpoint, with its defaults and with cases that
#          assert facts the sources state (tests/test_views.py: Abberley is entry 8146, 18 villagers,
#          £10 10s in 1086; King William heads the landholders of 1086).
#   L2     the parsed figures against Open Domesday, field by field (pages cached in .cache/).
#   L3     a checked Wikipedia article, read cold, costs one call to Wikipedia however many county
#          records share the name.
#   app    the app in a real browser against the live appliance (no model call), when Playwright is
#          installed in tests/browser; and against the captured stub, when tests/browser/fixtures/
#          (git-ignored: it holds the appliance runtime) is present.
# With FULL=1, also the natural-language question battery and the app's Ask box. Both call a
# model, so they are stochastic and cost money; they measure the ask surface, not the realm's data.
set -euo pipefail
cd "$(dirname "$0")/.."
BASE=${APPLIANCE:-${1:-http://localhost:11043}}
if [ -n "${AUTH:-}" ]; then EMBABEL_AUTH="Basic $(printf '%s' "$AUTH" | base64)"; fi
: "${EMBABEL_AUTH:?set AUTH=user:pass (or EMBABEL_AUTH to the Authorization header value)}"
export EMBABEL_AUTH

# The build's venv when there is one; otherwise a small one with just what the tests import.
PY=.cache/venv/bin/python
if [ ! -x "$PY" ]; then
  PY=.cache/venv-tests/bin/python
  [ -x "$PY" ] || { python3 -m venv .cache/venv-tests && "$PY" -m pip install -q pyyaml==6.0.3 beautifulsoup4==4.14.2; }
fi

echo "== views";                     "$PY" tests/test_views.py "$BASE"
echo "== figures vs Open Domesday";   "$PY" tests/check_against_opendomesday.py 450
echo "== Wikipedia, read cold";       "$PY" - "$BASE" <<'PY'
import json, os, sys, urllib.request
base = sys.argv[1]
q = ("MATCH (p:DomesdayPerson) WHERE p.canonicalName = 'Bishop Odo/of Bayeux' "
     "MATCH (p)-[:WIKIPEDIA {ai: {fresh: true}}]->(w:DomesdayWikipedia) "
     "RETURN count(DISTINCT p) AS records, collect(DISTINCT w.title) AS articles")
req = urllib.request.Request(base + "/api/v1/admin/kg/execute", json.dumps({"cypher": q}).encode(),
                             {"Content-Type": "application/json", "Authorization": os.environ["EMBABEL_AUTH"]})
r = json.load(urllib.request.urlopen(req, timeout=180))
row = (r.get("rows") or [{}])[0]
ok = r.get("apiCalls") == 1 and row.get("articles") and row.get("records", 0) >= 1
print(("ok  " if ok else "FAIL") + f" Odo's article: {row.get('records')} county records, {row.get('articles')}, {r.get('apiCalls')} call(s) to Wikipedia")
sys.exit(0 if ok else 1)
PY
if [ -d tests/browser/node_modules/playwright ] || (cd tests/browser && npm install --silent >/dev/null 2>&1); then
  echo "== app, live";                (cd tests/browser && node live.mjs "$BASE" ${FULL:+--ask})
  if [ -d tests/browser/fixtures ]; then
    echo "== app, stubbed";           (cd tests/browser && node stub.mjs)
  else
    echo "== app, stubbed: skipped (no tests/browser/fixtures; capture with node stub.mjs --capture)"
  fi
else
  echo "== app: skipped (Playwright could not be installed in tests/browser)"
fi
if [ -n "${FULL:-}" ]; then
  echo "== questions";                "$PY" tests/ask_battery.py "$BASE"
fi
echo "ALL CHECKS PASS"
