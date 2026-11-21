import type { FeatureCollection } from 'geojson'
import type { Tier } from './airports'

// [codcnh, name, muni, lat, lng, tier, beds, public, cath_lab, reach, point_source]
export type Hospital = [string, string, string, number, number, number, number | null, 0 | 1, 0 | 1, number, string]

export interface HospitalsData {
  generated_at: string
  params: { arrival: string; max_minutes: number; source: string; population_year: number | null; notes: string[] }
  hospitals: Hospital[]
  // code -> [t1, h1, t2, h2, t3, h3, population]; minutes (-1 = over the cap), hospital index (-1 = none)
  m: Record<string, (number | null)[]>
}

export const HOSPITAL_TEXT: Record<Tier, { label: string; noun: string; help: string }> = {
  1: {
    label: 'Major',
    noun: 'a major hospital',
    help: 'Public hospitals with a cardiac cath lab and 100+ beds: heart attacks, strokes, major trauma, most specialists.',
  },
  2: {
    label: 'Public',
    noun: 'a public hospital',
    help: 'Any public general hospital (incl. Catalonia’s public network): 24 h emergencies and the core specialties.',
  },
  3: { label: 'Any', noun: 'a hospital', help: 'Any general hospital, private clinics included.' },
}

export const HEADLINE_MINUTES = 30

export async function loadHospitals(): Promise<HospitalsData | null> {
  try {
    const r = await fetch('./data/hospitals.json')
    return r.ok ? ((await r.json()) as HospitalsData) : null
  } catch {
    return null
  }
}

/** Feature properties hm1..hm3 (minutes) and hi1..hi3 (hospital index). */
export function hospitalProps(row: (number | null)[]): Record<string, number> {
  const p: Record<string, number> = {}
  for (let t = 1; t <= 3; t++) {
    p[`hm${t}`] = row[(t - 1) * 2] as number
    p[`hi${t}`] = row[(t - 1) * 2 + 1] as number
  }
  return p
}

export function hospitalMarkers(d: HospitalsData, tier: Tier): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: d.hospitals
      .filter((h) => h[5] <= tier)
      .map((h) => ({
        type: 'Feature',
        // no label: hospital names are long and would cover the map; the tooltip names the hospital
        properties: { name: '', tier: h[5], reach: h[9] },
        geometry: { type: 'Point', coordinates: [h[4], h[3]] },
      })),
  }
}

export function hospitalCounts(d: HospitalsData): [number, number, number] {
  // only hospitals somebody can reach by public transport count (as for airports)
  const n = (t: number) => d.hospitals.filter((h) => h[9] > 0 && h[5] <= t).length
  return [n(1), n(2), n(3)]
}

export function hospitalTooltip(
  d: HospitalsData,
  p: Record<string, unknown>,
  tier: Tier,
  fmt: (t: number, max: number) => string,
  muniName: (code: string) => string,
): string {
  const name = String(p.name ?? '')
  const pop = typeof p.pop === 'number' ? `${p.pop.toLocaleString('en')} inhabitants` : ''
  const head = `<b>${name}</b>${pop ? `<br><span class="muted">${pop}</span>` : ''}`
  const t = p[`hm${tier}`]
  if (t === undefined) return `${head}<br><span class="muted">No travel data</span>`
  const hi = p[`hi${tier}`] as number
  const h = hi >= 0 ? d.hospitals[hi] : null
  const max = d.params.max_minutes
  if (!h) return `${head}<br><span class="muted">no ${HOSPITAL_TEXT[tier].noun.replace(/^an? /, '')} within ${max / 60} h</span>`
  if (t === 0) {
    const kind = HOSPITAL_TEXT[tier].noun.replace(/^an? /, '')
    return `${head}<br><span class="big">In town</span><br>${kind[0].toUpperCase()}${kind.slice(1)} in this municipality: ${h[1]}`
  }
  const town = muniName(h[2])
  return `${head}<br><span class="big">${fmt(t as number, max)}</span><br>to ${h[1]}${town ? ` (${town})` : ''}`
}

/** Share of all people more than HEADLINE_MINUTES from a hospital of this tier (population-weighted). */
export function hospitalHeadline(d: HospitalsData, tier: Tier): string | null {
  const i = (tier - 1) * 2
  let total = 0
  let far = 0
  for (const r of Object.values(d.m)) {
    const w = r[6] ?? 0
    total += w
    const t = r[i] as number
    if (t < 0 || t > HEADLINE_MINUTES) far += w
  }
  if (!total) return null
  const pct = Math.round((far / total) * 100)
  return `<b>${pct}%</b> of people are more than <b>${HEADLINE_MINUTES} min</b> by public transport from ${HOSPITAL_TEXT[tier].noun}.`
}
