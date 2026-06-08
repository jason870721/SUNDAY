# Milestone 4.0 — 研究台機器（任務分解）

> 上層：[`../README.md`](../README.md)（定位/決策/gate）｜ 深設計：[`../product-plan.md`](../product-plan.md)
> 慣例：一個 session 一個 T；契約先定、impl 折入；Sunday 端 Python + skill markdown，evva 缺口回 RP（不變量 4）。
> base = `http://127.0.0.1:7777`。所有新端點同步寫進 `/manual`。

---

## 契約 delta（相對 milestone-1~3）

| 變更 | 端點 / 形狀 | 服哪條主線 | ticket |
| --- | --- | --- | --- |
| **新** | `GET /desk` / `GET /desk?symbol=` → 多標的/單標的的 funding·OI·清算·basis + 近期 catalysts/news + notable score | 資訊層 | T2 |
| **新** | `POST /thesis` {symbol,direction,conviction,horizon,invalidation,invalidation_price?,evidence,rationale,set_by} → 套用後 posture（防呆回傳） | thesis lever | T4 |
| **新** | `GET /thesis?symbol=` 當前 active thesis；`GET /theses?since=` thesis 史 + outcome | 閉迴路/ablation | T3 |
| **新策略** | `directed`（thesis 驅動；momentum/mean_reversion 留作 baseline-C + info-OFF 對照） | directed 執行 | T4 |
| **增強** | webhook 事件型別：`catalyst` / `funding_extreme` / `liq_cluster` / `thesis_closed`（+ 既有 regime/risk） | event-gating | T1/T2 |
| **增強** | `/positions`·outcome：position tag `thesis_id` → per-thesis 歸因 | 閉迴路 | T3/T4 |
| **新** | ablation：shadow baseline 曲線 + 籃子 A/B 切分 + 決策歸因匯出 | 生死線 | T6 |
| **evva RP** | RP-11 事件路由+窄 lever、RP-12 advice-loop 閉合 | 協作/拓樸 | 回 ../evva |

---

## Ticket 索引

### T1 — 資訊層 feeds（批1：funding / OI / 清算 / basis）
**做什麼**：Sunday ingest 批1 微結構 feed → `perp_metrics` 表（schema 見 product-plan §3.2）。擴 `exchange.py`（已有 `fetch_funding_rate`）+ watcher tick 定期抓 OI / 多空比 / 清算 / basis 寫庫。**批2（news/calendar/onchain）獨立後做**（見 T1.1）。
**檔**：`sunday/feeds.py`（新，ingest）、`migrations/0004_info_layer.sql`、`engine.py` tick 掛 ingest、`store.py` DAO。
**依賴**：無（批1 全是 API 可得）。**可開工**：✅ 現在。
**驗收**：watcher 跑一段後 `perp_metrics` 有多標的時間序列；feed 斷線只記 warning、不崩 tick。

### T1.1 — 資訊層 feeds（批2：news / calendar / on-chain）
**做什麼**：`catalysts` + `news_items` 表 + 策展 ingest（行事曆 API / 新聞源 / 鏈上 provider）。文字源做去重 + 摘要快取；標注 symbols/sentiment。**防 prompt-injection**：Sunday 只存原文摘要，不執行內容。
**檔**：`sunday/feeds.py`（擴）、`migrations/0005_catalysts_news.sql`。
**依賴**：T1 schema 模式；外部 API 選定（待決 §10.6）。**可開工**：schema✅ / ingest 待 API 選定。
**驗收**：`catalysts` 有排程事件（解鎖/macro）；`news_items` 有近期策展新聞；皆可被 `/desk` 引用。

### T2 — `/desk` 綜合決策支援面板
**做什麼**：`GET /desk`（全籃子摘要 + notable 排序）/ `GET /desk?symbol=`（單標的深掘）。Sunday 端算 **notable score**（funding 極值 / OI Δ / 清算簇 / 臨近 catalyst → 加權）。notable 過閾值 → 發對應 webhook（`funding_extreme`/`catalyst`/`liq_cluster`）喚醒專責 analyst（event-gating）。
**檔**：`sunday/desk.py`（純綜合邏輯，可單測）、`app.py` `/desk` 端點、`engine.py` notable→notify 掛 tick、`views.py` 風格的 pure builder。
**依賴**：T1（批1 feed 有資料）。**可開工**：T1 後。
**驗收**：`/desk` 回多標的摘要 + 排序；注入假 funding 極值 → 對應 webhook 發出（V8 風格）；feed 缺時退化為「資料不足」不崩。

### T3 — thesis / outcome 帳本
**做什麼**：`theses` 表（schema 見 product-plan §4.1）+ `GET /thesis`·`GET /theses` 讀端點 + outcome 歸因 lens（position tag `thesis_id`、thesis 轉 closed/invalidated 時結算 `outcome_pnl`）。**POST /thesis 寫入折入 T4**（與 directed 一起）。
**檔**：`migrations/0006_theses.sql`、`store.py` DAO（set/supersede/close、outcome rollup）、`app.py` 讀端點、`views.py` thesis-view pure builder。
**依賴**：positions schema（已有，加 `thesis_id` 欄）。**可開工**：✅ schema + 讀端點現在可定。
**驗收**：thesis 生命週期（active→superseded/closed）留痕；`GET /theses` 回史 + outcome；per-thesis 命中率可查。

