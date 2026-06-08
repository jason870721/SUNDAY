-- Sunday engine — milestone-4 T6: ablation shadow baselines.
-- Periodic shadow equity for the no-trade reference strategies (buy_hold,
-- funding_carry), computed over the same tape — the always-on comparison for
-- "did the desk add value?" (M4-D5). No orders placed; pure bookkeeping.

CREATE TABLE IF NOT EXISTS shadow_equity (
    id       BIGSERIAL   PRIMARY KEY,
    ts       TIMESTAMPTZ NOT NULL DEFAULT now(),
    baseline TEXT        NOT NULL,           -- buy_hold | funding_carry
    equity   NUMERIC     NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_shadow_baseline_ts ON shadow_equity (baseline, ts);
