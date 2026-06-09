# Sunday — Agent Manual (`GET /manual`)

Sunday 是一個**為 agent 設計的 Binance USDⓈ-M 永續交易所代理**。你（agent）用通用 HTTP 工具
（`http_request` 或 `curl`）操作它，就像人類用幣安一樣：查市場、看 K 線/指標/資金費、下永續單
（槓桿 / 逐倉全倉 / 止盈止損）、查倉位損益與訂單、看外部總經指數、設定價格與倉位提醒。

- **行情資料 = 主網（mainnet，真實價格，免金鑰）；下單交易 = 測試網（testnet，假錢，安全）。**
- **所有 API 免 token。** Sunday 自己持有幣安金鑰，你只需要 HTTP。
- base = `http://127.0.0.1:7777`。回傳大量資料的 list 端點一律**分頁**。

## 分頁慣例（所有 list）

`?page=1&page_size=50` → `{ items, page, page_size, total, has_more }`。歷史類（orders/trades/funding）
另接受 `?start=<ms>&limit=`。

## 0 · 可下單市場 `/api/markets`

```bash
# 分頁 + 篩選 + 排序（sort=volume|change|symbol|last, order=desc|asc）
curl -s "http://127.0.0.1:7777/api/markets?sort=volume&order=desc&page=1&page_size=20"
curl -s "http://127.0.0.1:7777/api/markets?symbol=BTC"          # 子字串篩選
curl -s "http://127.0.0.1:7777/api/markets/BTCUSDT"             # 單一市場：ticker + 精度/限額/最大槓桿
```

## 2 · K 線 + 技術指標 + 資金費

```bash
# OHLCV，interval 切換時間框（1m 3m 5m 15m 30m 1h 2h 4h 6h 8h 12h 1d 3d 1w 1M）
curl -s "http://127.0.0.1:7777/api/klines?symbol=BTCUSDT&interval=1h&limit=200"
# 技術指標（set=rsi,ema,sma,macd,bollinger,adx,atr）
curl -s "http://127.0.0.1:7777/api/klines/indicators?symbol=BTCUSDT&interval=1h&set=rsi,macd,adx"
# 資金費（現值 + mark/index + 下次結算）/ 歷史（分頁）
curl -s "http://127.0.0.1:7777/api/funding?symbol=BTCUSDT"
curl -s "http://127.0.0.1:7777/api/funding/history?symbol=BTCUSDT&page=1"
```

## 1 · 永續下單 `/api/perp`（測試網）

```bash
# 市價買進 / 開多，用 USD 名目金額、5× 槓桿、逐倉，附止盈止損（reduce-only trigger legs）
# memo = 你下這一單的理由（≤300 字），會記入帳本並在 /api/account/positions 回顯給 User。
curl -sX POST http://127.0.0.1:7777/api/perp/order -H 'Content-Type: application/json' -d '{
  "symbol":"BTCUSDT","side":"buy","type":"market","notional_usd":200,
  "leverage":5,"margin_mode":"isolated","take_profit":75000,"stop_loss":60000,
  "memo":"4h 突破壓力 + 資金費轉負，順勢做多" }'

# 限價單（用 qty 指定張數）：
#   {"symbol":"ETHUSDT","side":"sell","type":"limit","qty":0.1,"price":4200}
curl -sX POST http://127.0.0.1:7777/api/perp/leverage     -d '{"symbol":"BTCUSDT","leverage":10}'
curl -sX POST http://127.0.0.1:7777/api/perp/margin-mode  -d '{"symbol":"BTCUSDT","mode":"cross"}'
curl -sX POST http://127.0.0.1:7777/api/perp/close         -d '{"symbol":"BTCUSDT"}'   # reduce-only 平倉
curl -sX DELETE "http://127.0.0.1:7777/api/perp/order/<id>?symbol=BTCUSDT"
curl -sX DELETE "http://127.0.0.1:7777/api/perp/orders?symbol=BTCUSDT"                  # 撤該標所有掛單
```

下單參數：`side` buy|sell · `type` market|limit · 大小用 `qty`（張數）或 `notional_usd`（USD，自動換算）·
`leverage` / `margin_mode`(isolated 逐倉 | cross 全倉) 在進場前套用 · `take_profit`/`stop_loss` 為觸發價 ·
`memo`（≤300 字）= 下單理由，記入帳本、在倉位查詢的 `memo` / `order` 欄回顯給 User。

