<template>
  <div class="tool-card" :class="[`status-${toolCall.status}`]">
    <!-- Header -->
    <div class="tool-header" @click="expanded = !expanded">
      <span class="tool-status-icon" :class="`si-${toolCall.status}`">{{ statusIcon }}</span>
      <code class="tool-name">{{ toolCall.tool_name }}</code>
      <span v-if="toolCall.risk_level" class="risk-tag" :class="`risk-${toolCall.risk_level}`">
        {{ riskLabel }}
      </span>
      <svg
        class="expand-icon"
        :class="{ expanded }"
        width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"
      >
        <polyline points="9 18 15 12 9 6" />
      </svg>
    </div>

    <!-- Expanded detail -->
    <transition name="slide-up">
      <div v-show="expanded" class="tool-detail">
        <!-- 参数 -->
        <div class="detail-section">
          <span class="detail-label">参数</span>
          <pre class="code-block">{{ formattedArgs }}</pre>
        </div>
        <!-- 结果摘要 (结构化) -->
        <div v-if="summaryFields.length > 0" class="detail-section">
          <span class="detail-label">结果摘要</span>
          <div class="summary-grid">
            <div v-for="f in summaryFields" :key="f.label" class="summary-item">
              <span class="summary-label">{{ f.label }}</span>
              <span class="summary-value" :class="{ 'value-danger': f.danger, 'value-warn': f.warn }">{{ f.value }}</span>
            </div>
          </div>
        </div>
        <!-- 原始数据 (默认隐藏) -->
        <div v-if="toolCall.result !== undefined" class="detail-section">
          <button class="raw-toggle" @click="showRaw = !showRaw">
            {{ showRaw ? '收起原始数据' : '查看原始数据' }}
            <svg class="raw-arrow" :class="{ open: showRaw }" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><polyline points="9 18 15 12 9 6"/></svg>
          </button>
          <pre v-show="showRaw" class="code-block raw-block">{{ formattedResult }}</pre>
        </div>
      </div>
    </transition>

    <!-- Running bar -->
    <div v-if="toolCall.status === 'running'" class="running-bar" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { ToolCall, RiskLevel } from '@/types'

const props = defineProps<{ toolCall: ToolCall }>()
const expanded = ref(false)
const showRaw = ref(false)

const statusIcon = computed(() => {
  switch (props.toolCall.status) {
    case 'pending': return '○'
    case 'running': return '◌'
    case 'done':    return '●'
    case 'error':   return '✕'
    default:        return '○'
  }
})

const riskLabel = computed(() => {
  switch (props.toolCall.risk_level) {
    case 'read_only':  return '只读'
    case 'restricted': return '受限'
    case 'dangerous':  return '高危'
    default:           return ''
  }
})

const formattedArgs = computed(() => {
  try { return JSON.stringify(props.toolCall.arguments, null, 2) }
  catch { return String(props.toolCall.arguments) }
})

const formattedResult = computed(() => {
  if (typeof props.toolCall.result === 'string') return props.toolCall.result
  try { return JSON.stringify(props.toolCall.result, null, 2) }
  catch { return String(props.toolCall.result) }
})

// 从工具结果中提取关键摘要字段
interface SummaryField { label: string; value: string; danger?: boolean; warn?: boolean }

