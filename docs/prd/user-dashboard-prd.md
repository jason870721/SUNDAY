# PRD — Sunday User Dashboard（Web UI）

> 狀態：**草案 / Draft（待開發 → 交付）** ｜ 日期：2026-06-08
> 上層權威：[`sunday-project-prd.md`](sunday-project-prd.md)（尤其 D14 / §7.4 API / §7.9 §7.11 legibility / §8 安全）
> 前置：[`milestone-2/milestone-2.0/T3-dashboard-ui.md`](milestone-2/milestone-2.0/T3-dashboard-ui.md)（既有單頁 dashboard，被本文擴充/取代）
>
> **一句話定位：** 一個由 **Sunday 自服**的專業量化交易終端風格 Web UI，把「**agent 能對 Sunday 做的每一件事**」等價地交到 **User** 手上——看得到引擎的全部狀態（面板）、能拉同一組策略/風險 lever（策略控制）、並讀得到 agent 寫給 User 的決策理由與市場脈絡（報告頁）。

---

## 0. 為什麼做這個（對齊權威 PRD）

| 來源 | 它說了什麼 | 本 UI 如何兌現 |
| --- | --- | --- |
| **D14** | Sunday = User-facing 系統 of record；**Gate-2 由 Sunday 自服一個 execution dashboard**（PnL / 倉位 / 30d PnL / 權益曲線 / per-strategy 歸因 + 理由疊圖 + commentary feed） | 本 UI 就是那個 dashboard 的完整化（從 milestone-2 的單頁擴成多頁終端） |
| **不變量 9** | 視覺化 dashboard 由 **Sunday serve（不塞進 evva）** | UI 全在 `engine/`，由 FastAPI 在 `GET /dashboard` serve；**evva 內零新增程式碼** |
| **§7.4** | Sunday 的 HTTP 契約（讀端點 + 三 lever + commentary/heartbeat） | UI = 這份契約的**人類前端**：每個端點都有對應面板/控制 |
| **§7.9 / §7.11** | 雙向 legibility：Sunday→agent 給理由；agent→User 給理由（`reason` + `commentary`） | 「報告頁」把 `strategy_state.reason`、`commentary`、`risk_events`、`webhook_log` co-locate 成一條給 User 看的決策時間軸 |
| **§8** | lever 走 permission 審批；硬限額在 Python/交易所層（誰下令都擋） | UI 的 lever 一律經 Sunday 同一組端點 → **同一層確定性風控仍是最終防線**；危險操作（halt）UI 端再加確認 |

**核心主張：User 與 agent 共用同一個 Sunday API；UI 不是另一套後端，是這組 API 的人類介面。** 這守住「單一真相源」——agent 用 `curl`、User 用瀏覽器，打的是同一批端點、看的是同一份資料。

---

## 1. 目標 / 非目標

### 目標
1. **等價於 agent 的能力**：UI 串接**目前所有** Sunday 端點——12 個讀端點全部可視化 + 5 個寫 lever（切策略 / 設風險封套 / halt / commentary / heartbeat）全部可操作。
2. **面板（at-a-glance 監控）**：權益曲線（切換理由疊圖）、30 日 PnL、倉位、per-strategy 歸因、即時 advisor 決策支援、風險封套使用率、swarm 雙向 dead-man 狀態。
3. **策略控制**：User 能像 leader 一樣拉 lever——切策略（reason 必填）、改風險封套、緊急 halt（flat/safe）、送 heartbeat；操作前後對齊 §7.10 紀律（先看現況、後驗證）。
4. **agent 對 User 的報告頁**：把 leader 的切策略理由、analyst 的市場 commentary、確定性風控事件、Sunday 對 swarm 發的喚醒事件，合成一條可篩選的決策/活動時間軸——這是 §7.11 的視覺化。
5. **專業量化終端的設計品質**：深色高密度、等寬數字、語意化漲跌色、克制的單一強調色、即時脈動指示、流暢微互動——不是通用後台模板。

