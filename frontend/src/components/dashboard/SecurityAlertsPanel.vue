<template>
  <el-card shadow="hover" class="panel">
    <template #header><span class="panel-title">🛡️ 安全告警</span></template>

    <div v-if="hasNoAlerts" class="empty-state">✅ 当前无安全告警</div>

    <div v-else class="alerts-body">
      <!-- 登录失败 TOP 5 -->
      <div class="alert-section">
        <span class="section-label">登录失败 TOP 5 IP</span>
        <el-table :data="topIps" size="small" stripe>
          <el-table-column prop="ip" label="来源 IP" />
          <el-table-column prop="count" label="次数" width="70" align="center">
            <template #default="{ row }">
              <span :class="{ 'text-danger': row.count >= 10 }">
                {{ row.count }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="user" label="尝试用户" />
        </el-table>
      </div>

      <!-- 网络状态 -->
      <div class="alert-section" v-if="store.network">
        <span class="section-label">网络连接</span>
        <div class="network-stats">
          <div class="stat-item">
            <span class="stat-num" :class="connColor(store.network.tcp_established)">
              {{ store.network.tcp_established }}
            </span>
            <span class="stat-label">活跃连接</span>
          </div>
          <div class="stat-item">
            <span class="stat-num dim">{{ store.network.tcp_time_wait }}</span>
            <span class="stat-label">TIME_WAIT</span>
          </div>
          <div class="stat-item">
            <span class="stat-num dim">{{ store.network.listening_ports }}</span>
            <span class="stat-label">监听端口</span>
          </div>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useSystemStore } from '@/stores/system'

const store = useSystemStore()

const topIps = computed(() => {
  const ips = store.authFailures.failed_ips
  return Object.entries(ips)
    .map(([ip, count]) => ({ ip, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 5)
})

const hasNoAlerts = computed(() => {
  return topIps.value.length === 0 && store.authFailures.total === 0
})

function connColor(n: number): string {
  if (n >= 10) return 'text-danger'
  if (n >= 5) return 'text-warning'
  return 'text-safe'
}
</script>

<style scoped>
.panel { height: 100%; }
.panel-title { font-size: 15px; font-weight: 600; }

.empty-state {
  padding: 30px 0;
  text-align: center;
  color: var(--text-secondary);
}

.alert-section {
  margin-bottom: 16px;
}
.section-label {
  display: block;
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.network-stats {
  display: flex;
  gap: 16px;
}
.stat-item {
  flex: 1;
  text-align: center;
  background: var(--bg-dark);
  border-radius: 6px;
  padding: 10px 0;
}
.stat-num {
  display: block;
  font-size: 22px;
  font-weight: 700;
}
.stat-num.dim {
  color: var(--text-secondary);
  font-size: 16px;
}
.stat-label {
  font-size: 11px;
  color: var(--text-secondary);
}
</style>
