<template>
  <div class="chat-input-area">
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
  padding: 0 20px 24px;
  background: var(--bg-root);
}

/* ── Input row ── */
.input-row {
  display: flex;
  justify-content: center;
}

.input-wrapper {
  width: 776px;
  min-height: 123px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: 16px;
  padding: 14px 12px 14px 18px;
  transition: border-color var(--dur-quick), box-shadow var(--dur-quick);
}
.input-wrapper:focus-within {
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px var(--color-accent-soft);
}

.chat-textarea {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: 14px;
  line-height: 1.5;
  resize: none;
  outline: none;
  max-height: 200px;
  min-height: 56px;
  padding: 0;
  align-self: stretch;
}
.chat-textarea::placeholder {
  color: var(--text-placeholder);
}
.chat-textarea:disabled {
  opacity: 0.5;
}

.send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 10px;
  background: var(--bg-hover);
  color: var(--text-tertiary);
  cursor: pointer;
  flex-shrink: 0;
  align-self: flex-end;
  transition: all var(--dur-quick);
}
.send-btn.active {
  background: var(--color-accent);
  color: #fff;
}
.send-btn.active:hover {
  background: var(--color-accent-hover);
}
.send-btn:disabled {
  cursor: not-allowed;
}
</style>
