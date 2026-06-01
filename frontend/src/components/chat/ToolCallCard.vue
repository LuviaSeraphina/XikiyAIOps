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
    <transition name="fade-up">
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
  background: var(--bg-panel);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  font-size: 12.5px;
  overflow: hidden;
  transition: border-color var(--duration-fast) var(--ease-out);
}
.tool-card:hover {
  border-color: var(--border-default);
}

/* Status border */
.status-running { border-left: 3px solid var(--color-accent); }
.status-done    { border-left: 3px solid var(--color-safe); }
.status-error   { border-left: 3px solid var(--color-danger); }

/* Header */
.tool-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  user-select: none;
}
.tool-header:hover {
  background: rgba(255,255,255,0.02);
}

.tool-status-icon {
  font-size: 13px;
  width: 16px;
  text-align: center;
  flex-shrink: 0;
}
.status-done .tool-status-icon    { color: var(--color-safe); }
.status-error .tool-status-icon   { color: var(--color-danger); }
.status-running .tool-status-icon { color: var(--color-accent); animation: blink 1.2s infinite; }

.tool-name {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
}

.risk-tag {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: var(--radius-full);
  letter-spacing: 0.3px;
}
.risk-read_only  { color: var(--color-safe); background: var(--color-safe-soft); }
.risk-restricted { color: var(--color-warning); background: var(--color-warning-soft); }
.risk-dangerous  { color: var(--color-danger); background: var(--color-danger-soft); }

.expand-icon {
  flex-shrink: 0;
  color: var(--text-tertiary);
  transition: transform var(--duration-fast) var(--ease-out);
}
.expand-icon.expanded {
  transform: rotate(90deg);
}

/* Detail */
.tool-detail {
  padding: 0 12px 10px;
}
.detail-section {
  margin-top: 8px;
}
.detail-label {
  display: block;
  font-size: 10px;
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
}
.code-block {
  background: var(--bg-dark);
  color: #5a7af7;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  font-size: 11.5px;
  font-family: var(--font-mono);
  max-height: 140px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.45;
}

/* Running indicator */
.running-bar {
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--color-accent), transparent);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
</style>
