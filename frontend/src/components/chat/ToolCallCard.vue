<template>
  <div class="tool-card" :class="[`status-${toolCall.status}`]">
    <!-- Header -->
    <div class="tool-header" @click="expanded = !expanded">
      <span class="tool-status-icon">{{ statusIcon }}</span>
      <code class="tool-name">{{ toolCall.tool_name }}</code>
      <span v-if="toolCall.risk_level" class="risk-tag" :class="`risk-${toolCall.risk_level}`">
        {{ riskLabel }}
      </span>
      <svg
        class="expand-icon"
        :class="{ expanded }"
        width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"
      >
        <polyline points="9 18 15 12 9 6" />
      </svg>
    </div>

    <!-- Expanded detail -->
    <transition name="slide-up">
      <div v-show="expanded" class="tool-detail">
        <div class="detail-section">
          <span class="detail-label">参数</span>
          <pre class="code-block">{{ formattedArgs }}</pre>
        </div>
        <div v-if="toolCall.result !== undefined" class="detail-section">
          <span class="detail-label">结果</span>
          <pre class="code-block">{{ formattedResult }}</pre>
        </div>
      </div>
    </transition>

    <!-- Running bar -->
    <div v-if="toolCall.status === 'running'" class="running-bar" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { ToolCall, RiskLevel } from '@/types'

const props = defineProps<{ toolCall: ToolCall }>()
const expanded = ref(false)

const statusIcon = computed(() => {
  switch (props.toolCall.status) {
    case 'pending': return '○'
    case 'running': return '◌'
    case 'done':    return '●'
    case 'error':   return '✕'
    default:        return '○'
  }
})

const riskLabel = computed(() => {
  switch (props.toolCall.risk_level) {
    case 'read_only':  return '只读'
    case 'restricted': return '受限'
    case 'dangerous':  return '高危'
    default:           return ''
  }
})

const formattedArgs = computed(() => {
  try { return JSON.stringify(props.toolCall.arguments, null, 2) }
  catch { return String(props.toolCall.arguments) }
})

const formattedResult = computed(() => {
  if (typeof props.toolCall.result === 'string') return props.toolCall.result
  try { return JSON.stringify(props.toolCall.result, null, 2) }
  catch { return String(props.toolCall.result) }
})
</script>

<style scoped>
.tool-card {
  background: var(--bg-code);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  font-size: 13px;
  overflow: hidden;
  transition: border-color var(--dur-quick);
}
.tool-card:hover {
  border-color: var(--border-default);
}
.status-running { border-left: 3px solid var(--color-accent); }
.status-done    { border-left: 3px solid var(--color-safe); }
.status-error   { border-left: 3px solid var(--color-danger); }

.tool-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  user-select: none;
}
.tool-status-icon {
  font-size: 10px;
}
.tool-name {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-primary);
  flex: 1;
}
.risk-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 600;
}
.risk-read_only  { background: var(--color-safe-soft); color: var(--color-safe); }
.risk-restricted { background: var(--color-warning-soft); color: var(--color-warning); }
.risk-dangerous  { background: var(--color-danger-soft); color: var(--color-danger); }

.expand-icon {
  flex-shrink: 0;
  transition: transform var(--dur-quick);
  color: var(--text-tertiary);
}
.expand-icon.expanded {
  transform: rotate(90deg);
}

.tool-detail {
  border-top: 1px solid var(--border-subtle);
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.detail-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.detail-label {
  font-size: 11px;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.code-block {
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-secondary);
  background: var(--bg-root);
  padding: 8px 10px;
  border-radius: 6px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.running-bar {
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--color-accent), transparent);
  animation: runningSlide 1.5s infinite ease-in-out;
}
@keyframes runningSlide {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}
</style>
