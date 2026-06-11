# evva 特派工程師進駐 sunday swarm — 整合設計

> 日期：2026-06-11 ｜ 狀態：設計定案 ｜ Sunday 側**零程式碼**，純設定 + 文件
> 依賴：evva 的 **persona members** 功能（RP-29，spec 在
> `EVVA/docs/superpowers/specs/2026-06-11-persona-members-design.md`）

## 1. 目標

讓 **evva 主人格**以本尊身分（完整 prompt / 全套工具 / 自有 skills + swarm teamwork
協議）進駐 sunday swarm，擔任**特派工程師** worker、聽 friday 指揮：接 Sunday
（Python web app）的軟體改動需求——PRD 票實作、bug 修復——實作、測試、部署、回報。

把現有的 PRD 迴路收進團隊內：目前 `docs/prd/` 的票開給「Boss」（User）人工實作；
evva 進駐後 friday 直接 `task_assign` 派工程師，閉環不再卡在人身上。

**已定案的兩個營運決策**（User 2026-06-11 拍板）：

1. **交付邊界 = 全自動含部署**：implement → 測試綠 → commit `main` → 照 RUNBOOK
   重啟 Sunday → 驗 `/health` + smoke → 回報 friday；失敗 → `git revert` + 回滾重啟
   + 如實回報。
2. **模型 = `deepseek-v4-pro` + `effort: ultra`**（與 friday 同款，host 金鑰已備）。

## 2. 部署順序（硬依賴）

1. EVVA 側 `feature/persona-members` 完成並合入 `dev`；host 的 `evva` binary 更新到
   含該功能的版本（beta cut 或自建）。
2. 才能套用本 spec 的 `evva-swarm.yml`（舊 binary 看到 `persona:` 鍵會拒載 manifest）。
3. host 端重新 register swarm（`evva swarm …`）。

## 3. `evva-swarm.yml` 變更

workers 追加一名（放 trader 之後、analyst 之前，貼近「執行」分群）：

```yaml
  - persona: evva            # 特派工程師 — friday 的 Sunday 軟體改動需求由他實作
    model: deepseek-v4-pro
    effort: ultra
    when_to_use: "特派工程師 — 接 friday 的 Sunday 軟體改動 ticket（PRD 實作、bug 修復）：實作 → 測試綠 → commit main → 照 RUNBOOK 部署重啟 → 驗 /health → 回報。不下單、不碰交易。"
    # 不設 schedule：純 ticket/訊息驅動（task_assign 即喚醒）；工程量低頻，cron 只會燒 token
```

settings 調整一處：

```yaml
  stall_hard_timeout: "2h"   # 原 30m。工程 run（讀碼/改碼/跑測試/部署）合法地比巡檢長；
                             # 10m stall 警告不變，僅吊死強切變慢。其他成員巡檢遠短於 30m，不受影響
```

header 註解的角色清單同步補一行 evva。

## 4. 新增 `EVVA.md`（repo 根，工程師簡報）

evva persona 成員會把 workdir `EVVA.md` 當專案記憶注入（等價 CLAUDE.md 之於
Claude Code；其他 swarm 成員 `inject_memory: false` 不受影響）。內容三節：

1. **這個 repo 是什麼**：CLAUDE.md 的工程精要——8 條不變量（原文照列或逐條精簡）、
   專案結構表、技術棧、測試慣例（`./scripts/run-tests.sh`；UI 動過要
   `npm run build` 重建 `dist/` 並 commit）。
2. **特派工程師 SOP**（你在 swarm 裡的行規）：
   - **接票**：工作來源是 friday 的 task（`my_tasks`）；票會引用 `docs/prd/PRD-*.md`，
     先讀票再讀相關程式碼；票寫不清楚 → `send_message` 問 friday，不猜。
   - **實作**：動工前確認不違反 8 條不變量；測試貼著程式碼寫；conventional commit。
   - **驗證**：`./scripts/run-tests.sh` 全綠才算完成；改到 HTTP 契約跑
     `./scripts/smoke.sh` 對照。
   - **交付**：commit 到 `main` → 照 `RUNBOOK.md` 重啟 Sunday（engine venv +
     `python -m sunday`）→ 驗 `GET /health` 與相關端點 → 回報 friday（票號 +
     commit hash + 測試證據 + 重啟確認）。
   - **失敗路徑**：部署後 `/health` 不通或 smoke 失敗 → 立刻 `git revert` + 回滾
     重啟 + 回報 friday 與票（如實，不粉飾）；連 revert 都救不回 → 訊息 friday
     讓他 `POST /api/reports` 升級 User。
   - **部署視窗**：重啟會讓全隊短暫斷交易所——部署前 `send_message` 知會 friday
     （有在途 ticket / 劇烈行情時 friday 可叫你等），重啟後回報完成。
