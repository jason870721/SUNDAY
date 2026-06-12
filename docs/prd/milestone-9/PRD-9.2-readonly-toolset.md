# PRD-9.2 — Phase 2：唯讀工具全集 + 回應整形

> 目標：行情與帳戶的決策資料全部有 typed 工具可拿，且每個工具的輸出在最壞輸入下也穩穩落在
> 60k chars 預算內（S3）。Phase 2 結束時 swarm 的**讀路徑**可以完全不碰 http_request。

## 1. 範圍

- 在 Phase 1 的 `markets_list` / `positions` 之上補滿 **13 個唯讀工具**（含改造）。
- MCP resource：`sunday://manual` → `GET /manual` 全文（evva 內建 `read_mcp_resource` 可讀）。
- `errors.py` 完整版（已知錯誤碼提示行）。
- 輸出預算測試（最壞輸入壓力案例）。
- **非範圍**：任何寫入工具（Phase 3）；prompt/settings 改動（Phase 4）。

## 2. 工具規格（13 個）

> 通則：所有 `page_size` 上限由工具 schema 鎖死（非引擎上限）——這是 S3 預算的第一道閘。
> 所有輸出尾行帶 `page X · total Y · has_more: true/false`（有分頁者）。
> 引擎回的 `stale: true` 一律透傳並在輸出首行標 `⚠ stale (age Xs)`。

### 行情組（upstream = mainnet，全部免金鑰）

| 工具 | 輸入 | upstream | 輸出（整形後） |
| --- | --- | --- | --- |
| `markets_list` | （Phase 1 規格不變） | `GET /api/markets` | 表格行 + 尾行 |
| `market_get` | `symbol: str` | `GET /api/markets/{symbol}` | ticker 一行 + 限額區塊：價格/數量精度、min/max qty、min notional、max leverage |
| `klines` | `symbol` · `interval: enum[1m,3m,5m,15m,30m,1h,2h,4h,6h,8h,12h,1d,3d,1w,1M]` · `limit?: int 1..500=100` · `start?: int(ms)` · `end?: int(ms)` | `GET /api/klines` | 首行 `symbol interval count`；資料行 `ts,o,h,l,c,v`（CSV，引擎本就回 columns+rows，直接透傳列） |
| `indicators` | `symbol` · `interval: 同上` · `set?: csv⊆{rsi,ema,sma,macd,bollinger,adx,atr}=全` · `limit?: int 50..400=200` | `GET /api/klines/indicators` | 每指標最後值 + 前值（判趨勢轉折用），完整序列**不**輸出；`as_of` + stale 標記 |
| `funding` | `symbol` · `history?: bool=false` · `page?: int=1` | `GET /api/funding`（history → `/history`） | 現值：rate/mark/index/下次結算一行；history：每期一行，page_size 鎖 30 |
| `indices` | `key?: enum[fear-greed,btc-dominance,vix,dxy,spx,ndx,us10y,gold]` | `GET /api/indices[/key]` | 全部：每指數一行（值 + 變動 + stale 標記）；單一：值 + 取得時間 |

### 帳戶組（upstream = testnet）

| 工具 | 輸入 | upstream | 輸出（整形後） |
| --- | --- | --- | --- |
| `positions` | （Phase 1 規格不變） | `GET /api/account/positions` | 每倉一行 |
| `balance` | `{}` | `GET /api/account/balance` | `equity / wallet / free / used / unrealized_pnl` 一行 |
| `pnl_drawdown` | `{}` | `GET /api/account/pnl` + `GET /api/account/drawdown`（sidecar 內兩呼叫合併） | 聚合區：equity、unrealized、total_notional、exposure_pct；回撤區：high_water、drawdown_pct、samples（samples 小 → 標「參考性低」）；每倉一行精簡版（symbol/side/notional/unrealized/roi%）——欄位**不**與 `positions` 重複到 protection/memo 層級 |
| `open_orders` | `symbol?: str` · `page?: int=1` | `GET /api/account/orders/open`（page_size 鎖 30） | 每單一行：`id symbol side type price/trigger qty algo? reduce_only? agent` |
| `trades` | `symbol: str` · `page?: int=1` · `agent?: str` | `GET /api/account/trades`（page_size 鎖 50） | 每筆一行：`ts side qty @price realized_pnl agent`；尾行加 `Σ realized（本頁）` |
| `order_history` | `symbol: str` · `page?: int=1` · `agent?: str` | `GET /api/account/orders`（page_size 鎖 30） | 每單一行（含條件單歷史，`algo` 標記） |
| `protection_status` | `symbol: str` | `GET /api/perp/protection` | position 摘要 + TP 腿/SL 腿（id、trigger、status）+ `tp_legs/sl_legs/sl_qty_covers`；**position null 但有腿 → 首行大寫警告 `ORPHAN LEGS`** |

