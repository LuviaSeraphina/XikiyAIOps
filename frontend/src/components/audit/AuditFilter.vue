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
      <button
        class="anomaly-toggle"
        :class="{ active: anomalyOnly }"
        @click="anomalyOnly = !anomalyOnly; emitImmediate()"
        title="仅显示异常记录"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
          <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
        仅异常
      </button>
      <span class="count-badge" v-if="total > 0">{{ total }} 条</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onBeforeUnmount } from 'vue'

const emit = defineEmits<{ 'filter-change': [params: { keyword: string; riskLevel: string; anomaly: boolean }] }>()
defineProps<{ total: number }>()

const keyword = ref('')
const riskLevel = ref('')
const anomalyOnly = ref(false)
let timer: ReturnType<typeof setTimeout> | null = null

function onKeywordInput() {
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => emitFilter(), 300)
}
function emitFilter() {
  if (timer) clearTimeout(timer)
  emit('filter-change', { keyword: keyword.value, riskLevel: riskLevel.value, anomaly: anomalyOnly.value })
}
function emitImmediate() {
  if (timer) clearTimeout(timer)
  emit('filter-change', { keyword: keyword.value, riskLevel: riskLevel.value, anomaly: anomalyOnly.value })
}
onBeforeUnmount(() => { if (timer) clearTimeout(timer) })
</script>

<style scoped>
.audit-filter {
  padding: 12px 20px;
  background: var(--bg-elevated);
  border-bottom: 1px solid var(--border-default);
  flex-shrink: 0;
}
.filter-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.search-box {
  position: relative;
  flex: 1;
  max-width: 300px;
}
.search-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-tertiary);
  pointer-events: none;
}
.search-input {
  width: 100%;
  padding: 8px 12px 8px 34px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
  transition: border-color var(--dur-quick) var(--ease-spring);
}
.search-input:focus {
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px var(--color-accent-soft);
}
.search-input::placeholder {
  color: var(--text-placeholder);
}
.risk-select {
  padding: 8px 12px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
  cursor: pointer;
  min-width: 170px;
  transition: border-color var(--dur-quick) var(--ease-spring);
}
.risk-select:focus {
  border-color: var(--color-accent);
}
.count-badge {
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--text-tertiary);
  white-space: nowrap;
  margin-left: auto;
}

.anomaly-toggle {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 8px 14px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all var(--dur-quick) var(--ease-spring);
  white-space: nowrap;
}
.anomaly-toggle:hover {
  border-color: var(--color-danger);
  color: var(--color-danger);
}
.anomaly-toggle.active {
  background: var(--color-danger-soft);
  border-color: var(--color-danger);
  color: var(--color-danger);
  font-weight: 600;
}
</style>