<template>
  <el-card shadow="hover" class="panel">
    <template #header>
      <div class="header-row">
        <span class="panel-title">📋 进程 TOP N</span>
        <el-radio-group v-model="sortBy" size="small" @change="onSortChange">
          <el-radio-button value="cpu">按 CPU</el-radio-button>
          <el-radio-button value="memory">按内存</el-radio-button>
        </el-radio-group>
      </div>
    </template>

    <el-table :data="store.processes" stripe size="small" v-loading="store.loading">
      <el-table-column prop="pid" label="PID" width="70" />
      <el-table-column prop="name" label="进程名" min-width="120" />
      <el-table-column prop="cpu_percent" label="CPU%" width="100" align="right">
        <template #default="{ row }">
          <el-progress
            :percentage="+row.cpu_percent.toFixed(1)"
            :color="row.cpu_percent > 80 ? '#F56C6C' : '#409EFF'"
            :stroke-width="8"
            :show-text="false"
          />
          <span class="cell-val">{{ row.cpu_percent.toFixed(1) }}%</span>
        </template>
      </el-table-column>
      <el-table-column prop="memory_percent" label="内存%" width="100" align="right">
        <template #default="{ row }">
          <el-progress
            :percentage="+row.memory_percent.toFixed(1)"
            :color="row.memory_percent > 80 ? '#F56C6C' : '#67C23A'"
            :stroke-width="8"
            :show-text="false"
          />
          <span class="cell-val">{{ row.memory_percent.toFixed(1) }}%</span>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="90">
        <template #default="{ row }">
          <StatusBadge :risk-level="statusToRisk(row.status)" />
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useSystemStore } from '@/stores/system'
import { fetchProcesses } from '@/api/dashboard'
import StatusBadge from '@/components/common/StatusBadge.vue'
import type { RiskLevel } from '@/types'

const store = useSystemStore()
const sortBy = ref<'cpu' | 'memory'>('cpu')

function statusToRisk(s: string): RiskLevel {
  switch (s.toLowerCase()) {
    case 'running':  return 'read_only'
    case 'sleeping': return 'restricted'
    case 'zombie':
    case 'stopped':  return 'dangerous'
    default:         return 'read_only'
  }
}

async function onSortChange() {
  const list = await fetchProcesses(sortBy.value, 10)
  store.processes = list
}
</script>

<style scoped>
.panel { height: 100%; }
.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.panel-title { font-size: 15px; font-weight: 600; }
.cell-val {
  font-size: 12px;
  color: var(--text-secondary);
  margin-left: 6px;
}
</style>
