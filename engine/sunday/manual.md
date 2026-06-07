# Sunday 操作手冊（`GET /manual`）

Sunday 是一個 Binance USDⓈ-M 永續 **testnet** 交易引擎。它自己偵測訊號、下單、平倉、跑確定性風險熔斷；
你（swarm agent）的工作是**監督**它：查狀態、在 regime 改變時切策略、必要時叫停。
用通用 `bash` + `curl` 操作。base = `http://127.0.0.1:7777`。

> **milestone 1.0**：單一標的 `BTCUSDT`、策略 `momentum` / `flat`。部分端點目前回 stub，待 T2–T4 接上真實資料。

## 唯讀（auto-allow，不需審批）

```bash
# 整體狀態（含當值策略 + 理由 + 倉位 + 曝險）
curl -s http://127.0.0.1:7777/status

# 行情 OHLCV
curl -s "http://127.0.0.1:7777/market?symbol=BTCUSDT&tf=1h&limit=100"

# 持倉 / 損益
curl -s http://127.0.0.1:7777/positions
curl -s "http://127.0.0.1:7777/pnl?since=2026-06-01"
```

## Lever（POST；需 permission 審批；僅 leader）

```bash
# 切換當值策略（reason 必填，會留存給 User）
curl -sX POST http://127.0.0.1:7777/strategy \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"BTCUSDT","strategy":"momentum","reason":"analyst 判趨勢偏多"}'

# 叫停：mode=flat 全平、mode=safe 凍新倉（既有倉留 stop）
curl -sX POST http://127.0.0.1:7777/halt \
  -H 'Content-Type: application/json' \
  -d '{"reason":"demo 結束","mode":"flat"}'
```

## liveness（leader 的 dead-man ping）

```bash
curl -sX POST http://127.0.0.1:7777/heartbeat -d '{}'
```

Sunday 連續一段時間（預設 90m）收不到 heartbeat → 自動停開新倉（safe 地板）。

## 策略

- `momentum`：EMA20 × EMA50 cross（1h）順勢開多/空。
- `flat`：空手（既有倉平掉）。

## 風險封套（確定性、Python 層硬擋；1.0 寫死，agent 不能改）

- 單筆上限 / 總曝險上限 / 最大槓桿 / 進場必掛 stop。**越線一律拒單**（誰下令都擋）。

## 下令紀律（重要）

1. **切策略前**先 `curl /status` 看現況——別只信 webhook payload（那是「當時」，決策要看「現在」）。
2. **切策略後**再 `curl /status` 驗證 `strategy` 真的換了；沒換要重送，別假設成功。
3. **服務重啟後**先查 `/status` 對帳再行動（你恢復的記憶可能過期）。
