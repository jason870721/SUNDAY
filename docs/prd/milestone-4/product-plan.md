# Milestone 4 — Product Plan：AI 事件驅動永續台（深設計）

> 配 [`README.md`](README.md)（定位 / 決策 / 範圍 / gate）｜ 任務分解 [`milestone-4.0/README.md`](milestone-4.0/README.md)
> 本檔是**架構與設計**：moat 論證、資訊層、thesis 帳本、directed 執行、研究台 workflow、ablation 框架、一個月 runbook。

---

## 1. moat：為什麼這條路有 edge，別的沒有

把「賺錢」拆成三個來源，逐一判斷 LLM swarm 在哪有結構性優勢：

| edge 來源 | 誰已經吃掉它 | LLM swarm 的勝算 |
| --- | --- | --- |
| **價格序列的統計 alpha**（TA、ML、因子） | 系統化 quant（更好的工具、更快） | **輸**。別碰。 |
| **執行/微結構**（maker rebate、低延遲、撮合） | HFT / 做市商 | **輸**。別碰。 |
| **資訊整合 + 事件/敘事定位**（funding 反身性、解鎖、被駭、治理、macro、鏈上、社群風向） | 人類裁量交易員——但**覆蓋不了** N 標的 × M 來源 × 24h | **這裡**。稀疏、異質、文字型、跨域、因果敘事——quant 系統化不了，人類規模化不了。 |

**結論：把全部投資押在第三欄。** 具體三個可辯護的子 edge：

1. **Funding / basis 反身性**（quant-credible 的硬底）：永續 funding 極值 + OI 堆積 + 清算簇 是真實、可量測的 perp 結構。naive carry farmer 會在反身性逆轉時被掃——**LLM 的工作是讀懂「這次 funding 極值會不會violently 逆轉」**（敘事 + 事件脈絡），決定收 carry 還是站旁邊。
2. **事件/catalyst 定位**：解鎖、上架/下架、被駭、治理投票、macro（CPI/FOMC）、ETF 流。排程事件可**預先備好 thesis**；突發事件 Python 先確定性降風險、swarm 隨後判斷。覆蓋廣度（多標的多來源）正是 LLM > 人類處。
3. **資本保全哨兵**（最像「人類贏過系統」、最該先做）：不利事件前主動降風險/flat。這是裁量交易員的核心價值，也最易衡量（回撤降幅）。

> **為什麼 multi-agent（不是單一 LLM）**：第三欄要 **平行廣度**（同時盯 funding / news / 鏈上 / macro）+ **對抗式驗證**（一個 agent 提 thesis、另一個專職踢館，壓制「自信地錯」）+ **持久記憶**（哪種敘事後來怎麼走）。這三者單一 agent 做不好，正是 swarm 協作真正創造價值的地方——也正好是 evva 要驗的能力。

---

## 2. 架構總圖（在既有基板上長出來）

```
  ┌──────────────────── evva swarm "sunday"：研究台 ────────────────────┐
  │  friday(desk lead)  ◄── send_message ──►  analyst-flow / analyst-news │
  │     │  綜合 → POST /thesis、回信採納與否(RP-12)      / analyst-onchain  │
  │     │                                          risk-monitor(踢館+窄halt)│
  │     │  webhook 喚醒(RP-9)：catalyst/funding極值/清算/regime/risk        │
  │     ▼                                          reviewer(復盤→playbook)  │
  └─────┼──────────────────────────────────────────────────────────────────┘
        │ http_request（同一組 + /desk + /thesis）
        ▼
  ┌──────────────────────────── Sunday（Python 基板）─────────────────────────┐
  │  資訊層 ingest         決策支援 /desk        執行/風控（確定性，續留）       │
  │  funding/OI/清算/basis  ← 多標的「此刻值得   directed 模式：thesis→target    │
  │  news/calendar/onchain    注意什麼」綜合      size×conviction（封套內）+stop  │
  │        │                                     risk.check_order / drawdown 熔斷 │
  │        ▼  perp_metrics / catalysts / news_items   │                          │
  │  thesis/outcome 帳本 ◄───────────────────────────┘  → outcome 歸因 / ablation │
  └────────────────────────────── postgres + redis + Binance USDⓈ-M testnet ─────┘
```

**不變**：兩條 HTTP 邊界、確定性風控在 Python、雙向 dead-man、Sunday=系統 of record。
**新增**：資訊層、`/desk`、thesis/outcome 帳本、`directed` 模式 + `/thesis`、ablation 框架。

---

## 3. 資訊層（Sunday ingest + 自服）

