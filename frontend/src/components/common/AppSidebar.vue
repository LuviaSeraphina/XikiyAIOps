<template>
  <div class="sidebar">
    <!-- Logo 区 -->
    <div class="sidebar-logo">
      <span class="logo-icon">🛡️</span>
      <span class="logo-text">SRE-Agent</span>
    </div>

    <!-- 菜单 -->
    <el-menu
      :default-active="currentRoute"
      router
      background-color="var(--bg-dark)"
      text-color="var(--text-primary)"
      active-text-color="var(--color-primary)"
    >
      <el-menu-item index="/chat">
        <el-icon><ChatDotRound /></el-icon>
        <span>智能对话</span>
      </el-menu-item>
      <el-menu-item index="/dashboard">
        <el-icon><Odometer /></el-icon>
        <span>系统仪表盘</span>
      </el-menu-item>
      <el-menu-item index="/audit">
        <el-icon><Document /></el-icon>
        <span>审计日志</span>
      </el-menu-item>
    </el-menu>

    <!-- 底部信息 -->
    <div class="sidebar-footer">
      <span>麒麟 OS · 安全运维 Agent v1.0</span>
      <el-button class="cl-btn" size="small" text @click="toggleCL">
        <el-icon :size="16"><Moon v-if="!isLight" /><Sunny v-else /></el-icon>
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ChatDotRound, Odometer, Document, Sunny, Moon } from '@element-plus/icons-vue'

const route = useRoute()
const currentRoute = computed(() => route.path)

// ---- CL: 主题切换（首次跟随系统默认） ----
const isLight = ref(false)
const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')

function detectSystemTheme(): boolean {
  // prefers-color-scheme: dark → 系统暗色 → isLight=false
  return !mediaQuery.matches
}

interface ThemeVars {
  '--bg-dark': string
  '--bg-panel': string
  '--text-primary': string
  '--text-secondary': string
  '--border-color': string
}

const darkTheme: ThemeVars = {
  '--bg-dark': '#1d1e1f',
  '--bg-panel': '#2a2b2c',
  '--text-primary': '#e0e0e0',
  '--text-secondary': '#909399',
  '--border-color': '#3a3b3d',
}

const lightTheme: ThemeVars = {
  '--bg-dark': 'rgb(235, 239, 243)',
  '--bg-panel': '#ffffff',
  '--text-primary': '#000000',
  '--text-secondary': '#606266',
  '--border-color': '#dcdfe6',
}

function applyTheme(vars: ThemeVars) {
  const root = document.documentElement
  ;(Object.keys(vars) as (keyof ThemeVars)[]).forEach((key) => {
    root.style.setProperty(key, vars[key])
  })
}

function toggleCL() {
  isLight.value = !isLight.value
  applyTheme(isLight.value ? lightTheme : darkTheme)
}

// 首次加载：跟随系统主题
onMounted(() => {
  isLight.value = detectSystemTheme()
  applyTheme(isLight.value ? lightTheme : darkTheme)
  // 监听系统主题变更，自动跟随
  mediaQuery.addEventListener('change', () => {
    isLight.value = detectSystemTheme()
    applyTheme(isLight.value ? lightTheme : darkTheme)
  })
})
</script>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: var(--bg-dark);
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 20px;
  border-bottom: 1px solid var(--border-color);
}

.logo-icon {
  font-size: 22px;
}

.logo-text {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-primary);
  letter-spacing: 1px;
}

.el-menu {
  flex: 1;
  border-right: none;
  padding-top: 8px;
}

.el-menu-item {
  transition: all 0.2s ease;
}
.el-menu-item:hover {
  background-color: rgba(64, 158, 255, 0.08) !important;
}

.sidebar-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 20px;
  font-size: 11px;
  color: var(--text-secondary);
  border-top: 1px solid var(--border-color);
}
</style>