const summaryFields = computed<SummaryField[]>(() => {
  const result = props.toolCall.result as Record<string, unknown> | undefined
  if (!result) return []
  const data = (result.data || {}) as Record<string, unknown>
  const summary = (result.summary || {}) as Record<string, unknown>
  const name = props.toolCall.tool_name
  const fields: SummaryField[] = []

  // 从 summary 中提取顶层告警字段
  const addSummaryField = (key: string, label: string, opts?: { danger?: boolean }) => {
    const v = summary[key]
    if (v !== undefined && v !== null && v !== '') {
      fields.push({ label, value: typeof v === 'boolean' ? (v ? '是' : '否') : String(v), ...opts })
    }
  }

  // 通用: summary 中的 alert
  addSummaryField('alert', '告警', { danger: summary.alert === true || summary.alert === 'true' })
  addSummaryField('alert_reason', '告警原因', { danger: true })

  // 按工具类型提取 data 中的核心字段
  const extractors: Record<string, () => void> = {
    system_load() {
      const d = data as Record<string, number>
      if (d.load_1min !== undefined) fields.push({ label: '1分钟负载', value: d.load_1min.toFixed(2), warn: d.load_1min > (d.cpu_cores || 4) })
      if (d.load_5min !== undefined) fields.push({ label: '5分钟负载', value: d.load_5min.toFixed(2) })
      if (d.load_15min !== undefined) fields.push({ label: '15分钟负载', value: d.load_15min.toFixed(2) })
      if (d.cpu_cores !== undefined) fields.push({ label: 'CPU 核心', value: String(d.cpu_cores) })
    },
    memory_info() {
      const d = data as Record<string, number>
      if (d.total_gb !== undefined) fields.push({ label: '总内存', value: d.total_gb.toFixed(1) + ' GB' })
      if (d.used_gb !== undefined) fields.push({ label: '已用', value: d.used_gb.toFixed(1) + ' GB' })
      if (d.usage_percent !== undefined) fields.push({ label: '使用率', value: d.usage_percent.toFixed(1) + '%', warn: d.usage_percent > 80, danger: d.usage_percent > 90 })
    },
    disk_inspect_handler() {
      const d = data as Record<string, number>
      if (d.total_gb !== undefined) fields.push({ label: '总容量', value: d.total_gb.toFixed(1) + ' GB' })
      if (d.usage_percent !== undefined) fields.push({ label: '使用率', value: d.usage_percent.toFixed(1) + '%', warn: d.usage_percent > 80, danger: d.usage_percent > 90 })
    },
    process_detail() {
      const p = (data as Record<string, unknown>).process as Record<string, unknown> | undefined
      if (p) {
        if (p.name) fields.push({ label: '进程名', value: String(p.name) })
        if (p.pid) fields.push({ label: 'PID', value: String(p.pid) })
        if (p.status) fields.push({ label: '状态', value: String(p.status) })
        if (p.cpu_percent !== undefined) fields.push({ label: 'CPU', value: Number(p.cpu_percent).toFixed(1) + '%' })
        if (p.memory_percent !== undefined) fields.push({ label: '内存', value: Number(p.memory_percent).toFixed(2) + '%' })
      }
    },
    process_top_cpu() {
      const procs = (data as Record<string, unknown>).processes as Array<Record<string, unknown>> | undefined
      if (procs) fields.push({ label: 'Top 进程数', value: String(procs.length) })
    },
    process_top_memory() {
      const procs = (data as Record<string, unknown>).processes as Array<Record<string, unknown>> | undefined
      if (procs) fields.push({ label: 'Top 进程数', value: String(procs.length) })
    },
    swap_info() {
      const d = data as Record<string, number>
      if (d.swap_percent !== undefined) fields.push({ label: 'Swap 使用率', value: d.swap_percent.toFixed(1) + '%', warn: d.swap_percent > 50, danger: d.swap_percent > 80 })
      if (d.swap_total_gb !== undefined) fields.push({ label: 'Swap 总量', value: d.swap_total_gb.toFixed(1) + ' GB' })
    },
    network_listening_ports() {
      const ports = (data as Record<string, unknown>).ports as Array<unknown> | undefined
      if (ports) fields.push({ label: '监听端口', value: String(ports.length) + ' 个' })
    },
    network_connections_summary() {
      const d = data as Record<string, number>
      if (d.established !== undefined) fields.push({ label: '已建立连接', value: String(d.established) })
      if (d.close_wait !== undefined) fields.push({ label: 'CLOSE_WAIT', value: String(d.close_wait), warn: d.close_wait > 0 })
    },
    security_auth_failures() {
      const d = data as Record<string, number>
      if (d.total_failures !== undefined) fields.push({ label: '认证失败', value: String(d.total_failures), warn: d.total_failures > 0 })
    },
    security_active_sessions() {
      const sessions = (data as Record<string, unknown>).sessions as Array<unknown> | undefined
      if (sessions) fields.push({ label: '活跃会话', value: String(sessions.length) + ' 个' })
    },
    system_info() {
      const d = data as Record<string, string | boolean>
      if (d.hostname) fields.push({ label: '主机名', value: String(d.hostname) })
      if (d.os) fields.push({ label: '操作系统', value: String(d.os) })
      if (d.kernel) fields.push({ label: '内核', value: String(d.kernel) })
    },
    system_failed_services() {
      const svcs = (data as Record<string, unknown>).services as Array<unknown> | undefined
      if (svcs) fields.push({ label: '失败服务', value: String(svcs.length) + ' 个', danger: svcs.length > 0 })
    },
    network_tcp_retrans() {
      const d = data as Record<string, number>
      if (d.retrans_percent !== undefined) fields.push({ label: 'TCP 重传率', value: d.retrans_percent.toFixed(2) + '%', warn: d.retrans_percent > 2 })
    },
  }

  // 执行对应提取器
  const extractor = extractors[name]
  if (extractor) {
    extractor()
  } else {
    // 通用提取: 从 summary 取关键信息
    const skipKeys = new Set(['alert', 'alert_reason'])
    for (const [k, v] of Object.entries(summary)) {
      if (skipKeys.has(k) || v === null || v === undefined || v === '') continue
      if (typeof v === 'object') continue
      fields.push({ label: k, value: String(v).substring(0, 80) })
    }
    // 如果是错误结果
    if (summary.error) {
      fields.push({ label: '错误', value: String(summary.error).substring(0, 120), danger: true })
    }
  }

  return fields
})
</script>