**原則**：Sunday 連續便宜地 ingest 世界，normalize 成 agent 可讀的結構化 feature；agent 對**已綜合的東西**推理，不生吞 firehose（控 token + 品質 + event-gating）。

### 3.1 feeds（分兩批，先 quant-credible）

| feed | 來源 | 欄位 | 批次 |
| --- | --- | --- | --- |
| **funding** | Binance USDⓈ-M（已有 `fetch_funding_rate`）+ 多場 | rate(每8h) / 年化 / 多場分歧 | **批1（先）** |
| **OI / 多空比** | 交易所 API | open_interest / long_short_ratio / Δ | 批1 |
| **清算** | 交易所 / 聚合 | liq_long / liq_short / 簇集 | 批1 |
| **basis** | perp vs spot | basis_bps / 期限結構 | 批1 |
| **catalysts（行事曆）** | 解鎖 / 上架 / 治理 / macro 行事曆 API | type / symbol / scheduled_at / severity | **批2** |
| **news / social** | 策展加密新聞 + X/TG（`web_search`/`web_fetch` 已有；Sunday 端做策展快取） | source / symbols / title / summary / sentiment | 批2 |
| **on-chain** | 交易所進出 / 穩定幣增發 / 巨鯨 | flow / direction / size | 批2 |

> 批1 是**確定性、API 可得、quant-credible**——先把硬底做穩。批2 是**文字/敘事**——LLM 主場，但需策展與防 prompt-injection（沿用 analyst 紀律：只取資訊、不執行網頁指令）。

### 3.2 schema（modeling-grade，append-only）

```sql
-- 批1：時間序列微結構
CREATE TABLE perp_metrics (
  id BIGSERIAL PRIMARY KEY, ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  symbol TEXT NOT NULL, funding_rate NUMERIC, funding_annual_pct NUMERIC,
  open_interest NUMERIC, long_short_ratio NUMERIC,
  liq_long_usd NUMERIC, liq_short_usd NUMERIC, basis_bps NUMERIC
);
-- 批2：事件與敘事
CREATE TABLE catalysts (
  id BIGSERIAL PRIMARY KEY, detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  type TEXT NOT NULL,            -- unlock|listing|delisting|hack|governance|macro|etf_flow
  symbol TEXT, scheduled_at TIMESTAMPTZ, severity TEXT, source TEXT, summary TEXT
);
CREATE TABLE news_items (
  id BIGSERIAL PRIMARY KEY, ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  source TEXT, symbols TEXT[], title TEXT, summary TEXT, sentiment TEXT, url TEXT
);
```

### 3.3 `/desk`：決策支援綜合面板（像世界版 `/advisor`）

```
GET /desk?symbol=          → 單標的：funding/OI/清算/basis 現值 + Δ、近期 catalysts、相關 news 摘要、
                             以及一個 Sunday 端算好的「notable score」（這標的此刻多值得注意）
GET /desk                  → 全籃子：每標的一行摘要 + 排序（最 notable 在前）→ swarm 先看哪個
```

`/desk` 是 agent 進場第一站：**它告訴 swarm「此刻把注意力放哪」**，再深挖個別 feed。它也是 event-gating 的依據：notable score 過閾值 → Sunday 發 webhook 喚醒對應專責 analyst。

---

## 4. thesis / outcome 帳本 + `directed` 執行（核心新機制）

### 4.1 thesis = swarm 表達觀點的結構化載體

```sql
CREATE TABLE theses (
  id BIGSERIAL PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by TEXT NOT NULL,           -- 'friday'（desk lead）
  symbol TEXT NOT NULL,
  direction TEXT NOT NULL,            -- long | short | flat
  conviction NUMERIC NOT NULL,        -- 0..1（→ 決定 size 佔封套比例）
  horizon TEXT,                       -- e.g. '4h' | '2d'（→ 影響 exit / 重評）
  invalidation TEXT,                  -- 文字 + 選填價格位（thesis 失效條件）
  invalidation_price NUMERIC,
  evidence JSONB,                     -- refs: catalyst ids / news ids / metric 讀數
  rationale TEXT NOT NULL,            -- 為何（留存給 User，§7.11）
  status TEXT NOT NULL DEFAULT 'active', -- active|closed|invalidated|superseded
  closed_at TIMESTAMPTZ, outcome_pnl NUMERIC, outcome_note TEXT
);
```

一個標的同時最多一個 `active` thesis（新的 supersede 舊的，append-only 留痕）。**thesis 是 audit + ablation 評分 + User legibility 的單一真相源。**

### 4.2 `directed` 執行模式：LLM 設 WHAT、Python 做 HOW（守不變量 7）

