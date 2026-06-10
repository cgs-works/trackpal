import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StatusBadge from '../StatusBadge.vue'

describe('StatusBadge', () => {
  it('renders the label and variant classes for active state', () => {
    const wrapper = mount(StatusBadge, {
      props: { variant: 'active', label: 'Active' },
    })

    expect(wrapper.text()).toContain('Active')
    expect(wrapper.classes().join(' ')).toContain('text-emerald')
  })
})
