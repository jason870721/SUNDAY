# PRD-006 — Sunday MCP server（typed 工具取代裸 http_request 的可行性分析與產品規劃）

> 狀態：**已立項（2026-06-12，採方案 B 混合制）→ 技術 PRD 見 [milestone-9/](milestone-9/README.md)**
> 起因：operator 觀察 swarm 用 `http_request` 操作 Sunday 不夠穩定。
> 調查範圍：`/mnt/evva` 原始碼（MCP client、http_request 工具、swarm 成員建構）+ Sunday 既有韌性機制。

---

## 1. 卡在哪（問題診斷）

「`http_request` 不穩定」拆開來是**四類機制性問題**（evva `pkg/tools/web/http.go` 逐行確認）：

| # | 問題 | 機制 | 後果 |
| --- | --- | --- | --- |
| 1 | **無 schema 的手拼呼叫** | agent 憑 manual.md 的記憶手拼 URL/query/body；參數名打錯、enum 拼錯、漏分頁、數字寫成字串都要等 Sunday 回 400/422 才知道 | 燒 turn 燒 token；高峰期一來一回就是一輪行情（PRD-005 中 analyst-flow 被迫手算 EMA 就是這類退化行為） |
| 2 | **100KB 回應截斷** | `maxBytes = 100_000`，超過直接砍斷 + `[truncated]` 標記；**砍斷的 JSON 無法解析** | 大 klines / 翻頁 trades / 多指標組合容易撞線，agent 拿到半截 JSON 只能重打或瞎猜 |
| 3 | **30 秒固定 timeout、零重試** | `httpReqTimeout = 30s`，一次網路抖動 / Binance 延遲尖峰 = tool error 直接回給 agent | PRD-005 的 3/3 連續失敗就是這一類（上游卡頓無退化）；agent 端的重試紀律全靠 prompt |
| 4 | **query 值必須是字串** | schema `additionalProperties:{"type":"string"}`——`"page":1` 直接 schema 驗證失敗 | 反直覺的小坑，模型隔幾天就會再踩一次 |

**已經不是問題的部分（避免重複造輪）**：Sunday 端的上游韌性已在 milestone-8 / PRD-005 處理過——
`-1021` 校時自癒、indicators `StaleCache`（stale-on-error）、markets TTL 快取。**剩餘的不穩定集中在
「呼叫建構層」與「回應運輸層」**，這正是 MCP 的 typed 工具能吃掉的部分；MCP **不能**讓 Binance 上游
變快（那部分已由 StaleCache 處理）。

> 註：swarm 的 `.vero` ledger 不在本 repo 主機上，以上為機制層診斷而非事故統計。M4 規劃了
> 上線後的量化對照。

---

## 2. 可行性分析

### 2.1 evva 端：原生支援，零改動 ✅

調查 `/mnt/evva` 確認（**不需要改任何 evva 程式碼**，符合「不從這裡改 evva」鐵則）：

1. **MCP client 是已出貨功能**（CHANGELOG roadmap v1.3；`pkg/mcp/` 完整套件含測試/OAuth/結果處理）。
2. **設定即接入**：`<workdir>/.evva/settings.json` 的 `mcpServers` 區塊（Claude Code 相容格式），
   支援 `stdio` 與 `http`（streamable HTTP）兩種 transport、**per-server `timeout`（秒）**、headers、
   env 展開、`disabled` 開關（`pkg/mcp/config.go`）。
3. **swarm 成員自動全員獲得**：每個成員都是 main-tier root agent（`space.go` 註明 "forcing
   main-tier"，經 `agent.New` 建構）→ `autoLoadMcp` + `foldMcpIntoProfile` 對每個成員執行 →
   發現的工具以 `mcp__sunday__<tool>` 進**deferred 目錄**並公告在 system prompt 的
   `<available-deferred-tools>`，成員用既有的 `tool_search` 按需載入 schema（RP-19 機制）。
   **agents/ 的 tools yml 一行都不用改。**
4. **權限**：swarm 跑 `permission_mode: bypass`，MCP 工具不會多出審批；MCP 工具視為 operator
   自有可信服務（CHANGELOG 明示不包 untrusted wrapper）。

**evva 端的天花板（設計約束）**：MCP 工具結果**同樣有 100k chars 截斷**（`pkg/mcp/result.go`
`maxResultChars = 100_000`）。所以「截斷問題」不是靠 MCP 拿到更大的管子，而是靠 **server 端把
回應整形成小而準的 payload**——這是工具設計的核心原則（見 §3.2）。

