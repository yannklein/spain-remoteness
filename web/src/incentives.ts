import { dataUrl } from './country'
import type { ExpressionSpecification } from 'maplibre-gl'
import type { Tier } from './airports'

// [id, kind, region, title, amount, conditions, age_max ("under N"), valid, source]
export type Offer = [string, 'tax' | 'grant' | 'business', string, string, string, string, number | null, string, string]

export interface IncentivesData {
  generated_at: string
  params: { checked: string; notes: string }
  offers: Offer[]
  // code -> [[offer index, detail for this municipality or null], ...]
  m: Record<string, [number, string | null][]>
}

const KINDS = ['tax', 'grant', 'business'] as const
/** Offers with an age limit (under 35, 36 or 40) show only with the age box ticked. */
export const YOUNG_ONLY = (o: Offer) => o[6] !== null
/** A detail ending in "only" means the offer covers part of the municipality: listed, never counted. */
export const PARTIAL = (detail: string | null) => !!detail && /\bonly$/.test(detail)
/** Spain: the Basque Country and Navarre have their own tax systems, not researched. */
const NOT_COVERED = (cc: string, code: string) => cc === 'es' && ['01', '20', '31', '48'].includes(code.slice(0, 2))

export const INCENTIVE_TEXT: Record<Tier, { label: string; noun: string; help: string }> = {
  1: { label: 'Tax breaks', noun: 'tax break', help: 'Yearly income-tax deductions for living, moving, renting or buying here.' },
  2: { label: 'Grants', noun: 'grant', help: 'One-off payments for moving here or buying a home.' },
  3: { label: 'Business', noun: 'business incentive', help: 'Exemptions for starting a business or freelance activity here.' },
}

export async function loadIncentives(): Promise<IncentivesData | null> {
  try {
    const r = await fetch(dataUrl('incentives.json'))
    return r.ok ? ((await r.json()) as IncentivesData) : null
  } catch {
    return null
  }
}

/** i1a/i2a/i3a: offers per kind (all ages); i1o/i2o/i3o: open to all ages. */
export function incentiveProps(row: [number, string | null][], offers: Offer[]): Record<string, number> {
  const p: Record<string, number> = {}
  KINDS.forEach((k, i) => {
    const of = row.filter(([, detail]) => !PARTIAL(detail)).map(([o]) => offers[o]).filter((o) => o[1] === k)
    p[`i${i + 1}a`] = of.length
    p[`i${i + 1}o`] = of.filter((o) => !YOUNG_ONLY(o)).length
  })
  return p
}

const COLOURS = ['#e7e5e0', '#9ec5f4', '#3987e5', '#0d366b'] // none, 1, 2, 3+

export function incentiveFill(tier: Tier, young: boolean, nodata: string): ExpressionSpecification {
  const key = `i${tier}${young ? 'a' : 'o'}`
  return ['case', ['!', ['has', key]], nodata,
    ['step', ['get', key], COLOURS[0], 1, COLOURS[1], 2, COLOURS[2], 3, COLOURS[3]]] as unknown as ExpressionSpecification
}

export function incentiveLegend(): [string, string][] {
  return [[COLOURS[0], 'None'], [COLOURS[1], '1 offer'], [COLOURS[2], '2 offers'], [COLOURS[3], '3 or more']]
}

const esc = (s: string) => s.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[c]!)

export function incentiveTooltip(p: Record<string, unknown>, d: IncentivesData | null | undefined, young: boolean, cc: string): string {
  const name = String(p.name ?? '')
  const pop = typeof p.pop === 'number' ? `${p.pop.toLocaleString('en')} inhabitants` : ''
  const head = `<b>${esc(name)}</b>${pop ? `<br><span class="muted">${pop}</span>` : ''}`
  const row = d?.m[String(p.code)] ?? []
  const shown = row.filter(([i]) => young || !YOUNG_ONLY(d!.offers[i]))
  const extra = NOT_COVERED(cc, String(p.code))
    ? `<br><span class="muted">The Basque Country and Navarre have their own tax systems: not covered here</span>`
    : ''
  if (!shown.length) {
    const hidden = row.length - shown.length
    if (extra) return head + extra
    return `${head}<br><span class="muted">No incentive found here${hidden ? ` (${hidden} with an age limit: tick the box)` : ''}</span>`
  }
  const lines = KINDS.map((k, ki) => {
    const items = shown.filter(([i]) => d!.offers[i][1] === k)
    if (!items.length) return ''
    return `<br><b>${INCENTIVE_TEXT[(ki + 1) as Tier].label}</b>` + items.map(([i, detail]) => {
      const o = d!.offers[i]
      const age = o[6] ? ` <span class="muted">(under ${o[6]})</span>` : ''
      return `<br>· ${esc(o[3])}: ${esc(o[4])}${detail ? ` <b>(${esc(detail)})</b>` : ''}${age}` +
        `<br><span class="muted cond">${esc(o[5])}</span>`
    }).join('')
  })
  return head + extra + lines.join('') + `<br><span class="muted">Sources and validity under “How this map is made”</span>`
}

/** Share of people in places under 20,000 with at least one offer of this kind. */
export function incentiveHeadline(d: IncentivesData, tier: Tier, young: boolean, pops: Map<string, number>): string | null {
  let total = 0
  let with_ = 0
  for (const [code, row] of Object.entries(d.m)) {
    const pop = pops.get(code) ?? 0
    if (pop >= 20000) continue
    total += pop
    if (row.some(([i, detail]) => !PARTIAL(detail) && d.offers[i][1] === KINDS[tier - 1] && (young || !YOUNG_ONLY(d.offers[i])))) with_ += pop
  }
  if (!total) return null
  const pct = Math.round((with_ / total) * 100)
  return `<b>${pct}%</b> of the people in places under 20,000 live where there is at least one ${INCENTIVE_TEXT[tier].noun}.`
}

/** Every offer, for the method notes: title, region, amount, conditions, validity and source. */
export function offerList(d: IncentivesData): string {
  return d.offers.map((o) =>
    `<li><b>${esc(o[3])}</b> (${esc(o[2])}; ${o[1] === 'tax' ? 'tax break' : o[1]}): ${esc(o[4])}. ${esc(o[5])}${o[6] ? ` Under ${o[6]}.` : ''} <span class="muted">${esc(o[7])}. ${esc(o[8])}</span></li>`).join('')
}
