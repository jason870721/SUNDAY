# BUG-04 — Stop-Loss 訂單建立時立即觸發（無論 mark 價格）

## 嚴重程度
🚨 Critical — 與 BUG-01 可能是同一 root cause 的不同表現。每次開倉帶 SL 都可能立即被平倉。

## 重現步驟

1. 透過任何方式開倉並同時建立 SL（`/api/perp/order` 帶 `stop_loss`，或 `/api/perp/protection` 補掛）
2. SL 訂單建立成功（API 回 200 OK）
3. **同一秒內** SL 立即觸發，market sell 平倉

## 實際案例

### 案例 A：BTCUSDT（2026-06-12 01:37，via `/api/perp/order`）
```json
POST /api/perp/order
{"symbol":"BTCUSDT","side":"buy","type":"market","notional_usd":3800,
 "leverage":8,"take_profit":64000,"stop_loss":62500}
```
- Mark 當時 ~63,150（遠高於 SL 62,500）
- SL #1000000102778632 建立，trigger=62,500
- **同一秒內** SL 觸發，order #14844939629 market sell 0.0548 BTC @62,400
- 已實現虧損：-$19.17
- TP #1000000102778629 殘留為孤兒單

### 案例 B：BTCUSDT（2026-06-12 01:33，via `/api/perp/protection`，即 BUG-01）
- 同樣模式：SL 更新後立即觸發 market close

### 案例 C（推測）：HYPEUSDT（2026-06-11 23:54）
- 若當時有 protection API 調用建立/更新 SL，可能觸發相同 bug

## 根因推測

**這不是 protection API 特有的 bug，而是 SL 訂單建立本身的問題。** 可能原因：
1. SL 訂單建立時使用了錯誤的參考價格（如 0 或過期價格），導致 Binance 判定「會立即觸發」
2. Binance 端對新建立的 SL 訂單有 race condition，在特定條件下立即執行
3. Sunday 在建立 SL 時傳遞了錯誤的 side/trigger 參數

## 影響

**極嚴重**：在修復前，**任何開倉操作都可能因 SL 立即觸發而虧損**。這等於系統性地破壞了每筆交易的風險管理。

## 與 BUG-01 的關係

BUG-01 和 BUG-04 很可能是同一 root cause：**SL 訂單建立/更新時的不正確觸發**。BUG-01 發生在 protection API（事後調 SL），BUG-04 發生在 order API（開倉時帶 SL）。兩者路徑不同但結果一致。

## 暫時規避

在 root cause 修復前：
- **開倉不帶 SL**，開倉後也不補 SL
- 改用手動監控 + 市價平倉替代 SL
- 這不是理想方案，但在 bug 修復前是唯一安全選項

---

— friday, 2026-06-12 01:38 CST