### 非目標（本次不做）
- **改 evva**：UI 不碰 swarm runtime；不在 evva 內加任何 Sunday-specific code（不變量 4）。
- **新交易邏輯**：UI 只讀/呼叫既有引擎決策；不在前端算指標、不繞過確定性風控。
- **`POST /restart`**：agent 目前也沒有（app.py 未實作）；UI 維持「等價於 agent 真實擁有的能力」，故不做 restart。kill-switch = `POST /halt`。
- **真錢 / mainnet**、**多 space 編排**、**telegram / 外部訊號源**：屬更後段（沿用權威 PRD 的 sequencing）。
- **使用者帳號 / 多租戶 / 權限分級**：Gate-1 testnet、單機 loopback，UI 與 API 同源、無登入（與現況一致；token 硬化是 Gate-2，§8.8）。

---

## 2. API 盤點：UI 要串接的全部端點（= agent 能用的全部）

> 「目前所有的 sunday API」逐一對應到 UI 的去處。✅=既有、🆕=本次新增（純讀、SELECT 既有表，零新資料邏輯）。

### 讀（GET，auto-allow）

| 端點 | 回傳重點 | UI 去處 |
| --- | --- | --- |
| ✅ `/status` | mode / strategy / rationale / position / exposure / leverage / equity / swarm_heartbeat_ok | 頂部狀態列（全頁共用） |
| ✅ `/health` | `{db, redis}` | 狀態列健康點 |
| ✅ `/advisor?symbol=` | regime + 每策略 vote(indicators/confidence/rationale) + funding + recommendation | Strategy 決策支援面板 + Overview mini |
| ✅ `/positions` | side/qty/entry/mark/upnl/stop/strategy/entry_reason | Overview 倉位表 |
| ✅ `/pnl?since=` | realized/unrealized/equity/equity_curve/window_days | Overview 權益曲線 + KPI 卡 |
| ✅ `/performance?since=` | per-strategy realized/n_trades/win_rate/avg_pnl/open_qty | Overview 歸因表 |
| ✅ `/strategy_history?since=` | 切策略時間軸（reason/set_by） | 權益曲線疊圖標記 + Reports 時間軸 |
| ✅ `/market?symbol=&tf=&limit=` | OHLCV | Strategy 行情圖 |
| ✅ `/envelope` | 當前風險封套（active caps） | Risk 封套編輯器（現值） |
| ✅ `/commentary?since=&limit=` | analyst 市場貼文 | Reports commentary feed |
| ✅ `/manual` | 操作手冊 markdown | Manual 頁 |
| 🆕 `/risk` | envelope + current(exposure/lev/dd) + utilization + violations + recent `risk_events` | Risk 頁主面板 |
| 🆕 `/trades?since=&limit=` | `orders` 帳本（ts/side/type/qty/price/status/strategy/intent） | Reports/Overview 成交 blotter |
| 🆕 `/events?since=&limit=` | `webhook_log`（Sunday→swarm 的喚醒事件） | Reports「引擎喚醒 agent」時間軸 |

### 寫（POST，lever；UI 端再加確認 + reason 強制）

| 端點 | body | UI 控制 |
| --- | --- | --- |
| ✅ `/strategy` | `{symbol, strategy, reason, set_by?}` | Strategy 頁的切換 lever（segmented 選擇 + reason） |
| ✅ `/envelope` | `{max_position_usd, max_total_exposure_usd, max_leverage, max_drawdown_pct, stop_pct, reason, set_by?}` | Risk 頁的封套編輯器 |
| ✅ `/halt` | `{reason, mode: flat\|safe, set_by?}` | 全頁頂部 kill-switch（雙重確認） |
| ✅ `/heartbeat` | `{}` | Risk/Ops 區的「送 heartbeat」按鈕 |
| ✅ `/commentary` | `{author, title?, body}` | Reports 頁的 User/operator note 撰寫框 |

### 🆕 新增端點為何合理（不違反「只串目前的 API」精神）
- `/risk`、`/trades` 是 **§7.4 契約本來就列的端點**，只是尚未實作——補上它們是「把契約補齊」，不是發明新東西。
- 三個都是**純讀**：只 `SELECT` 既有表（`risk_events`/`orders`/`webhook_log`）+ 既有 exchange best-effort，**零新交易/資料邏輯**，亦同步寫進 `/manual` 給 agent 共用。
- 它們讓「風險面板」與「agent 報告頁」有真實資料可呈現，否則這兩塊會是空的——而它們正是 User 需求的核心。

