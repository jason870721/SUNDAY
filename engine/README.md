# Sunday engine

Binance USDⓈ-M 永續 testnet 交易引擎。對 swarm 只暴露 HTTP（`/manual` 是 agent 的操作手冊）。

## Run（本機）

前提：docker postgres（:5432）+ redis（:6379）起著。

```bash
cd engine
python3 -m venv .venv
.venv/bin/pip install -e .            # 安裝全部依賴（含 T2+ 的 ccxt/pandas）
cp .env.example .env                  # 本機預設值已可用（DB/redis）
.venv/bin/uvicorn sunday.app:app --host 127.0.0.1 --port 7777
```

驗證：

```bash
curl -s http://127.0.0.1:7777/health   # {"db":true,"redis":true}
curl -s http://127.0.0.1:7777/status
curl -s http://127.0.0.1:7777/manual
```

啟動時會自動套用 `migrations/*.sql`（forward-only，記在 `schema_migrations`）。

## 結構

| 檔 | 任務 | 作用 |
| --- | --- | --- |
| `sunday/app.py` | T1 | FastAPI：`/manual`、`/status`、`/health` |
| `sunday/config.py` | T1 | env 設定 |
| `sunday/store.py` | T1 | postgres pool + redis + migration runner |
| `migrations/0001_init.sql` | T1 | schema（9 張表，modeling-grade） |
| `sunday/manual.md` | T1 | `/manual` 內容（agent 操作手冊） |
| `sunday/exchange.py` | T2 | ccxt testnet adapter |
| `sunday/strategy.py` · `risk.py` | T3 | 策略 + 風控熔斷 |
| `sunday/events.py` | T4 | `notify()` webhook |