## 3 · 帳戶：倉位 / 損益 / 訂單 `/api/account`（測試網）

```bash
curl -s http://127.0.0.1:7777/api/account/positions        # 開倉 + 每倉 ROI%
curl -s http://127.0.0.1:7777/api/account/balance          # equity / free / used
curl -s http://127.0.0.1:7777/api/account/pnl              # equity + 總未實現 + 每倉拆解
curl -s "http://127.0.0.1:7777/api/account/orders/open?page=1"          # 掛單（可加 &symbol=）
curl -s "http://127.0.0.1:7777/api/account/orders?symbol=BTCUSDT"       # 歷史訂單（需 symbol，分頁）
curl -s "http://127.0.0.1:7777/api/account/trades?symbol=BTCUSDT"       # 成交（含 realized PnL，分頁）
```

## 4 · 外部指數 `/api/indices`

```bash
curl -s http://127.0.0.1:7777/api/indices                  # 全部快照
curl -s http://127.0.0.1:7777/api/indices/fear-greed       # 加密恐懼貪婪
# 其他 key：btc-dominance | vix | dxy | spx | ndx | us10y | gold
```

加密情緒（Fear&Greed、BTC 主導率）+ 總經（VIX 波動率、DXY 美元、標普 / 那斯達克、美十年期殖利率、黃金）。
皆有 TTL 快取，feed 失效時回傳最後值（`stale: true`）而非報錯。

## 6 · 價格提醒 `/api/alerts`

```bash
# kind: price_above / price_below（threshold=價格）；pct_move（threshold=百分比，建立時鎖定參考價）
curl -sX POST http://127.0.0.1:7777/api/alerts -d '{"symbol":"BTCUSDT","kind":"price_above","threshold":75000,"note":"突破"}'
curl -s  "http://127.0.0.1:7777/api/alerts?status=active&page=1"
curl -sX DELETE http://127.0.0.1:7777/api/alerts/<id>
```

提醒**觸發一次**即送 webhook 給 evva swarm，並標記 `triggered`。

## 5 · 倉位監控 `/api/monitor`

```bash
curl -s http://127.0.0.1:7777/api/monitor                  # 目前監控中的倉位 + ROI% + step + 設定
curl -sX POST http://127.0.0.1:7777/api/monitor/config -d '{"step_pct":5,"enabled":true}'
```

Sunday 自動監控**每一個**開倉倉位（websocket 即時報價 + 輪詢備援），當某倉位的 ROI%
每跨越一個 `step_pct`（預設 5%）就送一次 webhook 給 swarm。**無需手動訂閱。**

## 工作日誌 `/api/journal`（reviewer 寫日報 → User 在 UI 看）

```bash
# 寫一篇日誌（body 為 markdown；date 省略則預設今天 UTC；author 預設 reviewer）
curl -sX POST http://127.0.0.1:7777/api/journal -H 'Content-Type: application/json' -d '{
  "author":"reviewer","date":"2026-06-09","title":"2026-06-09 當日復盤",
  "body":"## 當日操作\n- ...\n\n## 盈虧歸因\n- ...\n\n## 改進建議\n- ..." }'
curl -s  "http://127.0.0.1:7777/api/journal?page=1"        # 列出（新到舊，分頁；可加 &author=reviewer）
curl -s  "http://127.0.0.1:7777/api/journal/12"            # 單篇全文
```

reviewer 每日把復盤 POST 到這裡存進 DB，User 在 dashboard 的 **Journal** 分頁讀；`body` 用 markdown。

## Webhook（Sunday → evva swarm）

`position_pnl`（倉位每 5% ROI）與 `price_alert`（提醒觸發）兩種事件，POST 到 `EVVA_WEBHOOK_URL`
（預設 `…/api/swarm/sunday/event`），payload = `{title, body, data, to}`，`data` 內含結構化欄位
＋ `suggested_action`，woken 的 agent 第一回合即可行動。

## Dashboard（人類在瀏覽器看）

`http://127.0.0.1:7777/dashboard` —— TS + Vue 3 量化終端：Markets / Chart / Trade / Account /
Indices / Alerts / Journal / Manual。人能做的，agent 用上面同一組端點也能做。
