import { dataCountry, dataUrl } from './country'
import type { ExpressionSpecification } from 'maplibre-gl'
import type { Tier } from './airports'

export interface SettingData {
  generated_at: string
  params: { labels: string; heritage: string; sources: string[]; green_km: number; relief_km: number; ndvi_km: number }
  // code -> [nature %, water %, built %, July NDVI, relief m, elevation m, label, historic centre, listed buildings, pop]
  m: Record<string, (number | string | null)[]>
}

export const SETTING_TEXT: Record<Tier, { label: string; noun: string; help: string }> = {
  1: { label: 'Green', noun: 'nature', help: 'Share of the land within 3 km of the village centre that is forest, meadow, scrub or wetland (water left out).' },
  2: { label: 'Character', noun: 'character', help: 'Beautiful-village labels, protected historic centres and listed buildings.' },
  3: { label: 'Setting', noun: 'relief', help: 'Height difference within 5 km: hills and mountains around.' },
}

export const LABELS: Record<string, string> = {
  pmb: 'Los Pueblos más Bonitos de España',
  pbvf: 'Plus Beaux Villages de France',
  pcc: 'Petite Cité de Caractère',
}

export async function loadSetting(): Promise<SettingData | null> {
  try {
    const r = await fetch(dataUrl('setting.json'))
    return r.ok ? ((await r.json()) as SettingData) : null
  } catch {
    return null
  }
}

/** sn nature %, sw water %, sb built %, sv July NDVI, sr relief m, se elevation m, sl label, sh historic centre, sc listed. */
export function settingProps(row: (number | string | null)[]): Record<string, number | string> {
  const p: Record<string, number | string> = {}
  ;['sn', 'sw', 'sb', 'sv', 'sr', 'se', 'sl', 'sh', 'sc'].forEach((k, i) => {
    const v = row[i]
    if (v !== null && v !== undefined) p[k] = v
  })
  return p
}

const BINS: Record<string, number[]> = {
  sn: [10, 25, 40, 55, 70], // nature %: colors[0] = least green
  sv: [0.25, 0.35, 0.45, 0.55, 0.65],
  sr: [50, 150, 300, 500, 800],
}
// light = more of it, like the other maps (light = better): reverse the ramp
const ramp = (colors: string[]) => [...colors].reverse()

export const settingKey = (tier: Tier, summer: boolean) => (tier === 1 ? (summer ? 'sv' : 'sn') : 'sr')

export function settingFill(tier: Tier, summer: boolean, colors: string[], nodata: string): ExpressionSpecification {
  if (tier === 2) {
    // character: label > protected historic centre > listed buildings (many / some / none). Spain's listed-building
    // counts come from Wikidata and are uneven between regions: not used for colour there.
    if (dataCountry() === 'es') {
      return ['case', ['!', ['has', 'sh']], nodata, ['has', 'sl'], '#d99a00', ['==', ['get', 'sh'], 1], '#0d366b', '#e7e5e0'] as ExpressionSpecification
    }
    return ['case',
      ['!', ['has', 'sh']], nodata,
      ['has', 'sl'], '#d99a00',
      ['==', ['get', 'sh'], 1], '#0d366b',
      ['>=', ['coalesce', ['get', 'sc'], 0], 5], '#3987e5',
      ['>=', ['coalesce', ['get', 'sc'], 0], 1], '#9ec5f4',
      '#e7e5e0'] as ExpressionSpecification
  }
  const key = settingKey(tier, summer)
  const c = ramp(colors)
  const steps: (number | string)[] = [c[0]]
  BINS[key].forEach((b, i) => steps.push(b, c[i + 1]))
  return ['case', ['!', ['has', key]], nodata, ['step', ['get', key], ...steps]] as unknown as ExpressionSpecification
}

