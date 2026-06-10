# PRD-002：alert / webhook 支援指定收件 agent（讓 risk-monitor 擺脫純輪詢）

> 狀態：**提案**（開票日期 2026-06-10，來自 risk-monitor 優化稽核）

## 卡在哪 / 想解決的問題

所有 Sunday → swarm 的 webhook 事件（`position_pnl` / `price_alert`）都寫死 `to:"leader"`
（`events.py` builders 的預設值），alert 的資料模型（`store.py` 的 `alerts` 表）也沒有
收件人欄位。後果：

1. **risk-monitor 在兩次整點巡檢之間是瞎的。** 它的 system prompt 寫「察覺倉位異動時」
   啟動巡檢，但沒有任何事件會喚醒它——倉位在巡檢間隔內急速惡化（逼近清算、ROI 急墜），
   只有 friday 會收到 `position_pnl`，煞車角色反而是最後知道的。
2. **risk-monitor 無法自己佈防。** 它想在「價格逼近某倉位清算價」設一個觸發點，做不到——
   alert 觸發只會去 friday。風控的觸發器只能掛在被監督者身上，是設計上的倒置。

## 期望的 API 長相

1. **`POST /api/alerts` 加選配 `to` 欄位**（預設 `"leader"`，行為不變）：

   ```jsonc
   { "symbol":"BTCUSDT", "kind":"price_below", "threshold":58000,
     "note":"BTC 多單清算價 56800，逼近就回查", "to":"risk-monitor" }
   ```

   - `alerts` 表加 `recipient TEXT NOT NULL DEFAULT 'leader'` 欄位（sqlite `ALTER TABLE` 或
     schema 重建；沿用 RLock 寫鎖模式）。
   - `alerts._fire` → `events.price_alert_event(alert, price, to=alert["recipient"])`。
   - `GET /api/alerts` 回傳列表帶出 `to`，方便盤點誰掛了什麼觸發器。

2. **（選配、可拆開做）`position_pnl` 的負向大階梯抄送 risk-monitor**：
   ROI 跌破某個門檻（例如 -10% 起的每個 bucket）時，除了 `to:"leader"` 再發一份
   `to:"risk-monitor"`。讓煞車和油門同時收到壞消息。

## 為什麼有助於 10% 月目標

風控的反應速度直接決定單次虧損的深度。現在 risk-monitor 的偵測延遲上限是 1 小時（cron
間隔）；有了收件人路由，它可以在談定共識時就把「清算價警戒線」「回撤警戒 ROI」佈成 alert，
偵測延遲從小時級降到秒級（ws 路徑），而且不增加任何輪詢成本——平靜時零 token。

## 驗收

- 不帶 `to` 的既有用法行為完全不變（預設 leader）。
- `to:"risk-monitor"` 的 alert 觸發時，webhook payload 的 `to` 為 `risk-monitor`，
  evva 端把事件路由給 risk-monitor。
- 單元測試：alert CRUD 帶 `to` round-trip；`_fire` 帶出正確收件人；分頁列表含 `to`。
