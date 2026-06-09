// Typed client mirroring Sunday's REST surface — one function per endpoint. This file
// IS the agent's mental model made visible: the UI can do exactly what /manual documents.

export interface Page<T> { items: T[]; page: number; page_size: number; total: number; has_more: boolean }

export interface Market {
  symbol: string; unified: string; last: number | null; high: number | null; low: number | null
  change_pct: number | null; quote_volume: number | null; base_volume: number | null
}
export interface Position {
  symbol: string; side: string; qty: number | null; entry: number | null; mark: number | null
  leverage: number | null; margin_mode: string | null; notional: number
  unrealized_pnl: number | null; roi_pct: number | null; liquidation_price: number | null
}
export interface Order {
  id: string; symbol: string; type: string; side: string; price: number | null; amount: number | null
  filled: number | null; remaining: number | null; status: string; reduce_only: boolean
  trigger_price: number | null; ts: number | null; client_order_id?: string
}
export interface Trade {
  id: string; order: string; symbol: string; side: string; price: number | null; amount: number | null
  cost: number | null; fee: number | null; realized_pnl: number | null; ts: number | null
}
export interface Funding {
  symbol: string; rate: number | null; mark: number | null; index: number | null
  next_funding_ts: number | null; interval_hours?: number
}
export interface Klines { symbol: string; interval: string; columns: string[]; count: number; ohlcv: number[][] }
export interface IndexRow {
  key: string; group: string; label: string; available: boolean; stale?: boolean; as_of?: number
  value?: number; price?: number; change_pct?: number; classification?: string; source?: string
  total_market_cap_usd?: number; [k: string]: unknown
}
export interface Alert {
  id: number; symbol: string; kind: string; threshold: number; ref_price: number | null; note: string | null
  status: string; created_at: string; triggered_at: string | null; triggered_price: number | null
}
export interface MonitorState {
  config: { enabled: boolean; step_pct: number; poll_sec: number; ws: boolean }
  positions: Array<{ symbol: string; side: string; roi_pct: number | null; bucket: number | null; mark: number | null; entry: number | null; qty: number | null }>
}

const API = '/api'

function qs(params: Record<string, unknown> = {}): string {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(params))
    if (v !== undefined && v !== null && v !== '') p.set(k, String(v))
  const s = p.toString()
  return s ? `?${s}` : ''
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(API + path, { headers: { 'Content-Type': 'application/json' }, ...init })
  const text = await res.text()
  const data = text ? JSON.parse(text) : null
  if (!res.ok) throw new Error(data?.detail ? `${res.status} · ${data.detail}` : `${res.status} ${res.statusText}`)
  return data as T
}

export async function fetchHealth(): Promise<{ ok: boolean; version: string }> {
  return (await fetch('/health')).json()
}
export async function fetchManual(): Promise<string> {
  return (await fetch('/manual')).text()
}

export const api = {
  markets: (p: Record<string, unknown>) => req<Page<Market>>(`/markets${qs(p)}`),
  market: (s: string) => req<{ symbol: string; ticker: Record<string, number | null>; info: Record<string, unknown> }>(`/markets/${s}`),

  klines: (p: Record<string, unknown>) => req<Klines>(`/klines${qs(p)}`),
  indicators: (p: Record<string, unknown>) => req<{ symbol: string; interval: string; as_of: number | null; last_close: number | null; indicators: Record<string, unknown> }>(`/klines/indicators${qs(p)}`),
  funding: (symbol: string) => req<Funding>(`/funding${qs({ symbol })}`),
  fundingHistory: (p: Record<string, unknown>) => req<Page<{ symbol: string; ts: number; rate: number | null }>>(`/funding/history${qs(p)}`),

  positions: (p: Record<string, unknown> = {}) => req<Page<Position>>(`/account/positions${qs(p)}`),
  balance: () => req<{ equity: number | null; free: number | null; used: number | null; assets: Record<string, number> }>(`/account/balance`),
  pnl: () => req<{ equity: number | null; unrealized_pnl: number; positions: Position[] }>(`/account/pnl`),
  openOrders: (p: Record<string, unknown> = {}) => req<Page<Order>>(`/account/orders/open${qs(p)}`),
  orderHistory: (p: Record<string, unknown>) => req<Page<Order>>(`/account/orders${qs(p)}`),
  trades: (p: Record<string, unknown>) => req<Page<Trade>>(`/account/trades${qs(p)}`),

  placeOrder: (body: Record<string, unknown>) => req<Record<string, unknown>>(`/perp/order`, { method: 'POST', body: JSON.stringify(body) }),
  setLeverage: (body: Record<string, unknown>) => req<Record<string, unknown>>(`/perp/leverage`, { method: 'POST', body: JSON.stringify(body) }),
  setMarginMode: (body: Record<string, unknown>) => req<Record<string, unknown>>(`/perp/margin-mode`, { method: 'POST', body: JSON.stringify(body) }),
  closePosition: (symbol: string) => req<Record<string, unknown>>(`/perp/close`, { method: 'POST', body: JSON.stringify({ symbol }) }),
  cancelOrder: (id: string, symbol: string) => req<Record<string, unknown>>(`/perp/order/${id}${qs({ symbol })}`, { method: 'DELETE' }),
  cancelAll: (symbol: string) => req<Record<string, unknown>>(`/perp/orders${qs({ symbol })}`, { method: 'DELETE' }),

  indices: () => req<{ items: IndexRow[] }>(`/indices`),

  alerts: (p: Record<string, unknown> = {}) => req<Page<Alert>>(`/alerts${qs(p)}`),
  createAlert: (body: Record<string, unknown>) => req<Alert>(`/alerts`, { method: 'POST', body: JSON.stringify(body) }),
  deleteAlert: (id: number) => req<Record<string, unknown>>(`/alerts/${id}`, { method: 'DELETE' }),

  monitor: () => req<MonitorState>(`/monitor`),
  monitorConfig: (body: Record<string, unknown>) => req<Record<string, unknown>>(`/monitor/config`, { method: 'POST', body: JSON.stringify(body) }),
}
