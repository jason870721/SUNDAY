// Manual — makes "User gets the same API the agent has" literal: the rendered
// operations manual (the single source of truth the swarm reads via /manual), an
// endpoint reference, and a read-only API console to GET any endpoint live.
import { ref, reactive, onMounted } from '../vue.js';
import { api } from '../api.js';
import { Panel, Empty } from '../components.js';

const ENDPOINTS = [
  { m: 'GET', p: '/status', d: 'mode / strategy / rationale / position / equity / heartbeat', perm: 'auto' },
  { m: 'GET', p: '/advisor', d: 'regime + 每策略 vote + funding + recommendation', perm: 'auto' },
  { m: 'GET', p: '/positions', d: '持倉 + entry_reason + stop', perm: 'auto' },
  { m: 'GET', p: '/pnl', d: 'realized / unrealized / equity / equity_curve', perm: 'auto' },
  { m: 'GET', p: '/performance', d: 'per-strategy 績效歸因', perm: 'auto' },
  { m: 'GET', p: '/strategy_history', d: '切策略時間軸（含 reason）', perm: 'auto' },
  { m: 'GET', p: '/market', d: 'OHLCV', perm: 'auto' },
  { m: 'GET', p: '/envelope', d: '當前風險封套', perm: 'auto' },
  { m: 'GET', p: '/risk', d: '封套 vs 即時 + 使用率 + 違規 + 風控事件', perm: 'auto' },
  { m: 'GET', p: '/trades', d: '成交帳本 / blotter', perm: 'auto' },
  { m: 'GET', p: '/events', d: 'Sunday→swarm 喚醒事件', perm: 'auto' },
  { m: 'GET', p: '/commentary', d: 'analyst 市場貼文', perm: 'auto' },
  { m: 'POST', p: '/strategy', d: '切策略 lever（reason 必填）', perm: 'lever' },
  { m: 'POST', p: '/envelope', d: '設風險封套 lever', perm: 'lever' },
  { m: 'POST', p: '/halt', d: 'kill-switch（flat / safe）', perm: 'lever' },
  { m: 'POST', p: '/heartbeat', d: 'leader liveness ping', perm: 'auto' },
  { m: 'POST', p: '/commentary', d: 'analyst/User 推市場動態（無害寫入）', perm: 'auto' },
];

const PRESETS = ['/status', '/advisor?symbol=BTCUSDT', '/risk', '/pnl', '/performance', '/positions', '/trades?limit=20', '/events?limit=20', '/envelope', '/strategy_history', '/commentary?limit=20', '/health'];

export default {
  components: { Panel, Empty },
  setup() {
    const html = ref('');
    const rendered = ref(false);
    const path = ref('/status');
    const result = ref('');
    const busy = ref(false);
    const err = ref('');

    onMounted(async () => {
      try {
        const text = await api.manual();
        html.value = window.marked ? window.marked.parse(text) : '<pre>' + text.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c])) + '</pre>';
        rendered.value = true;
      } catch (e) { html.value = '<div class="empty">無法載入 /manual：' + (e.detail || e.message) + '</div>'; rendered.value = true; }
    });

    async function send() {
      err.value = '';
      const p = (path.value || '').trim();
      if (!p.startsWith('/')) { err.value = '路徑需以 / 開頭'; return; }
      busy.value = true;
      try {
        const res = await fetch(p, { cache: 'no-store', headers: { Accept: 'application/json' } });
        const txt = await res.text();
        try { result.value = JSON.stringify(JSON.parse(txt), null, 2); } catch { result.value = txt; }
        if (!res.ok) err.value = p + ' → ' + res.status;
      } catch (e) { err.value = e.message; result.value = ''; }
      busy.value = false;
    }
    function preset(p) { path.value = p; send(); }

    return { html, rendered, path, result, busy, err, ENDPOINTS, PRESETS, send, preset };
  },
  template: `
  <div class="view">
    <div class="view-head"><h1>Manual</h1><span class="sub">操作手冊 + API · agent 與 User 共讀同一份</span></div>

    <Panel title="Endpoint reference" flush>
      <table class="tbl">
        <thead><tr><th>Method</th><th>Path</th><th>用途</th><th>Permission</th></tr></thead>
        <tbody><tr v-for="e in ENDPOINTS" :key="e.m+e.p">
          <td><span class="tag" :class="e.m==='GET'?'long':'short'">{{ e.m }}</span></td>
          <td class="mono">{{ e.p }}</td>
          <td class="dim">{{ e.d }}</td>
          <td><span class="tag" :class="e.perm==='lever'?'short':'flat'">{{ e.perm==='lever' ? 'ask / lever' : 'auto-allow' }}</span></td>
        </tr></tbody>
      </table>
    </Panel>

    <Panel title="API console · 唯讀 GET" hint="等價於 agent 的 curl">
      <div class="flexrow" style="gap:6px;margin-bottom:10px">
        <span v-for="p in PRESETS" :key="p" class="chip" @click="preset(p)">{{ p }}</span>
      </div>
      <div class="flexrow">
        <input class="input mono grow" v-model="path" @keyup.enter="send" placeholder="/status">
        <button class="btn primary" :disabled="busy" @click="send"><span v-if="busy" class="ld"></span>Send</button>
      </div>
      <div class="hint-row err" v-if="err" style="margin-top:8px">{{ err }}</div>
      <pre v-if="result" class="md" style="margin-top:12px;max-height:420px;overflow:auto"><code>{{ result }}</code></pre>
      <div class="hint-row" style="margin-top:8px">只開放 GET（讀）。POST lever 一律走 Strategy / Risk 頁有確認的正式控制。</div>
    </Panel>

    <Panel title="GET /manual">
      <div class="md" v-html="html" v-if="rendered"></div>
      <Empty v-else>載入中…</Empty>
    </Panel>
  </div>`,
};
