<template>
  <div class="msg" :class="[message.role, { streaming }]">
    <!-- 头像 -->
    <div class="msg-avatar" :class="message.role">
      <span v-html="avatarSvg" />
    </div>

    <!-- 内容 -->
    <div class="msg-main">
      <!-- 元信息 -->
      <div class="msg-meta">
        <span class="msg-role">{{ roleLabel }}</span>
        <span class="msg-time">{{ timeStr }}</span>
      </div>

      <!-- 思考中 -->
      <div v-if="isStreaming && !message.content && !message.tool_calls?.length" class="msg-thinking">
        <span class="thinking-dot" />
        <span class="thinking-dot" />
        <span class="thinking-dot" />
        <span class="thinking-label">思考中...</span>
      </div>

      <!-- 工具执行中 -->
      <div v-if="hasRunningTools && !message.content" class="msg-thinking tool-mode">
        <span class="thinking-label">正在调用: {{ runningToolNames }}</span>
      </div>

      <!-- 正文 -->
      <div v-if="message.content" class="msg-content" v-html="renderedContent" />

      <!-- 流式光标 -->
      <span v-if="streaming && message.role === 'assistant' && message.content" class="cursor" />

      <!-- 工具卡片 -->
      <div v-if="message.tool_calls?.length" class="msg-tools">
        <ToolCallCard
          v-for="tc in message.tool_calls"
          :key="tc.id"
          :tool-call="tc"
        />
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
    case 'user':      return 'You'
    case 'assistant': return 'XikiyAIOps'
    case 'system':    return 'System'
    case 'tool':      return 'Tool'
    default:          return ''
  }
})

const avatarSvg = computed(() => {
  switch (props.message.role) {
    case 'user':
      return `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 0 0-16 0"/></svg>`
    case 'assistant':
      return `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>`
    case 'system':
      return `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`
    default:
      return `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>`
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

const hasRunningTools = computed(() => {
  return (props.message.tool_calls?.length ?? 0) > 0 &&
    props.message.tool_calls!.some(tc => tc.status === 'running' || tc.status === 'pending')
})

const runningToolNames = computed(() => {
  if (!props.message.tool_calls) return ''
  return props.message.tool_calls
    .filter(tc => tc.status === 'running' || tc.status === 'pending')
    .map(tc => tc.tool_name)
    .join(', ')
})
</script>

<style scoped>
.msg {
  display: flex;
  gap: 14px;
  padding: 20px 24px;
  transition: background var(--dur-base) var(--ease-spring);
}
.msg.assistant {
  background: var(--bg-elevated);
  border-radius: 0;
}
.msg + .msg {
  border-top: 1px solid var(--border-subtle);
}

/* ── Avatar ── */
.msg-avatar {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 2px;
}
.msg-avatar.user      { background: var(--color-accent-soft); color: var(--color-accent); }
.msg-avatar.assistant  { background: rgba(107, 138, 255, 0.1); color: var(--color-accent); }
.msg-avatar.system     { background: var(--color-warning-soft); color: var(--color-warning); }
.msg-avatar.tool       { background: var(--bg-hover); color: var(--text-tertiary); }

/* ── Main ── */
.msg-main {
  flex: 1;
  min-width: 0;
}

/* ── Meta ── */
.msg-meta {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 6px;
}
.msg-role {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.msg-time {
  font-size: 11px;
  color: var(--text-tertiary);
  font-family: var(--font-mono);
}

/* ── Thinking ── */
.msg-thinking {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 0;
}
.thinking-dot {
  width: 5px; height: 5px;
  border-radius: 50%;
  background: var(--color-accent);
  animation: dot-bounce 1.4s infinite ease-in-out both;
}
.thinking-dot:nth-child(1) { animation-delay: 0s; }
.thinking-dot:nth-child(2) { animation-delay: 0.16s; }
.thinking-dot:nth-child(3) { animation-delay: 0.32s; }
.thinking-label {
  font-size: 13px;
  color: var(--text-tertiary);
  margin-left: 6px;
}
.msg-thinking.tool-mode .thinking-label {
  color: var(--color-accent);
  font-weight: 500;
}

/* ── Content (Markdown) ── */
.msg-content {
  font-size: 15px;
  line-height: 1.75;
  color: var(--text-primary);
  word-break: break-word;
}
.msg-content :deep(p)          { margin: 0 0 10px; }
.msg-content :deep(p:last-child) { margin-bottom: 0; }
.msg-content :deep(ul),
.msg-content :deep(ol)         { padding-left: 22px; margin: 0 0 10px; }
.msg-content :deep(li)         { margin-bottom: 3px; }

.msg-content :deep(code) {
  font-family: var(--font-mono);
  font-size: 13px;
  background: var(--bg-code);
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid var(--border-subtle);
}
.msg-content :deep(pre) {
  background: var(--bg-code);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 14px 16px;
  margin: 8px 0 12px;
  overflow-x: auto;
}
.msg-content :deep(pre code) {
  background: none;
  border: none;
  padding: 0;
}
.msg-content :deep(blockquote) {
  border-left: 3px solid var(--color-accent);
  padding-left: 14px;
  margin: 8px 0;
  color: var(--text-secondary);
}
.msg-content :deep(table) {
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 13px;
}
.msg-content :deep(th) {
  background: var(--bg-surface);
  padding: 8px 12px;
  text-align: left;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-default);
}
.msg-content :deep(td) {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-subtle);
}
.msg-content :deep(a) {
  color: var(--color-accent);
  text-decoration: underline;
  text-decoration-color: var(--color-accent-soft);
}
.msg-content :deep(a:hover) {
  text-decoration-color: var(--color-accent);
}

/* ── Cursor ── */
.cursor {
  display: inline-block;
  width: 2px;
  height: 16px;
  background: var(--color-accent);
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: cursor-blink 1s infinite;
  border-radius: 1px;
  box-shadow: 0 0 6px var(--color-accent-glow);
}

/* ── Tools ── */
.msg-tools {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}
</style>
