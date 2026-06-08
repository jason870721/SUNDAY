# Gate-2 產品計畫 — Sunday：agent 專用的量化投資平台

> 狀態：**草案 / Draft（待 grill）** ｜ 日期：2026-06-08 ｜ 階段：**Gate-1 已驗收 → 全面進入 Gate-2**
> 上層 PRD：[`../sunday-project-prd.md`](../sunday-project-prd.md)（§2 兩段閘門、§2.1 生產等級≠賺錢、§10 Gate-2、D11/D14）
> 配套：[`feasibility-analysis.md`](feasibility-analysis.md)（可行性與風險分析 — 本計畫每條「可行」都在那裡有依據）
> 本文與既有 [`README.md`](README.md)：本文**re-center** 既有 milestone-2 的 2.1/2.2/2.3（2.0 dashboard 維持已完成）。詳見 §3。

---

## 0. 一句話定位

Gate-1 證明了「**一個 evva swarm 能用通用工具監督一個 Python 交易引擎**」。Gate-2 要回答下一個問題：

> **這個 swarm + 引擎，能不能真的賺錢？**

而要誠實地回答「能不能賺錢」，唯一的辦法是把 Sunday 從「一個會跑的笨策略引擎」升級成一台 **可解耦、可回測、可研究、可安全上線的專業交易機器**——並且把它打造成 **agent 專用的投資工具**：agent 不再只是「監督一個黑箱」，而是用 Sunday 來 **研究 → 決策 → 執行 → 學習**。

**北極星不變（D1）：Gate-2 的成敗 = 真實長期 P&L。** 但本計畫的核心主張是——**工程能保證的是「讓 edge 可被發現、可被複利、可被安全部署」；工程換不到 edge 本身。** 這份計畫把「找不找得到 alpha」這個唯一無保證的問題，變成一個**便宜、快速、可重複、低風險**的搜尋問題。

---

## 1. 從 Gate-1 到 Gate-2：到底變了什麼

| | Gate-1（已完成） | Gate-2（本計畫） |
| --- | --- | --- |
| **衡量** | swarm 對不對（監督/反應/叫停確定性正確） | **賺不賺**（真實長期風險調整後 P&L） |
| **環境** | Binance testnet | 回測（mainnet 歷史）→ paper-forward（mainnet 即時）→ 小額 mainnet（硬 gated） |
| **Sunday 的角色** | 笨策略引擎（momentum/MR/flat，單標的 1h），故意不在乎賺賠 | **專業量化引擎**：多標的、多週期、可回測、costs-aware、可研究 |
| **agent 的角色** | 隔著 HTTP 監督黑箱的「瞎子監督者」（M3 已開眼） | **投資研究員 + 投資組合經理**：用 Sunday 回測、選策略、調參、部署、歸因學習 |
| **alpha 在哪** | 不追（D1） | **切換政策 + 策略庫 + 風險配置**——可被離線搜尋、線上逼近、持續歸因 |

**三個用戶的明確需求（你這次的指令）對應到本計畫：**

| 你說的 | 在本計畫裡是 |
| --- | --- |
| 「達到專業策略交易機器等級」 | §6 G2.1（解耦核心）+ G2.3（策略擴張）+ §4 品質門檻（costs/walk-forward）|
| 「解耦設計，可以對策略進行回測」 | §6 G2.1（ports & adapters）+ G2.2（回測引擎 L0/L1）|
| 「甚至對 swarm team + sunday 整合回測」 | §6 G2.2 的 `SwitchingPolicy` + G2.4（整合驗證 L2/L3）；可行性見 feasibility §3 |
| 「以營利為目的」 | §4 北極星 = P&L；但見 feasibility §4 的誠實邊界 |
| 「打造成 agent 專用的投資工具」 | §2 產品願景 + §7 agent-native API 藍圖（整份計畫的脊椎）|

---

## 2. 產品願景：Sunday = agent 專用的量化投資平台

**不變量 #4（evva 內零 Sunday-specific code）反而定義了這個產品的形狀。** agent 不能有「Sunday 客製工具」，所以「agent 專用」**只能**體現為一件事：

