# Gate-2 可行性分析 — 解耦回測 · swarm 整合回測 · 營利

> 狀態：**草案 / Draft（待 grill）** ｜ 日期：2026-06-08
> 配套：[`product-plan.md`](product-plan.md)（產品計畫 — 本文是它每條「可行」的依據）
> 上層 PRD：[`../sunday-project-prd.md`](../sunday-project-prd.md)
> **方法**：本文的「現況」一節是**讀過 `engine/` 全部 ~2.4k LOC 後**的稽核，不是照抄 PRD。每個缺口都附 `檔案:依據`。

---

## 0. 一句話

三個可行性問題，三個誠實答案：

| 問題 | 結論 | 信心 |
| --- | --- | --- |
| **能對策略解耦回測嗎？** | **能，而且比想像便宜**——耦合面只有一個模組（`strategy.py`），核心多數已是純函式。主要新工是「模擬撮合 broker」。 | 高 |
| **能對 swarm + sunday 整合回測嗎？** | **能，分四層（L0–L3）**。L0–L2 完全可行且高價值；L3（重放真 LLM）可行但昂貴/不確定，需一份 evva RP，定位為週期性驗證而非主迴路。 | 中高 |
| **能營利嗎？** | **工程能，alpha 不保證**（上層 §2.1）。本計畫把「找 edge」變成便宜、快、可重複、低風險的搜尋；找不到也只在 testnet/paper 階段便宜地確認。 | 工程高 / alpha 本質不確定 |

---

## 1. 現況稽核（誠實的起點）

### 1.1 已經是「純核心」的部分（解耦的紅利已經一半在了）

這是好消息：**讀取/建議路徑早就是無 IO 的純函式**，可直接進回測核心：

| 模組 | 形狀 | 可直接重用？ |
| --- | --- | --- |
| `indicators.py` | `list[float] → 值`，純 stdlib | ✅ 原封不動 |
| `regime.py` | `classify(Candles) → RegimeRead`，純 | ✅ |
| `advisor.py` | `advise(Candles, funding, active, fast, slow) → dict`，純、**參數已可注入** | ✅（已是典範）|
| `execution.py` | `plan_transition(current, target) → action`，純 | ✅ |
| `attribution.py` | `attribute(switches, positions) → Episode[]`，純、tz-free | ✅ |
| `market.py` | `Candles` 值型別，刻意解耦交易所 wire format | ✅（回測的資料載體）|

> `market.py` 的 docstring 自己就寫了：「保留一個小的 column-oriented 型別…**decouples the strategy/regime logic from the exchange**」。這個 seam 是回測可行性的地基——**它已經在了**。

### 1.2 唯一耦合到「活世界」的模組：`strategy.py`

整個解耦工作量，幾乎集中在這一個檔案。它把三件本該注入的東西寫死成 import：

| 耦合點 | 證據 | 問題 |
| --- | --- | --- |
| **資料抓取寫進決策** | `strategy.py:30,41` — `compute_target` 內 `exchange.fetch_ohlcv(...)` | 策略訊號邏輯與「即時抓 200 根 K 線」綁死；回測無法餵歷史 bar、無「截至第 T 根」的時間游標（無 lookahead 保證）|
| **執行綁交易所單例** | `reconcile`/`_open` → `exchange.close_position` / `place_market` / `set_stop` / `set_leverage` / `fetch_positions` / `fetch_ticker` | `exchange.py` 是 module 級 ccxt 單例 + module 級函式，**無法注入** sim broker（只能 monkeypatch）|
| **狀態綁全域 store** | `reconcile` → `store.current_strategy/record_signal/...` | `store.py` 是 module 級 global pool/redis；回測想用 in-memory 帳本就得 monkeypatch |
| **參數綁全域 settings** | `compute_target` 讀 `settings.ema_fast/ema_slow/timeframe` | 參數是全域單例 → **無法平行跑兩組參數**（網格搜尋的硬傷）|

**結論**：解耦 = 把這四件事從「import 全域」改成「經 port 注入」。耦合面窄（一個模組），是好事。

### 1.3 必須先還的技術債（「專業機器」不能蓋在這上面）

