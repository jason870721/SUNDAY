# review-day 唯讀查 Sunday 的成交與績效（reviewer 復盤專用）

Sunday 在 `http://127.0.0.1:7777`，用 **`http_request`** 唯讀查（GET）。**你不下單、不改倉。**

## 復盤主力端點（GET）

```jsonc
{ "method":"GET", "url":"http://127.0.0.1:7777/api/account/trades", "query":{ "symbol":"BTCUSDT", "page":"1" } }  // ★ 成交 + realized PnL
{ "method":"GET", "url":"http://127.0.0.1:7777/api/account/orders", "query":{ "symbol":"BTCUSDT", "page":"1" } }  // 當日下單 / 成交 / 撤單
{ "method":"GET", "url":"http://127.0.0.1:7777/api/account/positions" }   // 現有持倉 + memo（friday 的下單理由）
{ "method":"GET", "url":"http://127.0.0.1:7777/api/account/pnl" }         // 權益 + 未實現 + 每倉拆解
```

## 歸因框架

- 賺 / 賠的單**為什麼**？停損及時嗎、還是被掃？停利太早 / 太晚？
- friday 採納 / 打槍 analyst 的判斷事後看對不對？risk-monitor 的警告成立嗎？
- 命中率、平均賺賠、對 10% 月報酬目標的進度。
- 對照持倉 `memo`（當初理由）與實際結果。
- **追蹤上次建議**（你的記憶目錄 playbook 裡有上次給了什麼）：friday 採納了嗎、行為改了嗎、結果如何？沒人理或沒照做都要點名。

## 產出

1. **寫工作日誌**：`POST /api/journal` 存進 Sunday DB（User 在 dashboard 的 Journal 分頁看）。`body` 用 markdown，建議分節：當日操作 / 盈虧歸因 / 做對做錯 / 上次建議追蹤 / 改進建議。
   ```jsonc
   { "method":"POST", "url":"http://127.0.0.1:7777/api/journal",
     "body": { "author":"reviewer", "date":"<今天>", "title":"<日期> 當日復盤",
               "body":"## 當日操作\n- …\n\n## 盈虧歸因\n- …\n\n## 上次建議追蹤\n- …\n\n## 改進建議\n- …" } }
   ```
2. **交 friday**（`send_message`）：報告重點 + 可執行建議（哪類 setup 加碼 / 避開、停損放寬 / 收緊）。**只建議，不下單。** 細節 `GET /manual`。