> **Sunday 自己用一套結構化、可被 LLM agent 操作的 HTTP 介面，把「一個量化投資者需要的全部能力」暴露出來。**

agent 用通用 `http_request` + skill + `/manual` 就能驅動完整的投資工作流。這台機器要服務的，是一個 **LLM 投資者**，不是一個人類交易終端。

### 2.1 agent 的投資迴路（產品的核心）

```
        ┌─────────────────────────── agent（friday / analyst）─────────────────────────┐
        │                                                                              │
        │   ① 研究 RESEARCH        ② 決策 DECIDE        ③ 執行 ACT       ④ 學習 LEARN     │
        │   GET  /advisor          （讀回測證據）        POST /strategy    GET /strategy/  │
        │   POST /backtest         + /advisor 面板       （切策略/調參/    outcomes        │
        │   POST /backtest/sweep   → 形成有證據的判斷     部署回測過的config）GET /performance│
        │   GET  /strategies                            POST /envelope    （歸因→下次更好）│
        │        ▲                                            │                  │        │
        └────────┼────────────────────────────────────────────┼──────────────────┼────────┘
                 │ 通用 http_request（GET 放行 / lever POST 審批）│                  │
                 ▼                                              ▼                  ▼
        ┌────────────────────────────── Sunday（:7777, Python）────────────────────────────┐
        │   解耦核心（pure）：strategy 庫 · risk · regime · advisor · attribution            │
        │   ├─ live 適配器   → ccxt（mainnet/testnet）· postgres · 即時時鐘                  │
        │   └─ sim 適配器    → 歷史回放 · 模擬撮合（fills/fees/funding/stop）· 模擬時鐘        │
        │   回測引擎 + 政策搜尋 + 指標（Sharpe/maxDD/…）+ 歷史資料庫（mainnet 公開回補）      │
        └──────────────────────────────────────────────────────────────────────────────────┘
```

**這個迴路的關鍵升級（相對 Gate-1）：** agent 的 lever 不再是「憑 advisor 面板拍腦袋切策略」，而是「**先回測、拿證據、再切**」。`POST /backtest` 讓 agent 在動真倉之前，先在歷史上驗證「如果這個 regime 我切到 mean_reversion，過去會怎樣」。**這才是「專業」與「agent 專用」的交集**：把人類 quant 的研究流程，變成 agent 可呼叫的端點。

### 2.2 為什麼這同時滿足「專業」「回測」「營利」「agent 專用」

- **專業**：可回測 + costs-aware + walk-forward + 多標的 = 量化團隊的標準工程基線（§4）。
- **回測**：解耦後，**同一份策略/風控/reconcile 程式碼**跑 live 也跑回測（feasibility §2）——回測驗的是生產引擎，不是另一份重寫。
- **營利**：回測 + 政策搜尋 + 歸因把「找 edge」變成可搜尋、可複利的流程；上真錢硬 gated 在 OOS + forward 證據後（§4、§6 G2.5）。
- **agent 專用**：以上全部是 Sunday 端 HTTP，agent 用通用工具就能操作；零 Sunday-specific evva code（守不變量 #4）。

---

## 3. 與既有 milestone-2 的關係（re-center，不是另起爐灶）

既有 [`README.md`](README.md) 把 Gate-2 拆成 2.0/2.1/2.2/2.3。Gate-1 完成、且你把目標明確定為「營利 + 專業回測 + agent 專用」之後，原拆解有兩處不足，本計畫據此 re-center：

| 既有 | 問題 | 本計畫的處理 |
| --- | --- | --- |
| **2.0 dashboard** ✅ | 無 | **保留為已完成。** Gate-2 的觀測層。 |
| **2.2「回測引擎（postgres 歷史回放）」** | 只有一行；且**前提錯誤**——引擎從未寫過 `ohlcv` 表（feasibility §1），postgres 裡沒有歷史可回放；也沒講「解耦」這個前置工程 | 升為本計畫主體：**G2.1 解耦 + G2.2 回測引擎**，資料改由 mainnet 公開歷史回補 |
| **「swarm + sunday 整合回測」** | 原文完全沒有 | 新增：**`SwitchingPolicy`（G2.2）+ 整合驗證（G2.4）**，把「swarm = 切換政策」這個洞見變成可回測的東西 |
| **2.1 情報 / 2.3 真錢** | 排序與內容仍有效 | 併入新的 sub-milestone 序列（§6）：情報併進 G2.3、真錢硬化併進 G2.5 |

