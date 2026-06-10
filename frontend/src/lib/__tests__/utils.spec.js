import { describe, it, expect } from 'vitest'
import { cn } from '../utils'

describe('cn', () => {
  it('merges tailwind classes and keeps the last conflicting utility', () => {
    expect(cn('px-2 text-sm', 'px-4', false && 'hidden')).toBe('text-sm px-4')
  })
})
