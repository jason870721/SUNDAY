// Sunday API client — one function per endpoint. This is the literal "User gets the
// same API the agent has": every GET the swarm polls + every lever it can pull.
// Same-origin (served by Sunday), so paths are absolute and unauthenticated (testnet
// loopback, per PRD §8 — token hardening is Gate-2).

const COMMON = { cache: 'no-store', headers: { Accept: 'application/json' } };

async function parseError(res, path) {
  let detail = res.statusText;
  try {
    const j = await res.json();
    if (j && j.detail) detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail);
  } catch { /* non-JSON body */ }
  const err = new Error(`${path} → ${res.status}: ${detail}`);
  err.status = res.status;
  err.detail = detail;
  return err;
}

async function get(path) {
  const res = await fetch(path, COMMON);
  if (!res.ok) throw await parseError(res, path);
  return res.json();
}

async function getText(path) {
  const res = await fetch(path, { ...COMMON, headers: { Accept: 'text/plain' } });
  if (!res.ok) throw await parseError(res, path);
  return res.text();
}

async function post(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
  if (!res.ok) throw await parseError(res, path);
  return res.json();
}

const qs = (params) => {
  const p = Object.entries(params || {}).filter(([, v]) => v !== undefined && v !== null && v !== '');
  return p.length ? '?' + new URLSearchParams(p).toString() : '';
};

export const api = {
  // --- reads (auto-allow) -------------------------------------------------
  status: () => get('/status'),
  health: () => get('/health'),
  advisor: (symbol = 'BTCUSDT') => get('/advisor' + qs({ symbol })),
  positions: () => get('/positions'),
  pnl: (since) => get('/pnl' + qs({ since })),
  performance: (since) => get('/performance' + qs({ since })),
  strategyHistory: (since) => get('/strategy_history' + qs({ since })),
  market: (symbol = 'BTCUSDT', tf = '1h', limit = 200) => get('/market' + qs({ symbol, tf, limit })),
  envelope: () => get('/envelope'),
  risk: () => get('/risk'),
  desk: (symbol) => get('/desk' + qs({ symbol })),
  thesis: (symbol = 'BTCUSDT') => get('/thesis' + qs({ symbol })),
  theses: (limit = 100, since) => get('/theses' + qs({ since, limit })),
  ablation: (since) => get('/ablation' + qs({ since })),
  trades: (limit = 100, since) => get('/trades' + qs({ since, limit })),
  events: (limit = 100, since) => get('/events' + qs({ since, limit })),
  commentary: (limit = 50, since) => get('/commentary' + qs({ since, limit })),
  manual: () => getText('/manual'),

  // --- levers (the User pulls them as the operator) -----------------------
  setStrategy: ({ symbol = 'BTCUSDT', strategy, reason }) =>
    post('/strategy', { symbol, strategy, reason, set_by: 'user' }),
  setEnvelope: (env) => post('/envelope', { ...env, set_by: 'user' }),
  setThesis: (t) => post('/thesis', { ...t, set_by: 'user' }),
  halt: ({ reason, mode }) => post('/halt', { reason, mode, set_by: 'user' }),
  heartbeat: () => post('/heartbeat', {}),
  postCommentary: ({ author = 'operator', title, body }) => post('/commentary', { author, title, body }),
};
