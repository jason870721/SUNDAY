// Global reactive store: the shared /status + /health snapshot the ribbon needs on
// every page, a polling loop, a toast system, and a lever() wrapper that gives the
// User success/failure feedback. Per-view heavy data is fetched by the views.
import { reactive } from './vue.js';
import { api } from './api.js';

export const store = reactive({
  status: null,
  health: null,
  statusError: null,
  lastStatusAt: null,
  toasts: [],
  _tid: 0,
  symbol: 'BTCUSDT',
});

let timer = null;

export async function refreshStatus() {
  try {
    const [st, hl] = await Promise.all([api.status(), api.health().catch(() => null)]);
    store.status = st;
    store.health = hl;
    store.statusError = null;
    store.lastStatusAt = Date.now();
  } catch (e) {
    store.statusError = e.detail || e.message;
  }
}

export function startPolling(ms = 10000) {
  if (timer) return;
  refreshStatus();
  timer = setInterval(refreshStatus, ms);
}

export function stopPolling() {
  if (timer) { clearInterval(timer); timer = null; }
}

export function toast(msg, kind = 'info', ttl = 4500) {
  const id = ++store._tid;
  store.toasts.push({ id, msg, kind });
  if (ttl) setTimeout(() => dismiss(id), ttl);
  return id;
}

export function dismiss(id) {
  const i = store.toasts.findIndex((t) => t.id === id);
  if (i >= 0) store.toasts.splice(i, 1);
}

// Run a lever call with toast feedback; refresh the shared status on success so the
// ribbon reflects the new state immediately (§7.10: verify after commanding).
export async function lever(fn, successMsg) {
  try {
    const r = await fn();
    toast(successMsg || '已送出', 'success');
    refreshStatus();
    return r;
  } catch (e) {
    toast(e.detail || e.message || '操作失敗', 'error', 8000);
    return null;
  }
}
