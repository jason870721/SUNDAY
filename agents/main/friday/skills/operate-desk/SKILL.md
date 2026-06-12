# operate-desk 用 Sunday 下永續單、管倉位、對帳（friday 執行 SOP）

Sunday 是 Binance USDⓈ-M 交易所代理，在 `http://127.0.0.1:7777`。用 **`http_request`**（`{method,url,query?,body?}` → `status + body`）操作。**行情=主網真價，下單=測試網。** 完整 API：`GET /manual`。交易權只在你（friday）手上——決策過了標準，就照這份 SOP 執行。

## 一筆交易的執行節奏

1. **Pre-flight（平行查齊）**：憲法的風控共識（開場已讀）＋ `GET /api/markets/{symbol}`（精度/限額/最大槓桿）＋ `GET /api/account/balance`·`/pnl`（free 夠嗎、加單後曝險）。違反共識 → 不下；共識不存在 → 先和 risk-monitor 談定。
2. **整備**：槓桿/保證金模式與現況不同才設定（先查後設）。
3. **下單**：`POST /api/perp/order`，**take_profit + stop_loss 必帶**，memo 寫決策理由，header 帶 `X-Agent: friday`。
4. **驗證**：回應成交狀態 → `GET /api/account/positions` 驗 `protection`（TP/SL 腿、`sl_qty_covers`）→ limit 未成交看 `/api/account/orders/open`，必要時 `alarm_set` 回查。
5. **落盤**：持倉理由 + standing rules 寫回憲法（`PUT /api/memory/friday`）；重大進出場 `POST /api/reports` 通報 User。

## 查（GET，唯讀）

```jsonc
{ "method":"GET", "url":"http://127.0.0.1:7777/api/markets/BTCUSDT" }                          // 精度/限額/最大槓桿
{ "method":"GET", "url":"http://127.0.0.1:7777/api/account/positions" }                        // 倉位 + protection + liq_distance_pct
{ "method":"GET", "url":"http://127.0.0.1:7777/api/account/pnl" }                              // 總曝險 total_notional / exposure_pct
{ "method":"GET", "url":"http://127.0.0.1:7777/api/account/balance" }                          // equity / free / used
{ "method":"GET", "url":"http://127.0.0.1:7777/api/account/orders/open", "query":{ "page":"1" } }
{ "method":"GET", "url":"http://127.0.0.1:7777/api/perp/protection", "query":{ "symbol":"BTCUSDT" } }  // 單一標的保護腿狀態
```

## 下單（POST；務必帶 take_profit + stop_loss + X-Agent）

```jsonc
{ "method":"POST", "url":"http://127.0.0.1:7777/api/perp/order",
  "headers":{ "X-Agent":"friday" },
  "body":{ "symbol":"BTCUSDT", "side":"buy", "type":"market", "notional_usd":200,
           "leverage":5, "margin_mode":"isolated",
           "take_profit":75000, "stop_loss":60000,
           "memo":"（你的決策理由，≤300 字，給 User 看）" } }
```

- `side` buy/sell · `type` market/limit（limit 要帶 `price`）· 大小用 `notional_usd`（USD，自動換張）或 `qty`（張數）。
- **`take_profit` / `stop_loss` 是觸發價**；Sunday 掛成 reduce-only TP/SL 腿（MARK_PRICE 觸發）。觸發價已在觸發區會被 400 擋下（防一掛即市價平倉）——limit 單先不帶會立觸的腿，成交後用 `/api/perp/protection` 補掛。
- 倉位大小換算交給 `calc`：風險額 ÷ |entry − stop_loss| → qty；qty × entry → notional。

## 管倉

```jsonc
{ "method":"POST",   "url":"http://127.0.0.1:7777/api/perp/close",         "headers":{ "X-Agent":"friday" }, "body":{ "symbol":"BTCUSDT" } }   // 市價平倉（reduce-only，自動清孤兒腿）
{ "method":"POST",   "url":"http://127.0.0.1:7777/api/perp/protection",    "headers":{ "X-Agent":"friday" }, "body":{ "symbol":"BTCUSDT", "stop_loss":62000 } }  // 補/改 TP/SL：先掛新腿、後撤舊腿，不裸奔（null = 該腿不動）
{ "method":"POST",   "url":"http://127.0.0.1:7777/api/perp/leverage",      "headers":{ "X-Agent":"friday" }, "body":{ "symbol":"BTCUSDT", "leverage":10 } }
{ "method":"POST",   "url":"http://127.0.0.1:7777/api/perp/margin-mode",   "headers":{ "X-Agent":"friday" }, "body":{ "symbol":"BTCUSDT", "mode":"cross" } }
{ "method":"DELETE", "url":"http://127.0.0.1:7777/api/perp/orders",        "query":{ "symbol":"BTCUSDT" } }  // 撤該標所有掛單
{ "method":"DELETE", "url":"http://127.0.0.1:7777/api/perp/order/123456",  "query":{ "symbol":"BTCUSDT" } }  // 撤單一掛單
```

- **改 TP/SL 一律走 `/api/perp/protection`**（引擎先掛新、後撤舊）→ 驗 `protection`，不留裸倉跨回合。
- **平倉後**：確認孤兒 TP/SL 掛單已清（`/api/perp/close` 會自動清；手動平的查 `/api/perp/protection`，position 為 null 卻列得出腿 = 孤兒腿，撤掉）。

## 錯誤碼速查

| 錯誤 | 含義 | 動作 |
| --- | --- | --- |
| `-4016 PERCENT_PRICE` | 價格離現價太遠 | 貼近現價重掛或改 market |
| `-1021 timestamp` | 時鐘偏移（Sunday 會自動校時重試） | 連續出現 → `POST /api/reports`（kind:"system"） |
| 400 參數錯 | 精度/限額不符，或 TP/SL 在會立觸的一側 | 對照 `/api/markets/{symbol}` 與錯誤說明修正再送 |
| 503 / 連不上 | Sunday 異常 | 等 30–60s 重試一次，仍失敗照 RUNBOOK.md 用 bash 重啟；先補齊半完成的保護腿 |

同一動作最多重試 2 次，再失敗停手：`POST /api/reports` 通報 User，現場記進記憶。

## 紀律

1. 沒有 stop_loss 的倉位不准存在；調倉後必驗 `protection`。
2. 共識為界：違反就縮單或先和 risk-monitor 重談，不准先斬後奏。
3. 下單前看現況、下單後驗結果、重啟後先對帳（positions/orders）。
4. 細節隨時 `GET /manual`。
