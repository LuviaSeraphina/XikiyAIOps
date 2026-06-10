<template>
  <div class="audit-filter">
    <div class="filter-row">
      <div class="search-box">
        <svg class="search-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <input v-model="keyword" class="search-input" placeholder="搜索指令关键字或用户名..." @input="onKeywordInput" />
      </div>
      <select v-model="riskLevel" class="risk-select" @change="emitImmediate">
        <option value="">全部等级</option>
        <option value="read_only">安全 (read_only)</option>
        <option value="restricted">需确认 (restricted)</option>
        <option value="dangerous">高危 (dangerous)</option>
      </select>
      <span class="count-badge" v-if="total > 0">{{ total }} 条</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onBeforeUnmount } from 'vue'

const emit = defineEmits<{ 'filter-change': [params: { keyword: string; riskLevel: string }] }>()
defineProps<{ total: number }>()

const keyword = ref('')
const riskLevel = ref('')
let timer: ReturnType<typeof setTimeout> | null = null

function onKeywordInput() {
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => emitFilter(), 300)
}
function emitFilter() {
  if (timer) clearTimeout(timer)
  emit('filter-change', { keyword: keyword.value, riskLevel: riskLevel.value })
}
function emitImmediate() {
  if (timer) clearTimeout(timer)
  emit('filter-change', { keyword: keyword.value, riskLevel: riskLevel.value })
}
onBeforeUnmount(() => { if (timer) clearTimeout(timer) })
</script>

<style scoped>
.audit-filter { padding: 10px 20px; background: var(--bg-elevated); border-bottom: 1px solid var(--border-subtle); flex-shrink: 0; }
.filter-row { display: flex; align-items: center; gap: 10px; }
.search-box { position: relative; flex: 1; max-width: 300px; }
.search-icon { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: var(--text-tertiary); pointer-events: none; }
.search-input { width: 100%; padding: 6px 10px 6px 30px; background: var(--bg-root); border: 1px solid var(--border-default); border-radius: 7px; color: var(--text-primary); font-size: 13px; outline: none; transition: border-color 150ms; }
.search-input:focus { border-color: var(--color-accent); }
.search-input::placeholder { color: var(--text-placeholder); }
.risk-select { padding: 6px 10px; background: var(--bg-root); border: 1px solid var(--border-default); border-radius: 7px; color: var(--text-primary); font-size: 13px; outline: none; cursor: pointer; min-width: 170px; transition: border-color 150ms; }
.risk-select:focus { border-color: var(--color-accent); }
.count-badge { font-size: 12px; color: var(--text-tertiary); white-space: nowrap; margin-left: auto; }
</style>