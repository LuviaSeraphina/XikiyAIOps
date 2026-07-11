<template>
  <div class="chat-page">
    <!-- 历史侧栏 -->
    <aside class="history-sidebar" :class="{ open: historyOpen }">
      <div class="history-header">
        <h3>对话历史</h3>
        <button class="icon-btn" @click="historyOpen = false" title="关闭">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
      <div class="history-list">
        <div v-if="store.historyLoading" class="history-loading">加载中...</div>
        <div
          v-for="conv in store.conversations"
          :key="conv.id"
          class="history-item"
          :class="{ active: conv.session_id === store.currentSessionId }"
          @click="loadSession(conv.session_id)"
        >
          <span class="history-title">{{ conv.title || '(空对话)' }}</span>
          <span class="history-time">{{ formatDate(conv.updated_at) }}</span>
        </div>
        <div v-if="!store.historyLoading && store.conversations.length === 0" class="history-empty">
          暂无历史对话
        </div>
      </div>
    </aside>

    <!-- 主聊天区 -->
    <div class="chat-main">
      <!-- 顶部工具栏 -->
      <div class="chat-toolbar">
        <button class="icon-btn" @click="historyOpen = !historyOpen" title="历史对话">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
          </svg>
        </button>
        <span class="session-id">{{ store.currentSessionId.slice(0, 8) }}...</span>
        <button class="icon-btn" @click="newSession" title="新对话" :disabled="store.streaming">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
        </button>
      </div>

      <!-- 欢迎引导 -->
      <div v-if="store.messages.length === 0" class="welcome">
        <div class="welcome-hero">
          <div class="welcome-icon-wrap">
            <svg width="56" height="56" viewBox="0 0 64 64" fill="none">
              <rect width="64" height="64" rx="20" fill="rgba(107,138,255,0.08)" />
              <path d="M32 16L18 26v12l14 10 14-10V26L32 16z" stroke="var(--color-accent)" stroke-width="2" stroke-linejoin="round" fill="none" />
              <circle cx="32" cy="30" r="5" fill="var(--color-accent)" opacity="0.6" />
              <path d="M22 40l10 7 10-7" stroke="var(--color-accent)" stroke-width="1.5" stroke-linecap="round" fill="none" opacity="0.4" />
            </svg>
          </div>
          <h1 class="welcome-title">XikiyAIOps Agent</h1>
          <p class="welcome-desc">通过自然语言对话，感知系统状态、排查故障、执行运维操作</p>

        </div>
        <ChatInput :disabled="store.streaming" @send="store.sendMessage" />
      </div>

      <!-- 消息列表 -->
      <template v-else>
        <div ref="listRef" class="message-list">
          <ChatBubble
            v-for="msg in store.messages"
            :key="msg.id"
            :message="msg"
            :streaming="store.streaming && msg.id === store.lastAgentId"
          />
        </div>
        <ChatInput :disabled="store.streaming" @send="store.sendMessage" />
      </template>

      <!-- 确认弹窗 -->
      <ConfirmDialog />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import ChatBubble from '@/components/chat/ChatBubble.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import ConfirmDialog from '@/components/chat/ConfirmDialog.vue'

const store = useChatStore()
const listRef = ref<HTMLDivElement>()
const historyOpen = ref(false)

// 自动滚动到底部
watch(
  () => store.messages.length,
  () => nextTick(() => listRef.value?.scrollTo({ top: listRef.value.scrollHeight, behavior: 'smooth' })),
)
watch(
  () => {
    const msgs = store.messages
    return msgs.length ? msgs[msgs.length - 1]?.content?.length ?? 0 : 0
  },
  () => nextTick(() => listRef.value?.scrollTo({ top: listRef.value.scrollHeight, behavior: 'auto' })),
)

function newSession() {
  store.newSession()
}

function loadSession(sessionId: string) {
  store.loadSession(sessionId)
  historyOpen.value = false
}

function formatDate(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 86400000) return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

onMounted(() => {
  store.loadConversations()
})
</script>

<style scoped>
.chat-page {
  display: flex;
  height: 100vh;
}

/* ── 历史侧栏 ── */
.history-sidebar {
  /* dark overrides for history sidebar */
  --hs-bg: #1a1b26;
  --hs-border: rgba(255, 255, 255, 0.06);
  --hs-text: #e8e8f0;
  --hs-text-muted: #8a8da0;
  --hs-text-dim: #555870;
  --hs-hover: rgba(255, 255, 255, 0.06);

  width: 0;
  overflow: hidden;
  background: var(--hs-bg);
  border-right: 1px solid var(--hs-border);
  transition: width var(--dur-gentle) var(--ease-spring);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}
.history-sidebar.open {
  width: 260px;
}
.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--hs-border);
}
.history-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--hs-text);
}
.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.history-item {
  padding: 10px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--dur-quick) var(--ease-spring);
}
.history-item:hover {
  background: var(--hs-hover);
}
.history-item.active {
  background: rgba(77, 107, 254, 0.15);
}
.history-title {
  display: block;
  font-size: 13px;
  color: var(--hs-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.history-time {
  font-size: 11px;
  color: var(--hs-text-dim);
}
.history-empty {
  text-align: center;
  color: var(--hs-text-dim);
  font-size: 13px;
  padding: 32px 0;
}

/* ── 主聊天区 ── */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: transparent;
}

.chat-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: var(--bg-elevated);
  border-bottom: 1px solid var(--border-default);
  flex-shrink: 0;
}
.session-id {
  font-size: 12px;
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  flex: 1;
}

.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--dur-quick) var(--ease-spring);
}
.icon-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}
.icon-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* ── Welcome ── */
.welcome {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 0 24px;
  gap: 36px;
}
.welcome-hero {
  text-align: center;
}
.welcome-icon-wrap {
  margin-bottom: 20px;
  display: inline-flex;
}
.welcome-title {
  font-size: 26px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 10px;
  letter-spacing: -0.5px;
}
.welcome-desc {
  font-size: 14px;
  color: var(--text-secondary);
  max-width: 380px;
  line-height: 1.7;
  margin: 0 auto 20px;
}


/* ── Message list ── */
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px 0;
}

@media (min-width: 800px) {
  .message-list {
    padding: 20px calc((100% - var(--chat-max-width)) / 2);
  }
}
</style>
