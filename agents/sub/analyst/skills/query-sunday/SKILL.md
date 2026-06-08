# query-sunday 唯讀查詢 Sunday：決策面板、行情、倉位、損益（諮詢角色用）

Sunday 在 `http://127.0.0.1:7777`，用 `bash`+`curl` **唯讀**查詢（不需審批）。你**不拉任何 lever**。

## 決策面板（你最該用的）

```bash
# 每個候選策略此刻的投票 + 指標 + regime 讀數——直接讀，別自己算 EMA/RSI
curl -s 'http://127.0.0.1:7777/signals?symbol=BTCUSDT' | jq '{regime, votes}'
```

回傳裡：`regime.label`（trending/ranging/volatile）、每個策略的 `vote`（long/short/neutral）、
`confidence`、`indicators`、`rationale`。**這就是你要的全部判斷材料。**

## 其他唯讀端點

```bash
curl -s http://127.0.0.1:7777/status     | jq '{strategy, strategy_rationale, position, equity}'
curl -s 'http://127.0.0.1:7777/market?symbol=BTCUSDT&tf=1h&limit=100' | jq '.ohlcv[-5:]'
curl -s http://127.0.0.1:7777/positions  | jq
curl -s 'http://127.0.0.1:7777/pnl?since=2026-06-01' | jq '{unrealized, equity}'
```

## 回報 friday 的格式

查完 `send_message` 給 leader（friday），固定三段：

> **方向**：偏多 / 偏空 / 中性
> **建議策略**：momentum / mean_reversion / flat
> **理由**：依據哪些指標與 regime（例：「ADX 28 趨勢盤、momentum 投 long、spread +0.9% → 建議 momentum」）

只給建議，**不要嘗試自己下令**。細節：`curl -s http://127.0.0.1:7777/manual`。
