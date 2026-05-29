<template>
  <el-card shadow="hover" class="panel">
    <template #header><span class="panel-title">💻 CPU & 内存</span></template>
    <div class="panel-body">
      <!-- 左：CPU 仪表盘 -->
      <div ref="cpuChartRef" class="chart-box"></div>
      <!-- 右：内存 + Swap -->
      <div class="memory-box">
        <div class="mem-item">
          <span class="mem-label">内存</span>
          <el-progress
            :percentage="memPercent"
            :color="progressColor(memPercent)"
            :stroke-width="14"
          />
          <span class="mem-detail">
            {{ memUsed }} GB / {{ memTotal }} GB
          </span>
        </div>
        <div class="mem-item" v-if="swapTotal > 0">
          <span class="mem-label">Swap</span>
          <el-progress
            :percentage="swapPercent"
            :color="progressColor(swapPercent)"
            :stroke-width="14"
          />
          <span class="mem-detail">
            {{ swapUsed }} GB / {{ swapTotal.toFixed(1) }} GB
          </span>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { useSystemStore } from '@/stores/system'

const store = useSystemStore()
const cpuChartRef = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null

// ---- CPU 仪表盘 ----
function initChart() {
  if (!cpuChartRef.value) return
  chart = echarts.init(cpuChartRef.value)
}

function updateChart() {
  if (!chart || !store.summary) return
  const s = store.summary
  chart.setOption({
    series: [{
      type: 'gauge',
      startAngle: 210,
      endAngle: -30,
      center: ['50%', '55%'],
      radius: '85%',
      min: 0,
      max: 100,
      axisLine: {
        lineStyle: {
          width: 14,
          color: [
            [0.3, '#67C23A'],
            [0.7, '#E6A23C'],
            [1, '#F56C6C'],
          ],
        },
      },
      pointer: { length: '60%', width: 4 },
      detail: {
        formatter: '{value}%',
        fontSize: 20,
        offsetCenter: [0, '60%'],
      },
      data: [{ value: +s.cpu_percent.toFixed(1), name: 'CPU' }],
    }],
  })
}

// ---- 内存 / Swap ----
const memPercent = computed(() => +(store.summary?.memory_percent ?? 0).toFixed(1))
const memUsed = computed(() => (store.summary?.memory_used_gb ?? 0).toFixed(1))
const memTotal = computed(() => (store.summary?.memory_total_gb ?? 0).toFixed(1))
const swapTotal = computed(() => store.summary?.swap_total_gb ?? 0)
const swapPercent = computed(() => {
  if (!store.summary?.swap_total_gb) return 0
  return +((store.summary.swap_used_gb / store.summary.swap_total_gb) * 100).toFixed(1)
})
const swapUsed = computed(() => (store.summary?.swap_used_gb ?? 0).toFixed(1))

function progressColor(pct: number): string {
  if (pct < 70) return 'var(--color-safe)'
  if (pct < 90) return 'var(--color-warning)'
  return 'var(--color-danger)'
}

// ---- 生命周期 ----
onMounted(() => {
  initChart()
  updateChart()
})

watch(() => store.summary, updateChart)

onUnmounted(() => {
  chart?.dispose()
})
</script>

<style scoped>
.panel {
  height: 100%;
}
.panel-body {
  display: flex;
  align-items: center;
  gap: 20px;
  height: 220px;
}
.chart-box {
  flex: 1;
  height: 100%;
}
.memory-box {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 20px;
}
.mem-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.mem-label {
  font-size: 13px;
  color: var(--text-secondary);
}
.mem-detail {
  font-size: 12px;
  color: var(--text-secondary);
  text-align: right;
}
.panel-title {
  font-size: 15px;
  font-weight: 600;
}
</style>
