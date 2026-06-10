<template>
  <div class="panel-card">
    <div class="panel-header">
      <h3 class="panel-title">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
          <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
        </svg>
        磁盘使用率
      </h3>
    </div>
    <div ref="chartRef" class="chart-box"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { useSystemStore } from '@/stores/system'

const store = useSystemStore()
const chartRef = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null
let resizeObserver: ResizeObserver | null = null

function barColor(pct: number): string {
  if (pct >= 90) return '#ef4444'
  if (pct >= 70) return '#f59e0b'
  return '#22c55e'
}

function updateChart() {
  if (!chart) return
  const snap = store.snapshot
  if (!snap.diskRootTotalGb) return

  const names = ['/']
  const values = [+(snap.diskRootPercent ?? 0).toFixed(1)]

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      confine: true,
      appendToBody: true,
      backgroundColor: 'rgba(17, 22, 30, 0.96)',
      borderColor: 'rgba(255,255,255,0.1)',
      textStyle: { color: '#e8ecf1', fontSize: 12 },
      formatter: () => `
        <div style="font-weight:600;margin-bottom:6px;font-size:13px;">/</div>
        <div style="display:flex;gap:16px;margin-bottom:4px;">
          <span>总量 <b>${snap.diskRootTotalGb?.toFixed(1)} GB</b></span>
          <span>已用 <b>${snap.diskRootUsedGb?.toFixed(1)} GB</b></span>
        </div>
        <div style="margin-top:6px;font-weight:600;color:${barColor(snap.diskRootPercent ?? 0)}">使用率 ${snap.diskRootPercent?.toFixed(0)}%</div>
      `,
    },
    grid: { left: 45, right: 20, top: 10, bottom: 35 },
    xAxis: {
      type: 'category',
      data: names,
      axisLabel: { color: '#8896a7', fontSize: 11, rotate: names.length > 4 ? 15 : 0 },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      max: 100,
      axisLabel: { formatter: '{value}%', color: '#8896a7', fontSize: 11 },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } },
    },
    series: [{
      type: 'bar',
      data: values.map((v) => ({
        value: v,
        itemStyle: {
          color: barColor(v),
          borderRadius: [6, 6, 0, 0],
        },
      })),
      barMaxWidth: 56,
      emphasis: {
        itemStyle: { color: '#3b82f6' },
      },
      markLine: {
        silent: true,
        symbol: 'none',
        lineStyle: { type: 'dashed', width: 1 },
        data: [
          { yAxis: 70, lineStyle: { color: '#f59e0b' }, label: { formatter: '70%', color: '#f59e0b', fontSize: 10 } },
          { yAxis: 90, lineStyle: { color: '#ef4444' }, label: { formatter: '90%', color: '#ef4444', fontSize: 10 } },
        ],
      },
    }],
  })
}

onMounted(() => {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
  updateChart()
  resizeObserver = new ResizeObserver(() => chart?.resize())
  resizeObserver.observe(chartRef.value)
})

watch(() => store.snapshot.diskRootPercent, updateChart)

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
  transition: border-color var(--dur-gentle) var(--ease-out);
}
.panel-card:hover {
  border-color: var(--border-emphasis);
}

.panel-header {
  display: flex;
  align-items: center;
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

.chart-box {
  width: 100%;
  height: 260px;
  padding: 8px 4px 4px;
}
</style>
