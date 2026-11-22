import { describe, expect, it } from 'vitest'
import { DEFAULTS, formatHash, judge, parseHash, type GemFilters } from './gems'

// a small village that meets every default threshold
const good = (): Record<string, unknown> => ({
  pop: 800, dt: 0,
  fd: 250, md: 40,
  t1: 120, t2: 40, t3: 30,
  y1: 150, y2: 70, y3: 60, s1: 150, s2: 50, s3: 50,
  hm1: 90, hm2: 30, hm3: 20,
  rh: 7.5, rf: 9, bh: 1400, bf: 1800, srh: 0, srf: 0, sbh: 2, sbf: 2,
  ch: 12, cn: 30, cf: 4,
})
const f = (over: Partial<GemFilters> = {}): GemFilters => ({ ...DEFAULTS, ...over })

describe('judge', () => {
  it('is a gem when every active criterion passes', () => {
    expect(judge(good(), f()).cls).toBe(2)
  })
  it('is a near miss with exactly one failure', () => {
    const r = judge({ ...good(), y2: 110 }, f())
    expect(r.cls).toBe(1)
    expect(r.checks.filter((c) => !c.ok).map((c) => c.crit)).toEqual(['air'])
  })
  it('is other with two failures', () => {
    expect(judge({ ...good(), y2: 110, hm2: 60 }, f()).cls).toBe(0)
  })
  it('is too big over the size limit, even when all passes', () => {
    expect(judge({ ...good(), pop: 25000 }, f()).cls).toBe(3)
  })
  it('counts an unknown population as small', () => {
    expect(judge({ ...good(), pop: undefined }, f()).cls).toBe(2)
  })
  it('has no size limit with pop null', () => {
    expect(judge({ ...good(), pop: 3_000_000 }, f({ pop: null })).cls).toBe(2)
  })
  it('fails an unreachable (-1) city', () => {
    expect(judge({ ...good(), t2: -1 }, f()).checks.find((c) => c.crit === 'city')).toMatchObject({ ok: false, value: null })
  })
  it('fails a missing value (dataset not loaded / no data)', () => {
    const p = good()
    delete p.hm2
    expect(judge(p, f()).checks.find((c) => c.crit === 'hosp')!.ok).toBe(false)
  })
  it('fails when there is no internet value', () => {
    const p = good()
    delete p.fd
    expect(judge(p, f()).checks.find((c) => c.crit === 'net')).toMatchObject({ ok: false, value: null })
  })
  it('counts an estimate only when est is on', () => {
    const p = { ...good(), fd: undefined, fed: 150 }
    expect(judge(p, f()).checks.find((c) => c.crit === 'net')).toMatchObject({ ok: true, value: 150, est: true })
    expect(judge(p, f({ est: false })).checks.find((c) => c.crit === 'net')!.ok).toBe(false)
  })
  it('prefers the measured value over the estimate', () => {
    const p = { ...good(), fd: 20, fed: 150 }
    expect(judge(p, f()).checks.find((c) => c.crit === 'net')).toMatchObject({ ok: false, value: 20 })
  })
  it('takes the best of fixed and mobile with either', () => {
    const p = { ...good(), fd: 20, md: 120 }
    const c = judge(p, f({ net: { kind: 'either', min: 100 } })).checks.find((x) => x.crit === 'net')!
    expect(c).toMatchObject({ ok: true, value: 120 })
    expect(judge(p, f({ net: { kind: 'mobile', min: 100 } })).checks[0].ok).toBe(true)
    expect(judge(p, f({ net: { kind: 'fixed', min: 100 } })).checks[0].ok).toBe(false)
  })
  it('passes the city criterion for a city of the chosen tier', () => {
    expect(judge({ ...good(), dt: 2, t2: -1 }, f()).checks.find((c) => c.crit === 'city')).toMatchObject({ ok: true, value: 0 })
    expect(judge({ ...good(), dt: 3, t2: -1 }, f()).checks.find((c) => c.crit === 'city')!.ok).toBe(false)
  })
  it('passes a hospital in town (0 min)', () => {
    expect(judge({ ...good(), hm2: 0 }, f()).checks.find((c) => c.crit === 'hosp')!.ok).toBe(true)
  })
  it('uses the seasonal airport key with summer', () => {
    const p = { ...good(), y2: 110, s2: 50 }
    expect(judge(p, f()).checks.find((c) => c.crit === 'air')!.ok).toBe(false)
    expect(judge(p, f({ summer: true })).checks.find((c) => c.crit === 'air')!.ok).toBe(true)
  })
  it('ignores a criterion that is off', () => {
    const r = judge({ ...good(), y2: -1 }, f({ air: null }))
    expect(r.checks.map((c) => c.crit)).toEqual(['net', 'city', 'hosp'])
    expect(r.cls).toBe(2)
  })
  it('uses the chosen tier and limit', () => {
    const p = good()
    expect(judge(p, f({ city: { tier: 1, max: 90 } })).checks.find((c) => c.crit === 'city')).toMatchObject({ ok: false, value: 120 })
    expect(judge(p, f({ city: { tier: 1, max: 120 } })).checks.find((c) => c.crit === 'city')!.ok).toBe(true)
  })
})

