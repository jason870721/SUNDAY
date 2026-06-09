<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { NAV } from './router'
import { fetchHealth } from './api/client'
import { useToasts } from './lib/toast'

const route = useRoute()
const toasts = useToasts()
const health = ref<{ ok: boolean; version: string } | null>(null)
const navOpen = ref(false)   // mobile drawer

function title(): string {
  return NAV.find((n) => route.path.startsWith(n.path))?.title ?? 'Sunday'
}
async function poll(): Promise<void> {
  try { health.value = await fetchHealth() } catch { health.value = null }
}
watch(() => route.path, () => { navOpen.value = false })   // close the drawer on navigation
onMounted(() => { poll(); setInterval(poll, 15000) })
</script>

<template>
  <div class="shell">
    <div v-if="navOpen" class="nav-backdrop" @click="navOpen = false"></div>
    <aside class="sidebar" :class="{ open: navOpen }">
      <div class="brand">
        <span class="mark">☀</span>
        <div><b>Sunday</b><br /><small>agent exchange</small></div>
      </div>
      <router-link v-for="n in NAV" :key="n.path" :to="n.path" class="nav-link"
        :class="{ active: route.path.startsWith(n.path) }">
        <span class="ic">{{ n.icon }}</span>{{ n.title }}
      </router-link>
      <div class="spacer"></div>
      <div class="foot">
        Binance USDⓈ-M<br />
        <span class="faint">data · mainnet</span><br />
        <span class="faint">trade · testnet</span>
      </div>
    </aside>

    <main class="main">
      <header class="topbar">
        <button class="hamburger" aria-label="menu" @click="navOpen = !navOpen">☰</button>
        <h1>{{ title() }}</h1>
        <div class="grow"></div>
        <span class="pill"><i class="dot" :class="health?.ok ? 'ok' : 'bad'"></i>
          {{ health?.ok ? 'engine online' : 'offline' }}</span>
        <span v-if="health" class="pill faint">v{{ health.version }}</span>
      </header>
      <div class="content"><router-view /></div>
    </main>

    <div class="toast">
      <div v-for="t in toasts.items" :key="t.id" class="msg" :class="t.kind">{{ t.text }}</div>
    </div>
  </div>
</template>
