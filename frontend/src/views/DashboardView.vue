<template>
  <div class="dashboard">
    <!-- ====== 页面标题 ====== -->
    <header class="dash-header">
      <div>
        <h1 class="dash-title">系统监控</h1>
        <p class="dash-subtitle">实时系统状态概览</p>
      </div>
      <div class="header-actions">
        <span class="refresh-indicator" v-if="systemStore.loading">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" class="spinning">
            <circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>
          </svg>
          刷新中
        </span>
        <span class="auto-refresh-tag" v-else>
          <span class="live-dot" />
          实时
        </span>
      </div>
    </header>

    <!-- ====== 统计卡片行 (Bento Grid) ====== -->
    <div class="stat-grid">
      <!-- 健康评分 -->
      <div class="stat-card" v-if="healthScore">
        <div class="card-shell">
          <div class="card-core">
            <div class="stat-top">
              <div class="stat-icon health-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                  <polyline points="22 4 12 14.01 9 11.01"/>
                </svg>
              </div>
              <span class="stat-grade" :class="gradeClass">{{ healthScore.grade }}</span>
            </div>
            <div class="stat-body">
              <span class="stat-value" :class="gradeClass">{{ healthScore.score }}</span>
              <span class="stat-unit">/100</span>
            </div>
            <span class="stat-label">健康评分</span>
          </div>
        </div>
      </div>

      <div class="stat-card" v-if="snap.cpuCores !== undefined">
        <div class="card-shell">
          <div class="card-core">
            <div class="stat-top">
              <div class="stat-icon cpu-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
                  <rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/>
                  <line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/>
                </svg>
              </div>
            </div>
            <div class="stat-body">
              <span class="stat-value" :class="cpuStatusClass">{{ snap.cpuPercent?.toFixed(0) ?? '--' }}<span class="stat-unit">%</span></span>
            </div>
            <div class="stat-footer">
              <span class="stat-label">CPU 使用率</span>
              <span class="stat-detail">{{ snap.cpuCores }} 核 · Load {{ snap.load1m?.toFixed(1) }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="stat-card" v-if="snap.memoryTotalGb !== undefined">
        <div class="card-shell">
          <div class="card-core">
            <div class="stat-top">
              <div class="stat-icon mem-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
                  <rect x="2" y="6" width="20" height="12" rx="2"/>
                  <line x1="6" y1="10" x2="6" y2="14"/><line x1="9" y1="10" x2="9" y2="14"/>
                </svg>
              </div>
            </div>
            <div class="stat-body">
              <span class="stat-value" :class="memStatusClass">{{ snap.memoryPercent?.toFixed(0) ?? '--' }}<span class="stat-unit">%</span></span>
            </div>
            <div class="stat-footer">
              <span class="stat-label">内存使用率</span>
              <span class="stat-detail">{{ snap.memoryUsedGb?.toFixed(1) }} / {{ snap.memoryTotalGb?.toFixed(1) }} GB</span>
            </div>
          </div>
        </div>
      </div>

      <div class="stat-card" v-if="snap.diskRootTotalGb !== undefined">
        <div class="card-shell">
          <div class="card-core">
            <div class="stat-top">
              <div class="stat-icon disk-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
                  <ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
                </svg>
              </div>
            </div>
            <div class="stat-body">
              <span class="stat-value" :class="diskStatusClass">{{ snap.diskRootPercent?.toFixed(0) ?? '--' }}<span class="stat-unit">%</span></span>
            </div>
            <div class="stat-footer">
              <span class="stat-label">磁盘 / 使用率</span>
              <span class="stat-detail">{{ snap.diskRootUsedGb?.toFixed(1) }} / {{ snap.diskRootTotalGb?.toFixed(1) }} GB</span>
            </div>
          </div>
        </div>
      </div>

      <div class="stat-card" v-if="snap.listeningPorts !== undefined">
        <div class="card-shell">
          <div class="card-core">
            <div class="stat-top">
              <div class="stat-icon net-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
                  <circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/>
                </svg>
              </div>
            </div>
            <div class="stat-body">
              <span class="stat-value">{{ snap.tcpEstablished ?? '--' }}</span>
            </div>
            <div class="stat-footer">
              <span class="stat-label">活跃连接</span>
              <span class="stat-detail">{{ snap.listeningPorts }} 端口监听</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ====== 系统概览面板 ====== -->
    <div v-if="snap.hostname" class="panel-card">
      <div class="panel-shell">
        <div class="panel-core">
          <div class="panel-header">
            <h3 class="panel-title">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--color-accent)" stroke-width="2" stroke-linecap="round">
                <rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>
              </svg>
              系统概览
            </h3>
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
          </div>
        </div>
      </div>
    </div>

    <!-- ====== 安全告警面板 ====== -->
    <SecurityAlertsPanel v-if="securityAlerts.length > 0" />

    <!-- ====== 加载中 ====== -->
    <div v-if="systemStore.loading && !hasData" class="empty-dashboard">
      <div class="loading-orb">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--color-accent)" stroke-width="1.5" stroke-linecap="round" class="spinning">
          <circle cx="12" cy="12" r="10" opacity="0.2"/><path d="M12 6v6l4 2"/>
        </svg>
      </div>
      <h3>正在获取系统数据</h3>
    </div>

    <!-- ====== 空状态 ====== -->
    <div v-else-if="!hasData" class="empty-dashboard">
      <div class="empty-icon-wrap">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" stroke-width="1.2" stroke-linecap="round">
          <rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/>
          <rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>
        </svg>
      </div>
      <h3>暂无系统数据</h3>
      <p>前往 <router-link to="/chat">智能对话</router-link> 输入"查看系统状态"以获取实时系统信息</p>
    </div>

    <!-- ====== 健康告警 ====== -->
    <div v-if="healthScore && healthScore.alerts && healthScore.alerts.length > 0" class="panel-card alerts-panel">
      <div class="panel-shell alert-shell">
        <div class="panel-core">
          <div class="panel-header">
            <h3 class="panel-title warning">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--color-warning)" stroke-width="2" stroke-linecap="round">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                <line x1="12" y1="9" x2="12" y2="13"/>
              </svg>
              健康告警
            </h3>
            <span class="alert-count">{{ healthScore.alerts.length }}</span>
          </div>
          <div class="alerts-list">
            <div v-for="(alert, idx) in healthScore.alerts" :key="idx" class="alert-item">
              <span class="alert-dot" />
              <span>{{ alert }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount } from 'vue'
