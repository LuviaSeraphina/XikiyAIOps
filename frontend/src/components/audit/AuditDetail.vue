<template>
  <div class="audit-detail">
    <!-- Empty state -->
    <div v-if="!log" class="empty-state">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
        <circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>
      </svg>
      <span>请选择一条审计记录查看详情</span>
    </div>

    <template v-else>
      <div class="detail-header">
        <h3 class="detail-title">审计详情</h3>
        <StatusBadge :risk-level="log.risk_level" size="md" />
      </div>

      <div class="stage-list">
        <!-- 阶段 1：接收指令 -->
        <div class="stage-card" :class="{ active: activeStage === 1 }" @click="toggleStage(1)">
          <div class="stage-header">
            <span class="stage-num">1</span>
            <span class="stage-label">接收指令</span>
            <span class="stage-time">{{ log.stages[0].timestamp }}</span>
            <svg class="stage-arrow" :class="{ expanded: activeStage === 1 }" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </div>
          <transition name="fade-up">
            <div v-show="activeStage === 1" class="stage-body">
              <div class="stage-field">
                <span class="field-label">用户</span>
                <span class="field-value">{{ log.stages[0].user }}</span>
              </div>
              <div class="stage-field">
                <span class="field-label">指令</span>
                <blockquote>{{ log.stages[0].raw_input }}</blockquote>
              </div>
            </div>
          </transition>
        </div>

        <!-- 阶段 2：感知环境 -->
        <div class="stage-card" :class="{ active: activeStage === 2 }" @click="toggleStage(2)">
          <div class="stage-header">
            <span class="stage-num">2</span>
            <span class="stage-label">感知环境</span>
            <svg class="stage-arrow" :class="{ expanded: activeStage === 2 }" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </div>
          <transition name="fade-up">
            <div v-show="activeStage === 2" class="stage-body">
              <div class="stage-field">
                <span class="field-label">调用工具</span>
                <div class="tag-list">
                  <span v-for="t in log.stages[1].tools_called" :key="t" class="field-tag">{{ t }}</span>
                  <span v-if="!log.stages[1].tools_called.length" class="text-dim">无</span>
                </div>
              </div>
              <div class="stage-field">
                <span class="field-label">快照摘要</span>
                <span class="field-value">{{ log.stages[1].snapshot_summary }}</span>
              </div>
            </div>
          </transition>
        </div>

        <!-- 阶段 3：推理决策 -->
        <div class="stage-card" :class="{ active: activeStage === 3 }" @click="toggleStage(3)">
          <div class="stage-header">
            <span class="stage-num">3</span>
            <span class="stage-label">推理决策</span>
            <svg class="stage-arrow" :class="{ expanded: activeStage === 3 }" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </div>
          <transition name="fade-up">
            <div v-show="activeStage === 3" class="stage-body">
              <div class="stage-field">
                <span class="field-label">LLM 模型</span>
                <span class="field-value">{{ log.stages[2].llm_model }}</span>
              </div>
              <div class="stage-field">
                <span class="field-label">计划工具</span>
                <div class="tag-list">
                  <span v-for="t in log.stages[2].tool_calls_planned" :key="t" class="field-tag">{{ t }}</span>
                  <span v-if="!log.stages[2].tool_calls_planned.length" class="text-dim">无</span>
                </div>
              </div>
              <div v-if="log.stages[2].llm_raw_output" class="stage-field">
                <span class="field-label">LLM 原始输出</span>
                <pre class="code-block">{{ log.stages[2].llm_raw_output }}</pre>
              </div>
            </div>
          </transition>
        </div>

        <!-- 阶段 4：安全校验 -->
        <div class="stage-card security" :class="{ active: activeStage === 4 }" @click="toggleStage(4)">
          <div class="stage-header">
            <span class="stage-num">4</span>
            <span class="stage-label">安全校验</span>
            <span class="stage-decision" :class="`decision-${log.stages[3].decision}`">
              {{ decisionLabel(log.stages[3].decision) }}
            </span>
            <svg class="stage-arrow" :class="{ expanded: activeStage === 4 }" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </div>
          <transition name="fade-up">
            <div v-show="activeStage === 4" class="stage-body">
              <div class="stage-field">
                <span class="field-label">命中规则</span>
                <div class="tag-list">
                  <span v-for="r in log.stages[3].rules_hit" :key="r" class="field-tag danger">{{ r }}</span>
                  <span v-if="!log.stages[3].rules_hit.length" class="text-dim">无</span>
                </div>
              </div>
              <div class="stage-field">
                <span class="field-label">风险评分</span>
                <div class="score-bar">
                  <div class="score-track">
                    <div
                      class="score-fill"
                      :style="{ width: log.stages[3].risk_score + '%', background: scoreColor(log.stages[3].risk_score) }"
                    />
                  </div>
                  <span class="score-value" :style="{ color: scoreColor(log.stages[3].risk_score) }">
                    {{ log.stages[3].risk_score }}
                  </span>
                </div>
              </div>
              <div class="stage-field">
                <span class="field-label">原因</span>
                <span class="field-value">{{ log.stages[3].reason }}</span>
              </div>
            </div>
          </transition>
        </div>

        <!-- 阶段 5：执行结果 -->
        <div class="stage-card" :class="{ active: activeStage === 5 }" @click="toggleStage(5)">
          <div class="stage-header">
            <span class="stage-num">5</span>
            <span class="stage-label">执行结果</span>
            <span v-if="log.stages[4].exit_code === 0" class="exit-ok">✓ 成功</span>
            <span v-else-if="log.stages[4].exit_code !== null" class="exit-fail">✕ 失败</span>
            <svg class="stage-arrow" :class="{ expanded: activeStage === 5 }" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </div>
          <transition name="fade-up">
            <div v-show="activeStage === 5" class="stage-body">
              <div class="stage-field">
                <span class="field-label">动作</span>
                <span class="field-value">{{ log.stages[4].action_taken }}</span>
              </div>
              <div class="stage-field">
                <span class="field-label">耗时</span>
                <span class="field-value">{{ log.stages[4].duration_ms }}ms</span>
              </div>
              <div v-if="log.stages[4].stdout" class="stage-field">
                <span class="field-label">stdout</span>
                <pre class="code-block">{{ log.stages[4].stdout }}</pre>
              </div>
              <div v-if="log.stages[4].stderr" class="stage-field">
                <span class="field-label">stderr</span>
                <pre class="code-block error">{{ log.stages[4].stderr }}</pre>
              </div>
            </div>
          </transition>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { AuditLog } from '@/types'
