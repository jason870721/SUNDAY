# operate-desk 用 Sunday 下永續單、管倉位、對帳（trader 執行 SOP）

Sunday 是 Binance USDⓈ-M 交易所代理，在 `http://127.0.0.1:7777`。用 **`http_request`**（`{method,url,query?,body?}` → `status + body`）操作。**行情=主網真價，下單=測試網。** 完整 API：`GET /manual`。

## 一張 ticket 的執行節奏

1. **Pre-flight（平行查齊）**：`GET /api/memory/friday`（風控共識）＋ `GET /api/markets/{symbol}`（精度/限額/最大槓桿）＋ `GET /api/account/balance`·`/pnl`（free 夠嗎、加單後曝險）。ticket 缺欄位或違反共識 → 退回 friday，不執行。
2. **整備**：槓桿/保證金模式與現況不同才設定（先查後設）。
3. **下單**：`POST /api/perp/order`，**take_profit + stop_loss 必帶**，memo 抄 friday 的理由。
4. **驗證**：回應成交狀態 → `GET /api/account/positions` 驗 `protection`（TP/SL 腿、`sl_qty_covers`）→ limit 未成交看 `/api/account/orders/open`。
5. **回報**：成交價/量/槓桿 + TP/SL 確認 + 滑價 + 加單後總曝險，帶 `ref_task`。

## 查（GET，唯讀）

```jsonc
{ "method":"GET", "url":"http://127.0.0.1:7777/api/markets/BTCUSDT" }                          // 精度/限額/最大槓桿
{ "method":"GET", "url":"http://127.0.0.1:7777/api/account/positions" }                        // 倉位 + protection + liq_distance_pct
{ "method":"GET", "url":"http://127.0.0.1:7777/api/account/pnl" }                              // 總曝險 total_notional / exposure_pct
{ "method":"GET", "url":"http://127.0.0.1:7777/api/account/balance" }                          // equity / free / used
{ "method":"GET", "url":"http://127.0.0.1:7777/api/account/orders/open", "query":{ "page":"1" } }
{ "method":"GET", "url":"http://127.0.0.1:7777/api/klines", "query":{ "symbol":"BTCUSDT", "interval":"15m", "limit":"50" } }
```

## 下單（POST；務必帶 take_profit + stop_loss）

```jsonc
{ "method":"POST", "url":"http://127.0.0.1:7777/api/perp/order",
  "body":{ "symbol":"BTCUSDT", "side":"buy", "type":"market", "notional_usd":200,
           "leverage":5, "margin_mode":"isolated",
           "take_profit":75000, "stop_loss":60000,
           "memo":"（抄 friday ticket 的理由，≤300 字，給 User 看）" } }
```

- `side` buy/sell · `type` market/limit（limit 要帶 `price`）· 大小用 `notional_usd`（USD，自動換張）或 `qty`（張數）。
- **`take_profit` / `stop_loss` 是觸發價**；Sunday 掛成 reduce-only TP/SL 腿。
- 倉位大小換算交給 `calc`：風險額 ÷ |entry − stop_loss| → qty；qty × entry → notional。

## 管倉

```jsonc
{ "method":"POST",   "url":"http://127.0.0.1:7777/api/perp/close",         "body":{ "symbol":"BTCUSDT" } }   // 市價平倉（reduce-only）
{ "method":"POST",   "url":"http://127.0.0.1:7777/api/perp/leverage",      "body":{ "symbol":"BTCUSDT", "leverage":10 } }
{ "method":"POST",   "url":"http://127.0.0.1:7777/api/perp/margin-mode",   "body":{ "symbol":"BTCUSDT", "mode":"cross" } }
{ "method":"DELETE", "url":"http://127.0.0.1:7777/api/perp/orders",        "query":{ "symbol":"BTCUSDT" } }  // 撤該標所有掛單
{ "method":"DELETE", "url":"http://127.0.0.1:7777/api/perp/order/123456",  "query":{ "symbol":"BTCUSDT" } }  // 撤單一掛單
```

- **改 TP/SL**：撤舊觸發單 → 掛新單 → 驗 `protection`，一氣呵成不留裸倉。
- **平倉後**：撤掉孤兒 TP/SL 掛單（不撤會留著幽靈觸發單）。

## 錯誤碼速查

| 錯誤 | 含義 | 動作 |
| --- | --- | --- |
| `-4016 PERCENT_PRICE` | 價格離現價太遠 | 貼近現價重掛或改 market |
| `-1021 timestamp` | 時鐘偏移（Sunday 會自動校時重試） | 連續出現 → 報 system + 通知 friday |
| 400 參數錯 | 精度/限額不符 | 對照 `/api/markets/{symbol}` 修正再送 |
| 503 / 連不上 | Sunday 異常 | 等 30–60s 重試一次，仍失敗通知 friday；先補齊半完成的保護腿 |

同一動作最多重試 2 次，再失敗升級 friday（附完整錯誤）。

## 紀律

1. 沒有 stop_loss 的倉位不准存在；調倉後必驗 `protection`。
2. ticket 為準、共識為界；衝突就停下來問 friday。
3. 下單前看現況、下單後驗結果、重啟後先對帳（positions/orders）。
4. 細節隨時 `GET /manual`。