### 🆕 actor 屬性（誠實稽核）
`POST /strategy|/envelope|/halt` 增加可選 `set_by`（預設 `leader`/`system`，**完全向後相容** agent 既有用法）；UI 一律帶 `set_by:"user"`，讓 `strategy_state`/`risk_envelope` 的稽核能區分「User 拉的」vs「leader 拉的」（對齊 §8.9「誰、何時、為何」）。

---

## 3. 資訊架構（5 個區段 = 一個量化終端）

```
┌─ StatusRibbon（sticky，全頁共用）─────────────────────────────────────────────┐
│ ☀ Sunday · testnet | mode:active | BTCUSDT · momentum | equity 10,240 | ● swarm ok | ⏻ KILL │
├──────────┬──────────────────────────────────────────────────────────────────┤
│ Sidebar  │  ▸ Overview  總覽    — 面板：KPI / 權益曲線(疊圖) / 倉位 / advisor mini │
│ (nav)    │  ▸ Strategy  策略    — 控制：advisor 全panel + 切策略 lever + 行情圖    │
│          │  ▸ Risk      風險    — 控制：封套編輯器 + 使用率 gauge + 風控事件        │
│          │  ▸ Reports   報告    — agent→User：commentary + 決策/事件時間軸 + 撰寫    │
│          │  ▸ Manual    手冊    — /manual 渲染 + 端點參考 + 唯讀 API console         │
└──────────┴──────────────────────────────────────────────────────────────────┘
```

- **路由**：hash 路由（`#/overview` …），SPA，無 build。
- **全頁輪詢**：共享 store 每 ~10s 輪詢 `/status`+`/health`（輕）；各頁進場時拉自己的重端點，並以較慢 cadence（20–30s）刷新。lever 操作後立即重抓相關端點（§7.10 後驗證）。

---

## 4. 設計語言（專業量化終端）

> 目標氛圍：Bloomberg / TradingView / 交易所永續面板。**深色、密集、數字至上、語意色、克制強調、即時感。**

- **色票（dark）**：底 `#0a0e15`、面板 `#10151f`、次面板 `#161c28`、髮絲線 `#1e2632`、主文 `#e6edf3`、次文 `#8b97a7`。
  - 語意：漲/正 `#2ebd85`（teal-green）、跌/負 `#f6465d`（red）、警示/active `#f0b90b`（amber，幣圈金）、強調/連結 `#5ccfe6`（cyan）。
- **字體**：UI 用系統 sans（含 PingFang/JhengHei 中文）；**所有數字用等寬**（`ui-monospace, "SF Mono", "JetBrains Mono", monospace`）+ `font-variant-numeric: tabular-nums`——對齊是專業感的根本。
- **版面**：左側 icon+label sidebar（可收合）；頂部 sticky 狀態 ribbon；主區 responsive panel grid。panel header = 小寫字距大寫、次文色。
- **資料密度**：13px 資料字、緊湊列高、髮絲分隔；表格右對齊數字、漲跌上色。
- **即時感**：heartbeat 綠點脈動動畫；數字更新時 200ms 高亮閃動；面板載入用 skeleton shimmer，不白屏。
- **微互動**：hover lift、focus ring（cyan）、lever 按鈕的 loading/disabled 態、操作結果用 toast（右下，成功 teal / 失敗 red）。
- **空狀態**：每個面板有體面的空狀態文案（「引擎跑一段後出現」），不顯示破圖。
- **離線退化**：圖表/exchange 端點失敗時，DB-backed 面板照常顯示（權益曲線、歸因、報告全來自 postgres）；錯誤收進 store 的 toast，不阻塞整頁。

---

## 5. 技術方案（嵌入式 Vue，零 build）