import { useSystemStore } from '@/stores/system'
import { useChatStore } from '@/stores/chat'
import SecurityAlertsPanel from '@/components/dashboard/SecurityAlertsPanel.vue'

const systemStore = useSystemStore()
const chatStore = useChatStore()

const snap = computed(() => systemStore.snapshot)
const hasData = computed(() => systemStore.hasData)
const healthScore = computed(() => chatStore.lastHealthScore)
const securityAlerts = computed(() => snap.value.securityAlerts ?? [])

//自动刷新间隔 (10秒)
const REFRESH_INTERVAL=10000
let refreshTimer: ReturnType<typeof setInterval> | null=null

onMounted(() => {
  systemStore.fetchSnapshot()
  //每 10 秒自动刷新
  refreshTimer=setInterval(() => systemStore.fetchSnapshot(), REFRESH_INTERVAL)
})

onBeforeUnmount(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer=null
  }
})

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
const cpuStatusClass = computed(() => {
  const v = snap.value.cpuPercent
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
</script>

<style scoped>
.dashboard {
  padding: 28px 32px;
  max-width: 1100px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
  overflow-y: auto;
  height: 100%;
}

/* ── Header ── */
.dash-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  padding-bottom: 4px;
}
.dash-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.5px;
  margin: 0;
}
.dash-subtitle {
  font-size: 13px;
  color: var(--text-tertiary);
  margin-top: 2px;
}
.header-actions {
  display: flex;
  align-items: center;
}
.refresh-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-tertiary);
}
.spinning {
  animation: spin 1.5s linear infinite;
}
.auto-refresh-tag {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-safe);
  letter-spacing: 0.3px;
  text-transform: uppercase;
}
.live-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-safe);
  box-shadow: 0 0 8px var(--color-safe-glow);
  animation: glow-pulse 2s infinite;
}

/* ── Stat Grid (Bento) ── */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(185px, 1fr));
  gap: 14px;
}

