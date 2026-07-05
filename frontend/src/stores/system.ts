// ============================================================
// 系统仪表盘 Store — 双数据源: API 直连 + MCP 工具结果兜底
//
// 数据来源:
//   1. (主) GET /api/system/snapshot — 仪表盘专属实时 API
//   2. (兜底) 最新对话中 MCP tool_result 的解析数据
// ============================================================

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useChatStore } from './chat'

/** 系统概览快照 */
export interface SecurityAlert {
  tool: string
  title: string
  detail: string
  severity: 'info' | 'warning' | 'danger'
}

export interface SystemSnapshot {
  hostname: string
  os: string
  kernel: string
  bootTime: string
  cpuCores: number
  cpuPercent: number
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
  securityAlerts: SecurityAlert[]
}

export const useSystemStore = defineStore('system', () => {
  // ====== 状态 ======
  const snapshot = ref<Partial<SystemSnapshot>>({})
  const lastUpdate = ref<number>(0)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // ====== 计算属性 ======
  const hasData = computed(() => Object.keys(snapshot.value).length > 0)

  // ====== API 直连: 实时获取系统快照 ======
  async function fetchSnapshot(): Promise<void> {
    loading.value=true
    error.value=null
    try {
      const resp=await fetch('/api/system/snapshot')
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const json=await resp.json()
      if (json.code!==0) throw new Error(json.message||'API error')
      const d=json.data

      const snap: Partial<SystemSnapshot>={
        hostname: d.hostname,
        os: d.os,
        kernel: d.kernel,
        bootTime: d.boot_time,
        cpuCores: d.cpu.cores_logical,
        cpuPercent: d.cpu.percent,
        load1m: d.cpu.load_1m,
        load5m: d.cpu.load_5m,
        load15m: d.cpu.load_15m,
        memoryTotalGb: d.memory.total_gb,
        memoryUsedGb: d.memory.used_gb,
        memoryPercent: d.memory.percent,
        swapTotalGb: d.memory.swap_total_gb,
        swapUsedGb: d.memory.swap_used_gb,
        swapPercent: d.memory.swap_percent,
        diskRootPercent: d.disk.percent,
        diskRootUsedGb: d.disk.used_gb,
        diskRootTotalGb: d.disk.total_gb,
        tcpEstablished: d.network.connections,
        listeningPorts: 0,
        authFailures: 0,
      }
      snapshot.value=snap
      lastUpdate.value=Date.now()
    } catch (e: unknown) {
      const msg=e instanceof Error ? e.message : String(e)
      error.value=msg
      //API 失败时尝试从 chat 消息提取
      extractFromChat()
    } finally {
      loading.value=false
    }
  }

  // ====== 从 Chat Store 派生（兜底） ======
  function extractFromChat() {
    const chatStore = useChatStore()
    const msgs = chatStore.messages
    if (msgs.length === 0) {
      if (Object.keys(snapshot.value).length===0) {
        snapshot.value={}
        lastUpdate.value=Date.now()
      }
      return
    }

    const snap: Partial<SystemSnapshot> = { ...snapshot.value }
    const alerts: SecurityAlert[] = []

    const pushAlert = (tool: string, title: string, detail: string, severity: SecurityAlert['severity']) => {
      if (!detail) return
      alerts.push({ tool, title, detail, severity })
    }

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
            {
              const states = (data.all_states || data.states || {}) as Record<string, number>
              snap.tcpEstablished =
                (data.established as number | undefined) ??
                (data.estab as number | undefined) ??
                states.ESTABLISHED ??
                states.ESTAB ??
                0
            }
            break

          case 'network_listening_ports':
            if (Array.isArray(data.port)) {
              snap.listeningPorts = data.port.length
            } else if (Array.isArray(data.ports)) {
              snap.listeningPorts = data.ports.length
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
            } else if (summary.total_failures !== undefined) {
              snap.authFailures = summary.total_failures as number
            }
            break
        }

        if (summary.alert || summary.alert_reason) {
          const reason = (summary.alert_reason as string) || (summary.error as string) || ''
          pushAlert(
            tc.tool_name,
            tc.tool_name,
            reason,
            summary.alert ? 'warning' : 'info',
          )
        }
      }
    }

    if (alerts.length > 0) {
      snap.securityAlerts = alerts
    }

    if (Object.keys(snap).length > 0) {
      snapshot.value = snap
      lastUpdate.value = Date.now()
    }
  }

  return { snapshot, lastUpdate, hasData, loading, error, fetchSnapshot, extractFromChat }
})
