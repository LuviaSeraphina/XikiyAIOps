<template>
  <div class="audit-filter">
    <el-form :inline="true" size="default">
      <el-form-item>
        <el-input
          v-model="local.keyword"
          placeholder="搜索指令关键字或用户名..."
          clearable
          :prefix-icon="Search"
          @change="emitFilter"
        />
      </el-form-item>
      <el-form-item>
        <el-select
          v-model="local.riskLevel"
          placeholder="风险等级"
          clearable
          @change="emitFilter"
        >
          <el-option label="全部" value="" />
          <el-option label="🟢 安全 (read_only)" value="read_only" />
          <el-option label="🟡 需确认 (restricted)" value="restricted" />
          <el-option label="🔴 高危 (dangerous)" value="dangerous" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-date-picker
          v-model="local.dateRange"
          type="daterange"
          range-separator="~"
          start-placeholder="开始"
          end-placeholder="结束"
          value-format="YYYY-MM-DD"
          @change="emitFilter"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="emitFilter">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue'
import { Search } from '@element-plus/icons-vue'
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
  padding: 12px 16px 0;
  background: var(--bg-panel);
  border-bottom: 1px solid var(--border-color);
}
</style>