### T4 — `directed` 執行模式 + `POST /thesis` lever
**做什麼**：`strategy.py` 加 `directed`（target = active thesis 的 direction；neutral 若無 thesis）。`engine.py` 的 `_open`/reconcile 支援 conviction→size 確定性映射（封套內）+ thesis.invalidation_price 當 stop + thesis 失效/horizon 到期 → 退場。`POST /thesis` lever（idempotent set、supersede、回傳套用後 posture，沿用 M3-T4 防呆）。**確定性風控（check_order/drawdown）不變，仍是最終防線。**
**檔**：`strategy.py`（`directed` 分支）、`engine.py`（directed reconcile + thesis-driven exit）、`risk.py`（conviction→qty 映射 helper）、`app.py` `POST /thesis`、`store.py`（set_thesis/supersede）。
**依賴**：T3 帳本。**可開工**：T3 後。守 **M4-D2**（LLM 不在快路徑）。
**驗收**：`POST /thesis{long,0.5}` → directed 在封套內開 0.5×max 多單 + 掛 stop；過激進 thesis 被 check_order 擋（V6）；thesis invalidated → 自動平。

### T5 — 研究台 roster + skills
**做什麼**：`agents/` 演進（product-plan §5.1）：friday → desk lead（綜合 + `POST /thesis` + 回信採納與否）；analyst 拆 `analyst-flow` / `analyst-news`（+ 批2 後 `analyst-onchain`）；risk-monitor → 對抗式踢館（+ 窄 halt lever，依 RP-11 或降級）；reviewer → post-mortem + playbook（typed-memory）。新 skills：`operate-desk`（leader：thesis recipe + 研究 round 紀律）、`research-*`（各專責 analyst 的 feed recipe）。`evva-swarm.yml` 更新排程。
**檔**：`agents/main/friday/*`、`agents/sub/analyst-*/*`、`agents/sub/risk-monitor/*`、`agents/sub/reviewer/*`、各 `skills/*/SKILL.md`、`evva-swarm.yml`。
**依賴**：T2（/desk）、T4（/thesis）契約定稿。**可開工**：契約定後（skill 是 markdown，無引擎依賴）。
**驗收**：一輪 research round 走完（事件→專責 analyst→friday 綜合 thesis→risk 踢館→POST /thesis→回信）；transcript + `.vero` + theses 為證。

### T6 — ablation 框架 + 一個月 running-test runbook
**做什麼**：ablation harness（product-plan §6）：shadow baseline（C funding-carry / D buy-hold，不下單、對同 tape 算 equity）+ 籃子 A/B 切分（info-ON vs info-OFF）+ 決策歸因匯出（per-thesis / per-catalyst-type / 風險調整指標）。runbook（pre-flight / during / exit gate）。dashboard 加 ablation 對照頁。
**檔**：`sunday/ablation.py`（shadow 計算 + 指標）、`app.py` `/ablation` 端點、`migrations/0007_shadow.sql`、`docs/prd/milestone-4/RUNBOOK.md`、dashboard Desk/Ablation 頁。
**依賴**：T1–T4 跑得起來（要有真實決策可對照）。**可開工**：harness 設計✅ / 全量待 T1-4。
**驗收**：能對一段 testnet 區間產出 A/B/C/D 風險調整對照表 + 決策歸因；即使樣本小也能跑出方向。

### （evva 側）RP-11 / RP-12 — 回填 `../evva`
**做什麼**：把研究台需要、屬 swarm-runtime 的兩個缺口以 RP 形式回填 evva（不在本 repo 改 evva）：RP-11（事件路由 + risk-monitor 窄 halt lever）、RP-12（leader advice-loop 閉合）。並在 RP 裡標注「請 evva 優先既有 structured-output / typed-memory PRD（研究台 thesis/playbook 的天然載體）」。
**檔**：`/Users/johnny/lab/evva/docs/roadmap/veronica/refine-plan/RP-11-*.md`、`RP-12-*.md`。
**依賴**：回 evva。**可開工**：✅ 文件即可（不改 sunday/evva code）。
**驗收**：兩份 RP 在 evva 開好（含 file:line 證據、acceptance、對齊既有 RP 格式）；本 repo 零 evva code 改動（V9）。

---

## 落地序（建議）

```
現在可開工（無外部依賴）
  ├─ T1   批1 feeds（funding/OI/清算/basis）            ← 硬底先做
  ├─ T3   thesis 帳本 schema + 讀端點                    ← 契約定
  └─ RP-11/12  回 ../evva 開 RP                          ← 文件，獨立

T1 → T2（/desk + notable→webhook）
T3 → T4（directed + POST /thesis；守 M4-D2）
T2,T4 → T5（roster + skills）
T1.1（批2 feeds）可與 T2~T5 平行
T1-T4 up → T6（ablation + runbook）

全部 up → M4.1 一個月 testnet running test（= milestone-4 gate）
```

> **先做防守骨架**：T4 的 directed 先支援 `flat`/降風險姿態（Phase A 哨兵），再開方向性建倉（Phase B）。一個月 test 跑完整 directed 台但**預設防守、caps 保守、ablation 全程**（M4-D6）。
