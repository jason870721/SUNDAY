"""Sunday proxy configuration (milestone-6).

Sunday is a stateless Binance USDⓈ-M proxy for agents. Two boundaries to configure:

  * the exchange — **market data from mainnet** (public, no key) + **trading on
    testnet** (keyed, fake money); and
  * the outbound webhook — Sunday → evva swarm (RP-9), for position-PnL / price alerts.

Everything else is small operational knobs (sqlite path, monitor cadence, cache TTLs).
No Postgres/Redis: the only durable state is the alerts table in a single sqlite file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- exchange ---------------------------------------------------------
    # Market data reads from MAINNET (no key needed). Trading uses the TESTNET
    # account (keys below). Agents never see these keys — that is the whole point
    # of the proxy: Sunday holds the keys, agents hold only HTTP.
    binance_testnet_key: str = ""
    binance_testnet_secret: str = ""

    # --- outbound webhook (Sunday -> evva swarm, RP-9) --------------------
    # POST {title, body, data, to}; deliberately token-free on the swarm side.
    evva_webhook_url: str = "http://127.0.0.1:8888/api/swarm/sunday/event"

    # --- Telegram notifications (milestone-8, User-facing) ----------------
    # A SECOND outbound channel (the evva webhook above is agent-facing): reports / price
    # alerts / position PnL push to the User's phone. Both blank → disabled, Sunday behaves
    # exactly as before. Keys stay engine-side — never exposed to agents (invariant 2).
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # --- http server ------------------------------------------------------
    sunday_host: str = "127.0.0.1"
    sunday_port: int = 7777

    # --- local state ------------------------------------------------------
    # Alerts (req 6) persist here; monitor baselines stay in-memory (rebuilt on boot).
    sqlite_path: str = "sunday.db"

    # --- position monitor (req 5) ----------------------------------------
    # Webhook the swarm every `monitor_step_pct` move in an open position's ROI%.
    monitor_enabled: bool = True
    monitor_step_pct: float = 5.0
    monitor_poll_sec: int = 15        # position-book refresh / REST fallback cadence

    # --- realtime price hub (req 5/6) ------------------------------------
    ws_enabled: bool = True            # set false to run monitor/alerts on REST polling only

    # --- external-indices cache TTLs (seconds, req 4) --------------------
    indices_ttl_fast: int = 300        # crypto dominance / total market cap (CoinGecko)
    indices_ttl_macro: int = 600       # equities/macro (Stooq)
    indices_ttl_feargreed: int = 3600  # crypto Fear & Greed (alternative.me)


settings = Settings()