import StatusBadge from '@/components/common/StatusBadge.vue'

defineProps<{ log: AuditLog | null }>()

const activeStage = ref<number | null>(4) // 默认展开安全校验

function toggleStage(n: number) {
  activeStage.value = activeStage.value === n ? null : n
}

function scoreColor(score: number): string {
  if (score >= 70) return '#ef4444'
  if (score >= 30) return '#f59e0b'
  return '#22c55e'
}

function decisionLabel(d: string): string {
  switch (d) {
    case 'allowed':   return '✅ 放行'
    case 'blocked':   return '❌ 拦截'
    case 'confirmed': return '👆 确认执行'
    default:          return d
  }
}
</script>

<style scoped>
.audit-detail {
  padding: 20px;
  height: 100%;
  overflow-y: auto;
}

.empty-state {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--text-tertiary);
  font-size: 13px;
}

/* ---- Detail header ---- */
.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.detail-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

/* ---- Stage cards ---- */
.stage-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.stage-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  overflow: hidden;
  transition: border-color var(--duration-fast) var(--ease-out);
  cursor: pointer;
}
.stage-card:hover {
  border-color: var(--border-default);
}
.stage-card.active {
  border-color: var(--border-emphasis);
}
.stage-card.security {
  border-left: 3px solid var(--color-warning);
}

.stage-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  user-select: none;
}
.stage-num {
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--bg-elevated);
  font-size: 11px;
  font-weight: 700;
  color: var(--text-secondary);
  flex-shrink: 0;
}
.stage-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
}
.stage-time {
  font-size: 11px;
  color: var(--text-tertiary);
}
.stage-decision {
  font-size: 11px;
  font-weight: 600;
  padding: 1px 8px;
  border-radius: var(--radius-full);
}
.decision-allowed   { color: var(--color-safe); background: var(--color-safe-soft); }
.decision-blocked   { color: var(--color-danger); background: var(--color-danger-soft); }
.decision-confirmed { color: var(--color-warning); background: var(--color-warning-soft); }

.exit-ok   { font-size: 11px; color: var(--color-safe); font-weight: 600; }
.exit-fail { font-size: 11px; color: var(--color-danger); font-weight: 600; }

.stage-arrow {
  color: var(--text-tertiary);
  transition: transform var(--duration-fast) var(--ease-out);
  flex-shrink: 0;
}
.stage-arrow.expanded {
  transform: rotate(180deg);
}

/* ---- Body ---- */
.stage-body {
  padding: 0 14px 12px 46px;
}
.stage-field {
  margin-bottom: 8px;
}
.stage-field:last-child {
  margin-bottom: 0;
}
.field-label {
  display: block;
  font-size: 10px;
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
}
.field-value {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.5;
}

blockquote {
  border-left: 3px solid var(--color-accent);
  padding: 6px 12px;
  margin: 0;
  background: var(--bg-elevated);
  border-radius: 0 4px 4px 0;
  font-size: 13px;
  color: var(--text-primary);
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.field-tag {
  font-size: 11px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: var(--bg-elevated);
  color: var(--text-secondary);
}
.field-tag.danger {
  background: var(--color-danger-soft);
  color: var(--color-danger);
}

/* Score bar */
.score-bar {
  display: flex;
  align-items: center;
  gap: 10px;
}
.score-track {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: rgba(255,255,255,0.06);
  overflow: hidden;
}
.score-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s var(--ease-out);
}
.score-value {
  font-size: 15px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  min-width: 30px;
  text-align: right;
}

/* Code block */
.code-block {
  background: rgba(0,0,0,0.3);
  color: #a8b8c8;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  font-size: 11.5px;
  font-family: var(--font-mono);
  max-height: 160px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.45;
  margin: 0;
}
.code-block.error {
  color: #f88;
}

.text-dim {
  color: var(--text-tertiary);
  font-size: 12px;
}

.dim { color: var(--text-secondary); }
.mr-4 { margin-right: 4px; }
.ml-8 { margin-left: 8px; }
</style>
