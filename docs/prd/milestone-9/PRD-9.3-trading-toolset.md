# PRD-9.3 — Phase 3：交易工具集（schema 即鐵則）

> 目標：交易熱路徑的每一個寫入動作都有 typed 工具，且「每筆開倉必帶 TP/SL」「寫入必歸責」
> 從 prompt 紀律升級為 **schema 強制**。這是整個 milestone 的安全核心——LLM 的 constrained
> decoding 會在生成期就擋掉裸單，而不是等 Sunday 回 400。

## 1. 範圍

- 8 個工具（下表；7 個寫入 + `alerts_manage` 含唯讀 list 動作）+ `validate.py`（純函式交叉驗證）。
- **非範圍**：journal/memory/reports 寫入（留 http_request）；prompt/settings（Phase 4）。

## 2. 工具規格（7 個）

> 通則（全部寫入工具）：
> - required `agent: str`（1..32 chars）→ `X-Agent` header（S4）。
> - **零自動重試**（S5）：upstream 連線失敗或 4xx/5xx 一律原樣交回 agent（附 errors.py 提示行）。
> - 成功輸出 = 引擎回應的關鍵欄位整形 + 一行**下一步提醒**（如下單成功 → `verify: call
>   protection_status / positions next`），把 SOP 的「下單 ≠ 完成」內建進工具回饋。

### 2.1 `place_order`（唯一開倉入口）

```jsonc
// 輸入 schema（JSON Schema 語義；FastMCP 由型別簽名 + Field 生成）
{
  "agent":        { "type":"string", "minLength":1, "maxLength":32 },          // required
  "symbol":       { "type":"string" },                                         // required
  "side":         { "enum":["buy","sell"] },                                   // required
  "type":         { "enum":["market","limit"] },                               // required
  "qty":          { "type":"number", "exclusiveMinimum":0 },                   // 與 notional_usd 二擇一
  "notional_usd": { "type":"number", "exclusiveMinimum":0 },
  "price":        { "type":"number", "exclusiveMinimum":0 },                   // type=limit 必填
  "leverage":     { "type":"integer", "minimum":1, "maximum":125 },            // optional（沿用現況）
  "margin_mode":  { "enum":["isolated","cross"] },                             // optional
  "take_profit":  { "type":"number", "exclusiveMinimum":0 },                   // ⭐ required
  "stop_loss":    { "type":"number", "exclusiveMinimum":0 },                   // ⭐ required
  "memo":         { "type":"string", "minLength":1, "maxLength":300 }          // ⭐ required（User 在 UI 看）
}
// required = [agent, symbol, side, type, take_profit, stop_loss, memo]
```

JSON Schema 表達不了的交叉規則 → `validate.py` 純函式，**呼叫 upstream 前**擋下、錯誤訊息
一次列完所有違規（不擠牙膏）：

| 規則 | 錯誤訊息（樣式） |
| --- | --- |
| `qty` / `notional_usd` 恰好一個 | `give exactly one of qty / notional_usd` |
| `type=limit` ⇒ `price` 必填；`type=market` ⇒ 不准帶 `price` | `limit order requires price` / `market order must not carry price` |
| TP/SL 與方向的相對關係（buy ⇒ TP > SL；sell ⇒ TP < SL） | `for buy: take_profit must be above stop_loss` |

> 注意分工：**觸發區判定（會立即成交的腿）是引擎的職責**（已擋、回 400 說明方向），sidecar
> 不重複實作、不猜 mark price——驗證只做「不需要行情就能判的」純結構規則（S1：sidecar 無行情狀態）。

upstream：`POST /api/perp/order`。成功輸出：成交/掛單狀態、均價、qty、TP/SL 腿 id（`algo` 標記）、
+ 下一步提醒行。

### 2.2 其餘 7 個

