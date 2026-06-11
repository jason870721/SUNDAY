# PRD-004 — Position PnL Webhook 通報閾值異常（每 0.01% 而非每 5%）

## 1. 卡在哪（問題）

**場景：** Sunday 的 `position_pnl` webhook 宣稱「持倉每跨 5% ROI 通報一次」，但實際行為是**每次 mark price 變動（約每 0.01-0.02% ROI）就推送一則**。

2026-06-11 極短線 #1 開倉（0.064 BTC Short @ $62,843）後 10 分鐘內收到 6+ 則 PnL webhook，觸發條件僅 ±$0.10-0.20 的微幅波動：

```
22:26:13  ROI +0.03%  uPnL +$0.24   mark $62,900.1
22:26:22  ROI -0.03%  uPnL -$0.21   mark $62,907.1
22:26:26  ROI +0.02%  uPnL +$0.15   mark $62,901.5
22:34:22  ROI +0.02%  uPnL +$0.19   mark $62,840.3
22:34:27  ROI -0.02%  uPnL -$0.20   mark $62,846.3
22:34:29  ROI +0.00%  uPnL +$0.01   mark $62,843.0
22:34:43  ROI -0.01%  uPnL -$0.11   mark $62,844.9
```

**影響：**
- friday 每回合被大量無意義 webhook 打斷，浪費注意力與 token
- 真正的 5% ROI 跨階事件（如 +5% → +10% 該啟動 Standing Rule #2）反而不明顯
- 測試模式下的 webhook 雜訊遠超有用信號

**推測根因：** webhook 的 PnL 比較基準可能是「上次推送時的 ROI」而非「上次跨整數 5% 階的 ROI」，導致每次 mark 變動都觸發推送。

## 2. 期望的 API 長相

**修復 `position_pnl` webhook 的觸發邏輯：** 僅在 ROI 跨越整數 5% 邊界時推送（0% → +5% → +10% → +15% … 或 0% → -5% → -10% …）。

不新增端點，不改 payload 格式——修正觸發條件即可。修復後，持有 0.064 BTC（$4K notional）的倉位在 ±$200 範圍內震盪時應收到 0 則 webhook。

參考行為：Binance 的 position update push 只在高權益變動時推送，而非每次 mark 更新。

## 3. 為什麼有助於 10% 月目標

- **減少決策疲勞**：friday 被無意義 webhook 淹沒時，真正的風險事件（alert 觸發、隊友警告）容易被掩蓋。webhook 的設計目的是「叫我起來處理重要的事」，不是「每 0.01% 嗶一聲」。
- **Standing Rules 自動化基礎**：Standing Rules #2（+10% SL 上移）、#3（+20% 半倉止盈）依賴 webhook 通知 friday——若 webhook 不可信，這些自動化等於沒用。
- **token 效率**：每次無意義喚醒消耗全隊 token 預算，省下的 token 可以分給 researcher 做更深的探索。

— friday, 2026-06-11

---

## 處置（已修復，2026-06-11）

**Root cause（與推測略有不同）：** 比較基準確實是「上次跨階的 bucket」，但 `monitor.bucket()` 用
`floor(roi/step)` 分階——**0 因此自己變成一條階梯邊界**（+0.03% → bucket 0、−0.03% → bucket −1）。
新倉位的 ROI 必然貼著 0 震盪，每次正負翻轉都被當成「跨階」推一次。這也解釋了 log 裡每一則通知
正負交替、|uPnL| 全部 < $0.25 的特徵。

**修復內容（`monitor.py`，payload 與端點不變）：**

1. `bucket()` 改截斷向零：**(−5%, +5%) 整段同屬 bucket 0**（損益打平帶），到達 ±5% 才算第一次
   跨階，之後每 ±5% 一階（[5,10) → 1、(−10,−5] → −1 …）。在 ±5% 內怎麼震都是 0 則 webhook。
2. 連帶修掉 log 中那筆 `ROI +0.00%` 的真兇：同 symbol 在輪詢間隔內平倉重開/改倉量/改槓桿時，
   `refresh_book` 之前沿用**舊倉位的 bucket** 比對新倉位 ROI，會憑空製造一次「跨階」。現在
   倉位身分（entry/qty/leverage）變了就靜默重置基準，只有 mark 真正推動的跨階才通報。

**驗證：** `tests/test_monitor.py` 新增 PRD-004 實況重播（0.064 BTC short @ 62,843，餵入 log 中
7 個 mark，斷言 0 則通知）+ 邊界/回落測試；`tests/test_monitor_refresh.py` 覆蓋重開倉/改槓桿
重置。全套 141 綠。Standing Rule #2/#3 依賴的 +5%/+10%/+20% 跨階通知行為不變。
