<template>
  <el-tag :type="tagType" :size="size" :effect="effect">
    <slot>{{ label }}</slot>
  </el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { RiskLevel } from '@/types'

const props = withDefaults(
  defineProps<{
    riskLevel: RiskLevel
    size?: 'small' | 'default' | 'large'
    effect?: 'dark' | 'light' | 'plain'
  }>(),
  { size: 'small', effect: 'dark' },
)

const tagType = computed(() => {
  switch (props.riskLevel) {
    case 'read_only':  return 'success'
    case 'restricted': return 'warning'
    case 'dangerous':  return 'danger'
    default:           return 'info'
  }
})

const label = computed(() => {
  switch (props.riskLevel) {
    case 'read_only':  return '🟢 安全'
    case 'restricted': return '🟡 需确认'
    case 'dangerous':  return '🔴 高危'
    default:           return props.riskLevel
  }
})
</script>
