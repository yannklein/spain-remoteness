/**
 * Gems: small municipalities that meet the user's thresholds for internet, city, airport and hospital.
 * Pure logic, shared by the map colours, the counts, the list and the tooltip (one judge, no drift).
 * Feature properties come from the other modes: t1..t3 / dt (cities), y1..s3 (airports),
 * hm1..hm3 (hospitals), fd/md (measured download) and fed/med (estimated download).
 */
import type { Tier } from './airports'

export type NetKind = 'fixed' | 'mobile' | 'either'
export interface Limit { tier: Tier; max: number }
export type HomeKind = 'house' | 'flat'
export type IncentiveKind = 'tax' | 'grant' | 'business' | 'any'
export interface PriceLimit { kind: HomeKind; max: number } // €/m² (rent: per month)
export interface GemFilters {
  pop: number | null // largest population a gem may have; null = any size
  net: { kind: NetKind; min: number } | null // minimum download in Mbps; null = criterion off
  est: boolean // count estimates from nearby speed tests
  city: Limit | null
  air: Limit | null
  summer: boolean // count seasonal flights
  hosp: Limit | null
  rent: PriceLimit | null
  buy: PriceLimit | null
  heat: number | null // most days a year at or above 35 °C
  frost: number | null // most frost days a year
  incent: IncentiveKind | null // at least one offer of this kind (open to all ages)
}

export const DEFAULTS: GemFilters = {
  pop: 20000,
  net: { kind: 'fixed', min: 100 },
  est: true,
  city: { tier: 2, max: 60 },
  air: { tier: 2, max: 90 },
  summer: false,
  hosp: { tier: 2, max: 45 },
  rent: null, // off by default: a missing figure fails, which would exclude the smallest villages
  buy: null,
  heat: null,
  frost: null,
  incent: null,
}

export const POP_CHOICES = [1000, 2000, 5000, 10000, 20000, 50000]
export const NET_CHOICES = [10, 25, 50, 100, 300]
export const TIME_CHOICES = [30, 45, 60, 90, 120, 150, 180]
export const HOSP_TIME_CHOICES = [15, 30, 45, 60, 90, 120, 180]
export const RENT_CHOICES = [4, 5, 6, 7, 8, 9, 10, 12, 15]
export const BUY_CHOICES = [500, 750, 1000, 1250, 1500, 2000, 2500, 3000, 4000]
export const HEAT_CHOICES = [1, 3, 5, 10, 20, 30, 50]
export const FROST_CHOICES = [1, 5, 10, 20, 40, 60, 90]

export type Crit = 'net' | 'city' | 'air' | 'hosp' | 'rent' | 'buy' | 'heat' | 'frost' | 'incent'
/** scope (housing): 0 own figure, 1 nearby estimate, 2 province average, 3 area model */
export interface Check { crit: Crit; value: number | null; ok: boolean; est?: boolean; scope?: number }
/** 0 other, 1 near miss (exactly one criterion missed), 2 gem, 3 too big to be a gem. */
export type GemClass = 0 | 1 | 2 | 3
export interface Verdict { cls: GemClass; checks: Check[] }

const num = (v: unknown): number | null => (typeof v === 'number' && v >= 0 ? v : null)

/** Download in Mbps for one connection kind: measured, else (if allowed) the estimate. */
function download(p: Record<string, unknown>, k: 'f' | 'm', est: boolean): { v: number | null; est: boolean } {
  const measured = num(p[`${k}d`])
  if (measured !== null) return { v: measured, est: false }
  const e = est ? num(p[`${k}ed`]) : null
  return { v: e, est: e !== null }
}

function days(value: number | null, max: number, crit: Crit): Check {
  return { crit, value, ok: value !== null && value <= max }
}

function minutes(value: number | null, max: number, crit: Crit): Check {
  return { crit, value, ok: value !== null && value <= max }
}

