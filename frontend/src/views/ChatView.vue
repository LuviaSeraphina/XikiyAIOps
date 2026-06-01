<template>
  <div class="chat-page">
    <!-- 欢迎引导 -->
    <div v-if="store.messages.length === 0" class="welcome">
      <div class="welcome-hero">
        <div class="welcome-glow" />
        <div class="welcome-icon">
          <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
            <rect width="64" height="64" rx="18" fill="rgba(59,130,246,0.1)" />
            <path d="M32 16L18 26v12l14 10 14-10V26L32 16z" stroke="#3b82f6" stroke-width="2.5" stroke-linejoin="round" fill="none" />
            <circle cx="32" cy="30" r="5" fill="#3b82f6" />
            <path d="M22 40l10 7 10-7" stroke="#60a5fa" stroke-width="1.5" stroke-linecap="round" fill="none" />
          </svg>
        </div>
        <h1 class="welcome-title">麒麟安全运维 Agent</h1>
        <p class="welcome-desc">通过自然语言对话，感知系统状态、排查故障、执行运维操作</p>
      </div>

      <div class="welcome-cards">
        <button
          v-for="q in quickStarts"
          :key="q.label"
          class="quick-card"
          @click="store.sendMessage(q.text)"
        >
          <span class="quick-icon">{{ q.icon }}</span>
          <div class="quick-info">
            <span class="quick-label">{{ q.label }}</span>
            <span class="quick-hint">{{ q.hint }}</span>
          </div>
        </button>
      </div>
    </div>

    <!-- 消息列表 -->
    <div v-else ref="listRef" class="message-list">
      <ChatBubble
        v-for="msg in store.messages"
        :key="msg.id"
        :message="msg"
        :streaming="store.streaming && msg.id === lastAgentId"
      />
    </div>

    <!-- 确认弹窗 -->
    <ConfirmDialog />

    <!-- 输入框 -->
    <ChatInput :disabled="store.streaming" @send="store.sendMessage" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { useChatStore } from '@/stores/chat'
import ChatBubble from '@/components/chat/ChatBubble.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import ConfirmDialog from '@/components/chat/ConfirmDialog.vue'

const store = useChatStore()
const listRef = ref<HTMLDivElement>()

const lastAgentId = computed(() => {
  const msgs = store.messages
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === 'assistant') return msgs[i].id
  }
  return ''
})

const quickStarts = [
  { icon: '🔍', label: '查看系统状态', hint: 'CPU、内存、磁盘等', text: '帮我看看当前系统状态' },
  { icon: '🧹', label: '检查磁盘空间', hint: '查看各分区使用率', text: '帮我检查磁盘空间使用情况' },
  { icon: '📋', label: '查看进程信息', hint: 'TOP N 进程排行', text: '帮我查看占用最高的进程' },
  { icon: '🛡️', label: '安全审计', hint: '检查登录失败记录', text: '帮我检查最近的登录失败情况' },
  { icon: '🌐', label: '网络状态', hint: '连接数和监听端口', text: '帮我查看当前网络连接状态' },
  { icon: '📊', label: '健康评分', hint: '系统综合健康评估', text: '帮我生成系统健康评分报告' },
]

// 自动滚动到底部
watch(
  () => store.messages.length,
  () => {
    nextTick(() => {
      if (listRef.value) {
        listRef.value.scrollTo({ top: listRef.value.scrollHeight, behavior: 'smooth' })
      }
    })
  },
)

// 持续流式输出时也滚动
watch(
  () => {
    const msgs = store.messages
    return msgs.length ? msgs[msgs.length - 1].content?.length ?? 0 : 0
  },
  () => {
    nextTick(() => {
      if (listRef.value) {
        listRef.value.scrollTo({ top: listRef.value.scrollHeight, behavior: 'auto' })
      }
    })
  },
)
</script>

<style scoped>
.chat-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - var(--header-height));
}

/* ---- Welcome ---- */
.welcome {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 24px;
}

.welcome-hero {
  text-align: center;
  margin-bottom: 40px;
  position: relative;
}
.welcome-glow {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 200px;
  height: 200px;
  border-radius: 50%;
  background: radial-gradient(circle, var(--color-accent-glow), transparent 70%);
  pointer-events: none;
}
.welcome-icon {
  position: relative;
  margin-bottom: 20px;
  display: inline-flex;
}
.welcome-title {
  font-size: 26px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 8px;
  position: relative;
}
.welcome-desc {
  font-size: 15px;
  color: var(--text-secondary);
  max-width: 400px;
  position: relative;
}

/* Quick cards */
.welcome-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  max-width: 660px;
  width: 100%;
}

.quick-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  cursor: pointer;
  text-align: left;
  color: var(--text-primary);
  transition: all var(--duration-normal) var(--ease-out);
}
.quick-card:hover {
  border-color: var(--color-accent);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.quick-icon {
  font-size: 24px;
  flex-shrink: 0;
}
.quick-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.quick-label {
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}
.quick-hint {
  font-size: 11px;
  color: var(--text-tertiary);
  white-space: nowrap;
}

/* ---- Message list ---- */
.message-list {
  flex: 1;
  overflow-y: auto;
  scroll-behavior: smooth;
  padding: 0 24px;
}

/* Center messages on wide screens */
@media (min-width: 900px) {
  .message-list {
    padding: 0 calc((100% - 800px) / 2);
  }
}
</style>
