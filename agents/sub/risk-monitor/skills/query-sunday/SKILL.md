# query-sunday 唯讀查 Sunday 的帳戶與風險狀態（risk-monitor 巡檢用）

Sunday 在 `http://127.0.0.1:7777`，用 **`http_request`** 唯讀查（GET）。**你不下單、不改倉——只觀察與建議。**

## 巡檢主力端點（GET）

```jsonc
{ "method":"GET", "url":"http://127.0.0.1:7777/api/account/positions" }      // ★ 每倉 side/qty/槓桿/liquidation_price/ROI%/memo
{ "method":"GET", "url":"http://127.0.0.1:7777/api/account/pnl" }            // 權益 + 總未實現 + 每倉拆解（看回撤）
{ "method":"GET", "url":"http://127.0.0.1:7777/api/account/balance" }        // equity / free / used margin
{ "method":"GET", "url":"http://127.0.0.1:7777/api/account/orders/open" }    // ★ 停損 / 停利單還掛著嗎
{ "method":"GET", "url":"http://127.0.0.1:7777/api/funding", "query":{ "symbol":"BTCUSDT" } } // 持倉的資金費逆風
```

## 對照共識（巡檢清單）

- **沒停損的裸倉？**（最嚴重）→ 比對 positions 與 open orders 有沒有對應的 STOP 單。
- 單筆 / 總曝險、槓桿超標？回撤（`/pnl` 權益）逼近上限？
- 單一標的或高相關標的（BTC/ETH/SOL）同向集中 → 曝險加總。
- liquidation_price 離現價太近？

## 警告 friday（send_message）

**哪一條越線 + 具體數字 + 建議動作（補停損 / 縮倉到 X / 降槓桿 / 停手）。** 逼近就預警。friday 要加槓桿 / 加碼時，評估最壞情況再決定是否同意調整共識。**只建議，不替他執行。** 細節 `GET /manual`。
