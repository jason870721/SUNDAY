# BUG-03 — 無訂單來源審計記錄（Audit Log）

## 嚴重程度
⚠️ Medium-High — 無法追溯訂單操作者，導致異常事件（如 HYPE 不明平倉）無法歸責

## 問題

Sunday 的訂單記錄（`GET /api/account/orders`、`/trades`）不包含操作者身份資訊。`client_order_id` 僅為隨機 hex，不攜帶 agent 識別碼。

## 實際案例

**HYPEUSDT 不明平倉**（2026-06-11 23:54）：
- Order #259885354：reduce-only market sell，70.54 HYPE @56.555
- 非 friday 指令、非 trader 執行、非 TP/SL 觸發、非 liquidation
- **無法從 API 確認操作者**——只能推測可能是其他 agent 繞過 ticket 協議，或 protection API bug
- 若有 audit log，此事件可在數秒內結案

## 影響

- 異常交易無法追溯 → 治理依賴團隊紀律而非技術強制
- 調查成本高（task #4 需交叉訊問全隊）
- 若發生在更大倉位上，可能造成重大損失而無法究責

## 修復建議

1. Sunday 從 HTTP request 中識別操作 agent（自訂 header `X-Agent` 或 evva 注入的呼叫者身份）
2. `GET /api/account/orders`、`/trades`、`/orders/open` 每筆記錄新增 `agent` 欄位
3. 可選查詢參數 `?agent=` 用於過濾
4. 舊訂單 `agent` 欄位回 `null`（向後相容）

參見 PRD-001-audit-log。

---

— friday, 2026-06-12 01:36 CST
