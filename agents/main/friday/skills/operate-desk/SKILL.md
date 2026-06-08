# operate-desk 經營事件驅動永續台：看 /desk、派研究、下 thesis、切策略、叫停（desk lead 專用）

Sunday 是執行/風險/資訊基板，在 `http://127.0.0.1:7777`。用 **`http_request`** 工具操作：傳 `{method, url, query?, body?}`，拿回 `status + 解析後的 body`。
**GET 自動放行（唯讀）；lever POST 跳 permission 審批（僅你）。** 完整 API：`GET /manual`。
**你設方向/信念（thesis），Sunday 確定性地做大小/時機/止損。你不手動下單。**

## 一輪研究（research round）

1. **`GET /desk`** → 全籃子（BTC/ETH/SOL）此刻哪個最 notable。對它 **`GET /desk?symbol=`** 深掘。
2. `send_message` 指派 **analyst-flow**（資金費/持倉/基差）、**analyst-news**（新聞/事件）蒐證。
3. 綜合他們的 finding → 草擬 thesis（方向 + conviction + 失效條件 + 證據）。
4. `send_message` 給 **risk-monitor**「試圖證偽這個 thesis」。多數反對 → 降 conviction 或不發。
5. **`POST /thesis`** 拍板 → **回信** analyst 採納/不採納 + 一句理由。

## 看哪裡有事（GET，免審批）

```jsonc
{ "method": "GET", "url": "http://127.0.0.1:7777/desk" }                                  // 全籃子 notable 排序
{ "method": "GET", "url": "http://127.0.0.1:7777/desk", "query": { "symbol": "BTCUSDT" } } // 單標的：funding/OI/基差 + advisor regime/votes/funding
{ "method": "GET", "url": "http://127.0.0.1:7777/status" }                                // 當值策略 / 倉位 / mode
{ "method": "GET", "url": "http://127.0.0.1:7777/thesis", "query": { "symbol": "BTCUSDT" } } // 當前 active thesis
{ "method": "GET", "url": "http://127.0.0.1:7777/positions" }
{ "method": "GET", "url": "http://127.0.0.1:7777/risk" }                                   // 封套使用率 + 違規 + 風控事件
{ "method": "GET", "url": "http://127.0.0.1:7777/theses", "query": { "limit": "20" } }     // thesis 史 + 結果
```

## Lever：下 thesis（你的主要手段；`rationale` 必填，留存給 User）

```jsonc
{ "method": "POST", "url": "http://127.0.0.1:7777/thesis",
  "body": { "symbol": "BTCUSDT", "direction": "long", "conviction": 0.4,
            "rationale": "<為什麼：funding/事件/敘事依據>",
            "invalidation": "<什麼條件這個 thesis 就錯了>", "invalidation_price": 60000,
            "evidence": { "funding_annual_pct": -10.9, "catalyst": "<...>" } } }
```

- `direction`：`long` / `short` / `flat`。`conviction` 0..1 → Sunday 確定性決定倉位大小（封套內）；**低於 0.2 視為 flat**。
- `invalidation_price` → 當 stop；directed 模式自動依此 + thesis 失效退場。
- 下完看回應 `result`（posture）；**過激進會被確定性風控擋（409）**——那是最終防線，但別依賴它。

## Lever：切策略 / 叫停 / 心跳

```jsonc
{ "method": "POST", "url": "http://127.0.0.1:7777/strategy",
  "body": { "symbol": "BTCUSDT", "strategy": "directed", "reason": "<...>" } }  // directed/momentum/mean_reversion/flat
{ "method": "POST", "url": "http://127.0.0.1:7777/halt", "body": { "reason": "<...>", "mode": "flat" } }  // flat=全平籃子 / safe=凍新倉
{ "method": "POST", "url": "http://127.0.0.1:7777/heartbeat", "body": {} }      // dead-man ping（timer 每 30m）
```

## 紀律

1. 下 thesis/切策略**前** GET `/status`·`/desk`（payload 是「當時」，決策看「現在」）；**後**驗證回應 posture；服務重啟後先對帳。
2. **防守先行**：不確定就低 conviction 或 `flat`；不利事件前主動降風險。寧可錯過，不追敘事追到頂。
3. **回信 analyst 採納與否**（advice loop）——看不到輸入有沒有落地的隊友無法改進。
4. 你不下單；確定性封套 + drawdown 熔斷是最終防線（誰下令都擋）。細節 `GET /manual`。