### 2.2 Sunday 端：sidecar 形態，引擎零侵入 ✅

- **新增獨立行程 `engine/mcp/`**（Python，官方 `mcp` SDK / FastMCP），**streamable HTTP** 跑在
  `127.0.0.1:7780`，工具實作 = 薄轉接層打 `http://127.0.0.1:7777` 既有 API（stdlib urllib，延續引擎慣例）。
- **為什麼不是 stdio**：每個成員有自己的 MCP manager，stdio = 7 個成員各 spawn 一條 python 子行程；
  HTTP = 一個共享行程，可觀測、可重啟、與引擎同生命週期管理。
- **為什麼不從 FastAPI OpenAPI 自動生成工具**（考慮過，否決）：1:1 端點映射會原樣繼承分頁囉嗦、
  大 payload、與「TP/SL 靠紀律不靠 schema」的問題。**精選工具集 + 手工 schema 才是這次的價值所在。**
- **不變量全數保持**：金鑰仍只在引擎側（MCP server 只打 localhost，不碰金鑰）；無新增持久狀態
  （sidecar 無狀態）；引擎程式碼零改動；webhook 通道不變。

### 2.3 真正的產品問題：completeness oracle 的論文要不要讓位

CLAUDE.md 明示本專案的實驗命題：**「swarm 只靠通用工具 + `/manual` 文件就能驅動任意 HTTP 外部
系統」**。全面換成 MCP 等於放棄這個命題。這不是技術判斷，是產品定位判斷，所以方案分三檔
（建議 B，理由見後）：

| 方案 | 內容 | 穩定性 | 命題保留 | 成本 |
| --- | --- | --- | --- | --- |
| A. 不做 MCP，只調參 | 調大 FetchMaxBytes、skill 再教育 | 改善 #2 一半，#1/#3/#4 原地踏步 | 完整 | ~0.5d |
| **B. MCP sidecar（混合，建議）** | 交易/帳戶熱路徑走 typed MCP 工具；`http_request` + `/manual` 保留為 fallback 與長尾端點通道 | #1–#4 全吃（熱路徑） | 降級保留（MCP 掛了照舊能跑） | ~3–4d |
| C. 全面 MCP、撤 http_request | 成員 active.yml 移除 http_request | 最高 | 放棄 | ~4d + sidecar 變成交易 SPOF |

**建議 B 的理由**：交易/管倉是「一次打錯就是真實成本」的熱路徑，typed schema 的邊際價值最高；
研究類唯讀長尾（indices 細項、journal、reports）錯了就重打，留在 http_request 沒有痛感。混合制
還附帶免費的韌性敘事：**sidecar 掛掉時 agent 退回 http_request，系統不停擺**——watchdog 不用加
新巡檢項，RUNBOOK 加一節即可。

---

## 3. 產品規劃

### 3.1 接入設定（交付物之一）

```jsonc
// <workdir>/.evva/settings.json（commit 進 repo）
{ "mcpServers": {
    "sunday": { "type": "http", "url": "http://127.0.0.1:7780/mcp", "timeout": 60 } } }
```

成員看到的工具名：`mcp__sunday__place_order`、`mcp__sunday__positions`…（deferred，`tool_search` 載入）。

### 3.2 工具設計原則（比工具清單更重要）

1. **schema 即鐵則**：`place_order` 的 `take_profit`、`stop_loss` 是 **required 欄位**——「每筆開倉
   必帶 TP/SL」從 prompt 紀律升級為機器強制（LLM 的 constrained decoding 在生成期就擋掉裸單）。
   side/type/margin_mode 用 enum；數字就是 number。
2. **回應整形**：每個工具只回決策需要的欄位、預設緊湊（如 klines 回 `[ts,o,h,l,c,v]` 陣列而非
   物件陣列；positions 回 ROI/protection/liq_distance 等決策欄位）——在 100k 截斷天花板下穩穩過。
3. **運輸層韌性內建**：sidecar 對 Sunday 的呼叫帶**一次重試 + 合理 timeout**；Binance 錯誤碼
   （-4016 等）原文透傳並附 manual 的處置提示一行。
4. **歸責保留**：寫入類工具帶 required `agent` 參數 → 轉成 `X-Agent` header，BUG-03 稽核帳本
   照常運作（與今日 header 同等信任層級：自報名）。
