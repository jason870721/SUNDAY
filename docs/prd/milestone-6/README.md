# milestone-6 — Pivot to an Agent-Native Binance Proxy

## Why (the pivot)

Sunday was a **supervised trading engine**: a Python engine ran deterministic execution +
risk while an evva swarm "operated" it via strategy/thesis levers, with a desk/ablation
research layer. milestone-6 **drops that product direction entirely**. The new product is:

> **An agent-native Binance USDⓈ-M exchange service.** An agent talks to Sunday over plain
> HTTP (`http_request` / curl) and uses Binance *like a human would* — browse markets, read
> klines/indicators/funding, place perp orders with leverage / margin-mode / TP-SL, query
> positions/PnL/orders, watch external macro indices, and receive pushed price/PnL alerts.

Sunday becomes a thin, **stateless proxy** in front of ccxt. It owns the Binance keys; agents
hold only HTTP. This keeps the evva "completeness oracle" thesis intact — a swarm should drive
an arbitrary HTTP system with generic tools + a `/manual` — while making the surface genuinely
useful (and judge-able) on its own.

## Locked decisions

1. **Topology** — market data from **mainnet** (real prices, public, no key); trading on
   **testnet** (fake money, keyed). Dual ccxt instances in `exchange.py`.
2. **Persistence** — **no Postgres/Redis**; one **sqlite** file for alerts + monitor config
   (`store.py`, reentrant write mutex + WAL). `python -m sunday` needs no external services.
3. **External indices** — crypto Fear&Greed + BTC dominance, VIX + DXY, S&P500 + Nasdaq,
   US10Y + Gold (Stooq CSV with a Yahoo fallback; all free).

## Requirements → where

| # | Requirement | Endpoint(s) / module |
|---|---|---|
| 0 | Tradeable markets (paginate / filter / volume·change sort) | `GET /api/markets` · `routers/markets.py` |
| 1 | Full perp orders (place / leverage / isolated·cross / TP·SL) | `POST /api/perp/*` · `routers/perp.py` |
| 2 | OHLCV all timeframes + indicators + funding | `/api/klines`, `/api/klines/indicators`, `/api/funding` |
| 3 | Positions+PnL / open orders / order & trade history (paginated) | `/api/account/*` |
| 4 | External indices (F&G + US equities/macro) | `/api/indices` · `indices.py` |
| 5 | Open-position monitor → webhook every 5% ROI | `/api/monitor` · `monitor.py` + `pricehub.py` |
| 6 | Price alerts (price / pct-move) → webhook | `/api/alerts` · `alerts.py` |
| 7 | Frontend rewrite to TypeScript + Vue 3 | `web/` (Vite + Vue 3 + TS) |
| 9 | All token-free; large responses paginated | every router · `pagination.py` |
| 10 | Prefixes grouped by module | `/api/<group>` per `routers/` module |
| 11 | Delete the old strategy-trading API | removed (see below) |

## What was removed (req 11)

Routes `/strategy /thesis /theses /desk /advisor /ablation /envelope /halt /heartbeat
/commentary /strategy_history /performance` and the swarm-posture `/status`; modules
`engine, strategy, desk, advisor, ablation, regime, feeds, attribution, backtest,
adapters_sim, adapters_live, ports, risk, execution, views`; the Postgres `migrations/`;
and the old no-build Vue dashboard. `psycopg`/`redis` dropped from deps; `websockets` added.

## Realtime (req 5/6)

`pricehub.Realtime` runs websocket `@markPrice@1s` streams (testnet marks → position monitor;
mainnet marks → price alerts) plus a `MONITOR_POLL_SEC` REST backstop. The monitor fires on a
ROI **bucket change** (`MONITOR_STEP_PCT`, default 5%); alerts fire **once**. Both are therefore
idempotent across the ws + poll paths. Events POST to the evva swarm webhook (`events.post`),
reusing the existing RP-9 receiver — no evva change required.

## Verification

- **Unit (stdlib, runs anywhere):** 60 tests — `./scripts/run-tests.sh`. Covers indicators
  (incl. macd/atr), pagination, the alert rule + engine (sqlite `:memory:` + injected notify),
  the monitor ROI/bucket math + bucket-change firing, the indices parsers, and the event builders.
- **Frontend:** `npm run build` + `vue-tsc` typecheck (green).
- **Live (your env):** `./scripts/smoke.sh` curls every `/api/*` group; browser walk of the
  dashboard; webhook delivery to a running swarm. See [RUNBOOK](../../../RUNBOOK.md).

## Follow-up (out of scope here)

`evva-swarm.yml` + `agents/` still reference the removed endpoints — the swarm *consumer* config
needs a separate refresh to drive the new `/api/*` surface (e.g. role skills that read `/api/markets`
and place orders via `/api/perp/order`). That's an evva-side configuration task, not part of the
Sunday-service build.