3. **邊界（鐵則）**：`engine/.env`（testnet 金鑰）永不 commit；不碰 `../evva`
   （evva 專案另有人管）；**不下單、不碰 `/api/perp` 交易端點**——你是工程師不是
   交易員；不改 friday 憲法與隊友記憶。

## 5. friday 整合（`agents/main/friday/system_prompt.md`）

1. **花名冊表**加一行：
   `| **evva** | 特派工程師：Sunday 軟體改動 | Sunday 缺陷/缺功能 → 開 PRD 票 + task 派他：他實作、測試綠、commit、部署重啟、回報；你驗收（看測試證據 + GET /health + 抽查端點）。部署會短暫重啟 Sunday，他會先知會你 |`
2. **「有需求就開票」一節改寫**：開 PRD 票後**接著開 task 派 evva 實作**（票是規格、
   task 是派工）；緊急系統缺陷照舊同步 `POST /api/reports` 通報 User。「請 Boss 處理」
   的措辭改為「派 evva 處理；evva 救不回的才升級 Boss」。
3. 驗收紀律一句：工程交付的 `task_verify` 要查證測試證據與 `/health`，不蓋橡皮章
   （與現有「驗收是硬功夫」一致，點名工程票怎麼查）。

## 6. 其他文件同步

- **`agents/skills/prd-ticket/SKILL.md`**：「後續會有人實作」→「特派工程師 evva 會
  接票實作（friday 派工）」；票格式不變。
- **`docs/workflow.md`**：§1 全景圖 swarm 框內加 evva（工程師）；§3 角色表加一行
  （喚醒來源：friday 的 ticket / 訊息，無 cron；做什麼：PRD 實作→測試→部署→回報；
  不做：不下單）；§7 狀態表 `docs/PRD/` 行的讀者由「開發者」改「evva（特派工程師）
  與開發者」。
- **`CLAUDE.md`**：「現況」的 swarm 消費端段落改為 1 leader + 8 workers 並補一句
  evva 特派工程師（persona member）。

## 7. 風險與緩解

| 風險 | 緩解 |
| --- | --- |
| 壞部署弄死 :7777（全隊斷交易所） | SOP 失敗路徑（revert + 回滾重啟）；watchdog 每 5m `GET /health` 異常即報 friday；friday 本就有 RUNBOOK 急救權 |
| 改 code 期間引擎照跑 | Python process 不熱載——commit 不影響運行中引擎，重啟才生效；部署視窗由 evva 主動知會 friday 擇時 |
| 工程 run 超時被強切 | `stall_hard_timeout` 30m→2h；強切後 mail 重排、task 仍在 running，下次喚醒接續 |
| 工程師越權下單 | EVVA.md 鐵則明文 + 既有信任模型（prompt 紀律 + testnet 假錢，與 workflow.md §2 的邊界聲明一致） |
| token 燒量 | 無 cron、純事件驅動；`list_members` 用量表 friday 可見，必要時 manifest 加 `budget_tokens` 上限 |

## 8. 驗收（host 端，feature 上線後）

1. 新 manifest register 成功，`list_members`/web roster 看得到 evva（when_to_use 正確、
   無 cron、模型 deepseek-v4-pro）。
2. User 或 friday 開一張小票（例：`/api/system/time` 回應加一個無害欄位，或指定一個
   現有 PRD），`task_assign` 給 evva。
3. evva 走完 SOP：commit 出現在 `main`、測試綠、Sunday 重啟後 `/health` 200、
   回報訊息帶票號+hash+證據；friday `task_verify` 結案。
4. 故障演練（選做）：給一張會讓 smoke 失敗的票，驗 revert 路徑真的執行。

## 9. 範圍外

- Sunday 引擎程式碼修改（本案零程式碼）。
- evva 功能本體（見 EVVA 側 spec）。
- 工程師的 git push 遠端 / CI——Sunday repo 目前本地 main 工作流，維持現狀。
