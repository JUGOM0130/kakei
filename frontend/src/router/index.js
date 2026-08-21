import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/login', name: 'login', component: () => import('../pages/LoginPage.vue'), meta: { public: true } },
    { path: '/register', name: 'register', component: () => import('../pages/RegisterPage.vue'), meta: { public: true } },
    { path: '/', name: 'dashboard', component: () => import('../pages/DashboardPage.vue') },
    { path: '/transactions', name: 'transactions', component: () => import('../pages/TransactionsPage.vue') },
    { path: '/transactions/new', name: 'transaction-new', component: () => import('../pages/TransactionFormPage.vue') },
    { path: '/transactions/:id/edit', name: 'transaction-edit', component: () => import('../pages/TransactionFormPage.vue'), props: true },
    { path: '/recurring', name: 'recurring', component: () => import('../pages/RecurringPage.vue') },
    { path: '/categories', name: 'categories', component: () => import('../pages/CategoriesPage.vue') },
    { path: '/settings', name: 'settings', component: () => import('../pages/SettingsPage.vue') },
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
