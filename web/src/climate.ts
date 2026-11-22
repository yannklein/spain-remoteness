import { dataUrl } from './country'
import type { ExpressionSpecification } from 'maplibre-gl'
import type { Tier } from './airports'

export interface ClimateData {
  generated_at: string
  params: { source: string; period: string; notes: string[]; population_year: number | null }
  // code -> [hot days >= 35 °C, hot nights >= 20 °C, frost days (per year), July high °C, January low °C, population]
  m: Record<string, (number | null)[]>
}

/** Tier buttons on the Climate map. */
export const CLIMATE_TEXT: Record<Tier, { label: string; noun: string; help: string }> = {
  1: { label: 'Hot days', noun: 'hot days', help: 'Days a year when it reaches 35 °C or more.' },
  2: { label: 'Hot nights', noun: 'hot nights', help: 'Nights a year that stay at 20 °C or above: hard to sleep without air conditioning.' },
  3: { label: 'Frost', noun: 'frost days', help: 'Days a year when it freezes at night.' },
}

const KEY: Record<Tier, string> = { 1: 'ch', 2: 'cn', 3: 'cf' }
const BINS: Record<Tier, number[]> = { 1: [1, 5, 10, 20, 40], 2: [1, 10, 30, 60, 90], 3: [1, 10, 30, 60, 100] }

export async function loadClimate(): Promise<ClimateData | null> {
  try {
    const r = await fetch(dataUrl('climate.json'))
    return r.ok ? ((await r.json()) as ClimateData) : null
  } catch {
    return null
  }
}

/** Feature properties ch (hot days), cn (hot nights), cf (frost days), cjh (July high), cjl (January low). */
export function climateProps(row: (number | null)[]): Record<string, number> {
  const p: Record<string, number> = {}
  ;['ch', 'cn', 'cf', 'cjh', 'cjl'].forEach((k, i) => {
    if (typeof row[i] === 'number') p[k] = row[i] as number
  })
  return p
}

/** 6 colours, colors[0] = fewest days; nodata without a value. */
export function climateFill(tier: Tier, colors: string[], nodata: string): ExpressionSpecification {
  const key = KEY[tier]
  const steps: (number | string)[] = [colors[0]]
  BINS[tier].forEach((b, i) => steps.push(b, colors[i + 1]))
  return ['case', ['!', ['has', key]], nodata, ['step', ['get', key], ...steps]] as unknown as ExpressionSpecification
}

export function climateLegend(tier: Tier): string[] {
  const b = BINS[tier]
  return ['under 1 a year', ...b.slice(0, -1).map((v, i) => `${v}–${b[i + 1]}`), `${b[b.length - 1]}+`]
}

const days = (v: unknown) => (typeof v === 'number' ? (v < 1 && v > 0 ? 'under 1' : String(Math.round(v))) : '–')
const deg = (v: unknown) => (typeof v === 'number' ? `${v.toFixed(1)} °C` : '–')

export function climateTooltip(p: Record<string, unknown>, period: string): string {
  const name = String(p.name ?? '')
  const pop = typeof p.pop === 'number' ? `${p.pop.toLocaleString('en')} inhabitants` : ''
  const head = `<b>${name}</b>${pop ? `<br><span class="muted">${pop}</span>` : ''}`
  if (p.ch === undefined) return `${head}<br><span class="muted">No climate data</span>`
  return (
    head +
    `<br>Hot days (≥ 35 °C): <b>${days(p.ch)}</b> a year` +
    `<br>Hot nights (≥ 20 °C): <b>${days(p.cn)}</b> a year` +
    `<br>Frost days: <b>${days(p.cf)}</b> a year` +
    `<br>July average high: <b>${deg(p.cjh)}</b>` +
    `<br>January average low: <b>${deg(p.cjl)}</b>` +
    `<br><span class="muted">Averages ${period}</span>`
  )
}

/** Population-weighted median among places under 20,000 inhabitants. */
export function climateHeadline(d: ClimateData, tier: Tier): string | null {
  const i = tier - 1
  const vals: [number, number][] = []
  for (const r of Object.values(d.m)) {
    const pop = r[5] ?? 0
    if (typeof r[i] === 'number' && pop < 20000) vals.push([r[i] as number, pop || 1])
  }
  if (!vals.length) return null
  vals.sort((a, b) => a[0] - b[0])
  const total = vals.reduce((s, v) => s + v[1], 0)
  let acc = 0
  const median = vals.find((v) => (acc += v[1]) >= total / 2)![0]
  return `Half of the people in places under 20,000 have more than <b>${Math.round(median)} ${CLIMATE_TEXT[tier].noun}</b> a year (${d.params.period} average).`
}
