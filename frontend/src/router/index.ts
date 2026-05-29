import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/chat' },
  { path: '/chat', name: 'chat', component: () => import('../views/ChatView.vue') },
  { path: '/dashboard', name: 'dashboard', component: () => import('../views/DashboardView.vue') },
  { path: '/audit', name: 'audit', component: () => import('../views/AuditLogView.vue') },
]

export default createRouter({ history: createWebHashHistory(), routes })
