-- Sunday engine — milestone-4 T3: thesis / outcome ledger.
-- A thesis is the swarm's structured view (direction + conviction + invalidation +
-- evidence) that the `directed` execution mode consumes. Append-only: a new thesis
-- for a symbol supersedes the prior active one (audit trail preserved). Positions
-- opened under `directed` tag thesis_id → per-thesis outcome attribution + ablation.

CREATE TABLE IF NOT EXISTS theses (
    id                 BIGSERIAL   PRIMARY KEY,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by         TEXT        NOT NULL,           -- 'friday' (desk lead) | 'user'
    symbol             TEXT        NOT NULL,
    direction          TEXT        NOT NULL,           -- long | short | flat
    conviction         NUMERIC     NOT NULL,           -- 0..1 → size as fraction of max_position
    horizon            TEXT,                           -- e.g. '4h' | '2d'
    invalidation       TEXT,                           -- failure condition (text)
    invalidation_price NUMERIC,                        -- optional price level → stop
    evidence           JSONB,                          -- refs: metric reads / catalyst / news
    rationale          TEXT        NOT NULL,           -- why (User-visible)
    status             TEXT        NOT NULL DEFAULT 'active',  -- active|closed|invalidated|superseded
    closed_at          TIMESTAMPTZ,
    outcome_pnl        NUMERIC,
    outcome_note       TEXT
);
CREATE INDEX IF NOT EXISTS idx_theses_symbol ON theses (symbol, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_theses_active ON theses (symbol) WHERE status = 'active';

ALTER TABLE positions ADD COLUMN IF NOT EXISTS thesis_id BIGINT;
