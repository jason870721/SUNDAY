<script setup lang="ts">
const props = defineProps<{ page: number; pageSize: number; total: number; hasMore: boolean }>()
const emit = defineEmits<{ (e: 'go', page: number): void }>()

const from = () => (props.total === 0 ? 0 : (props.page - 1) * props.pageSize + 1)
const to = () => Math.min(props.page * props.pageSize, props.total)
</script>

<template>
  <div class="pager">
    <span class="faint">{{ from() }}–{{ to() }} of {{ total }}</span>
    <div class="grow"></div>
    <button class="btn sm ghost" :disabled="page <= 1" @click="emit('go', page - 1)">‹ prev</button>
    <span>p{{ page }}</span>
    <button class="btn sm ghost" :disabled="!hasMore" @click="emit('go', page + 1)">next ›</button>
  </div>
</template>
