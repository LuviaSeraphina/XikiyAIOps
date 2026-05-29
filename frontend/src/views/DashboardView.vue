<template>
  <div class="dashboard">
    <!-- 第一行：CPU + 内存（跨两列） -->
    <div class="grid-span">
      <CpuMemoryPanel />
    </div>

    <!-- 第二行：磁盘 + 安全告警 -->
    <DiskPanel />
    <SecurityAlertsPanel />

    <!-- 第三行：进程 TOP N（跨两列） -->
    <div class="grid-span">
      <ProcessTopTable />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useSystemStore } from '@/stores/system'
import CpuMemoryPanel from '@/components/dashboard/CpuMemoryPanel.vue'
import DiskPanel from '@/components/dashboard/DiskPanel.vue'
import ProcessTopTable from '@/components/dashboard/ProcessTopTable.vue'
import SecurityAlertsPanel from '@/components/dashboard/SecurityAlertsPanel.vue'

const store = useSystemStore()

onMounted(() => {
  store.refreshAll()
})
</script>

<style scoped>
.dashboard {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  padding: 16px;
}

.grid-span {
  grid-column: 1 / -1;
}
</style>
