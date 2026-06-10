<template>
  <aside class="sidebar" :class="{ collapsed }">
    <!-- Logo + 折叠按钮 -->
    <div class="sidebar-brand">
      <div class="brand-icon">
        <svg width="26" height="26" viewBox="0 0 32 32" fill="none">
          <rect width="32" height="32" rx="8" fill="var(--color-accent)" />
          <path d="M16 6L8 12v8l8 6 8-6v-8L16 6z" stroke="#fff" stroke-width="1.8" stroke-linejoin="round" fill="none" />
          <circle cx="16" cy="16" r="3" fill="#fff" />
        </svg>
      </div>
      <transition name="fade">
        <span v-if="!collapsed" class="brand-name">SRE-Agent</span>
      </transition>
      <button
        class="collapse-btn"
        @click="$emit('update:collapsed', !collapsed)"
        :title="collapsed ? '展开菜单' : '收起菜单'"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <polyline v-if="collapsed" points="9 18 15 12 9 6" />
          <polyline v-else points="15 18 9 12 15 6" />
        </svg>
      </button>
    </div>

    <!-- 导航 -->
    <nav class="sidebar-nav">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="nav-item"
        :class="{ active: currentRoute === item.path }"
        :title="collapsed ? item.label : ''"
      >
        <span class="nav-icon" v-html="item.icon" />
        <span v-if="!collapsed" class="nav-label">{{ item.label }}</span>
      </router-link>
    </nav>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

defineProps<{ collapsed: boolean }>()
defineEmits<{ 'update:collapsed': [val: boolean] }>()

const route = useRoute()
const currentRoute = computed(() => route.path)

const navItems = [
  {
    path: '/chat',
    label: '智能对话',
    icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
    </svg>`,
  },
  {
    path: '/dashboard',
    label: '仪表盘',
    icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/>
      <rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>
    </svg>`,
  },
  {
    path: '/audit',
    label: '审计日志',
    icon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
      <polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
    </svg>`,
  },
]
</script>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  width: var(--sidebar-width);
  height: 100vh;
  background: #1e2029;
  border-right: 1px solid rgba(255, 255, 255, 0.06);
  transition: width var(--dur-gentle) var(--ease-out);
  flex-shrink: 0;
  overflow: hidden;
}
.sidebar.collapsed {
  width: var(--sidebar-collapsed);
}

/* ── Brand ── */
.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.brand-icon {
  flex-shrink: 0;
  display: flex;
}
.brand-name {
  font-size: 15px;
  font-weight: 700;
  color: #fff;
  letter-spacing: -0.3px;
  white-space: nowrap;
  flex: 1;
}

/* ── Collapse btn in brand row ── */
.collapse-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: #6a6d78;
  border-radius: 6px;
  cursor: pointer;
  flex-shrink: 0;
  transition: all var(--dur-quick) var(--ease-out);
}
.collapse-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #c0c4d0;
}

/* ── Nav ── */
.sidebar-nav {
  flex: 1;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  color: #a0a4b0;
  text-decoration: none;
  font-size: 14px;
  font-weight: 450;
  transition: all var(--dur-quick) var(--ease-out);
}
.nav-item:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #e0e2e8;
}
.nav-item.active {
  background: rgba(77, 107, 254, 0.15);
  color: #fff;
}
.nav-icon {
  display: flex;
  flex-shrink: 0;
  width: 20px;
  height: 20px;
}
.nav-label {
  white-space: nowrap;
  overflow: hidden;
}

/* ── Transition ── */
.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--dur-quick) var(--ease-out);
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