新策略值 `directed`。當某標的當值策略 = `directed` 且有 `active` thesis：

```
target_side   = thesis.direction                       （long/short/flat）
target_size   = conviction × envelope.max_position_usd  （確定性映射，封套硬上限）
stop          = thesis.invalidation_price（若有）否則 envelope.stop_pct
exit 觸發      = thesis 被 invalidated/closed/superseded、或 stop 命中、或 horizon 到期重評
```

**全部在 Python 確定性執行**：sizing、進出場時機、掛 stop、管理、`risk.check_order` gate、drawdown 熔斷——**一行 LLM 都不在快路徑**。LLM 只提供 thesis（慢、meta、有後果），與既有「切策略」lever 同一個安全層級。

> 這是「AI 操盤」的精確定義：**swarm 決定方向/信念/失效條件；引擎決定多大、何時、何價、何時止損。** thesis 再激進，封套與熔斷仍是最終防線（誰下令都擋，沿用 V6）。

### 4.3 `/thesis` lever（第四個輸入；僅 leader）

```
POST /thesis  {symbol, direction, conviction, horizon, invalidation, invalidation_price?,
               evidence, rationale, set_by:"friday"}
   → 寫 theses（supersede 同標的舊 active）；若該標的當值策略非 directed，一併切到 directed
   → idempotent set 語意（同 thesis 重送 = 同狀態）；回傳套用後的 target posture（防呆，沿用 M3-T4）
GET  /thesis?symbol=        → 當前 active thesis
GET  /theses?since=         → thesis 歷史 + outcome（ablation / reviewer 用）
```

權限同其他 lever：POST → ask（leader-only 由 skill 紀律 + permission 承擔，沿用 §8）。**確定性風控不被繞過**。

### 4.4 outcome 歸因（閉迴路，沿用 M3-T3 lens 思路）

position 開倉時 tag `thesis_id`；thesis 轉 closed/invalidated/superseded 時，從關聯 positions 的 realized/unrealized 結算 `outcome_pnl` + reviewer 寫 `outcome_note`。→ **per-thesis 命中率、per-catalyst-type 績效、「失效條件是否及時觸發」** 全可查。這是 ablation 與 playbook 學習的資料地基。

---

## 5. 研究台 workflow（swarm 協作的價值落地）

### 5.1 roster 演進（從監督員 → 研究台）

| 成員 | 原角色 | milestone-4 角色 | 喚醒 |
| --- | --- | --- | --- |
| **friday** | CEO/風險長 | **desk lead**：派研究、綜合 thesis、`POST /thesis`、回信採納與否（RP-12）、kill | webhook（catalyst/funding/risk）+ user + dead-man timer |
| **analyst-flow** | （原 analyst 拆分） | funding / OI / 清算 / basis 的反身性判讀 | webhook(`funding_extreme`/`liq_cluster`) + 指派 |
| **analyst-news** | 新增 | 新聞 / 社群 / 行事曆 catalyst 判讀（防 injection） | webhook(`catalyst`) + schedule(每 30m 掃) |
| **analyst-onchain** | 新增（批2 後啟用） | 鏈上流向 / 穩定幣 / 巨鯨 | webhook + schedule |
| **risk-monitor** | 巡檢 | **對抗式踢館**：專職證偽 thesis（下檔、crowding、相關性、funding trap）+ 窄 halt lever（RP-11） | webhook(`risk_breach`) + 每個 draft thesis |
| **reviewer** | 日復盤 | **post-mortem + playbook**：thesis 結果歸因，寫入 typed-memory playbook | cron(每日) + webhook(`thesis_closed`) |

> reporter 併入 reviewer（狀態快照可由 dashboard 自服，不需專人）。roster 大小可調（§12 待決），但「平行專責 + 對抗式 risk + 復盤 playbook」是骨架。

### 5.2 一輪研究（research round）

```
觸發：Sunday /desk notable score 過閾值 → webhook 喚醒對應專責 analyst（event-gated）
  1. 平行蒐證：專責 analyst 查自己領域的 feed（/desk?symbol、/market、web）→ 結構化 finding
     （POST /commentary 推 User-visible 脈絡；send_message 給 friday）
  2. 綜合：friday 整合 findings → 草擬 thesis（方向/信念/失效/證據）
  3. 對抗式踢館：friday send_message 給 risk-monitor「試圖證偽這個 thesis」
     → risk 回「下檔/crowding/funding 逆風/相關性」評估（多數反對 → 降 conviction 或不發）
  4. 拍板：friday POST /thesis（directed 模式接管執行）；回信各 analyst「採納/不採納 + 一句why」(RP-12)
  5. 復盤：thesis 平掉 → reviewer 歸因 → 寫 playbook（typed-memory）→ 下一輪可檢索
```

