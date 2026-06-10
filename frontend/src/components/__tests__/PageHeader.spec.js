import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PageHeader from '../PageHeader.vue'

describe('PageHeader', () => {
  it('renders title, description, and actions slot', () => {
    const wrapper = mount(PageHeader, {
      props: { title: 'Subscriptions', description: 'Manage client access' },
      slots: { actions: '<button>New</button>' },
    })

    expect(wrapper.text()).toContain('Subscriptions')
    expect(wrapper.text()).toContain('Manage client access')
    expect(wrapper.text()).toContain('New')
  })
})
