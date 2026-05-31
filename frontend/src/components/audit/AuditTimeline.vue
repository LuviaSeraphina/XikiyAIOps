<template>
  <div class="audit-timeline" v-loading="loading">
    <!-- Empty state -->
    <div v-if="!loading && logs.length === 0" class="empty-state">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
      </svg>
      <span>暂无审计记录</span>
    </div>

    <!-- Timeline -->
    <div v-else class="timeline-list">
      <div
        v-for="log in logs"
        :key="log.id"
        class="timeline-item"
        :class="{ selected: selectedId === log.id }"
        @click="emit('select', log)"
      >
        <div class="timeline-dot" :style="{ background: riskColor(log.risk_level) }" />
        <div class="timeline-card">
          <div class="card-top">
            <StatusBadge :risk-level="log.risk_level" size="sm" />
            <span class="card-time">{{ formatTime(log.timestamp) }}</span>
          </div>
          <p class="card-summary">{{ log.stages[0].raw_input }}</p>
          <div class="card-meta">
            <span class="meta-user">{{ log.user }}</span>
            <span class="meta-sep">·</span>
            <span v-if="log.stages[3].rules_hit.length" class="meta-rules">
              {{ log.stages[3].rules_hit.join(', ') }}
            </span>
            <span v-if="log.stages[4].duration_ms" class="meta-duration">
              {{ log.stages[4].duration_ms }}ms
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Pagination -->
    <div v-if="total > size" class="pagination">
      <el-pagination
        background
        layout="total, prev, pager, next"
        :total="total"
        :page-size="size"
        :current-page="currentPage"
        @current-change="emit('page-change', $event)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { AuditLog, RiskLevel } from '@/types'
import StatusBadge from '@/components/common/StatusBadge.vue'

const props = defineProps<{
  logs: AuditLog[]
  loading: boolean
  total: number
  size: number
  currentPage: number
  selectedId: string | null
}>()

const emit = defineEmits<{
  select: [log: AuditLog]
  'page-change': [page: number]
}>()

function riskColor(level: RiskLevel): string {
  switch (level) {
    case 'dangerous':  return '#ef4444'
    case 'restricted': return '#f59e0b'
    default:           return '#22c55e'
  }
}

function formatTime(ts: string): string {
  const d = new Date(ts)
  return d.toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}
</script>

<style scoped>
.audit-timeline {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--text-tertiary);
  font-size: 13px;
}

/* Timeline */
.timeline-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.timeline-item {
  display: flex;
  gap: 12px;
  position: relative;
  cursor: pointer;
}
.timeline-item:not(:last-child)::before {
  content: '';
  position: absolute;
  left: 11px;
  top: 24px;
  bottom: -16px;
  width: 1px;
  background: var(--border-subtle);
}

.timeline-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-top: 10px;
  flex-shrink: 0;
  z-index: 1;
  box-shadow: 0 0 0 3px var(--bg-root);
}

.timeline-card {
  flex: 1;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  margin-bottom: 16px;
  transition: all var(--duration-fast) var(--ease-out);
}
.timeline-card:hover {
  border-color: var(--border-emphasis);
}
.timeline-item.selected .timeline-card {
  border-color: var(--color-accent);
  background: var(--color-accent-soft);
}

.card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.card-time {
  font-size: 11px;
  color: var(--text-tertiary);
}

.card-summary {
  font-size: 13px;
  color: var(--text-primary);
  margin: 0 0 6px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-tertiary);
}
.meta-user {
  color: var(--text-secondary);
  font-weight: 500;
}
.meta-sep {
  color: var(--border-emphasis);
}
.meta-rules {
  color: var(--color-warning);
}
.meta-duration {
  color: var(--text-tertiary);
  margin-left: auto;
}

.pagination {
  display: flex;
  justify-content: center;
  padding: 16px 0;
  border-top: 1px solid var(--border-subtle);
}
</style>
