// Reports — the agent→User legibility surface (PRD §7.11). Four streams co-located:
// leader strategy switches (+reason), analyst commentary, deterministic risk events,
// and the wake events Sunday sent the swarm — merged into one filterable timeline.
// Plus a composer so the User can post an operator note onto the same record.
import { ref, reactive, onMounted, onBeforeUnmount, computed } from '../vue.js';
import { api } from '../api.js';
import { lever, toast } from '../store.js';
import * as fmt from '../format.js';
import { Panel, Empty, Icon } from '../components.js';

const KINDS = [
  { id: 'all', label: '全部' }, { id: 'strat', label: '策略' },
  { id: 'comment', label: 'Commentary' }, { id: 'risk', label: '風控' }, { id: 'event', label: '喚醒' },
];
const ICON = { strat: 'swap', comment: 'chat', risk: 'alert', event: 'bell' };

export default {
  components: { Panel, Empty, Icon },
  setup() {
    const d = reactive({ comm: [], hist: [], risk: {}, events: [], loaded: false });
    const filter = ref('all');
    const draft = reactive({ author: 'operator', title: '', body: '' });
    const busy = ref(false);
    let timer = null;

    async function load() {
      const [comm, hist, risk, events] = await Promise.all([
        api.commentary(60).catch(() => []), api.strategyHistory().catch(() => []),
        api.risk().catch(() => ({})), api.events(60).catch(() => []),
      ]);
      Object.assign(d, { comm, hist, risk, events, loaded: true });
    }
    onMounted(() => { load(); timer = setInterval(load, 25000); });
    onBeforeUnmount(() => clearInterval(timer));

    const timeline = computed(() => {
      const items = [];
      for (const h of d.hist || []) items.push({ ts: h.set_at_ms, kind: 'strat', who: h.set_by || 'friday', title: '切策略 → ' + h.strategy, body: h.reason || '' });
      for (const c of d.comm || []) items.push({ ts: new Date(c.ts).getTime(), kind: 'comment', who: c.author || 'analyst', title: c.title || 'commentary', body: c.body });
      for (const e of (d.risk.recent_events || [])) items.push({ ts: new Date(e.ts).getTime(), kind: 'risk', who: 'engine', title: 'risk · ' + e.type, body: (e.action_taken || '') + (e.detail ? ' — ' + JSON.stringify(e.detail) : '') });
      for (const w of d.events || []) items.push({ ts: new Date(w.ts).getTime(), kind: 'event', who: 'engine → ' + w.to_member, title: w.event_type, body: w.body || w.title || '' });
      items.sort((a, b) => b.ts - a.ts);
      return filter.value === 'all' ? items : items.filter((i) => i.kind === filter.value);
    });

    async function post() {
      if (!draft.body.trim()) { toast('內容必填', 'error'); return; }
      busy.value = true;
      const r = await lever(() => api.postCommentary({ author: draft.author || 'operator', title: draft.title || null, body: draft.body }), 'Note 已發佈');
      busy.value = false;
      if (r) { draft.title = ''; draft.body = ''; load(); }
    }

    return { d, fmt, filter, draft, busy, KINDS, ICON, timeline, post };
  },
  template: `
  <div class="view">
    <div class="view-head"><h1>Reports</h1><span class="sub">agent → User · 決策理由 + 市場脈絡</span></div>

    <div class="grid cols-2">
      <Panel title="Commentary feed · analyst 市場動態" hint="GET /commentary">
        <div v-if="(d.comm||[]).length">
          <div v-for="(c,i) in d.comm" :key="i" class="note">
            <div class="nh"><span class="auth">{{ c.author }}</span><span class="when">{{ fmt.relTime(c.ts) }} · {{ fmt.dateTime(c.ts) }}</span></div>
            <div class="ntitle" v-if="c.title">{{ c.title }}</div>
            <div class="nbody">{{ c.body }}</div>
          </div>
        </div>
        <Empty v-else>尚無 commentary。analyst 會在此推市場脈絡（也可由 User 在右側撰寫）。</Empty>
      </Panel>

      <Panel title="撰寫 note · POST /commentary">
        <div class="field"><label>Author</label><input class="input" v-model="draft.author" placeholder="operator"></div>
        <div class="field" style="margin-top:10px"><label>Title（選填）</label><input class="input" v-model="draft.title" placeholder="例如：手動觀察 / 市場備註"></div>
        <div class="field" style="margin-top:10px"><label>Body</label><textarea class="input" v-model="draft.body" style="min-height:120px" placeholder="寫給 User 自己看的市場脈絡 / 操作備註…"></textarea></div>
        <div class="flexrow end" style="margin-top:12px">
          <button class="btn primary" :disabled="busy" @click="post"><span v-if="busy" class="ld"></span><Icon v-else name="chat" :size="15"/>發佈</button>
        </div>
        <div class="hint-row" style="margin-top:8px">無害寫入（非交易 lever）；會出現在左側 feed 與下方時間軸。</div>
      </Panel>
    </div>

    <Panel title="Decision & event timeline">
      <template #head>
        <div class="flexrow">
          <span v-for="k in KINDS" :key="k.id" class="chip" :class="{on: filter===k.id}" @click="filter=k.id">{{ k.label }}</span>
        </div>
      </template>
      <div class="feed" v-if="timeline.length">
        <div v-for="(it,i) in timeline" :key="i" class="item">
          <div class="rail"><span class="icn" :class="it.kind"><Icon :name="ICON[it.kind]" :size="13"/></span></div>
          <div class="body">
            <div class="top"><span class="who">{{ it.who }}</span><span class="ttl">· {{ it.title }}</span><span class="when">{{ fmt.dateTime(it.ts) }}</span></div>
            <div class="txt" v-if="it.body">{{ it.body }}</div>
          </div>
        </div>
      </div>
      <Empty v-else>尚無活動。引擎切策略 / analyst commentary / 風控 / 喚醒事件會在此匯流。</Empty>
    </Panel>
  </div>`,
};
