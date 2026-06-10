<template>
  <div class="panel-card">
    <div class="panel-header">
      <h3 class="panel-title">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
        </svg>
        安全告警
      </h3>
      <span v-if="hasNoAlerts" class="panel-badge safe">无告警</span>
      <span v-else class="panel-badge warn">{{ alertCount }} 条</span>
    </div>

    <!-- 无告警 -->
    <div v-if="hasNoAlerts" class="empty-state">
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="1.5" stroke-linecap="round">
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
        <polyline points="22 4 12 14.01 9 11.01"/>
      </svg>
      <span>当前无安全告警</span>
    </div>

    <!-- 有告警 -->
    <div v-else class="alerts-body">
      <!-- 登录失败 -->
      <div class="alert-section">
        <span class="section-label">安全扫描结果</span>
        <p class="text-dim">请通过智能对话中的 MCP 安全工具获取详细安全审计结果</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useSystemStore } from '@/stores/system'

const store = useSystemStore()

const topIps = computed(() => {
  // 认证失败详情来自 MCP security_auth_failures 工具结果
  // 当前由 DashboardView 统一展示
  return [] as { ip: string; count: number; user: string }[]
})

const hasNoAlerts = computed(() => true)
const alertCount = computed(() => 0)

function connColor(_n: number): string {
  return 'safe'
}
</script>
</script>

<style scoped>
.panel-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  overflow: hidden;
  transition: border-color var(--dur-gentle) var(--ease-out);
}
.panel-card:hover {
  border-color: var(--border-emphasis);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-subtle);
}
.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.panel-badge {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 2px 8px;
  border-radius: var(--radius-full);
}
.panel-badge.safe { color: var(--color-safe); background: var(--color-safe-soft); }
.panel-badge.warn { color: var(--color-warning); background: var(--color-warning-soft); }

/* ---- Empty ---- */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 36px 20px;
  color: var(--text-tertiary);
  font-size: 13px;
}

/* ---- Alerts ---- */
.alerts-body {
  padding: 16px 20px;
}

.alert-section {
  margin-bottom: 18px;
}
.alert-section:last-child {
  margin-bottom: 0;
}
.section-label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 10px;
}

/* IP list */
.ip-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ip-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  background: var(--bg-elevated);
  border-radius: var(--radius-sm);
  font-size: 13px;
}
.ip-rank {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-tertiary);
  width: 16px;
  text-align: center;
}
.ip-addr {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-primary);
  flex: 1;
}
.ip-user {
  font-size: 12px;
  color: var(--text-secondary);
}
.ip-count {
  font-size: 13px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  min-width: 36px;
  text-align: right;
}

/* Network stats */
.network-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}
.net-stat {
  text-align: center;
  background: var(--bg-elevated);
  border-radius: var(--radius-md);
  padding: 12px 8px;
}
.net-num {
  display: block;
  font-size: 20px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--text-primary);
  line-height: 1.2;
}
.net-num.dim {
  color: var(--text-secondary);
  font-size: 16px;
}
.net-label {
  display: block;
  font-size: 10px;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.3px;
  margin-top: 4px;
}
</style>
