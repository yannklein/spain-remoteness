import { describe, expect, it } from 'vitest'
import { housingTooltip } from './housing'

describe('housing tooltip', () => {
  it('shows one "any home" line with appraisals for Spanish all-dwellings values', () => {
    const html = housingTooltip({ name: 'Teruel', rh: 4, srh: 0, nrh: 188, bh: 1810, bf: 1810, sbh: 0, sbf: 0, nbh: 97, nbf: 97 }, true)
    expect(html).toContain('Buy, any home')
    expect(html).toContain('97 appraisals')
    expect(html).not.toContain('Buy, flat')
    expect(html).not.toContain('sales')
  })
  it('keeps house and flat apart where the data has both', () => {
    const html = housingTooltip({ name: 'Guéret', bh: 1170, bf: 960, sbh: 0, sbf: 0, nbh: 520, nbf: 317 }, false)
    expect(html).toContain('Buy, house')
    expect(html).toContain('Buy, flat')
    expect(html).toContain('520 sales')
  })
})
