<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api, type Market, type Page } from '../api/client'
import { price, pct, compact, sign } from '../lib/format'
import { attempt } from '../lib/toast'
import Pager from '../components/Pager.vue'

const router = useRouter()
const data = ref<Page<Market> | null>(null)
const loading = ref(false)
const symbol = ref('')
const sort = ref('volume')
const order = ref<'desc' | 'asc'>('desc')
const page = ref(1)
let timer: number | undefined

const COLS: Array<{ key: string; label: string; sort?: string }> = [
  { key: 'symbol', label: 'Symbol', sort: 'symbol' },
  { key: 'last', label: 'Last', sort: 'last' },
  { key: 'change', label: '24h %', sort: 'change' },
  { key: 'high', label: '24h High' },
  { key: 'low', label: '24h Low' },
  { key: 'vol', label: 'Volume', sort: 'volume' },
]

async function load(): Promise<void> {
  loading.value = true
  const r = await attempt(() => api.markets({ symbol: symbol.value, sort: sort.value, order: order.value, page: page.value, page_size: 25 }))
  if (r) data.value = r
  loading.value = false
}
function setSort(col: string): void {
  if (sort.value === col) order.value = order.value === 'desc' ? 'asc' : 'desc'
  else { sort.value = col; order.value = 'desc' }
  page.value = 1; load()
}
function go(p: number): void { page.value = p; load() }
let debounce: number | undefined
watch(symbol, () => { clearTimeout(debounce); debounce = setTimeout(() => { page.value = 1; load() }, 250) })
onMounted(() => { load(); timer = setInterval(load, 10000) })
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div class="panel">
    <div class="panel-head">
      <h2>Tradeable Markets</h2>
      <span class="faint">USDⓈ-M perpetuals · mainnet</span>
      <div class="grow"></div>
      <input v-model="symbol" placeholder="filter symbol…" style="width: 200px" />
    </div>
    <div style="overflow:auto; max-height: calc(100vh - 230px)">
      <table class="tbl">
        <thead>
          <tr>
            <th v-for="(c, i) in COLS" :key="c.key" :class="[i === 0 ? 'left' : '', c.sort ? 'sortable' : '']"
              @click="c.sort && setSort(c.sort)">
              {{ c.label }}
              <span v-if="c.sort === sort">{{ order === 'desc' ? '▼' : '▲' }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="m in data?.items ?? []" :key="m.symbol" class="clickable" @click="router.push(`/chart/${m.symbol}`)">
            <td class="left"><b>{{ m.symbol }}</b></td>
            <td>{{ price(m.last) }}</td>
            <td :class="sign(m.change_pct)">{{ pct(m.change_pct) }}</td>
            <td class="faint">{{ price(m.high) }}</td>
            <td class="faint">{{ price(m.low) }}</td>
            <td>{{ compact(m.quote_volume) }}</td>
          </tr>
          <tr v-if="!loading && (data?.items.length ?? 0) === 0">
            <td colspan="6" class="empty">no markets match “{{ symbol }}”</td>
          </tr>
        </tbody>
      </table>
    </div>
    <Pager v-if="data" :page="data.page" :page-size="data.page_size" :total="data.total" :has-more="data.has_more" @go="go" />
  </div>
</template>
