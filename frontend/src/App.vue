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

    <!-- 主区域 -->
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
  padding: 10px;
  background: linear-gradient(90deg, rgba(248, 113, 113, 0.95), rgba(239, 68, 68, 0.95));
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  backdrop-filter: blur(12px);
}
.offline-dot {
  width: 7px; height: 7px;
  border-radius: 50%;
  background: #fff;
  animation: glow-pulse 1.5s infinite;
}

/* ── 主区域 ── */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: transparent;
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
  transition: opacity var(--dur-quick) var(--ease-spring);
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: all var(--dur-gentle) var(--ease-spring);
}
.slide-up-enter-from {
  opacity: 0;
  transform: translateY(10px);
}
.slide-up-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
