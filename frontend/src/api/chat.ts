// ============================================================
// 对话 API — SSE 流式对话 + 历史查询 + 确认回调
// 对齐后端 app/api/chat.py
// ============================================================

import { BASE_URL, apiGet } from './client'
import type { ApiResponse, Conversation, ChatMessage, PaginatedData } from '../types'

// ====== SSE 流式对话 ======

/**
 * POST /api/chat/send — 发送消息，返回原始 Response
 * 调用方通过 response.body!.getReader() 读取 SSE 流
 */
export function sendMessage(message: string, sessionId: string): Promise<Response> {
  return fetch(BASE_URL + '/chat/send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
  })
}

// ====== 危险操作确认 ======

/**
 * POST /api/chat/confirm — 确认危险操作
 * 当前为 Phase 1 桩实现：后端仅记录审计，不恢复执行
 */
export async function confirmAction(sessionId: string): Promise<{ success: boolean; message: string }> {
  const res = await fetch(BASE_URL + '/chat/confirm', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, confirmed: true }),
  })
  if (!res.ok) throw new Error(`确认失败: HTTP ${res.status}`)
  return res.json() as Promise<{ success: boolean; message: string }>
}

// ====== 对话历史 ======

/**
 * GET /api/chat/history — 会话列表（分页）
 */
export function fetchConversations(
  page: number = 1,
  size: number = 20,
): Promise<ApiResponse<PaginatedData<Conversation>>> {
  return apiGet('/chat/history', { page: String(page), size: String(size) })
}

/**
 * GET /api/chat/history/{session_id} — 会话消息详情
 */
export function fetchConversationDetail(
  sessionId: string,
): Promise<ApiResponse<{ session_id: string; messages: ChatMessage[] }>> {
  return apiGet(`/chat/history/${sessionId}`)
}
