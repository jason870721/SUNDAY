# Milestone-9 — Sunday MCP Server（typed 工具通道）

> **方向（2026-06-12）**：在 milestone-6/8 的 agent-native 代理之上，為 swarm 增加一條
> **typed MCP 工具通道**，消滅 `http_request` 裸呼叫的四類機制性不穩定（手拼參數、100KB 截斷、
> 零重試、字串 query 坑——診斷見 [PRD-006](../PRD-006-sunday-mcp-server.md)）。
> **混合制**：交易/帳戶熱路徑走 MCP，`http_request` + `/manual` 保留為降級通道與長尾通道。
> 引擎程式碼零侵入；milestone-6 八條不變量全數沿用。

## 為什麼是 MCP（一段話講完）

evva 的 MCP client 是已出貨功能：`.evva/settings.json` 設定即接入，swarm 每個成員都是
main-tier root agent，自動把 `mcp__sunday__<tool>` 收進 deferred 目錄、`tool_search` 按需載入
——**evva 端零改動、agents/ 的 tools yml 零改動**。Sunday 端做一個無狀態 sidecar（薄轉接層打
localhost:7777），typed schema 把「每筆開倉必帶 TP/SL」從 prompt 紀律升級成機器強制，
回應整形把 payload 壓進 evva 的 100k 截斷天花板之下。

## 本里程碑的新增不變量（S 系列，每個 phase 動工前先讀）

| # | 不變量 |
| --- | --- |
| S1 | **sidecar 無狀態、零金鑰**：只打 `127.0.0.1:7777`，幣安金鑰/簽名永不進 sidecar。 |
| S2 | **引擎零侵入**：`engine/sunday/` 不因 MCP 改任何程式碼（唯一例外：Phase 4 在 manual.md 加一節文件）。 |
| S3 | **輸出有預算**：單一工具單次輸出設計目標 ≤ 60k chars（evva 天花板 100k 的 0.6 倍安全係數）；禁止無上限 list 的 raw passthrough。 |
| S4 | **歸責不斷鏈**：所有寫入工具帶 required `agent` 參數 → 轉 `X-Agent` header（BUG-03 稽核帳本照常）。 |
| S5 | **非冪等寫入零自動重試**：`place_order` 等寫入失敗一律把錯誤交回 agent 判斷；只有唯讀 GET 允許 sidecar 內重試一次。 |
| S6 | **降級通道常開**：`http_request` 不從任何成員移除；sidecar 掛掉，系統退回 milestone-6 行為。 |
| S7 | **純邏輯 stdlib-only**（沿用引擎不變量 6）：整形/驗證/錯誤映射是純函式，`mcp` SDK 一律惰性 import，單元測試在無 SDK 環境照跑。 |

## 架構（一張圖）

```
 evva swarm（7 成員，main-tier root agents）
   │  mcp__sunday__*（streamable HTTP，tool_search 按需載入 schema）
   ▼
 sunday_mcp sidecar（:7780/mcp，無狀態，獨立行程）
   │  stdlib urllib · GET 重試一次 · 寫入帶 X-Agent · 回應整形
   ▼
 Sunday engine（:7777，不動）──ccxt──► Binance mainnet/testnet
```

設定（Phase 4 才 commit）：

```jsonc
// <workdir>/.evva/settings.json
{ "mcpServers": {
    "sunday": { "type": "http", "url": "http://127.0.0.1:7780/mcp", "timeout": 60 } } }
```

## Phase 切分與閘門

每個 phase 是**獨立可驗收、可停損**的交付；前一個 phase 的驗收清單全綠才開下一個。

