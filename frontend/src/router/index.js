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
    path: '/client/dashboard',
    name: 'client-dashboard',
    meta: { requiresAuth: true, role: 'client' },
    component: () => import('../views/ClientDashboardView.vue')
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

  const redirectForRole = () => {
    if (authStore.role === 'master') return '/master/dashboard'
    if (authStore.role === 'tenant') return '/admin/dashboard'
    if (authStore.role === 'client') return '/client/dashboard'
    return '/login'
  }

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return next('/login')
  }

  if (to.meta.role && authStore.role !== to.meta.role) {
    if (to.meta.role === 'tenant' && authStore.role === 'master' && authStore.activeTenantId) return next()
    return next(redirectForRole())
  }

  // If already logged in and going to login, redirect
  if (to.path === '/login' && authStore.isAuthenticated) {
    return next(redirectForRole())
  }

  next()
})

export default router
