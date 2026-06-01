<template>
  <aside class="sidebar" :class="{ collapsed }">
    <!-- Logo -->
    <div class="sidebar-brand">
      <div class="brand-icon">
        <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
          <rect width="32" height="32" rx="8" fill="var(--color-accent)" />
          <path d="M16 6L8 12v8l8 6 8-6v-8L16 6z" stroke="#fff" stroke-width="1.8" stroke-linejoin="round" fill="none" />
          <circle cx="16" cy="16" r="3" fill="#fff" />
        </svg>
      </div>
      <transition name="fade-up">
        <div v-if="!collapsed" class="brand-text">
          <span class="brand-name">SRE-Agent</span>
          <span class="brand-sub">麒麟安全运维</span>
        </div>
      </transition>
    </div>

    <!-- 导航菜单 -->
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
        <span v-if="!collapsed && currentRoute === item.path" class="nav-indicator" />
      </router-link>
    </nav>

    <!-- 底部 -->
    <div class="sidebar-footer">
      <button class="theme-toggle" @click="toggleCL" :title="isLight ? '切换暗色' : '切换亮色'">
        <svg v-if="isLight" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
          <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
        </svg>
        <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
        </svg>
      </button>
      <transition name="fade-up">
        <span v-if="!collapsed" class="footer-version">v1.0</span>
      </transition>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'

const props = defineProps<{ collapsed: boolean }>()
const emit = defineEmits<{ 'update:collapsed': [val: boolean] }>()

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

// ---- 主题 ----
const isLight = ref(false)
const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')

function detectSystemTheme(): boolean {
  return !mediaQuery.matches
}

function applyTheme(light: boolean) {
  const root = document.documentElement
  if (light) {
    root.style.setProperty('--bg-root', '#f1f5f9')
    root.style.setProperty('--bg-elevated', '#ffffff')
    root.style.setProperty('--bg-surface', '#f8fafc')
    root.style.setProperty('--bg-surface-hover', '#f1f5f9')
    root.style.setProperty('--text-primary', '#0f172a')
    root.style.setProperty('--text-secondary', '#475569')
    root.style.setProperty('--text-tertiary', '#94a3b8')
    root.style.setProperty('--border-subtle', 'rgba(0,0,0,0.04)')
    root.style.setProperty('--border-default', 'rgba(0,0,0,0.08)')
    root.style.setProperty('--border-emphasis', 'rgba(0,0,0,0.14)')
    root.style.setProperty('--bg-glass', 'rgba(255,255,255,0.82)')
  } else {
    root.style.setProperty('--bg-root', '#0b0f15')
    root.style.setProperty('--bg-elevated', '#11161e')
    root.style.setProperty('--bg-surface', '#161c26')
    root.style.setProperty('--bg-surface-hover', '#1c2330')
    root.style.setProperty('--text-primary', '#e8ecf1')
    root.style.setProperty('--text-secondary', '#8896a7')
    root.style.setProperty('--text-tertiary', '#5c6a7d')
    root.style.setProperty('--border-subtle', 'rgba(255,255,255,0.06)')
    root.style.setProperty('--border-default', 'rgba(255,255,255,0.09)')
    root.style.setProperty('--border-emphasis', 'rgba(255,255,255,0.14)')
    root.style.setProperty('--bg-glass', 'rgba(22,28,38,0.82)')
  }
}

function toggleCL() {
  isLight.value = !isLight.value
  applyTheme(isLight.value)
}

onMounted(() => {
  isLight.value = detectSystemTheme()
  applyTheme(isLight.value)
  mediaQuery.addEventListener('change', () => {
    isLight.value = detectSystemTheme()
    applyTheme(isLight.value)
  })
})
</script>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  width: var(--sidebar-width);
  height: 100vh;
  background: var(--bg-elevated);
  border-right: 1px solid var(--border-subtle);
  transition: width var(--duration-slow) var(--ease-out);
  flex-shrink: 0;
  z-index: 100;
}
.sidebar.collapsed {
  width: var(--sidebar-collapsed);
}

/* ---- Brand ---- */
.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  height: var(--header-height);
  padding: 0 18px;
  border-bottom: 1px solid var(--border-subtle);
  overflow: hidden;
  flex-shrink: 0;
}
.brand-icon {
  flex-shrink: 0;
  display: flex;
}
.brand-icon :deep(svg) {
  width: 28px;
  height: 28px;
  display: block;
}
.brand-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  overflow: hidden;
  white-space: nowrap;
}
.brand-name {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.3px;
}
.brand-sub {
  font-size: 11px;
  color: var(--text-tertiary);
  font-weight: 400;
}

/* ---- Nav ---- */
.sidebar-nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 12px 10px;
  overflow-y: auto;
  overflow-x: hidden;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 13.5px;
  font-weight: 500;
  position: relative;
  transition: all var(--duration-fast) var(--ease-out);
  white-space: nowrap;
  overflow: hidden;
}
.nav-item:hover {
  color: var(--text-primary);
  background: var(--bg-surface-hover);
}
.nav-item.active {
  color: var(--color-accent);
  background: var(--color-accent-soft);
}
.nav-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
}
.nav-icon :deep(svg) {
  width: 20px;
  height: 20px;
  display: block;
}
.nav-label {
  flex: 1;
  height: 20px;
  line-height: 20px;
  overflow: hidden;
}
.nav-indicator {
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 18px;
  border-radius: 3px;
  background: var(--color-accent);
}

/* ---- Footer ---- */
.sidebar-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--border-subtle);
}
.theme-toggle {
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
  flex-shrink: 0;
}
.theme-toggle:hover {
  border-color: var(--border-emphasis);
  color: var(--text-primary);
  background: var(--bg-surface);
}
.footer-version {
  font-size: 11px;
  color: var(--text-tertiary);
  white-space: nowrap;
}
</style>
