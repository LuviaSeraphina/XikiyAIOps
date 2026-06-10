<template>
  <div class="dashboard">
    <!-- ====== 统计卡片行 ====== -->
    <div class="stat-row">
      <!-- 健康评分（来自最新对话） -->
      <div class="stat-card health-card" v-if="healthScore">
        <div class="stat-icon health-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
            <polyline points="22 4 12 14.01 9 11.01"/>
          </svg>
        </div>
        <div class="stat-body">
          <span class="stat-value" :class="gradeClass">{{ healthScore.score }}/100</span>
          <span class="stat-label">健康评分</span>
        </div>
        <div class="stat-spark">
          <span class="stat-detail">{{ healthScore.grade }}</span>
        </div>
      </div>

      <div class="stat-card" v-if="snap.cpuCores !== undefined">
        <div class="stat-icon cpu-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
            <rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/>
            <line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/>
          </svg>
        </div>
        <div class="stat-body">
          <span class="stat-value">{{ snap.cpuCores }} 核</span>
          <span class="stat-label">CPU</span>
        </div>
        <div class="stat-spark">
          <span class="stat-detail" v-if="snap.load1m !== undefined">Load {{ snap.load1m?.toFixed(1) }}</span>
        </div>
      </div>

      <div class="stat-card" v-if="snap.memoryTotalGb !== undefined">
        <div class="stat-icon mem-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
            <rect x="2" y="6" width="20" height="12" rx="2"/>
            <line x1="6" y1="10" x2="6" y2="14"/><line x1="9" y1="10" x2="9" y2="14"/>
          </svg>
        </div>
        <div class="stat-body">
          <span class="stat-value" :class="memStatusClass">{{ snap.memoryPercent?.toFixed(0) ?? '--' }}%</span>
          <span class="stat-label">内存使用率</span>
        </div>
        <div class="stat-spark">
          <span class="stat-detail">{{ snap.memoryUsedGb?.toFixed(1) }} / {{ snap.memoryTotalGb?.toFixed(1) }} GB</span>
        </div>
      </div>

      <div class="stat-card" v-if="snap.diskRootTotalGb !== undefined">
        <div class="stat-icon disk-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
            <ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
          </svg>
        </div>
        <div class="stat-body">
          <span class="stat-value" :class="diskStatusClass">{{ snap.diskRootPercent?.toFixed(0) ?? '--' }}%</span>
          <span class="stat-label">磁盘 / 使用率</span>
        </div>
        <div class="stat-spark">
          <span class="stat-detail">{{ snap.diskRootUsedGb?.toFixed(1) }} / {{ snap.diskRootTotalGb?.toFixed(1) }} GB</span>
        </div>
      </div>

      <div class="stat-card" v-if="snap.listeningPorts !== undefined">
        <div class="stat-icon net-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
            <circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/>
          </svg>
        </div>
        <div class="stat-body">
          <span class="stat-value">{{ snap.tcpEstablished ?? '--' }}</span>
          <span class="stat-label">活跃连接</span>
        </div>
        <div class="stat-spark">
          <span class="stat-detail">{{ snap.listeningPorts }} 端口监听</span>
        </div>
      </div>
    </div>

    <!-- ====== 系统概览面板 ====== -->
    <div v-if="snap.hostname" class="panel-card">
      <div class="panel-header">
        <h3 class="panel-title">系统概览</h3>
      </div>
      <div class="system-overview-grid">
        <div class="overview-item">
          <span class="overview-label">主机名</span>
          <span class="overview-value">{{ snap.hostname }}</span>
        </div>
        <div class="overview-item">
          <span class="overview-label">操作系统</span>
          <span class="overview-value">{{ snap.os }}</span>
        </div>
        <div class="overview-item">
          <span class="overview-label">内核版本</span>
          <span class="overview-value">{{ snap.kernel }}</span>
        </div>
        <div class="overview-item">
          <span class="overview-label">启动时间</span>
          <span class="overview-value">{{ snap.bootTime }}</span>
        </div>
        <div class="overview-item" v-if="snap.swapTotalGb !== undefined && snap.swapTotalGb > 0">
          <span class="overview-label">Swap</span>
          <span class="overview-value">{{ snap.swapUsedGb?.toFixed(1) }} / {{ snap.swapTotalGb?.toFixed(1) }} GB ({{ snap.swapPercent?.toFixed(0) }}%)</span>
        </div>
        <div class="overview-item" v-if="snap.authFailures !== undefined">
          <span class="overview-label">认证失败</span>
          <span class="overview-value" :class="{ 'text-danger': snap.authFailures > 10 }">{{ snap.authFailures }} 次</span>
        </div>
      </div>
    </div>

    <!-- ====== 空状态 ====== -->
    <div v-if="!hasData" class="empty-dashboard">
      <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" opacity="0.35">
        <rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/>
        <rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>
      </svg>
      <h3>暂无系统数据</h3>
      <p>前往 <router-link to="/chat">智能对话</router-link> 输入"查看系统状态"以获取实时系统信息。</p>
    </div>

    <!-- ====== 健康告警 ====== -->
    <div v-if="healthScore && healthScore.alerts && healthScore.alerts.length > 0" class="panel-card alerts-panel">
      <div class="panel-header">
        <h3 class="panel-title">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2" stroke-linecap="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/>
          </svg>
          健康告警
        </h3>
      </div>
      <div class="alerts-list">
        <div v-for="(alert, idx) in healthScore.alerts" :key="idx" class="alert-item">
          <span class="alert-dot" />
          <span>{{ alert }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useSystemStore } from '@/stores/system'
