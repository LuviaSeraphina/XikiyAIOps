import { BASE_URL } from './client'

/**
 * POST /api/chat/send — 发送消息，返回 SSE ReadableStream
 * @returns 原始 Response，由调用方通过 response.body.getReader() 读取 SSE 流
 */
export function sendMessage(message: string, sessionId: string): Promise<Response> {
  return fetch(BASE_URL + '/chat/send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
  })
}

/**
 * POST /api/chat/confirm — 确认危险操作
 * 取消操作不调此 API，直接丢弃消息即可
 */
export async function confirmAction(
  sessionId: string,
  messageId: string,
): Promise<{ success: boolean }> {
  const res = await fetch(BASE_URL + '/chat/confirm', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, message_id: messageId, confirmed: true }),
  })
  if (!res.ok) {
    throw new Error(`Confirm API Error: ${res.status}`)
  }
  return res.json()
}
