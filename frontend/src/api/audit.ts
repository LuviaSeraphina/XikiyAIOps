import { apiGet } from './client'
import { USE_MOCK, MOCK_AUDIT_LOGS } from './mock'
import type { AuditLog } from '../types'

export interface AuditListParams {
  page?: number
  size?: number
  risk_level?: string
  keyword?: string
}

/** GET /api/audit/list — 分页 + 筛选查询 */
export async function fetchAuditLogs(
  params: AuditListParams = {},
): Promise<{ items: AuditLog[]; total: number }> {
  if (USE_MOCK) {
    let filtered = MOCK_AUDIT_LOGS
    if (params.risk_level) {
      filtered = filtered.filter((l) => l.risk_level === params.risk_level)
    }
    if (params.keyword) {
      const kw = params.keyword.toLowerCase()
      filtered = filtered.filter(
        (l) =>
          l.user.toLowerCase().includes(kw) ||
          l.stages[0].raw_input.toLowerCase().includes(kw),
      )
    }
    const page = params.page || 1
    const size = params.size || 20
    const start = (page - 1) * size
    return { items: filtered.slice(start, start + size), total: filtered.length }
  }

  const query: Record<string, string> = {}
  if (params.page) query.page = String(params.page)
  if (params.size) query.size = String(params.size)
  if (params.risk_level) query.risk_level = params.risk_level
  if (params.keyword) query.keyword = params.keyword
  return apiGet('/audit/list', query)
}

/** GET /api/audit/{id} — 单条审计详情 */
export async function fetchAuditDetail(id: string): Promise<AuditLog> {
  if (USE_MOCK) {
    const found = MOCK_AUDIT_LOGS.find((l) => l.id === id)
    if (!found) throw new Error(`Audit log not found: ${id}`)
    return found
  }
  return apiGet(`/audit/${id}`)
}
