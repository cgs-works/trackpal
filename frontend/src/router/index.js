import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import LoginView from '../views/LoginView.vue'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: LoginView,
    meta: { requiresAuth: false }
  },
  {
    path: '/master/dashboard',
    name: 'master-dashboard',
    meta: { requiresAuth: true, role: 'master' },
    component: () => import('../views/MasterDashboardView.vue')
  },
  {
    path: '/admin/dashboard',
    name: 'tenant-dashboard',
    meta: { requiresAuth: true, role: 'tenant' },
    component: () => import('../views/TenantDashboardView.vue')
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/login'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return next('/login')
  }

  if (to.meta.role && authStore.role !== to.meta.role) {
    if (to.meta.role === 'tenant' && authStore.role === 'master' && authStore.activeTenantId) return next()
    // Redirect to appropriate dashboard
    if (authStore.role === 'master') return next('/master/dashboard')
    if (authStore.role === 'tenant') return next('/admin/dashboard')
    return next('/login')
  }

  // If already logged in and going to login, redirect
  if (to.path === '/login' && authStore.isAuthenticated) {
    if (authStore.role === 'master') return next('/master/dashboard')
    if (authStore.role === 'tenant') return next('/admin/dashboard')
  }

  next()
})

export default router
