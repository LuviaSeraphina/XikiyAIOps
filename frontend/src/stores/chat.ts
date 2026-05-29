import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ChatMessage, PendingConfirm, RiskLevel, ToolCallStatus } from '../types'
import { sendMessage as apiSendMessage } from '../api/chat'

export const useChatStore = defineStore('chat', () => {
  // ---- 状态 ----
  const messages = ref<ChatMessage[]>([])
  const streaming = ref(false)
  const pendingConfirm = ref<PendingConfirm | null>(null)
  const currentSessionId = ref(crypto.randomUUID())

  // ---- 内部方法：SSE 事件分发 ----
  function handleSSEEvent(event: string, data: Record<string, unknown>, agentMsg: ChatMessage) {
    switch (event) {
      case 'token':
        agentMsg.content += data.text as string
        break

      case 'tool_call':
        agentMsg.tool_calls!.push({
          id: crypto.randomUUID(),
          tool_name: data.tool_name as string,
          arguments: data.arguments as Record<string, unknown>,
          status: 'running',
          risk_level: data.risk_level as RiskLevel,
        })
        break

      case 'tool_result': {
        const tc = agentMsg.tool_calls?.find(
          (t) => t.tool_name === (data.tool_name as string),
        )
        if (tc) {
          tc.status = data.status as ToolCallStatus
          tc.result = data.result
        }
        break
      }

      case 'security_check':
        pendingConfirm.value = {
          message_id: agentMsg.id,
          tool_name: data.tool_name as string,
          summary: data.summary as string,
          details: data.details as string,
          risk_level: data.risk_level as RiskLevel,
        }
        break

      case 'done':
        // 流结束，streaming 由外层设为 false
        break

      case 'error':
        agentMsg.content += `\n\n❌ 错误: ${data.message}`
        break
    }
  }

  // ---- 发送消息 ----
  async function sendMessage(text: string) {
    // 1. 追加用户消息
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    }
    messages.value.push(userMsg)

    // 2. 追加空的 Agent 消息（流式填充）
    const agentMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
      tool_calls: [],
    }
    messages.value.push(agentMsg)

    // 3. 发起 SSE 请求
    streaming.value = true
    try {
      const response = await apiSendMessage(text, currentSessionId.value)
      if (!response.ok) {
        agentMsg.content = `❌ 请求失败: HTTP ${response.status}`
        return
      }

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop() || ''

        for (const part of parts) {
          if (!part.trim()) continue
          const lines = part.split('\n')
          let eventType = ''
          let dataStr = ''
          for (const line of lines) {
            if (line.startsWith('event: ')) eventType = line.slice(7)
            else if (line.startsWith('data: ')) dataStr = line.slice(6)
          }
          if (eventType && dataStr) {
            try {
              handleSSEEvent(eventType, JSON.parse(dataStr), agentMsg)
            } catch {
              console.warn('SSE 解析失败:', part)
            }
          }
        }
      }
    } catch (e) {
      agentMsg.content += `\n\n❌ 连接中断: ${e instanceof Error ? e.message : '未知错误'}`
    } finally {
      streaming.value = false
    }
  }

  // ---- 清除确认弹窗 ----
  function clearPendingConfirm() {
    pendingConfirm.value = null
  }

  return { messages, streaming, pendingConfirm, currentSessionId, sendMessage, clearPendingConfirm }
})
