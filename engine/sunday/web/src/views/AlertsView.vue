<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { api, type Alert, type MonitorState, type Page } from '../api/client'
import { price, pct, num, time, sign } from '../lib/format'
import { attempt, toast } from '../lib/toast'
import Pager from '../components/Pager.vue'

const list = ref<Page<Alert> | null>(null)
const statusFilter = ref('')
const monitor = ref<MonitorState | null>(null)
const stepEdit = ref<number | null>(null)
const form = reactive({ symbol: 'BTCUSDT', kind: 'price_above', threshold: null as number | null, note: '' })
let timer: number | undefined

const KIND_LABEL: Record<string, string> = { price_above: 'Price ≥', price_below: 'Price ≤', pct_move: '±% move' }

async function loadAlerts(pg = 1): Promise<void> { list.value = (await attempt(() => api.alerts({ status: statusFilter.value, page: pg }))) ?? null }
async function loadMonitor(): Promise<void> {
  monitor.value = (await attempt(() => api.monitor())) ?? null
  if (monitor.value && stepEdit.value == null) stepEdit.value = monitor.value.config.step_pct
}
async function create(): Promise<void> {
  if (!form.threshold || form.threshold <= 0) { toast('threshold must be positive', 'err'); return }
  const r = await attempt(() => api.createAlert({ symbol: form.symbol.toUpperCase(), kind: form.kind, threshold: form.threshold, note: form.note || undefined }), 'alert armed')
  if (r) { form.threshold = null; form.note = ''; loadAlerts() }
}
async function remove(id: number): Promise<void> { await attempt(() => api.deleteAlert(id), 'alert removed'); loadAlerts(list.value?.page) }
async function saveStep(): Promise<void> { await attempt(() => api.monitorConfig({ step_pct: stepEdit.value }), 'monitor step updated'); loadMonitor() }
async function toggle(): Promise<void> { await attempt(() => api.monitorConfig({ enabled: !monitor.value?.config.enabled }), 'monitor toggled'); loadMonitor() }

onMounted(() => { loadAlerts(); loadMonitor(); timer = setInterval(() => { loadAlerts(list.value?.page); loadMonitor() }, 8000) })
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div class="split-r" style="--aside: 360px">
    <!-- alerts -->
    <div class="panel">
      <div class="panel-head"><h2>Price Alerts</h2>
        <div class="grow"></div>
        <div class="seg">
          <button :class="{ on: statusFilter === '' }" @click="statusFilter = ''; loadAlerts()">all</button>
          <button :class="{ on: statusFilter === 'active' }" @click="statusFilter = 'active'; loadAlerts()">active</button>
          <button :class="{ on: statusFilter === 'triggered' }" @click="statusFilter = 'triggered'; loadAlerts()">triggered</button>
        </div>
      </div>
      <div class="tbl-wrap">
        <table class="tbl">
          <thead><tr><th class="left">#</th><th class="left">Symbol</th><th class="left">Condition</th><th>Ref</th><th>Status</th><th>Created</th><th></th></tr></thead>
          <tbody>
            <tr v-for="a in list?.items ?? []" :key="a.id">
              <td class="left faint">{{ a.id }}</td>
              <td class="left"><b>{{ a.symbol }}</b></td>
              <td class="left">{{ KIND_LABEL[a.kind] ?? a.kind }} <b>{{ a.kind === 'pct_move' ? a.threshold + '%' : num(a.threshold, 2) }}</b></td>
              <td class="faint">{{ a.ref_price ? price(a.ref_price) : '—' }}</td>
              <td><span class="tag" :class="a.status === 'active' ? 'long' : ''">{{ a.status }}</span></td>
              <td class="faint">{{ time(Date.parse(a.created_at)) }}</td>
              <td><button class="btn sm ghost" @click="remove(a.id)">✕</button></td>
            </tr>
            <tr v-if="(list?.items.length ?? 0) === 0"><td colspan="7" class="empty">no alerts</td></tr>
          </tbody>
        </table>
      </div>
      <Pager v-if="list" :page="list.page" :page-size="list.page_size" :total="list.total" :has-more="list.has_more" @go="loadAlerts" />
    </div>

    <div class="grid" style="align-content: start">
      <!-- new alert -->
      <div class="panel panel-pad">
        <b>New Alert</b>
        <label class="field" style="margin-top: 12px"><span>Symbol</span><input v-model="form.symbol" spellcheck="false" /></label>
        <label class="field"><span>Condition</span>
          <select v-model="form.kind">
            <option value="price_above">Price rises above</option>
            <option value="price_below">Price falls below</option>
            <option value="pct_move">Moves ±% from now</option>
          </select></label>
        <label class="field"><span>{{ form.kind === 'pct_move' ? 'Percent (%)' : 'Price' }}</span>
          <input v-model.number="form.threshold" type="number" /></label>
        <label class="field"><span>Note (optional)</span><input v-model="form.note" /></label>
        <button class="btn accent" style="width: 100%" @click="create">Arm alert</button>
        <p class="faint" style="font-size: 11px; margin: 10px 0 0">Fires once → webhook to the evva swarm.</p>
      </div>

      <!-- monitor -->
      <div class="panel panel-pad">
        <div class="row"><b>Position Monitor</b><div class="grow"></div>
          <span class="pill"><i class="dot" :class="monitor?.config.enabled ? 'ok' : 'bad'"></i>{{ monitor?.config.enabled ? 'on' : 'off' }}</span>
        </div>
        <p class="faint" style="font-size: 12px; margin: 8px 0 12px">Webhooks the swarm whenever an open position's ROI crosses a step.</p>
        <div class="row" style="margin-bottom: 12px">
          <label class="field" style="margin: 0; flex: 1"><span>Step %</span>
            <input v-model.number="stepEdit" type="number" step="1" @keyup.enter="saveStep" /></label>
          <button class="btn sm" style="margin-top: 18px" @click="saveStep">save</button>
          <button class="btn sm ghost" style="margin-top: 18px" @click="toggle">{{ monitor?.config.enabled ? 'disable' : 'enable' }}</button>
        </div>
        <div class="tbl-wrap">
          <table class="tbl">
            <thead><tr><th class="left">Symbol</th><th>Side</th><th>ROI%</th><th>Step</th></tr></thead>
            <tbody>
              <tr v-for="p in monitor?.positions ?? []" :key="p.symbol">
                <td class="left"><b>{{ p.symbol }}</b></td>
                <td><span class="tag" :class="p.side">{{ p.side }}</span></td>
                <td :class="sign(p.roi_pct)">{{ pct(p.roi_pct) }}</td>
                <td class="faint">{{ p.bucket }}</td>
              </tr>
              <tr v-if="(monitor?.positions.length ?? 0) === 0"><td colspan="4" class="empty">no positions watched</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>
