#!/usr/bin/env bash
# Smoke-test the LIVE Sunday → evva-swarm webhook path (req 5/6).
#
#   ./scripts/smoke-webhook.sh [evva_base_url] [space_id]
#     evva_base_url  default http://127.0.0.1:8888   (evva service; EVVA_SERVICE_ADDR)
#     space_id       default sunday                  (evva-swarm.yml `name:`)
#
# Checks the RECEIVING side: that the evva swarm ingests Sunday-shaped events at
# POST /api/swarm/<id>/event and routes `to:"leader"` to the leader (friday). It posts
# SYNTHETIC events (no orders, no real alerts), so it is safe to run whenever the swarm
# is up — but note the two valid events DO wake friday once (that is the proof). The
# event endpoint is loopback-unauthenticated by design, so no token is needed.
#
# For the FULL path (Sunday actually firing a webhook), see the recipe at the bottom.
set -u
EVVA=${1:-http://127.0.0.1:8888}
SPACE=${2:-sunday}
URL="$EVVA/api/swarm/$SPACE/event"
pass=0 fail=0
ok()  { echo "  PASS  $1"; pass=$((pass+1)); }
bad() { echo "  FAIL  $1"; fail=$((fail+1)); }
post_code() { curl -s -o /dev/null -w '%{http_code}' -X POST "$URL" -H 'Content-Type: application/json' -d "$1"; }

echo "== evva swarm reachable? =="
hc=$(curl -s -o /dev/null -w '%{http_code}' "$EVVA/healthz" 2>/dev/null || echo 000)
if [ "$hc" = "200" ]; then ok "GET /healthz ($hc)"; else
  bad "GET /healthz (got $hc)"; echo; echo "aborting: swarm not reachable at $EVVA — start it: 'evva service start' && 'evva swarm .'"; exit 1
fi

echo "== ingest synthetic position_pnl → leader (friday) =="
c=$(post_code '{"title":"smoke BTC ROI +5.0%","body":"smoke-test position_pnl","to":"leader","data":{"event_type":"position_pnl","symbol":"BTCUSDT","roi_pct":5.0,"suggested_action":"(smoke, ignore)"}}')
[[ "$c" =~ ^20[02]$ ]] && ok "POST position_pnl to:leader ($c — 202 new / 200 dup)" || bad "POST position_pnl to:leader (got $c)"

echo "== ingest synthetic price_alert → leader =="
c=$(post_code '{"title":"smoke alert","body":"smoke-test price_alert","to":"leader","data":{"event_type":"price_alert","symbol":"BTCUSDT","price":1,"suggested_action":"(smoke, ignore)"}}')
[[ "$c" =~ ^20[02]$ ]] && ok "POST price_alert to:leader ($c)" || bad "POST price_alert to:leader (got $c)"

echo "== recipient + body validation =="
c=$(post_code '{"body":"x","to":"ghost-agent"}'); [ "$c" = "400" ] && ok "unknown recipient → 400" || bad "unknown recipient (got $c, want 400)"
c=$(post_code '{"to":"leader","body":""}');       [ "$c" = "400" ] && ok "empty body → 400"        || bad "empty body (got $c, want 400)"

echo
echo "Result: $pass passed, $fail failed."
[ "$fail" -eq 0 ] && echo "✓ evva ingests Sunday-shaped events and routes to:leader (friday). Open the swarm UI to see friday wake (message sender = \"webhook\")."

cat <<'NOTE'

── Full path (Sunday actually fires → evva → friday) ───────────────────────────
1. evva swarm up:  evva service start  &&  evva swarm .                    (binds :8888)
2. Sunday up, webhook pointed at the swarm (default already matches :8888):
     EVVA_WEBHOOK_URL=http://127.0.0.1:8888/api/swarm/sunday/event  python -m sunday
3. Fire a price alert that triggers on the next tick (price_above 1 is always true):
     curl -sX POST http://127.0.0.1:7777/api/alerts -H 'Content-Type: application/json' \
       -d '{"symbol":"BTCUSDT","kind":"price_above","threshold":1,"note":"webhook smoke"}'
   → Sunday's price hub fires once → POSTs the swarm → friday wakes with the event.
4. Position PnL: open a small testnet position; every 5% ROI move pushes a position_pnl event.
NOTE
[ "$fail" -eq 0 ]
