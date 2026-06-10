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

  // --- Master routes ---
  {
    path: '/master/overview',
    name: 'master-overview',
    meta: { requiresAuth: true, role: 'master' },
    component: () => import('../views/MasterDashboardView.vue')
  },
  {
    path: '/master/code-services',
    name: 'master-code-services',
    meta: { requiresAuth: true, role: 'master' },
    component: () => import('../views/MasterCodeServicesView.vue')
  },
  {
    path: '/master/dashboard',
    redirect: '/master/overview'
  },

  // --- Tenant / admin routes ---
  {
    path: '/admin/overview',
    name: 'tenant-overview',
    meta: { requiresAuth: true, role: 'tenant', allowMasterSupport: true },
    component: () => import('../views/TenantDashboardView.vue')
  },
  {
    path: '/admin/clients',
    name: 'tenant-clients',
    meta: { requiresAuth: true, role: 'tenant', allowMasterSupport: true },
    component: () => import('../views/TenantClientsView.vue')
  },
  {
    path: '/admin/catalog',
    name: 'tenant-catalog',
    meta: { requiresAuth: true, role: 'tenant', allowMasterSupport: true },
    component: () => import('../views/TenantCatalogView.vue')
  },
  {
    path: '/admin/subscriptions',
    name: 'tenant-subscriptions',
    meta: { requiresAuth: true, role: 'tenant', allowMasterSupport: true },
    component: () => import('../views/SubscriptionsView.vue')
  },
  {
    path: '/admin/mailbox',
    name: 'tenant-mailbox',
    meta: { requiresAuth: true, role: 'tenant', allowMasterSupport: true },
    component: () => import('../views/TenantMailboxView.vue')
  },
  {
    path: '/admin/code-services',
    name: 'tenant-code-services',
    meta: { requiresAuth: true, role: 'tenant', allowMasterSupport: true },
    component: () => import('../views/TenantCodeServicesView.vue')
  },
  {
    path: '/admin/settings',
    name: 'tenant-settings',
    meta: { requiresAuth: true, role: 'tenant', allowMasterSupport: false },
    component: () => import('../views/TenantSettingsView.vue')
  },
  {
    path: '/admin/dashboard',
    redirect: '/admin/overview'
  },

  // --- Client routes ---
  {
    path: '/client/overview',
    name: 'client-overview',
    meta: { requiresAuth: true, role: 'client' },
    component: () => import('../views/ClientDashboardView.vue')
  },
  {
    path: '/client/dashboard',
    redirect: '/client/overview'
  },

  // --- Catch-all ---
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
    if (authStore.role === 'master') return '/master/overview'
    if (authStore.role === 'tenant') return '/admin/overview'
    if (authStore.role === 'client') return '/client/overview'
    return '/login'
  }

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return next('/login')
  }

  if (to.meta.role && authStore.role !== to.meta.role) {
    // Master in support mode: respect allowMasterSupport meta
    if (authStore.role === 'master' && authStore.activeTenantId) {
      if (to.meta.allowMasterSupport === true) return next()
      // allowMasterSupport === false or undefined → redirect
      return next(redirectForRole())
    }
    return next(redirectForRole())
  }

  // If already logged in and going to login, redirect
  if (to.path === '/login' && authStore.isAuthenticated) {
    return next(redirectForRole())
  }

  next()
})

export default router
