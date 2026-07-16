<template>
  <span class="status-badge" :class="[`risk-${riskLevel}`, size]">
    <span class="status-dot" />
    <slot>{{ label }}</slot>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { RiskLevel } from '@/types'

const props = withDefaults(
  defineProps<{
    riskLevel: RiskLevel
    size?: 'sm' | 'md'
  }>(),
  { size: 'sm' },
)

const label = computed(() => {
  switch (props.riskLevel) {
    case 'read_only':  return '安全'
    case 'restricted': return '需确认'
    case 'dangerous':  return '高危'
    default:           return props.riskLevel
  }
})
</script>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-weight: 600;
  border-radius: 5px;
  white-space: nowrap;
  user-select: none;
}
.status-badge.sm { font-size: 10px; padding: 2px 7px; }
.status-badge.md { font-size: 11px; padding: 3px 9px; }

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.risk-read_only  { background: var(--color-safe-soft); color: var(--color-safe); }
.risk-restricted { background: var(--color-warning-soft); color: var(--color-warning); }
.risk-dangerous  { background: var(--color-danger-soft); color: var(--color-danger); }
.risk-critical   { background: #ede9fe; color: #7c3aed; }

.risk-read_only .status-dot  { background: var(--color-safe); }
.risk-restricted .status-dot { background: var(--color-warning); }
.risk-dangerous .status-dot  { background: var(--color-danger); }
.risk-critical .status-dot   { background: #7c3aed; }
</style>
