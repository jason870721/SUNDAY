# Sunday — Runbook (milestone-6: agent-native Binance proxy)

How to run and **validate** the proxy. The pure logic is unit-tested anywhere (stdlib
only); the live exchange / websocket / dashboard run in *your* environment (they need
`pip install`, network, and a testnet key — none of which exist in the CI sandbox).

---

## 0. What's verified where (read this first)

| Layer | How it's verified | Where |
| --- | --- | --- |
| indicators / pagination / alerts rule / monitor math / indices parsers / events | **60 unit tests, stdlib only** — run anywhere | `./scripts/run-tests.sh` |
| store.py (sqlite) + alert/monitor engines | unit-tested in `:memory:` with injected notifiers | `tests/test_store.py`, `test_alerts.py`, `test_monitor.py` |
| exchange.py / routers / pricehub (ccxt + FastAPI + ws) | syntax-checked (`py_compile`); **integration-tested by you** | `./scripts/smoke.sh` against a running engine |
| dashboard (TS + Vue 3) | `npm run build` + `vue-tsc` typecheck (green) | `engine/sunday/web/` |

> Honest boundary: the build sandbox has no `pip`/`ccxt`/network/testnet key, so the live
> exchange calls, the websocket monitor/alert webhooks, and the served dashboard are
> validated by **you** with the smoke test + a browser. Everything is correct-by-construction
> + syntax-checked + covered by the stdlib unit tests where the logic is pure.

---

## 1. Prerequisites

- **Python ≥ 3.11**. (No Postgres, no Redis — a single sqlite file is the only state.)
- **Node ≥ 20** (only to *build* the dashboard; the engine serves the committed `dist/`).
- **Binance USDⓈ-M testnet** API key + secret (for trading; market data needs none).

```bash
cd engine
python3 -m venv .venv && . .venv/bin/activate
pip install -e .                      # fastapi / uvicorn / pydantic-settings / ccxt / websockets

cp .env.example .env                  # fill BINANCE_TESTNET_KEY / SECRET (NEVER commit .env)
```

> The testnet keys live **only** in `engine/.env` (gitignored). Agents never see them —
> all exchange access is inside Sunday.

## 2. Build the dashboard (once, or after a UI change)

```bash
cd engine/sunday/web
npm install && npm run build          # outputs engine/sunday/web/dist (served at / and /ui)
```

The engine runs without this step (it falls back to a placeholder page); build it to get the UI.

## 3. Run Sunday

```bash
cd engine && . .venv/bin/activate
python -m sunday                      # serves :7777, opens sunday.db, starts the realtime hub
```

## 4. Validate (smoke + browser)

```bash
./scripts/run-tests.sh                # 60 unit tests, green (stdlib only)
./scripts/smoke.sh                    # curls every /api/* group on :7777
```

Then open `http://127.0.0.1:7777/dashboard` and walk the pages: **Markets** (sort/filter/paginate) →
**Chart** (interval switch + indicators + funding) → **Trade** (place a leveraged TP/SL order on
testnet) → **Account** (positions/PnL/orders/trades) → **Indices** → **Alerts** (arm a price alert
+ watch the monitor). Anything the UI does, an agent can do with the same token-free `/api/*` calls
documented in `GET /manual`.

### Realtime webhooks → swarm

With an evva swarm running (`evva service start` + `evva swarm .`), Sunday POSTs `position_pnl`
(every `MONITOR_STEP_PCT`% move on an open position) and `price_alert` (when an alert fires) to
`EVVA_WEBHOOK_URL`. To eyeball the payload without a swarm, point `EVVA_WEBHOOK_URL` at any HTTP
echo endpoint.

## 5. Reset

```bash
rm -f engine/sunday.db                # wipe alerts + monitor config (rebuilt empty on next boot)
```

## 6. Scope note

milestone-6 is the pivot from the old supervised-trading engine to an **agent-native exchange
proxy** (markets / klines+indicators / funding / perp orders / account / indices / alerts /
monitor). The previous strategy/thesis/desk/ablation API was removed. Follow-up (not part of this
build): refresh `evva-swarm.yml` + `agents/` so the swarm *consumer* uses the new `/api/*` surface.
