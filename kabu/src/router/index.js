import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/login', name: 'login', component: () => import('../pages/LoginPage.vue'), meta: { public: true } },
    { path: '/register', name: 'register', component: () => import('../pages/RegisterPage.vue'), meta: { public: true } },
    { path: '/', name: 'dashboard', component: () => import('../pages/DashboardPage.vue') },
    { path: '/trades', name: 'trades', component: () => import('../pages/TradesPage.vue') },
    { path: '/trades/new', name: 'trade-new', component: () => import('../pages/TradeFormPage.vue') },
    { path: '/trades/:id/edit', name: 'trade-edit', component: () => import('../pages/TradeFormPage.vue'), props: true },
    { path: '/positions', name: 'positions', component: () => import('../pages/PositionsPage.vue') },
    { path: '/watch', name: 'watch', component: () => import('../pages/WatchPage.vue') },
    { path: '/dividends', name: 'dividends', component: () => import('../pages/DividendsPage.vue') },
    { path: '/import', name: 'import', component: () => import('../pages/ImportPage.vue') },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.initialized) await auth.init()
  if (!to.meta.public && !auth.user) return { name: 'login' }
  if (to.meta.public && auth.user) return { name: 'dashboard' }
})

export default router
