<template>
  <div class="audit-detail">
    <el-empty v-if="!log" description="请选择一条审计记录查看详情" />

    <template v-else>
      <h3 class="detail-title">审计详情</h3>

      <el-collapse v-model="activeNames">
        <!-- 阶段 1：接收指令 -->
        <el-collapse-item name="1">
          <template #title>
            <span class="stage-title">📥 接收指令</span>
          </template>
          <div class="stage-body">
            <p><b>用户：</b>{{ log.stages[0].user }}</p>
            <p><b>时间：</b>{{ log.stages[0].timestamp }}</p>
            <blockquote>{{ log.stages[0].raw_input }}</blockquote>
          </div>
        </el-collapse-item>

        <!-- 阶段 2：感知环境 -->
        <el-collapse-item name="2">
          <template #title>
            <span class="stage-title">🔍 感知环境</span>
          </template>
          <div class="stage-body">
            <p>
              <b>调用工具：</b>
              <el-tag v-for="t in log.stages[1].tools_called" :key="t" size="small" class="mr-4">{{ t }}</el-tag>
              <span v-if="!log.stages[1].tools_called.length" class="dim">无</span>
            </p>
            <p><b>快照摘要：</b>{{ log.stages[1].snapshot_summary }}</p>
          </div>
        </el-collapse-item>

        <!-- 阶段 3：推理决策 -->
        <el-collapse-item name="3">
          <template #title>
            <span class="stage-title">🧠 推理决策</span>
          </template>
          <div class="stage-body">
            <p><b>LLM 模型：</b>{{ log.stages[2].llm_model }}</p>
            <p>
              <b>计划工具：</b>
              <el-tag v-for="t in log.stages[2].tool_calls_planned" :key="t" size="small" class="mr-4">{{ t }}</el-tag>
              <span v-if="!log.stages[2].tool_calls_planned.length" class="dim">无</span>
            </p>
            <el-collapse class="inner-collapse" v-if="log.stages[2].llm_raw_output">
              <el-collapse-item title="LLM 原始输出">
                <pre class="code-block">{{ log.stages[2].llm_raw_output }}</pre>
              </el-collapse-item>
            </el-collapse>
          </div>
        </el-collapse-item>

        <!-- 阶段 4：安全校验 -->
        <el-collapse-item name="4">
          <template #title>
            <span class="stage-title">🛡️ 安全校验</span>
            <StatusBadge :risk-level="log.risk_level" size="small" class="ml-8" />
          </template>
          <div class="stage-body">
            <p>
              <b>命中规则：</b>
              <el-tag v-for="r in log.stages[3].rules_hit" :key="r" type="danger" size="small" class="mr-4">{{ r }}</el-tag>
              <span v-if="!log.stages[3].rules_hit.length" class="dim">无</span>
            </p>
            <p>
              <b>风险评分：</b>
              <el-progress
                :percentage="log.stages[3].risk_score"
                :color="scoreColor(log.stages[3].risk_score)"
                :stroke-width="10"
                style="width: 200px; display: inline-flex; vertical-align: middle;"
              />
            </p>
            <p>
              <b>决策：</b>
              <el-tag :type="decisionType(log.stages[3].decision)" size="small">
                {{ decisionLabel(log.stages[3].decision) }}
              </el-tag>
            </p>
            <p><b>原因：</b>{{ log.stages[3].reason }}</p>
          </div>
        </el-collapse-item>

        <!-- 阶段 5：执行结果 -->
        <el-collapse-item name="5">
          <template #title>
            <span class="stage-title">⚡ 执行结果</span>
          </template>
          <div class="stage-body">
            <p><b>动作：</b>{{ log.stages[4].action_taken }}</p>
            <p>
              <b>退出码：</b>
              <el-tag v-if="log.stages[4].exit_code === 0" type="success" size="small">0</el-tag>
              <el-tag v-else-if="log.stages[4].exit_code !== null" type="danger" size="small">{{ log.stages[4].exit_code }}</el-tag>
              <span v-else class="dim">未执行</span>
            </p>
            <p><b>耗时：</b>{{ log.stages[4].duration_ms }}ms</p>
            <div v-if="log.stages[4].stdout">
              <b>stdout：</b>
              <pre class="code-block">{{ log.stages[4].stdout }}</pre>
            </div>
            <div v-if="log.stages[4].stderr">
              <b>stderr：</b>
              <pre class="code-block stderr">{{ log.stages[4].stderr }}</pre>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { AuditLog } from '@/types'
import StatusBadge from '@/components/common/StatusBadge.vue'

defineProps<{ log: AuditLog | null }>()

const activeNames = ref(['1', '4']) // 默认展开阶段 1 和 4

function scoreColor(score: number): string {
  if (score >= 70) return '#F56C6C'
  if (score >= 30) return '#E6A23C'
  return '#67C23A'
}

function decisionType(d: string): 'success' | 'danger' | 'warning' | 'info' {
  switch (d) {
    case 'allowed':   return 'success'
    case 'blocked':   return 'danger'
    case 'confirmed': return 'warning'
    default:          return 'info'
  }
}

function decisionLabel(d: string): string {
  switch (d) {
    case 'allowed':   return '✅ 放行'
    case 'blocked':   return '❌ 拦截'
    case 'confirmed': return '👆 确认后执行'
    default:          return d
  }
}
</script>

<style scoped>
.audit-detail {
  padding: 16px;
  height: 100%;
  overflow-y: auto;
}

.detail-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
}

.stage-title {
  font-size: 14px;
  font-weight: 500;
}

.stage-body {
  font-size: 13px;
  line-height: 1.8;
}
.stage-body p {
  margin-bottom: 4px;
}
.stage-body blockquote {
  border-left: 3px solid var(--color-primary);
  padding: 6px 12px;
  margin: 8px 0;
  background: var(--bg-dark);
  border-radius: 0 4px 4px 0;
}

.code-block {
  background: #111;
  color: #ccc;
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 12px;
  max-height: 180px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
.code-block.stderr {
  color: #f88;
}

.inner-collapse {
  margin-top: 8px;
}

.dim { color: var(--text-secondary); }
.mr-4 { margin-right: 4px; }
.ml-8 { margin-left: 8px; }
</style>
