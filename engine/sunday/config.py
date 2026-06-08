from pydantic_settings import BaseSettings, SettingsConfigDict


def _split(csv: str) -> list[str]:
    return [s.strip().upper() for s in csv.split(",") if s.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://root:root@localhost:5432/sunday"
    redis_url: str = "redis://localhost:6379/0"
    evva_webhook_url: str = "http://127.0.0.1:8888/api/swarm/sunday/event"

    binance_testnet_key: str = ""
    binance_testnet_secret: str = ""

    sunday_host: str = "127.0.0.1"
    sunday_port: int = 7777

    # trading basket (milestone-4: multi-symbol). `symbol` stays the primary/default
    # for single-symbol endpoint params; `symbols` is the basket the watcher loops.
    symbol: str = "BTCUSDT"
    symbols: str = "BTCUSDT,ETHUSDT,SOLUSDT"
    timeframe: str = "1h"
    ema_fast: int = 20
    ema_slow: int = 50
    target_notional_usd: float = 500.0  # baseline (momentum/mean_reversion) entry size
    leverage: int = 3

    # deterministic risk envelope (hard caps; NOT the LLM's job) — milestone-4 test caps
    max_position_usd: float = 1500.0
    max_total_exposure_usd: float = 3000.0   # < 3×single → forces selectivity across the basket
    max_leverage: int = 3
    max_drawdown_pct: float = 5.0            # drawdown circuit breaker → flatten + lock
    stop_pct: float = 0.02

    # milestone-4 directed mode: conviction (0..1) → size. Below the floor = stay flat.
    conviction_floor: float = 0.2

    # ablation: symbols forced to info-OFF (the desk gets no feeds for them). Empty = all ON.
    info_off_symbols: str = ""

    # event watcher / dead-man
    tick_interval_sec: int = 60        # how often the watcher ingests feeds + checks regime/watchdog
    heartbeat_timeout_sec: int = 5400  # 90m without a swarm heartbeat -> safe-mode

    @property
    def symbol_list(self) -> list[str]:
        return _split(self.symbols) or [self.symbol]

    @property
    def info_off_list(self) -> list[str]:
        return _split(self.info_off_symbols)


settings = Settings()