**平靜時段**：`/desk` 無 notable → 無 webhook → swarm idle（沿用 event-gated，不燒 token）。

### 5.3 為什麼這能壓制「LLM 自信地錯」

- **對抗式 risk-monitor**：thesis 預設要過踢館才發；專職證偽 ≠ 附和。
- **確定性封套**：thesis 再錯，size/stop/drawdown 由 Python 擋住損失幅度。
- **invalidation 必填**：每個 thesis 自帶失效條件 → directed 模式自動退場，不靠 LLM 記得平倉。
- **playbook 記憶**：reviewer 把「這種敘事上次怎麼走」寫進 typed-memory → 下次 thesis 有歷史校準。

---

## 6. ablation 評測框架（生死線；M4-D5）

**要回答的唯一問題**：**資訊層 + agent 綜合，到底有沒有加值？** 沒這個答案，整個 milestone 是昂貴劇場。

### 6.1 對照組

| 組 | 怎麼跑 | 答什麼 |
| --- | --- | --- |
| **A. full desk（info ON）** | 完整研究台 + 資訊層 + directed | 我們的主張 |
| **B. info-OFF（同 swarm）** | 同 roster/prompt，但 `/desk` 回空、無 feed → agent 只剩價格 | **資訊層有沒有加值？**（最關鍵對照） |
| **C. 確定性 baseline** | 純規則：funding-carry + 簡單 regime（無 LLM） | **LLM 有沒有贏過便宜規則？** |
| **D. buy-and-hold** | 籃子等權持有 | beta 基準 |

### 6.2 怎麼在一個 testnet 帳戶上跑（務實）

- **C、D 用 shadow（影子）計算**：不下單，Sunday 對同一 tape 計算「baseline 此刻會持什麼」→ 記 shadow equity 曲線。零資金、與 A 同期。
- **A vs B 用籃子切分 A/B**：籃子一半標的跑 info-ON desk、一半跑 info-OFF（同 swarm、關 feed），同期、同 caps。一個月後比兩半的風險調整表現。（標的相關性高 → 也輔以 shadow B 對「全籃子 info-OFF」的估計。）
- **決策歸因**：每筆 directed 進出場 tag thesis_id + 觸發來源（哪個 feed / catalyst）→ 拆解「哪類資訊貢獻了哪些結果」。

### 6.3 指標（風險調整，不只 P&L）

- **Sharpe / Calmar**、**max drawdown**、**事件期間回撤**（哨兵該救的東西）、**per-thesis 命中率**、**per-catalyst-type 期望值**、**invalidation 及時率**、**每決策 token 成本**。
- **kill-line**：若 **A 在風險調整上贏不過 B（info-OFF）**，資訊層無加值 → 砍 feed 或重設計；若 **A 贏不過 C（規則 baseline）**，LLM 層無加值 → 收斂成規則。**贏不過就不轉真錢（M4-D9）。**

---

## 7. 一個月 running test — runbook

### 7.1 pre-flight（開跑前）

- 資訊層批1 feeds 健康（`/desk` 多標的有值；斷線退化測過）。
- 封套保守（單筆/曝險/槓桿/回撤 caps 偏緊；M4-D6 防守先行）。
- roster 排程就緒（analyst 群 webhook+schedule、risk 踢館、reviewer cron）。
- dead-man 雙向 wired（friday heartbeat / Sunday watchdog）。
- ablation 開：A/B 籃子切分 + C/D shadow 啟動。
- RP-11/12 若 evva 尚未實作 → 以**現有機制**降級跑（leader 手動回信 = RP-12 的人工版；事件全進 leader = 無 RP-11 的單漏斗版），並記為 test 的已知限制。

### 7.2 during（跑一個月）

- **每週**：reviewer 產出週報（thesis 命中、ablation 中間對照、incident log）。
- **V8 注入測**：人為塞假 `catalyst` / `funding_extreme` → 確認對應 analyst 醒來、thesis 流程走完、directed 反映。
- **成本**：每日 token/run（沿用 V5）；idle 時段確認 swarm 真的睡。
- **incident**：dead-man / safe-mode / feed 斷線 各至少自然或注入觸發一次（沿用 V7）。

### 7.3 exit（gate）

產出三份東西：

1. **swarm 耐久報告**（V1/V5/V7 在一個月真實時間下成立）。
2. **研究台機制報告**（每條協作箭頭有佐證：事件→專責→綜合→踢館→拍板→執行→復盤）。
3. **ablation 報告**（A/B/C/D 風險調整對照 + 決策歸因）——**這份決定要不要轉真錢**。

