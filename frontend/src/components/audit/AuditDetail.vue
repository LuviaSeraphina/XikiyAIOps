<template>
  <div class="detail-panel">
    <!-- 空状态 -->
    <div v-if="!item" class="state-box">
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" opacity="0.35">
        <circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>
      </svg>
      <span>选择一条记录查看详情</span>
    </div>

    <!-- 详情 -->
    <template v-else>
      <div class="detail-header">
        <h3>审计详情</h3>
        <span class="risk-badge" :class="'risk-' + item.risk_level">
          {{ item.risk_level === 'dangerous' ? '高危' : item.risk_level === 'restricted' ? '受限' : '安全' }}
        </span>
      </div>

      <div class="stages">
        <!-- 阶段 1: 接收指令 -->
        <StageBlock :open="openStage === 1" @toggle="openStage = openStage === 1 ? null : 1">
          <template #header>
            <span class="stage-num">1</span>
            <span class="stage-name">接收指令</span>
            <span class="stage-extra">{{ item.stages[0]?.timestamp || '' }}</span>
          </template>
          <div class="stage-fields">
            <div class="field">
              <span class="field-key">用户</span>
              <span class="field-val">{{ item.stages[0]?.user || '-' }}</span>
            </div>
            <div class="field">
              <span class="field-key">指令</span>
              <span class="field-val quote">{{ item.stages[0]?.raw_input || '-' }}</span>
            </div>
          </div>
        </StageBlock>

        <!-- 阶段 2: 感知环境 -->
        <StageBlock :open="openStage === 2" @toggle="openStage = openStage === 2 ? null : 2">
          <template #header>
            <span class="stage-num">2</span>
            <span class="stage-name">感知环境</span>
          </template>
          <div class="stage-fields">
            <div class="field">
              <span class="field-key">调用工具</span>
              <div class="tag-row">
                <span v-if="!item.stages[1]?.tools_called?.length" class="text-dim">无</span>
                <span v-for="t in item.stages[1]?.tools_called || []" :key="t" class="tag">{{ t }}</span>
              </div>
            </div>
            <div class="field">
              <span class="field-key">快照摘要</span>
              <span class="field-val">{{ item.stages[1]?.snapshot_summary || '-' }}</span>
            </div>
          </div>
        </StageBlock>

        <!-- 阶段 3: 推理决策 -->
        <StageBlock :open="openStage === 3" @toggle="openStage = openStage === 3 ? null : 3">
          <template #header>
            <span class="stage-num">3</span>
            <span class="stage-name">推理决策</span>
          </template>
          <div class="stage-fields">
            <div class="field">
              <span class="field-key">模型</span>
              <span class="field-val">{{ item.stages[2]?.llm_model || '-' }}</span>
            </div>
            <div class="field" v-if="item.stages[2]?.llm_raw_output">
              <span class="field-key">原始输出</span>
              <pre class="code-block">{{ item.stages[2].llm_raw_output.slice(0, 500) }}</pre>
            </div>
          </div>
        </StageBlock>

        <!-- 阶段 4: 安全校验（默认展开） -->
        <StageBlock :open="openStage === 4" @toggle="openStage = openStage === 4 ? null : 4">
          <template #header>
            <span class="stage-num stage-num-sec">4</span>
            <span class="stage-name">安全校验</span>
            <span class="stage-extra" :style="{ color: decisionColor }">{{ decisionText }}</span>
          </template>
          <div class="stage-fields">
            <div class="field">
              <span class="field-key">风险评分</span>
              <span class="field-val" :style="{ color: scoreColor(item.stages[3]?.risk_score || 0) }">
                {{ item.stages[3]?.risk_score ?? '-' }}
              </span>
            </div>
            <div class="field" v-if="item.stages[3]?.rules_hit?.length">
              <span class="field-key">命中规则</span>
              <div class="tag-row">
                <span v-for="r in item.stages[3].rules_hit" :key="r" class="tag tag-danger">{{ r }}</span>
              </div>
            </div>
            <div class="field">
              <span class="field-key">决策理由</span>
              <span class="field-val">{{ item.stages[3]?.reason || '-' }}</span>
            </div>
          </div>
        </StageBlock>

        <!-- 阶段 5: 执行结果 -->
        <StageBlock :open="openStage === 5" @toggle="openStage = openStage === 5 ? null : 5">
          <template #header>
            <span class="stage-num">5</span>
            <span class="stage-name">执行结果</span>
            <span class="stage-extra" :class="item.stages[4]?.exit_code === 0 ? 'text-safe' : 'text-danger'">
              {{ item.stages[4]?.exit_code === 0 ? '成功' : item.stages[4]?.exit_code != null ? '失败' : '' }}
            </span>
          </template>
          <div class="stage-fields">
            <div class="field">
              <span class="field-key">动作</span>
              <span class="field-val">{{ item.stages[4]?.action_taken || '-' }}</span>
            </div>
            <div class="field" v-if="item.stages[4]?.duration_ms">
              <span class="field-key">耗时</span>
              <span class="field-val">{{ item.stages[4].duration_ms }}ms</span>
            </div>
            <div class="field" v-if="item.stages[4]?.stdout">
              <span class="field-key">stdout</span>
              <pre class="code-block">{{ item.stages[4].stdout }}</pre>
            </div>
            <div class="field" v-if="item.stages[4]?.stderr">
              <span class="field-key">stderr</span>
              <pre class="code-block code-error">{{ item.stages[4].stderr }}</pre>
            </div>
          </div>
        </StageBlock>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { AuditLog } from '@/types'
