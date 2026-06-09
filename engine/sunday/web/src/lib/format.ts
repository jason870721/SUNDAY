// Display formatters — tabular, terminal-style. null/undefined render as an em dash.

export function num(v: unknown, dp = 2): string {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '—'
  return Number(v).toLocaleString('en-US', { minimumFractionDigits: dp, maximumFractionDigits: dp })
}

export function price(v: unknown): string {
  if (v === null || v === undefined) return '—'
  const n = Number(v)
  const dp = Math.abs(n) >= 1000 ? 2 : Math.abs(n) >= 1 ? 3 : 6
  return n.toLocaleString('en-US', { minimumFractionDigits: dp, maximumFractionDigits: dp })
}

export function pct(v: unknown, dp = 2): string {
  if (v === null || v === undefined) return '—'
  const n = Number(v)
  return `${n >= 0 ? '+' : ''}${n.toFixed(dp)}%`
}

export function usd(v: unknown, dp = 2): string {
  return v === null || v === undefined ? '—' : '$' + num(v, dp)
}

export function compact(v: unknown): string {
  if (v === null || v === undefined) return '—'
  const n = Number(v), a = Math.abs(n)
  if (a >= 1e9) return (n / 1e9).toFixed(2) + 'B'
  if (a >= 1e6) return (n / 1e6).toFixed(2) + 'M'
  if (a >= 1e3) return (n / 1e3).toFixed(1) + 'K'
  return n.toFixed(0)
}

export function sign(v: unknown): '' | 'up' | 'down' {
  if (v === null || v === undefined) return ''
  return Number(v) >= 0 ? 'up' : 'down'
}

export function ago(ts: unknown): string {
  if (!ts) return '—'
  const s = Math.floor((Date.now() - Number(ts)) / 1000)
  if (s < 60) return s + 's ago'
  const m = Math.floor(s / 60)
  if (m < 60) return m + 'm ago'
  const h = Math.floor(m / 60)
  if (h < 24) return h + 'h ago'
  return Math.floor(h / 24) + 'd ago'
}

export function time(ts: unknown): string {
  return ts ? new Date(Number(ts)).toLocaleString() : '—'
}
