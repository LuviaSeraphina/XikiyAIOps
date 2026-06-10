<template>
  <div class="audit-page">
    <AuditFilter
      :total="store.total"
      @filter-change="onFilterChange"
    />

    <div class="audit-body">
      <div class="left-panel">
        <AuditTimeline
          :items="store.logs"
          :loading="store.loading"
          :total="store.total"
          :page-size="store.filter.size"
          :current-page="store.filter.page"
          :selected-id="selectedId"
          @select="onSelect"
          @page-change="onPageChange"
        />
      </div>
      <div class="right-panel">
        <AuditDetail :item="selectedItem" />
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="store.error" class="error-bar">
      <span>{{ store.error }}</span>
      <button @click="store.loadLogs()">重试</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useAuditStore } from '@/stores/audit'
import AuditFilter from '@/components/audit/AuditFilter.vue'
import AuditTimeline from '@/components/audit/AuditTimeline.vue'
import AuditDetail from '@/components/audit/AuditDetail.vue'

const store = useAuditStore()
const selectedId = ref<string | null>(null)

const selectedItem = computed(() => {
  if (!selectedId.value) return null
  return store.logs.find(l => l.id === selectedId.value) ?? null
})

function onSelect(item: { id: string }) {
  selectedId.value = item.id
}

function onFilterChange(params: { keyword: string; riskLevel: string }) {
  store.setFilter({ keyword: params.keyword, risk_level: params.riskLevel as any })
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

onBeforeUnmount(() => {
  store.cancelLoading()
})
</script>

<style scoped>
.audit-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.audit-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.left-panel {
  flex: 6;
  border-right: 1px solid var(--border-subtle);
  background: var(--bg-root);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.right-panel {
  flex: 4;
  background: var(--bg-elevated);
  overflow: hidden;
}

/* ── Error bar ── */
.error-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 20px;
  background: var(--color-danger-soft);
  color: var(--color-danger);
  font-size: 13px;
  border-top: 1px solid rgba(239, 68, 68, 0.15);
}
.error-bar button {
  padding: 3px 12px;
  border: 1px solid var(--color-danger);
  border-radius: 5px;
  background: transparent;
  color: var(--color-danger);
  font-size: 12px;
  cursor: pointer;
  transition: all 120ms;
}
.error-bar button:hover {
  background: var(--color-danger);
  color: #fff;
}
</style>
