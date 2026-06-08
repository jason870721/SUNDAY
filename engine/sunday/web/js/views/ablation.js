// Ablation — the kill-line (M4-D5). Desk vs no-trade shadow baselines + the
// info-ON/OFF realized split. The question this whole pivot lives or dies on:
// did the information layer + agent synthesis actually add value?
import { ref, reactive, onMounted, onBeforeUnmount } from '../vue.js';
import { api } from '../api.js';
import * as fmt from '../format.js';
import { Panel, Kpi, Empty } from '../components.js';
import { makeCompareChart, hasCharts } from '../charts.js';

export default {
  components: { Panel, Kpi, Empty },
  setup() {
    const d = reactive({ rep: {}, loaded: false });
    const chartEl = ref(null);
    let chart = null;
    let timer = null;

    async function load() {
      const rep = await api.ablation().catch(() => ({}));
      d.rep = rep;
      d.loaded = true;
      if (chart) {
        const data = { desk: rep.desk?.equity_curve || [] };
        for (const [b, s] of Object.entries(rep.shadows || {})) data[b] = s.equity_curve || [];
        chart.setData(data);
      }
    }
    onMounted(() => {
      if (hasCharts() && chartEl.value) chart = makeCompareChart(chartEl.value);
      load();
      timer = setInterval(load, 30000);
    });
    onBeforeUnmount(() => { clearInterval(timer); if (chart) chart.destroy(); });

    return { d, fmt, chartEl, hasCharts: hasCharts() };
  },
  template: `
  <div class="view">
    <div class="view-head"><h1>Ablation</h1><span class="sub">驗證 · 資訊層到底有沒有加值（生死線）</span></div>

    <div class="grid cols-4">
      <Kpi k="Desk realized" :v="fmt.signed(d.rep.desk?.realized)" :tone="fmt.signClass(d.rep.desk?.realized)" sub="實際 directed 台"/>
      <Kpi k="Buy-hold (shadow)" :v="fmt.money(d.rep.shadows?.buy_hold?.equity_latest)" sub="等權持有基準"/>
      <Kpi k="Funding-carry (shadow)" :v="fmt.money(d.rep.shadows?.funding_carry?.equity_latest)" sub="理想化 carry 參考"/>
      <Kpi k="Info ON − OFF" :v="fmt.signed((d.rep.info_split?.on?.realized||0)-(d.rep.info_split?.off?.realized||0))"
           :tone="((d.rep.info_split?.on?.realized||0)-(d.rep.info_split?.off?.realized||0))>=0?'up':'down'" sub="資訊有無加值"/>
    </div>

    <Panel title="Equity: desk vs shadow baselines">
      <div class="chart" ref="chartEl"></div>
      <Empty v-if="d.loaded && !(d.rep.desk?.equity_curve||[]).length">尚無權益/影子資料（跑一段後出現）。<span v-if="!hasCharts"><br>圖表庫未載入。</span></Empty>
    </Panel>

    <div class="grid cols-2">
      <Panel title="info-ON / OFF realized split" hint="GET /ablation">
        <div class="kv"><span class="kk">ON（有資訊層）{{ (d.rep.info_split?.on?.symbols||[]).join(' ') }}</span>
          <span class="vv" :class="fmt.signClass(d.rep.info_split?.on?.realized)">{{ fmt.signed(d.rep.info_split?.on?.realized) }}</span></div>
        <div class="kv"><span class="kk">OFF（只看價格）{{ (d.rep.info_split?.off?.symbols||[]).join(' ') }}</span>
          <span class="vv" :class="fmt.signClass(d.rep.info_split?.off?.realized)">{{ fmt.signed(d.rep.info_split?.off?.realized) }}</span></div>
        <div class="rationale" style="margin-top:12px">{{ d.rep.note }}</div>
      </Panel>

      <Panel title="Theses">
        <div class="kv"><span class="kk">總數</span><span class="vv">{{ d.rep.theses?.n ?? '—' }}</span></div>
        <div class="kv" v-for="(n,s) in (d.rep.theses?.by_status||{})" :key="s"><span class="kk">{{ s }}</span><span class="vv">{{ n }}</span></div>
        <Empty v-if="!(d.rep.theses?.n)">尚無 thesis。</Empty>
      </Panel>
    </div>
  </div>`,
};