讀碼發現的真實缺陷（非 PRD 已知的 roadmap 缺口，是 bug/drift）：

| # | 缺陷 | 證據 | 影響 |
| --- | --- | --- | --- |
| **DEBT-1** | **宣告的依賴與實際 import 不符** | `pyproject.toml` core deps 無 `ccxt`/`httpx`，且註解寫「no ccxt / urllib+hmac / no httpx」；但 `exchange.py:11 import ccxt`、`events.py:12 import httpx`；`ccxt` 只在 `[modeling]` extra、`httpx` 完全沒列 | **`pip install -e .`（core）後，`import sunday.app` 會因缺 ccxt/httpx 而掛**。RUNBOOK 的安裝指引與實際不符。 |
| **DEBT-2** | **`views.py` 死碼 + 壞測試** | `app.py` 用 `/advisor`（`advisor.py`），**沒 import `views`**；`views.py:35,45,62` 呼叫 `strat.vote_all` / `strat.VALID_STRATEGIES`，但 `strategy.py` 只有 `STRATEGIES`、無 `vote_all`；`tests/test_views.py:22` 呼叫 `views.signals_view(...)` → 會 `AttributeError` | M3 的 `/signals` 設計被 `/advisor` 取代後，`views.py` + 其測試留下成為壞死碼。「80 tests 綠」的宣稱在 main 上對 `test_views.signals_view` 不成立。 |
| **DEBT-3** | **`ohlcv` / `fills` 表有 schema、無 writer** | `0001_init.sql` 定義 `ohlcv`/`fills`；`store.py` **無任何 `INSERT INTO ohlcv/fills`**；行情一律 live `fetch_ohlcv`（`exchange.py:47`）即用即丟 | **postgres 裡沒有歷史 K 線可回放**。原 milestone-2.2「postgres 歷史回放」前提不成立 → 改 mainnet 公開回補（§4.3）。 |
| **DEBT-4** | **PnL 是 proxy，非 fill-by-fill** | `strategy.py:71 _capture_realized` 用平倉前的 `unrealizedPnl` 當 realized；`fills` 表沒寫 | 回測 broker 的損益模型要對齊這個近似（或升級成 fill-by-fill），否則回測 vs live 對不上。 |
| **DEBT-5** | **風控缺角**：無 `/envelope` lever、無 drawdown breaker | `risk.guard` 只檢 size/exposure/leverage（`risk.py:18-26`）；無 drawdown 保險絲；`config.py` 無 `max_drawdown_pct`（只有 `stop_pct`）；app 無 `POST /envelope` | PRD §7.3 要的回撤熔斷 + 封套 lever 尚未實作（屬 1.1 scope 但未落）。「專業」與「營利」都需要它。 |
| **DEBT-6** | **單標的、單週期寫死** | `config.py:18` `symbol="BTCUSDT"`；`tick()`/`halt()` 用 `settings.symbol`；無 basket 設定 | 「專業」需要多標的/多週期；main 上沒有（git log 的 1.2 basket 未在 main）。 |

> **G2.1 必須順手清掉 DEBT-1/2，補上 DEBT-5；DEBT-3/4/6 在 G2.2/G2.3 處理。** 成本都低，但不清就不是「專業機器」。

---

## 2. 可行性一：策略解耦回測

### 2.1 目標架構：ports & adapters（hexagonal）

核心思想：**core 不知道交易所/DB/時鐘存在，只認 port（介面）。** live 與 sim 是兩套 adapter。回測跑的是**同一份**生產 core。

```
sunday/
  core/                  # 純：無 IO、無全域。live 與 backtest 跑同一份。
    candles.py indicators.py regime.py advisor.py attribution.py execution.py   ← 多數已存在
    strategy/            # Strategy 介面 + 各策略；參數可注入（取代 compute_target 讀 settings）
      base.py momentum.py mean_reversion.py flat.py registry.py
    risk.py              # guard(envelope, order, exposure) → Decision（純，不讀 settings、不寫 store）
    portfolio.py         # 新：倉位/權益/保證金會計（sim broker 與 live mirror 共用）
  ports/                 # Protocol 介面
    market_data.py  broker.py  clock.py  ledger.py  event_sink.py
  adapters/
    live/   ccxt_market.py  ccxt_broker.py  pg_ledger.py  wall_clock.py  webhook_sink.py   ← 多數＝現有 exchange/store/events 拆出
    sim/    replay_market.py  sim_broker.py★  sim_clock.py  mem_ledger.py  capture_sink.py
  engine.py              # 迴路（現 strategy.tick + reconcile glue），只依賴 ports
  backtest/  runner.py  metrics.py  policy.py  policies/  sweep.py  data.py
  app.py                 # FastAPI：live wiring + 新 agent-native 端點
```

