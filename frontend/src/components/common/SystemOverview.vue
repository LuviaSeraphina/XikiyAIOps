<template>
  <div class="system-overview">
    <!-- CPU -->
    <div class="metric-chip">
      <div class="metric-ring" :style="cpuRingStyle">
        <svg width="32" height="32" viewBox="0 0 32 32">
          <circle cx="16" cy="16" r="13" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="3" />
          <circle
            cx="16" cy="16" r="13"
            fill="none"
            :stroke="cpuColor"
            stroke-width="3"
            stroke-linecap="round"
            :stroke-dasharray="cpuDashArray"
            :stroke-dashoffset="0"
            transform="rotate(-90 16 16)"
            style="transition: stroke-dasharray 0.6s cubic-bezier(0.16, 1, 0.3, 1)"
          />
        </svg>
      </div>
      <div class="metric-info">
        <span class="metric-value">{{ cpuText }}</span>
        <span class="metric-label">CPU</span>
      </div>
    </div>

    <!-- Memory -->
    <div class="metric-chip">
      <div class="metric-ring">
        <svg width="32" height="32" viewBox="0 0 32 32">
          <circle cx="16" cy="16" r="13" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="3" />
          <circle
            cx="16" cy="16" r="13"
            fill="none"
            :stroke="memColor"
            stroke-width="3"
            stroke-linecap="round"
            :stroke-dasharray="memDashArray"
            :stroke-dashoffset="0"
            transform="rotate(-90 16 16)"
            style="transition: stroke-dasharray 0.6s cubic-bezier(0.16, 1, 0.3, 1)"
          />
        </svg>
      </div>
      <div class="metric-info">
        <span class="metric-value">{{ memText }}</span>
        <span class="metric-label">MEM</span>
      </div>
    </div>

    <!-- Disk -->
    <div class="metric-chip">
      <div class="metric-ring">
        <svg width="32" height="32" viewBox="0 0 32 32">
          <circle cx="16" cy="16" r="13" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="3" />
          <circle
            cx="16" cy="16" r="13"
            fill="none"
            :stroke="diskColor"
            stroke-width="3"
            stroke-linecap="round"
            :stroke-dasharray="diskDashArray"
            :stroke-dashoffset="0"
            transform="rotate(-90 16 16)"
            style="transition: stroke-dasharray 0.6s cubic-bezier(0.16, 1, 0.3, 1)"
          />
        </svg>
      </div>
      <div class="metric-info">
        <span class="metric-value">{{ diskText }}</span>
        <span class="metric-label">DISK</span>
      </div>
    </div>

    <!-- Alerts -->
    <div class="metric-chip alerts" :class="{ 'has-alerts': alertCount > 0 }">
      <div class="alert-icon">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" :stroke="alertCount > 0 ? '#f59e0b' : 'currentColor'" stroke-width="2">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
          <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
        </svg>
      </div>
      <div class="metric-info">
        <span class="metric-value" :class="{ 'text-warning': alertCount >= 5, 'text-danger': alertCount >= 10 }">
          {{ alertCount }}
        </span>
        <span class="metric-label">告警</span>
      </div>
    </div>

    <!-- Uptime -->
    <span class="update-time" v-if="lastUpdateText">
      更新于 {{ lastUpdateText }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useSystemStore } from '@/stores/system'

const store = useSystemStore()

const CIRCUMFERENCE = 2 * Math.PI * 13 // ~81.68

// ---- CPU ----
const cpuPercent = computed(() => +(store.summary?.cpu_percent ?? 0).toFixed(1))
const cpuText = computed(() => store.summary ? `${cpuPercent.value}%` : '--')
const cpuColor = computed(() => {
  if (cpuPercent.value >= 90) return '#ef4444'
  if (cpuPercent.value >= 70) return '#f59e0b'
  return '#22c55e'
})
const cpuDashArray = computed(() => {
  const pct = Math.min(cpuPercent.value / 100, 1)
  return `${(CIRCUMFERENCE * pct).toFixed(1)} ${CIRCUMFERENCE.toFixed(1)}`
})
const cpuRingStyle = computed(() => ({
  filter: cpuPercent.value >= 90 ? 'drop-shadow(0 0 4px rgba(239,68,68,0.4))' : 'none',
}))

// ---- Memory ----
const memPercent = computed(() => +(store.summary?.memory_percent ?? 0).toFixed(1))
const memText = computed(() => store.summary ? `${memPercent.value}%` : '--')
const memColor = computed(() => {
  if (memPercent.value >= 90) return '#ef4444'
  if (memPercent.value >= 70) return '#f59e0b'
  return '#22c55e'
})
const memDashArray = computed(() => {
  const pct = Math.min(memPercent.value / 100, 1)
  return `${(CIRCUMFERENCE * pct).toFixed(1)} ${CIRCUMFERENCE.toFixed(1)}`
})

// ---- Disk ----
const diskPercent = computed(() => {
  const disks = store.disks
  if (!disks.length) return 0
  return Math.max(...disks.map((d) => d.usage_percent))
})
const diskText = computed(() => store.disks.length ? `${diskPercent.value.toFixed(0)}%` : '--')
const diskColor = computed(() => {
  if (diskPercent.value >= 90) return '#ef4444'
  if (diskPercent.value >= 70) return '#f59e0b'
  return '#22c55e'
})
const diskDashArray = computed(() => {
  const pct = Math.min(diskPercent.value / 100, 1)
  return `${(CIRCUMFERENCE * pct).toFixed(1)} ${CIRCUMFERENCE.toFixed(1)}`
})

// ---- Alerts ----
const alertCount = computed(() => store.authFailures.total)

// ---- Uptime ----
const lastUpdateText = computed(() => {
  if (!store.lastUpdate) return ''
  const diff = Math.floor((Date.now() - store.lastUpdate) / 1000)
  if (diff < 60) return `${diff}s ago`
  return `${Math.floor(diff / 60)}m ago`
})

// ---- Polling ----
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
  gap: 4px;
}

.metric-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 12px 5px 6px;
  border-radius: var(--radius-lg);
  transition: background var(--duration-fast) var(--ease-out);
}
.metric-chip:hover {
  background: var(--bg-surface);
}

.metric-ring {
  display: flex;
  flex-shrink: 0;
}

.metric-info {
  display: flex;
  flex-direction: column;
  gap: 0;
  min-width: 36px;
}
.metric-value {
  font-size: 13px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--text-primary);
  line-height: 1.2;
}
.metric-label {
  font-size: 10px;
  font-weight: 500;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  line-height: 1.2;
}

/* Alerts chip */
.alerts.has-alerts {
  background: rgba(245, 158, 11, 0.08);
}
.alert-icon {
  display: flex;
  color: var(--text-tertiary);
}

.update-time {
  margin-left: 8px;
  font-size: 11px;
  color: var(--text-tertiary);
  white-space: nowrap;
}
</style>