import StageBlock from './StageBlock.vue'

const props = defineProps<{ item: AuditLog | null }>()
const openStage = ref<number | null>(4) // 默认展开安全校验

const decisionText = computed(() => {
  const d = props.item?.stages[3]?.decision
  if (d === 'blocked') return '已拦截'
  if (d === 'confirmed') return '已确认'
  if (d === 'allowed') return '已放行'
  return ''
})
const decisionColor = computed(() => {
  const d = props.item?.stages[3]?.decision
  if (d === 'blocked') return 'var(--color-danger)'
  if (d === 'allowed' || d === 'confirmed') return 'var(--color-safe)'
  return 'var(--text-tertiary)'
})

function scoreColor(s: number): string {
  if (s >= 70) return 'var(--color-danger)'
  if (s >= 30) return 'var(--color-warning)'
  return 'var(--color-safe)'
}
</script>

<style scoped>
.detail-panel {
  height: 100%;
  overflow-y: auto;
  padding: 18px;
}

.state-box {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--text-tertiary);
  font-size: 13px;
}

.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.detail-header h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.risk-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
}
.risk-read_only  { background: var(--color-safe-soft); color: var(--color-safe); }
.risk-restricted { background: var(--color-warning-soft); color: var(--color-warning); }
.risk-dangerous  { background: var(--color-danger-soft); color: var(--color-danger); }

/* ── Stages ── */
.stages {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* ── Fields ── */
.stage-fields {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px 0 10px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.field-key {
  font-size: 10px;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.4px;
}
.field-val {
  font-size: 13px;
  color: var(--text-primary);
}
.field-val.quote {
  padding: 6px 10px;
  background: var(--bg-root);
  border-radius: 5px;
  border-left: 3px solid var(--color-accent);
  color: var(--text-secondary);
}
.tag-row { display: flex; flex-wrap: wrap; gap: 4px; }
.tag {
  display: inline-block;
  font-size: 11px;
  padding: 2px 7px;
  background: var(--bg-hover);
  border-radius: 4px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}
.tag-danger { background: var(--color-danger-soft); color: var(--color-danger); }

.code-block {
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.5;
  background: var(--bg-root);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 8px 10px;
  margin: 2px 0 0;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
}
.code-error {
  border-color: var(--color-danger-soft);
  color: var(--color-danger);
}

.text-dim { color: var(--text-tertiary); }
.text-safe { color: var(--color-safe); }
.text-danger { color: var(--color-danger); }
</style>
