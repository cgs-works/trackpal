/**
 * Determines the navigation context based on the user's role and support mode.
 *
 * @param {import('@/stores/auth').AuthStore} authStore
 * @param {import('vue-router').RouteLocationNormalizedLoaded} route
 * @returns {{ mode: string, items: Array<{ label: string, to: string }> }}
 */
export function getNavigationContext(authStore, route) {
  const isSupportMode =
    authStore.role === 'master' &&
    !!authStore.activeTenantId &&
    route.path.startsWith('/admin')

  if (isSupportMode) {
    return {
      mode: 'tenant-support',
      items: [
        { label: 'Overview', to: '/admin/overview' },
        { label: 'Clients', to: '/admin/clients' },
        { label: 'Catalog', to: '/admin/catalog' },
        { label: 'Subscriptions', to: '/admin/subscriptions' },
        { label: 'Mailbox', to: '/admin/mailbox' },
        { label: 'Code Services', to: '/admin/code-services' },
      ],
    }
  }

  if (authStore.role === 'master') {
    return {
      mode: 'master',
      items: [
        { label: 'Overview', to: '/master/overview' },
        { label: 'Code Services', to: '/master/code-services' },
      ],
    }
  }

  if (authStore.role === 'tenant') {
    return {
      mode: 'tenant',
      items: [
        { label: 'Overview', to: '/admin/overview' },
        { label: 'Clients', to: '/admin/clients' },
        { label: 'Catalog', to: '/admin/catalog' },
        { label: 'Subscriptions', to: '/admin/subscriptions' },
        { label: 'Mailbox', to: '/admin/mailbox' },
        { label: 'Code Services', to: '/admin/code-services' },
        { label: 'Settings', to: '/admin/settings' },
      ],
    }
  }

  return {
    mode: 'client',
    items: [{ label: 'Overview', to: '/client/overview' }],
  }
}
