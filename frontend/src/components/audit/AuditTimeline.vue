<template>
  <div class="timeline-panel">
    <!-- 加载中 -->
    <div v-if="loading" class="state-box">
      <span class="state-text">加载中...</span>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!items || items.length === 0" class="state-box">
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" opacity="0.35">
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
        :class="{ selected: item.id === selectedId }"
        @click="$emit('select', item)"
      >
        <span class="dot" :style="{ background: riskColor(item.risk_level) }" />
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
  return level === 'dangerous' ? '#ef4444' : level === 'restricted' ? '#f59e0b' : '#22c55e'
}
function riskLabel(level: RiskLevel): string {
  return level === 'dangerous' ? '高危' : level === 'restricted' ? '受限' : '安全'
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
  padding: 8px 14px;
  cursor: pointer;
  border-left: 3px solid transparent;
  transition: background 120ms;
}
.timeline-row:hover { background: var(--bg-hover); }
.timeline-row.selected {
  background: var(--color-accent-soft);
  border-left-color: var(--color-accent);
}

.dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  margin-top: 5px;
  flex-shrink: 0;
}

.row-card { flex: 1; min-width: 0; }

.row-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 3px;
}
.risk-label {
  font-size: 10px;
  font-weight: 600;
  padding: 0 5px;
  border-radius: 3px;
  line-height: 18px;
}
.risk-read_only  { background: var(--color-safe-soft); color: var(--color-safe); }
.risk-restricted { background: var(--color-warning-soft); color: var(--color-warning); }
.risk-dangerous  { background: var(--color-danger-soft); color: var(--color-danger); }

.row-time {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-left: auto;
}

.row-summary {
  font-size: 13px;
  color: var(--text-primary);
  margin: 0 0 3px;
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
  gap: 2px;
}
.meta-sep { margin: 0 2px; }
.meta-danger { color: var(--color-danger); }

/* ── Pager ── */
.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 12px;
  border-top: 1px solid var(--border-subtle);
  flex-shrink: 0;
}
.page-btn {
  padding: 4px 14px;
  border: 1px solid var(--border-default);
  border-radius: 6px;
  background: var(--bg-elevated);
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all 120ms;
}
.page-btn:hover:not(:disabled) {
  border-color: var(--color-accent);
  color: var(--color-accent-text);
}
.page-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
.page-info {
  font-size: 12px;
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}
</style>