> **一句話：** 本計畫不推翻 milestone-2 的閘門紀律（真錢最後、硬 gated、零 evva 客製、確定性風控在 Python 層），只是把「回測 + agent-native」從一行字擴張成一條有工程地基的主線，並補上原拆解缺的「解耦」前置與「整合回測」。

---

## 4. 北極星與誠實邊界

**Gate-2 成敗 = 真實長期、風險調整後 P&L 為正（OOS + forward 證實，非 in-sample 回測）。**

本計畫對「營利」採取上層 §2.1 的紀律，講死三件事（完整論證見 feasibility §4）：

1. **工程可行性 = 高。** 解耦、模擬撮合、回測、政策搜尋、agent API——都是有界、可估、標準的量化工程（codebase 僅 ~2.4k LOC，耦合面只有一個模組）。
2. **alpha 可行性 = 本質不保證。** 純 momentum/MR 在 BTC 1h、扣掉 taker fee + funding + slippage 後，歷史上多半邊際或負報酬。**工程不會變出 edge。**
3. **本計畫能保證的，是把「找 edge」變成一個便宜、快、可重複、低風險的搜尋。** 找到 → 複利、安全部署；找不到 → **在 testnet/paper 階段就便宜地確認**，不賠真錢。這就是兩段閘門的價值。

**候選 edge（當研究軌、非承諾）：** ①regime-timed 切換政策（§2.1 的 alpha 主張）；②funding-carry / basis（永續原生，advisor 已讀 funding）；③多標的橫斷面動能；④vol-targeting / 風險配置（改善風險調整後報酬，而非方向）。

> **品質門檻（區分「專業機器」與「過擬合幻覺」）：** 真實 mainnet 歷史資料、真實成本模型（taker fee≈0.04% + 8h funding + slippage）、next-bar 成交（無 lookahead）、walk-forward OOS、paper-forward on mainnet data 才准碰真錢。細節見 feasibility §4.4。

---

## 5. 決策紀錄（G2-D1..D8）

| # | 決策 | 為什麼 |
| --- | --- | --- |
| **G2-D1** | **「agent 專用投資工具」= Sunday 端豐富 HTTP API + skill + `/manual`，不是 evva 客製工具** | 守不變量 #4。能力邊界主張更強：「agent 只靠通用 http_request + 文件就能驅動一台完整量化平台」。 |
| **G2-D2** | **解耦採 ports & adapters（hexagonal）**：core 純、live/sim 兩套適配器 | 回測必須跑**同一份**生產策略/風控碼，否則驗的是重寫不是產品。現有 advisor/regime/execution 已是純函式，半套架構已在（feasibility §2）。 |
| **G2-D3** | **「swarm + sunday 整合回測」= 回測 `engine + SwitchingPolicy`**；LLM 是政策的一種實作 | swarm 的工作本質就是一個切換政策（§2.1）。把政策抽象成介面，離線搜尋的政策 = 線上 agent 該執行的政策，且可量測兩者差距。讓「整合回測」從「重放昂貴 LLM」變成「回測確定性政策」。 |
| **G2-D4** | **回測資料 = mainnet 公開歷史回補（ccxt 公開端點，免 key）**，不靠 testnet 累積 | 引擎從未寫 `ohlcv` 表（feasibility §1），testnet 流動性/funding 不具代表性。mainnet 公開 OHLCV 免帳號即可取，歷史更長、更真。 |
| **G2-D5** | **真錢最後、硬 gated**：OOS + paper-forward 證實後才小額 canary | 對齊既有 2.3 + invariant #1/#10。營利是目標，但真錢是最不可逆的一步，放最後。**你可在 review 推翻 sequencing，但需說明為何提前上真錢能降低風險。** |
| **G2-D6** | **先還技術債再談專業**：修 packaging（ccxt/httpx 未列 deps）、清 `views.py` 死碼、補 `/envelope` + drawdown breaker | 「專業機器」不能蓋在 import 就掛、有死碼、風控缺角的地基上（feasibility §1）。這是 G2.1 的一部分，便宜但必要。 |
| **G2-D7** | **確定性風控在回測與 live 共用同一份 `risk` core**；LLM 永不在快路徑 | 對齊 invariant #3/#7。回測必須含與 live 相同的風控保險絲，否則回測的權益曲線是假的（會做出 live 永遠下不出去的單）。 |
| **G2-D8** | **整合回測的 live-LLM 模式（L3）需 evva 能力 → 回 `../evva` 開 RP**，不在本 repo 改 evva | 守不變量「swarm 缺能力開 RP，不 fork」。L3 是唯一需要 evva 改動的部分，且非主迴路（用作週期性驗證，feasibility §3）。 |

