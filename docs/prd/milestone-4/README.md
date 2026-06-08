# Milestone 4 — 從「監督笨策略」轉向「AI 經營事件驅動永續台」

> 狀態：**草案 / Draft（方向已定，待開工）** ｜ 日期：2026-06-08
> 上層權威：[`../sunday-project-prd.md`](../sunday-project-prd.md)（兩段閘門、lever 契約、legibility、安全）
> 同層：[`../milestone-1/`](../milestone-1/)（Gate-1 水管）、[`../milestone-2/`](../milestone-2/)（dashboard）、[`../milestone-3/`](../milestone-3/)（agent legibility / 閉迴路）
> 深設計：[`product-plan.md`](product-plan.md)（資訊層 / thesis 帳本 / directed 執行 / 研究台 workflow / ablation / 一個月 running test）
> 任務分解：[`milestone-4.0/README.md`](milestone-4.0/README.md)
> evva 依賴：[`../../../evva` `docs/roadmap/veronica/refine-plan/RP-11`、`RP-12`](#8-evva-依賴只填真正的-swarm-runtime-缺口) + 既有 `structured-output-tool` / `memory-typed-directory` PRD

---

## 0. 一句話定位

milestone-1~3 證明了**水管通、看得見、能閉迴路**——但 swarm 監督的是一組**沒有 edge 的 TA 笨策略**（EMA cross / 布林·RSI），而 §2.1 早已講死「生產等級 ≠ 賺錢」。milestone-4 是**產品轉向**：

> **停止讓 AI 做它會輸的事**（預測 K 線、跟 quant 拚統計 alpha）；**讓它做它唯一能贏的事**——7×24、跨多標的、把 funding / 鏈上 / 新聞 / 事件這些**非結構化資訊**即時整合成「**方向 + 信念 + 風險姿態**」。一個**沒有人類能輪班、沒有 quant 能輕易系統化**的事件/敘事驅動永續台。

**Sunday 從「策略引擎」降格為「執行 / 風險 / 資訊基板」；swarm 從「監督員」升格為「研究台（research desk）」——alpha 不在策略，在 swarm 的資訊整合。**

milestone-4 結束 = evva-swarm + Sunday 迎來**第一次為期一個月的 testnet running test**（§7）。

---

## 1. 為什麼是這個方向（破局的論證）

護城河只有一處站得住——**quant 系統化不了、人類規模化不了的資訊夾縫，形狀剛好是 LLM 的**：

| 玩家 | 強 | 弱 |
| --- | --- | --- |
| 系統化 quant | 數值/統計 alpha、低延遲 | 稀疏、異質、敘事/因果型資訊**系統化不了**（解鎖、被駭、治理、macro、鏈上流向） |
| 人類裁量交易員 | 讀場面、事件判斷 | **規模化不了**：盯不了 N 標的 × M 來源 × 24h，流程不一致 |
| **LLM agent swarm** | **正好補那個夾縫** | 慢、不會算、會追敘事追到山頂 → 用確定性風控 + ablation 紀律壓制 |

加密永續比股票更被**敘事 / 事件 / 反身性**（funding↔OI↔清算瀑布）主導，而這些大多藏在文字裡——LLM 主場。**這是唯一能宣稱的 moat。** 完整論證見 [`product-plan.md`](product-plan.md) §1。

> **兩段閘門第一次對齊**：原本 Gate-1（驗 swarm）與 Gate-2（賺錢）脫鉤；轉向後「swarm 做對 = 資訊整合好 = 有 edge」，兩個願望拉向同一方向。但**獲利仍不是 Gate-1 的 gate**（§9 紀律不變）——本 milestone 的成敗是「研究台機制正確 + ablation 證明資訊層有無加值」，**不是 P&L 正負**。

---

## 2. 決策紀錄（M4-D1..D9）

| # | 決策 | 為什麼 |
| --- | --- | --- |
| **M4-D1** | **重構角色**：Sunday = 執行/風險/**資訊**基板；swarm = 研究台；edge = 資訊整合（事件/敘事驅動），**非 TA** | 唯一能贏的戰場（§1）。把投資從「更好的指標」轉進「更好的資訊與綜合」。 |
| **M4-D2** | **確定性執行/風控續留 Python**（守不變量 7）；swarm 透過**結構化 thesis** 表達觀點，由新的 **`directed` 執行模式**消費 | LLM 永不在快路徑。swarm 設 **WHAT**（方向 + 信念 + 失效條件），Python 做 **HOW**（sizing / 進出場 / stop / risk fuse）。這讓「AI 操盤」成真又不破安全架構。 |
| **M4-D3** | **資訊層 Sunday 自服**（像 `/advisor`）：先做 quant-credible 的 **funding / OI / 清算 / basis**，再加 **新聞 / 行事曆 / 鏈上**；Sunday normalize，agent 對**已綜合的特徵**推理 | 永續真實 edge 在 funding/basis/清算反身性，不在 TA。先給結構化、可信的；控 token + 品質（agent 不生吞 firehose）。 |
| **M4-D4** | **thesis / outcome 帳本** = 系統 of record 延伸（Sunday/postgres），agent 經 HTTP 查；與 evva 的 **typed-memory**（agent 自己的 playbook）**互補不重複** | 系統真相在 Sunday（可被 ablation 評分、對 User legible）；agent 記憶是工作記憶/學到的啟發。兩者方向不同。 |
| **M4-D5** | **ablation 是生死線**（載重不變量）：任何 edge 主張都要對照 buy-hold / funding-carry / 確定性 baseline / **資訊層 OFF 的同一 swarm**。沒 ablation → 不准宣稱 edge | 否則分不清「資訊有加值」與「agent 只是看起來在忙」。這是上一輪 review 最大的缺口，現在升為產品紀律。 |
| **M4-D6** | **分段上線**：Phase A **哨兵/防守先行**為一個月 testnet run 的主姿態；testnet 無真錢故**同時開放進攻**並全程量測；真錢（Gate-2）**gated on ablation 顯示 edge** | 防守先行最安全、最可衡量、最像「人類贏過系統」；testnet 上讓它真的操盤（含進攻）以蒐證，但 caps 保守、ablation 全程跑。 |
| **M4-D7** | **多標的籃子**（LLM edge 隨廣度放大；人類覆蓋不了）；起手小型流動性永續籃子 | 廣度正是 swarm > 人類之處，也是平行協作真正有價值的地方。 |
| **M4-D8** | evva 端只填**真正的 swarm-runtime 缺口**：RP-11（事件路由 + 窄 lever）、RP-12（advice-loop 閉合）；並請 evva **優先**既有 `structured-output` / `typed-memory` PRD。`http_request`(舊 RP-A) **已 ship**，不再列 | 守不變量 4（evva 內零 Sunday-specific code）。研究台機器多數在 Sunday + skill/prompt；只有協作協議與路由是 evva 的事。 |
| **M4-D9** | 一個月 running test **全程 testnet**（Gate-1 紀律不破）；它同時驗 swarm + 蒐第一手「資訊 edge」證據。轉真錢是 test 之後的獨立決策 | testnet = 不賠錢的壓力測試場。先證明機制 + 量到 edge，再談真錢。 |

---

## 3. 範圍：milestone-4 要交付什麼

**建造研究台的完整機器，使系統能自主跑滿一個月（§7）。** 六條主線（任務細節見 [`milestone-4.0/README.md`](milestone-4.0/README.md)）：

1. **資訊層（feeds）** — Sunday ingest + normalize：funding rate（多場）/ OI / 多空比 / 清算 / basis（quant-credible，先做）＋ 新聞 / 行事曆（解鎖·macro·治理）/ 鏈上流向（LLM 主場）。
2. **決策支援綜合面板** — Sunday 自服 `/desk`（像 `/advisor` 的世界版）：把上面預聚合成「此刻什麼值得注意」+ 每標的的 funding/OI/event 摘要。
3. **thesis / outcome 帳本** — 結構化 thesis（方向 / 信念 / 時程 / 失效條件 / 證據 refs）→ 連到 positions / PnL 結果；可被 ablation 評分、對 User legible。
4. **`directed` 執行模式 + `/thesis` lever** — Sunday 依當前 thesis 確定性地 size/進出場/掛 stop/管理；swarm 經 `/thesis` 表達觀點（守 M4-D2）。
5. **研究台 roster + skills** — friday(desk lead) + 專責 analyst 群（funding/OI、news、on-chain、macro）+ risk-monitor（對抗式踢館）+ reviewer（事後復盤寫 playbook）。
6. **ablation 評測框架** — 基準組 + 資訊層 ON/OFF 開關 + 決策歸因 + 風險調整指標（Sharpe/Calmar/事件期回撤/per-thesis 命中率）。

詳細架構（資料 schema、directed 語意、workflow、ablation 設計、runbook）見 [`product-plan.md`](product-plan.md)。

---

## 4. 哪些不變量續用 / 哪些演進（對齊上層 PRD）

**續用（不動）：** 兩段閘門紀律（獲利非 Gate-1 gate）、確定性風控在 Python/交易所層（不變量 7）、雙向 dead-man + safe-mode（8）、兩條 HTTP 邊界（5）、event-gated 喚醒（6）、evva 內零 Sunday-specific code（4）、Sunday = 系統 of record + legible（9）。

**演進（本 milestone 改寫）：**

| 上層 | 原本 | milestone-4 演進 |
| --- | --- | --- |
| 不變量 2 | Sunday = 完整策略引擎；swarm 只監督 | Sunday = 執行/風險/**資訊**基板；swarm **驅動** positioning（透過 thesis），不只監督。Sunday 仍擁有**所有確定性執行/風控**。 |
| 不變量 3 | 三個 meta-lever（切策略/封套/kill） | 三個 lever 續用 + **第四個輸入：`thesis`**（結構化方向/信念，驅動 `directed` 模式）。仍只有 leader 拉；仍無逐單核准。 |
| §2.1 | 笨策略就夠（生產等級 ≠ 賺錢） | 笨策略**被取代**為 `directed`（thesis 驅動）。「生產等級 ≠ 賺錢」仍真，但**edge 來源從策略移到資訊綜合**。 |
| §9 | V1–V9 驗 swarm 機制 | 續驗 + 新增 **V10（ablation）**：資訊層 ON vs OFF 的風險調整表現差異被量到（見 product-plan §6）。 |

**新增載重不變量（提案併入 CLAUDE.md）：** **ablation 紀律**——任何「資訊/agent 有加值」的宣稱，都必須對照基準 + 資訊層 OFF 的同一 swarm；沒 ablation 證據，不准宣稱 edge、不准轉真錢。

---

## 5. 落地序（milestone-4 內部）

```
M4.0 — 研究台機器（本 milestone 主體，testnet）
  T1 資訊層 feeds（funding/OI/清算/basis 先；news/calendar/on-chain 後）
  T2 /desk 綜合決策支援面板
  T3 thesis/outcome 帳本（schema + 端點）
  T4 directed 執行模式 + /thesis lever（守 M4-D2）
  T5 研究台 roster + skills（friday desk-lead + 專責 analyst 群 + risk 踢館 + reviewer playbook）
  T6 ablation 評測框架 + 一個月 running-test runbook
  （evva 側）RP-11 事件路由+窄 lever、RP-12 advice-loop 閉合 → 回填 ../evva

M4.1 — 一個月 testnet running test（§7）= milestone-4 的 gate
```

> **先做防守骨架**：T4 的 directed 模式先支援「flat / 降風險」姿態（Phase A 哨兵），再開放方向性建倉（Phase B）。一個月 test 在 testnet 上跑**完整 directed 台**（含進攻），但**預設姿態防守、caps 保守、ablation 全程**（M4-D6）。

---

## 6. 驗收（milestone-4 的 DoD）

- [ ] **資訊層活著**：`/desk` 回多標的的 funding/OI/清算/basis + 近期事件/新聞摘要；feed 斷線優雅退化。
- [ ] **thesis 迴路閉合**：swarm 能 `POST /thesis` → `directed` 模式依其確定性建/減倉 → 結果寫回 outcome 帳本 → reviewer 事後可歸因（賺賠 / 命中率 / 失效是否觸發）。
- [ ] **確定性安全不破**：thesis 再激進，`risk.check_order` / drawdown 熔斷仍硬擋（沿用 V6）；LLM 不在快路徑。
- [ ] **研究台協作有證據**：平行蒐證 → 綜合 thesis → risk-monitor 踢館 → leader 拍板並**回信採納與否**（RP-12）→ reviewer 寫 playbook。`.vero` messages + thesis 帳本 + commentary 為證。
- [ ] **ablation 跑得起來**：能對同一段 testnet 區間產出「資訊層 ON vs OFF」與基準組的風險調整對照表（即使樣本還小）。
- [ ] **可跑滿一個月**：dead-man / safe-mode / 成本可觀測 / event-gated idle 經得起連續 run（沿用 V1/V5/V7）。
- [ ] **不變量**：evva 內零 Sunday-specific code（V9）；RP-11/12 以 RP 形式回填 ../evva，不在本 repo 改 evva。

> **milestone-4 不驗 P&L 正負**（守 D1）。它驗：研究台機制正確、確定性安全完好、**且 ablation 機器能回答「資訊層到底有沒有加值」**——那個答案是 Gate-2（真錢）的前置條件。

---

## 7. 一個月 running test（milestone-4 的 gate）

**目的**：第一次讓 evva-swarm + Sunday 在 testnet 連續自主跑滿一個月，同時達成三件事：

1. **驗 swarm 耐久**：V1（連續自主）/ V5（idle 不燒 token）/ V7（雙向 dead-man）在「真實連續時間 × 多標的事件叢發」下成立。
2. **驗研究台機制**：事件→專責 analyst→綜合 thesis→risk 踢館→leader 拍板→directed 執行→reviewer 復盤，每條箭頭有佐證。
3. **蒐第一手 edge 證據**：跑 ablation（資訊層 ON vs OFF + 基準），產出第一份「資訊綜合有無加值」的風險調整報告——**這份報告是要不要轉真錢的依據**。

**紀律**：全程 testnet（M4-D9）；預設防守姿態 + 保守 caps（M4-D6）；每週快照（reviewer cron）；人為注入事件測 V8。詳細 runbook 見 [`product-plan.md`](product-plan.md) §7。

> **這不是「跑一個月看賺多少」**——是「跑一個月證明機制 + 量到資訊 edge 的方向與幅度」。賺賠是 testnet 的，不計分；**edge 的統計訊號**才是產出。

---

## 8. evva 依賴（只填真正的 swarm-runtime 缺口）

守不變量 4：研究台機器多數在 Sunday（資訊層、帳本、ablation）+ skill/prompt（desk workflow）。**只有「swarm 成員怎麼協作/路由」是 evva 的事**。回填 `../evva`：

| RP | 主題 | 一句話 | 狀態 |
| --- | --- | --- | --- |
| **RP-11** | 事件路由 + 窄 lever | 研究台事件類型變多（catalyst / funding 極值 / 清算）→ 路由給專責 analyst；給 risk-monitor 一根**只能 halt** 的窄 lever，紓解單一 leader 漏斗 | 新填（前身 = M3 RP-B 草案，未 file） |
| **RP-12** | advice-loop 閉合 | leader 綜合 worker 建議後**回信採納與否 + 一句理由**；研究台的命脈（leader 整合 worker 是核心迴路） | 新填（前身 = M3 RP-C 草案，未 file） |
| （既有 PRD） | structured-output tool | 讓 headless agent 回 typed JSON → 結構化 thesis 的天然載體 | **請 evva 優先**（已在 `docs/roadmap/PRD/`） |
| （既有 PRD） | typed memory directory | agent 自己的 playbook 記憶（與 Sunday 帳本互補） | **請 evva 優先**（已在 `docs/roadmap/PRD/`） |

> `http_request`（舊 M3 RP-A）**已在 evva ship**（`pkg/tools/web/http.go`），roster 已採用，故不再列為缺口。

---

## 9. 不在範圍（milestone-4）

- **真錢 / mainnet** — Gate-2，gated on 一個月 test 的 ablation 結果（M4-D9）。
- **在 evva 內實作 RP-11/12** — 那是 evva 的排程；本 milestone 只回填 RP（不變量 4）。
- **Sunday 內 ML 建模 / 自動策略最佳化** — edge 在資訊綜合，不在煉指標；ML 是更後段、且需先有一個月資料。
- **HFT / 秒級** — 物理上 LLM 節奏是 swing/event；directed 模式維持分鐘~小時級。
- **telegram 對外播報** — Gate-2 extra，不擋本 milestone。
