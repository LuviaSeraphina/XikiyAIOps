<template>
  <div class="stage-block" :class="{ open }">
    <div class="stage-header" @click="$emit('toggle')">
      <slot name="header" />
      <svg class="arrow" :class="{ rotated: open }" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
        <polyline points="6 9 12 15 18 9" />
      </svg>
    </div>
    <div v-show="open" class="stage-body">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ open: boolean }>()
defineEmits<{ toggle: [] }>()
</script>

<style scoped>
.stage-block {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  overflow: hidden;
  transition: border-color var(--dur-base) var(--ease-spring),
              background var(--dur-base) var(--ease-spring);
}
.stage-block.open {
  border-color: rgba(107, 138, 255, 0.2);
  background: var(--color-accent-soft);
}

.stage-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  cursor: pointer;
  user-select: none;
  font-size: 13px;
  transition: background var(--dur-quick) var(--ease-spring);
}
.stage-header:hover {
  background: var(--bg-hover);
}

.stage-num {
  width: 22px; height: 22px;
  border-radius: var(--radius-sm);
  background: var(--bg-hover);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  color: var(--text-secondary);
  flex-shrink: 0;
  font-family: var(--font-mono);
}
.stage-num-sec {
  background: var(--color-warning-soft) !important;
  color: var(--color-warning) !important;
}

.stage-name {
  font-weight: 500;
  color: var(--text-primary);
  flex: 1;
}

.stage-extra {
  font-size: 11px;
  color: var(--text-tertiary);
  white-space: nowrap;
  font-family: var(--font-mono);
}

.arrow {
  flex-shrink: 0;
  color: var(--text-tertiary);
  transition: transform var(--dur-base) var(--ease-spring);
}
.arrow.rotated {
  transform: rotate(180deg);
}

.stage-body {
  padding: 2px 14px 14px;
}
</style>
