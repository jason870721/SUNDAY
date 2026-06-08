// Desk — the research panel: the basket's notable ranking (funding/OI/basis), the
// active theses, and the thesis lever (POST /thesis) so the User can operate the
// desk exactly as friday does (set_by:user). The directed mode turns a thesis into
// a deterministically-sized position.
import { ref, reactive, onMounted, onBeforeUnmount, computed } from '../vue.js';
import { api } from '../api.js';
import { lever, toast } from '../store.js';
import * as fmt from '../format.js';
import { Panel, Empty, ConfirmModal, Icon } from '../components.js';

const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'];
const DIRS = ['long', 'short', 'flat'];

export default {
  components: { Panel, Empty, ConfirmModal, Icon },
  setup() {
    const d = reactive({ basket: [], theses: [], loaded: false });
    const form = reactive({ symbol: 'BTCUSDT', direction: 'long', conviction: 0.4, rationale: '', invalidation: '', invalidation_price: '' });
    const confirmOpen = ref(false);
    const busy = ref(false);
    let timer = null;

    async function load() {
      const [desk, theses] = await Promise.all([api.desk().catch(() => ({ basket: [] })), api.theses(50).catch(() => [])]);
      d.basket = desk.basket || [];
      d.theses = theses;
      d.loaded = true;
    }
    onMounted(() => { load(); timer = setInterval(load, 20000); });
    onBeforeUnmount(() => clearInterval(timer));

    const activeTheses = computed(() => d.theses.filter((t) => t.status === 'active'));
    const thesisFor = (sym) => activeTheses.value.find((t) => t.symbol === sym);

    function review() {
      if (!form.rationale.trim()) { toast('rationale 必填', 'error'); return; }
      const c = Number(form.conviction);
      if (!(c >= 0 && c <= 1)) { toast('conviction 需在 0..1', 'error'); return; }
      confirmOpen.value = true;
    }
    async function submit() {
      busy.value = true;
      const body = { symbol: form.symbol, direction: form.direction, conviction: Number(form.conviction), rationale: form.rationale };
      if (form.invalidation) body.invalidation = form.invalidation;
      if (form.invalidation_price) body.invalidation_price = Number(form.invalidation_price);
      const r = await lever(() => api.setThesis(body), `thesis 已下：${form.symbol} ${form.direction}@${form.conviction}`);
      busy.value = false;
      if (r) { confirmOpen.value = false; form.rationale = ''; form.invalidation = ''; form.invalidation_price = ''; load(); }
    }

    return { d, fmt, form, confirmOpen, busy, activeTheses, thesisFor, SYMBOLS, DIRS, review, submit };
  },
  template: `
  <div class="view">
    <div class="view-head"><h1>Desk</h1><span class="sub">研究台 · 此刻看哪裡 + thesis lever</span></div>

    <Panel title="Basket · GET /desk" hint="notable 排序：funding / OI Δ / 基差" flush>
      <table class="tbl" v-if="d.basket.length">
        <thead><tr><th>Symbol</th><th class="n">Funding %/yr</th><th class="n">OI</th><th class="n">OIΔ%</th><th class="n">Basis bps</th><th class="n">Notable</th><th>Driver</th><th>Info</th><th>Active thesis</th></tr></thead>
        <tbody><tr v-for="r in d.basket" :key="r.symbol">
          <td>{{ r.symbol }}</td>
          <td class="n" :class="fmt.signClass(r.funding_annual_pct)">{{ fmt.num(r.funding_annual_pct,1) }}</td>
          <td class="n">{{ fmt.compact(r.open_interest) }}</td>
          <td class="n" :class="fmt.signClass(r.oi_change_pct)">{{ fmt.num(r.oi_change_pct,1) }}</td>
          <td class="n">{{ fmt.num(r.basis_bps,1) }}</td>
          <td class="n"><span :class="r.notable>=0.5?'warn':''">{{ fmt.num(r.notable,2) }}</span></td>
          <td><span v-if="r.driver" class="tag" :class="r.notable>=0.5?'short':'flat'">{{ r.driver }}</span><span v-else class="dim">—</span></td>
          <td><span class="tag" :class="r.info_mode==='off'?'flat':'mom'">{{ r.info_mode }}</span></td>
          <td><span v-if="thesisFor(r.symbol)" class="tag" :class="thesisFor(r.symbol).direction">{{ thesisFor(r.symbol).direction }}@{{ fmt.num(thesisFor(r.symbol).conviction,2) }}</span><span v-else class="dim">—</span></td>
        </tr></tbody>
      </table>
      <Empty v-else>資訊層尚無資料（watcher tick 跑一輪後出現）。</Empty>
    </Panel>

    <div class="grid cols-2">
      <Panel title="下 thesis · POST /thesis">
        <div class="field"><label>Symbol</label>
          <div class="seg"><button v-for="s in SYMBOLS" :key="s" :class="{on: form.symbol===s}" @click="form.symbol=s">{{ s.replace('USDT','') }}</button></div>
        </div>
        <div class="field" style="margin-top:12px"><label>Direction</label>
          <div class="seg"><button v-for="dir in DIRS" :key="dir" :class="{on: form.direction===dir}" @click="form.direction=dir">{{ dir }}</button></div>
        </div>
        <div class="grid cols-2" style="gap:12px;margin-top:12px">
          <div class="field"><label>Conviction (0..1)</label><input class="input" type="number" min="0" max="1" step="0.05" v-model="form.conviction"></div>
          <div class="field"><label>Invalidation price（選填→stop）</label><input class="input" type="number" v-model="form.invalidation_price"></div>
        </div>
        <div class="field" style="margin-top:12px"><label>Invalidation（失效條件，選填）</label><input class="input" v-model="form.invalidation" placeholder="什麼條件這個 thesis 就錯了"></div>
        <div class="field" style="margin-top:12px"><label>Rationale（必填）</label><textarea class="input" v-model="form.rationale" placeholder="為何：funding/事件/敘事依據"></textarea></div>
        <div class="flexrow" style="margin-top:12px;justify-content:space-between">
          <span class="hint-row">conviction × 單筆上限 = 倉位（封套內，&lt;0.2 視為 flat）。directed 模式確定性執行。set_by=user。</span>
          <button class="btn primary" @click="review"><Icon name="radar" :size="15"/>下 thesis</button>
        </div>
      </Panel>

      <Panel title="Active theses" flush hint="GET /theses">
        <table class="tbl" v-if="activeTheses.length">
          <thead><tr><th>Symbol</th><th>Dir</th><th class="n">Conv</th><th>Rationale</th></tr></thead>
          <tbody><tr v-for="t in activeTheses" :key="t.id">
            <td>{{ t.symbol }}</td><td><span class="tag" :class="t.direction">{{ t.direction }}</span></td>
            <td class="n">{{ fmt.num(t.conviction,2) }}</td>
            <td class="tiny dim">{{ t.rationale }}</td>
          </tr></tbody>
        </table>
        <Empty v-else>無 active thesis。下一個 thesis 即由 directed 模式接管執行。</Empty>
      </Panel>
    </div>

    <ConfirmModal :open="confirmOpen" :busy="busy" title="下 thesis？" confirmText="確認下單" @cancel="confirmOpen=false" @confirm="submit">
      <p>Sunday 的 directed 模式會依此確定性建倉/管理。過大或超曝險會被風控擋（409）。</p>
      <div class="rationale">{{ form.symbol }} · {{ form.direction }} · conviction {{ form.conviction }}<span v-if="form.invalidation_price"> · stop {{ form.invalidation_price }}</span></div>
    </ConfirmModal>
  </div>`,
};
