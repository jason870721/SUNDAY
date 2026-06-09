# Milestone-8 — Resilience · Black-Gold UI · Telegram

> **方向（2026-06-10）**：在 milestone-6 的 agent-native Binance 代理之上，做三件「讓人用得順、
> 讓系統撐得住」的事。不改交易語義、不違反 milestone-6 的 8 條不變量（其中第 8 條由本里程碑
> **明確擴充**：多一條 User-facing 的 Telegram 通知通道，見下）。

本里程碑只有三個交付項，全部來自 User 的一句話需求：

1. **修掉啟動後狂噴的 `-1021` 時間戳錯誤**（`poll cycle: binance 400 … Timestamp … ahead of the server's time`）。
2. **前端 UI 重新設計**：黑金配色、美觀、**不能跑版**（responsive，窄螢幕也不爆版）。
3. **report 串接 Telegram 通知**：friday 發 report 時，順手推一則 Telegram 給 User。

---

## T1 — Binance `-1021` 時鐘偏移加固

### 現象
引擎啟動後，背景 poll loop 每 `MONITOR_POLL_SEC` 秒打一次 testnet 簽名請求
（`GET /fapi/v2/positionRisk`，走 `exchange._signed`）。本機時鐘比幣安伺服器**快**超過 1000ms 時，
幣安直接回 `-1021 Timestamp for this request was 1000ms ahead of the server's time.`，poll cycle 整輪失敗。

### 根因
幣安的時間戳規則是**不對稱**的：請求的 `timestamp` 只允許比伺服器時間**快 ≤ 1000ms**，但可以
**慢到 `recvWindow`**（預設 5000ms）。原本 `_server_ms()` 用 `offset = serverTime − localBefore`
估算偏移——這個估法把「到時間端點的單程網路延遲」整包算進 offset 變成**正向偏壓**。在受限地區
走 proxy 連幣安、單程延遲可達 1~3 秒時，算出來的 timestamp 會落在伺服器時間**前方 >1000ms**，
於是每一輪簽名請求都踩 `-1021`。ccxt 的 `trade_ex()`（下單路徑）自己用 `milliseconds()` 當 nonce、
**完全沒有**偏移校正，本機時鐘一快，下單也會同樣 `-1021`。

### 修法（`exchange.py`）
把「估 offset」與「組 timestamp」都改成**對稱規則下的安全側**：

1. **round-trip 中點估 offset**：量測 `before`/`after`，用 `(before+after)/2` 當本地對應時刻，
   消掉大半單程延遲偏壓。
2. **timestamp 故意偏向「落後」伺服器**：回傳值再減一個 `_TS_SAFETY_MS`（1000ms）。落後是安全的
   （到 `recvWindow` 都合法），超前才危險（>1000ms 即死）。
3. **`recvWindow` 加大到 10000ms**：給落後側更多餘裕。
4. **`-1021` 自癒**：簽名請求若回 `-1021`，強制重新同步時鐘並**重試一次**，避免長時間漂移後卡死。
5. **ccxt `trade_ex()` 開 `adjustForTimeDifference: true` + `recvWindow: 10000`**：讓下單/槓桿/改保證金
   等 ccxt 簽名路徑也自動校正，與 `_signed` 一致。

時鐘同步失敗（proxy 掛了）時 **graceful degrade**：沿用上次 offset、不讓 poll loop 崩潰。

### 驗收
- 本機時鐘比伺服器快 ~2s 時，poll cycle 不再噴 `-1021`。
- 下單（`POST /api/perp/order`）在同樣偏移下成功。
- 既有 71 個單元測試維持綠（本項為 I/O 邊界，純邏輯不受影響）。

---

## T2 — 黑金（Black-Gold）UI 重設計，且不跑版

### 目標
把既有「給 agent 看的 quant 終端機」深色主題，升級成一套**精緻的黑金視覺系統**：純粹的深黑底、
雙調金（亮金高光 + 深琥珀），細緻的描邊／微光／漸層，沉穩不喧嘩；同時把**所有版面改成 responsive**，
窄螢幕（平板／手機）也**絕不跑版**。

### 設計原則
- **Token 驅動、集中改造**：所有 view 都共用 `style.css` 的 class（`.panel`/`.tbl`/`.btn`/`.stat`/
  `.seg`/`.tag`/`.pill`/`.grid`…），沒有任何 view 帶 scoped style。因此**主視覺一律改 `style.css`**，
  view 只動「版面結構（responsive）」必要處，把硬寫死的雙欄寬度換成 responsive class。
