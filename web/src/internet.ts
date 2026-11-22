import type { ExpressionSpecification } from 'maplibre-gl'
import type { Tier } from './airports'

export interface InternetData {
  generated_at: string
  params: {
    source: string
    licence: string
    quarters: string[]
    min_tests: number
    min_devices: number
    estimate_radius_km: number
    estimate_min_coverage_pct?: number
    coverage: { source: string; year: number | null }
    population_year: number | null
    notes: string[]
  }
  // code -> [f_down, f_up, f_lat, f_tests, f_devices, m_down, m_up, m_lat, m_tests, m_devices,   (measured, 0-9)
  //          f_est_down, f_est_up, f_est_lat, f_est_tests, m_est_down, m_est_up, m_est_lat, m_est_tests, (10-17)
  //          cov_100, cov_1g, cov_5g, population]                                                    (18-21)
  // speeds in Mbps, latency in ms, coverage in % of households; null when below the minimum evidence
  m: Record<string, (number | null)[]>
}

type MetricKey = 'd' | 'u' | 'l'

export const METRICS: Record<
  Tier,
  { label: string; noun: string; key: MetricKey; unit: string; bins: number[]; higherIsBetter: boolean; threshold: number; help: string }
> = {
  1: {
    label: 'Download', noun: 'download', key: 'd', unit: 'Mbps', bins: [10, 25, 50, 100, 300], higherIsBetter: true, threshold: 25,
    help: 'Average download speed from speed tests. 25 Mbps is plenty for video calls; large files want more.',
  },
  2: {
    label: 'Upload', noun: 'upload', key: 'u', unit: 'Mbps', bins: [3, 10, 20, 50, 100], higherIsBetter: true, threshold: 10,
    help: 'Average upload speed from speed tests: what video calls and sending work depend on. Under 10 Mbps gets tight.',
  },
  3: {
    label: 'Latency', noun: 'latency', key: 'l', unit: 'ms', bins: [20, 35, 50, 80, 120], higherIsBetter: false, threshold: 80,
    help: 'Average latency from speed tests (lower is better). Above 80 ms, calls start to lag.',
  },
}

export async function loadInternet(): Promise<InternetData | null> {
  try {
    const r = await fetch('./data/es/internet.json')
    return r.ok ? ((await r.json()) as InternetData) : null
  } catch {
    return null
  }
}

export const POP = 21

/**
 * Feature properties (a missing key = no value):
 * measured fd fu fl ft fv / md mu ml mt mv (down, up, latency, tests, devices),
 * estimated from nearby tests fed feu fel fet / med meu mel met, official coverage c100 c1g c5g.
 */
export function internetProps(row: (number | null)[]): Record<string, number> {
  const p: Record<string, number> = {}
  const put = (k: string, v: number | null | undefined) => {
    if (typeof v === 'number') p[k] = v
  }
  ;(['f', 'm'] as const).forEach((t, ti) => {
    ;(['d', 'u', 'l', 't', 'v'] as const).forEach((k, ki) => put(`${t}${k}`, row[ti * 5 + ki]))
    ;(['d', 'u', 'l', 't'] as const).forEach((k, ki) => put(`${t}e${k}`, row[10 + ti * 4 + ki]))
  })
  put('c100', row[18])
  put('c1g', row[19])
  put('c5g', row[20])
  return p
}

const keyOf = (metric: Tier, mobile: boolean) => `${mobile ? 'm' : 'f'}${METRICS[metric].key}`
const estKeyOf = (metric: Tier, mobile: boolean) => `${mobile ? 'm' : 'f'}e${METRICS[metric].key}`
/** Measured value, else the estimate from nearby tests. */
const shown = (metric: Tier, mobile: boolean): ExpressionSpecification =>
  ['coalesce', ['get', keyOf(metric, mobile)], ['get', estKeyOf(metric, mobile)]] as ExpressionSpecification

/** Municipalities showing an estimate (no measured value): drawn in their true colour, hatched on top. */
export function internetEstimateFilter(metric: Tier, mobile: boolean): ExpressionSpecification {
  return ['all',
    ['!=', ['typeof', ['get', keyOf(metric, mobile)]], 'number'],
    ['==', ['typeof', ['get', estKeyOf(metric, mobile)]], 'number']] as ExpressionSpecification
}

/** 8x8 white diagonal hatch, for map.addImage. */
export function hatchImage(): { width: number; height: number; data: Uint8Array } {
  const n = 8
  const data = new Uint8Array(n * n * 4)
  for (let y = 0; y < n; y++) {
    for (let x = 0; x < n; x++) {
      const on = (x + y) % n < 2
      const i = (y * n + x) * 4
      data.set(on ? [255, 255, 255, 200] : [0, 0, 0, 0], i)
    }
  }
  return { width: n, height: n, data }
}

/** 6 colours, colors[0] = best for remote work; grey when there is no value. */
export function internetFill(metric: Tier, mobile: boolean, colors: string[], nodata: string): ExpressionSpecification {
  const { bins, higherIsBetter } = METRICS[metric]
  const value = shown(metric, mobile)
  // step() walks values upwards: for speeds that is worst -> best, for latency best -> worst
  const ordered = higherIsBetter ? [...colors].reverse() : colors
  const steps: (number | string)[] = [ordered[0]]
  bins.forEach((b, i) => steps.push(b, ordered[i + 1]))
  return [
    'case',
    ['!=', ['typeof', value], 'number'], nodata,
    ['step', value, ...steps] as unknown as ExpressionSpecification,
  ] as ExpressionSpecification
}

