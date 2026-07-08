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
        <div class="header-badges">
          <!-- 异常标记 (v2.1) -->
          <span v-if="item.is_anomaly" class="anomaly-badge" :class="'anomaly-' + (item.anomaly_type || 'none')">
            ⚠ {{ anomalyLabel }}
          </span>
          <span class="risk-badge" :class="'risk-' + item.risk_level">
            {{ item.risk_level === 'dangerous' ? '高危' : item.risk_level === 'restricted' ? '受限' : '安全' }}
          </span>
        </div>
      </div>

      <!-- ====== 异常回溯面板 (v2.1 新增) ====== -->
      <div v-if="tracebackData" class="traceback-panel">
        <div class="traceback-header">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
          </svg>
          <span>推理链路溯源</span>
          <button class="traceback-toggle" @click="showTraceback = !showTraceback">
            {{ showTraceback ? '收起' : '展开' }}
          </button>
        </div>

        <div v-if="showTraceback" class="traceback-body">
          <!-- 因果链流程图 -->
          <div class="causal-flow">
            <div class="flow-step" v-for="(step, idx) in causalSteps" :key="idx">
              <div class="flow-badge" :class="{ 'flow-anomaly': step.isAnomaly }">
                {{ idx + 1 }}
              </div>
              <div class="flow-label">{{ step.label }}</div>
              <div class="flow-desc">{{ step.desc }}</div>
              <!-- 箭头 (非最后一步) -->
              <div v-if="idx < causalSteps.length - 1" class="flow-arrow">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 18 18 12 6 6"/></svg>
              </div>
            </div>
          </div>

          <!-- 回溯指引 (仅异常时显示) -->
          <div v-if="tracebackData.traceback_guidance" class="guidance-box">
            <div class="guidance-title">🔍 异常回溯指引</div>
            <div class="guidance-grid">
              <div class="guidance-item">
                <span class="guidance-key">根因阶段</span>
                <span class="guidance-val">{{ tracebackData.traceback_guidance.root_cause_stage }}</span>
              </div>
              <div class="guidance-item">
                <span class="guidance-key">根因</span>
                <span class="guidance-val">{{ tracebackData.traceback_guidance.root_cause }}</span>
              </div>
              <div class="guidance-item full-width">
                <span class="guidance-key">回溯路径</span>
                <span class="guidance-val">{{ tracebackData.traceback_guidance.trace_path }}</span>
              </div>
              <div class="guidance-item full-width">
                <span class="guidance-key">建议</span>
                <span class="guidance-val suggestion">{{ tracebackData.traceback_guidance.suggestion }}</span>
              </div>
            </div>
          </div>

          <!-- 关联操作 (同会话) -->
          <div v-if="tracebackData.related_ops?.length" class="related-section">
            <div class="related-title">
              同会话关联操作
              <span class="related-count">{{ tracebackData.related_ops_count }} 条</span>
            </div>
            <div class="related-list">
              <div
                v-for="op in tracebackData.related_ops"
                :key="op.id"
                class="related-item"
                :class="{ 'related-anomaly': op.is_anomaly }"
              >
                <span class="related-time">{{ formatShortTime(op.timestamp) }}</span>
                <span class="related-input">{{ op.input_preview || '(空)' }}</span>
                <span v-if="op.is_anomaly" class="related-anomaly-tag">异常</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 加载回溯按钮 (未加载时) -->
      <div v-else-if="item.is_anomaly" class="traceback-load-bar">
        <button class="btn-traceback" @click="loadTraceback">🔍 查看推理链路溯源</button>
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

        <!-- 阶段 4: 安全校验 -->
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
            <span class="stage-num" :class="{ 'stage-num-danger': item.stages[4]?.is_anomaly }">5</span>
            <span class="stage-name">执行结果</span>
            <span class="stage-extra" :class="item.stages[4]?.is_anomaly ? 'text-danger' : 'text-safe'">
              {{ item.stages[4]?.is_anomaly ? '异常' : '成功' }}
            </span>
          </template>
          <div class="stage-fields">
            <div class="field">
              <span class="field-key">动作</span>
              <span class="field-val">{{ item.stages[4]?.action_taken || '-' }}</span>
            </div>
            <!-- v2.1: 工具执行明细 -->
            <div v-if="item.stages[4]?.tool_executions?.length" class="field">
              <span class="field-key">工具执行明细</span>
              <div class="tool-exec-list">
                <div
                  v-for="te in item.stages[4]!.tool_executions!"
                  :key="te.tool_name"
                  class="tool-exec-item"
                  :class="{ 'tool-exec-error': te.is_anomaly }"
                >
                  <span class="te-name">{{ te.tool_name }}</span>
                  <span class="te-status" :class="te.is_anomaly ? 'text-danger' : 'text-safe'">
                    {{ te.is_anomaly ? '✗' : '✓' }}
                  </span>
                  <span class="te-output" v-if="te.output_summary">{{ te.output_summary }}</span>
                </div>
              </div>
            </div>
            <div class="field" v-if="item.stages[4]?.duration_ms">
              <span class="field-key">耗时</span>
              <span class="field-val">{{ item.stages[4].duration_ms }}ms</span>
            </div>
          </div>
        </StageBlock>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { AuditLog, TracebackResponse, CausalChain } from '@/types'
