// ============================================================
// 审计日志 Store — 分页查询 + 筛选 + 请求取消
// 对齐后端 /api/audit/list 响应: { code, data: { items, total, page, page_size } }
// ============================================================

import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { AuditLog, RiskLevel } from '../types'
import { fetchAuditLogs } from '../api/audit'

export const useAuditStore = defineStore('audit', () => {
  // ====== 状态 ======
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

  // 当前请求的 AbortController，用于组件卸载时取消
  let abortController: AbortController | null = null

  // ====== 操作 ======
  async function loadLogs() {
    // 取消上一个未完成的请求
    cancelLoading()
    abortController = new AbortController()

    loading.value = true
    error.value = null
    try {
      const res = await fetchAuditLogs(
        {
          page: filter.value.page,
          size: filter.value.size,
          risk_level: filter.value.risk_level || undefined,
          keyword: filter.value.keyword || undefined,
        },
        abortController.signal,
      )
      if (res.code === 0 && res.data) {
        logs.value = res.data.items
        total.value = res.data.total
      } else {
        error.value = res.message || '加载失败'
      }
    } catch (e: unknown) {
      // 忽略主动取消的请求
      if (e instanceof DOMException && e.name === 'AbortError') return
      error.value = e instanceof Error ? e.message : '加载失败'
      console.error('审计日志加载失败:', e)
    } finally {
      loading.value = false
    }
  }

  /** 取消进行中的请求，用于组件卸载时调用 */
  function cancelLoading() {
    if (abortController) {
      abortController.abort()
      abortController = null
    }
    loading.value = false
  }

  function setFilter(partial: Partial<typeof filter.value>) {
    Object.assign(filter.value, partial)
    filter.value.page = 1 // 筛选变更时重置页码
  }

  function setPage(page: number) {
    filter.value.page = page
  }

  return { logs, total, loading, error, filter, loadLogs, cancelLoading, setFilter, setPage }
})