> 通過 = 機制正確 + ablation 顯示資訊層有方向性加值（即使幅度小、樣本小）。**不通過不是失敗**——是「資訊 edge 假設被證偽」的寶貴結論，省下真錢。

---

## 8. 對既有資產的影響

- **Sunday engine**：新增資訊層 ingest（批1 先）、`/desk`、thesis/outcome 帳本 + `directed` 模式 + `/thesis`、ablation harness。**既有確定性風控/執行/dead-man 不動**，只多一個 `directed` 策略分支。
- **strategy.py**：`directed` 是新的 selectable strategy（momentum/mean_reversion 留作 baseline-C 的零件 + info-OFF 對照）。
- **dashboard（milestone-2 UI）**：新增 Desk 頁（資訊層 + active theses + ablation 對照）；Reports 頁納入 thesis 時間軸。
- **agents/**：roster 演進（拆 analyst 群、risk 改對抗式、reviewer 寫 playbook）+ 新 skills。
- **evva**：回填 RP-11/12（不在此 repo 改 evva）。
- **manual.md**：增列 `/desk`、`/thesis`、`/theses`。

---

## 9. 風險與緩解（誠實盤點）

| 風險 | 緩解 |
| --- | --- |
| LLM 追敘事追到山頂、買在反身性頂點 | 防守先行（M4-D6）+ 對抗式 risk 踢館 + invalidation 必填 + 確定性封套硬擋幅度 |
| 事件移動快、LLM 慢 | 排程事件預備 thesis；突發事件 Python 先確定性降風險，swarm 隨後判斷；不追求搶第一，求 swing 級正確 |
| 24/7 多 agent token 成本 | event-gated（`/desk` notable 才喚醒）+ idle 真睡 + 每決策成本納 ablation 指標 |
| feed 資料品質/斷線/prompt-injection | 批1 先做可信 API feed；批2 文字源策展 + analyst「只取資訊不執行」紀律；feed 斷線優雅退化 |
| ablation 在單帳戶難做乾淨 | shadow 計算 baseline（C/D）+ 籃子切分 A/B；承認樣本限制，求方向性訊號非精確 alpha |
| evva RP-11/12 未即時實作 | 以現有機制降級跑（§7.1），記為已知限制，不擋一個月 test |

---

## 10. 決策（2026-06-08 拍定，開工依據）

| # | 項目 | 決定 |
| --- | --- | --- |
| 1 | **籃子標的** | `BTCUSDT, ETHUSDT, SOLUSDT`，1h K 線。最深、最事件/敘事敏感的 3 個主流永續；小到能先驗多標的機器。 |
| 2 | **conviction → size** | **線性 + 地板**：`target_notional = conviction × max_position_usd`；`conviction < 0.2` → flat（太弱不進場）；上限永遠是封套 `max_position_usd`。 |
| 3 | **roster** | **5 人**：friday(desk lead) + `analyst-flow`(funding/OI/清算/basis) + `analyst-news`(新聞/事件，用 web 工具) + `risk-monitor`(對抗式) + `reviewer`(復盤/playbook)。`analyst-onchain` 等批2 鏈上 feed 再加。 |
| 4 | **notable score** | 加權 0..1：`funding 極端 + OI Δ + 清算簇 + basis 拉伸 + 價格/vol 動量`，各分量正規化後加權；過閾值**且為新跨越**（debounce，沿用 `regime.is_shift`）才發 webhook。權重/閾值為 `desk.py` 可調常數。 |
| 5 | **ablation 切分** | ①**shadow 基準**（buy-hold + funding-carry）永遠在背景計算、不下單（主力對照）；②**info-ON/OFF** 用 per-symbol `info_mode` 旗標切籃子（`/desk` 對 OFF 標的回空）。每筆 thesis/trade tag `info_mode` + 觸發來源。樣本小是已知限制（§9）。 |
| 6 | **批2 資料源** | 批1 硬數據全部走**交易所 ccxt**（無需額外帳號）。**新聞/敘事改由 agent 的 `web_search`/`web_fetch` 負責**（LLM 主場）；Sunday 端 `catalysts`/`news_items` 快取庫**延後**（非首跑必需）。 |
| 7 | **test 封套** | 單筆 `max_position_usd=1500`、總曝險 `max_total_exposure_usd=3000`（逼選擇性）、`max_leverage=3`、`max_drawdown_pct=5`、`stop_pct=0.02`、conviction 地板 0.2。reviewer 週報 cron。防守優先（M4-D6）。 |
