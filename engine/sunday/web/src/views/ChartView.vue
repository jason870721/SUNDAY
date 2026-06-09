<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createChart, ColorType, type IChartApi, type ISeriesApi, type UTCTimestamp } from 'lightweight-charts'
import { api, type Funding } from '../api/client'
import { price, pct, num } from '../lib/format'
import { attempt } from '../lib/toast'

const route = useRoute()
const router = useRouter()
const symbol = ref(((route.params.symbol as string) || 'BTCUSDT').toUpperCase())
const interval = ref('1h')
const INTERVALS = ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w']

const chartEl = ref<HTMLDivElement>()
let chart: IChartApi | null = null
let candle: ISeriesApi<'Candlestick'> | null = null

const funding = ref<Funding | null>(null)
const ind = ref<Record<string, any> | null>(null)
const lastClose = ref<number | null>(null)

async function loadChart(): Promise<void> {
  const r = await attempt(() => api.klines({ symbol: symbol.value, interval: interval.value, limit: 400 }))
  if (r && candle) {
    candle.setData(r.ohlcv.map((k) => ({ time: Math.floor(k[0] / 1000) as UTCTimestamp, open: k[1], high: k[2], low: k[3], close: k[4] })))
    chart?.timeScale().fitContent()
    lastClose.value = r.ohlcv.length ? r.ohlcv[r.ohlcv.length - 1][4] : null
  }
}
async function loadMeta(): Promise<void> {
  funding.value = (await attempt(() => api.funding(symbol.value))) ?? null
  const i = await attempt(() => api.indicators({ symbol: symbol.value, interval: interval.value }))
  ind.value = (i?.indicators as Record<string, any>) ?? null
}
function reload(): void { loadChart(); loadMeta() }
function setSymbol(): void {
  const s = symbol.value.toUpperCase().trim()
  if (!s) return
  symbol.value = s
  router.replace(`/chart/${s}`)
  reload()
}
watch(interval, reload)

onMounted(() => {
  chart = createChart(chartEl.value!, {
    autoSize: true,
    layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: '#8a93a6', fontFamily: 'monospace' },
    grid: { vertLines: { color: '#161a23' }, horzLines: { color: '#161a23' } },
    timeScale: { borderColor: '#232a36', timeVisible: true },
    rightPriceScale: { borderColor: '#232a36' },
    crosshair: { mode: 0 },
  })
  candle = chart.addCandlestickSeries({
    upColor: '#3fb950', downColor: '#f85149', borderVisible: false,
    wickUpColor: '#3fb950', wickDownColor: '#f85149',
  })
  reload()
})
onUnmounted(() => chart?.remove())
</script>

<template>
  <div class="grid" style="grid-template-columns: 1fr 280px">
    <div class="panel">
      <div class="panel-head">
        <input v-model="symbol" @keyup.enter="setSymbol" style="width: 140px; font-weight: 600"
          spellcheck="false" />
        <button class="btn sm" @click="setSymbol">load</button>
        <div class="seg">
          <button v-for="iv in INTERVALS" :key="iv" :class="{ on: interval === iv }" @click="interval = iv">{{ iv }}</button>
        </div>
        <div class="grow"></div>
        <span v-if="lastClose" class="mono" style="font-size: 16px">{{ price(lastClose) }}</span>
        <button class="btn sm accent" @click="router.push(`/trade/${symbol}`)">Trade →</button>
      </div>
      <div ref="chartEl" style="height: 460px"></div>
    </div>

    <div class="grid" style="align-content: start">
      <div class="panel panel-pad">
        <div class="row"><b>Funding</b><div class="grow"></div>
          <span class="pill" v-if="funding" :class="(funding.rate ?? 0) >= 0 ? 'up' : 'down'">
            {{ pct((funding.rate ?? 0) * 100, 4) }} / {{ funding.interval_hours ?? 8 }}h</span>
        </div>
        <div class="muted" style="margin-top: 8px; font-size: 12px" v-if="funding">
          mark {{ price(funding.mark) }} · index {{ price(funding.index) }}<br />
          <span class="faint" v-if="funding.next_funding_ts">next · {{ new Date(funding.next_funding_ts).toLocaleString() }}</span>
        </div>
      </div>

      <div class="panel panel-pad">
        <b>Indicators</b>
        <div v-if="ind" class="grid cols-2" style="margin-top: 10px; gap: 8px">
          <div class="stat" style="padding: 8px 10px" v-if="ind.rsi != null">
            <div class="label">RSI 14</div><div class="value" style="font-size: 16px">{{ num(ind.rsi, 1) }}</div></div>
          <div class="stat" style="padding: 8px 10px" v-if="ind.adx != null">
            <div class="label">ADX</div><div class="value" style="font-size: 16px">{{ num(ind.adx, 1) }}</div></div>
          <div class="stat" style="padding: 8px 10px" v-if="ind.ema">
            <div class="label">EMA 20 / 50</div><div class="value" style="font-size: 13px">{{ num(ind.ema.ema20) }}<br />{{ num(ind.ema.ema50) }}</div></div>
          <div class="stat" style="padding: 8px 10px" v-if="ind.macd">
            <div class="label">MACD hist</div><div class="value" style="font-size: 16px" :class="ind.macd.hist >= 0 ? 'up' : 'down'">{{ num(ind.macd.hist, 2) }}</div></div>
          <div class="stat" style="padding: 8px 10px" v-if="ind.bollinger">
            <div class="label">BOLL z</div><div class="value" style="font-size: 16px">{{ num(ind.bollinger.z, 2) }}</div></div>
          <div class="stat" style="padding: 8px 10px" v-if="ind.atr != null">
            <div class="label">ATR 14</div><div class="value" style="font-size: 16px">{{ num(ind.atr) }}</div></div>
        </div>
        <div v-else class="loading"><span class="spinner"></span></div>
      </div>
    </div>
  </div>
</template>
