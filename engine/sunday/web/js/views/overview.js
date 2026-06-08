// Overview — the at-a-glance command panel: KPIs, the equity curve with strategy-
// switch reason overlay (D14 centerpiece), open positions, per-strategy attribution,
// a live advisor read, and a recent-trades blotter.
import { ref, reactive, onMounted, onBeforeUnmount } from '../vue.js';
import { api } from '../api.js';
import * as fmt from '../format.js';
import { Panel, Kpi, Empty } from '../components.js';
import { makeEquityChart, hasCharts } from '../charts.js';

export default {
  components: { Panel, Kpi, Empty },
  setup() {
    const d = reactive({ pnl: {}, risk: {}, positions: [], perf: [], hist: [], adv: {}, trades: [], loaded: false });
    const equityEl = ref(null);
    let chart = null;
    let timer = null;

    async function load() {
      const [pnl, risk, positions, perf, hist, adv, trades] = await Promise.all([
        api.pnl().catch(() => ({})), api.risk().catch(() => ({})), api.positions().catch(() => []),
        api.performance().catch(() => []), api.strategyHistory().catch(() => []),
        api.advisor().catch(() => ({})), api.trades(8).catch(() => []),
      ]);
      Object.assign(d, { pnl, risk, positions, perf, hist, adv, trades, loaded: true });
      if (chart) chart.setData(pnl.equity_curve || [], hist || []);
    }

    onMounted(() => {
      if (hasCharts() && equityEl.value) chart = makeEquityChart(equityEl.value);
      load();
      timer = setInterval(load, 20000);
    });
    onBeforeUnmount(() => { clearInterval(timer); if (chart) chart.destroy(); });

    return { d, fmt, equityEl, hasCharts: hasCharts() };
  },
  template: `
  <div class="view">
    <div class="view-head"><h1>Overview</h1><span class="sub">總覽 · 引擎執行面板</span></div>

    <div class="grid cols-4">
      <Kpi k="Equity (USDT)" :v="fmt.money(d.pnl.equity ?? d.risk?.current?.equity)"/>
      <Kpi k="Realized" :v="fmt.signed(d.pnl.realized)" :tone="fmt.signClass(d.pnl.realized)" :sub="d.pnl.window_days ? d.pnl.window_days+'d window' : ''"/>
      <Kpi k="Unrealized" :v="fmt.signed(d.pnl.unrealized)" :tone="fmt.signClass(d.pnl.unrealized)"/>
      <Kpi k="Drawdown" :v="fmt.pct(d.risk?.current?.drawdown_pct)" :tone="(d.risk?.current?.drawdown_pct>=4)?'warn':''" :sub="'cap '+fmt.pct(d.risk?.envelope?.max_drawdown_pct)"/>
    </div>

    <Panel title="Equity curve · strategy-switch overlay" hint="切換點 hover 看 reason">
      <div class="chart" ref="equityEl"></div>
      <Empty v-if="d.loaded && !(d.pnl.equity_curve||[]).length">尚無權益快照（引擎跑一段、watcher tick 後出現）。<span v-if="!hasCharts"><br>圖表庫未載入 — 數據面板仍可用。</span></Empty>
    </Panel>

    <div class="grid cols-2">
      <Panel title="Open positions" flush>
        <table class="tbl" v-if="d.positions.length">
          <thead><tr><th>Symbol</th><th>Side</th><th class="n">Qty</th><th class="n">Entry</th><th class="n">Mark</th><th class="n">uPnL</th><th>Strategy</th><th class="n">Stop</th></tr></thead>
          <tbody><tr v-for="p in d.positions" :key="p.symbol+p.side">
            <td>{{ p.symbol }}</td>
            <td><span class="tag" :class="p.side">{{ p.side }}</span></td>
            <td class="n">{{ fmt.num(p.qty,3) }}</td>
            <td class="n">{{ fmt.money(p.entry) }}</td>
            <td class="n">{{ fmt.money(p.mark) }}</td>
            <td class="n" :class="fmt.signClass(p.upnl)">{{ fmt.signed(p.upnl) }}</td>
            <td><span class="tag" :class="p.strategy==='momentum'?'mom':p.strategy==='mean_reversion'?'mr':'flat'">{{ p.strategy }}</span></td>
            <td class="n">{{ fmt.money(p.stop) }}</td>
          </tr></tbody>
        </table>
        <Empty v-else>無持倉（flat）。</Empty>
      </Panel>

      <Panel title="Advisor · 引擎此刻怎麼想" hint="GET /advisor">
        <div v-if="d.adv.regime">
          <div class="kv"><span class="kk">Regime</span><span class="vv"><span class="tag" :class="d.adv.regime.label==='trending'?'mom':d.adv.regime.label==='volatile'?'short':'mr'">{{ d.adv.regime.label }}</span> <span class="dim">ADX {{ fmt.num(d.adv.regime.adx,1) }} · vol {{ fmt.num(d.adv.regime.vol_pct,2) }}%</span></span></div>
          <div class="kv"><span class="kk">Recommendation</span><span class="vv"><span class="warn">{{ d.adv.recommendation?.strategy }}</span> <span class="dim" v-if="d.adv.recommendation?.direction">· {{ d.adv.recommendation.direction }}</span></span></div>
          <div class="rationale" style="margin:10px 0">{{ d.adv.recommendation?.why }}</div>
          <div class="kv"><span class="kk">Funding</span><span class="vv dim">{{ d.adv.funding?.note }}</span></div>
        </div>
        <Empty v-else>advisor 無資料（exchange 不可達？）。</Empty>
      </Panel>
    </div>

    <div class="grid cols-2">
      <Panel title="Per-strategy attribution" flush hint="GET /performance">
        <table class="tbl" v-if="d.perf.length">
          <thead><tr><th>Strategy</th><th class="n">Realized</th><th class="n">Trades</th><th class="n">Win%</th><th class="n">Avg</th><th class="n">Open</th></tr></thead>
          <tbody><tr v-for="r in d.perf" :key="r.strategy">
            <td><span class="tag" :class="r.strategy==='momentum'?'mom':r.strategy==='mean_reversion'?'mr':'flat'">{{ r.strategy }}</span></td>
            <td class="n" :class="fmt.signClass(r.realized_pnl)">{{ fmt.signed(r.realized_pnl) }}</td>
            <td class="n">{{ r.n_trades }}</td>
            <td class="n">{{ fmt.num(r.win_rate*100,1) }}%</td>
            <td class="n" :class="fmt.signClass(r.avg_pnl)">{{ fmt.signed(r.avg_pnl) }}</td>
            <td class="n">{{ fmt.num(r.open_qty,3) }}</td>
          </tr></tbody>
        </table>
        <Empty v-else>尚無交易。</Empty>
      </Panel>

      <Panel title="Recent orders" flush hint="GET /trades">
        <table class="tbl" v-if="d.trades.length">
          <thead><tr><th>Time</th><th>Side</th><th>Type</th><th class="n">Qty</th><th class="n">Price</th><th>Strategy</th></tr></thead>
          <tbody><tr v-for="(t,i) in d.trades" :key="i">
            <td class="tiny">{{ fmt.dateTime(t.ts) }}</td>
            <td><span class="tag" :class="t.side">{{ t.side }}</span></td>
            <td class="tiny">{{ t.type }}</td>
            <td class="n">{{ fmt.num(t.qty,3) }}</td>
            <td class="n">{{ fmt.money(t.price) }}</td>
            <td class="tiny">{{ t.strategy }}</td>
          </tr></tbody>
        </table>
        <Empty v-else>尚無成交。</Empty>
      </Panel>
    </div>
  </div>`,
};
