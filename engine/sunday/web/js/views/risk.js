// Risk — the risk-control room. Envelope utilization gauges (current vs caps), the
// /envelope lever editor (reason required, confirm before shrinking), the
// deterministic-fuse log (risk_events — the V6 evidence), and the heartbeat op.
import { ref, reactive, onMounted, onBeforeUnmount, computed } from '../vue.js';
import { api } from '../api.js';
import { store, lever, refreshStatus, toast } from '../store.js';
import * as fmt from '../format.js';
import { Panel, Kpi, Empty, Gauge, ConfirmModal, Icon } from '../components.js';

export default {
  components: { Panel, Kpi, Empty, Gauge, ConfirmModal, Icon },
  setup() {
    const d = reactive({ risk: {}, loaded: false });
    const form = reactive({ max_position_usd: 0, max_total_exposure_usd: 0, max_leverage: 0, max_drawdown_pct: 0, stop_pct: 0, reason: '' });
    const dirty = ref(false);
    const confirmOpen = ref(false);
    const busy = ref(false);
    const hbBusy = ref(false);
    let timer = null;

    const cur = computed(() => d.risk.current || {});
    const env = computed(() => d.risk.envelope || {});
    const util = computed(() => d.risk.utilization || {});
    const violations = computed(() => d.risk.violations || []);

    async function load() {
      const risk = await api.risk().catch(() => ({}));
      d.risk = risk;
      d.loaded = true;
      if (!dirty.value && risk.envelope) {
        for (const k of ['max_position_usd', 'max_total_exposure_usd', 'max_leverage', 'max_drawdown_pct', 'stop_pct']) form[k] = risk.envelope[k];
      }
    }
    onMounted(() => { refreshStatus(); load(); timer = setInterval(load, 20000); });
    onBeforeUnmount(() => clearInterval(timer));

    function onEdit() { dirty.value = true; }
    function review() {
      const vals = [form.max_position_usd, form.max_total_exposure_usd, form.max_leverage, form.max_drawdown_pct, form.stop_pct].map(Number);
      if (vals.some((v) => !(v > 0))) { toast('所有封套值必須為正數', 'error'); return; }
      if (!form.reason.trim()) { toast('reason 必填', 'error'); return; }
      confirmOpen.value = true;
    }
    async function submit() {
      busy.value = true;
      const r = await lever(() => api.setEnvelope({
        max_position_usd: Number(form.max_position_usd), max_total_exposure_usd: Number(form.max_total_exposure_usd),
        max_leverage: Number(form.max_leverage), max_drawdown_pct: Number(form.max_drawdown_pct),
        stop_pct: Number(form.stop_pct), reason: form.reason,
      }), '風險封套已更新');
      busy.value = false;
      if (r) { confirmOpen.value = false; dirty.value = false; form.reason = ''; load(); }
    }
    async function ping() {
      hbBusy.value = true;
      await lever(() => api.heartbeat(), 'Heartbeat → Sunday · watchdog 已重置（這不會通知 swarm）');
      hbBusy.value = false;
      refreshStatus();
    }

    return { d, fmt, form, cur, env, util, violations, confirmOpen, busy, hbBusy, store, onEdit, review, submit, ping };
  },
  template: `
  <div class="view">
    <div class="view-head"><h1>Risk</h1><span class="sub">風險控制 · 封套 + 確定性熔斷</span></div>

    <Panel title="Envelope utilization · GET /risk" :hint="d.risk.as_of_ts ? '' : 'live read'">
      <template #head>
        <span v-if="violations.length" class="badge" style="color:var(--down);border-color:rgba(246,70,93,.4)"><span class="dot bad"></span>{{ violations.length }} violation(s): {{ violations.join(', ') }}</span>
        <span v-else class="badge"><span class="dot ok"></span>within caps</span>
      </template>
      <div class="grid cols-2" style="gap:18px">
        <Gauge label="Single position" :ratio="util.position" :value="fmt.money(cur.position_usd)" :cap="fmt.money(env.max_position_usd)"/>
        <Gauge label="Total exposure" :ratio="util.exposure" :value="fmt.money(cur.exposure_usd)" :cap="fmt.money(env.max_total_exposure_usd)"/>
        <Gauge label="Leverage (eff.)" :ratio="util.leverage" :value="fmt.num(cur.leverage,2)+'x'" :cap="fmt.num(env.max_leverage,1)+'x'"/>
        <Gauge label="Drawdown" :ratio="util.drawdown" :value="fmt.pct(cur.drawdown_pct)" :cap="fmt.pct(env.max_drawdown_pct)"/>
      </div>
      <div class="kv" style="margin-top:16px"><span class="kk">Equity (USDT)</span><span class="vv">{{ fmt.money(cur.equity) }}</span></div>
    </Panel>

    <div class="grid cols-2">
      <Panel title="Envelope lever · POST /envelope">
        <div class="grid cols-2" style="gap:12px">
          <div class="field"><label>Max position (USD)</label><input class="input" type="number" v-model="form.max_position_usd" @input="onEdit"></div>
          <div class="field"><label>Max total exposure (USD)</label><input class="input" type="number" v-model="form.max_total_exposure_usd" @input="onEdit"></div>
          <div class="field"><label>Max leverage (x)</label><input class="input" type="number" step="0.5" v-model="form.max_leverage" @input="onEdit"></div>
          <div class="field"><label>Max drawdown (%)</label><input class="input" type="number" step="0.5" v-model="form.max_drawdown_pct" @input="onEdit"></div>
          <div class="field"><label>Stop (fraction)</label><input class="input" type="number" step="0.005" v-model="form.stop_pct" @input="onEdit"></div>
        </div>
        <div class="field" style="margin-top:12px"><label>Reason（必填）</label><textarea class="input" v-model="form.reason" @input="onEdit" placeholder="為何調整封套？例如：波動升高，收緊單筆與槓桿…"></textarea></div>
        <div class="flexrow" style="margin-top:12px;justify-content:space-between">
          <span class="hint-row">立即生效於下一輪 reconcile/tick；確定性風控以新封套硬擋。set_by=user。</span>
          <button class="btn primary" @click="review"><Icon name="scale" :size="15"/>套用封套</button>
        </div>
      </Panel>

      <Panel title="Risk events · 確定性熔斷日誌" flush hint="GET /risk → risk_events">
        <table class="tbl" v-if="(d.risk.recent_events||[]).length">
          <thead><tr><th>Time</th><th>Type</th><th>Action</th><th>Detail</th></tr></thead>
          <tbody><tr v-for="(e,i) in d.risk.recent_events" :key="i">
            <td class="tiny">{{ fmt.dateTime(e.ts) }}</td>
            <td><span class="tag short">{{ e.type }}</span></td>
            <td class="tiny">{{ e.action_taken }}</td>
            <td class="tiny dim">{{ JSON.stringify(e.detail) }}</td>
          </tr></tbody>
        </table>
        <Empty v-else>尚無熔斷事件（好事）。越線會在此留證（V6）。</Empty>
      </Panel>
    </div>

    <Panel title="Liveness · 雙向 dead-man">
      <div class="flexrow" style="justify-content:space-between">
        <div class="flexrow" style="gap:18px">
          <div><div class="dim mono" style="font-size:10px;text-transform:uppercase">swarm → Sunday ping</div>
            <div style="margin-top:4px"><span class="badge"><span class="dot" :class="store.status?.swarm_heartbeat_ok===false?'bad':store.status?.swarm_heartbeat_ok?'ok':''"></span>{{ store.status?.swarm_heartbeat_ok===false?'stale (>90m)':store.status?.swarm_heartbeat_ok?'recent':'—' }}</span></div></div>
          <div><div class="dim mono" style="font-size:10px;text-transform:uppercase">engine mode</div>
            <div style="margin-top:4px"><span class="tag" :class="store.status?.mode==='active'?'long':store.status?.mode==='halted'?'short':'flat'">{{ store.status?.mode || '—' }}</span></div></div>
        </div>
        <button class="btn" :disabled="hbBusy" @click="ping"><span v-if="hbBusy" class="ld"></span><Icon v-else name="heart" :size="15"/>Ping Sunday</button>
      </div>
      <div class="rationale" style="margin-top:12px">
        <b>方向：heartbeat 是 swarm → Sunday 的存活訊號</b>（leader 每 ~30m POST /heartbeat）。按這鍵 = 你代替 leader ping Sunday、<b>重置 Sunday 的 dead-man watchdog</b>，讓它不要因收不到心跳而進 safe-mode（連續 ~90m 沒心跳才會）。
        它<b>不會、也不該通知 swarm</b> —— swarm 只對 Sunday 主動發的「事件」醒來（RP-9 webhook：regime_shift / risk_breach…）。要讓 swarm 反應請用「喚醒事件」，不是 heartbeat。
      </div>
    </Panel>

    <ConfirmModal :open="confirmOpen" :busy="busy" title="套用風險封套？" confirmText="確認套用" @cancel="confirmOpen=false" @confirm="submit">
      <p>新封套將立即成為硬限額。引擎以此 gate 新倉、跑回撤熔斷。</p>
      <div class="rationale">pos ≤ {{ fmt.money(form.max_position_usd) }} · exp ≤ {{ fmt.money(form.max_total_exposure_usd) }} · lev ≤ {{ form.max_leverage }}x · dd ≤ {{ form.max_drawdown_pct }}% · stop {{ form.stop_pct }}</div>
    </ConfirmModal>
  </div>`,
};
