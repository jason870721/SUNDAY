-- Sunday engine — milestone-4 T1: information layer (batch-1 perp microstructure).
-- Time-series of the quant-credible perp signals the research desk reads via /desk.
-- Liquidation / long-short columns are nullable (best-effort; testnet often omits).

CREATE TABLE IF NOT EXISTS perp_metrics (
    id                 BIGSERIAL   PRIMARY KEY,
    ts                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    symbol             TEXT        NOT NULL,
    funding_rate       NUMERIC,                 -- per-8h fraction (+ = longs pay shorts)
    funding_annual_pct NUMERIC,                 -- annualised %
    open_interest      NUMERIC,                 -- USD value (or contract amount)
    long_short_ratio   NUMERIC,
    basis_bps          NUMERIC,                 -- (mark - index) / index, in bps
    liq_long_usd       NUMERIC,
    liq_short_usd      NUMERIC
);
CREATE INDEX IF NOT EXISTS idx_perp_metrics_symbol_ts ON perp_metrics (symbol, ts DESC);