- **框架**：**Vue 3**，使用 **vendored global build**（`vue.global.prod.js`）——`window.Vue` 全域，元件用 plain object + template 字串；**無 SFC、無 node、無打包**。
- **圖表**：**TradingView `lightweight-charts`**（vendored, UMD）——權益曲線（line series + 切換 markers = D14 疊圖）與行情（candlestick series）皆用它，專業量化圖表標準。
- **vendoring**：`vue.global.prod.js` 與 `lightweight-charts.standalone.production.js` 下載進 `engine/sunday/web/vendor/`（離線可跑、版本鎖定、不依賴 CDN）。載入失敗時優雅退化（數字/表照常）。
- **模組化**：原生 ES modules（`<script type="module">`）切多檔（api/store/format/components/views）——可維護又零 build。
- **serve**：FastAPI `StaticFiles` mount 在 `/ui`；`GET /dashboard` 與 `GET /` 回 `web/index.html`。前端對同源 `/status` 等端點 `fetch`。
- **不變量**：全部檔案在 `engine/sunday/web/`，由 Sunday serve；**evva 完全不動**（守 D12 / 不變量 9）。

### 檔案佈局
```
engine/sunday/web/
├── index.html                  # shell：vendor scripts + #app mount
├── styles.css                  # 設計系統（tokens + 元件樣式）
├── vendor/
│   ├── vue.global.prod.js
│   └── lightweight-charts.standalone.production.js
└── js/
    ├── api.js                  # 每個 Sunday 端點一個函式（含 set_by）
    ├── store.js                # reactive 全域狀態 + 輪詢 + toast/error
    ├── format.js               # 數字/時間/漲跌/百分比 格式化
    ├── charts.js               # lightweight-charts 工廠（equity / market）
    ├── router.js               # 極簡 hash 路由
    ├── components.js           # StatusRibbon/Sidebar/KpiCard/Gauge/VoteBar/ConfirmModal/Toast/Timeline…
    ├── app.js                  # root：layout + router + mount
    └── views/
        ├── overview.js · strategy.js · risk.js · reports.js · manual.js
```

---

## 6. 各頁規格

### 6.1 Overview（總覽 / 面板）
- **KPI 卡**：Equity、Realized（窗）、Unrealized、Drawdown%、Exposure/Leverage（資料：`/pnl`+`/status`+`/risk`）。
- **權益曲線**（主圖）：`/pnl.equity_curve` line + `/strategy_history` 切換點 markers（hover 顯示 strategy + reason）= **D14 疊圖**。
- **當前倉位表**：`/positions`（side/qty/entry/mark/upnl/strategy/entry_reason/stop），漲跌上色。
- **Advisor mini**：`/advisor` 的 regime + recommendation + funding 摘要（一眼看「引擎此刻怎麼想」）。
- **近期成交**：`/trades` 最近數筆 blotter。

### 6.2 Strategy（策略控制）
- **決策支援面板（完整 `/advisor`）**：regime 讀數（label/ADX/vol + rationale）；momentum & mean_reversion 各自 vote（方向 + confidence bar + indicators + rationale）；funding context；**recommendation**（含 funding_caveat 警示）。這就是 agent 切策略前看的同一份。
- **切策略 lever**：顯示當前 active（即時輪詢）；segmented 選 `momentum / mean_reversion / flat`；**reason 必填**；送出前再抓一次 `/status`（§7.10-1 先看現況），送出後輪詢確認 `strategy` 真的換了並 toast（§7.10-2 後驗證）；附「引擎建議」一鍵帶入 recommendation 當預設。
- **行情圖**：`/market` candlestick（symbol/tf 可切），給切換決策視覺脈絡。

### 6.3 Risk（風險控制）
- **封套使用率**：`/risk` 的 current vs caps，畫成 gauge/進度條（單筆/總曝險/槓桿/回撤），越界轉紅。
- **封套編輯器**：`/envelope` 現值預填；表單編輯五個 cap + **reason 必填**；送出 = `POST /envelope`（set_by:user）；確認後 toast + 重抓。
- **風控事件**：`/risk.recent_events`（`risk_events`：size_cap/exposure_cap/leverage_cap/drawdown + detail + action_taken）——V6 證據的可視化。
- **Ops 小工具**：送 `POST /heartbeat`（reset watchdog）按鈕 + 顯示 heartbeat age / safe-mode 狀態。

