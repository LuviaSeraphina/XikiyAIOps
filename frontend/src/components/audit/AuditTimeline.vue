<template>
  <div class="timeline-panel">
    <!-- 加载中 -->
    <div v-if="loading" class="state-box">
      <span class="state-text">加载中...</span>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!items || items.length === 0" class="state-box">
      <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" opacity="0.3">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
      </svg>
      <span class="state-text">暂无审计记录</span>
    </div>

    <!-- 列表 -->
    <div v-else class="timeline-list">
      <div
        v-for="item in items"
        :key="item.id"
        class="timeline-row"
        :class="{ selected: item.id === selectedId, 'row-anomaly': item.is_anomaly }"
        @click="$emit('select', item)"
      >
        <span class="dot" :style="{ background: riskColor(item.risk_level) }" />
        <span v-if="item.is_anomaly" class="anomaly-dot" title="异常记录">⚠</span>
        <div class="row-card">
          <div class="row-top">
            <span class="risk-label" :class="'risk-' + item.risk_level">
              {{ riskLabel(item.risk_level) }}
            </span>
            <span class="row-time">{{ formatTime(item.timestamp) }}</span>
          </div>
          <p class="row-summary">{{ item.stages[0]?.raw_input || '(空)' }}</p>
          <div class="row-meta">
            <span>{{ item.user }}</span>
            <template v-if="item.stages[3]?.rules_hit?.length">
              <span class="meta-sep">·</span>
              <span class="meta-danger">{{ item.stages[3].rules_hit.join(', ') }}</span>
            </template>
            <template v-if="item.stages[4]?.duration_ms">
              <span class="meta-sep">·</span>
              <span>{{ item.stages[4].duration_ms }}ms</span>
            </template>
          </div>
        </div>
      </div>

      <!-- 分页 -->
      <div v-if="total > pageSize" class="pager">
        <button
          class="page-btn"
          :disabled="currentPage <= 1"
          @click="$emit('page-change', currentPage - 1)"
        >上一页</button>
        <span class="page-info">{{ currentPage }} / {{ totalPages }}</span>
        <button
          class="page-btn"
          :disabled="currentPage >= totalPages"
          @click="$emit('page-change', currentPage + 1)"
        >下一页</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AuditLog, RiskLevel } from '@/types'

const props = defineProps<{
  items: AuditLog[]
  loading: boolean
  total: number
  pageSize: number
  currentPage: number
  selectedId: string | null
}>()

defineEmits<{
  select: [item: AuditLog]
  'page-change': [page: number]
}>()

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

function riskColor(level: RiskLevel): string {
  switch (level) {
    case 'critical':   return '#7c3aed'
    case 'dangerous':  return '#ef4444'
    case 'restricted': return '#f59e0b'
    default:           return '#22c55e'
  }
}
function riskLabel(level: RiskLevel): string {
  switch (level) {
    case 'critical':   return '致命'
    case 'dangerous':  return '高危'
    case 'restricted': return '受限'
    default:           return '安全'
  }
}
function formatTime(ts: string): string {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped>
.timeline-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.state-box {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--text-tertiary);
}
.state-text { font-size: 13px; }

.timeline-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}

.timeline-row {
  display: flex;
  gap: 10px;
  padding: 10px 16px;
  cursor: pointer;
  border-left: 3px solid transparent;
  transition: background var(--dur-quick) var(--ease-spring);
}
.timeline-row:hover {
  background: var(--bg-hover);
}
.timeline-row.selected {
  background: var(--color-accent-soft);
  border-left-color: var(--color-accent);
}
.timeline-row.row-anomaly {
  border-left-color: var(--color-danger);
}

.dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  margin-top: 5px;
  flex-shrink: 0;
}
.anomaly-dot {
  font-size: 12px;
  line-height: 1;
  margin-top: 3px;
  flex-shrink: 0;
  cursor: help;
}

.row-card { flex: 1; min-width: 0; }

.row-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.risk-label {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  line-height: 18px;
}
.risk-read_only  { background: var(--color-safe-soft); color: var(--color-safe); }
.risk-restricted { background: var(--color-warning-soft); color: var(--color-warning); }
.risk-dangerous  { background: var(--color-danger-soft); color: var(--color-danger); }
.risk-critical   { background: #ede9fe; color: #7c3aed; }

.row-time {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-left: auto;
  font-family: var(--font-mono);
}

.row-summary {
  font-size: 13px;
  color: var(--text-primary);
  margin: 0 0 4px;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row-meta {
  font-size: 11px;
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}
.meta-sep {
  color: var(--text-placeholder);
}
.meta-danger {
  color: var(--color-danger);
  font-weight: 500;
}

/* ── Pager ── */
.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 14px;
  border-top: 1px solid var(--border-subtle);
}
.page-btn {
  padding: 5px 14px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  background: var(--bg-elevated);
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all var(--dur-quick) var(--ease-spring);
}
.page-btn:hover:not(:disabled) {
  border-color: var(--color-accent);
  color: var(--color-accent);
}
.page-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
.page-info {
  font-size: 12px;
  color: var(--text-tertiary);
  font-family: var(--font-mono);
}
</style>
