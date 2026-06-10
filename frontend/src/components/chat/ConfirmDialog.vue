<template>
  <el-dialog
    :model-value="!!store.pendingConfirm"
    width="460px"
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

    <div v-if="store.pendingConfirm" class="confirm-body">
      <div class="confirm-item">
        <span class="item-label">工具名称</span>
        <code class="item-code">{{ store.pendingConfirm.tool_name }}</code>
      </div>
      <div class="confirm-item">
        <span class="item-label">风险等级</span>
        <span class="risk-badge" :class="`risk-${store.pendingConfirm.risk_level}`">
          {{ riskLabel }}
        </span>
      </div>
      <div class="confirm-item">
        <span class="item-label">操作摘要</span>
        <span class="item-text">{{ store.pendingConfirm.summary }}</span>
      </div>

      <el-collapse class="detail-collapse">
        <el-collapse-item title="查看详情">
          <pre class="detail-text">{{ store.pendingConfirm.details }}</pre>
        </el-collapse-item>
      </el-collapse>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="store.clearPendingConfirm()">取消</el-button>
        <el-button
          type="danger"
          :disabled="confirming"
          @click="handleConfirm"
        >
          {{ confirmText }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useChatStore } from '@/stores/chat'
import { confirmAction } from '@/api/chat'

const store = useChatStore()
const confirming = ref(false)
const confirmCount = ref(0)
const confirmText = ref('确认执行')

const riskLabel = computed(() => {
  switch (store.pendingConfirm?.risk_level) {
    case 'dangerous':  return '高危'
    case 'restricted': return '受限'
    default:           return '未知'
  }
})

async function handleConfirm() {
  confirmCount.value++
  if (confirmCount.value < 2) {
    confirmText.value = '再次确认'
    setTimeout(() => {
      if (confirmCount.value < 2) {
        confirmText.value = '确认执行'
        confirmCount.value = 0
      }
    }, 1500)
    return
  }

  if (!store.pendingConfirm) return
  confirming.value = true
  try {
    await confirmAction(store.currentSessionId)
  } catch (e) {
    console.error('确认操作失败:', e)
  } finally {
    confirming.value = false
    confirmCount.value = 0
    confirmText.value = '确认执行'
    store.clearPendingConfirm()
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
  gap: 14px;
}

.confirm-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.item-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-tertiary);
  min-width: 56px;
  flex-shrink: 0;
  padding-top: 2px;
}
.item-code {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  background: var(--bg-elevated);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
}
.item-text {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.5;
}

.risk-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: var(--radius-full);
}
.risk-dangerous  { color: var(--color-danger); background: var(--color-danger-soft); }
.risk-restricted { color: var(--color-warning); background: var(--color-warning-soft); }

.detail-collapse {
  margin-top: 4px;
}
.detail-text {
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--text-secondary);
  background: var(--bg-elevated);
  padding: 10px;
  border-radius: var(--radius-sm);
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 180px;
  overflow-y: auto;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 13px;
}
.detail-collapse {
  margin-top: 4px;
}
.detail-text {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
}