### 6.4 Reports（agent 對 User 的報告頁）
- **決策/活動時間軸**（合一、可篩選）：
  - leader 切策略（`/strategy_history`：strategy + reason + set_by）
  - analyst commentary（`/commentary`：title + body）
  - 確定性風控動作（`/risk.recent_events`）
  - Sunday→swarm 喚醒事件（`/events`：regime_shift / risk_breach / engine_degraded / safe_mode_entered）
  - 篩選 chips（全部 / 策略 / commentary / 風控 / 喚醒），時間倒序。
- **commentary feed**（主，卡片式）：analyst 市場脈絡，最顯眼。
- **撰寫框**：User 以 operator 身分 `POST /commentary`（author 預設 `operator`）留註記——讓 User 也能在同一條時間軸上記事。

### 6.5 Manual（手冊 / API）
- **渲染 `/manual`**（markdown → HTML），給 User 讀懂 agent 在做什麼。
- **端點參考**：把 §2 盤點表做成卡片（方法/路徑/用途/權限）。
- **唯讀 API console**：選任一 GET 端點 + 參數 → 打 → 顯示 JSON（讓「等價於 agent 能用的 API」字面成真，且方便除錯）；POST lever 不放進 console（一律走有確認的正式控制）。

---

## 7. Lever UX 與安全

1. **reason 一律強制**（前端擋空白 + 後端已擋）——留存給 User/稽核（§7.11）。
2. **危險操作確認**：`halt`（尤其 `flat` 全平）跳 ConfirmModal，要 User 再按一次；`envelope` 縮小封套也提示影響。
3. **§7.10 時差防呆內建**：切策略「前抓現況、後驗證」；服務若重啟，頁面重抓 `/status` 對帳（與既有紀律一致）。
4. **確定性風控不被繞過**：所有 lever 經 Sunday 同一組端點 → `risk.check_order`/`check_drawdown` 仍是最終防線（誰下令都擋，§7.3/§8.3）。UI 只是更友善的 caller。
5. **誠實屬性**：`set_by:"user"` 入庫，報告頁能標「User 切」vs「friday 切」。
6. **testnet / loopback**：與現況一致，無登入；token 硬化是 Gate-2（§8.8）。UI 不引入新攻擊面（同源、只呼叫本機 Sunday）。

---

## 8. 驗收準則

- [ ] 瀏覽器開 `http://127.0.0.1:7777/dashboard`，**零 build**（直接開頁即動），5 個區段可導覽。
- [ ] **每個既有端點都有對應呈現**（§2 盤點全綠）；新增 `/risk` `/trades` `/events` 回正確 JSON 且有測試。
- [ ] **權益曲線**畫得出 + 切換點 markers + hover 顯示 reason（D14）。
- [ ] **Strategy 頁**顯示完整 advisor，並能完成一次切策略 lever round-trip（reason 必填 → 送出 → 後驗證 → toast）。
- [ ] **Risk 頁**顯示封套使用率 + 能改封套 + 列出風控事件。
- [ ] **Reports 頁**合成決策/事件時間軸，commentary feed 顯示，且 User 能 `POST /commentary`。
- [ ] **離線退化**：殺 exchange/CDN 不白屏，DB 面板照常。
- [ ] **不變量**：全部新碼在 `engine/`，evva 零改動；全測試（含新測）綠燈。

---

## 9. 對既有資產的影響
- **取代** milestone-2 的單頁 `dashboard.html`（功能被多頁 UI 涵蓋）；`GET /dashboard` 改 serve 新 `web/index.html`。
- **manual.md** 增列 `/risk` `/trades` `/events`（agent 與 User 共讀同一份）。
- **app.py / store.py** 增 3 個讀端點 + store 查詢方法 + lever 的 `set_by` 透傳；引擎決策邏輯不動。
- **不影響** swarm 設定（`agents/`、`evva-swarm.yml`）與引擎核心（strategy/risk/regime/advisor/execution）。
