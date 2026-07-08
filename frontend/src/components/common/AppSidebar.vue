<template>
  <aside class="sidebar" :class="{ collapsed }">
    <!-- Logo + 折叠按钮 -->
    <div class="sidebar-brand">
      <div class="brand-icon">
        <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
          <rect width="32" height="32" rx="10" fill="var(--color-accent)" opacity="0.15" />
          <path d="M16 6L8 12v8l8 6 8-6v-8L16 6z" stroke="var(--color-accent)" stroke-width="1.6" stroke-linejoin="round" fill="none" />
          <circle cx="16" cy="16" r="3" fill="var(--color-accent)" />
        </svg>
      </div>
      <transition name="fade">
        <span v-if="!collapsed" class="brand-name">XikiyAIOps</span>
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
        <span v-if="currentRoute === item.path" class="nav-glow" />
      </router-link>
    </nav>

    <!-- 底部版本信息 -->
    <div class="sidebar-footer" v-if="!collapsed">
      <span class="version-tag">v1.2.0</span>
    </div>
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
  /* ── Sidebar dark theme overrides ── */
  --sb-bg: #1a1b26;
  --sb-border: rgba(255, 255, 255, 0.06);
  --sb-text: #e8e8f0;
  --sb-text-muted: #8a8da0;
  --sb-text-dim: #555870;
  --sb-hover: rgba(255, 255, 255, 0.06);

  display: flex;
  flex-direction: column;
  width: var(--sidebar-width);
  height: 100vh;
  background: var(--sb-bg);
  border-right: 1px solid var(--sb-border);
  transition: width var(--dur-gentle) var(--ease-spring);
  flex-shrink: 0;
  overflow: hidden;
  position: relative;
  z-index: 10;
}
.sidebar.collapsed {
  width: var(--sidebar-collapsed);
}

/* ── Brand ── */
.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 14px;
  border-bottom: 1px solid var(--sb-border);
}
.brand-icon {
  flex-shrink: 0;
  display: flex;
}
.brand-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--sb-text);
  letter-spacing: -0.3px;
  white-space: nowrap;
  flex: 1;
}

/* ── Collapse btn ── */
.collapse-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: var(--sb-text-dim);
  border-radius: var(--radius-sm);
  cursor: pointer;
  flex-shrink: 0;
  transition: all var(--dur-quick) var(--ease-spring);
}
.collapse-btn:hover {
  background: var(--sb-hover);
  color: var(--sb-text-muted);
}

/* ── Nav ── */
.sidebar-nav {
  flex: 1;
  padding: 10px 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  color: var(--sb-text-dim);
  text-decoration: none;
  font-size: 14px;
  font-weight: 450;
  transition: all var(--dur-base) var(--ease-spring);
  overflow: hidden;
}
.nav-item:hover {
  background: var(--sb-hover);
  color: var(--sb-text-muted);
}
.nav-item.active {
  background: rgba(77, 107, 254, 0.15);
  color: #fff;
}

/* Active glow indicator */
.nav-glow {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 18px;
  border-radius: 0 3px 3px 0;
  background: var(--color-accent);
  box-shadow: 0 0 12px var(--color-accent-glow);
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

/* ── Footer ── */
.sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--sb-border);
}
.version-tag {
  font-size: 10px;
  font-family: var(--font-mono);
  color: var(--sb-text-dim);
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

/* ── Transition ── */
.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--dur-quick) var(--ease-spring);
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