| 工具 | 輸入（agent 之外） | upstream | 備註 |
| --- | --- | --- | --- |
| `close_position` | `symbol` | `POST /api/perp/close` | 輸出含 `cancelled_protection`（引擎自動清孤兒腿）；無倉位時透傳引擎錯誤 |
| `set_protection` | `symbol` · `take_profit?: number>0` · `stop_loss?: number>0`（**至少一個**，validate.py 擋） | `POST /api/perp/protection` | 引擎先掛新後撤舊（不裸奔）；輸出 `replaced` 舊腿 id + 下一步提醒（verify protection_status） |
| `cancel_order` | `symbol` · `order_id: str` | `DELETE /api/perp/order/{id}` | 兩本訂單簿 id 都可（引擎 -2011 轉打 algo 簿） |
| `cancel_all_orders` | `symbol` | `DELETE /api/perp/orders` | **與 cancel_order 分成兩個工具**——「撤一張」和「撤全部」風險量級不同，不准靠參數有無切換 |
| `set_leverage_margin` | `symbol` · `leverage?: int 1..125` · `margin_mode?: enum`（至少一個） | `POST /api/perp/leverage` ＋/或 `/margin-mode`（順序：先 margin-mode 後 leverage） | 兩段呼叫部分成功時：輸出兩段各自結果，不掩蓋半成功狀態 |
| `alert_set` | `symbol` · `kind: enum[price_above,price_below,pct_move]` · `threshold: number>0` · `note?: ≤120` | `POST /api/alerts` | 觸發一次即失效（語義透傳） |
| `alerts_manage` | `action: enum[list,delete]` · `id?: int`（delete 必填，validate.py 擋） · `status?: enum[active,triggered]` | `GET /api/alerts` / `DELETE /api/alerts/{id}` | list 的 page_size 鎖 30 |

（alerts 歸在本 phase 因為它屬於寫入通道；`alerts_manage` 的 list 是附帶的唯讀動作。）

## 3. 錯誤處理（沿用 PRD-9.2 §3 的 errors.py 提示行，本 phase 補交易視角）

- 引擎擋下的 400（觸發區、精度、限額）：原文透傳 + 提示行；**sidecar 不改寫不重試**——
  修參數是 agent 的決策（錯誤手冊在 friday prompt 裡）。
- 連線層失敗：tool error + `placed-or-not UNKNOWN — reconcile with open_orders/positions
  before retrying`（防 timeout 後盲目重送造成雙倉——這行提醒是 S5 的另一半）。

## 4. 測試

| 檔案 | 內容 |
| --- | --- |
| `tests/test_mcp_validate.py` | 交叉規則全覆蓋：qty/notional 二擇一（0 個、2 個）、limit/price 配對、buy/sell 的 TP/SL 相對方向、set_protection 至少一腿、alerts_manage delete 缺 id；錯誤訊息「一次列完」斷言 |
| `tests/test_mcp_shaping.py` 擴充 | 下單成功輸出（market 成交 / limit 掛單 / 帶 algo 腿）、close 含 cancelled_protection、set_leverage_margin 半成功呈現 |
| `tests/test_mcp_client.py` 擴充 | POST 連線失敗零重試 + UNKNOWN 提醒行出現 |

`scripts/smoke-mcp.sh` 擴充（**testnet 全鏈路**，金額用最小可下單量）：
`place_order(market, 帶 TP/SL)` → `protection_status` 斷言雙腿 + `sl_qty_covers:true` →
`set_protection`（SL 上移）斷言 `replaced` 非空 → `close_position` 斷言 `cancelled_protection`
→ `open_orders` 斷言該標的零殘留。**孤兒腿清零是煙測的硬斷言。**

## 5. 驗收清單

- [ ] 7 工具上線；`run-tests.sh` 全綠（無 SDK 環境照跑）。
- [ ] **schema 拒裸單**：用 SDK client 構造缺 `stop_loss` 的 `place_order` 呼叫 → 在 MCP 層
      被 input validation 拒絕，請求**未抵達** Sunday（order_log 無痕）。
- [ ] smoke 的 testnet 全鏈路綠（含孤兒腿清零斷言）。
- [ ] order_log 抽查：smoke 產生的每筆寫入 `agent` 欄 = smoke 用的名字（S4 歸責鏈完整）。
- [ ] 連線失敗注入測試（停 engine 再呼叫 place_order）：拿到 UNKNOWN 提醒行、無自動重試（S5）。
- [ ] 引擎目錄零 diff（S2）。

## 6. 風險

| 風險 | 對策 |
| --- | --- |
| validate.py 與引擎驗證規則漂移（引擎日後放寬/收緊） | validate.py 只做「結構規則」（二擇一、配對、相對方向）——這些是數學不是政策；政策類（觸發區、精度、限額）一律留引擎，本來就單邊維護 |
| timeout 落在「引擎已收單、回應沒到」窗口 | UNKNOWN 提醒行 + friday prompt 的冪等紀律（先查再動）雙保險；不做 client 端去重（引擎無冪等鍵，v1 不發明） |
| agent 把 `agent` 參數填錯名字 | 與今日 X-Agent header 同信任層級（自報名），不在本 phase 解；稽核帳本照樣記下填的值 |

— operator + Claude，2026-06-12