export function settingLegend(tier: Tier, summer: boolean, colors: string[]): [string, string][] {
  if (tier === 2) {
    const head: [string, string][] = [['#d99a00', 'Beautiful-village label'], ['#0d366b', 'Protected historic centre']]
    if (dataCountry() === 'es') return [...head, ['#e7e5e0', 'Neither']]
    return [...head, ['#3987e5', '5+ listed buildings'], ['#9ec5f4', '1-4 listed buildings'], ['#e7e5e0', 'None']]
  }
  const key = settingKey(tier, summer)
  const b = BINS[key]
  const unit = key === 'sn' ? '%' : key === 'sr' ? ' m' : ''
  const c = ramp(colors)
  const labels = [`under ${b[0]}${unit}`, ...b.slice(0, -1).map((v, i) => `${v}-${b[i + 1]}${unit}`), `${b[b.length - 1]}${unit}+`]
  return labels.map((l, i) => [c[i], l])
}

const pct = (v: unknown) => (typeof v === 'number' ? `${Math.round(v)}%` : '-')

export function settingTooltip(p: Record<string, unknown>): string {
  const name = String(p.name ?? '')
  const pop = typeof p.pop === 'number' ? `${p.pop.toLocaleString('en')} inhabitants` : ''
  const head = `<b>${name}</b>${pop ? `<br><span class="muted">${pop}</span>` : ''}`
  if (p.sn === undefined && p.sh === undefined) return `${head}<br><span class="muted">No setting data</span>`
  const green = typeof p.sv === 'number' ? (p.sv >= 0.55 ? 'lush' : p.sv >= 0.4 ? 'fairly green' : p.sv >= 0.3 ? 'mixed' : 'dry') : ''
  const lines = [
    `Nature within 3 km: <b>${pct(p.sn)}</b>${typeof p.sb === 'number' ? ` <span class="muted">(built-up ${pct(p.sb)})</span>` : ''}`,
    typeof p.sv === 'number' ? `In July: <b>${green}</b> <span class="muted">(NDVI ${(p.sv as number).toFixed(2)})</span>` : '',
    typeof p.sr === 'number' ? `Relief within 5 km: <b>${p.sr} m</b>${typeof p.se === 'number' ? ` <span class="muted">(village at ${p.se} m)</span>` : ''}` : '',
    typeof p.sw === 'number' && (p.sw as number) >= 1 ? `Water within 3 km: <b>${pct(p.sw)}</b> (lake, wide river or sea)` : '',
    p.sl ? `<b>${LABELS[String(p.sl)] ?? p.sl}</b>` : '',
    p.sh === 1 ? 'Protected historic centre' : '',
    typeof p.sc === 'number' && p.sc > 0
      ? `${p.sc} listed building${p.sc === 1 ? '' : 's'}${dataCountry() === 'es' ? ' <span class="muted">(Wikidata, incomplete in some regions)</span>' : ''}`
      : '',
  ].filter(Boolean)
  return head + lines.map((l) => `<br>${l}`).join('')
}

/** Share of people in places under 20,000 with at least 50% nature within 3 km (or the tier's own measure). */
export function settingHeadline(d: SettingData, tier: Tier, summer = false): string | null {
  let total = 0
  let yes = 0
  for (const r of Object.values(d.m)) {
    const pop = (r[9] as number) ?? 0
    if (pop >= 20000) continue
    total += pop
    const hit = tier === 1 ? (summer ? (r[3] as number) >= 0.5 : (r[0] as number) >= 50) : tier === 2 ? Boolean(r[6]) || r[7] === 1 : (r[4] as number) >= 300
    if (hit) yes += pop
  }
  if (!total) return null
  const pct = Math.round((yes / total) * 100)
  const what = tier === 1 ? (summer ? 'have land still green in July (vegetation index 0.5+)' : 'have at least half of the land around as nature (3 km)') : tier === 2 ? 'live in a labelled village or a protected historic centre' : 'have hills or mountains around (300 m+ within 5 km)'
  return `<b>${pct}%</b> of the people in places under 20,000 ${what}.`
}
