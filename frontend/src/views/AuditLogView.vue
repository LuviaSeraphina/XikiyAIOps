<template>
  <div class="audit-page">
    <!-- 筛选器 -->
    <AuditFilter @filter-change="onFilterChange" />

    <!-- 主内容：时间线 + 详情 -->
    <div class="audit-body">
      <div class="timeline-panel">
        <AuditTimeline
          :logs="store.logs"
          :loading="store.loading"
          :total="store.total"
          :size="store.filter.size"
          :current-page="store.filter.page"
          :selected-id="selectedId"
          @select="selectedId = $event.id"
          @page-change="onPageChange"
        />
      </div>
      <div class="detail-panel">
        <AuditDetail :log="selectedLog" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAuditStore } from '@/stores/audit'
import type { RiskLevel } from '@/types'
import AuditFilter from '@/components/audit/AuditFilter.vue'
import AuditTimeline from '@/components/audit/AuditTimeline.vue'
import AuditDetail from '@/components/audit/AuditDetail.vue'

const store = useAuditStore()
const selectedId = ref<string | null>(null)

const selectedLog = computed(() => {
  if (!selectedId.value) return null
  return store.logs.find((l) => l.id === selectedId.value) ?? null
})

function onFilterChange(params: { keyword: string; riskLevel: RiskLevel | ''; dateRange: string[] }) {
  store.setFilter({
    keyword: params.keyword,
    risk_level: params.riskLevel as RiskLevel | '',
  })
  selectedId.value = null
  store.loadLogs()
}

function onPageChange(page: number) {
  store.setPage(page)
  store.loadLogs()
}

onMounted(() => {
  store.loadLogs()
})
</script>

<style scoped>
.audit-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - var(--header-height));
}

.audit-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.timeline-panel {
  flex: 6;
  overflow-y: auto;
  border-right: 1px solid var(--border-subtle);
  background: var(--bg-root);
}

.detail-panel {
  flex: 4;
  overflow-y: auto;
  background: var(--bg-elevated);
}
</style>