import StageBlock from './StageBlock.vue'
import { fetchTraceback } from '@/api/audit'

const props = defineProps<{ item: AuditLog | null }>()
const openStage = ref<number | null>(4) // 默认展开安全校验

// v2.1: 异常回溯状态
const showTraceback = ref(false)
const tracebackData = ref<TracebackResponse | null>(null)

// 选中审计记录变化时, 自动加载异常回溯
watch(() => props.item?.id, (newId) => {
  tracebackData.value = null
  showTraceback.value = false
  // v2.1: 异常记录自动加载回溯, 无需手动点击按钮
  if (newId && props.item?.is_anomaly) {
    loadTraceback()
  }
})

async function loadTraceback() {
  if (!props.item?.id) return
  try {
    const res = await fetchTraceback(props.item.id)
    if (res.code === 0 && res.data) {
      tracebackData.value = res.data
      showTraceback.value = true
    }
  } catch (e) {
    console.error('回溯数据加载失败:', e)
  }
}

const anomalyLabel = computed(() => {
  const t = props.item?.anomaly_type
  const map: Record<string, string> = {
    jailbreak_blocked: '越狱拦截',
    injection_blocked: '注入拦截',
    dangerous_blocked: '高危拦截',
    security_blocked: '安全拦截',
    tool_error: '工具异常',
  }
  return map[t || ''] || '异常'
})

// 因果链步骤 (用于流程图渲染)
const causalSteps = computed(() => {
  const chain: CausalChain | null | undefined = tracebackData.value?.causal_chain
  if (!chain) return []
  const isAnomaly = tracebackData.value?.is_anomaly
  return [
    {
      label: '1. 输入 → 感知',
      desc: chain.input_to_perception?.description || '',
      isAnomaly: false,
    },
    {
      label: '2. 感知 → 推理',
      desc: chain.perception_to_reasoning?.description || '',
      isAnomaly: false,
    },
    {
      label: '3. 推理 → 校验',
      desc: chain.reasoning_to_validation?.description || '',
      isAnomaly: chain.reasoning_to_validation?.decision === 'blocked',
    },
    {
      label: '4. 校验 → 执行',
      desc: chain.validation_to_execution?.description || '',
      isAnomaly: isAnomaly,
    },
  ]
})

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

function formatShortTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}
</script>

<style scoped>
.detail-panel {
  height: 100%;
  overflow-y: auto;
  padding: 20px;
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
  margin-bottom: 16px;
}
.detail-header h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.risk-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: var(--radius-sm);
}
.risk-read_only  { background: var(--color-safe-soft); color: var(--color-safe); }
.risk-restricted { background: var(--color-warning-soft); color: var(--color-warning); }
.risk-dangerous  { background: var(--color-danger-soft); color: var(--color-danger); }

/* ── Stages ── */
.stages {
  display: flex;
  flex-direction: column;
  gap: 8px;
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
  gap: 3px;
}
.field-key {
  font-size: 10px;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
}
.field-val {
  font-size: 13px;
  color: var(--text-primary);
}
.field-val.quote {
  padding: 8px 12px;
  background: var(--bg-root);
  border-radius: var(--radius-sm);
  border-left: 3px solid var(--color-accent);
  color: var(--text-secondary);
  font-size: 13px;
}
.tag-row { display: flex; flex-wrap: wrap; gap: 4px; }
.tag {
  display: inline-block;
  font-size: 11px;
  padding: 2px 8px;
  background: var(--bg-hover);
  border-radius: var(--radius-sm);
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
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  margin: 2px 0 0;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
  color: var(--text-secondary);
}
.code-error {
  border-color: rgba(248, 113, 113, 0.2);
  color: var(--color-danger);
}

.text-dim { color: var(--text-tertiary); }
.text-safe { color: var(--color-safe); }
.text-danger { color: var(--color-danger); }

