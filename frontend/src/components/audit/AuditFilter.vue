<template>
  <div class="audit-filter">
    <div class="filter-row">
      <div class="filter-input">
        <svg class="filter-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <input
          v-model="local.keyword"
          class="filter-text-input"
          placeholder="搜索指令关键字或用户名..."
          @input="emitFilter"
        />
      </div>

      <el-select
        v-model="local.riskLevel"
        placeholder="风险等级"
        clearable
        style="width: 170px;"
        @change="emitFilter"
      >
        <el-option label="全部" value="" />
        <el-option label="安全 (read_only)" value="read_only" />
        <el-option label="需确认 (restricted)" value="restricted" />
        <el-option label="高危 (dangerous)" value="dangerous" />
      </el-select>

      <el-date-picker
        v-model="local.dateRange"
        type="daterange"
        range-separator="~"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        value-format="YYYY-MM-DD"
        style="width: 240px;"
        @change="emitFilter"
      />

      <el-button type="primary" @click="emitFilter">查询</el-button>
      <el-button @click="reset">重置</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue'
import type { RiskLevel } from '@/types'

const emit = defineEmits<{
  'filter-change': [params: { keyword: string; riskLevel: RiskLevel | ''; dateRange: string[] }]
}>()

const local = reactive({
  keyword: '',
  riskLevel: '' as RiskLevel | '',
  dateRange: [] as string[],
})

function emitFilter() {
  emit('filter-change', {
    keyword: local.keyword,
    riskLevel: local.riskLevel,
    dateRange: local.dateRange,
  })
}

function reset() {
  local.keyword = ''
  local.riskLevel = ''
  local.dateRange = []
  emitFilter()
}
</script>

<style scoped>
.audit-filter {
  padding: 14px 20px;
  background: var(--bg-elevated);
  border-bottom: 1px solid var(--border-subtle);
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.filter-input {
  position: relative;
  flex: 1;
  min-width: 180px;
  max-width: 300px;
}
.filter-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-tertiary);
  pointer-events: none;
}
.filter-text-input {
  width: 100%;
  height: 32px;
  padding: 0 12px 0 32px;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: 13px;
  font-family: var(--font-sans);
  outline: none;
  transition: border-color var(--duration-fast) var(--ease-out);
}
.filter-text-input::placeholder {
  color: var(--text-tertiary);
}
.filter-text-input:focus {
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px var(--color-accent-soft);
}
</style>
