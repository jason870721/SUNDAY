<script setup lang="ts">
import { reactive, ref, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'
import { price, num } from '../lib/format'
import { attempt } from '../lib/toast'

const route = useRoute()
const router = useRouter()
const form = reactive({
  symbol: (((route.params.symbol as string) || 'BTCUSDT').toUpperCase()),
  side: 'buy' as 'buy' | 'sell',
  type: 'market' as 'market' | 'limit',
  sizeMode: 'notional' as 'notional' | 'qty',
  qty: null as number | null,
  notional_usd: 100 as number | null,
  price: null as number | null,
  leverage: 5 as number,
  margin_mode: 'cross' as 'cross' | 'isolated',
  take_profit: null as number | null,
  stop_loss: null as number | null,
  memo: '' as string,
})
const last = ref<number | null>(null)
const busy = ref(false)
const result = ref<Record<string, unknown> | null>(null)

async function loadPrice(): Promise<void> {
  const m = await attempt(() => api.market(form.symbol))
  last.value = (m?.ticker?.last as number) ?? null
  if (form.type === 'limit' && form.price == null) form.price = last.value
}
async function submit(): Promise<void> {
  busy.value = true
  const body: Record<string, unknown> = {
    symbol: form.symbol, side: form.side, type: form.type,
    leverage: form.leverage || undefined, margin_mode: form.margin_mode,
    take_profit: form.take_profit || undefined, stop_loss: form.stop_loss || undefined,
    memo: form.memo || undefined,
  }
  if (form.sizeMode === 'qty') body.qty = form.qty
  else body.notional_usd = form.notional_usd
  if (form.type === 'limit') body.price = form.price
  const r = await attempt(() => api.placeOrder(body), `order placed · ${form.side.toUpperCase()} ${form.symbol}`)
  if (r) result.value = r
  busy.value = false
}
watch(() => form.symbol, () => { form.symbol = form.symbol.toUpperCase(); loadPrice() })
onMounted(loadPrice)
</script>

<template>
  <div class="split" style="--aside: 420px">
    <div class="panel">
      <div class="panel-head"><h2>Order Ticket</h2><span class="tag" :class="'isolated'">testnet</span></div>
      <div class="panel-pad">
        <div class="seg" style="width: 100%; margin-bottom: 14px">
          <button style="flex:1" class="buy" :class="{ on: form.side === 'buy' }" @click="form.side = 'buy'"
            :style="form.side === 'buy' ? 'background:rgba(58,208,127,.18);color:var(--up)' : ''">Buy / Long</button>
          <button style="flex:1" :class="{ on: form.side === 'sell' }" @click="form.side = 'sell'"
            :style="form.side === 'sell' ? 'background:rgba(242,85,85,.18);color:var(--down)' : ''">Sell / Short</button>
        </div>

        <label class="field"><span>Symbol</span>
          <input v-model="form.symbol" spellcheck="false" /></label>

        <div class="row" style="margin-bottom: 12px">
          <div class="seg"><button :class="{ on: form.type === 'market' }" @click="form.type = 'market'">Market</button>
            <button :class="{ on: form.type === 'limit' }" @click="form.type = 'limit'">Limit</button></div>
          <div class="grow"></div>
          <span class="faint mono" v-if="last">mkt {{ price(last) }}</span>
        </div>

        <label v-if="form.type === 'limit'" class="field"><span>Limit price</span>
          <input v-model.number="form.price" type="number" /></label>

        <div class="row" style="margin-bottom: 6px">
          <div class="seg"><button :class="{ on: form.sizeMode === 'notional' }" @click="form.sizeMode = 'notional'">USD</button>
            <button :class="{ on: form.sizeMode === 'qty' }" @click="form.sizeMode = 'qty'">Contracts</button></div>
        </div>
        <label class="field" v-if="form.sizeMode === 'notional'"><span>Notional (USDT)</span>
          <input v-model.number="form.notional_usd" type="number" /></label>
        <label class="field" v-else><span>Quantity (contracts)</span>
          <input v-model.number="form.qty" type="number" /></label>

        <label class="field"><span>Leverage · {{ form.leverage }}×</span>
          <input v-model.number="form.leverage" type="range" min="1" max="75" step="1" /></label>

        <label class="field"><span>Margin mode</span>
          <div class="seg" style="width: 100%"><button style="flex:1" :class="{ on: form.margin_mode === 'cross' }" @click="form.margin_mode = 'cross'">Cross 全倉</button>
            <button style="flex:1" :class="{ on: form.margin_mode === 'isolated' }" @click="form.margin_mode = 'isolated'">Isolated 逐倉</button></div></label>

        <div class="grid cols-2" style="gap: 10px">
          <label class="field"><span>Take profit</span><input v-model.number="form.take_profit" type="number" placeholder="trigger" /></label>
          <label class="field"><span>Stop loss</span><input v-model.number="form.stop_loss" type="number" placeholder="trigger" /></label>
        </div>

        <label class="field"><span>Memo · why this trade ({{ form.memo.length }}/300, shown to User)</span>
          <textarea v-model="form.memo" rows="2" maxlength="300" placeholder="rationale the agent logs for this order…"></textarea></label>

        <button class="btn" :class="form.side === 'buy' ? 'buy' : 'sell'" style="width: 100%; margin-top: 6px"
          :disabled="busy" @click="submit">
          {{ busy ? 'submitting…' : `${form.side === 'buy' ? 'Buy / Long' : 'Sell / Short'} ${form.symbol}` }}
        </button>
      </div>
    </div>

    <div class="grid" style="align-content: start">
      <div class="panel panel-pad">
        <div class="row"><b>Last order</b><div class="grow"></div>
          <button class="btn sm ghost" @click="router.push('/account')">Account →</button></div>
        <pre v-if="result" class="markdown" style="margin-top: 10px"><code>{{ JSON.stringify(result, null, 2) }}</code></pre>
        <div v-else class="muted" style="margin-top: 10px; font-size: 13px">
          Submit an order to see the exchange response here. Leverage and margin mode are applied before the
          entry; take-profit / stop-loss are placed as reduce-only trigger legs.
        </div>
      </div>
    </div>
  </div>
</template>
