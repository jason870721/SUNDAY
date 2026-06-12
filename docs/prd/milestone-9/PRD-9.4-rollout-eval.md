# PRD-9.4 — Phase 4：上線整合 + 兩週量化評估

> 目標：把前三個 phase 的成果接上真實 swarm（混合制），並用數據裁決這條通道的最終形態。
> 這是唯一**改變既有系統行為**的 phase——所有改動都有單行 kill-switch。

## 1. 範圍

- `.evva/settings.json` commit（swarm 接入點）。
- prompts / skills 改混合制（friday 為主，analyst 唯讀組順帶）。
- `RUNBOOK.md` 新章節 + `engine/sunday/manual.md` 加 MCP 節（S2 的唯一引擎側例外，純文件）。
- 兩週評估與裁決。
- **非範圍**：任何新工具；evva 改動（永遠非範圍）。

## 2. 接入（交付物逐項）

### 2.1 `.evva/settings.json`（commit）

```jsonc
{ "mcpServers": {
    "sunday": { "type": "http", "url": "http://127.0.0.1:7780/mcp", "timeout": 60 } } }
```

- kill-switch = 加 `"disabled": true`（或刪檔）+ 重啟 swarm；agent 行為退回 milestone-6（S6）。
- sidecar 未啟動時 evva 只在 boot log 留 connect warning、成員照常運作——已在 Phase 1 驗證。

### 2.2 prompts / skills（混合制的一句話規則）

寫進相關 persona 的規則統一為一句，不展開教學（工具 schema 自說明）：

> **Sunday 熱路徑優先用 `mcp__sunday__*` 工具；工具不可用（tool error / server 不在）時退回
> `http_request` + `GET /manual`，並在回報裡註明走了降級通道。**

改動點：

| 檔案 | 改什麼 |
| --- | --- |
| `agents/main/friday/system_prompt.md` | 「工具的指揮紀律」加上面一句；執行 SOP 的端點敘述補 MCP 工具名對照（下單=`place_order`、改腿=`set_protection`、對帳=`positions`/`open_orders`） |
| `agents/main/friday/skills/operate-desk/SKILL.md` | 改版：每節並列 MCP 工具（主）與 http_request（降級）；錯誤手冊不變 |
| `agents/sub/analyst-flow/system_prompt.md` | 行情查詢改建議 `klines`/`indicators`/`indices`/`funding`（唯讀組） |
| `agents/sub/risk-monitor/system_prompt.md` | 巡檢三件套改建議 `pnl_drawdown`/`positions`/`protection_status` |
| 其餘成員 | 不動（reviewer 的 repl 工作流、researcher/news 的 web 工作流不在熱路徑） |

### 2.3 `RUNBOOK.md` 新章節「sunday-mcp sidecar」

- 啟動/停止：`python -m sunday_mcp`（與 engine 同機；開機自啟方式比照 engine 現行做法）。
- 健康：`curl :7780/healthz`（`ok` + `engine.reachable` 兩層）。
- 故障處置表：sidecar 掛 → agent 自動降級（S6），不急；engine 掛 → 先救 engine（既有章節）。
- kill-switch 操作（§2.1）。
- Phase 1 記錄的「殺 sidecar → 重啟 → 成員自癒」實測結果。

### 2.4 `engine/sunday/manual.md` 加一節（≤15 行）

「**MCP 通道**：本手冊的熱路徑端點另有 typed 工具版（`mcp__sunday__*`，見工具自帶 schema）；
本手冊仍是完整合約與降級通道的權威文件。」——維持單一事實源（工具 description 不複寫手冊）。

## 3. 上線程序（順序即回滾邊界）

1. sidecar 部署 + healthz 綠（此時 swarm 無感）。
2. commit settings.json → 重啟 swarm → 驗收：7 成員 `list_members`/`/mcp` 面板全 connected，
   任一成員 deferred 目錄含 `mcp__sunday__*` 全集。
3. commit prompts/skills → 下一次各成員喚醒自然生效（無需再重啟）。
4. 觀察 48h：friday 的交易動作是否實際走 MCP（order_log 的 agent 欄不變、evva event log 的
   tool 名變化）；異常即回滾第 3 步（prompts revert）或第 2 步（kill-switch）。

## 4. 兩週評估（裁決依據 = milestone README 的四個指標）

| 指標 | 來源 | 基線（上線前兩週） | 目標 |
| --- | --- | --- | --- |
| `/api/perp`+`/api/account` 400/422 率 | Sunday order_log + engine access log | 實測記錄 | **−70%**（手拼參數錯誤類應趨近消失） |
| tool result 截斷事件 | evva event log `[truncated]` 計數 | 實測記錄 | **0**（熱路徑） |
| 一筆交易平均 turn 數 | evva event log（friday 從 ticket 決策到驗證收尾） | 實測記錄 | 下降（方向性，不訂死數字） |
| sidecar 可用率 / 降級次數 | healthz 抽樣 + 回報中「降級通道」字樣 | — | 可用率 ≥ 99%；降級可數可解釋 |

**裁決選項**（評估報告以 `POST /api/reports` kind=info 同步給 User）：

- **A. 維持混合**（預設）：指標達標、降級路徑有被用到 → 現狀即終態。
- **B. 收編長尾**：agent 頻繁為 journal/memory/reports 退回 http_request 且出錯 → 開 PRD-9.5。
- **C. 退場**：指標無改善或 sidecar 維運成本 > 收益 → kill-switch + prompts revert，
  PRD 留檔記錄結論（負結果也是 completeness oracle 實驗的合法產出）。

## 5. 驗收清單

- [ ] settings.json / prompts / RUNBOOK / manual.md 四件 commit。
- [ ] 真實 swarm 重啟後：7 成員都看得到 `mcp__sunday__*`；friday 實際用 `place_order` 在
      testnet 完成一筆帶 TP/SL 的單（order_log `agent=friday`）。
- [ ] kill-switch 演練一次：disabled → 重啟 → friday 用 http_request 完成同型操作 → 還原。
- [ ] 基線數據已抓取存檔（評估的「前兩週」視窗）。
- [ ] D+14 評估報告產出並完成裁決。

## 6. 風險

| 風險 | 對策 |
| --- | --- |
| 模型混用兩通道造成行為不穩定 | 規則只有一句（優先 MCP、error 才降級）+ 回報註明降級——可觀測、可歸因 |
| prompts 改動與 milestone-9 之外的 prompt 演進衝突 | prompts 改動集中一個 commit，revert 即回滾 |
| 評估期間行情極端，turn 數指標被污染 | 指標 3 只看方向不訂死；裁決以指標 1/2（機制性）為主 |

— operator + Claude，2026-06-12