describe('housing criteria', () => {
  it('passes rent at or under the limit for the chosen kind', () => {
    // off by default: a missing figure would otherwise exclude the smallest villages
    expect(judge(good(), f()).checks.some((c) => c.crit === 'rent')).toBe(false)
    expect(judge(good(), f({ rent: { kind: 'house', max: 10 } })).checks.find((c) => c.crit === 'rent')).toMatchObject({ ok: true, value: 7.5 })
    expect(judge(good(), f({ rent: { kind: 'flat', max: 8 } })).checks.find((c) => c.crit === 'rent')).toMatchObject({ ok: false, value: 9 })
  })
  it('fails a missing rent', () => {
    const p = good()
    delete p.rh
    expect(judge(p, f({ rent: { kind: 'house', max: 10 } })).checks.find((c) => c.crit === 'rent')).toMatchObject({ ok: false, value: null })
  })
  it('judges buy only when switched on, and reports the scope', () => {
    expect(judge(good(), f()).checks.some((c) => c.crit === 'buy')).toBe(false)
    const c = judge(good(), f({ buy: { kind: 'house', max: 1500 } })).checks.find((x) => x.crit === 'buy')!
    expect(c).toMatchObject({ ok: true, value: 1400, scope: 2 })
  })
})

describe('climate criteria', () => {
  it('are off by default', () => {
    expect(judge(good(), f()).checks.some((c) => c.crit === 'heat' || c.crit === 'frost')).toBe(false)
  })
  it('pass at or under the number of days', () => {
    const r = judge(good(), f({ heat: 10, frost: 5 }))
    expect(r.checks.find((c) => c.crit === 'heat')).toMatchObject({ ok: false, value: 12 })
    expect(r.checks.find((c) => c.crit === 'frost')).toMatchObject({ ok: true, value: 4 })
  })
  it('fail without climate data', () => {
    const p = good()
    delete p.ch
    expect(judge(p, f({ heat: 30 })).checks.find((c) => c.crit === 'heat')!.ok).toBe(false)
  })
})

describe('hash', () => {
  it('round-trips the defaults', () => {
    expect(parseHash(formatHash(DEFAULTS))).toEqual(DEFAULTS)
  })
  it('round-trips criteria switched off and other values', () => {
    const x: GemFilters = {
      pop: null, net: null, est: false, city: { tier: 3, max: 30 }, air: null, summer: true, hosp: { tier: 1, max: 120 },
      rent: null, buy: { kind: 'flat', max: 2000 }, heat: 5, frost: null,
    }
    expect(formatHash(x)).toBe('pop=any&net=off&est=0&city=3:30&air=off&summer=1&hosp=1:120&rent=off&buy=flat:2000&heat=5&frost=off')
    expect(parseHash(formatHash(x))).toEqual(x)
  })
  it('falls back to the defaults on garbage', () => {
    expect(parseHash('pop=lots&net=fast:x&city=9:60&air=2&hosp=2:-5&summer=maybe&est=2&rent=castle:9&buy=house:&heat=-1&frost=lots')).toEqual(DEFAULTS)
  })
  it('keeps old links working: no rent/buy means the defaults', () => {
    expect(parseHash('pop=20000&net=fixed:100&est=1&city=2:60&air=2:90&summer=0&hosp=2:45')).toEqual(DEFAULTS)
  })
  it('fills missing keys with the defaults', () => {
    expect(parseHash('pop=5000')).toEqual({ ...DEFAULTS, pop: 5000 })
    expect(parseHash('')).toEqual(DEFAULTS)
  })
})
