<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api, type JournalEntry, type Page } from '../api/client'
import { time } from '../lib/format'
import { attempt } from '../lib/toast'
import { renderMarkdown } from '../lib/md'
import Pager from '../components/Pager.vue'

const list = ref<Page<JournalEntry> | null>(null)
const selected = ref<JournalEntry | null>(null)

async function load(pg = 1): Promise<void> {
  list.value = (await attempt(() => api.journal({ page: pg }))) ?? null
  const items = list.value?.items ?? []
  // keep the current selection if it's still on the page, else select the newest.
  if (items.length && (!selected.value || !items.some((e) => e.id === selected.value!.id)))
    selected.value = items[0]
}

onMounted(() => load())
</script>

<template>
  <div class="grid" style="grid-template-columns: 320px 1fr; align-items: start">
    <!-- entry list -->
    <div class="panel">
      <div class="panel-head"><h2>Work Log</h2><div class="grow"></div><span class="faint">reviewer · 每日</span></div>
      <table class="tbl">
        <thead><tr><th class="left">Date</th><th class="left">Title</th><th>By</th></tr></thead>
        <tbody>
          <tr v-for="e in list?.items ?? []" :key="e.id" class="clickable" @click="selected = e"
            :style="selected?.id === e.id ? 'background: var(--panel-3)' : ''">
            <td class="left faint">{{ e.date ?? time(Date.parse(e.ts)) }}</td>
            <td class="left">{{ e.title || '(untitled)' }}</td>
            <td class="faint">{{ e.author }}</td>
          </tr>
          <tr v-if="(list?.items.length ?? 0) === 0"><td colspan="3" class="empty">還沒有日誌 — reviewer 每日收盤後會寫一篇</td></tr>
        </tbody>
      </table>
      <Pager v-if="list" :page="list.page" :page-size="list.page_size" :total="list.total" :has-more="list.has_more" @go="load" />
    </div>

    <!-- selected entry -->
    <div class="panel panel-pad">
      <template v-if="selected">
        <div class="row"><h2 style="margin: 0">{{ selected.title || '(untitled)' }}</h2><div class="grow"></div>
          <span class="pill faint">{{ selected.author }}</span>
          <span class="pill faint">{{ selected.date ?? time(Date.parse(selected.ts)) }}</span>
        </div>
        <div class="markdown" style="margin-top: 14px" v-html="renderMarkdown(selected.body)"></div>
      </template>
      <div v-else class="muted" style="font-size: 13px">
        選一篇日誌看內容。reviewer 每日收盤後寫一篇當日復盤，POST 進 Sunday、在這裡呈現給你。
      </div>
    </div>
  </div>
</template>
