# operate-desk 用 Sunday 下永續單、管倉位、盯盤（friday 操盤 SOP）

Sunday 是 Binance USDⓈ-M 交易所代理，在 `http://127.0.0.1:7777`。用 **`http_request`**（`{method,url,query?,body?}` → `status + body`）操作。**行情=主網真價，下單=測試網。** 完整 API：`GET /manual`。

## 一輪操作的節奏

1. **看現況**：`GET /api/account/positions`·`/pnl`——手上有什麼、賺賠多少、TP/SL 還在不在。
2. **找機會**：`GET /api/markets?sort=volume&order=desc` 掃量大的標的；對有興趣的看 `GET /api/markets/{symbol}`（限額/最大槓桿）、`GET /api/klines/indicators?...&set=rsi,macd,adx`、`GET /api/funding`、`GET /api/indices`（情緒/總經）。
3. **要研究**：拿不準就 `task_assign` 派 analyst-flow（技術/資金費）、analyst-news（事件/敘事），等回報再決定。不急就設 alert 觀望。
4. **下單**：方向 + 大小 + 槓桿 + 保證金模式 + **停利 + 停損（必帶）** + memo → `POST /api/perp/order`。
5. **驗證 + 記錄**：看回應的成交與 TP/SL legs；把理由 / 共識 / 教訓寫進 `{workdir}/MEMORY.md`。

## 看行情（GET，唯讀）

```jsonc
{ "method":"GET", "url":"http://127.0.0.1:7777/api/markets", "query":{ "sort":"volume", "order":"desc", "page_size":"10" } }
{ "method":"GET", "url":"http://127.0.0.1:7777/api/markets/BTCUSDT" }
{ "method":"GET", "url":"http://127.0.0.1:7777/api/klines", "query":{ "symbol":"BTCUSDT", "interval":"1h", "limit":"200" } }
{ "method":"GET", "url":"http://127.0.0.1:7777/api/klines/indicators", "query":{ "symbol":"BTCUSDT", "interval":"1h", "set":"rsi,macd,adx,atr" } }
{ "method":"GET", "url":"http://127.0.0.1:7777/api/funding", "query":{ "symbol":"BTCUSDT" } }
{ "method":"GET", "url":"http://127.0.0.1:7777/api/indices" }
```

## 下單（POST；務必帶 take_profit + stop_loss）

```jsonc
{ "method":"POST", "url":"http://127.0.0.1:7777/api/perp/order",
  "body":{ "symbol":"BTCUSDT", "side":"buy", "type":"market", "notional_usd":200,
           "leverage":5, "margin_mode":"isolated",
           "take_profit":75000, "stop_loss":60000,
           "memo":"為什麼下這單（≤300 字，給 User 看）" } }
```

- `side` buy/sell · `type` market/limit（limit 要帶 `price`）· 大小用 `notional_usd`（USD，自動換張）或 `qty`（張數）。
- **`take_profit` / `stop_loss` 是觸發價，每筆必帶**；Sunday 會掛成 reduce-only 的 TP/SL 腿。
- limit 價被 `-4016 PERCENT_PRICE` 擋 = 離市價太遠，貼近現價或改用 market。

## 管倉 / 盯盤

```jsonc
{ "method":"POST",   "url":"http://127.0.0.1:7777/api/perp/close",          "body":{ "symbol":"BTCUSDT" } }   // 市價平倉
{ "method":"POST",   "url":"http://127.0.0.1:7777/api/perp/leverage",       "body":{ "symbol":"BTCUSDT", "leverage":10 } }
{ "method":"DELETE", "url":"http://127.0.0.1:7777/api/perp/orders",         "query":{ "symbol":"BTCUSDT" } }  // 撤該標所有掛單
{ "method":"POST",   "url":"http://127.0.0.1:7777/api/alerts",              "body":{ "symbol":"BTCUSDT", "kind":"price_above", "threshold":75000, "note":"突破就回來看" } }
{ "method":"GET",    "url":"http://127.0.0.1:7777/api/account/orders/open", "query":{ "page":"1" } }
```

- alert / 持倉監控觸發時 Sunday 會主動 webhook 你——**設好 alert 就能安心觀望**，不必一直醒著盯盤。不需要 alert 時請取消該 alert．

## 紀律

1. 每筆開倉必帶 TP/SL；倉位大小 / 槓桿在和 risk-monitor 談定的範圍內。
2. 下單前看現況、下單後驗證回應、服務重啟後先對帳。
3. 拿不準就派研究或設 alert；防守先行。
4. 細節隨時 `GET /manual`。
