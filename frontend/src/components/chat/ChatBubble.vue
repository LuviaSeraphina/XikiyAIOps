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
        <span class="thinking-label">🔧 正在调用: {{ runningToolNames }}</span>
      </div>

      <!-- 正文 -->
      <div v-if="message.content" class="msg-content" v-html="renderedContent" />

      <!-- 流式光标 -->
      <span v-if="isStreaming && message.content" class="cursor" />

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
    case 'assistant': return 'SRE-Agent'
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
  gap: 16px;
  padding: 16px 0;
  animation: fadeIn 0.3s ease;
}
.msg + .msg {
  border-top: 1px solid var(--border-subtle);
}

/* ---- Avatar ---- */
.msg-avatar {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  margin-top: 2px;
}
.msg-avatar.user      { background: #5a7af7; }
.msg-avatar.assistant  { background: #10a37f; }
.msg-avatar.system     { background: #8896a7; }
.msg-avatar.tool       { background: #8896a7; }

/* ---- Main ---- */
.msg-main {
  flex: 1;
  min-width: 0;
  padding-top: 2px;
}

/* ---- Meta ---- */
.msg-meta {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 6px;
}
.msg-role {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.msg-time {
  font-size: 12px;
  color: var(--text-tertiary);
}

/* ---- Content ---- */
.msg-content {
  font-size: 15px;
  line-height: 1.75;
  color: var(--text-primary);
}
.msg-content :deep(p)          { margin: 0 0 12px; }
.msg-content :deep(p:last-child) { margin-bottom: 0; }
.msg-content :deep(ul),
.msg-content :deep(ol)         { padding-left: 22px; margin: 0 0 12px; }
.msg-content :deep(li)         { margin-bottom: 4px; }
.msg-content :deep(strong)     { font-weight: 600; }
.msg-content :deep(h1),
.msg-content :deep(h2),
.msg-content :deep(h3),
.msg-content :deep(h4)         { margin: 16px 0 8px; font-weight: 600; line-height: 1.3; }
.msg-content :deep(h1)         { font-size: 20px; }
.msg-content :deep(h2)         { font-size: 18px; }
.msg-content :deep(h3)         { font-size: 16px; }
.msg-content :deep(h4)         { font-size: 14px; }
.msg-content :deep(blockquote) {
  border-left: 3px solid var(--color-accent);
  padding: 4px 0 4px 14px;
  margin: 12px 0;
  color: var(--text-secondary);
}
.msg-content :deep(table) {
  border-collapse: collapse;
  margin: 12px 0;
  width: 100%;
  font-size: 14px;
}
.msg-content :deep(th),
.msg-content :deep(td) {
  border: 1px solid var(--border-subtle);
  padding: 8px 12px;
  text-align: left;
}
.msg-content :deep(th) {
  background: rgba(255,255,255,0.03);
  font-weight: 600;
  font-size: 13px;
}
.msg-content :deep(hr) {
  border: none;
  border-top: 1px solid var(--border-subtle);
  margin: 16px 0;
}
.msg-content :deep(a) {
  color: var(--color-accent-subtle);
  text-decoration: underline;
}
.msg-content :deep(code) {
  font-family: var(--font-mono);
  font-size: 13px;
  background: rgba(0,0,0,0.2);
  padding: 2px 6px;
  border-radius: 4px;
}
.msg-content :deep(pre) {
  background: #0d1117;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: 16px;
  margin: 12px 0;
  overflow-x: auto;
}
.msg-content :deep(pre code) {
  background: none;
  padding: 0;
  font-size: 13px;
  line-height: 1.6;
}

/* ---- Thinking ---- */
.msg-thinking {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
}
.msg-thinking.tool-mode {
  gap: 0;
}
.thinking-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--text-tertiary);
  animation: dotBounce 1.4s infinite ease-in-out;
}
.thinking-dot:nth-child(1) { animation-delay: 0s; }
.thinking-dot:nth-child(2) { animation-delay: 0.2s; }
.thinking-dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes dotBounce {
  0%, 80%, 100% { opacity: 0.2; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-3px); }
}
.thinking-label {
  font-size: 14px;
  color: var(--text-tertiary);
  margin-left: 4px;
}

/* ---- Cursor ---- */
.cursor {
  display: inline-block;
  width: 1.5px;
  height: 18px;
  background: var(--color-accent);
  animation: blink 0.7s infinite;
  vertical-align: text-bottom;
  border-radius: 1px;
  margin-left: 1px;
}

/* ---- Tools ---- */
.msg-tools {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}
</style>
