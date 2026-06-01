<template>
  <div class="chat-input-area">
    <!-- 快捷指令 -->
    <div class="quick-chips">
      <button
        v-for="q in quickList"
        :key="q.label"
        class="quick-chip"
        @click="emit('send', q.text)"
      >
        {{ q.icon }} {{ q.label }}
      </button>
    </div>

    <!-- 输入行 -->
    <div class="input-row">
      <div class="input-wrapper">
        <textarea
          ref="textareaRef"
          v-model="text"
          :disabled="disabled"
          class="chat-textarea"
          placeholder="输入运维指令，Enter 发送，Shift+Enter 换行..."
          rows="1"
          @keydown="onKeydown"
          @input="autoResize"
        />
        <button
          class="send-btn"
          :class="{ active: text.trim() && !disabled }"
          :disabled="disabled || !text.trim()"
          @click="send"
          :title="disabled ? 'Agent 正在回复...' : '发送消息'"
        >
          <svg v-if="!disabled" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
          <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <rect x="6" y="6" width="12" height="12" rx="2"/>
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'

defineProps<{ disabled: boolean }>()
const emit = defineEmits<{ send: [text: string] }>()

const text = ref('')
const textareaRef = ref<HTMLTextAreaElement>()

const quickList = [
  { icon: '🔍', label: '系统状态', text: '帮我看看当前系统状态' },
  { icon: '🧹', label: '磁盘检查', text: '帮我检查磁盘空间使用情况' },
  { icon: '📋', label: '进程检查', text: '帮我查看占用最高的进程' },
  { icon: '🛡️', label: '安全审计', text: '帮我检查最近的登录失败情况' },
]

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

function send() {
  const msg = text.value.trim()
  if (!msg) return
  emit('send', msg)
  text.value = ''
  nextTick(() => {
    autoResize()
    textareaRef.value?.focus()
  })
}

function autoResize() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 150) + 'px'
}

onMounted(() => {
  nextTick(() => textareaRef.value?.focus())
})
</script>

<style scoped>
.chat-input-area {
  padding: 0 24px 20px;
  background: transparent;
}

/* Center on wide screens */
@media (min-width: 900px) {
  .chat-input-area {
    padding: 0 calc((100% - 800px) / 2) 20px;
  }
}

/* Quick chips */
.quick-chips {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
  flex-wrap: wrap;
  justify-content: center;
}
.quick-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  background: transparent;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}
.quick-chip:hover {
  color: var(--text-primary);
  border-color: var(--border-emphasis);
  background: var(--bg-surface);
}

/* Input row */
.input-row {
  display: flex;
}

.input-wrapper {
  flex: 1;
  display: flex;
  align-items: flex-end;
  gap: 8px;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: 20px;
  padding: 10px 8px 10px 18px;
  transition: border-color var(--duration-fast) var(--ease-out);
}
.input-wrapper:focus-within {
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px var(--color-accent-soft);
}

.chat-textarea {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: 15px;
  line-height: 1.5;
  resize: none;
  min-height: 24px;
  max-height: 150px;
}
.chat-textarea::placeholder {
  color: var(--text-tertiary);
}
.chat-textarea:disabled {
  opacity: 0.5;
}

.send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  flex-shrink: 0;
  transition: all var(--duration-fast) var(--ease-out);
}
.send-btn.active {
  background: var(--color-accent);
  color: #fff;
}
.send-btn.active:hover {
  background: #2563eb;
  transform: scale(1.05);
}
.send-btn:disabled {
  cursor: not-allowed;
}
</style>
