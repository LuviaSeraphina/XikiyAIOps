// ============================================================
// 审计日志 API — 分页查询 + 详情
// 对齐后端 app/api/audit.py
// ============================================================

import { apiGet } from './client'
import type { ApiResponse, AuditLog, PaginatedData } from '../types'

export interface AuditListParams {
  page?: number
  size?: number
  risk_level?: string
  keyword?: string
}

/**
 * GET /api/audit/list — 分页 + 筛选查询
 * @param signal 可选的 AbortSignal，用于取消请求
 */
export function fetchAuditLogs(
  params: AuditListParams = {},
  signal?: AbortSignal,
): Promise<ApiResponse<PaginatedData<AuditLog>>> {
  const query: Record<string, string> = {}
  if (params.page) query.page = String(params.page)
  if (params.size) query.size = String(params.size)
  if (params.risk_level) query.risk_level = params.risk_level
  if (params.keyword) query.keyword = params.keyword
  return apiGet('/audit/list', query, undefined, signal)
}

/**
 * GET /api/audit/{id} — 单条审计日志详情
 */
export function fetchAuditDetail(
  id: string,
): Promise<ApiResponse<AuditLog>> {
  return apiGet(`/audit/${id}`)
}
