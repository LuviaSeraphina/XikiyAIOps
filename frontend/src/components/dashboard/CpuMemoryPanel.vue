<template>
  <div class="panel-card">
    <div class="panel-header">
      <h3 class="panel-title">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/>
          <line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/>
        </svg>
        CPU & 内存
      </h3>
      <span class="panel-badge" v-if="store.summary">实时</span>
    </div>

    <div class="panel-body">
      <!-- 左：CPU 仪表盘 -->
      <div class="cpu-section">
        <div ref="cpuChartRef" class="chart-box"></div>
        <div class="cpu-extra">
          <div class="extra-item">
            <span class="extra-label">核心数</span>
            <span class="extra-value">{{ store.summary?.cpu_cores ?? '--' }}</span>
          </div>
          <div class="extra-item">
            <span class="extra-label">Load 1m</span>
            <span class="extra-value">{{ store.summary?.load_avg?.[0]?.toFixed(1) ?? '--' }}</span>
          </div>
          <div class="extra-item">
            <span class="extra-label">Load 5m</span>
            <span class="extra-value">{{ store.summary?.load_avg?.[1]?.toFixed(1) ?? '--' }}</span>
          </div>
          <div class="extra-item">
            <span class="extra-label">Load 15m</span>
            <span class="extra-value">{{ store.summary?.load_avg?.[2]?.toFixed(1) ?? '--' }}</span>
          </div>
        </div>
      </div>

      <!-- 右：内存 + Swap -->
      <div class="memory-section">
        <div class="mem-block">
          <div class="mem-header">
            <span class="mem-label">内存</span>
            <span class="mem-pct" :class="memStatusClass">{{ memPercent }}%</span>
          </div>
          <div class="mem-bar-track">
            <div class="mem-bar-fill" :style="{ width: memPercent + '%', background: memBarColor }" />
          </div>
          <span class="mem-detail">{{ memUsed }} GB / {{ memTotal }} GB</span>
        </div>

        <div class="mem-block" v-if="swapTotal > 0">
          <div class="mem-header">
            <span class="mem-label">Swap</span>
            <span class="mem-pct" :class="swapStatusClass">{{ swapPercent }}%</span>
          </div>
          <div class="mem-bar-track">
            <div class="mem-bar-fill" :style="{ width: swapPercent + '%', background: swapBarColor }" />
          </div>
          <span class="mem-detail">{{ swapUsed }} GB / {{ swapTotal }} GB</span>
        </div>

        <!-- Uptime -->
        <div class="uptime-row" v-if="uptimeText">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
          </svg>
          <span>{{ uptimeText }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { useSystemStore } from '@/stores/system'

const store = useSystemStore()
const cpuChartRef = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null
let resizeObserver: ResizeObserver | null = null

// ---- CPU Gauge ----
function initChart() {
  if (!cpuChartRef.value) return
  chart = echarts.init(cpuChartRef.value)
  chart.setOption({
    series: [{
      type: 'gauge',
      startAngle: 210,
      endAngle: -30,
      center: ['50%', '52%'],
      radius: '90%',
      min: 0,
      max: 100,
      splitNumber: 10,
      axisLine: {
        lineStyle: {
          width: 12,
          color: [
            [0.3, '#22c55e'],
            [0.7, '#f59e0b'],
            [1, '#ef4444'],
          ],
        },
      },
      pointer: {
        length: '62%',
        width: 4,
        itemStyle: { color: '#e8ecf1' },
      },
      axisTick: { distance: -12, length: 6, lineStyle: { width: 1, color: '#555' } },
      splitLine: { distance: -18, length: 14, lineStyle: { width: 1.5, color: '#555' } },
      axisLabel: { distance: 20, color: '#8896a7', fontSize: 10 },
      detail: {
        formatter: '{value}%',
        fontSize: 28,
        fontWeight: 'bold',
        color: '#e8ecf1',
        offsetCenter: [0, '65%'],
      },
      data: [{ value: 0, name: 'CPU' }],
    }],
  })
}

function updateChart() {
  if (!chart || !store.summary) return
  chart.setOption({
    series: [{ data: [{ value: +store.summary.cpu_percent.toFixed(1), name: 'CPU' }] }],
  })
}

// ---- Memory ----
const memPercent = computed(() => +(store.summary?.memory_percent ?? 0).toFixed(1))
const memUsed = computed(() => (store.summary?.memory_used_gb ?? 0).toFixed(1))
const memTotal = computed(() => (store.summary?.memory_total_gb ?? 0).toFixed(1))
const swapTotal = computed(() => store.summary?.swap_total_gb ?? 0)
const swapPercent = computed(() => {
  if (!store.summary?.swap_total_gb) return 0
  return +((store.summary.swap_used_gb / store.summary.swap_total_gb) * 100).toFixed(1)
})
const swapUsed = computed(() => (store.summary?.swap_used_gb ?? 0).toFixed(1))

function barColor(pct: number): string {
  if (pct >= 90) return 'linear-gradient(90deg, #f59e0b, #ef4444)'
  if (pct >= 70) return 'linear-gradient(90deg, #22c55e, #f59e0b)'
  return 'linear-gradient(90deg, #3b82f6, #22c55e)'
}
const memBarColor = computed(() => barColor(memPercent.value))
const swapBarColor = computed(() => barColor(swapPercent.value))

function statusClass(pct: number): string {
  if (pct >= 90) return 'danger'
  if (pct >= 70) return 'warning'
  return 'safe'
}
const memStatusClass = computed(() => statusClass(memPercent.value))
const swapStatusClass = computed(() => statusClass(swapPercent.value))

// ---- Uptime ----
const uptimeText = computed(() => {
  const sec = store.summary?.uptime_seconds
  if (sec === undefined || sec === null) return ''
  const d = Math.floor(sec / 86400)
  const h = Math.floor((sec % 86400) / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const parts: string[] = []
  if (d > 0) parts.push(`${d}d`)
  if (h > 0) parts.push(`${h}h`)
  parts.push(`${m}m`)
  return `已运行 ${parts.join(' ')}`
})

// ---- Lifecycle ----
onMounted(() => {
  initChart()
  updateChart()
  if (cpuChartRef.value) {
    resizeObserver = new ResizeObserver(() => chart?.resize())
    resizeObserver.observe(cpuChartRef.value)
  }
})

watch(() => store.summary, updateChart)

onUnmounted(() => {
  resizeObserver?.disconnect()
  chart?.dispose()
})
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
.panel-badge {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--color-safe);
  background: var(--color-safe-soft);
  padding: 2px 8px;
  border-radius: var(--radius-full);
}

/* ---- Body ---- */
.panel-body {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 20px;
  min-height: 240px;
}

/* ---- CPU ---- */
.cpu-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.chart-box {
  width: 100%;
  height: 180px;
}
.cpu-extra {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  width: 100%;
}
.extra-item {
  text-align: center;
  background: var(--bg-elevated);
  border-radius: var(--radius-sm);
  padding: 6px 4px;
}
.extra-label {
  display: block;
  font-size: 10px;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.3px;
  margin-bottom: 2px;
}
.extra-value {
  display: block;
  font-size: 14px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--text-primary);
}

/* ---- Memory ---- */
.memory-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.mem-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.mem-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}
.mem-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}
.mem-pct {
  font-size: 18px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.mem-pct.safe    { color: var(--color-safe); }
.mem-pct.warning { color: var(--color-warning); }
.mem-pct.danger  { color: var(--color-danger); }

.mem-bar-track {
  height: 8px;
  border-radius: 4px;
  background: rgba(255,255,255,0.06);
  overflow: hidden;
}
.mem-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.6s var(--ease-out);
  min-width: 2px;
}

.mem-detail {
  font-size: 11px;
  color: var(--text-tertiary);
  text-align: right;
}

/* ---- Uptime ---- */
.uptime-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-tertiary);
  padding-top: 4px;
  border-top: 1px solid var(--border-subtle);
}
</style>
