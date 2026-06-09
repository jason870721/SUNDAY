<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchManual } from '../api/client'
import { renderMarkdown } from '../lib/md'

const html = ref('')
const loading = ref(true)

onMounted(async () => {
  try { html.value = renderMarkdown(await fetchManual()) }
  catch { html.value = '<p class="down">could not load /manual</p>' }
  loading.value = false
})
</script>

<template>
  <div class="panel panel-pad">
    <div v-if="loading" class="loading"><span class="spinner"></span></div>
    <div v-else class="markdown" v-html="html"></div>
  </div>
</template>
