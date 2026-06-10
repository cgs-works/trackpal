import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'

export async function renderWithApp(component, {
  props = {},
  slots = {},
  routes = [{ path: '/', component }],
  path = '/',
  global = {},
} = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)

  const router = createRouter({
    history: createMemoryHistory(),
    routes,
  })

  router.push(path)
  await router.isReady()

  return mount(component, {
    props,
    slots,
    global: {
      plugins: [pinia, router],
      ...global,
    },
  })
}
