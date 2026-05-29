import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { AuditLog, RiskLevel } from '../types'
import { fetchAuditLogs } from '../api/audit'

export const useAuditStore = defineStore('audit', () => {
  // ---- 状态 ----
  const logs = ref<AuditLog[]>([])
  const total = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const filter = ref({
    page: 1,
    size: 20,
    risk_level: '' as RiskLevel | '',
    keyword: '',
  })

  // ---- 操作 ----
  async function loadLogs() {
    loading.value = true
    error.value = null
    try {
      const res = await fetchAuditLogs({
        page: filter.value.page,
        size: filter.value.size,
        risk_level: filter.value.risk_level || undefined,
        keyword: filter.value.keyword || undefined,
      })
      logs.value = res.items
      total.value = res.total
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载失败'
      console.error('审计日志加载失败:', e)
    } finally {
      loading.value = false
    }
  }

  function setFilter(partial: Partial<typeof filter.value>) {
    Object.assign(filter.value, partial)
    filter.value.page = 1 // 筛选条件变更时重置页码
  }

  function setPage(page: number) {
    filter.value.page = page
  }

  return { logs, total, loading, error, filter, loadLogs, setFilter, setPage }
})
