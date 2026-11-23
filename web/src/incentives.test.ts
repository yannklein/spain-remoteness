import { describe, expect, it } from 'vitest'
import { incentiveProps, incentiveTooltip, type IncentivesData, type Offer } from './incentives'

const offer = (id: string, kind: Offer[1], age: number | null): Offer =>
  [id, kind, 'Region', `Title ${id}`, `Amount ${id}`, `Rule-${id}`, age, 'valid', 'source']
const offers = [offer('a', 'tax', null), offer('b', 'tax', 40), offer('c', 'grant', 36), offer('d', 'tax', null)]

describe('incentive counts', () => {
  it('count age-limited offers (any limit) only for "all ages = a"', () => {
    const p = incentiveProps([[0, null], [1, null], [2, null]], offers)
    expect(p).toMatchObject({ i1a: 2, i1o: 1, i2a: 1, i2o: 0, i3a: 0 })
  })
  it('leave out offers that cover only part of the municipality', () => {
    expect(incentiveProps([[3, 'some of its settlements only']], offers)).toMatchObject({ i1a: 0, i1o: 0 })
  })
})

describe('incentive tooltip', () => {
  const d: IncentivesData = { generated_at: '', params: { checked: '2026-11', notes: '' }, offers, m: { '01001': [], '44001': [[0, null], [3, 'some of its settlements only']] } }
  it('shows conditions and marks partial coverage', () => {
    const html = incentiveTooltip({ code: '44001', name: 'X' }, d, false, 'es')
    expect(html).toContain("Rule-a")
    expect(html).toContain('some of its settlements only')
  })
  it('says the Basque Country and Navarre are not covered rather than "none"', () => {
    expect(incentiveTooltip({ code: '01001', name: 'Y' }, d, false, 'es')).toContain('not covered')
  })
})
