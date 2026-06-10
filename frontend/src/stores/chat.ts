// ============================================================
// 对话 Store — 消息管理 + SSE 事件分发 + 安全确认 + 历史加载
// 严格对齐后端 chat_stream + _process_tool_call 事件流
// ============================================================

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ChatMessage, PendingConfirm, RiskLevel, ToolCallStatus, Conversation } from '../types'
import { sendMessage as apiSendMessage, fetchConversations, fetchConversationDetail } from '../api/chat'

export const useChatStore = defineStore('chat', () => {
  // ====== 状态 ======
  const messages = ref<ChatMessage[]>([])
  const streaming = ref(false)
  const pendingConfirm = ref<PendingConfirm | null>(null)
  const currentSessionId = ref<string>(crypto.randomUUID())

  // 历史
  const conversations = ref<Conversation[]>([])
  const historyLoading = ref(false)

  // 最近一次对话的健康评分（用于仪表盘）
  const lastHealthScore = ref<{ score: number; grade: string; alerts: string[] } | null>(null)

  // ====== 计算属性 ======
  const lastAgentId = computed(() => {
    const msgs = messages.value
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].role === 'assistant') return msgs[i].id
    }
    return ''
  })

  // ====== SSE 事件分发 ======
  function handleSSEEvent(event: string, data: Record<string, unknown>, agentMsg: ChatMessage) {
    switch (event) {
      case 'token':
        agentMsg.content += (data.text as string) || ''
        break

      case 'tool_call': {
        const toolName = (data.tool_name as string) || ''
        // 避免重复：同一次对话中同一 tool 可能多次调用，用 id 去重
        const existing = agentMsg.tool_calls?.find(
          (tc) => tc.tool_name === toolName && tc.status === 'running',
        )
        if (!existing) {
          agentMsg.tool_calls = agentMsg.tool_calls || []
          agentMsg.tool_calls.push({
            id: crypto.randomUUID(),
            tool_name: toolName,
            arguments: (data.arguments as Record<string, unknown>) || {},
            status: 'running',
            risk_level: (data.risk_level as RiskLevel) || 'read_only',
          })
        }
        break
      }

      case 'tool_result': {
        const resultToolName = (data.tool_name as string) || ''
        const status = (data.status as ToolCallStatus) || 'done'
        // 更新最近一个匹配的 running tool_call
        const tcs = agentMsg.tool_calls
        if (tcs) {
          for (let i = tcs.length - 1; i >= 0; i--) {
            if (tcs[i].tool_name === resultToolName && tcs[i].status === 'running') {
              tcs[i].status = status
              tcs[i].result = data.result
              break
            }
          }
        }
        break
      }

      case 'security_check':
        pendingConfirm.value = {
          tool_name: (data.tool_name as string) || '',
          summary: (data.summary as string) || '',
          details: (data.details as string) || '',
          risk_level: (data.risk_level as RiskLevel) || 'restricted',
        }
        break

      case 'rca_analysis':
        lastHealthScore.value = {
          score: (data.score as number) || 0,
          grade: (data.grade as string) || '',
          alerts: (data.alerts as string[]) || [],
        }
        agentMsg.content += `\n\n📊 **系统健康评分**: ${data.score}/100 (${data.grade})`
        if (data.alerts && (data.alerts as string[]).length > 0) {
          agentMsg.content += '\n⚠️ 告警: ' + (data.alerts as string[]).join('; ')
        }
        break

      case 'error':
        agentMsg.content += `\n\n❌ ${(data.message as string) || '未知错误'}`
        break

      case 'done':
        // 流结束 — 外层会设置 streaming = false
        break
    }
  }

  // ====== 发送消息 ======
  async function sendMessage(text: string) {
    if (!text.trim() || streaming.value) return

    // 1. 追加用户消息
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    }
    messages.value.push(userMsg)

    // 2. 追加空的助理消息（流式填充）
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
    pendingConfirm.value = null

    try {
      const response = await apiSendMessage(text, currentSessionId.value)
      if (!response.ok) {
        agentMsg.content = `❌ 请求失败: HTTP ${response.status}`
        streaming.value = false
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
              console.warn('SSE 解析失败:', part.slice(0, 100))
            }
          }
        }
      }

      // 清理：移除空 tool_calls 数组
      if (agentMsg.tool_calls && agentMsg.tool_calls.length === 0) {
        delete agentMsg.tool_calls
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '未知错误'
      agentMsg.content += `\n\n❌ 连接中断: ${msg}`
    } finally {
      streaming.value = false
    }
  }

  // ====== 确认操作 ======
  function clearPendingConfirm() {
    pendingConfirm.value = null
  }

  function cancelPendingConfirm() {
    if (pendingConfirm.value) {
      // 追加系统消息记录取消
      messages.value.push({
        id: crypto.randomUUID(),
        role: 'system',
        content: `⚠️ 已取消操作: ${pendingConfirm.value.tool_name}`,
        timestamp: new Date().toISOString(),
      })
    }
    pendingConfirm.value = null
  }

  // ====== 会话管理 ======
  function newSession() {
    messages.value = []
    pendingConfirm.value = null
    lastHealthScore.value = null
    currentSessionId.value = crypto.randomUUID()
  }

  /** 加载历史会话列表 */
  async function loadConversations(page = 1, size = 20) {
    historyLoading.value = true
    try {
      const res = await fetchConversations(page, size)
      if (res.code === 0 && res.data) {
        conversations.value = res.data.items
      }
    } catch (e) {
      console.error('加载会话列表失败:', e)
    } finally {
      historyLoading.value = false
    }
  }

  /** 加载指定会话的历史消息 */
  async function loadSession(sessionId: string) {
    historyLoading.value = true
    try {
      const res = await fetchConversationDetail(sessionId)
      if (res.code === 0 && res.data) {
        messages.value = res.data.messages
        currentSessionId.value = sessionId
      }
    } catch (e) {
      console.error('加载会话详情失败:', e)
    } finally {
      historyLoading.value = false
    }
  }

  return {
    messages,
    streaming,
    pendingConfirm,
    currentSessionId,
    conversations,
    historyLoading,
    lastHealthScore,
    lastAgentId,
    sendMessage,
    clearPendingConfirm,
    cancelPendingConfirm,
    newSession,
    loadConversations,
    loadSession,
  }
})