import { useChatStore } from '@/stores/chat'

const systemStore = useSystemStore()
const chatStore = useChatStore()

const snap = computed(() => systemStore.snapshot)
const hasData = computed(() => systemStore.hasData)
const healthScore = computed(() => chatStore.lastHealthScore)

// 状态颜色
function statusClass(pct: number): string {
  if (pct >= 90) return 'danger'
  if (pct >= 70) return 'warning'
  return 'safe'
}
const memStatusClass = computed(() => {
  const v = snap.value.memoryPercent
  return v !== undefined ? statusClass(v) : ''
})
const diskStatusClass = computed(() => {
  const v = snap.value.diskRootPercent
  return v !== undefined ? statusClass(v) : ''
})
const gradeClass = computed(() => {
  const g = healthScore.value?.grade
  if (!g) return ''
  if (g === 'A' || g === 'B') return 'safe'
  if (g === 'C') return 'warning'
  return 'danger'
})

onMounted(() => {
  systemStore.extractFromChat()
})
</script>

<style scoped>
.dashboard {
  padding: 24px;
  max-width: 960px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ── Stat Cards ── */
.stat-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 12px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 18px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: 10px;
  transition: border-color var(--dur-quick);
}
.stat-card:hover {
  border-color: var(--border-default);
}

.stat-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 8px;
  flex-shrink: 0;
}
.cpu-icon { background: var(--color-accent-soft); color: var(--color-accent-text); }
.mem-icon { background: var(--color-safe-soft); color: var(--color-safe); }
.disk-icon { background: var(--color-warning-soft); color: var(--color-warning); }
.net-icon { background: rgba(139,92,246,0.1); color: #8b5cf6; }
.health-icon { background: var(--color-safe-soft); color: var(--color-safe); }

.stat-body {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.stat-value {
  font-size: 20px;
  font-weight: 650;
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
  letter-spacing: 0.3px;
  font-weight: 500;
  margin-top: 2px;
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

/* ── Panel Card ── */
.panel-card {
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: 10px;
  padding: 20px;
}
.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}
.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

/* ── System Overview Grid ── */
.system-overview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}
.overview-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.overview-label {
  font-size: 11px;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.4px;
}
.overview-value {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
  font-family: var(--font-mono);
}

/* ── Empty State ── */
.empty-dashboard {
  text-align: center;
  padding: 80px 20px;
  color: var(--text-secondary);
}
.empty-dashboard h3 {
  margin: 16px 0 8px;
  font-size: 17px;
  color: var(--text-primary);
  font-weight: 600;
}
.empty-dashboard p {
  font-size: 14px;
  max-width: 400px;
  margin: 0 auto;
}
.empty-dashboard a {
  color: var(--color-accent-text);
  font-weight: 500;
}

/* ── Alerts ── */
.alerts-panel {
  border-color: var(--color-warning-soft);
}
.alerts-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.alert-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  color: var(--text-primary);
  padding: 8px 12px;
  background: var(--color-warning-soft);
  border-radius: 6px;
}
.alert-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--color-warning);
  margin-top: 5px;
  flex-shrink: 0;
}
</style>
