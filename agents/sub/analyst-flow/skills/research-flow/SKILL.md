# research-flow 判讀永續微結構（資金費/持倉/基差反身性）→ 給 friday 方向 + conviction

Sunday 在 `http://127.0.0.1:7777`。用 **`http_request`** 查（GET 免審批）。**你只讀、不拉 lever**（`POST /commentary` 例外）。

## 讀（GET）

```jsonc
{ "method": "GET", "url": "http://127.0.0.1:7777/desk", "query": { "symbol": "BTCUSDT" } } // ★ funding 年化 / OI Δ / 基差 + advisor regime/funding——先看這個
{ "method": "GET", "url": "http://127.0.0.1:7777/desk" }                                   // 全籃子哪個最 notable
{ "method": "GET", "url": "http://127.0.0.1:7777/market", "query": { "symbol": "BTCUSDT", "tf": "1h", "limit": "100" } }
{ "method": "GET", "url": "http://127.0.0.1:7777/positions" }
{ "method": "GET", "url": "http://127.0.0.1:7777/performance" }
```

## 判讀框架

- **funding 年化** |x| 高 → 多單（或空單）付高成本；極端常隨清算 violently 逆轉。問：擁擠在哪一邊？
- **OI Δ** 大 + 價格動 → 新倉建立（順勢）vs 平倉（反轉）。
- **基差（basis_bps）** 拉伸 → 期現偏離，反身性風險升高。
- 結論給 friday：**方向 + conviction(0..1) + 失效條件**。

## 推 commentary（給 User；免審批、非交易 lever）

```jsonc
{ "method": "POST", "url": "http://127.0.0.1:7777/commentary",
  "body": { "author": "analyst-flow", "title": "<標的> flow", "body": "<funding/OI/基差 的市場脈絡>" } }
```

## 回報 friday

`send_message`：方向（偏多 / 偏空 / 觀望）+ conviction + 失效條件 + 理由。**不拉 lever。**
