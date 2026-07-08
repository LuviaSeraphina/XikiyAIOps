<template>
  <div class="security-panel">
    <div class="panel-shell">
      <div class="panel-core">
        <div class="panel-header">
          <h3 class="panel-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            </svg>
            安全告警
          </h3>
          <span v-if="hasNoAlerts" class="panel-badge safe">无告警</span>
          <span v-else class="panel-badge warn">{{ alerts.length }} 条</span>
        </div>

        <div v-if="hasNoAlerts" class="empty-state">
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="var(--color-safe)" stroke-width="1.5" stroke-linecap="round">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
            <polyline points="22 4 12 14.01 9 11.01"/>
          </svg>
          <span>当前无安全告警</span>
        </div>

        <div v-else class="alerts-body">
          <div class="alert-section">
            <span class="section-label">安全扫描结果</span>
            <div class="alert-list">
              <div
                v-for="alert in alerts"
                :key="`${alert.tool}-${alert.title}-${alert.detail}`"
                class="alert-item"
                :class="alert.severity"
              >
                <div class="alert-head">
                  <span class="alert-tool">{{ alert.title }}</span>
                  <span class="alert-severity" :class="alert.severity">{{ severityLabel(alert.severity) }}</span>
                </div>
                <p class="alert-detail">{{ alert.detail }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useSystemStore } from '@/stores/system'

const store = useSystemStore()

const alerts = computed(() => store.snapshot.securityAlerts ?? [])
const hasNoAlerts = computed(() => alerts.value.length === 0)

function severityLabel(severity: 'info' | 'warning' | 'danger'): string {
  switch (severity) {
    case 'danger':
      return '高危'
    case 'warning':
      return '警告'
    default:
      return '提示'
  }
}
</script>

<style scoped>
.security-panel {
  animation: slide-up 500ms var(--ease-spring) both;
  animation-delay: 200ms;
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
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 22px;
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
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 3px 10px;
  border-radius: var(--radius-full);
}
.panel-badge.safe { color: var(--color-safe); background: var(--color-safe-soft); }
.panel-badge.warn { color: var(--color-warning); background: var(--color-warning-soft); }

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 40px 20px;
  color: var(--text-tertiary);
  font-size: 13px;
}

.alerts-body {
  padding: 16px 22px;
}

.alert-section {
  margin-bottom: 18px;
}
.alert-section:last-child {
  margin-bottom: 0;
}
.section-label {
  display: block;
  font-size: 10px;
  font-weight: 700;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.6px;
  margin-bottom: 10px;
}

.alert-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.alert-item {
  border-radius: var(--radius-md);
  padding: 12px 14px;
  border: 1px solid var(--border-subtle);
  background: var(--bg-surface);
  transition: border-color var(--dur-quick) var(--ease-spring);
}
.alert-item.warning {
  border-color: rgba(245, 158, 11, 0.15);
  background: rgba(245, 158, 11, 0.04);
}
.alert-item.danger {
  border-color: rgba(248, 113, 113, 0.15);
  background: rgba(248, 113, 113, 0.04);
}
.alert-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}
.alert-tool {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.alert-severity {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.4px;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
}
.alert-severity.warning { color: var(--color-warning); background: var(--color-warning-soft); }
.alert-severity.danger  { color: var(--color-danger); background: var(--color-danger-soft); }
.alert-severity.info    { color: var(--text-tertiary); background: var(--bg-hover); }

.alert-detail {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-secondary);
}

@keyframes slide-up {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: translateY(0); }
}
</style>