<style scoped>
.tool-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  font-size: 13px;
  overflow: hidden;
  transition: border-color var(--dur-quick) var(--ease-spring);
}
.tool-card:hover {
  border-color: var(--border-default);
}
.status-running { border-left: 3px solid var(--color-accent); }
.status-done    { border-left: 3px solid var(--color-safe); }
.status-error   { border-left: 3px solid var(--color-danger); }

.tool-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 14px;
  cursor: pointer;
  user-select: none;
}
.tool-status-icon {
  font-size: 10px;
}
.si-pending  { color: var(--text-tertiary); }
.si-running  { color: var(--color-accent); animation: glow-pulse 1.5s infinite; }
.si-done     { color: var(--color-safe); }
.si-error    { color: var(--color-danger); }

.tool-name {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-primary);
  flex: 1;
}
.risk-tag {
  font-size: 10px;
  padding: 2px 7px;
  border-radius: var(--radius-sm);
  font-weight: 600;
}
.risk-read_only  { background: var(--color-safe-soft); color: var(--color-safe); }
.risk-restricted { background: var(--color-warning-soft); color: var(--color-warning); }
.risk-dangerous  { background: var(--color-danger-soft); color: var(--color-danger); }

.expand-icon {
  flex-shrink: 0;
  transition: transform var(--dur-quick) var(--ease-spring);
  color: var(--text-tertiary);
}
.expand-icon.expanded {
  transform: rotate(90deg);
}

.tool-detail {
  border-top: 1px solid var(--border-subtle);
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: var(--bg-code);
}
.detail-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.detail-label {
  font-size: 10px;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.6px;
  font-weight: 600;
}
/* ── Summary grid ── */
.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 4px 14px;
}
.summary-item {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 4px 0;
  border-bottom: 1px dotted var(--border-subtle);
}
.summary-label {
  font-size: 12px;
  color: var(--text-tertiary);
}
.summary-value {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-primary);
  font-weight: 500;
}
.summary-value.value-warn  { color: var(--color-warning); }
.summary-value.value-danger { color: var(--color-danger); font-weight: 600; }

/* ── Raw toggle ── */
.raw-toggle {
  background: none; border: none;
  font-size: 11px; color: var(--text-tertiary);
  cursor: pointer; padding: 2px 0;
  display: flex; align-items: center; gap: 4px;
  transition: color var(--dur-quick);
}
.raw-toggle:hover { color: var(--text-secondary); }
.raw-arrow { transition: transform var(--dur-quick) var(--ease-spring); }
.raw-arrow.open { transform: rotate(90deg); }
.raw-block { max-height: 200px; overflow-y: auto; }

.code-block {
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-secondary);
  background: var(--bg-root);
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-subtle);
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.running-bar {
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--color-accent), transparent);
  animation: runningSlide 1.5s infinite ease-in-out;
}
@keyframes runningSlide {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: all var(--dur-base) var(--ease-spring);
}
.slide-up-enter-from,
.slide-up-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
