<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { api, type Position, type Order, type Trade, type Page } from '../api/client'
import { price, pct, usd, num, sign, time } from '../lib/format'
import { attempt } from '../lib/toast'
import Pager from '../components/Pager.vue'

type Tab = 'positions' | 'open' | 'orders' | 'trades'
const tab = ref<Tab>('positions')
const balance = ref<{ equity: number | null; free: number | null; used: number | null } | null>(null)
const positions = ref<Position[]>([])
const unrealized = ref(0)
const open = ref<Page<Order> | null>(null)
const orders = ref<Page<Order> | null>(null)
const trades = ref<Page<Trade> | null>(null)
const histSymbol = ref('BTCUSDT')
let timer: number | undefined

async function loadAll(): Promise<void> {
  balance.value = (await attempt(() => api.balance())) ?? null
  const p = await attempt(() => api.pnl())
  if (p) { positions.value = p.positions; unrealized.value = p.unrealized_pnl }
}
async function loadOpen(pg = 1): Promise<void> { open.value = (await attempt(() => api.openOrders({ page: pg }))) ?? null }
async function loadOrders(pg = 1): Promise<void> { orders.value = (await attempt(() => api.orderHistory({ symbol: histSymbol.value, page: pg }))) ?? null }
async function loadTrades(pg = 1): Promise<void> { trades.value = (await attempt(() => api.trades({ symbol: histSymbol.value, page: pg }))) ?? null }
function go(t: Tab): void {
  tab.value = t
  if (t === 'open' && !open.value) loadOpen()
  if (t === 'orders' && !orders.value) loadOrders()
  if (t === 'trades' && !trades.value) loadTrades()
}
async function closePos(sym: string): Promise<void> { if (await attempt(() => api.closePosition(sym), `closed ${sym}`)) loadAll() }
async function cancel(o: Order): Promise<void> { await attempt(() => api.cancelOrder(o.id, o.symbol), 'order cancelled'); loadOpen(open.value?.page) }

