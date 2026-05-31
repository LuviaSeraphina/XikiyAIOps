<template>
  <div class="panel-card">
    <div class="panel-header">
      <h3 class="panel-title">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
        </svg>
        进程 TOP 10
      </h3>
      <div class="header-actions">
        <el-radio-group v-model="sortBy" size="small" @change="onSortChange">
          <el-radio-button value="cpu">CPU</el-radio-button>
          <el-radio-button value="memory">内存</el-radio-button>
        </el-radio-group>
      </div>
    </div>

    <el-table :data="store.processes" stripe size="small" v-loading="store.loading" class="process-table">
      <el-table-column prop="pid" label="PID" width="70" align="center">
        <template #default="{ row }">
          <code class="pid-code">{{ row.pid }}</code>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="进程名" min-width="140">
        <template #default="{ row }">
          <span class="process-name">{{ row.name }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="cpu_percent" label="CPU" width="120" align="right">
        <template #default="{ row }">
          <div class="metric-cell">
            <div class="metric-bar-track">
              <div
                class="metric-bar-fill"
                :style="{ width: Math.min(row.cpu_percent, 100) + '%', background: row.cpu_percent > 80 ? '#ef4444' : '#3b82f6' }"
              />
            </div>
            <span class="metric-num" :class="{ 'text-danger': row.cpu_percent > 80 }">
              {{ row.cpu_percent.toFixed(1) }}%
            </span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="memory_percent" label="内存" width="120" align="right">
        <template #default="{ row }">
          <div class="metric-cell">
            <div class="metric-bar-track">
              <div
                class="metric-bar-fill"
                :style="{ width: Math.min(row.memory_percent, 100) + '%', background: row.memory_percent > 80 ? '#ef4444' : '#22c55e' }"
              />
            </div>
            <span class="metric-num" :class="{ 'text-danger': row.memory_percent > 80 }">
              {{ row.memory_percent.toFixed(1) }}%
            </span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="80" align="center">
        <template #default="{ row }">
          <span class="status-dot" :class="statusDotClass(row.status)" />
          {{ row.status }}
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useSystemStore } from '@/stores/system'
import { fetchProcesses } from '@/api/dashboard'

const store = useSystemStore()
const sortBy = ref<'cpu' | 'memory'>('cpu')

function statusDotClass(s: string): string {
  switch (s.toLowerCase()) {
    case 'running':  return 'dot-safe'
    case 'sleeping': return 'dot-idle'
    case 'zombie':
    case 'stopped':  return 'dot-danger'
    default:         return 'dot-idle'
  }
}

async function onSortChange() {
  const list = await fetchProcesses(sortBy.value, 10)
  store.processes = list
}
</script>

<style scoped>
.panel-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  overflow: hidden;
  transition: border-color var(--duration-normal) var(--ease-out);
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
