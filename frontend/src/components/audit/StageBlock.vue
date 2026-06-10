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
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  overflow: hidden;
  transition: border-color 150ms;
}
.stage-block.open {
  border-color: var(--color-accent);
  background: var(--color-accent-soft);
}

.stage-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 12px;
  cursor: pointer;
  user-select: none;
  font-size: 13px;
}
.stage-header:hover {
  background: var(--bg-hover);
}

.stage-num {
  width: 20px; height: 20px;
  border-radius: 5px;
  background: var(--bg-hover);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  flex-shrink: 0;
}
.stage-num-sec {
  background: var(--color-warning-soft);
  color: var(--color-warning);
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
}

.arrow {
  flex-shrink: 0;
  color: var(--text-tertiary);
  transition: transform 150ms;
}
.arrow.rotated {
  transform: rotate(180deg);
}

.stage-body {
  padding: 2px 12px 12px;
}
</style>
