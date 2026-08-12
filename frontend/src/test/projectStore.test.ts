import { describe, it, expect } from 'vitest'
import { PROJECT_SCOPED_QUERY_PREFIXES } from '@/store/projectStore'

describe('project store', () => {
  it('defines query prefixes cleared on project switch', () => {
    expect(PROJECT_SCOPED_QUERY_PREFIXES).toContain('incidents')
    expect(PROJECT_SCOPED_QUERY_PREFIXES).toContain('dashboard')
    expect(PROJECT_SCOPED_QUERY_PREFIXES).toContain('compliance')
  })
})