5. **分頁折疊**：列表工具收 `page`，回傳明確帶 `has_more`；歷史類提供合理上限的一次取齊參數。
6. **單一事實源**：工具 description 一句話 + 指回 `GET /manual`，不複寫第二份手冊（防文件漂移）。

### 3.3 工具清單（v1，精選 ~16 個）

| 群組 | 工具 | 對應 API |
| --- | --- | --- |
| 行情 | `markets_list` `market_get` `klines` `indicators` `funding` `indices` | /api/markets·/klines·/indicators·/funding·/indices |
| 帳戶 | `positions` `balance` `pnl_drawdown` `open_orders` `trades` | /api/account/* |
| 交易 | `place_order`（TP/SL required）`close_position` `set_protection` `cancel_orders` `set_leverage_margin` | /api/perp/*（含 /protection） |
| 提醒 | `alert_set` `alerts_manage`（list+delete） | /api/alerts |

憲法/日誌/通報（memory、journal、reports）**v1 留在 http_request**（低頻、低風險、敘事自由度高），
視 M4 數據決定要不要收進來。

### 3.4 里程碑

| 階段 | 內容 | 工時 | 驗收 |
| --- | --- | --- | --- |
| **M0 spike** | sidecar 骨架 + 3 個唯讀工具（markets/klines/positions）+ settings.json，dev swarm 確認 `tool_search` 看得到、叫得動 | 0.5d | 成員能以 `mcp__sunday__positions` 拿到緊湊倉位 |
| **M1 唯讀全集** | 行情/帳戶 11 個工具 + 回應整形；整形邏輯抽純函式（stdlib-only 可單測，沿用不變量 6 模式） | 1d | 單測綠；100k 截斷壓力案例（200 根 klines×6 指標）過 |
| **M2 交易集** | 5 個交易工具：required TP/SL schema、`agent`→X-Agent、重試與錯誤透傳 | 1–1.5d | testnet 全鏈路：開倉→驗 protection→改 SL→平倉→孤兒腿清零；裸單請求被 schema 拒絕 |
| **M3 上線** | settings.json commit、`operate-desk` skill 與 friday/analyst prompt 改為「優先 MCP、http_request 為 fallback」、RUNBOOK 加 sidecar 起停/健康檢查、scripts/smoke-mcp.sh | 0.5d | swarm 重啟後全員 deferred 目錄出現 sunday 工具 |
| **M4 評估** | 跑兩週，對照 evva event log / `/metrics` 的 tool error 率與 Sunday order_log 的 400/422 率，裁決：維持混合 / 收編長尾 / 退場 | — | 數據報告一份 |

### 3.5 風險與對策

| 風險 | 對策 |
| --- | --- |
| 工具描述與 manual.md 漂移成兩份手冊 | 工具 description 一句話制 + 指回 /manual（§3.2-6） |
| sidecar 成為交易新 SPOF | 混合制保留 http_request 退路；prompt 明寫降級動作 |
| `mcp` SDK 依賴進引擎 repo | 獨立 `engine/mcp/requirements.txt`，引擎本體 requirements 不動 |
| MCP 結果同樣 100k 截斷 | 回應整形是 v1 驗收條件，不做 raw passthrough 工具 |
| 模型反而混用兩條通道造成混亂 | prompt 規則一句話：「Sunday 熱路徑用 mcp__sunday__*，404/連不上才退 http_request」 |

— Claude（operator 調查代筆），2026-06-12

---

## 附錄：關鍵證據（原始碼座標）

- `evva pkg/tools/web/http.go:20,145` — 30s timeout、100KB 截斷、無重試
- `evva pkg/mcp/config.go:55-78` — `.evva/settings.json` mcpServers 載入（Claude Code 相容）
- `evva pkg/mcp/types.go:11-12` — stdio + streamable HTTP 兩種 transport
- `evva pkg/mcp/result.go:18` — MCP 結果同樣 100k chars 截斷（`maxResultChars`）
- `evva internal/agent/mcp_wiring.go:28-49,122-147` — autoLoadMcp / foldMcpIntoProfile（MAIN-tier 自動公告）
- `evva internal/swarm/space.go:183,218-330` — swarm 成員 = main-tier root agent，經 `agent.New` 建構
- `evva CHANGELOG.md:617-641` — MCP client 出貨說明（deferred 目錄 + tool_search 整合）
