<template>
  <div class="audit-timeline" v-loading="loading">
    <el-empty v-if="!loading && logs.length === 0" description="暂无审计记录" />

    <el-timeline v-else>
      <el-timeline-item
        v-for="log in logs"
        :key="log.id"
        :timestamp="formatTime(log.timestamp)"
        :color="riskColor(log.risk_level)"
        placement="top"
      >
        <div
          class="timeline-card"
          :class="{ selected: selectedId === log.id }"
          @click="emit('select', log)"
        >
          <div class="card-header">
            <StatusBadge :risk-level="log.risk_level" size="small" />
            <span class="card-user">{{ log.user }}</span>
          </div>
          <p class="card-summary">{{ log.stages[0].raw_input }}</p>
          <div class="card-meta">
            <span v-if="log.stages[3].rules_hit.length">
              命中: {{ log.stages[3].rules_hit.join(', ') }}
            </span>
            <span v-if="log.stages[4].duration_ms">
              耗时: {{ log.stages[4].duration_ms }}ms
            </span>
          </div>
        </div>
      </el-timeline-item>
    </el-timeline>

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
import { computed } from 'vue'
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
    case 'dangerous':  return '#F56C6C'
    case 'restricted': return '#E6A23C'
    default:           return '#67C23A'
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
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.timeline-card {
  background: var(--bg-panel);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 10px 14px;
  cursor: pointer;
  transition: border-color 0.2s;
}
.timeline-card:hover {
  border-color: var(--color-primary);
}
.timeline-card.selected {
  border-color: var(--color-primary);
  background: rgba(64, 158, 255, 0.06);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.card-user {
  font-size: 13px;
  font-weight: 600;
}
.card-summary {
  font-size: 13px;
  margin: 0 0 6px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}
.card-meta {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: var(--text-secondary);
}

.pagination {
  display: flex;
  justify-content: center;
  padding: 16px 0;
}
</style>
