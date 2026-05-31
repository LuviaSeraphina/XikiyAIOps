<template>
  <div class="app-shell">
    <!-- 离线提示 -->
    <transition name="fade-up">
      <div v-if="offline" class="offline-bar">
        <span class="offline-dot" />
        <span>网络连接已断开，请检查网络</span>
      </div>
    </transition>

    <!-- 侧边栏 -->
    <AppSidebar v-model:collapsed="sidebarCollapsed" />

    <!-- 主区域 -->
    <div class="main-area" :class="{ collapsed: sidebarCollapsed }">
      <!-- 顶部栏 -->
      <header class="top-bar">
        <div class="top-bar-left">
          <button class="collapse-btn" @click="sidebarCollapsed = !sidebarCollapsed" :title="sidebarCollapsed ? '展开菜单' : '收起菜单'">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="12" x2="15" y2="12" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
          <div class="breadcrumb">
            <span class="breadcrumb-item">{{ pageTitle }}</span>
          </div>
        </div>
        <SystemOverview />
      </header>

      <!-- 内容区 -->
      <main class="main-content">
        <router-view v-slot="{ Component }">
          <transition name="fade-up" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import AppSidebar from '@/components/common/AppSidebar.vue'
import SystemOverview from '@/components/common/SystemOverview.vue'

const route = useRoute()
const sidebarCollapsed = ref(false)
const offline = ref(!navigator.onLine)

const pageTitle = computed(() => {
  const map: Record<string, string> = {
    '/chat': '智能对话',
    '/dashboard': '系统仪表盘',
    '/audit': '审计日志',
  }
  return map[route.path] || 'SRE-Agent'
})

function onOnline()  { offline.value = false }
function onOffline() { offline.value = true }

onMounted(() => {
  window.addEventListener('online',  onOnline)
  window.addEventListener('offline', onOffline)
})
onUnmounted(() => {
  window.removeEventListener('online',  onOnline)
  window.removeEventListener('offline', onOffline)
})
</script>

<style scoped>
.app-shell {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: var(--bg-root);
}

/* ---- 离线提示 ---- */
.offline-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 4000;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 8px;
  background: rgba(239, 68, 68, 0.92);
  backdrop-filter: blur(12px);
  color: #fff;
  font-size: 13px;
  font-weight: 500;
}
.offline-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #fff;
  animation: pulse-glow 1.5s infinite;
}

/* ---- 主区域 ---- */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  margin-left: 0;
  transition: margin-left var(--duration-slow) var(--ease-out);
}

/* ---- 顶部栏 ---- */
.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--header-height);
  padding: 0 20px;
  background: var(--bg-elevated);
  border-bottom: 1px solid var(--border-subtle);
  backdrop-filter: blur(12px);
  flex-shrink: 0;
}
.top-bar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.collapse-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}
.collapse-btn:hover {
  border-color: var(--border-emphasis);
  color: var(--text-primary);
  background: var(--bg-surface);
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 6px;
}
.breadcrumb-item {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

/* ---- 内容区 ---- */
.main-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--bg-root);
}
</style>
