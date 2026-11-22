import type { FeatureCollection } from 'geojson'

export type Tier = 1 | 2 | 3

// [iata, name, country, lat, lng, tierYear, tierSummer, note, reach]
// reach = municipalities that get there within the cap; 0 = no public transport link in the data
export type Airport = [string, string, string, number, number, number | null, number | null, string, number]

export interface AirportsData {
  generated_at: string
  params: { arrival: string; max_minutes: number; population_year: number | null; notes: string[] }
  airports: Airport[]
  // code -> [y1, ya1, y2, ya2, y3, ya3, s1, sa1, s2, sa2, s3, sa3, population]
  // minutes (-1 = over the cap / none), index into airports (-1 = none)
  m: Record<string, (number | null)[]>
}

export const AIRPORT_TEXT: Record<Tier, { label: string; noun: string; help: string }> = {
  1: {
    label: 'Intercontinental',
    noun: 'an intercontinental airport',
    help: 'Airports with flights longer than 4,000 km: the Americas, the Gulf, Asia.',
  },
  2: {
    label: 'Europe',
    noun: 'an airport with European flights',
    help: 'Airports with at least one flight to another European country.',
  },
  3: { label: 'Any airport', noun: 'an airport', help: 'Any airport with scheduled passenger flights.' },
}

const COUNTRY: Record<string, string> = { PT: 'Portugal', FR: 'France', GI: 'Gibraltar' }

export async function loadAirports(): Promise<AirportsData | null> {
  try {
    const r = await fetch('./data/es/airports.json')
    return r.ok ? ((await r.json()) as AirportsData) : null
  } catch {
    return null
  }
}

/** Feature properties for one municipality row: y1, ya1 ... s3, sa3. */
export function airportProps(row: (number | null)[]): Record<string, number> {
  const p: Record<string, number> = {}
  ;(['y', 's'] as const).forEach((v, vi) => {
    for (let t = 1; t <= 3; t++) {
      const i = vi * 6 + (t - 1) * 2
      p[`${v}${t}`] = row[i] as number
      p[`${v}a${t}`] = row[i + 1] as number
    }
  })
  return p
}

const tierOf = (a: Airport, summer: boolean) => (summer ? a[6] : a[5])

export function airportMarkers(d: AirportsData, tier: Tier, summer: boolean): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: d.airports
      .filter((a) => (tierOf(a, summer) ?? 99) <= tier)
      .map((a) => ({
        type: 'Feature',
        properties: { name: a[0], iata: a[0], tier: tierOf(a, summer), reach: a[8] },
        geometry: { type: 'Point', coordinates: [a[4], a[3]] },
      })),
  }
}

export function airportCounts(d: AirportsData, summer: boolean): [number, number, number] {
  // only airports somebody can actually reach count
  const n = (t: number) => d.airports.filter((a) => a[8] > 0 && (tierOf(a, summer) ?? 99) <= t).length
  return [n(1), n(2), n(3)]
}

export function airportTooltip(
  d: AirportsData,
  p: Record<string, unknown>,
  tier: Tier,
  summer: boolean,
  fmt: (t: number, max: number) => string,
  at?: [number, number],
): string {
  const name = String(p.name ?? '')
  const pop = typeof p.pop === 'number' ? `${p.pop.toLocaleString('en')} inhabitants` : ''
  const head = `<b>${name}</b>${pop ? `<br><span class="muted">${pop}</span>` : ''}`
  const v = summer ? 's' : 'y'
  const t = p[`${v}${tier}`]
  if (t === undefined) return `${head}<br><span class="muted">No travel data</span>`
  const ai = p[`${v}a${tier}`] as number
  const a = ai >= 0 ? d.airports[ai] : null
  const max = d.params.max_minutes
  if (!a) {
    const noun = AIRPORT_TEXT[tier].noun.replace(/^an? /, '')
    // an eligible airport close by that nobody reaches: say so rather than "no airport"
    const near = at
      ? d.airports.filter((x) => x[8] === 0 && (tierOf(x, summer) ?? 99) <= tier && kmBetween(at, [x[4], x[3]]) < 40)
      : []
    const why = near.length
      ? `<br><span class="muted">${near.map((x) => `${x[1]} (${x[0]})`).join(', ')} has no public transport link in TravelTime's data</span>`
      : ''
    return `${head}<br><span class="muted">no ${noun} reachable within ${max / 60} h by public transport</span>${why}`
  }
  const where = COUNTRY[a[2]] ? `${a[0]}, ${COUNTRY[a[2]]}` : a[0]
  return `${head}<br><span class="big">${fmt(t as number, max)}</span><br>to ${a[1]} (${where})`
}

function kmBetween([lng1, lat1]: [number, number], [lng2, lat2]: [number, number]): number {
  const r = Math.PI / 180
  const h =
    Math.sin(((lat2 - lat1) * r) / 2) ** 2 +
    Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(((lng2 - lng1) * r) / 2) ** 2
  return 2 * 6371 * Math.asin(Math.sqrt(h))
}

/** Share of all people more than 60 min from an airport of this tier (population-weighted). */
export function airportHeadline(d: AirportsData, tier: Tier, summer: boolean): string | null {
  const i = (summer ? 6 : 0) + (tier - 1) * 2
  let total = 0
  let far = 0
  for (const r of Object.values(d.m)) {
    const w = r[12] ?? 0
    total += w
    const t = r[i] as number
    if (t < 0 || t > 60) far += w
  }
  if (!total) return null
  const pct = Math.round((far / total) * 100)
  return `<b>${pct}%</b> of people are more than <b>1 hour</b> by public transport from ${AIRPORT_TEXT[tier].noun}.`
}
