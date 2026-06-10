import { afterEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import SummaryMetric from '@/components/SummaryMetric.vue'
import EntityInspector from '@/components/EntityInspector.vue'
import ImpactConfirmDialog from '@/components/ImpactConfirmDialog.vue'

describe('command center primitives', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('renders a compact summary metric', () => {
    const wrapper = mount(SummaryMetric, {
      props: { label: 'Active', value: '12', tone: 'success' },
    })

    expect(wrapper.text()).toContain('Active')
    expect(wrapper.text()).toContain('12')
    expect(wrapper.classes()).toContain('border-border')
  })

  it('renders inspector fields and emits edit', async () => {
    const wrapper = mount(EntityInspector, {
      props: {
        title: 'Client detail',
        description: 'Selected client',
        fields: [
          { label: 'Name', value: 'Ana' },
          { label: 'Status', value: 'Active' },
        ],
      },
    })

    expect(wrapper.text()).toContain('Client detail')
    expect(wrapper.text()).toContain('Ana')
    expect(wrapper.classes()).toContain('border-primary')

    await wrapper.get('[data-testid="inspector-edit"]').trigger('click')
    expect(wrapper.emitted('edit')).toHaveLength(1)
  })

  it('renders destructive impact details and emits confirm', async () => {
    const wrapper = mount(ImpactConfirmDialog, {
      props: {
        open: true,
        title: 'Delete client',
        description: 'This client will be removed.',
        targetName: 'Ana',
        impacts: [
          { label: 'Subscriptions', value: '2 affected' },
        ],
        confirmLabel: 'Delete',
      },
      global: {
        stubs: {
          Dialog: { template: '<div><slot /></div>' },
          DialogContent: { template: '<section><slot /></section>' },
          DialogDescription: { template: '<p><slot /></p>' },
          DialogFooter: { template: '<footer><slot /></footer>' },
          DialogHeader: { template: '<header><slot /></header>' },
          DialogTitle: { template: '<h2><slot /></h2>' },
        },
      },
    })

    expect(wrapper.text()).toContain('Delete client')
    expect(wrapper.text()).toContain('Ana')
    expect(wrapper.text()).toContain('2 affected')

    await wrapper.get('[data-testid="impact-confirm"]').trigger('click')
    expect(wrapper.emitted('confirm')).toHaveLength(1)
  })
})
