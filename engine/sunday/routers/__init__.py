"""HTTP routers, one module per API group (req 10 — prefixes by module function).

  markets  /api/markets    req 0   tradeable-market discovery
  klines   /api/klines     req 2   OHLCV + technical indicators
  funding  /api/funding    req 2   funding rate (current + history)
  perp     /api/perp       req 1   perpetual order flow (testnet)
  account  /api/account    req 3   positions / PnL / orders / trades (testnet)
  indices  /api/indices    req 4   external macro/crypto indices
  alerts   /api/alerts     req 6   price alerts
  monitor  /api/monitor    req 5   open-position PnL monitoring
"""
