# research-flow 技術面 + 永續微結構 + 世界指數 → 給 friday 方向 + 關鍵價位

Sunday 在 `http://127.0.0.1:7777`，用 **`http_request`** 唯讀查（GET）。**你只讀、不下單。**

## 世界指數（例行先掃）

```jsonc
{ "method":"GET", "url":"http://127.0.0.1:7777/api/indices" }                 // 全部：F&G / 主導率 / VIX / DXY / SPX / NDX / US10Y / Gold
{ "method":"GET", "url":"http://127.0.0.1:7777/api/indices/fear-greed" }
```

- risk-on / risk-off 轉變？VIX 飆、DXY 強、美股弱 → 加密通常承壓；F&G 極端貪婪 → 過熱、極端恐懼 → 可能超賣。

## 標的技術面（friday 指定）

```jsonc
{ "method":"GET", "url":"http://127.0.0.1:7777/api/klines", "query":{ "symbol":"BTCUSDT", "interval":"1h", "limit":"200" } }
{ "method":"GET", "url":"http://127.0.0.1:7777/api/klines/indicators", "query":{ "symbol":"BTCUSDT", "interval":"4h", "set":"rsi,ema,macd,bollinger,adx,atr" } }
{ "method":"GET", "url":"http://127.0.0.1:7777/api/funding", "query":{ "symbol":"BTCUSDT" } }
{ "method":"GET", "url":"http://127.0.0.1:7777/api/markets/BTCUSDT" }
```

## 判讀框架

- **趨勢 / 動能**：EMA 排列、MACD、ADX（>25 才算有趨勢）；多時間框對照（1h vs 4h）。
- **超買超賣 + 波動**：RSI、Bollinger；**ATR 決定停損該放多寬**（給 friday 的停損區要參考 ATR）。
- **資金費**：年化 |值| 高 → 該邊付高成本、擁擠；極端常隨清算反轉。問：擁擠在哪一邊？
- **量能 / 漲跌**：`/api/markets` 的 quoteVolume、percentage。

## 回報 friday（send_message）

**方向（偏多 / 偏空 / 觀望）+ 訊號強度 + 關鍵價位（支撐 / 壓力 / 建議停損）+ 失效條件 + 一句理由 + 數據出處。** 給得出「在哪進、在哪停」最有用。細節 `GET /manual`。
