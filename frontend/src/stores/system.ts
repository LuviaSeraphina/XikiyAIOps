import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { SystemSummary, DiskInfo, ProcessInfo, NetworkStats } from '../types'
import {
  fetchSystemSummary,
  fetchDisks,
  fetchProcesses,
  fetchNetworkStats,
  fetchAuthFailures,
} from '../api/dashboard'

export const useSystemStore = defineStore('system', () => {
  // ---- 状态 ----
  const summary = ref<SystemSummary | null>(null)
  const disks = ref<DiskInfo[]>([])
  const processes = ref<ProcessInfo[]>([])
  const network = ref<NetworkStats | null>(null)
  const authFailures = ref<{ failed_ips: Record<string, number>; total: number }>({
    failed_ips: {},
    total: 0,
  })
  const lastUpdate = ref<number>(0)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // ---- 操作 ----
  async function refreshAll() {
    loading.value = true
    error.value = null
    try {
      const [s, d, p, n, a] = await Promise.all([
        fetchSystemSummary(),
        fetchDisks(),
        fetchProcesses('cpu', 10),
        fetchNetworkStats(),
        fetchAuthFailures(),
      ])
      summary.value = s
      disks.value = d
      processes.value = p
      network.value = n
      authFailures.value = a
      lastUpdate.value = Date.now()
    } catch (e) {
      error.value = e instanceof Error ? e.message : '刷新失败'
      console.error('仪表盘刷新失败:', e)
    } finally {
      loading.value = false
    }
  }

  return { summary, disks, processes, network, authFailures, lastUpdate, loading, error, refreshAll }
})
