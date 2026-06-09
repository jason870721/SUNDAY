#!/usr/bin/env bash
# Smoke-test a RUNNING Sunday proxy (milestone-6) — curls every /api/* group on :7777.
#
#   ./scripts/smoke.sh [base_url]
#
# Market-data + indices + alerts work with no key. Account/perp endpoints need a testnet
# key; without one they answer 503 (still a correct response), so those checks accept
# 200-or-503. The only mutations are an alert create/delete (safe) — no orders are placed.
set -u
BASE=${1:-http://127.0.0.1:7777}
pass=0 fail=0
ok()  { echo "  PASS  $1"; pass=$((pass+1)); }
bad() { echo "  FAIL  $1"; fail=$((fail+1)); }
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
# expect <regex> <label> <curl-args...>
expect() { local re=$1 label=$2; shift 2; local c; c=$(code "$@"); [[ "$c" =~ $re ]] && ok "$label ($c)" || bad "$label (got $c)"; }

echo "== system =="
expect '200' "GET /health"  "$BASE/health"
expect '200' "GET /manual"  "$BASE/manual"

echo "== market data (mainnet, no key — expect 200) =="
expect '200' "GET /api/markets"               "$BASE/api/markets?page=1&page_size=10"
expect '200' "GET /api/markets/BTCUSDT"       "$BASE/api/markets/BTCUSDT"
expect '200' "GET /api/klines"                "$BASE/api/klines?symbol=BTCUSDT&interval=1h&limit=50"
expect '200' "GET /api/klines/indicators"     "$BASE/api/klines/indicators?symbol=BTCUSDT&interval=1h"
expect '200' "GET /api/funding"               "$BASE/api/funding?symbol=BTCUSDT"
expect '400' "GET /api/klines bad interval"   "$BASE/api/klines?symbol=BTCUSDT&interval=2s"

echo "== pagination envelope shape =="
m=$(curl -s "$BASE/api/markets?page_size=5")
echo "$m" | grep -q '"items"' && echo "$m" | grep -q '"has_more"' && ok "/api/markets paginated" || bad "/api/markets shape"

echo "== indices + monitor (no key — expect 200) =="
expect '200' "GET /api/indices"          "$BASE/api/indices"
expect '200' "GET /api/indices/fear-greed" "$BASE/api/indices/fear-greed"
expect '404' "GET /api/indices/bogus"    "$BASE/api/indices/bogus"
expect '200' "GET /api/monitor"          "$BASE/api/monitor"

echo "== account / perp (need testnet key — accept 200 or 503) =="
expect '200|503' "GET /api/account/positions" "$BASE/api/account/positions"
expect '200|503' "GET /api/account/balance"   "$BASE/api/account/balance"
expect '200|503' "GET /api/account/pnl"       "$BASE/api/account/pnl"
# bad side is rejected (400) once past the key guard (503 if no key) — never opens a position
expect '400|503' "POST /api/perp/order bad side" -X POST "$BASE/api/perp/order" \
  -H 'Content-Type: application/json' -d '{"symbol":"BTCUSDT","side":"long","type":"market","qty":0.001}'

echo "== alerts roundtrip (create -> list -> delete) =="
resp=$(curl -s -X POST "$BASE/api/alerts" -H 'Content-Type: application/json' \
  -d '{"symbol":"BTCUSDT","kind":"price_above","threshold":999999,"note":"smoke"}')
id=$(echo "$resp" | grep -o '"id":[0-9]*' | head -1 | grep -o '[0-9]*')
[ -n "${id:-}" ] && ok "alert created (#$id)" || bad "alert create: $resp"
expect '200' "GET /api/alerts"        "$BASE/api/alerts?status=active"
if [ -n "${id:-}" ]; then expect '200' "DELETE /api/alerts/$id" -X DELETE "$BASE/api/alerts/$id"; fi

echo "== old strategy API is gone (expect 404) =="
for ep in "/strategy" "/desk" "/thesis" "/advisor" "/ablation" "/envelope"; do
  expect '404|405' "GET $ep removed" "$BASE$ep"
done

echo
echo "== $pass passed, $fail failed =="
[ "$fail" -eq 0 ]