/* Double-Bezel card */
.stat-card {
  animation: slide-up 500ms var(--ease-spring) both;
}
.stat-card:nth-child(1) { animation-delay: 0ms; }
.stat-card:nth-child(2) { animation-delay: 60ms; }
.stat-card:nth-child(3) { animation-delay: 120ms; }
.stat-card:nth-child(4) { animation-delay: 180ms; }
.stat-card:nth-child(5) { animation-delay: 240ms; }

.card-shell {
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-xl);
  padding: 0;
  transition: border-color var(--dur-gentle) var(--ease-spring),
              box-shadow var(--dur-gentle) var(--ease-spring);
}
.card-shell:hover {
  border-color: var(--border-emphasis);
  box-shadow: var(--shadow-md);
}

.card-core {
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.stat-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.stat-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  flex-shrink: 0;
}
.cpu-icon { background: var(--color-accent-soft); color: var(--color-accent); }
.mem-icon { background: var(--color-safe-soft); color: var(--color-safe); }
.disk-icon { background: var(--color-warning-soft); color: var(--color-warning); }
.net-icon { background: rgba(139,92,246,0.1); color: #a78bfa; }
.health-icon { background: var(--color-safe-soft); color: var(--color-safe); }

.stat-grade {
  font-size: 12px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  letter-spacing: 0.5px;
}
.stat-grade.safe    { background: var(--color-safe-soft); color: var(--color-safe); }
.stat-grade.warning { background: var(--color-warning-soft); color: var(--color-warning); }
.stat-grade.danger  { background: var(--color-danger-soft); color: var(--color-danger); }

.stat-body {
  display: flex;
  align-items: baseline;
  gap: 2px;
  padding: 4px 0 0;
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  font-family: var(--font-mono);
  line-height: 1;
  color: var(--text-primary);
  letter-spacing: -1px;
}
.stat-value.safe    { color: var(--color-safe); }
.stat-value.warning { color: var(--color-warning); }
.stat-value.danger  { color: var(--color-danger); }
.stat-unit {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-tertiary);
}
.stat-label {
  font-size: 11px;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 500;
}
.stat-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.stat-detail {
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--text-tertiary);
  white-space: nowrap;
}

/* ── Panel Card (Double-Bezel) ── */
.panel-card {
  animation: slide-up 500ms var(--ease-spring) both;
  animation-delay: 300ms;
}
.panel-shell {
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-xl);
  padding: 0;
  transition: border-color var(--dur-gentle) var(--ease-spring),
              box-shadow var(--dur-gentle) var(--ease-spring);
}
.panel-shell:hover {
  border-color: var(--border-emphasis);
  box-shadow: var(--shadow-md);
}
.panel-core {
  padding: 20px 24px;
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
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
.panel-title.warning { color: var(--color-warning); }

.alert-count {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: var(--color-warning-soft);
  color: var(--color-warning);
}

/* ── System Overview Grid ── */
.system-overview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 14px;
}
.overview-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 14px;
  background: var(--bg-surface);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-subtle);
}
.overview-label {
  font-size: 10px;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.6px;
  font-weight: 600;
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
.loading-orb {
  display: inline-flex;
  padding: 16px;
  border-radius: 50%;
  background: var(--color-accent-soft);
  margin-bottom: 16px;
}
.empty-icon-wrap {
  display: inline-flex;
  padding: 16px;
  border-radius: 50%;
  background: var(--bg-hover);
  margin-bottom: 16px;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
.empty-dashboard h3 {
  margin: 0 0 8px;
  font-size: 17px;
  color: var(--text-primary);
  font-weight: 600;
}
.empty-dashboard p {
  font-size: 14px;
  max-width: 400px;
  margin: 0 auto;
  color: var(--text-secondary);
}
.empty-dashboard a {
  color: var(--color-accent-text);
  font-weight: 500;
}

/* ── Alerts ── */
.alert-shell {
  border-color: rgba(245, 158, 11, 0.15);
}
.alerts-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.alert-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 13px;
  color: var(--text-primary);
  padding: 10px 14px;
  background: var(--color-warning-soft);
  border-radius: var(--radius-md);
  border: 1px solid rgba(245, 158, 11, 0.08);
}
.alert-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-warning);
  margin-top: 6px;
  flex-shrink: 0;
  box-shadow: 0 0 6px rgba(245, 158, 11, 0.4);
}

@keyframes slide-up {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: translateY(0); }
}
</style>
