# BUG-01 — `/api/perp/protection` 更新 SL 時觸發意外 market close

## 嚴重程度
🚨 Critical — 導致倉位意外平倉，造成實際資金損失

## 重現步驟

1. 開倉（例如 BTCUSDT long，帶 TP/SL）
2. 調用 `POST /api/perp/protection` 更新 stop_loss 觸發價
3. API 回應 200 OK，顯示新 SL 已建立
4. **同一秒內**產生了 reduce-only market sell order，平倉全部部位

## 實際案例

**時間**：2026-06-12 01:33:12 CST

**操作**：
```json
POST /api/perp/protection
{"symbol":"BTCUSDT","take_profit":64000,"stop_loss":62615}
```

**API 回應**（200 OK）：
```json
{
  "ok": true,
  "stop_loss": {
    "id": "1000000102773934",
    "trigger_price": 62615.0,
    "status": "open"
  },
  "replaced": ["1000000102764267"]
}
```

**實際結果**：
- 新 SL #1000000102773934 建立（未被觸發，mark ~63,400 >> 62,615）
- 但同時產生了 order #14843715560：market sell 0.0318 BTC @62,430，平倉全部部位
- 倉位從 +$25 浮盈變成 -$5.80 已實現虧損

## 根因推測

`/api/perp/protection` 在「取消舊 SL 腿 → 建立新 SL 腿」的流程中：
- 取消舊腿時可能誤走了「market sell」路徑而非「cancel order」
- 或新舊腿替換的競態窗口觸發了 Binance 的 reduce-only close

## 影響範圍

- **所有調用 `/api/perp/protection` 的操作都有風險**
- Standing rule「+10% ROI 時 SL 上移保本」無法安全執行
- 任何事後調整 TP/SL 的操作都可能觸發此 bug

## 關聯事件

- **HYPEUSDT 不明平倉**（2026-06-11 23:54）：也可能是同一 bug。HYPE 倉位在無任何顯式平倉指令下被 market sell @56.555。若當時有人（如 trader 巡檢）調用了 protection API，可能觸發了相同行為。但因 Sunday 無 audit log，無法確認。

## 暫時規避方案

1. **禁止調用 `/api/perp/protection`** 進行任何 TP/SL 修改
2. 開倉時直接在 `/api/perp/order` 中帶入 `take_profit` 和 `stop_loss`
3. 若需調整 TP/SL：先手動平倉 → 再以新參數重新開倉（繞過 protection API）
4. trader 巡檢僅驗證 protection 狀態，不執行修改

## 修復建議

1. 審查 `/api/perp/protection` 的「取消舊腿」邏輯，確保走 cancel order 而非 market sell
2. 加入防禦性檢查：若 position qty > 0，禁止對該 symbol 發起 reduce-only market order（除非是明確的 close 請求）
3. 加入 audit log（PRD-001），記錄每次 API 調用的操作者和結果
4. 修復平倉後 TP/SL 自動清理（PRD-002），減少孤兒單

---

— friday, 2026-06-12 01:36 CST
