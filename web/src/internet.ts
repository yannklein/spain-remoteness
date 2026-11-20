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
    population_year: number | null
    notes: string[]
  }
  // code -> [f_down, f_up, f_lat, f_tests, f_devices, m_down, m_up, m_lat, m_tests, m_devices, population]
  // speeds in Mbps, latency in ms; null when below the minimum evidence
  m: Record<string, (number | null)[]>
}

type MetricKey = 'd' | 'u' | 'l'

export const METRICS: Record<
  Tier,
  { label: string; noun: string; key: MetricKey; unit: string; bins: number[]; higherIsBetter: boolean; threshold: number; help: string }
> = {
  1: {
    label: 'Download', noun: 'download', key: 'd', unit: 'Mbps', bins: [10, 25, 50, 100, 300], higherIsBetter: true, threshold: 25,
    help: 'Average measured download speed. 25 Mbps is plenty for video calls; large files want more.',
  },
  2: {
    label: 'Upload', noun: 'upload', key: 'u', unit: 'Mbps', bins: [3, 10, 20, 50, 100], higherIsBetter: true, threshold: 10,
    help: 'Average measured upload speed: what video calls and sending work depend on. Under 10 Mbps gets tight.',
  },
  3: {
    label: 'Latency', noun: 'latency', key: 'l', unit: 'ms', bins: [20, 35, 50, 80, 120], higherIsBetter: false, threshold: 80,
    help: 'Average measured latency (lower is better). Above 80 ms, calls start to lag.',
  },
}

export async function loadInternet(): Promise<InternetData | null> {
  try {
    const r = await fetch('./data/internet.json')
    return r.ok ? ((await r.json()) as InternetData) : null
  } catch {
    return null
  }
}

/** Feature properties: fd fu fl ft fv (fixed down/up/latency/tests/devices), md mu ml mt mv (mobile). */
export function internetProps(row: (number | null)[]): Record<string, number> {
  const p: Record<string, number> = {}
  ;(['f', 'm'] as const).forEach((t, ti) => {
    ;(['d', 'u', 'l', 't', 'v'] as const).forEach((k, ki) => {
      const v = row[ti * 5 + ki]
      if (typeof v === 'number') p[`${t}${k}`] = v // missing key = not enough tests
    })
  })
  return p
}

const keyOf = (metric: Tier, mobile: boolean) => `${mobile ? 'm' : 'f'}${METRICS[metric].key}`

/** 6 colours, colors[0] = best for remote work; grey when there is no value. */
export function internetFill(metric: Tier, mobile: boolean, colors: string[], nodata: string): ExpressionSpecification {
  const { bins, higherIsBetter } = METRICS[metric]
  const key = keyOf(metric, mobile)
  // step() walks values upwards: for speeds that is worst -> best, for latency best -> worst
  const ordered = higherIsBetter ? [...colors].reverse() : colors
  const steps: (number | string)[] = [ordered[0]]
  bins.forEach((b, i) => steps.push(b, ordered[i + 1]))
  return [
    'case',
    ['!=', ['typeof', ['get', key]], 'number'], nodata,
    ['step', ['get', key], ...steps] as unknown as ExpressionSpecification,
  ] as ExpressionSpecification
}

/** Legend labels from best to worst. */
export function internetLegend(metric: Tier): string[] {
  const { bins, higherIsBetter, unit } = METRICS[metric]
  const asc = [`< ${bins[0]} ${unit}`, ...bins.slice(1).map((b, i) => `${bins[i]}–${b}`), `≥ ${bins[bins.length - 1]}`]
  return higherIsBetter ? asc.reverse() : asc
}

const fmt = (v: unknown, unit: string) => (typeof v === 'number' ? `${unit === 'ms' ? Math.round(v) : v.toFixed(1)} ${unit}` : '–')

export function internetTooltip(p: Record<string, unknown>, metric: Tier, mobile: boolean): string {
  const name = String(p.name ?? '')
  const pop = typeof p.pop === 'number' ? `${p.pop.toLocaleString('en')} inhabitants` : ''
  const head = `<b>${name}</b>${pop ? `<br><span class="muted">${pop}</span>` : ''}`
  const t = mobile ? 'm' : 'f'
  const kind = mobile ? 'Mobile' : 'Fixed broadband'
  const tests = typeof p[`${t}t`] === 'number' ? (p[`${t}t`] as number) : 0
  const devices = typeof p[`${t}v`] === 'number' ? (p[`${t}v`] as number) : 0
  if (typeof p[`${t}d`] !== 'number') {
    return (
      `${head}<br><span class="muted">${kind}: not enough speed tests ` +
      `(${tests.toLocaleString('en')} tests, ${devices} devices; needs 20 tests and 5 devices)</span>`
    )
  }
  const main = METRICS[metric]
  const others = ([1, 2, 3] as Tier[]).filter((m) => m !== metric)
  return (
    `${head}<br><span class="muted">${kind}</span>` +
    `<br><span class="big">${fmt(p[`${t}${main.key}`], main.unit)}</span> ${main.noun}` +
    `<br>${others.map((m) => `${METRICS[m].label} ${fmt(p[`${t}${METRICS[m].key}`], METRICS[m].unit)}`).join(' · ')}` +
    `<br><span class="muted">from ${tests.toLocaleString('en')} tests; ${devices.toLocaleString('en')} devices in the busiest quarter</span>`
  )
}

/** Share of people (with data) on the wrong side of the metric's threshold, plus the share without data. */
export function internetHeadline(d: InternetData, metric: Tier, mobile: boolean): string | null {
  const { threshold, higherIsBetter, unit, noun } = METRICS[metric]
  const i = (mobile ? 5 : 0) + (metric - 1)
  let total = 0
  let withData = 0
  let bad = 0
  for (const r of Object.values(d.m)) {
    const w = r[10] ?? 0
    total += w
    const v = r[i]
    if (typeof v !== 'number') continue
    withData += w
    if (higherIsBetter ? v < threshold : v > threshold) bad += w
  }
  if (!withData) return null
  const pct = (x: number) => {
    const p = (x / withData) * 100
    return p > 0 && p < 1 ? '<1' : String(Math.round(p))
  }
  const missing = Math.round(((total - withData) / total) * 100)
  const kind = mobile ? 'mobile' : 'fixed'
  const cmp = higherIsBetter ? 'under' : 'over'
  return (
    `<b>${pct(bad)}%</b> of people live where measured ${kind} ${noun} is ${cmp} <b>${threshold} ${unit}</b>` +
    ` <span class="muted">(${missing}% live where there are too few tests to tell)</span>`
  )
}