export function judge(p: Record<string, unknown>, f: GemFilters): Verdict {
  const checks: Check[] = []
  if (f.net) {
    const fixed = download(p, 'f', f.est)
    const mobile = download(p, 'm', f.est)
    const pick =
      f.net.kind === 'fixed' ? fixed
        : f.net.kind === 'mobile' ? mobile
          : (mobile.v ?? -1) > (fixed.v ?? -1) ? mobile : fixed
    checks.push({ crit: 'net', value: pick.v, ok: pick.v !== null && pick.v >= f.net.min, ...(pick.est ? { est: true } : {}) })
  }
  if (f.city) {
    const dt = num(p.dt) ?? 0
    // a place that is itself a city of the chosen tier is there already
    checks.push(minutes(dt > 0 && dt <= f.city.tier ? 0 : num(p[`t${f.city.tier}`]), f.city.max, 'city'))
  }
  if (f.air) checks.push(minutes(num(p[`${f.summer ? 's' : 'y'}${f.air.tier}`]), f.air.max, 'air'))
  if (f.hosp) checks.push(minutes(num(p[`hm${f.hosp.tier}`]), f.hosp.max, 'hosp'))
  for (const crit of ['rent', 'buy'] as const) {
    const l = f[crit]
    if (!l) continue
    const key = `${crit === 'rent' ? 'r' : 'b'}${l.kind === 'flat' ? 'f' : 'h'}`
    const value = num(p[key])
    const scope = num(p[`s${key}`])
    checks.push({ crit, value, ok: value !== null && value <= l.max, ...(scope !== null ? { scope } : {}) })
  }
  if (f.heat !== null) checks.push(days(num(p.ch), f.heat, 'heat'))
  if (f.frost !== null) checks.push(days(num(p.cf), f.frost, 'frost'))
  if (f.incent !== null) {
    // i1o/i2o/i3o: tax breaks, grants, business offers open to all ages
    const counts = [num(p.i1o), num(p.i2o), num(p.i3o)]
    const pick = f.incent === 'any' ? counts : [counts[{ tax: 0, grant: 1, business: 2 }[f.incent]]]
    const value = pick.some((c) => c === null) ? null : pick.reduce((a: number, b) => a + (b as number), 0)
    checks.push({ crit: 'incent', value, ok: value !== null && value >= 1 })
  }

  const pop = num(p.pop)
  if (f.pop !== null && pop !== null && pop > f.pop) return { cls: 3, checks }
  const fails = checks.filter((c) => !c.ok).length
  return { cls: fails === 0 ? 2 : fails === 1 ? 1 : 0, checks }
}

const limitText = (l: Limit | null) => (l ? `${l.tier}:${l.max}` : 'off')

/** Query part of the hash: "pop=20000&net=fixed:100&est=1&city=2:60&air=2:90&summer=0&hosp=2:45". */
export function formatHash(f: GemFilters): string {
  return [
    `pop=${f.pop ?? 'any'}`,
    `net=${f.net ? `${f.net.kind}:${f.net.min}` : 'off'}`,
    `est=${f.est ? 1 : 0}`,
    `city=${limitText(f.city)}`,
    `air=${limitText(f.air)}`,
    `summer=${f.summer ? 1 : 0}`,
    `hosp=${limitText(f.hosp)}`,
    `rent=${f.rent ? `${f.rent.kind}:${f.rent.max}` : 'off'}`,
    `buy=${f.buy ? `${f.buy.kind}:${f.buy.max}` : 'off'}`,
    `heat=${f.heat ?? 'off'}`,
    `frost=${f.frost ?? 'off'}`,
    `incent=${f.incent ?? 'off'}`,
  ].join('&')
}

const positive = (s: string | undefined): number | null => {
  const n = Number(s)
  return s && Number.isFinite(n) && n > 0 ? n : null
}

function parseLimit(s: string | null, fallback: Limit | null): Limit | null {
  if (s === null) return fallback
  if (s === 'off') return null
  const [t, m] = s.split(':')
  const tier = Number(t)
  const max = positive(m)
  return (tier === 1 || tier === 2 || tier === 3) && max !== null ? { tier, max } : fallback
}

const parseBool = (s: string | null, fallback: boolean) => (s === '1' ? true : s === '0' ? false : fallback)

function parseIncent(s: string | null, fallback: IncentiveKind | null): IncentiveKind | null {
  if (s === null) return fallback
  if (s === 'off') return null
  return s === 'tax' || s === 'grant' || s === 'business' || s === 'any' ? s : fallback
}

function parseDays(s: string | null, fallback: number | null): number | null {
  if (s === null) return fallback
  if (s === 'off') return null
  return positive(s) ?? fallback
}

function parsePrice(s: string | null, fallback: PriceLimit | null): PriceLimit | null {
  if (s === null) return fallback
  if (s === 'off') return null
  const [kind, m] = s.split(':')
  const max = positive(m)
  return (kind === 'house' || kind === 'flat') && max !== null ? { kind, max } : fallback
}

/** Settings from the hash query; anything missing or unreadable keeps its default. */
export function parseHash(query: string): GemFilters {
  const q = new URLSearchParams(query)
  const d = DEFAULTS
  const popS = q.get('pop')
  const pop = popS === null ? d.pop : popS === 'any' ? null : positive(popS) ?? d.pop
  let net = d.net
  const netS = q.get('net')
  if (netS === 'off') net = null
  else if (netS) {
    const [kind, min] = netS.split(':')
    const m = positive(min)
    if ((kind === 'fixed' || kind === 'mobile' || kind === 'either') && m !== null) net = { kind, min: m }
  }
  return {
    pop,
    net,
    est: parseBool(q.get('est'), d.est),
    city: parseLimit(q.get('city'), d.city),
    air: parseLimit(q.get('air'), d.air),
    summer: parseBool(q.get('summer'), d.summer),
    hosp: parseLimit(q.get('hosp'), d.hosp),
    rent: parsePrice(q.get('rent'), d.rent),
    buy: parsePrice(q.get('buy'), d.buy),
    heat: parseDays(q.get('heat'), d.heat),
    frost: parseDays(q.get('frost'), d.frost),
    incent: parseIncent(q.get('incent'), d.incent),
  }
}
