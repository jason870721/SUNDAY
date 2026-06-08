// Strategy — the control room. The full /advisor decision-support panel (the same
// computed features the agent reads), the switch lever (reason required; re-read
// /status before commanding + verify after, per PRD §7.10), and a market candlestick
// chart for context.
import { ref, reactive, onMounted, onBeforeUnmount, computed } from '../vue.js';
import { api } from '../api.js';
import { store, lever, refreshStatus, toast } from '../store.js';
import * as fmt from '../format.js';
import { Panel, Kpi, Empty, VoteBar, Icon } from '../components.js';
import { makeMarketChart, hasCharts } from '../charts.js';

const STRATS = ['momentum', 'mean_reversion', 'flat'];

export default {
  components: { Panel, Kpi, Empty, VoteBar, Icon },
  setup() {
    const d = reactive({ adv: {}, loaded: false });
    const chosen = ref('momentum');
    const reason = ref('');
    const tf = ref('1h');
    const busy = ref(false);
    const touched = ref(false);     // once the User picks, stop auto-syncing to live
    const marketEl = ref(null);
    let chart = null;
    let timer = null;

    const current = computed(() => store.status?.strategy || '—');
    const reci = computed(() => d.adv.recommendation || {});

    async function loadAdvisor() {
      const adv = await api.advisor(store.symbol).catch(() => ({}));
      Object.assign(d, { adv, loaded: true });
      if (!touched.value && store.status?.strategy && STRATS.includes(store.status.strategy)) chosen.value = store.status.strategy;
    }
    async function loadMarket() {
      if (!chart) return;
      const m = await api.market(store.symbol, tf.value, 200).catch(() => ({ ohlcv: [] }));
      chart.setData(m.ohlcv || []);
    }

    onMounted(() => {
      if (hasCharts() && marketEl.value) chart = makeMarketChart(marketEl.value);
      refreshStatus().then(loadAdvisor);
      loadMarket();
      timer = setInterval(() => { loadAdvisor(); loadMarket(); }, 30000);
    });
    onBeforeUnmount(() => { clearInterval(timer); if (chart) chart.destroy(); });

    function pick(s) { chosen.value = s; touched.value = true; }
    function setTf(t) { tf.value = t; loadMarket(); }
    function useRec() {
      if (reci.value.strategy) { pick(reci.value.strategy); reason.value = '採納引擎建議：' + (reci.value.why || ''); }
    }
    async function submit() {
      if (!reason.value.trim()) { toast('reason 必填 — 會留存給 User 與稽核', 'error'); return; }
      if (chosen.value === current.value) { toast('已是當值策略（idempotent，無動作）', 'info'); }
      busy.value = true;
      await refreshStatus();   // §7.10-1: decide on "now", not the last snapshot
      const r = await lever(() => api.setStrategy({ symbol: store.symbol, strategy: chosen.value, reason: reason.value }), '已切到 ' + chosen.value);
      busy.value = false;
      if (r) { reason.value = ''; touched.value = false; await refreshStatus(); loadAdvisor(); }   // §7.10-2: verify
    }

    return { d, fmt, chosen, reason, tf, busy, current, reci, marketEl, hasCharts: hasCharts(), STRATS, pick, setTf, useRec, submit, store };
  },
  template: `
  <div class="view">
    <div class="view-head"><h1>Strategy</h1><span class="sub">策略控制 · 決策支援 + 切換 lever</span></div>

    <div class="grid cols-2">
      <Panel title="Decision support · GET /advisor" :hint="store.symbol">
        <div v-if="d.adv.regime">
          <div class="flexrow" style="justify-content:space-between">
            <div><div class="dim mono" style="font-size:10px;text-transform:uppercase;letter-spacing:.07em">Regime</div>
              <div style="font-size:18px;font-weight:700;margin-top:3px">
                <span class="tag" :class="d.adv.regime.label==='trending'?'mom':d.adv.regime.label==='volatile'?'short':'mr'">{{ d.adv.regime.label }}</span>
              </div></div>
            <div class="right dim mono" style="font-size:12px">ADX {{ fmt.num(d.adv.regime.adx,1) }}<br>vol {{ fmt.num(d.adv.regime.vol_pct,2) }}%</div>
          </div>
          <div class="rationale" style="margin:10px 0">{{ d.adv.regime.rationale }}</div>

          <div class="dim mono" style="font-size:10px;text-transform:uppercase;letter-spacing:.07em;margin:14px 0 2px">Strategy votes</div>
          <VoteBar v-for="v in d.adv.votes" :key="v.strategy" :vote="v"/>

          <div class="kv" style="margin-top:12px"><span class="kk">Funding</span><span class="vv dim">{{ d.adv.funding?.note }}</span></div>
        </div>
        <Empty v-else>advisor 無資料 — exchange 不可達時這裡會空（lever 仍可用）。</Empty>
      </Panel>

      <div style="display:flex;flex-direction:column;gap:14px">
        <Panel title="Recommendation">
          <div v-if="reci.strategy" class="flexrow" style="justify-content:space-between;align-items:flex-start">
            <div><div style="font-size:22px;font-weight:700"><span class="warn">{{ reci.strategy }}</span> <span class="dim" style="font-size:15px" v-if="reci.direction">· {{ reci.direction }}</span></div>
              <div class="muted" style="margin-top:4px;max-width:340px">{{ reci.why }}</div></div>
            <button class="btn sm" @click="useRec"><Icon name="check" :size="14"/>採納</button>
          </div>
          <div class="rationale warn" v-if="reci.funding_caveat" style="margin-top:10px">⚠ funding 逆風：{{ reci.funding_caveat }}</div>
          <Empty v-else-if="!reci.strategy">—</Empty>
        </Panel>

        <Panel title="Switch lever · POST /strategy">
          <div class="kv"><span class="kk">當值策略 (live)</span><span class="vv"><span class="tag" :class="current==='momentum'?'mom':current==='mean_reversion'?'mr':'flat'">{{ current }}</span></span></div>
          <div class="field" style="margin-top:12px">
            <label>目標策略</label>
            <div class="seg">
              <button v-for="s in STRATS" :key="s" :class="{on: chosen===s, mom: chosen===s&&s==='momentum', mr: chosen===s&&s==='mean_reversion'}" @click="pick(s)">{{ s }}</button>
            </div>
          </div>
          <div class="field" style="margin-top:12px">
            <label>Reason（必填，留存給 User）</label>
            <textarea class="input" v-model="reason" placeholder="為何切換？例如：analyst 判趨勢轉強、regime 由 ranging→trending…"></textarea>
          </div>
          <div class="flexrow" style="margin-top:12px;justify-content:space-between">
            <span class="hint-row">送出前自動重抓 /status，送出後驗證已切換（§7.10）。set_by=user。</span>
            <button class="btn primary" :disabled="busy" @click="submit"><span v-if="busy" class="ld"></span><Icon v-else name="swap" :size="15"/>切換策略</button>
          </div>
        </Panel>
      </div>
    </div>

    <Panel title="Market · candlesticks">
      <template #head>
        <div class="seg" style="padding:2px">
          <button v-for="t in ['15m','1h','4h']" :key="t" :class="{on: tf===t}" @click="setTf(t)" style="padding:5px 12px;font-size:12px">{{ t }}</button>
        </div>
      </template>
      <div class="chart tall" ref="marketEl"></div>
      <Empty v-if="!hasCharts">圖表庫未載入（離線？）。</Empty>
    </Panel>
  </div>`,
};
