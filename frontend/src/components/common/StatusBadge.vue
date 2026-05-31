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
  border-radius: var(--radius-full);
  white-space: nowrap;
  user-select: none;
}
.status-badge.sm { font-size: 10px; padding: 2px 8px; }
.status-badge.md { font-size: 11px; padding: 3px 10px; }

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

/* Risk levels */
.risk-read_only {
  color: var(--color-safe);
  background: var(--color-safe-soft);
}
.risk-read_only .status-dot { background: var(--color-safe); }

.risk-restricted {
  color: var(--color-warning);
  background: var(--color-warning-soft);
}
.risk-restricted .status-dot { background: var(--color-warning); }

.risk-dangerous {
  color: var(--color-danger);
  background: var(--color-danger-soft);
}
.risk-dangerous .status-dot { background: var(--color-danger); }
</style>