onMounted(() => { loadAll(); timer = setInterval(() => { loadAll(); if (tab.value === 'open') loadOpen(open.value?.page) }, 8000) })
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div class="grid cols-4" style="margin-bottom: 14px">
    <div class="panel stat"><div class="label">Equity (USDT)</div><div class="value">{{ usd(balance?.equity) }}</div></div>
    <div class="panel stat"><div class="label">Free margin</div><div class="value">{{ usd(balance?.free) }}</div></div>
    <div class="panel stat"><div class="label">Used margin</div><div class="value">{{ usd(balance?.used) }}</div></div>
    <div class="panel stat"><div class="label">Unrealized PnL</div><div class="value" :class="sign(unrealized)">{{ usd(unrealized) }}</div></div>
  </div>

  <div class="panel">
    <div class="panel-head">
      <div class="seg">
        <button :class="{ on: tab === 'positions' }" @click="go('positions')">Positions</button>
        <button :class="{ on: tab === 'open' }" @click="go('open')">Open Orders</button>
        <button :class="{ on: tab === 'orders' }" @click="go('orders')">Order History</button>
        <button :class="{ on: tab === 'trades' }" @click="go('trades')">Trades</button>
      </div>
      <div class="grow"></div>
      <template v-if="tab === 'orders' || tab === 'trades'">
        <input v-model="histSymbol" style="width: 130px" spellcheck="false"
          @keyup.enter="tab === 'orders' ? loadOrders() : loadTrades()" />
        <button class="btn sm" @click="tab === 'orders' ? loadOrders() : loadTrades()">load</button>
      </template>
    </div>

    <div style="overflow: auto">
      <!-- positions -->
      <table v-if="tab === 'positions'" class="tbl">
        <thead><tr><th class="left">Symbol</th><th>Side</th><th>Qty</th><th>Entry</th><th>Mark</th><th>Lev</th><th>uPnL</th><th>ROI%</th><th>Liq</th><th></th></tr></thead>
        <tbody>
          <tr v-for="p in positions" :key="p.symbol">
            <td class="left"><b>{{ p.symbol }}</b></td>
            <td><span class="tag" :class="p.side">{{ p.side }}</span></td>
            <td>{{ num(p.qty, 4) }}</td><td>{{ price(p.entry) }}</td><td>{{ price(p.mark) }}</td>
            <td class="faint">{{ num(p.leverage, 0) }}×</td>
            <td :class="sign(p.unrealized_pnl)">{{ usd(p.unrealized_pnl) }}</td>
            <td :class="sign(p.roi_pct)">{{ pct(p.roi_pct) }}</td>
            <td class="faint">{{ price(p.liquidation_price) }}</td>
            <td><button class="btn sm ghost" @click="closePos(p.symbol)">close</button></td>
          </tr>
          <tr v-if="positions.length === 0"><td colspan="10" class="empty">no open positions</td></tr>
        </tbody>
      </table>

      <!-- open orders -->
      <table v-else-if="tab === 'open'" class="tbl">
        <thead><tr><th class="left">Symbol</th><th>Type</th><th>Side</th><th>Price</th><th>Amount</th><th>Filled</th><th>Trigger</th><th>Status</th><th></th></tr></thead>
        <tbody>
          <tr v-for="o in open?.items ?? []" :key="o.id">
            <td class="left"><b>{{ o.symbol }}</b></td><td class="faint">{{ o.type }}</td>
            <td><span class="tag" :class="o.side">{{ o.side }}</span></td>
            <td>{{ price(o.price) }}</td><td>{{ num(o.amount, 4) }}</td><td>{{ num(o.filled, 4) }}</td>
            <td class="faint">{{ price(o.trigger_price) }}</td><td class="faint">{{ o.status }}</td>
            <td><button class="btn sm ghost" @click="cancel(o)">cancel</button></td>
          </tr>
          <tr v-if="(open?.items.length ?? 0) === 0"><td colspan="9" class="empty">no open orders</td></tr>
        </tbody>
      </table>

      <!-- order history -->
      <table v-else-if="tab === 'orders'" class="tbl">
        <thead><tr><th class="left">Time</th><th>Type</th><th>Side</th><th>Price</th><th>Amount</th><th>Filled</th><th>Status</th></tr></thead>
        <tbody>
          <tr v-for="o in orders?.items ?? []" :key="o.id">
            <td class="left faint">{{ time(o.ts) }}</td><td class="faint">{{ o.type }}</td>
            <td><span class="tag" :class="o.side">{{ o.side }}</span></td>
            <td>{{ price(o.price) }}</td><td>{{ num(o.amount, 4) }}</td><td>{{ num(o.filled, 4) }}</td>
            <td class="faint">{{ o.status }}</td>
          </tr>
          <tr v-if="(orders?.items.length ?? 0) === 0"><td colspan="7" class="empty">no orders for {{ histSymbol }}</td></tr>
        </tbody>
      </table>

      <!-- trades -->
      <table v-else class="tbl">
        <thead><tr><th class="left">Time</th><th>Side</th><th>Price</th><th>Amount</th><th>Fee</th><th>Realized PnL</th></tr></thead>
        <tbody>
          <tr v-for="t in trades?.items ?? []" :key="t.id">
            <td class="left faint">{{ time(t.ts) }}</td>
            <td><span class="tag" :class="t.side">{{ t.side }}</span></td>
            <td>{{ price(t.price) }}</td><td>{{ num(t.amount, 4) }}</td><td class="faint">{{ num(t.fee, 4) }}</td>
            <td :class="sign(t.realized_pnl)">{{ t.realized_pnl == null ? '—' : usd(t.realized_pnl) }}</td>
          </tr>
          <tr v-if="(trades?.items.length ?? 0) === 0"><td colspan="6" class="empty">no trades for {{ histSymbol }}</td></tr>
        </tbody>
      </table>
    </div>

    <Pager v-if="tab === 'open' && open" :page="open.page" :page-size="open.page_size" :total="open.total" :has-more="open.has_more" @go="loadOpen" />
    <Pager v-else-if="tab === 'orders' && orders" :page="orders.page" :page-size="orders.page_size" :total="orders.total" :has-more="orders.has_more" @go="loadOrders" />
    <Pager v-else-if="tab === 'trades' && trades" :page="trades.page" :page-size="trades.page_size" :total="trades.total" :has-more="trades.has_more" @go="loadTrades" />
  </div>
</template>
