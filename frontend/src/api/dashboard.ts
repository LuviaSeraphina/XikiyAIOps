import { apiGet } from './client'
import { USE_MOCK, MOCK_SYSTEM_SUMMARY, MOCK_DISKS, MOCK_PROCESSES, MOCK_NETWORK, MOCK_AUTH_FAILURES } from './mock'
import type { SystemSummary, DiskInfo, ProcessInfo, NetworkStats } from '../types'

/** GET /api/dashboard/summary — 系统概览（30s 轮询） */
export async function fetchSystemSummary(): Promise<SystemSummary> {
  if (USE_MOCK) return MOCK_SYSTEM_SUMMARY
  return apiGet('/dashboard/summary')
}

/** GET /api/dashboard/disks — 磁盘列表 */
export async function fetchDisks(): Promise<DiskInfo[]> {
  if (USE_MOCK) return MOCK_DISKS
  return apiGet('/dashboard/disks')
}

/** GET /api/dashboard/processes?sort_by=cpu&top_n=10 — 进程 TOP N */
export async function fetchProcesses(
  sortBy: 'cpu' | 'memory' = 'cpu',
  topN = 10,
): Promise<ProcessInfo[]> {
  if (USE_MOCK) return MOCK_PROCESSES.slice(0, topN)
  return apiGet('/dashboard/processes', { sort_by: sortBy, top_n: String(topN) })
}

/** GET /api/dashboard/network — 网络统计 */
export async function fetchNetworkStats(): Promise<NetworkStats> {
  if (USE_MOCK) return MOCK_NETWORK
  return apiGet('/dashboard/network')
}

/** GET /api/dashboard/auth-failures — 登录失败统计 */
export async function fetchAuthFailures(): Promise<{ failed_ips: Record<string, number>; total: number }> {
  if (USE_MOCK) return MOCK_AUTH_FAILURES
  return apiGet('/dashboard/auth-failures')
}
