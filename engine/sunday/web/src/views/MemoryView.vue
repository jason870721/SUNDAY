<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api, type MemoryDoc, type MemoryIndexItem } from '../api/client'
import { time, ago } from '../lib/format'
import { attempt } from '../lib/toast'
import { renderMarkdown } from '../lib/md'

const agents = ref<MemoryIndexItem[]>([])
const selected = ref<string | null>(null)
const doc = ref<MemoryDoc | null>(null)
const loadingDoc = ref(false)

async function loadIndex(): Promise<void> {
  const r = await attempt(() => api.memoryIndex())
  agents.value = r?.items ?? []
  if (agents.value.length && !selected.value) select(agents.value[0].agent)
}
async function select(agent: string): Promise<void> {
  selected.value = agent
  loadingDoc.value = true
  doc.value = (await attempt(() => api.memory(agent))) ?? null
  loadingDoc.value = false
}

onMounted(loadIndex)
</script>

<template>
  <div class="split" style="--aside: 300px">
    <!-- agent list -->
    <div class="panel">
      <div class="panel-head"><h2>Agents</h2><div class="grow"></div>
        <button class="btn sm ghost" @click="loadIndex" title="refresh">↻</button></div>
      <div class="tbl-wrap">
        <table class="tbl">
          <thead><tr><th class="left">Agent</th><th>Updated</th></tr></thead>
          <tbody>
            <tr v-for="a in agents" :key="a.agent" class="clickable" @click="select(a.agent)"
              :style="selected === a.agent ? 'background: var(--gold-tint)' : ''">
              <td class="left"><b>{{ a.agent }}</b></td>
              <td class="faint" :title="a.updated_at ? time(Date.parse(a.updated_at)) : 'no memory yet'">
                {{ a.updated_at ? ago(Date.parse(a.updated_at)) : '—' }}</td>
            </tr>
            <tr v-if="agents.length === 0"><td colspan="2" class="empty">no agents</td></tr>
          </tbody>
        </table>
      </div>
      <div class="panel-pad faint" style="font-size: 11px; border-top: 1px solid var(--border-soft)">
        每個 agent 的長期記憶（取代 MEMORY.md / RESEARCH.md）。醒來時讀、收工時寫回。
      </div>
    </div>

    <!-- selected memory doc -->
    <div class="panel panel-pad">
      <template v-if="selected">
        <div class="row"><h2 style="margin: 0">{{ selected }}</h2><div class="grow"></div>
          <span v-if="doc?.updated_at" class="pill faint">updated {{ time(Date.parse(doc.updated_at)) }}</span>
          <span v-else class="pill faint">no memory yet</span>
        </div>
        <div v-if="loadingDoc" class="loading"><span class="spinner"></span>loading…</div>
        <div v-else-if="doc && doc.content.trim()" class="markdown" style="margin-top: 14px"
          v-html="renderMarkdown(doc.content)"></div>
        <div v-else class="muted" style="margin-top: 14px; font-size: 13px">
          <b>{{ selected }}</b> 還沒寫過記憶。它下次醒來、收工前會用 <code>PUT /api/memory/{{ selected }}</code> 建立。
        </div>
      </template>
      <div v-else class="muted" style="font-size: 13px">選一個 agent 看它的長期記憶。</div>
    </div>
  </div>
</template>
