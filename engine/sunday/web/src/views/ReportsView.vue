<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api, type Report, type Page } from '../api/client'
import { time } from '../lib/format'
import { attempt } from '../lib/toast'
import { renderMarkdown } from '../lib/md'
import Pager from '../components/Pager.vue'

const list = ref<Page<Report> | null>(null)
const selected = ref<Report | null>(null)

async function load(pg = 1): Promise<void> {
  list.value = (await attempt(() => api.reports({ page: pg }))) ?? null
  const items = list.value?.items ?? []
  // keep the current selection if still on the page, else select the newest.
  if (items.length && (!selected.value || !items.some((r) => r.id === selected.value!.id)))
    selected.value = items[0]
}

function kindClass(kind: string): string { return ['profit', 'loss', 'system', 'info'].includes(kind) ? kind : 'info' }

onMounted(() => load())
</script>

<template>
  <div class="grid" style="grid-template-columns: 340px 1fr; align-items: start">
    <!-- report list (newest first) -->
    <div class="panel">
      <div class="panel-head"><h2>Reports</h2><div class="grow"></div>
        <button class="btn sm ghost" @click="load(list?.page ?? 1)" title="refresh">↻</button></div>
      <table class="tbl">
        <thead><tr><th class="left">Date</th><th class="left">Title</th><th>Kind</th></tr></thead>
        <tbody>
          <tr v-for="r in list?.items ?? []" :key="r.id" class="clickable" @click="selected = r"
            :style="selected?.id === r.id ? 'background: var(--panel-3)' : ''">
            <td class="left faint">{{ time(Date.parse(r.ts)) }}</td>
            <td class="left">{{ r.title || '(untitled)' }}</td>
            <td><span class="tag" :class="kindClass(r.kind)">{{ r.kind }}</span></td>
          </tr>
          <tr v-if="(list?.items.length ?? 0) === 0">
            <td colspan="3" class="empty">還沒有通報 — friday 遇到大賺 / 大賠 / 系統錯誤時會在這裡通報你</td></tr>
        </tbody>
      </table>
      <Pager v-if="list" :page="list.page" :page-size="list.page_size" :total="list.total" :has-more="list.has_more" @go="load" />
    </div>

    <!-- selected report -->
    <div class="panel panel-pad">
      <template v-if="selected">
        <div class="row"><h2 style="margin: 0">{{ selected.title || '(untitled)' }}</h2><div class="grow"></div>
          <span class="tag" :class="kindClass(selected.kind)">{{ selected.kind }}</span>
          <span class="pill faint">{{ time(Date.parse(selected.ts)) }}</span>
        </div>
        <div class="markdown" style="margin-top: 14px" v-html="renderMarkdown(selected.body)"></div>
      </template>
      <div v-else class="muted" style="font-size: 13px">
        選一則通報看內容。當有重要的事（大量盈利 / 大量虧損 / 系統錯誤），friday 會 POST 一則通報到 Sunday、在這裡呈現給你。
      </div>
    </div>
  </div>
</template>