---

## 6. 範圍與順序（五個 sub-milestone）

> 每個 sub-milestone 有明確 **Gate**（工程驗收，**非獲利驗收**，除了最後上真錢那關）。工作量/依賴/風險見 feasibility §7。

| 版本 | 主題 | 範圍（重點） | 環境 | Gate（驗收） |
| --- | --- | --- | --- | --- |
| **G2.0** ✅ | 觀測層 | Sunday 自服 dashboard（已完成的舊 2.0） | testnet | （已達）|
| **G2.1** | **解耦核心** | ports & adapters；core 純化；strategy 參數可注入；**還債**（packaging / `views.py` / `/envelope` / drawdown breaker）；live 行為不變 | testnet | live 引擎在新適配器上行為不變 + 單元/契約測試全綠 + 一個 trivial 回放跑通 |
| **G2.2** | **回測引擎 + agent 研究 API** | sim broker（fills/fees/funding/stop/margin）+ 歷史回放 + 指標 + `SwitchingPolicy` + sweep；mainnet 歷史回補；`POST /backtest`·`GET /strategies`·`POST /backtest/sweep`·`/strategy/outcomes`；agent 研究 skill | 回測 | agent 用 `http_request` 跑一次 costs-aware 回測並據此行動；同參數結果可重現 |
| **G2.3** | **策略擴張 + 情報**（併舊 2.1） | 多標的籃子 + 多週期 + funding-carry 策略 + vol-targeting sizing；第 4 lever（調參）+ envelope lever；analyst 外部輸入（fear&greed/on-chain/news）+ telegram 播報 | 回測 + testnet | walk-forward OOS 顯示**至少一個 config 在多 regime、含成本下存活**（工程 gate，非獲利承諾）|
| **G2.4** | **整合驗證 + evva RP** | 錄製重放（L2 反事實）；回 `../evva` 開 RP（sim-time / headless swarm replay）；週期性量測「LLM 切換 vs 搜尋出的政策」差距（L3）| 回測 + testnet | 量出 LLM-vs-policy gap；RP 已 filed 於 `../evva` |
| **G2.5** | **上線硬化 + canary**（舊 2.3，硬 gated）| webhook 窄 token + command token + mainnet key；paper-forward；小額 canary；kill-switch 演練 | **mainnet** | OOS + forward 為正 → 小額 canary；**持續 live 為正才擴大** |

```
G2.0 ✅ ──► G2.1 解耦 ──► G2.2 回測+研究API ──┬──► G2.3 策略擴張+情報 ──► G2.5 canary🔒
   觀測         │（前置：一切的地基）          └──► G2.4 整合驗證+evva RP ──┘
              還債也在這
```

> **關鍵依賴**：G2.1 是**一切的前置**（沒有解耦就沒有回測）。G2.2 之後 G2.3/G2.4 可部分平行。G2.5 硬 gated 在前面全綠 + OOS/forward 證據。

---

## 7. agent-native API 藍圖（G2-D1 的具體化）

新增/增強的端點（全 Sunday 端，agent 用通用 `http_request`；GET 放行、lever POST 審批；寫進 `/manual` + skill）：

