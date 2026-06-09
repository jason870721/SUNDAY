import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'

export const NAV = [
  { path: '/markets', title: 'Markets', icon: '▤' },
  { path: '/chart', title: 'Chart', icon: '◫' },
  { path: '/trade', title: 'Trade', icon: '⊹' },
  { path: '/account', title: 'Account', icon: '▦' },
  { path: '/indices', title: 'Indices', icon: '◴' },
  { path: '/alerts', title: 'Alerts', icon: '◆' },
  { path: '/manual', title: 'Manual', icon: '❯' },
]

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/markets' },
  { path: '/markets', component: () => import('./views/MarketsView.vue') },
  { path: '/chart/:symbol?', component: () => import('./views/ChartView.vue') },
  { path: '/trade/:symbol?', component: () => import('./views/TradeView.vue') },
  { path: '/account', component: () => import('./views/AccountView.vue') },
  { path: '/indices', component: () => import('./views/IndicesView.vue') },
  { path: '/alerts', component: () => import('./views/AlertsView.vue') },
  { path: '/manual', component: () => import('./views/ManualView.vue') },
]

export const router = createRouter({ history: createWebHashHistory(), routes })
