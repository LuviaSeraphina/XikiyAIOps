// ============================================================
// 系统仪表盘 Store — 基于 MCP 工具调用结果
//
// 数据来源: 最新对话中 MCP tool_result 的解析数据
// 后端无独立 dashboard API，系统状态通过 chat + MCP 工具获取
// 此 Store 从 Chat Store 的 lastHealthScore + tool 结果派生
// ============================================================

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useChatStore } from './chat'

/** 系统概览快照（从 MCP 工具结果提取） */
export interface SystemSnapshot {
  hostname: string
  os: string
  kernel: string
  bootTime: string
  cpuCores: number
  load1m: number
  load5m: number
  load15m: number
  memoryTotalGb: number
  memoryUsedGb: number
  memoryPercent: number
  swapTotalGb: number
  swapUsedGb: number
  swapPercent: number
  diskRootPercent: number
  diskRootUsedGb: number
  diskRootTotalGb: number
  tcpEstablished: number
  listeningPorts: number
  authFailures: number
}

export const useSystemStore = defineStore('system', () => {
  // ====== 状态 ======
  const snapshot = ref<Partial<SystemSnapshot>>({})
  const lastUpdate = ref<number>(0)

  // ====== 计算属性 ======
  const hasData = computed(() => Object.keys(snapshot.value).length > 0)

  // ====== 从 Chat Store 派生 ======
  /**
   * 尝试从最新对话的 MCP 工具结果中提取系统指标
   * 由 Dashboard 页面在 onMounted 时调用
   */
  function extractFromChat() {
    const chatStore = useChatStore()
    const msgs = chatStore.messages
    if (msgs.length === 0) return

    const snap: Partial<SystemSnapshot> = {}

    for (const msg of msgs) {
      if (!msg.tool_calls) continue
      for (const tc of msg.tool_calls) {
        if (tc.status !== 'done' || !tc.result) continue
        const result = tc.result as Record<string, unknown>
        const data = (result.data as Record<string, unknown>) || {}
        const summary = (result.summary as Record<string, unknown>) || {}

        switch (tc.tool_name) {
          case 'system_info':
            snap.hostname = data.hostname as string
            snap.os = data.os as string
            snap.kernel = data.kernel as string
            snap.bootTime = data.boot_time as string
            snap.cpuCores = data.cpu_cores as number
            break

          case 'system_load':
            snap.load1m = data.load_1min as number
            snap.load5m = data.load_5min as number
            snap.load15m = data.load_15min as number
            break

          case 'memory_info':
            snap.memoryTotalGb = data.total_gb as number
            snap.memoryUsedGb = data.used_gb as number
            snap.memoryPercent = data.usage_percent as number
            break

          case 'swap_info':
            snap.swapTotalGb = data.total_gb as number
            snap.swapUsedGb = data.used_gb as number
            snap.swapPercent = summary.swap_percent as number
            break

          case 'disk_inspect':
          case 'disk_inspect_handler':
            if ((data.path as string) === '/' || (summary.path as string) === '/') {
              snap.diskRootPercent = (data.usage_percent || summary.usage_percent) as number
              snap.diskRootUsedGb = data.used_gb as number
              snap.diskRootTotalGb = data.total_gb as number
            }
            break

          case 'network_connections_summary':
            if (data.states && typeof data.states === 'object') {
              snap.tcpEstablished = (data.states as Record<string, number>).ESTABLISHED || 0
            }
            break

          case 'network_listening_ports':
            if (data.port && Array.isArray(data.port)) {
              snap.listeningPorts = (data.port as unknown[]).length
            } else if (summary.total !== undefined) {
              snap.listeningPorts = summary.total as number
            }
            break

          case 'security_auth_failures':
            if (data.failed_ips && typeof data.failed_ips === 'object') {
              snap.authFailures = Object.values(data.failed_ips as Record<string, number>).reduce(
                (a, b) => a + b,
                0,
              )
            }
            break
        }
      }
    }

    if (Object.keys(snap).length > 0) {
      snapshot.value = snap
      lastUpdate.value = Date.now()
    }
  }

  return { snapshot, lastUpdate, hasData, extractFromChat }
})
