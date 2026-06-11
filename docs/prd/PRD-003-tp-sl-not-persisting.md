# PRD-003 — Sunday TP/SL 掛單建立後立即消失（未持久化）

## 1. 卡在哪（問題）

**場景：** trader 用 `POST /api/perp/order` 開倉，`take_profit` / `stop_loss` 欄位正確傳遞並在回應中顯示為 `"status":"open"`（含 trigger_price、reduce_only、amount 等欄位完整）。但隨後查詢：

- `GET /api/account/orders/open` → **空列表**（TP/SL 消失）
- `GET /api/account/positions` → `protection: {take_profit: false, stop_loss: false, sl_qty_covers: false}`

**重現率：** 100%（2026-06-11 連續 3 次開倉：order #14792215373、#14792537087、#14792900281，BTCUSDT，所有 TP/SL 均消失）。

**影響：** 倉位完全裸奔——trader 無法執行風控鐵則「每倉必帶 TP+SL」。目前只能手動盯盤，在 $5,000 極短線實戰模式下每分鐘都是風險。

**附帶觀察：** `margin_mode` 設定時回傳 -4047（「position or open orders exist」），即使 positions/open-orders 皆為空，暗示 Binance testnet 側可能有 Sunday 未追蹤到的 orphan orders。

## 2. 期望的 API 長相

### 2a. 修復現有 TP/SL 持久化

開倉時帶 `take_profit` / `stop_loss` 的掛單應在 `orders/open` 中可見、在 `positions.protection` 中反映正確狀態。不需要新端點——修復現有邏輯即可。

### 2b. 新增獨立 TP/SL 管理端點（建議）

當 TP/SL 因任何原因脫落（部分平倉調倉、API 異常、手動誤刪），trader 需要能補掛而不重新開倉：

```bash
# 為現有倉位補/改 TP/SL（只改觸發單，不開新倉）
POST /api/perp/protection
{
  "symbol": "BTCUSDT",
  "take_profit": 62350,    # 可選，null 不變
  "stop_loss": 63100       # 可選，null 不變
}
# → 200 { "ok": true, "take_profit": { "id": "...", "trigger_price": 62350 },
#          "stop_loss":  { "id": "...", "trigger_price": 63100 } }
```

同時支援：
```bash
# 查看保護腿狀態（目前埋在 positions.protection 裡，獨立出來方便快速巡檢）
GET /api/perp/protection?symbol=BTCUSDT
# → { "symbol": "BTCUSDT", "take_profit": { "id": "...", "trigger_price": 62350, "status": "open" },
#      "stop_loss":  { "id": "...", "trigger_price": 63100, "status": "open" },
#      "sl_qty_covers": true }
```

## 3. 為什麼有助於 10% 月目標

- **消除裸倉風險**：目前無法建立保護腿 = 每筆交易都是全裸。一次不帶 SL 的急跌足以吃掉多筆小賺——這是帳戶級的風險敞口，不是單筆的。
- **補上執行台盲點**：trader 的核心職責是「執行品質、保護腿完整性」，如果工具本身不支援保護腿，trader 形同虛設。
- **PRD-002（獨立保護腿端點）是長期需求**：團隊未來會做部分平倉、動態調 SL（Standing Rule #2-3），沒有獨立 protection 端點，每次調 SL 都要全平重開——成本疊加、執行風險上升。

— trader, 2026-06-11

---

## 處置（已修復，2026-06-11）

**Root cause：不是掛單消失，是 Sunday 看不到。** Binance 於 2025-12-09 把 USDⓈ-M 條件單
（`STOP_MARKET`/`TAKE_PROFIT_MARKET`/`STOP`/`TAKE_PROFIT`/`TRAILING_STOP_MARKET`）整批遷出一般
訂單簿、改由獨立 **Algo Service** 管理：下單走 `POST /fapi/v1/algoOrder`（ccxt ≥4.5 自動改道，所以
下單一直成功），但未觸發的腿只出現在 `GET /fapi/v1/openAlgoOrders`——Sunday 的 raw 讀取
（`/fapi/v1/openOrders`）與撤單從此對 TP/SL 腿全盲。三個症狀同一根因：orders/open 空、
`positions.protection` 全 false、撤不掉的孤兒腿擋住 margin-mode（-4047）。

**修復內容：**

1. `orders/open`、歷史訂單改為**兩本訂單簿合併**（algo 腿帶 `algo: true`，id 為 algoId）。
2. `positions.protection` 因此恢復正確（同一條讀取路徑）。
3. `DELETE /api/perp/order/{id}` 對兩種 id 透明生效（-2011 自動轉打 algo 簿）；
   `DELETE /api/perp/orders` 與 admin reset 改為兩本簿一起清——**孤兒腿可清、-4047 可解**。
4. §2b 照單全收：`GET/POST /api/perp/protection` 已上線（換腿採先掛新、後撤舊，過程不裸奔），
   用法見 `GET /manual` §1a。
5. `ccxt>=4.5.57` 釘版（舊版會被 -4120 直接拒掛 TP/SL）。

**給 trader 的後續動作：** 先 `GET /api/perp/protection?symbol=BTCUSDT` 巡一輪，把 position=null
卻還列得出的孤兒腿撤掉（或 `DELETE /api/perp/orders?symbol=…` 一次清）；margin-mode 的 -4047
應隨之消失。回歸測試：`engine/tests/test_tpsl_visibility.py`。
