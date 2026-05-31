<template>
  <div class="dashboard">
    <!-- ====== 统计卡片行 ====== -->
    <div class="stat-row">
      <div class="stat-card">
        <div class="stat-icon cpu-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
            <rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/>
            <line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/>
            <line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/>
            <line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/>
            <line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/>
          </svg>
        </div>
        <div class="stat-body">
          <span class="stat-value" :class="cpuStatusClass">{{ cpuPercent }}%</span>
          <span class="stat-label">CPU 使用率</span>
        </div>
        <div class="stat-spark">
          <span class="stat-detail">{{ cpuCores }} 核 · Load {{ loadAvg }}</span>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon mem-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
            <rect x="2" y="6" width="20" height="12" rx="2"/>
            <line x1="6" y1="10" x2="6" y2="14"/><line x1="9" y1="10" x2="9" y2="14"/>
            <line x1="12" y1="10" x2="12" y2="14"/><line x1="15" y1="10" x2="15" y2="14"/>
            <line x1="18" y1="10" x2="18" y2="14"/>
          </svg>
        </div>
        <div class="stat-body">
          <span class="stat-value" :class="memStatusClass">{{ memPercent }}%</span>
          <span class="stat-label">内存使用率</span>
        </div>
        <div class="stat-spark">
          <span class="stat-detail">{{ memUsed }} / {{ memTotal }} GB</span>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon disk-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
            <ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
          </svg>
        </div>
        <div class="stat-body">
          <span class="stat-value" :class="diskStatusClass">{{ diskMaxPercent }}%</span>
          <span class="stat-label">磁盘峰值</span>
        </div>
        <div class="stat-spark">
          <span class="stat-detail">{{ diskCount }} 个挂载点</span>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon net-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
            <circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/>
            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
          </svg>
        </div>
        <div class="stat-body">
          <span class="stat-value">{{ establishedConns }}</span>
          <span class="stat-label">活跃连接</span>
        </div>
        <div class="stat-spark">
          <span class="stat-detail">{{ listeningPorts }} 端口监听</span>
        </div>
      </div>
    </div>

    <!-- ====== 主面板：CPU & 内存 (跨两列) ====== -->
    <div class="grid-span">
      <CpuMemoryPanel />
    </div>

    <!-- ====== 磁盘 + 安全告警 ====== -->
    <DiskPanel />
    <SecurityAlertsPanel />

    <!-- ====== 进程 TOP N (跨两列) ====== -->
    <div class="grid-span">
      <ProcessTopTable />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useSystemStore } from '@/stores/system'
import CpuMemoryPanel from '@/components/dashboard/CpuMemoryPanel.vue'
import DiskPanel from '@/components/dashboard/DiskPanel.vue'
import ProcessTopTable from '@/components/dashboard/ProcessTopTable.vue'
import SecurityAlertsPanel from '@/components/dashboard/SecurityAlertsPanel.vue'

const store = useSystemStore()

// ---- Stat card computed ----
const cpuPercent = computed(() => store.summary?.cpu_percent?.toFixed(1) ?? '--')
const cpuCores = computed(() => store.summary?.cpu_cores ?? '--')
const loadAvg = computed(() => store.summary?.load_avg?.[0]?.toFixed(1) ?? '--')

const memPercent = computed(() => store.summary?.memory_percent?.toFixed(1) ?? '--')
const memUsed = computed(() => store.summary?.memory_used_gb?.toFixed(1) ?? '--')
const memTotal = computed(() => store.summary?.memory_total_gb?.toFixed(1) ?? '--')

const diskMaxPercent = computed(() => {
  if (!store.disks.length) return '--'
  return Math.max(...store.disks.map(d => d.usage_percent)).toFixed(0)
})
const diskCount = computed(() => store.disks.length)

const establishedConns = computed(() => store.network?.tcp_established ?? '--')
const listeningPorts = computed(() => store.network?.listening_ports ?? '--')

// Status classes
function statusClass(pct: number): string {
  if (pct >= 90) return 'danger'
  if (pct >= 70) return 'warning'
  return 'safe'
}
const cpuStatusClass = computed(() => statusClass(+(cpuPercent.value || 0)))
const memStatusClass = computed(() => statusClass(+(memPercent.value || 0)))
const diskStatusClass = computed(() => {
  const v = diskMaxPercent.value
  if (v === '--') return ''
  return statusClass(+v)
})

onMounted(() => {
  store.refreshAll()
})
</script>

<style scoped>
.dashboard {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  padding: 20px;
  max-width: 1440px;
  margin: 0 auto;
}

.grid-span {
  grid-column: 1 / -1;
}

/* ====== Stat Cards ====== */
.stat-row {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  transition: all var(--duration-normal) var(--ease-out);
}
.stat-card:hover {
  border-color: var(--border-emphasis);
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

.stat-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border-radius: var(--radius-md);
  flex-shrink: 0;
}
.cpu-icon { background: rgba(59,130,246,0.12); color: var(--color-accent); }
.mem-icon { background: rgba(34,197,94,0.12); color: var(--color-safe); }
.disk-icon { background: rgba(245,158,11,0.12); color: var(--color-warning); }
.net-icon { background: rgba(139,92,246,0.12); color: #a78bfa; }

.stat-body {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.stat-value {
  font-size: 22px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
  color: var(--text-primary);
}
.stat-value.safe    { color: var(--color-safe); }
.stat-value.warning { color: var(--color-warning); }
.stat-value.danger  { color: var(--color-danger); }
.stat-label {
  font-size: 11px;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.4px;
  font-weight: 500;
}

.stat-spark {
  margin-left: auto;
  flex-shrink: 0;
}
.stat-detail {
  font-size: 11px;
  color: var(--text-tertiary);
  white-space: nowrap;
}
</style>