/* ── 异常标记 ── */
.header-badges {
  display: flex;
  gap: 6px;
  align-items: center;
}
.anomaly-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: var(--radius-sm);
}
.anomaly-jailbreak_blocked { background: var(--color-danger-soft); color: var(--color-danger); }
.anomaly-injection_blocked { background: var(--color-danger-soft); color: var(--color-danger); }
.anomaly-dangerous_blocked { background: var(--color-warning-soft); color: var(--color-warning); }
.anomaly-security_blocked  { background: var(--color-warning-soft); color: var(--color-warning); }
.anomaly-tool_error        { background: var(--color-warning-soft); color: var(--color-warning); }

/* ── 阶段 5: 危险标记 ── */
.stage-num-danger {
  background: var(--color-danger-soft) !important;
  color: var(--color-danger) !important;
}

/* ── 回溯面板 ── */
.traceback-panel {
  margin-bottom: 16px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  overflow: hidden;
  background: var(--bg-surface);
}
.traceback-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: var(--bg-sidebar);
  border-bottom: 1px solid var(--border-subtle);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.traceback-toggle {
  margin-left: auto;
  font-size: 12px;
  color: var(--color-accent);
  background: none;
  border: none;
  cursor: pointer;
  padding: 3px 10px;
  border-radius: var(--radius-sm);
  transition: background var(--dur-quick) var(--ease-spring);
}
.traceback-toggle:hover { background: var(--color-accent-soft); }
.traceback-body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ── 因果链流程图 ── */
.causal-flow {
  display: flex;
  align-items: flex-start;
  gap: 0;
  overflow-x: auto;
  padding: 8px 0;
}
.flow-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 120px;
  flex-shrink: 0;
}
.flow-badge {
  width: 28px; height: 28px;
  border-radius: 50%;
  background: var(--bg-hover);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-secondary);
  border: 2px solid var(--border-subtle);
  font-family: var(--font-mono);
}
.flow-badge.flow-anomaly {
  background: var(--color-danger-soft);
  color: var(--color-danger);
  border-color: var(--color-danger);
}
.flow-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-primary);
  text-align: center;
}
.flow-desc {
  font-size: 10px;
  color: var(--text-tertiary);
  text-align: center;
  max-width: 140px;
  line-height: 1.4;
}
.flow-arrow {
  display: flex;
  align-items: center;
  padding: 0 4px;
  color: var(--text-tertiary);
  margin-top: 6px;
}

/* ── 回溯指引 ── */
.guidance-box {
  background: var(--color-danger-soft);
  border: 1px solid rgba(248, 113, 113, 0.2);
  border-radius: var(--radius-md);
  padding: 14px;
}
.guidance-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-danger);
  margin-bottom: 10px;
}
.guidance-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.guidance-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.guidance-item.full-width {
  grid-column: 1 / -1;
}
.guidance-key {
  font-size: 10px;
  color: var(--text-tertiary);
  text-transform: uppercase;
  font-weight: 600;
}
.guidance-val {
  font-size: 12px;
  color: var(--text-primary);
  line-height: 1.5;
}
.guidance-val.suggestion {
  color: var(--color-safe);
  font-weight: 500;
}

/* ── 关联操作 ── */
.related-section {
  border-top: 1px solid var(--border-subtle);
  padding-top: 12px;
}
.related-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.related-count {
  font-size: 10px;
  color: var(--text-tertiary);
  font-weight: 400;
}
.related-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 150px;
  overflow-y: auto;
}
.related-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 10px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  background: var(--bg-root);
}
.related-item.related-anomaly {
  background: var(--color-danger-soft);
}
.related-time {
  color: var(--text-tertiary);
  font-family: var(--font-mono);
  font-size: 11px;
  white-space: nowrap;
}
.related-input {
  color: var(--text-secondary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.related-anomaly-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  background: var(--color-danger);
  color: #fff;
  font-weight: 700;
}

/* ── 回溯加载按钮 ── */
.traceback-load-bar {
  margin-bottom: 14px;
}
.btn-traceback {
  width: 100%;
  padding: 10px 0;
  background: var(--bg-surface);
  border: 1px dashed var(--border-default);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--color-accent);
  cursor: pointer;
  transition: all var(--dur-quick) var(--ease-spring);
}
.btn-traceback:hover {
  background: var(--color-accent-soft);
  border-color: var(--color-accent);
}

/* ── 工具执行明细 ── */
.tool-exec-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 4px;
}
.tool-exec-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 10px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  background: var(--bg-root);
}
.tool-exec-item.tool-exec-error {
  background: var(--color-danger-soft);
}
.te-name {
  font-family: var(--font-mono);
  color: var(--text-primary);
  font-weight: 500;
  min-width: 120px;
}
.te-status {
  flex-shrink: 0;
  font-size: 12px;
}
.te-output {
  color: var(--text-tertiary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
}
</style>