- **黑金 palette**：
  - 底色更深更純（`--bg:#070708`），面板用近黑加極淡暖調漸層。
  - 金色雙調：`--gold:#e8c069`（主）、`--gold-bright:#f7d98a`（高光）、`--gold-deep:#b8893a`（深）。
    主強調 `--accent` = 金；hover/active/focus 都走金。
  - 漲跌維持綠紅（交易語義不可改），但調成與黑金協調的色階。
  - 金色僅用於「強調」（品牌、active、主按鈕、focus、關鍵數字 highlight），**不**整片塗金，維持高級感。
- **不跑版（responsive）**：
  - App shell 側欄在 ≤900px **收成滑出式抽屜**（漢堡鈕在 topbar；點連結／點遮罩即關），
    桌機維持固定側欄。
  - 6 個硬寫死雙欄版面（Trade/Reports/Journal/Memory = 左固定欄；Alerts/Chart = 右固定欄）改用
    `.split` / `.split-r` class，欄寬用 `--aside` 變數帶入；≤900px 自動**堆疊成單欄**。
  - CSS grid 子項補 `min-width:0`（grid 子項預設 `min-width:auto`，是寬表格把整頁撐爆的元兇）；
    寬表格一律落在可水平捲動的容器內。
  - `.grid.cols-2/3/4` 補滿中小斷點，避免卡片擠成一團。

### 不變動
- 所有資料流、API client、view 的邏輯與互動行為不變；只動視覺與 responsive 結構。
- `lightweight-charts` 主題色同步調成黑金（grid/border/text）。

### 驗收
- `vue-tsc --noEmit` 綠、`vite build` 綠、`dist/` 重新產出並 commit。
- 桌機與 ~375px 窄寬下逐頁檢視：side-by-side 版面正確堆疊、無水平爆版、表格在容器內捲動。

---

## T3 — Telegram 通知（report 為主）

### 範圍
新增一條 **User-facing** 的 Telegram 推播通道。三個觸發點：
- **report（主需求）**：`POST /api/reports` 建立通報後，推一則 Telegram（標題＋kind＋內文摘要）。
- **price_alert**：價格提醒觸發時，除了既有 evva webhook，另推 Telegram。
- **position_pnl**：持倉 ROI 跨步通報時，另推 Telegram。

### 設計（`telegram.py`，新檔）
- **stdlib only（urllib）、永不 raise**：照 `events.py` 同款 fire-and-forget；未設定 token/chat 時
  整個模組是 no-op（`enabled()` 為 False 直接跳過），對既有行為零影響。
- 純函式 formatter（`report_text` / `alert_text` / `position_text`）可離線單元測試（無網路）。
- HTTP 送出走 `https://api.telegram.org/bot<token>/sendMessage`，`parse_mode=HTML`，短 timeout。
- report 在 FastAPI `BackgroundTasks` 內推送，不阻塞 HTTP 回應；alert/pnl 本就在背景執行緒，直接同步推。

### 設定（`config.py` / `.env.example`）
- `TELEGRAM_BOT_TOKEN`（空＝關閉）、`TELEGRAM_CHAT_ID`。金鑰只在引擎側，**不**經 port 外洩給 agent
  （延續不變量 2）。

### 對不變量 8 的擴充
milestone-6 不變量 8 寫「只有一條對外 webhook（Sunday → evva swarm）」。本里程碑**明確擴充**為：
Sunday 有**兩條對外通道**——(a) **evva swarm webhook**（agent-facing，沿用不變）；(b) **Telegram**
（User-facing 通知，可選、未設定即關閉）。兩者互不影響，evva 流程完全不動。

### 驗收
- 設好 `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` 後，建立一則 report 會在 Telegram 收到推播。
- 未設定時，所有路徑行為與現在完全一致（no-op），測試全綠。
- 新增 formatter 單元測試（純文字、無網路）。

---

## 交付清單
- `exchange.py`：時鐘加固（T1）。
- `telegram.py`（新）、`config.py`、`.env.example`、`routers/reports.py`、`alerts.py`、`monitor.py`：Telegram（T3）。
- `web/src/style.css`、`web/src/App.vue`、6 個 view 的版面 class、`ChartView` 圖表主題、重建 `web/dist/`：UI（T2）。
- `tests/test_telegram.py`（新）。
- `CLAUDE.md`：更新不變量 8 註記與現況。