| Phase | PRD | 內容 | 工時 | 閘門（DoD） |
| --- | --- | --- | --- | --- |
| **1** | [PRD-9.1](PRD-9.1-sidecar-skeleton.md) | sidecar 骨架：行程/設定/healthz + urllib client + 3 個 spike 工具（`ping`/`markets_list`/`positions`）+ smoke 腳本 | 1d | smoke 綠；evva `/mcp` 面板看得到 server connected + 3 tools |
| **2** | [PRD-9.2](PRD-9.2-readonly-toolset.md) | 唯讀工具全集（13 個）+ 回應整形規格 + `sunday://manual` resource + 輸出預算測試 | 1–1.5d | 全工具單測綠；最大輸入壓力案例 < 60k chars |
| **3** | [PRD-9.3](PRD-9.3-trading-toolset.md) | 寫入/管理工具（8 個）：schema 強制 TP/SL、`agent`→X-Agent、錯誤透傳 + 提示行、參數交叉驗證 | 1–1.5d | testnet 全鏈路（開倉→改 SL→平倉→孤兒腿清零）走 MCP 完成；裸單在 schema 層被拒 |
| **4** | [PRD-9.4](PRD-9.4-rollout-eval.md) | 上線：settings.json commit、prompts/skills 改混合制、RUNBOOK、manual.md 加節 + 兩週量化評估與裁決 | 0.5d + 2w 觀測 | swarm 重啟後全員 deferred 目錄出現 sunday 工具；評估報告產出 |

## 非目標（v1 明確不做）

- **不做 OpenAPI 自動生成工具**——1:1 端點映射會原樣繼承大 payload 與「TP/SL 靠紀律」的問題；精選 + 手工 schema 是本里程碑的價值核心。
- **不做** journal / memory / reports 的 MCP 工具（低頻、低風險、敘事自由度高，留在 `http_request`；Phase 4 閘門再裁決要不要收編）。
- **不做** MCP prompts；resources 只做 `sunday://manual` 一個。
- **不撤** `http_request`（S6）；**不改** webhook 通道與 Telegram 通道。
- **不改** evva（消費其公開介面，與 RP-9 同一紀律）。

## 成功指標（Phase 4 評估的裁決依據）

對照上線前後各兩週（evva event log / `/metrics` + Sunday order_log）：

1. swarm 對 `/api/perp` + `/api/account` 的 **400/422 率**（手拼參數錯誤類）。
2. **截斷事件數**（evva tool result 帶 `[truncated]` 的次數）。
3. **一筆交易執行的平均 turn 數**（friday 從決定到驗證完成）。
4. sidecar 可用率（healthz）與降級次數（agent 退回 http_request 的事件）。

裁決選項：維持混合 / 收編長尾端點 / 退場（settings.json `disabled: true` 即 kill-switch）。

## 交付物總覽

```
engine/
├── pyproject.toml                  # [project.optional-dependencies] mcp = [...]（Phase 1）
├── sunday_mcp/                     # 新套件（sidecar，invariant S1/S7）
│   ├── __init__.py
│   ├── __main__.py                 # python -m sunday_mcp（惰性 import SDK）
│   ├── server.py                   # FastMCP 組裝 + 工具註冊（唯一碰 SDK 的檔）
│   ├── client.py                   # stdlib urllib JSON client（timeout/GET 重試/X-Agent）
│   ├── shaping.py                  # 純函式：upstream JSON → 緊湊輸出（stdlib-only）
│   ├── validate.py                 # 純函式：寫入參數交叉驗證（Phase 3）
│   └── errors.py                   # 純函式：錯誤 → 工具結果文字 + 提示行
├── tests/test_mcp_shaping.py       # Phase 1–2
├── tests/test_mcp_client.py        # Phase 1（urllib 以注入 opener 假測）
├── tests/test_mcp_errors.py        # Phase 2
└── tests/test_mcp_validate.py      # Phase 3
scripts/smoke-mcp.sh                # Phase 1 起逐 phase 擴充
.evva/settings.json                 # Phase 4 commit
agents/main/friday/skills/operate-desk/SKILL.md   # Phase 4 改混合制
RUNBOOK.md 新章節（repo 根目錄）+ engine/sunday/manual.md MCP 節   # Phase 4
```
