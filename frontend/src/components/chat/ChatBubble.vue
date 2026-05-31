<template>
  <div
    class="bubble-wrapper"
    :class="[message.role, { streaming }]"
  >
    <!-- 头像 -->
    <div class="bubble-avatar">
      <span class="avatar-icon" v-html="avatarSvg" />
    </div>

    <!-- 消息内容 -->
    <div class="bubble-main">
      <div class="bubble-meta">
        <span class="meta-role">{{ roleLabel }}</span>
        <span class="meta-time">{{ timeStr }}</span>
      </div>

      <div class="bubble-body">
        <!-- 思考中: 流式激活但无内容 -> 显示思考动画 -->
        <div v-if="isStreaming && !message.content && !message.tool_calls?.length" class="thinking-indicator">
          <span class="thinking-dot" />
          <span class="thinking-dot" />
          <span class="thinking-dot" />
          <span class="thinking-text">思考中，正在感知系统状态...</span>
        </div>

        <!-- 工具调用中: 有 tool_calls 但无内容 -->
        <div v-if="hasRunningTools" class="thinking-indicator tool-running">
          <span class="thinking-text">🔧 正在调用工具: {{ runningToolNames }}</span>
        </div>

        <!-- Markdown 渲染 -->
        <div v-if="message.content" class="content markdown-body" v-html="renderedContent" />

        <!-- 闪烁光标 (有内容时才显示) -->
        <span v-if="isStreaming && message.content" class="cursor-blink" />

        <!-- 工具调用卡片 -->
        <div v-if="message.tool_calls?.length" class="tool-calls">
          <ToolCallCard
            v-for="tc in message.tool_calls"
            :key="tc.id"
            :tool-call="tc"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ChatMessage } from '@/types'
import { renderMarkdown } from '@/utils/markdown'
import ToolCallCard from './ToolCallCard.vue'

const props = defineProps<{
  message: ChatMessage
  streaming: boolean
}>()

const isStreaming = computed(() => props.streaming && props.message.role === 'assistant')

const roleLabel = computed(() => {
  switch (props.message.role) {
    case 'user':      return '你'
    case 'assistant': return 'SRE-Agent'
    case 'system':    return '系统'
    case 'tool':      return '工具'
    default:          return ''
  }
})

const avatarSvg = computed(() => {
  switch (props.message.role) {
    case 'user':
      return `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`
    case 'assistant':
      return `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>`
    case 'system':
      return `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="3"/><path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72 1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>`
    default:
      return `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>`
  }
})

const timeStr = computed(() => {
  const d = new Date(props.message.timestamp)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
})

const renderedContent = computed(() => {
  if (!props.message.content) return ''
  return renderMarkdown(props.message.content)
})

// 是否有正在执行的工具
const hasRunningTools = computed(() => {
  return (props.message.tool_calls?.length ?? 0) > 0 &&
    props.message.tool_calls!.some(tc => tc.status === 'running' || tc.status === 'pending')
})

// 正在执行的工具名称列表
const runningToolNames = computed(() => {
  if (!props.message.tool_calls) return ''
  return props.message.tool_calls
    .filter(tc => tc.status === 'running' || tc.status === 'pending')
    .map(tc => tc.tool_name)
    .join(', ')
})
</script>

<style scoped>
.bubble-wrapper {
  display: flex;
  gap: 12px;
  max-width: 85%;
  margin-bottom: 20px;
  animation: fadeInUp 0.35s var(--ease-out);
}

/* ---- User: right align ---- */
.bubble-wrapper.user {
  margin-left: auto;
  flex-direction: row-reverse;
}
.bubble-wrapper.user .bubble-meta {
  flex-direction: row-reverse;
}
.bubble-wrapper.user .bubble-body {
  background: var(--color-accent);
  color: #fff;
  border-radius: 14px 4px 14px 14px;
}
.bubble-wrapper.user .meta-role {
  color: var(--text-tertiary);
}

/* ---- Agent: left align ---- */
.bubble-wrapper.assistant .bubble-body {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: 4px 14px 14px 14px;
}

/* ---- System / Tool ---- */
.bubble-wrapper.system .bubble-body,
.bubble-wrapper.tool .bubble-body {
  background: var(--bg-elevated);
  border: 1px dashed var(--border-subtle);
  border-radius: 10px;
  font-size: 12px;
  opacity: 0.8;
}

/* ---- Avatar ---- */
.bubble-avatar {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-surface);
  color: var(--text-secondary);
}
.bubble-wrapper.user .bubble-avatar {
  background: var(--color-accent);
  color: #fff;
}

/* ---- Main ---- */
.bubble-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

/* ---- Meta ---- */
.bubble-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  padding: 0 4px;
}
.meta-role {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}
.meta-time {
  font-size: 11px;
  color: var(--text-tertiary);
}

/* ---- Body ---- */
.bubble-body {
  padding: 12px 16px;
  line-height: 1.65;
  word-break: break-word;
}

/* ---- Content styling ---- */
.content :deep(p) { margin: 4px 0; }
.content :deep(p:first-child) { margin-top: 0; }
.content :deep(p:last-child) { margin-bottom: 0; }
.content :deep(ul), .content :deep(ol) { padding-left: 20px; margin: 4px 0; }
.content :deep(table) {
  border-collapse: collapse;
  margin: 8px 0;
  width: 100%;
}
.content :deep(th), .content :deep(td) {
  border: 1px solid var(--border-subtle);
  padding: 6px 10px;
  font-size: 12.5px;
}
.content :deep(th) {
  background: rgba(255,255,255,0.03);
  font-weight: 600;
}
.content :deep(blockquote) {
  border-left: 3px solid var(--color-accent);
  padding: 4px 12px;
  margin: 6px 0;
  opacity: 0.8;
  background: rgba(255,255,255,0.02);
  border-radius: 0 4px 4px 0;
}
.content :deep(h1), .content :deep(h2), .content :deep(h3) {
  margin: 8px 0 4px;
  font-weight: 600;
}
.content :deep(h1) { font-size: 18px; }
.content :deep(h2) { font-size: 16px; }
.content :deep(h3) { font-size: 14px; }

/* 思考中动画 */
.bubble-body .thinking-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 0;
}
.bubble-body .thinking-text {
  font-size: 13px;
  color: var(--text-secondary);
  margin-left: 4px;
}
.bubble-body .thinking-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-secondary);
  animation: dotPulse 1.4s infinite ease-in-out;
}
.bubble-body .thinking-dot:nth-child(1) { animation-delay: 0s; }
.bubble-body .thinking-dot:nth-child(2) { animation-delay: 0.2s; }
.bubble-body .thinking-dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes dotPulse {
  0%, 80%, 100% { opacity: 0.2; }
  40% { opacity: 1; }
}

/* ---- Tool calls ---- */
.tool-calls {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* ---- Cursor ---- */
.cursor-blink {
  display: inline-block;
  width: 2px;
  height: 16px;
  background: var(--color-accent);
  animation: blink 0.6s infinite;
  vertical-align: text-bottom;
  border-radius: 1px;
}
</style>