| 類 | 端點 | 給 agent 的能力 | sub-milestone |
| --- | --- | --- | --- |
| 研究 | `POST /backtest` | 「用策略/政策 X、參數 Y、標的/週期 Z、期間 W 回測」→ 結構化 metrics + 權益曲線 + per-regime + 成本歸因 | G2.2 |
| 研究 | `POST /backtest/sweep` | 參數/政策網格搜尋 → 排名後的 config 清單（agent 的「研究」工具）| G2.2 |
| 研究 | `GET /strategies` | 策略庫 introspection：可用策略 + 參數（含建議範圍）+ live/回測歷史績效 | G2.2 |
| 研究 | `GET /advisor`（增強）| 多標的/多週期；加 expected-edge、regime 轉移機率、funding carry、「此建議的回測表現」| G2.2/G2.3 |
| 決策→執行 | `POST /strategy`（增強）| 第 4 lever：可帶 `params`（調參）；可「部署一個回測過的 config」| G2.3 |
| 執行 | `POST /envelope` | 風險封套 lever（**目前缺，G2-D6 補**）| G2.1/G2.3 |
| 學習 | `GET /strategy/outcomes` | 每次切換的結果歸因 lens（M3-T3 設計，接成真端點）| G2.2 |
| 學習 | `GET /performance`（已有）| per-strategy 績效歸因 | ✅ |
| 資料 | `GET /data/coverage`·`POST /data/backfill` | agent 查/觸發歷史資料覆蓋（mainnet 回補）| G2.2 |

> **設計原則（沿用 M3 legibility）**：agent 讀到的一律是 **derived + 帶理由** 的結構化結果，不是 raw。回測回的是 metrics 與歸因，不是要 agent 自己算 Sharpe。

---

## 8. 守住的不變量（本計畫如何對齊，而非違反）

| 不變量 | Gate-2 如何守 |
| --- | --- |
| #1 兩段閘門 / D1 | Gate-2 才追 P&L；且真錢硬 gated 在 OOS+forward（G2-D5）。 |
| #4 **零 Sunday-specific evva code** | 「agent 專用」= Sunday 端 HTTP + skill（G2-D1）；L3 需 evva 能力 → 開 RP（G2-D8）。 |
| #3/#7 確定性風控在 Python/交易所層 | 回測與 live 共用同一份 `risk` core（G2-D7）；LLM 永不在快路徑。 |
| #2 Sunday 執行、swarm 監督 | 不變。agent 多了「研究」能力，但下單仍是 Sunday；agent 只拉 meta lever。 |
| #5 兩條 HTTP 邊界 | 不變。回測是 Sunday 內部能力，仍經 `/backtest` 暴露。 |
| #10 testnet-first | G2.1–G2.4 全程 testnet/回測；只有 G2.5 碰 mainnet，硬 gated。 |

---

## 9. 不在範圍（Gate-2 本期）

- **HFT / 秒級**：LLM 與本架構皆 swing/regime 節奏（上層 §11）。
- **為 Sunday 寫 evva 客製 Go tool**：永遠 out（不變量 #4）；L3 走 RP。
- **大規模真錢**：G2.5 只到「小額 canary」；擴大規模是 canary 持續為正後的另一個獨立決策。
- **多 swarm space 編排**：單 space `sunday` 即可。
- **保證獲利**：見 §4——本計畫保證的是「可搜尋、可安全部署」，不是 alpha 本身。

---

## 10. 下一步

1. **先 grill 本計畫 + [`feasibility-analysis.md`](feasibility-analysis.md)**（對齊你的 grilling 工作流），收斂決策 G2-D1..D8 與 sub-milestone 序列。
2. 收斂後，把 **G2.1 解耦** 拆成 ticket（一個 session 一個 T，對齊既有 milestone 慣例），開工。
3. G2.1 完成才動 G2.2（回測引擎是建在解耦地基上的）。

> 詳細的「能不能做、怎麼做、要多少工、風險在哪」——見 [`feasibility-analysis.md`](feasibility-analysis.md)。
