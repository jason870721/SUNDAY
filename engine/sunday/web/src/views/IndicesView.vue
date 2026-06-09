<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { api, type IndexRow } from '../api/client'
import { num, pct, sign, ago } from '../lib/format'
import { attempt } from '../lib/toast'

const items = ref<IndexRow[]>([])
const loading = ref(true)
let timer: number | undefined

async function load(): Promise<void> {
  const r = await attempt(() => api.indices())
  if (r) items.value = r.items
  loading.value = false
}
function bigValue(it: IndexRow): string {
  if (it.value != null) return num(it.value, it.key === 'fear-greed' ? 0 : 2)
  if (it.price != null) return num(it.price, 2)
  return '—'
}
function fgColor(v?: number): string {
  if (v == null) return 'var(--muted)'
  if (v >= 75) return 'var(--up)'
  if (v >= 55) return '#8fce4f'
  if (v >= 45) return 'var(--accent)'
  if (v >= 25) return '#f0883e'
  return 'var(--down)'
}
onMounted(() => { load(); timer = setInterval(load, 60000) })
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div v-if="loading" class="loading"><span class="spinner"></span> loading indices…</div>
  <div v-else class="grid cols-4">
    <div v-for="it in items" :key="it.key" class="panel panel-pad">
      <div class="row"><span class="muted" style="font-size: 12px">{{ it.label }}</span>
        <div class="grow"></div>
        <span class="tag">{{ it.group }}</span></div>

      <div class="value mono" style="font-size: 26px; margin: 10px 0 2px"
        :style="it.key === 'fear-greed' ? `color:${fgColor(it.value)}` : ''">{{ bigValue(it) }}</div>

      <div v-if="it.key === 'fear-greed'">
        <div class="gauge" style="margin: 6px 0"><i :style="`width:${it.value ?? 0}%; background:${fgColor(it.value)}`"></i></div>
        <span class="faint" style="font-size: 12px">{{ it.classification ?? '—' }}</span>
      </div>
      <div v-else-if="it.change_pct != null" :class="sign(it.change_pct)" class="mono" style="font-size: 13px">{{ pct(it.change_pct) }}</div>
      <div v-else class="faint mono" style="font-size: 12px" v-if="it.total_market_cap_usd">mcap ${{ num(it.total_market_cap_usd / 1e12, 2) }}T</div>

      <div class="faint" style="font-size: 10px; margin-top: 10px; font-family: var(--mono)">
        <span v-if="!it.available" class="down">unavailable</span>
        <template v-else>{{ it.source ?? 'live' }}<span v-if="it.stale"> · stale</span><span v-if="it.as_of"> · {{ ago(it.as_of) }}</span></template>
      </div>
    </div>
  </div>
</template>