★ = 主要新工（見 §2.3）。其餘多為**搬移 + 去全域**，非重寫。

### 2.2 四個 port（最小介面）

```python
class MarketData(Protocol):           # 餵 bar，含時間游標 → 無 lookahead
    def ohlcv(self, symbol, tf, limit) -> Candles: ...
    def ticker(self, symbol) -> float: ...
    def funding_rate(self, symbol) -> float | None: ...

class Broker(Protocol):               # 執行
    def position(self, symbol) -> Position | None: ...
    def place_market(self, symbol, side, qty, reduce_only=False) -> Order: ...
    def set_stop(self, symbol, close_side, qty, stop_price) -> Order: ...
    def close(self, symbol) -> Order | None: ...
    def set_leverage(self, symbol, lev) -> None: ...
    def balance(self) -> float: ...

class Clock(Protocol):     def now(self) -> datetime: ...
class Ledger(Protocol):    # record_* / read_*（現 store.py 的 DAO 介面化）
```

`engine.reconcile(symbol, *, market, broker, ledger, clock, envelope, params)` —— 把現在的 import 全域，換成參數注入。**diff 主要是把 `exchange.X` 改成 `broker.X` / `market.X`，把 `store.X` 改成 `ledger.X`，把 `settings.X` 改成 `params`/`envelope`。** 行為不變（G2.1 的 Gate 就是「live 行為不變 + 測試全綠」）。

### 2.3 主要新工：`sim_broker`（模擬撮合）

這是回測「專業 vs 玩具」的分水嶺，也是唯一的大塊新程式。要建模：

| 元素 | 做法 | 為何不可省 |
| --- | --- | --- |
| **成交模型** | next-bar open 成交（或 close ± slippage），**不准用訊號那根 bar 的收盤成交** | 用訊號 bar 成交 = lookahead = 回測作弊，權益曲線必假 |
| **手續費** | taker fee（Binance USDⓈ-M ≈ 0.04%/邊）每筆扣 | 高頻切換的策略，fee 常吃光毛利 |
| **資金費 funding** | 每 8h 依持倉 × funding rate 結算 | 永續核心成本/收益；advisor 已讀 funding，回測必須結算它 |
| **滑價 slippage** | 依下單量/波動的簡單模型 | 市價單真實成本 |
| **停損觸發** | bar high/low 觸及 stop → 該 bar 內成交 | 不模 stop = 高估獲利、低估回撤 |
| **保證金/強平** | 槓桿 × 維持保證金 → 強平價；觸及即強平 | 永續槓桿的尾部風險，少了它回測對風險盲目 |
| **權益/回撤** | 逐 bar mark-to-market → equity curve | 指標（Sharpe/maxDD）的輸入 |

> **保真度校準（對齊 DEBT-4）**：sim_broker 的損益會計先對齊現行 proxy（平倉 unrealizedPnl），G2.4 再用 live 階段捕捉的真實 fills 校準。**校準誤差要量、要報**，否則「專業」是自稱的。

### 2.4 工作量評估

| 工作 | 量 | 風險 |
| --- | --- | --- |
| 抽 ports + 拆 live adapter（搬現有 exchange/store/events）| 中（機械搬移）| 低 |
| 去全域：strategy 參數化、risk 純化 | 中 | 低（測試護航）|
| `sim_broker` + replay_market + sim_clock + mem_ledger | **大**（撮合/費用/funding/強平）| 中（保真度是難點）|
| metrics（Sharpe/Sortino/maxDD/CAGR/turnover/cost-attribution）| 小 | 低 |
| 還 DEBT-1/2/5 | 小 | 低 |

