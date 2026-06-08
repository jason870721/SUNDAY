// Display formatting — all numbers go through here so the terminal stays consistent
// (tabular alignment, em-dash for null, signed PnL, semantic up/down classes).

const DASH = '—';
const isNum = (v) => v !== null && v !== undefined && v !== '' && !Number.isNaN(Number(v));

export function num(v, dp = 2) {
  if (!isNum(v)) return DASH;
  return Number(v).toLocaleString(undefined, { minimumFractionDigits: dp, maximumFractionDigits: dp });
}

// Money with a thin USDT suffix omitted (callers label the column). Signed optional.
export function money(v, dp = 2) {
  return num(v, dp);
}

// Signed value: "+1,234.50" / "-12.00" — for PnL where direction matters.
export function signed(v, dp = 2) {
  if (!isNum(v)) return DASH;
  const n = Number(v);
  return (n > 0 ? '+' : '') + num(n, dp);
}

export function pct(v, dp = 2) {
  if (!isNum(v)) return DASH;
  return num(v, dp) + '%';
}

// ratio (0..1+) -> percent string, for utilization bars.
export function ratioPct(v, dp = 0) {
  if (!isNum(v)) return DASH;
  return num(Number(v) * 100, dp) + '%';
}

export function compact(v) {
  if (!isNum(v)) return DASH;
  const n = Number(v);
  const a = Math.abs(n);
  if (a >= 1e9) return (n / 1e9).toFixed(2) + 'B';
  if (a >= 1e6) return (n / 1e6).toFixed(2) + 'M';
  if (a >= 1e3) return (n / 1e3).toFixed(1) + 'k';
  return num(n, 0);
}

// CSS class for sign coloring.
export function signClass(v) {
  if (!isNum(v)) return '';
  const n = Number(v);
  return n > 0 ? 'up' : n < 0 ? 'down' : '';
}

// ms epoch | ISO string -> Date
function toDate(t) {
  if (t === null || t === undefined) return null;
  if (typeof t === 'number') return new Date(t);
  const d = new Date(t);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function time(t) {
  const d = toDate(t);
  return d ? d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : DASH;
}

export function dateTime(t) {
  const d = toDate(t);
  return d ? d.toLocaleString([], { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : DASH;
}

export function relTime(t) {
  const d = toDate(t);
  if (!d) return DASH;
  const s = Math.round((Date.now() - d.getTime()) / 1000);
  if (s < 0) return 'now';
  if (s < 60) return s + 's ago';
  const m = Math.round(s / 60);
  if (m < 60) return m + 'm ago';
  const h = Math.round(m / 60);
  if (h < 24) return h + 'h ago';
  return Math.round(h / 24) + 'd ago';
}

// seconds -> "1h 30m" / "45m" / "20s"
export function dur(seconds) {
  if (!isNum(seconds)) return DASH;
  const s = Math.max(0, Math.round(Number(seconds)));
  if (s < 60) return s + 's';
  const m = Math.floor(s / 60);
  if (m < 60) return m + 'm';
  const h = Math.floor(m / 60);
  return h + 'h ' + (m % 60) + 'm';
}

export function titleCase(s) {
  return (s || '').replace(/(^|_)([a-z])/g, (_, p, c) => (p ? ' ' : '') + c.toUpperCase());
}
