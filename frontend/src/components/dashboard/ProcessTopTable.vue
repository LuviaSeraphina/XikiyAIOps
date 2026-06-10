<template>
  <div class="panel-card">
    <div class="panel-header">
      <h3 class="panel-title">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
        </svg>
        进程列表
      </h3>
    </div>
    <div class="empty-state">
      <p>请通过智能对话中的 MCP 工具查看进程信息</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const sortBy = ref<'cpu' | 'memory'>('cpu')

// 进程数据来自 MCP process_inspect 工具，通过 chat 获取
// 当前仪表盘已整合到 DashboardView，此组件预留用于后续扩展
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

.header-actions {
  display: flex;
  gap: 8px;
}

.process-table {
  --el-table-header-bg-color: transparent !important;
  font-size: 13px;
}
.process-table :deep(.el-table__header-wrapper) {
  background: rgba(255,255,255,0.02);
}

.pid-code {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-secondary);
}
.process-name {
  font-weight: 500;
}

/* Metric bar cells */
.metric-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}
.metric-bar-track {
  flex: 1;
  height: 5px;
  border-radius: 3px;
  background: rgba(255,255,255,0.06);
  overflow: hidden;
  min-width: 40px;
}
.metric-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s var(--ease-out);
}
.metric-num {
  font-size: 12px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: var(--text-secondary);
  min-width: 42px;
  text-align: right;
}

/* Status dot */
.status-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-right: 4px;
  vertical-align: middle;
}
.dot-safe   { background: #22c55e; }
.dot-idle   { background: #8896a7; }
.dot-danger { background: #ef4444; }
</style>
