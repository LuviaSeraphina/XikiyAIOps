<template>
  <div class="app-shell">
    <!-- 离线提示 -->
    <transition name="slide-up">
      <div v-if="offline" class="offline-bar">
        <span class="offline-dot" />
        <span>网络连接已断开，请检查网络</span>
      </div>
    </transition>

    <!-- 侧边栏 -->
    <AppSidebar v-model:collapsed="sidebarCollapsed" />

    <!-- 主区域：无顶部栏，内容直接铺满 -->
    <div class="main-area" :class="{ collapsed: sidebarCollapsed }">
      <main class="main-content">
        <router-view v-slot="{ Component, route }">
          <component :is="Component" :key="route.path" />
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import AppSidebar from '@/components/common/AppSidebar.vue'

const sidebarCollapsed = ref(false)
const offline = ref(!navigator.onLine)

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

/* ── 离线提示 ── */
.offline-bar {
  position: fixed;
  top: 0; left: 0; right: 0;
  z-index: 4000;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 8px;
  background: var(--color-danger);
  color: #fff;
  font-size: 13px;
  font-weight: 500;
}
.offline-dot {
  width: 7px; height: 7px;
  border-radius: 50%;
  background: #fff;
  animation: pulse 1.5s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* ── 主区域 ── */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: var(--bg-root);
}

.main-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* ── 过渡动画 ── */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 150ms ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
