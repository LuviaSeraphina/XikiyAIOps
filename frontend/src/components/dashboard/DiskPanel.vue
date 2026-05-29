<template>
  <el-card shadow="hover" class="panel">
    <template #header><span class="panel-title">💾 磁盘使用率</span></template>
    <div ref="chartRef" class="chart-box"></div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { useSystemStore } from '@/stores/system'

const store = useSystemStore()
const chartRef = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null

function barColor(pct: number): string {
  if (pct < 70) return '#67C23A'
  if (pct < 90) return '#E6A23C'
  return '#F56C6C'
}

function updateChart() {
  if (!chart || !store.disks.length) return

  const names = store.disks.map((d) => d.mount_point)
  const values = store.disks.map((d) => +d.usage_percent.toFixed(1))

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: (params: { dataIndex: number }[]) => {
        const i = params[0].dataIndex
        const d = store.disks[i]
        return `
          <b>${d.mount_point}</b> (${d.filesystem})<br/>
          总量: ${d.total_gb} GB<br/>
          已用: ${d.used_gb} GB | 可用: ${d.free_gb} GB<br/>
          使用率: ${d.usage_percent}% | inode: ${d.inode_percent}%
        `
      },
    },
    xAxis: {
      type: 'category',
      data: names,
      axisLabel: { color: '#909399' },
    },
    yAxis: {
      type: 'value',
      max: 100,
      axisLabel: { formatter: '{value}%', color: '#909399' },
    },
    series: [{
      type: 'bar',
      data: values.map((v, i) => ({
        value: v,
        itemStyle: { color: barColor(v), borderRadius: [4, 4, 0, 0] },
      })),
      barWidth: 40,
      markLine: {
        silent: true,
        symbol: 'none',
        data: [
          { yAxis: 70, lineStyle: { color: '#E6A23C', type: 'dashed' } },
          { yAxis: 90, lineStyle: { color: '#F56C6C', type: 'dashed' } },
        ],
      },
    }],
  })
}

onMounted(() => {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
  updateChart()
})

watch(() => store.disks, updateChart, { deep: true })

onUnmounted(() => {
  chart?.dispose()
})
</script>

<style scoped>
.panel { height: 100%; }
.chart-box { height: 260px; }
.panel-title { font-size: 15px; font-weight: 600; }
</style>
