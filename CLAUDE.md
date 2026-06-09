# Sunday — Claude Code 開發指引

> **milestone-6 起轉向（2026-06-09）：產品 = 為 agent 設計的 Binance USDⓈ-M 永續交易所代理。**
> 先讀 [docs/prd/milestone-6/README.md](docs/prd/milestone-6/README.md)。舊的「策略監督交易引擎」
> 方向（thesis/desk/ablation/risk-envelope）已**整批移除**，不再發展。

## 我們在蓋什麼

一個**無狀態的 Binance 代理**：agent 用通用 HTTP 工具（`http_request` / curl）操作 Sunday，就像
人類用幣安——查可下單市場、讀 K 線/指標/資金費、下永續單（槓桿/逐倉全倉/止盈止損）、查倉位損益與
訂單、看外部總經指數、設定價格與倉位提醒。Sunday 持有金鑰，agent 只需要 HTTP。

## 不可違反的不變量

1. **行情 = 主網（真實價格、免金鑰）；交易 = 測試網（假錢、需金鑰）。** `exchange.py` 兩個 ccxt
   實例：`market_ex()`（mainnet）給所有行情；`trade_ex()`（testnet sandbox）給帳戶/下單。
2. **所有 API 免 token。** Sunday 持金鑰，agent 只持 HTTP。port 上不放交易所金鑰給 agent 看。
3. **回傳大量資料的 list 一律分頁**（`pagination.paginate` 的統一信封 `{items,page,page_size,total,has_more}`）。
4. **API prefix 依模組劃分**（req 10）：`/api/markets` `/api/klines` `/api/funding` `/api/perp`
   `/api/account` `/api/indices` `/api/alerts` `/api/monitor`，各自一個 `routers/` 模組。
5. **無 Postgres/Redis。** 唯一持久狀態 = alerts，存在單一 sqlite 檔（`store.py`，stdlib `sqlite3`）。
   sqlite wrapper 用**可重入寫鎖（RLock）**序列化所有存取 + WAL/busy_timeout（多執行緒寫入會死鎖）。
6. **純邏輯 stdlib-only、可在任何環境單元測試**（indicators / pagination / alerts 規則 / monitor 數學 /
   indices parsers / events builders）。重依賴（ccxt/fastapi/config）一律**惰性 import**，別在模組頂層。
7. **realtime 用 websocket + 輪詢備援**：`pricehub.Realtime` 跑 ws mark-price 串流（testnet 餵倉位監控、
   mainnet 餵價格提醒）+ 每 `MONITOR_POLL_SEC` 輪詢備援。monitor 以「跨 bucket 才發」、alert「觸發一次」，
   故 ws 與輪詢同時跑也不會重複通知。
8. **只有一條對外 webhook**：Sunday → evva swarm（`events.post` → `EVVA_WEBHOOK_URL`），事件
   `position_pnl` / `price_alert`，payload `{title,body,data,to}`，自帶 `suggested_action`。

## 專案結構

```
engine/sunday/
├── app.py            FastAPI 組裝（lifespan + router 掛載 + 系統路由 + realtime 啟停）
├── exchange.py       雙 ccxt（mainnet 行情 / testnet 交易）
├── store.py          sqlite（alerts + kv）；RLock 寫鎖
├── config.py         proxy 設定（pydantic-settings）
├── indicators.py     純指標：sma/ema/rsi/bollinger/adx/macd/atr
├── pagination.py     統一分頁 + 排序
├── indices.py        外部指數 feed + TTL 快取（F&G/CoinGecko/Stooq+Yahoo）
├── alerts.py         價格提醒規則 + 引擎（注入式 notify）
├── monitor.py        倉位 ROI/bucket 監控（注入式 notify）
├── pricehub.py       Realtime：ws 串流 + 輪詢備援
├── events.py         webhook builders + post（stdlib urllib）
├── routers/          每模組一檔（markets/klines/funding/perp/account/indices/alerts/monitor）
├── manual.md         agent API 手冊（GET /manual）
└── web/              TS + Vue 3 dashboard（Vite → dist/，FastAPI 自服於 / 與 /ui）
```

## 技術棧

- 引擎：Python ≥ 3.11，FastAPI + uvicorn，ccxt（USDⓈ-M），`websockets`，stdlib `sqlite3`。
- 前端：Vite + Vue 3 + TypeScript + vue-router + lightweight-charts（`npm run build` → `dist/`，committed）。
- 無 pandas/numpy（指標為純 Python）；webhook 用 urllib（無 httpx）。

## 與 evva 的關係（重要）

- evva 是 swarm runtime，**獨立 Go 專案在 `../evva`**。本專案是 evva swarm 的**被使用對象**：agent 用
  通用 `http_request` 操作 Sunday，Sunday 用 webhook 回推事件。**不從這裡改 evva。**
- Sunday 只消費 evva 公開介面（`POST /api/swarm/{ref}/event`，RP-9）。這仍是 multi-agent completeness
  oracle 的重點：swarm 只靠通用工具 + `/manual` 文件就能驅動任意 HTTP 外部系統。

## 慣例

- testnet 金鑰放 `engine/.env`，**永不 commit**（已 gitignore）。
- commit 用 conventional prefix（`feat`/`fix`/`chore`/`docs`/`refactor`/`test`）。
- 測試貼著程式碼（`tests/*_test` 不適用；本 repo 用 `tests/test_*.py`，`./scripts/run-tests.sh`）。
- 動工前先確認沒違反上面 8 條不變量。新 SQLite store 一律沿用 RLock 寫鎖模式。

## 現況

- **milestone-6（現行）= agent-native proxy。** 60 單元測試綠；前端 `npm run build` + `vue-tsc` 綠。
  後續：刷新 `evva-swarm.yml` + `agents/`（swarm *消費端*）改用新 `/api/*` 介面（本次未做）。