**整體：可行、有界。** 耦合面窄 + 純核心已在，最大不確定性是 sim_broker 保真度（可控、可校準）。

---

## 3. 可行性二：swarm + sunday 整合回測

### 3.1 關鍵洞見：swarm 的工作 = 一個切換政策

agent 在 Gate-1 做的事，本質上是一個函式：

```
SwitchingPolicy:  decide(advisor_panel, current_state) → lever（切策略/調封套/halt）| none
```

LLM agent 是這個政策的一種實作（昂貴、適應性強、非確定）。**規則式 Python stub 是另一種**（便宜、確定、可搜尋）。只要兩者**消費同一個 `/advisor` 面板、輸出同一組 lever 呼叫**，「離線搜尋出的政策」就 = 「線上 agent 該執行的政策」，且兩者差距可量測。

> **這把「整合回測」從「重放昂貴的 LLM」變成「回測一個確定性政策」**——可行性、成本、可重複性全部翻盤。

### 3.2 四層光譜（按可行性與價值排序）

| 層 | 是什麼 | 可行性 | 價值 | 成本 |
| --- | --- | --- | --- | --- |
| **L0 策略回測** | 固定策略（或腳本化切換）跑歷史，量純策略+執行 P&L | ✅ 完全可行、確定、快 | 地基 | 低 |
| **L1 引擎 + 政策 stub** | 用確定性 `SwitchingPolicy` 取代 LLM，跑歷史 → 量「切換政策」的 P&L，**並可 sweep 搜尋好政策** | ✅ 完全可行、確定、快、可平行 | **最高**（§2.1 的 alpha 就在這）| 低 |
| **L2 錄製重放** | 把 live/forward 跑時捕捉的真 agent 決策（`strategy_state` 已存 set_by+reason）當「政策」重放，做反事實（「若 stop 更緊會怎樣」）| ✅ 可行（決策已被捕捉）| 中（驗證真 agent 行為）| 低 |
| **L3 live-LLM 加速模擬** | 真 evva agent 跑在被快轉的 Sunday 上，量真 LLM 切換的整合 P&L | ⚠️ 技術可行、但**昂貴+非確定**，需 evva 改動 | 中（驗證 LLM ≈ 搜尋政策）| **高** |

### 3.3 L3 的硬點與對策（誠實標記）

L3 是唯一**真正困難/不確定**的部分：

- **LLM 慢、貴、非確定**：多日 1h 回測 = 數十~數百 bar，每個 regime_shift 喚醒 friday+analyst（多次 LLM 呼叫）→ 數千次呼叫，慢（小時級）、貴（$）、不可重現。
- **時間膨脹**：live 時 agent 有數分鐘思考；回測要快轉 → sim 時鐘必須 event-driven（agent 思考時暫停 sim time，思考完再推進），而 Sunday 現在的 loop 是 `asyncio.sleep(wall-clock)`（`app.py:52`）。
- **需 evva 能力**：要讓 evva 在「快於 wall-clock」下驅動 agent → **回 `../evva` 開 RP**（守 invariant #4 / G2-D8）。候選 RP：「sim-time / accelerated wake driver」或「headless swarm replay harness」。

**對策**：L3 **不進 sweep 內迴路**。用 L1 離線搜尋好政策（便宜、確定），L3 只當**週期性驗證關**——跑一週歷史，量「真 LLM 的切換」與「L1 搜尋出的政策」差多少。差距大 → 改 skill/prompt/advisor 面板讓 LLM 更逼近；差距小 → 信心。**主迴路是 L1，L3 是體檢。**

### 3.4 結論

「swarm + sunday 整合回測」**可行**，且最有價值的形式（L1）恰好是最便宜、最確定的。真 LLM 重放（L3）可行但昂貴、需 evva RP，定位為驗證而非搜尋。**這正確地把「找切換政策的 alpha」與「驗證 LLM 執行得對不對」分開**——對齊兩段閘門的精神。

---

## 4. 可行性三：營利

### 4.1 拆成兩個問題（這是降焦慮的最大槓桿，沿用 §2.1）

