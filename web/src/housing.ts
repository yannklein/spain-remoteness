import { dataCountry, dataUrl } from './country'
import type { ExpressionSpecification } from 'maplibre-gl'
import type { Tier } from './airports'

export interface HousingData {
  generated_at: string
  params: {
    sources: string[]
    notes: string[]
    nearby_km: number
    population_year: number | null
    rent_years?: number[]
    buy_period?: string
    buy_all_dwellings?: boolean // Spain: one appraisal value for any home (houses = flats)
  }
  // code -> [rent_house, rent_flat, buy_house, buy_flat, s_rh, s_rf, s_bh, s_bf, n_rh, n_rf, n_bh, n_bf, population]
  // €/m² (rent per month); scope 0 own figure, 1 nearby estimate, 2 province average, 3 area model
  m: Record<string, (number | null)[]>
}

/** Tier buttons on the Housing map: 1 = rent, 2 = buy (3 unused). */
export const HOUSING_TEXT: Record<Tier, { label: string; noun: string; help: string }> = {
  1: { label: 'Rent', noun: 'rent', help: 'Rent per m² per month.' },
  2: { label: 'Buy', noun: 'price', help: 'Price per m².' },
  3: { label: '', noun: '', help: '' },
}

const KEYS = ['rh', 'rf', 'bh', 'bf'] as const
// Rents differ in kind between the countries (declared leases vs listings incl. charges): bins per country
const BINS: Record<string, Record<'r' | 'b', number[]>> = {
  es: { r: [3, 4, 5, 6, 8], b: [800, 1200, 1600, 2200, 3000] },
  fr: { r: [7, 8, 9, 10, 12], b: [800, 1200, 1600, 2200, 3000] },
}
const bins = (tier: Tier) => BINS[dataCountry()][tier === 1 ? 'r' : 'b']
export const SCOPE_TEXT: Record<number, string> = {
  1: 'estimated from places nearby',
  2: 'province average',
  3: 'estimated from its area',
}

export async function loadHousing(): Promise<HousingData | null> {
  try {
    const r = await fetch(dataUrl('housing.json'))
    return r.ok ? ((await r.json()) as HousingData) : null
  } catch {
    return null
  }
}

/** Feature properties rh rf bh bf (€/m²), srh.. (scope), nrh.. (count); missing keys = no value. */
export function housingProps(row: (number | null)[]): Record<string, number> {
  const p: Record<string, number> = {}
  KEYS.forEach((k, i) => {
    if (typeof row[i] === 'number') p[k] = row[i] as number
    if (typeof row[4 + i] === 'number') p[`s${k}`] = row[4 + i] as number
    if (typeof row[8 + i] === 'number') p[`n${k}`] = row[8 + i] as number
  })
  return p
}

export const housingKey = (tier: Tier, flats: boolean) => `${tier === 1 ? 'r' : 'b'}${flats ? 'f' : 'h'}`

const euros = (v: number, rent: boolean) =>
  rent ? `€${v.toFixed(1)}` : `€${Math.round(v).toLocaleString('en')}`

/** 6 colours, colors[0] = cheapest; nodata when there is no figure. */
export function housingFill(tier: Tier, flats: boolean, colors: string[], nodata: string): ExpressionSpecification {
  const key = housingKey(tier, flats)
  const steps: (number | string)[] = [colors[0]]
  bins(tier).forEach((b, i) => steps.push(b, colors[i + 1]))
  return ['case', ['!', ['has', key]], nodata, ['step', ['get', key], ...steps]] as unknown as ExpressionSpecification
}

/** Anything that is not the municipality's own figure is hatched. */
export function housingEstimateFilter(tier: Tier, flats: boolean): ExpressionSpecification {
  const key = housingKey(tier, flats)
  return ['all', ['has', key], ['>', ['coalesce', ['get', `s${key}`], 0], 0]] as ExpressionSpecification
}

export function housingLegend(tier: Tier): string[] {
  const rent = tier === 1
  const b = bins(tier)
  const f = (v: number) => euros(v, rent).replace('.0', '')
  return [`under ${f(b[0])}`, ...b.slice(0, -1).map((v, i) => `${f(v)}–${f(b[i + 1])}`), `${f(b[b.length - 1])}+`]
}

/** allDwellings (Spain): rents come from leases and the buy figure is one appraisal value for any home. */
export function housingTooltip(p: Record<string, unknown>, allDwellings: boolean): string {
  const name = String(p.name ?? '')
  const pop = typeof p.pop === 'number' ? `${p.pop.toLocaleString('en')} inhabitants` : ''
  const head = `<b>${name}</b>${pop ? `<br><span class="muted">${pop}</span>` : ''}`
  const line = (label: string, k: string, rent: boolean) => {
    const v = p[k]
    if (typeof v !== 'number') return `<br>${label}: <span class="muted">no figure</span>`
    const scope = p[`s${k}`] as number | undefined
    const n = p[`n${k}`] as number | undefined
    const counted = rent ? (allDwellings ? 'leases' : 'listings') : allDwellings ? 'appraisals' : 'sales'
    const note = scope ? SCOPE_TEXT[scope] : n ? `${n.toLocaleString('en')} ${counted}` : ''
    return `<br>${label}: <b>${scope ? '≈ ' : ''}${euros(v, rent)}/m²</b>${rent ? ' a month' : ''}${note ? ` <span class="muted">(${note})</span>` : ''}`
  }
  const sameBuy = allDwellings && p.bh === p.bf
  return (
    head +
    line('Rent, house', 'rh', true) +
    line('Rent, flat', 'rf', true) +
    (sameBuy ? line('Buy, any home', 'bh', false) : line('Buy, house', 'bh', false) + line('Buy, flat', 'bf', false))
  )
}

/** Population-weighted median among places under 20,000 inhabitants. */
export function housingHeadline(d: HousingData, tier: Tier, flats: boolean): string | null {
  const i = (tier === 1 ? 0 : 2) + (flats ? 1 : 0)
  const vals: [number, number][] = []
  for (const r of Object.values(d.m)) {
    const pop = r[12] ?? 0
    if (typeof r[i] === 'number' && pop < 20000) vals.push([r[i] as number, pop || 1])
  }
  if (!vals.length) return null
  vals.sort((a, b) => a[0] - b[0])
  const total = vals.reduce((s, v) => s + v[1], 0)
  let acc = 0
  const median = vals.find((v) => (acc += v[1]) >= total / 2)![0]
  const what = tier === 1 ? `a ${flats ? 'flat' : 'house'} rents for under` : `a ${flats ? 'flat' : 'house'} sells for under`
  const coarse = tier === 2 && vals.length && Object.values(d.m).some((r) => r[6] === 2) ? ' (province averages for most villages)' : ''
  return `Half of the people in places under 20,000 live where ${what} <b>${euros(median, tier === 1)}/m²</b>${tier === 1 ? ' a month' : ''}${coarse}.`
}
