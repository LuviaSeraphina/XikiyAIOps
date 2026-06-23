<template>
  <el-dialog
    :model-value="store.isAwaitingConfirm"
    width="520px"
    :close-on-click-modal="false"
    @close="store.clearPendingConfirm()"
  >
    <template #header>
      <div class="dialog-title">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2.5" stroke-linecap="round">
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
          <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
        <span>危险操作确认</span>
      </div>
    </template>

    <div class="confirm-body" v-if="store.pendingTools.length > 0">
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        title="勾选要放行的操作，未勾选的将被跳过"
      />

      <!-- 全选/全部反选 -->
      <div class="toggle-all">
        <el-checkbox
          :model-value="allSelected"
          :indeterminate="someSelected && !allSelected"
          @change="toggleAll"
        >
          {{ allSelected ? '全部取消' : '全选' }}
        </el-checkbox>
      </div>

      <!-- 工具列表 -->
      <div class="tool-list">
        <div
          v-for="tool in store.pendingTools"
          :key="tool.tool_call_id"
          class="tool-row"
        >
          <el-checkbox
            :model-value="decisions[tool.tool_call_id] !== false"
            @change="(val: boolean) => decisions[tool.tool_call_id] = val"
          />
          <code class="tool-name">{{ tool.tool_name }}</code>
          <span class="risk-tag" :class="`risk-${tool.risk_level}`">
            {{ tool.risk_level === 'dangerous' ? '高危' : '受限' }}
          </span>
          <el-collapse class="tool-detail-collapse">
            <el-collapse-item title="参数">
              <pre class="detail-text">{{ tool.details }}</pre>
            </el-collapse-item>
          </el-collapse>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="store.cancelPendingConfirm()">取消</el-button>
        <el-button
          type="danger"
          :disabled="confirming"
          @click="handleConfirm"
        >
          {{ confirming ? '提交中...' : `确认已选 (${selectedCount}/${store.pendingTools.length})` }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, reactive, watch } from 'vue'
import { useChatStore } from '@/stores/chat'

const store = useChatStore()
const confirming = ref(false)

// 本地 decisions 状态: tool_call_id → boolean
const decisions = reactive<Record<string, boolean>>({})

// 当弹窗打开时初始化 decisions（默认全部选中）
watch(() => store.isAwaitingConfirm, (open) => {
  if (open) {
    for (const tool of store.pendingTools) {
      decisions[tool.tool_call_id] = true
    }
  }
})

const allSelected = computed(() => {
  const tools = store.pendingTools
  if (tools.length === 0) return false
  return tools.every(t => decisions[t.tool_call_id] !== false)
})

const someSelected = computed(() => {
  return store.pendingTools.some(t => decisions[t.tool_call_id] !== false)
})

const selectedCount = computed(() => {
  return store.pendingTools.filter(t => decisions[t.tool_call_id] !== false).length
})

function toggleAll() {
  const newVal = !allSelected.value
  for (const tool of store.pendingTools) {
    decisions[tool.tool_call_id] = newVal
  }
}

async function handleConfirm() {
  confirming.value = true
  try {
    await store.submitDecisions({ ...decisions })
  } catch (e) {
    console.error('提交确认失败:', e)
  } finally {
    confirming.value = false
  }
}
</script>

<style scoped>
.dialog-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.confirm-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.toggle-all {
  display: flex;
  align-items: center;
  padding: 4px 0;
  border-bottom: 1px solid var(--border-subtle);
  font-size: 13px;
}

.tool-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 360px;
  overflow-y: auto;
}

.tool-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  transition: border-color var(--dur-quick);
}
.tool-row:hover {
  border-color: var(--border-default);
}

.tool-name {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.risk-tag {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 7px;
  border-radius: 4px;
  flex-shrink: 0;
}
.risk-dangerous {
  color: var(--color-danger);
  background: var(--color-danger-soft);
}
.risk-restricted {
  color: var(--color-warning);
  background: var(--color-warning-soft);
}

.tool-detail-collapse {
  flex-shrink: 0;
}
.tool-detail-collapse :deep(.el-collapse-item__header) {
  font-size: 11px;
  color: var(--color-accent-text);
  border: none;
  padding: 0;
  height: auto;
}
.tool-detail-collapse :deep(.el-collapse-item__wrap) {
  border: none;
}

.detail-text {
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--text-secondary);
  background: var(--bg-root);
  padding: 8px 10px;
  border-radius: 5px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 140px;
  overflow-y: auto;
  margin: 0;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