| | 工程可行性 | alpha 可行性 |
| --- | --- | --- |
| 是什麼 | 乾淨執行、準確記帳、確定性風控、回測基建、政策搜尋、安全部署 | 真實、扣成本後、能持續的 edge |
| 結論 | **高**（§2 已論證；2.4k LOC、耦合窄）| **本質不保證**（edge 稀少、脆弱、隨 regime 衰減）|
| 誰能給 | 本計畫 | 沒有人能保證——只能**搜尋 + 誠實驗證** |

**工程不會變出 alpha。** 但工程能讓「有沒有 alpha」變成一個**便宜、快、可重複、低風險**的問題——找到就複利+安全部署，找不到就在 paper 階段便宜地確認。**這就是把它做成回測平台的全部意義。**

### 4.2 候選 edge（研究軌，非承諾）

| edge | 依據 | 風險 |
| --- | --- | --- |
| **regime-timed 切換政策** | §2.1 明指 alpha 在切換政策；L1 可直接搜尋 | regime 偵測落後、切換成本 |
| **funding-carry / basis** | 永續原生；`advisor.funding_context` 已在讀 funding（`advisor.py:72`）| funding 翻向、極端行情 |
| **多標的橫斷面動能** | 籃子分散、相對強弱 | 相關性叢發（幣圈高相關）|
| **vol-targeting / 風險配置** | 改善風險調整後報酬（非方向押注）| 不產生方向 alpha，只改善 Sharpe |

> 純 momentum/MR 在 BTC 1h、扣 taker+funding+slippage 後**歷史多半邊際或負**。所以營利路線**不是**煉某個聖杯指標，而是上面四條（尤其切換政策 + funding carry）。

### 4.3 資料可行性（DEBT-3 的解法）

- postgres 無歷史（DEBT-3）→ **改 mainnet 公開 OHLCV 回補**：ccxt 公開端點**免 API key**即可抓 mainnet 歷史（更長、更真、流動性具代表性），落 parquet/pg（`backtest/data.py` + `POST /data/backfill`）。
- **testnet 不可用於營利結論**：testnet 流動性/funding/成交不具代表性。回測用 mainnet 歷史；paper-forward 用 mainnet 即時資料（read-only，不下真單）。

### 4.4 品質門檻（區分「專業」與「過擬合幻覺」）

回測只值「成本模型 + 防作弊」那麼可信。**這條線是「專業機器」的定義：**

1. **真實成本**：taker fee + 8h funding + slippage（§2.3）。
2. **無 lookahead**：next-bar 成交、指標只用截至當下的 bar。
3. **walk-forward / OOS**：in-sample 調參 → out-of-sample 驗證；報 OOS 指標，不報 in-sample。
4. **paper-forward**：在 mainnet 即時資料上影子跑，先於任何真錢。
5. **成本歸因**：回測輸出要能拆「毛利 vs fee vs funding vs slippage」——很多策略的真相藏在這。

### 4.5 上真錢路徑（硬 gated，G2-D5 / 舊 2.3）

```
in-sample 回測 → walk-forward OOS → paper-forward（mainnet 即時、零真錢）
   → 小額 canary（真錢、硬化 token、kill-switch 演練）→ 持續 live 為正才擴大
```

**獲利的 gate 是 OOS + forward，永遠不是 in-sample 回測。** 任一關不過，停在該關，零真錢損失。

---

## 5. agent-native 可行性

「打造成 agent 專用投資工具」在 invariant #4 下**只能**是 Sunday 端 HTTP（G2-D1）——這反而讓它**更可行**：

- `POST /backtest` / `/backtest/sweep` / `GET /strategies` / `/strategy/outcomes` 都是 Sunday 內回測引擎的薄 HTTP 包裝，agent 用通用 `http_request` 即可呼叫。**零 evva 改動。**
- permission 模型不變：研究/讀端點 GET 放行；部署/調參/封套是 lever POST → 審批（對齊現行 advisor/strategy 的 gating）。
- skill 升級：把「研究→決策→部署→歸因」的 recipe 寫進 `operate-sunday`（leader）/ 新增研究 recipe，dogfood RP-10。

> **能力邊界主張因此更強**：「一個 swarm 只靠通用 http_request + 文件，就能操作一台完整的量化研究+執行平台。」

