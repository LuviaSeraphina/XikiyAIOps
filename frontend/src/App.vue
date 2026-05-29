<template>
  <el-container class="app-root">
    <!-- 侧边栏 -->
    <el-aside :width="sidebarWidth">
      <AppSidebar />
    </el-aside>

    <!-- 右侧区域 -->
    <el-container>
      <!-- 顶部状态栏 -->
      <el-header height="var(--header-height)" class="app-header">
        <SystemOverview />
      </el-header>

      <!-- 主内容区 -->
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import AppSidebar from '@/components/common/AppSidebar.vue'
import SystemOverview from '@/components/common/SystemOverview.vue'

const sidebarWidth = '220px'
</script>

<style scoped>
.app-root {
  height: 100vh;
}

.app-header {
  padding: 0;
}

.app-main {
  background-color: var(--bg-dark);
  overflow-y: auto;
  padding: 0;
}
</style>