### Resource

| URI | 內容 | 理由 |
| --- | --- | --- |
| `sunday://manual` | `GET /manual` 原文（markdown） | 長尾端點仍走 http_request（混合制），agent 不離開 MCP 也能查到完整合約；單一事實源不複寫 |

## 3. 整形與預算（S3 的實作規格）

1. **預算驗證是單元測試**：對每個工具構造**最壞合法輸入**（如 `klines limit=500`、
   `trades page_size=50` 且每欄位最長），斷言渲染輸出 `len() < 60_000`。新工具沒有預算測試
   = review 不過。
2. **序列類不回全序列**：`indicators` 只回最後值+前值（要全序列的場景——reviewer 畫權益曲線
   ——本來就走 repl + http_request，不是這條通道的客戶）。
3. **數字渲染共用一組純函式**（`shaping.fmt_price/fmt_pct/fmt_usd`）：價格透傳引擎精度、
   百分比 2 位、USD `k/M` 後綴；全部 stdlib（S7）。
4. **錯誤提示行**（`errors.py` 完整版）——upstream 4xx/5xx 原文透傳之外，已知碼補一行行動提示
   （與 manual / operate-desk skill 的錯誤手冊同語料，單一來源寫死在表裡）：

   | 匹配 | 提示行 |
   | --- | --- |
   | `-4016` | `→ price too far from mark; re-quote near current price or use market` |
   | `-1021` | `→ clock skew; engine self-heals — if repeated, POST /api/reports kind=system` |
   | `-2011` | `→ order id not found on either book; refresh open_orders first` |
   | 400 + `trigger` 字樣 | `→ trigger price on the wrong side; engine blocked an instant-fill leg` |
   | 503 / unreachable | `→ engine down? check /health; fall back to http_request per RUNBOOK` |

## 4. 測試

- `tests/test_mcp_shaping.py` 擴充：13 工具 ×（正常 / 空資料 / stale 透傳）+ 預算壓力案例。
- `tests/test_mcp_errors.py`：錯誤碼 → 提示行映射表全覆蓋 + 未知錯誤原文透傳。
- `scripts/smoke-mcp.sh` 擴充：`tools/list` 斷言 13+1（ping）、`resources/list` 斷言 manual、
  逐工具煙測（live engine，testnet 無倉位時帳戶組驗「空資料」路徑即可）。

## 5. 驗收清單

- [ ] 13 工具 + 1 resource 上線；`run-tests.sh` 全綠（無 SDK 環境照跑，S7）。
- [ ] 每個工具都有預算壓力測試且 < 60k chars（S3）。
- [ ] `klines limit=500 × indicators set=全` 等最壞組合在 live engine 實打一輪無截斷。
- [ ] evva 成員以 `read_mcp_resource` 讀回 manual 全文。
- [ ] 引擎目錄零 diff（S2）。

## 6. 風險

| 風險 | 對策 |
| --- | --- |
| 整形欄位選錯，agent 反而要回頭打 http_request 補欄位 | Phase 2 驗收後請 friday 在 dev 環境跑一次「晨間對帳」腳本化清單，缺欄位當 bug 修，不擴 scope |
| `pnl_drawdown` 兩個 upstream 呼叫其一失敗 | 部分成功照出（成功半邊 + 失敗半邊的錯誤行），不整體報錯 |

— operator + Claude，2026-06-12