---

## 6. 風險登記簿

| # | 風險 | 影響 | 對策 | 殘餘 |
| --- | --- | --- | --- | --- |
| R1 | **sim_broker 保真度不足** → 回測騙人 | 高 | §2.3 完整成本模型 + §2.4 對齊 proxy + G2.4 用真 fills 校準、量誤差 | 中 |
| R2 | **回測過擬合** → OOS 崩 | 高 | §4.4 walk-forward + OOS + paper-forward；報 OOS 不報 in-sample | 中 |
| R3 | **alpha 根本不存在** | 高（對營利目標）| 兩段閘門：在 paper 階段便宜確認；零真錢損失。**這是設計，不是失敗** | 低（風險被隔離）|
| R4 | **L3 LLM 成本/非確定** | 中 | L3 出 sweep 內迴路，只當週期性驗證；主迴路用 L1 確定性政策 | 低 |
| R5 | **testnet 資料誤導營利結論** | 中 | 回測用 mainnet 歷史、forward 用 mainnet 即時（G2-D4）| 低 |
| R6 | **技術債（DEBT-1/2）拖慢地基** | 中 | G2.1 順手清（成本低）| 低 |
| R7 | **L3 需 evva 改動但 RP 卡住** | 中 | L3 非主迴路；RP 卡住不擋 L0–L2 與營利主線 | 低 |
| R8 | **多標的相關性叢發**壓 leader 漏斗（上層 §5 已標）| 中 | 沿用 event-gating + 確定性快路徑；籃子大小 sweep 時量漏斗壓力 | 中 |

---

## 7. 工作量與順序

| sub-milestone | 主要工作 | 量 | 關鍵風險 | 前置 |
| --- | --- | --- | --- | --- |
| **G2.1 解耦** | ports/adapters、去全域、strategy 參數化、還 DEBT-1/2/5 | 中 | 低（測試護航；live 行為不變即過）| G2.0 |
| **G2.2 回測+研究API** | sim_broker★、replay、metrics、SwitchingPolicy、sweep、data 回補、agent 端點 | 大 | R1 保真度 | **G2.1**（硬前置）|
| **G2.3 策略擴張+情報** | 多標的/週期、funding-carry、vol-target、第4 lever、envelope、情報/telegram | 大 | R2 過擬合、R8 漏斗 | G2.2 |
| **G2.4 整合驗證** | L2 重放、evva RP（L3 sim-time）、LLM-vs-policy gap | 中 | R4、R7 | G2.2（L2）/ G2.3（L3）|
| **G2.5 上線硬化+canary** | token 硬化、paper-forward、小額 canary、kill drill | 中 | 真錢不可逆 | **全部 + OOS/forward 證據** |

> **G2.1 是一切前置。** 沒有解耦就沒有回測；沒有回測就沒有「營利可被驗證」。**先做 G2.1，且順手把現況稽核的債清掉。**

---

## 8. 驗收 / 品質門檻（怎麼證明「真的能回測、且回測可信」）

- **F1 — 同碼雙跑**：同一份 `core` strategy/risk/reconcile 跑 live 與 sim，行為一致（live 回放一段歷史 ≈ live 當時行為）。
- **F2 — 無作弊**：回測對「未來資訊」的單元測試（餵到第 T 根，斷言看不到 T+1）通過。
- **F3 — costs-aware**：回測輸出含 fee/funding/slippage 拆解；關掉成本 vs 開啟成本的權益曲線差異可見。
- **F4 — 可重現**：同 config 同資料 → 同結果（確定性；L0/L1）。
- **F5 — OOS 紀律**：報告分 in-sample / out-of-sample 兩段，數字分開。
- **F6 — agent 可操作**：transcript 顯示 agent 用 `http_request` 跑 `POST /backtest`、讀結構化結果、據此拉 lever——零 Sunday-specific evva code（沿用 V9）。
- **F7 — 整合可量**：L1 能 sweep 出一個政策；L3（或 L2）能量出「LLM/真 agent 切換」與該政策的差距。

> **F1–F3 是「專業回測」與「玩具回測」的分界線。** 沒有它們，再漂亮的權益曲線都不可信。
