<template>
  <div class="system-overview">
    <el-tag type="info" effect="dark" size="large">
      CPU {{ summary?.cpu_percent?.toFixed(1) ?? '--' }}%
    </el-tag>
    <el-tag type="warning" effect="dark" size="large">
      MEM {{ summary?.memory_percent?.toFixed(1) ?? '--' }}%
    </el-tag>
    <el-tag type="info" effect="dark" size="large">
      DISK {{ diskUsage }}%
    </el-tag>
    <el-tag :type="alertType" effect="dark" size="large">
      ⚠ {{ alertCount }} 告警
    </el-tag>
    <span class="update-time" v-if="lastUpdateText">
      更新于 {{ lastUpdateText }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useSystemStore } from '@/stores/system'

const store = useSystemStore()

const summary = computed(() => store.summary)

const diskUsage = computed(() => {
  const disks = store.disks
  if (!disks.length) return '--'
  const max = Math.max(...disks.map((d) => d.usage_percent))
  return max.toFixed(0)
})

const alertCount = computed(() => store.authFailures.total)

const alertType = computed(() => {
  const t = alertCount.value
  if (t >= 10) return 'danger'
  if (t >= 5) return 'warning'
  return 'info'
})

const lastUpdateText = computed(() => {
  if (!store.lastUpdate) return ''
  const diff = Math.floor((Date.now() - store.lastUpdate) / 1000)
  if (diff < 60) return `${diff} 秒前`
  return `${Math.floor(diff / 60)} 分钟前`
})

let timer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  store.refreshAll()
  timer = setInterval(() => store.refreshAll(), 30_000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.system-overview {
  display: flex;
  align-items: center;
  gap: 14px;
  height: 100%;
  padding: 0 20px;
  background-color: var(--bg-panel);
  border-bottom: 1px solid var(--border-color);
}

.update-time {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
