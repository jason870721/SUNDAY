-- Sunday engine — milestone 1.0 schema (modeling-grade from the start).
-- Money / quantities are NUMERIC (never float). Times are TIMESTAMPTZ.

CREATE TABLE IF NOT EXISTS ohlcv (
    symbol    TEXT        NOT NULL,
    tf        TEXT        NOT NULL,
    bar_time  TIMESTAMPTZ NOT NULL,
    open      NUMERIC     NOT NULL,
    high      NUMERIC     NOT NULL,
    low       NUMERIC     NOT NULL,
    close     NUMERIC     NOT NULL,
    volume    NUMERIC     NOT NULL,
    PRIMARY KEY (symbol, tf, bar_time)
);

CREATE TABLE IF NOT EXISTS orders (
    id                BIGSERIAL   PRIMARY KEY,
    ts                TIMESTAMPTZ NOT NULL DEFAULT now(),
    symbol            TEXT        NOT NULL,
    side              TEXT        NOT NULL,          -- buy | sell
    type              TEXT        NOT NULL,          -- market | limit | stop
    qty               NUMERIC     NOT NULL,
    price             NUMERIC,
    status            TEXT        NOT NULL,          -- new | filled | rejected | canceled
    exchange_order_id TEXT,
    strategy          TEXT        NOT NULL,          -- attribution: which strategy emitted this
    intent            TEXT,                          -- entry reason / why
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_orders_symbol_ts ON orders (symbol, ts);

CREATE TABLE IF NOT EXISTS fills (
    id         BIGSERIAL   PRIMARY KEY,
    order_id   BIGINT      REFERENCES orders (id),
    ts         TIMESTAMPTZ NOT NULL DEFAULT now(),
    symbol     TEXT        NOT NULL,
    qty        NUMERIC     NOT NULL,
    price      NUMERIC     NOT NULL,
    fee        NUMERIC     NOT NULL DEFAULT 0,
    strategy   TEXT        NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS positions (
    id           BIGSERIAL   PRIMARY KEY,
    symbol       TEXT        NOT NULL,
    side         TEXT        NOT NULL,               -- long | short
    qty          NUMERIC     NOT NULL,
    entry_price  NUMERIC     NOT NULL,
    stop_price   NUMERIC,
    strategy     TEXT        NOT NULL,
    entry_reason TEXT,
    realized_pnl NUMERIC,
    opened_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at    TIMESTAMPTZ                          -- NULL = open
);
CREATE INDEX IF NOT EXISTS idx_positions_open ON positions (symbol) WHERE closed_at IS NULL;

CREATE TABLE IF NOT EXISTS pnl_snapshots (
    id           BIGSERIAL   PRIMARY KEY,
    ts           TIMESTAMPTZ NOT NULL DEFAULT now(),
    equity       NUMERIC     NOT NULL,
    realized     NUMERIC     NOT NULL,
    unrealized   NUMERIC     NOT NULL,
    drawdown_pct NUMERIC
);
CREATE INDEX IF NOT EXISTS idx_pnl_ts ON pnl_snapshots (ts);

CREATE TABLE IF NOT EXISTS strategy_state (
    id       BIGSERIAL   PRIMARY KEY,
    symbol   TEXT        NOT NULL,
    strategy TEXT        NOT NULL,                    -- momentum | mean_reversion | flat
    reason   TEXT,                                    -- leader's rationale (User-visible)
    set_by   TEXT        NOT NULL,                    -- agent name | 'system'
    set_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_strategy_state_symbol ON strategy_state (symbol, set_at DESC);

CREATE TABLE IF NOT EXISTS signals (
    id              BIGSERIAL   PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL DEFAULT now(),
    symbol          TEXT        NOT NULL,
    strategy        TEXT        NOT NULL,
    indicators_json JSONB       NOT NULL,             -- features at decision time (modeling)
    action          TEXT        NOT NULL              -- open_long | open_short | close | hold
);
CREATE INDEX IF NOT EXISTS idx_signals_symbol_ts ON signals (symbol, ts);

CREATE TABLE IF NOT EXISTS risk_events (
    id           BIGSERIAL   PRIMARY KEY,
    ts           TIMESTAMPTZ NOT NULL DEFAULT now(),
    type         TEXT        NOT NULL,                -- size_cap | exposure_cap | leverage_cap | drawdown
    detail       JSONB,
    action_taken TEXT
);

CREATE TABLE IF NOT EXISTS webhook_log (
    id          BIGSERIAL   PRIMARY KEY,
    ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
    event_type  TEXT        NOT NULL,                 -- regime_shift | engine_degraded | ...
    to_member   TEXT        NOT NULL,                 -- default 'leader'
    title       TEXT,
    body        TEXT,
    http_status INT,
    message_id  TEXT
);