/** Legend labels from best to worst. */
export function internetLegend(metric: Tier): string[] {
  const { bins, higherIsBetter, unit } = METRICS[metric]
  const asc = [`< ${bins[0]} ${unit}`, ...bins.slice(1).map((b, i) => `${bins[i]}–${b}`), `≥ ${bins[bins.length - 1]}`]
  return higherIsBetter ? asc.reverse() : asc
}

const fmt = (v: unknown, unit: string) => (typeof v === 'number' ? `${unit === 'ms' ? Math.round(v) : v.toFixed(1)} ${unit}` : '–')

function coverageLine(p: Record<string, unknown>, year: number | null): string {
  const parts: string[] = []
  if (typeof p.c100 === 'number') parts.push(`≥100 Mbps for ${p.c100}% of households`)
  if (typeof p.c1g === 'number') parts.push(`1 Gbps ${p.c1g}%`)
  if (typeof p.c5g === 'number') parts.push(`5G ${p.c5g}%`)
  return parts.length ? `<br><span class="muted">Official coverage${year ? ` ${year}` : ''}: ${parts.join(' · ')}</span>` : ''
}

export function internetTooltip(p: Record<string, unknown>, metric: Tier, mobile: boolean, d?: InternetData | null): string {
  const name = String(p.name ?? '')
  const pop = typeof p.pop === 'number' ? `${p.pop.toLocaleString('en')} inhabitants` : ''
  const head = `<b>${name}</b>${pop ? `<br><span class="muted">${pop}</span>` : ''}`
  const cov = coverageLine(p, d?.params.coverage?.year ?? null)
  const km = d?.params.estimate_radius_km ?? 10
  const t = mobile ? 'm' : 'f'
  const kind = mobile ? 'Mobile' : 'Fixed broadband'
  const num = (k: string) => (typeof p[k] === 'number' ? (p[k] as number) : 0)
  const tests = num(`${t}t`)
  const devices = num(`${t}v`)
  const main = METRICS[metric]
  const others = ([1, 2, 3] as Tier[]).filter((m) => m !== metric)
  const block = (pre: string) =>
    `<br><span class="big">${fmt(p[`${pre}${main.key}`], main.unit)}</span> ${main.noun}` +
    `<br>${others.map((m) => `${METRICS[m].label} ${fmt(p[`${pre}${METRICS[m].key}`], METRICS[m].unit)}`).join(' · ')}`
  if (typeof p[`${t}d`] === 'number') {
    return (
      `${head}<br><span class="muted">${kind}</span>` + block(t) +
      `<br><span class="muted">from ${tests.toLocaleString('en')} tests; ${devices.toLocaleString('en')} devices in the busiest quarter</span>` +
      cov
    )
  }
  const local = tests ? `only ${tests.toLocaleString('en')} local test${tests === 1 ? '' : 's'}` : 'no local tests'
  if (typeof p[`${t}ed`] === 'number') {
    return (
      `${head}<br><span class="muted">${kind}, estimated</span>` + block(`${t}e`) +
      `<br><span class="muted">from ${num(`${t}et`).toLocaleString('en')} tests within ${km} km (${local})</span>` +
      cov
    )
  }
  const minCov = d?.params.estimate_min_coverage_pct ?? 50
  if (!mobile && typeof p.c100 === 'number' && p.c100 < minCov && num('fet') > 0) {
    return (
      `${head}<br><span class="muted">${kind}: ${local}. Only ${p.c100}% of households here can get ≥100 Mbps ` +
      `(official), so speeds measured nearby don't apply.</span>` +
      cov
    )
  }
  return (
    `${head}<br><span class="muted">${kind}: not enough speed tests, here or within ${km} km ` +
    `(${tests.toLocaleString('en')} local tests, ${devices} devices)</span>` +
    cov
  )
}

/** Share of people (with data) on the wrong side of the metric's threshold, plus the share without data. */
export function internetHeadline(d: InternetData, metric: Tier, mobile: boolean): string | null {
  const { threshold, higherIsBetter, unit, noun } = METRICS[metric]
  const i = (mobile ? 5 : 0) + (metric - 1)
  const ei = 10 + (mobile ? 4 : 0) + (metric - 1)
  let total = 0
  let withData = 0
  let estimated = 0
  let bad = 0
  for (const r of Object.values(d.m)) {
    const w = r[POP] ?? 0
    total += w
    const measured = r[i]
    const v = typeof measured === 'number' ? measured : r[ei]
    if (typeof v !== 'number') continue
    withData += w
    if (typeof measured !== 'number') estimated += w
    if (higherIsBetter ? v < threshold : v > threshold) bad += w
  }
  if (!withData) return null
  const pct = (x: number) => {
    const p = (x / withData) * 100
    return p > 0 && p < 1 ? '<1' : String(Math.round(p))
  }
  const share = (x: number) => {
    const p = (x / total) * 100
    return p > 0 && p < 1 ? '<1' : String(Math.round(p))
  }
  const kind = mobile ? 'mobile' : 'fixed'
  const cmp = higherIsBetter ? 'under' : 'over'
  return (
    `<b>${pct(bad)}%</b> of people live where ${kind} ${noun} is ${cmp} <b>${threshold} ${unit}</b>` +
    ` <span class="muted">(measured, or estimated from nearby tests for ${share(estimated)}% of people;` +
    ` unknown for ${share(total - withData)}%)</span>`
  )
}
