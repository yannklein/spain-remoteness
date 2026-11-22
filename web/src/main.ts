import maplibregl, { type ExpressionSpecification, type StyleSpecification } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { feature } from 'topojson-client'
import type { Topology, GeometryCollection } from 'topojson-specification'
import type { FeatureCollection, Geometry } from 'geojson'
import './style.css'
import {
  AIRPORT_TEXT,
  airportCounts,
  airportHeadline,
  airportMarkers,
  airportProps,
  airportTooltip,
  loadAirports,
  type AirportsData,
  type Tier,
} from './airports'
import {
  METRICS,
  internetFill,
  internetHeadline,
  internetEstimateFilter,
  hatchImage,
  POP as INTERNET_POP,
  internetLegend,
  internetProps,
  internetTooltip,
  loadInternet,
  type InternetData,
} from './internet'
import {
  HOSPITAL_TEXT,
  hospitalCounts,
  hospitalHeadline,
  hospitalMarkers,
  hospitalProps,
  hospitalTooltip,
  loadHospitals,
  type HospitalsData,
} from './hospitals'
import {
  HOUSING_TEXT,
  SCOPE_TEXT,
  housingEstimateFilter,
  housingFill,
  housingHeadline,
  housingLegend,
  housingProps,
  housingTooltip,
  loadHousing,
  type HousingData,
} from './housing'
import { dataUrl, setDataCountry, viaText, withCountry, type Country, type Gateway } from './country'
import {
  DEFAULTS as GEM_DEFAULTS,
  BUY_CHOICES,
  HOSP_TIME_CHOICES,
  RENT_CHOICES,
  NET_CHOICES,
  POP_CHOICES,
  TIME_CHOICES,
  formatHash,
  judge,
  parseHash,
  type Check,
  type GemFilters,
  type HomeKind,
  type Limit,
  type PriceLimit,
  type NetKind,
} from './gems'

type Mode = 'cities' | 'airports' | 'internet' | 'hospitals' | 'housing' | 'gems'

// [code, name, tier, lat, lng, metro, population]
type City = [string, string, number, number, number, string | null, number | null]

interface Remoteness {
  generated_at: string
  params: { arrival: string; endpoint: string; max_minutes: number; population_year: number | null; notes: string[] }
  cities: City[] // codes: INE/INSEE, or "PT:porto" for a city abroad
  gateways?: Gateway[] // border stations estimates go through
  // code -> [t1, c1, t2, c2, t3, c3, urban (any tier), population, via]; t = minutes, -1 = over the cap;
  // via: null, or the gateway index per tier (-1 = measured)
  m: Record<string, [number, number, number, number, number, number, 0 | 1, number | null, number[] | null]>
}

// Sequential blue ramp (light = close, dark = remote): 7 bins of 30 min.
const BINS = [30, 60, 90, 120, 150, 180]
const COLORS = ['#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#184f95', '#0d366b']
const URBAN = '#b9b7b1'
const NODATA = '#ecebe8'

type TierText = Record<Tier, { label: string; noun: string; help: string }>

const CITY_TEXT: Record<Country, TierText> = {
  es: {
    1: { label: 'Metros', noun: 'metro', help: 'Madrid, Barcelona, València, Sevilla, Zaragoza, Málaga.' },
    2: { label: 'Regional hubs', noun: 'regional hub', help: 'Provincial and regional capitals plus every city over 100k.' },
    3: { label: 'All urban', noun: 'urban area', help: 'Regional hubs plus every municipality over 50k.' },
  },
  fr: {
    1: { label: 'Métropoles', noun: 'métropole', help: 'The central communes of the 22 métropoles (Paris, Lyon, Marseille, Toulouse…).' },
    2: { label: 'Hubs', noun: 'regional hub', help: 'Métropoles plus every préfecture and every commune over 100k.' },
    3: { label: 'All urban', noun: 'urban area', help: 'Regional hubs plus every commune over 50k.' },
  },
}

/** France counts only hospitals with a general emergency department (DREES SAE). */
const HOSPITAL_TEXT_FR: TierText = {
  1: { label: 'Major', noun: 'a major hospital', help: 'University and regional hospitals (CHU/CHR) with an emergency department.' },
  2: { label: 'Public', noun: 'a public hospital', help: 'Public hospitals with a 24 h emergency department.' },
  3: { label: 'Any', noun: 'a hospital', help: 'Any hospital with an emergency department, private clinics included.' },
}

const COUNTRY_NAME: Record<Country, string> = { es: 'Spain', fr: 'France' }

function title(m: Mode): string {
  const where = `rural ${COUNTRY_NAME[country]}`
  return {
    cities: `How far is ${where} from a city?`,
    airports: `How far is ${where} from an airport?`,
    internet: `How good is the internet in ${where}?`,
    hospitals: `How far is ${where} from a hospital?`,
    housing: `What does housing cost in ${where}?`,
    gems: `Where could you live and work remotely in ${where}?`,
  }[m]
}
const INTERNET_NODATA = '#c4c2bc'

type Bounds = [[number, number], [number, number]]
const VIEWS: Record<Country, { id: string; label: string; bounds: Bounds }[]> = {
  es: [
    { id: 'peninsula', label: 'Peninsula', bounds: [[-9.6, 35.8], [4.5, 43.9]] },
    { id: 'canarias', label: 'Canarias', bounds: [[-18.3, 27.5], [-13.3, 29.5]] },
    { id: 'baleares', label: 'Balears', bounds: [[1.1, 38.6], [4.4, 40.2]] },
  ],
  fr: [
    { id: 'metropole', label: 'Métropole', bounds: [[-5.3, 41.3], [9.6, 51.15]] },
    { id: 'corse', label: 'Corse', bounds: [[8.5, 41.3], [9.6, 43.1]] },
  ],
}

const BASE_STYLE = 'https://tiles.openfreemap.org/styles/positron'
const FALLBACK_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#f6f5f2' } }],
}

const $ = <T extends HTMLElement>(sel: string) => document.querySelector(sel) as T

const MODES: Mode[] = ['cities', 'airports', 'internet', 'hospitals', 'housing', 'gems']
// hash: "#fr/hospitals", "#es/airports", "#fr/gems?pop=20000&…"; old links ("#airports") mean Spain
const [hashPath, hashQuery = ''] = location.hash.slice(1).split('?')
const [hashCountry, hashMode] = hashPath.includes('/') ? hashPath.split('/') : ['es', hashPath]
let country: Country = hashCountry === 'fr' ? 'fr' : 'es'
setDataCountry(country)
let mode: Mode = MODES.find((m) => m === hashMode) ?? 'cities'
const tiers: Record<Mode, Tier> = { cities: 2, airports: 2, internet: 1, hospitals: 2, housing: 1, gems: 2 }
let gemFilters: GemFilters = mode === 'gems' ? parseHash(hashQuery) : { ...GEM_DEFAULTS }
let tier: Tier = tiers[mode]
let summer = false
let data: Remoteness | null = null
let airports: AirportsData | null | undefined // undefined = not loaded yet
let internet: InternetData | null | undefined
let hospitals: HospitalsData | null | undefined
let housing: HousingData | null | undefined
let flats = false
const muniNames = new Map<string, string>()
let mobile = false
let geo: FeatureCollection<Geometry, Record<string, unknown>> | null = null
// Country switches are slow (France: ~35k communes). gen identifies the current switch; anything
// loaded for an older one is dropped, and nothing merges while `loading` is true.
let gen = 0
let loading = false
let provincesGeo: FeatureCollection | null = null

function fmtMinutes(t: number, max = 180): string {
  if (t < 0) return `over ${max / 60} h (or no service)`
  if (t < 60) return `${t} min`
  const h = Math.floor(t / 60)
  const m = t % 60
  return m ? `${h} h ${String(m).padStart(2, '0')}` : `${h} h`
}

/** Feature property holding the minutes shown for the current mode, tier and variant. */
function valueKey(): string {
  if (mode === 'hospitals') return `hm${tier}`
  return mode === 'cities' ? `t${tier}` : `${summer ? 's' : 'y'}${tier}`
}

/** Feature property set where the shown time is an estimate through a border station. */
function viaKey(): string | null {
  if (mode === 'cities') return `v${tier}`
  if (mode === 'airports') return `v${summer ? 's' : 'y'}${tier}`
  return null
}

/** Hatch layer on top of municipalities whose value is an estimate (internet: nearby tests; cities and
 * airports: through a border station). */
function applyEstimateLayer(map: maplibregl.Map) {
  if (!map.getLayer('muni-est')) return
  const via = viaKey()
  const on = mode === 'internet' || mode === 'housing' || via !== null
  map.setLayoutProperty('muni-est', 'visibility', on ? 'visible' : 'none')
  if (mode === 'internet') map.setFilter('muni-est', internetEstimateFilter(tier, mobile))
  else if (mode === 'housing') map.setFilter('muni-est', housingEstimateFilter(tier, flats))
  else if (via) {
    // a main city of the tier is grey, never hatched
    const notCity: ExpressionSpecification = mode === 'cities'
      ? ['!', ['all', ['>', ['get', 'dt'], 0], ['<=', ['get', 'dt'], tier]]]
      : ['literal', true]
    map.setFilter('muni-est', ['all', ['has', via], notCity] as ExpressionSpecification)
  }
}

const GEM_COLORS = { gem: '#d99a00', near: '#f2d27e', other: '#f1f0ec', big: URBAN }

function currentFill(): ExpressionSpecification {
  if (mode === 'gems') {
    return ['match', ['coalesce', ['feature-state', 'gem'], -1],
      2, GEM_COLORS.gem, 1, GEM_COLORS.near, 0, GEM_COLORS.other, 3, GEM_COLORS.big, NODATA] as ExpressionSpecification
  }
  if (mode === 'internet') return internetFill(tier, mobile, COLORS.slice(1), INTERNET_NODATA)
  if (mode === 'housing') return housingFill(tier, flats, COLORS.slice(1), INTERNET_NODATA)
  return fillColor(valueKey(), mode === 'cities' ? tier : null)
}

/** Colour by minutes in `key`; municipalities that are a city of tier <= greyTier are grey. */
function fillColor(key: string, greyTier: Tier | null): ExpressionSpecification {
  const steps: (number | string)[] = [COLORS[0]]
  BINS.slice(0, -1).forEach((b, i) => steps.push(b, COLORS[i + 1]))
  return [
    'case',
    ['all', ['>', ['get', 'dt'], 0], ['<=', ['get', 'dt'], greyTier ?? 0]], URBAN,
    ['!', ['has', key]], NODATA,
    ['<', ['get', key], 0], COLORS[6],
    ['step', ['get', key], ...steps] as unknown as ExpressionSpecification,
  ] as ExpressionSpecification
}

async function loadStyle(): Promise<StyleSpecification | string> {
  try {
    const r = await fetch(BASE_STYLE, { signal: AbortSignal.timeout(6000) })
    if (r.ok) return BASE_STYLE
  } catch {
    /* offline or blocked: plain background */
  }
  return FALLBACK_STYLE
}

async function loadData() {
  const topo = (await (await fetch(dataUrl('municipalities.topo.json'))).json()) as Topology
  const g = feature(topo, topo.objects.municipalities as GeometryCollection) as FeatureCollection<
    Geometry,
    Record<string, unknown>
  >
  const provinces = feature(topo, topo.objects.provinces as GeometryCollection)

  let cities: Remoteness | null = null
  try {
    const r = await fetch(dataUrl('remoteness.json'))
    if (r.ok) cities = (await r.json()) as Remoteness
  } catch {
    cities = null
  }

  // tier in which each municipality counts as a main city (tiers are nested)
  const cityTier = new Map((cities?.cities ?? []).map((c) => [c[0], c[2]]))
  const names = new Map<string, string>()
  for (const f of g.features) {
    const code = String(f.id)
    const p: Record<string, unknown> = { code, name: f.properties?.name }
    const row = cities?.m[code]
    if (row) {
      ;[p.t1, p.c1, p.t2, p.c2, p.t3, p.c3, , p.pop] = row
      row[8]?.forEach((g, i) => {
        if (g >= 0) p[`v${i + 1}`] = g // estimate through a border station
      })
    }
    p.dt = cityTier.get(code) ?? 0
    f.properties = p
    names.set(code, String(p.name ?? ''))
  }
  return { geo: g, provinces, cities, names }
}

/** Load hospitals.json once and merge its values into the municipality features. */
async function ensureHospitals(map: maplibregl.Map) {
  if (hospitals !== undefined || loading) return
  const g = gen
  const got = await loadHospitals()
  if (g !== gen || loading) return // the country changed meanwhile: these values belong to the other one
  hospitals = got
  if (!hospitals || !geo) return
  for (const f of geo.features) {
    const row = hospitals.m[String(f.id)]
    if (row) Object.assign(f.properties, hospitalProps(row))
  }
  ;(map.getSource('munis') as maplibregl.GeoJSONSource | undefined)?.setData(geo)
}

async function ensureAirports(map: maplibregl.Map) {
  if (airports !== undefined || loading) return
  const g = gen
  const got = await loadAirports()
  if (g !== gen || loading) return // the country changed meanwhile: these values belong to the other one
  airports = got
  if (!airports || !geo) return
  for (const f of geo.features) {
    const row = airports.m[String(f.id)]
    if (row) Object.assign(f.properties, airportProps(row))
  }
  const src = map.getSource('munis') as maplibregl.GeoJSONSource | undefined
  src?.setData(geo)
}

/** Load housing.json once and merge its values into the municipality features. */
async function ensureHousing(map: maplibregl.Map) {
  if (housing !== undefined || loading) return
  const g = gen
  const got = await loadHousing()
  if (g !== gen || loading) return // the country changed meanwhile: these values belong to the other one
  housing = got
  if (!housing || !geo) return
  for (const f of geo.features) {
    const row = housing.m[String(f.id)]
    if (row) Object.assign(f.properties, housingProps(row))
  }
  ;(map.getSource('munis') as maplibregl.GeoJSONSource | undefined)?.setData(geo)
}

/** Load internet.json once and merge its values into the municipality features. */
async function ensureInternet(map: maplibregl.Map) {
  if (internet !== undefined || loading) return
  const g = gen
  const got = await loadInternet()
  if (g !== gen || loading) return // the country changed meanwhile: these values belong to the other one
  internet = got
  if (!internet || !geo) return
  for (const f of geo.features) {
    const row = internet.m[String(f.id)]
    if (!row) continue
    Object.assign(f.properties, internetProps(row))
    if (f.properties.pop == null && typeof row[INTERNET_POP] === 'number') f.properties.pop = row[INTERNET_POP]
  }
  ;(map.getSource('munis') as maplibregl.GeoJSONSource | undefined)?.setData(geo)
}

function destGeoJSON(): FeatureCollection {
  if (mode === 'internet' || mode === 'gems' || mode === 'housing') return { type: 'FeatureCollection', features: [] }
  if (mode === 'hospitals') return hospitals ? hospitalMarkers(hospitals, tier) : { type: 'FeatureCollection', features: [] }
  if (mode === 'airports') return airports ? airportMarkers(airports, tier, summer) : { type: 'FeatureCollection', features: [] }
  return cityGeoJSON(tier)
}

function cityGeoJSON(t: Tier): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: (data?.cities ?? [])
      .filter((c) => c[2] <= t)
      .map((c) => ({
        type: 'Feature',
        properties: { name: c[1], tier: c[2], metro: c[5] ?? '' },
        geometry: { type: 'Point', coordinates: [c[4], c[3]] },
      })),
  }
}

/** Share of the population living outside this tier's cities that is beyond 60 min. */
function headline(t: Tier): string | null {
  if (!data) return null
  const idx = (t - 1) * 2
  let total = 0
  let far = 0
  let usesPop = true
  const tierOf = new Map(data.cities.map((c) => [c[0], c[2]]))
  const rows = Object.entries(data.m)
    .filter(([code]) => !((tierOf.get(code) ?? 99) <= t))
    .map(([, r]) => r)
  if (rows.every((r) => r[7] == null)) usesPop = false
  for (const r of rows) {
    const w = usesPop ? (r[7] ?? 0) : 1
    total += w
    const tt = r[idx] as number
    if (tt < 0 || tt > 60) far += w
  }
  if (!total) return null
  const pct = Math.round((far / total) * 100)
  const n = data.cities.filter((c) => c[2] <= t).length
  const who = usesPop ? `of people living outside these ${n} cities` : 'of the other municipalities'
  return `<b>${pct}%</b> ${who} are more than <b>1 hour</b> by public transport from a ${CITY_TEXT[country][t].noun}.`
}

function renderLegend() {
  const item = (c: string, l: string) => `<div><i style="background:${c}"></i>${l}</div>`
  if (mode === 'internet') {
    const labels = internetLegend(tier)
    $('#legend').innerHTML =
      COLORS.slice(1).map((c, i) => item(c, labels[i])).join('') +
      item(INTERNET_NODATA, 'Not enough speed tests') +
      `<div class="wide"><i class="hatched" style="background-color:${COLORS[3]}"></i>Hatched: estimated from speed tests within ${internet?.params.estimate_radius_km ?? 10} km</div>`
    return
  }
  if (mode === 'housing') {
    const labels = housingLegend(tier)
    $('#legend').innerHTML =
      COLORS.slice(1).map((c, i) => item(c, labels[i])).join('') +
      item(INTERNET_NODATA, 'No figure') +
      `<div class="wide"><i class="hatched" style="background-color:${COLORS[3]}"></i>Hatched: not the place's own figure (nearby, area or province estimate)</div>`
    return
  }
  if (mode === 'gems') {
    $('#legend').innerHTML =
      item(GEM_COLORS.gem, 'Gem: meets everything') + item(GEM_COLORS.near, 'Near miss: one short') +
      item(GEM_COLORS.other, 'Misses two or more') + item(GEM_COLORS.big, 'Over the size limit')
    return
  }
  const labels = ['< 30 min', '30–60', '60–90', '90 min–2 h', '2 h–2 h 30', '2 h 30–3 h', '3 h+ / no service']
  const gateways = mode === 'cities' ? data?.gateways : mode === 'airports' ? airports?.gateways : undefined
  $('#legend').innerHTML =
    COLORS.map((c, i) => item(c, labels[i])).join('') +
    (mode === 'cities' ? item(URBAN, 'City of the selected tier') : '') +
    (gateways?.length
      ? `<div class="wide"><i class="hatched" style="background-color:${COLORS[3]}"></i>Hatched: across the border, estimated through a border station</div>`
      : '')
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

/** Everything in the panel and on the map that depends on mode, tier and the seasonal checkbox. */
function refresh(map: maplibregl.Map) {
  const panel = $('#panel')
  panel.dataset.mode = mode
  document.querySelectorAll<HTMLButtonElement>('.modes button').forEach((b) => {
    b.setAttribute('aria-checked', String(b.dataset.mode === mode))
  })
  document.querySelectorAll<HTMLElement>('[data-for]').forEach((el) => {
    el.hidden = el.dataset.for !== mode || (el.dataset.country ?? country) !== country
  })
  $('#title').textContent = title(mode)
  document.title = title(mode)
  panel.dataset.country = country
  document.querySelectorAll<HTMLButtonElement>('.countries button').forEach((b) => {
    b.setAttribute('aria-checked', String(b.dataset.country === country))
  })
  const text = {
    cities: CITY_TEXT[country],
    airports: AIRPORT_TEXT,
    internet: METRICS,
    hospitals: country === 'fr' ? HOSPITAL_TEXT_FR : HOSPITAL_TEXT,
    housing: HOUSING_TEXT,
    gems: CITY_TEXT[country],
  }[mode]
  const counts: (number | null)[] =
    mode === 'cities'
      ? [1, 2, 3].map((t) => (data ? data.cities.filter((c) => c[2] <= t).length : null))
      : mode === 'airports' && airports
        ? airportCounts(airports, summer)
        : mode === 'hospitals' && hospitals
          ? hospitalCounts(hospitals)
          : [null, null, null]
  document.querySelectorAll<HTMLButtonElement>('.tiers button').forEach((b) => {
    const t = Number(b.dataset.tier) as Tier
    b.setAttribute('aria-checked', String(t === tier))
    b.querySelector('.tl')!.textContent = text[t].label
    b.querySelector('.n')!.textContent = counts[t - 1] == null ? '' : String(counts[t - 1])
  })
  $('#summer-wrap').hidden = mode !== 'airports'
  $('#summer-note').textContent =
    country === 'fr' ? '(summer-only, or winter-only ski routes)' : '(summer-only, or winter-only in Canarias)'
  $('#mobile-wrap').hidden = mode !== 'internet'
  // Spain's price to buy covers any home: the flats switch would change nothing there
  $('#flats-wrap').hidden = mode !== 'housing' || (tier === 2 && !!housing?.params.buy_all_dwellings)
  const noun = `<strong>${text[tier].noun.replace(/^an? /, '')}</strong>`
  $('#lead').innerHTML =
    mode === 'gems'
      ? 'Small places that meet <strong>all</strong> your needs (gold) or miss just one (pale). Tune the thresholds below.'
      : mode === 'housing'
      ? country === 'es'
        ? tier === 1
          ? 'Median <strong>rent</strong> per m² a month from declared leases (Ministry of Housing).'
          : 'Appraisal <strong>price</strong> per m²: towns over 25,000 have their own; villages show their province average (hatched).'
        : tier === 1
          ? 'Advertised <strong>rent</strong> per m² a month, charges included (ANIL rent map 2025).'
          : 'Median <strong>price</strong> per m² of sales over the last 5 years (DVF).'
      : mode === 'internet'
      ? `Average ${noun}${tier === 3 ? '' : ' speed'} per municipality from Speedtest by Ookla, measured locally or estimated from nearby tests (hatched), last 4 quarters.`
      : `Public transport time from each municipality to the nearest ${noun}, best connection of a weekday.`
  $('#tier-help').textContent = text[tier].help

  if (mode === 'gems') renderGemControls()
  // gems need all four datasets: judging before they arrive would show wrong counts
  const gemsLoading = mode === 'gems' && [airports, internet, hospitals, housing].some((x) => x === undefined)
  const gemResult = mode === 'gems' && geo && !loading && !gemsLoading ? computeGems() : null
  const h =
    mode === 'gems'
      ? gemResult && gemHeadline(gemResult)
      : mode === 'housing'
        ? housing ? housingHeadline(housing, tier, flats) : null
      : mode === 'cities'
      ? headline(tier)
      : mode === 'airports'
        ? airports ? airportHeadline(airports, tier, summer) : null
        : mode === 'hospitals'
          ? hospitals ? hospitalHeadline(hospitals, tier) : null
          : internet ? internetHeadline(internet, tier, mobile) : null
  const el = $('#headline')
  el.hidden = !h
  if (h) el.innerHTML = h

  const s = $('#status')
  if (loading || gemsLoading) {
    s.hidden = false
    s.textContent = `Loading ${COUNTRY_NAME[country]}…`
    $('#headline').hidden = true
    $('#gems-list').innerHTML = ''
    renderLegend()
    return
  }
  const gemsMissing = [
    !data && 'cities', airports === null && 'airports', internet === null && 'internet', hospitals === null && 'hospitals',
    housing === null && 'housing',
  ].filter(Boolean)
  const missing = {
    cities: !data, airports: airports === null, internet: internet === null, hospitals: hospitals === null,
    housing: housing === null, gems: gemsMissing.length > 0,
  }[mode]
  s.hidden = !missing
  s.innerHTML = {
    cities: 'Travel times have not been computed yet. Run <code>python3 pipeline/compute_times.py</code>.',
    airports: 'Airport travel times have not been computed yet. Run <code>python3 pipeline/compute_airports.py</code>.',
    internet: 'Internet speeds have not been computed yet. Run <code>python3 pipeline/compute_internet.py</code>.',
    hospitals: 'Hospital travel times have not been computed yet. Run <code>python3 pipeline/compute_hospitals.py</code>.',
    housing: 'Housing prices have not been computed yet. Run <code>python3 pipeline/compute_housing.py</code>.',
    gems: `Missing data (${gemsMissing.join(', ')}): those criteria fail everywhere.`,
  }[mode]

  const meta = $('#meta')
  if (mode === 'cities' && data) {
    meta.textContent =
      `Computed ${fmtDate(data.generated_at)} · ${data.cities.length} cities · ${data.params.endpoint} endpoint` +
      (data.params.population_year ? ` · population ${data.params.population_year}` : '') +
      (data.params.notes.length ? ` · ${data.params.notes.join('; ')}` : '')
  } else if (mode === 'airports' && airports) {
    meta.textContent =
      `Computed ${fmtDate(airports.generated_at)} · ${airports.airports.length} airports` +
      (airports.params.population_year ? ` · population ${airports.params.population_year}` : '')
    $('#airport-notes').innerHTML = airports.params.notes.map((n) => `<li>${n}</li>`).join('')
  } else if (mode === 'hospitals' && hospitals) {
    meta.textContent =
      `Computed ${fmtDate(hospitals.generated_at)} · ${hospitals.hospitals.length} hospitals · ${hospitals.params.source}` +
      (hospitals.params.population_year ? ` · population ${hospitals.params.population_year}` : '')
    $('#hospital-notes').innerHTML = hospitals.params.notes.map((n) => `<li>${n}</li>`).join('')
  } else if (mode === 'housing' && housing) {
    meta.textContent = `Computed ${fmtDate(housing.generated_at)} · ${housing.params.sources.join(' · ')}`
  } else if (mode === 'internet' && internet) {
    const q = internet.params.quarters
    const n = Object.values(internet.m).filter((r) => typeof r[mobile ? 5 : 0] === 'number').length
    const e = Object.values(internet.m).filter((r) => typeof r[mobile ? 14 : 10] === 'number').length
    meta.textContent =
      `Speed tests ${q[0]} to ${q[q.length - 1]} · ${n.toLocaleString('en')} municipalities measured, ` +
      `${e.toLocaleString('en')} estimated (${mobile ? 'mobile' : 'fixed'}) · official coverage ${internet.params.coverage?.year ?? ''}`
    $('#internet-period').textContent = `${q[0]} to ${q[q.length - 1]}`
    $('#internet-licence').textContent = internet.params.licence
  } else {
    meta.textContent = ''
  }

  renderLegend()
  renderGemList(map, gemResult)
  if (map.getLayer('muni-fill')) {
    if (gemResult) paintGems(map, gemResult)
    map.setPaintProperty('muni-fill', 'fill-color', currentFill())
    applyEstimateLayer(map)
    ;(map.getSource('dests') as maplibregl.GeoJSONSource).setData(destGeoJSON())
  }
  hideTooltip()
}

// ---- gems ---------------------------------------------------------------------------------

interface GemResult { cls: Map<string, number>; gems: number; near: number; small: number; list: { code: string; name: string; net: number | null }[] }

/** Judge every municipality of the current country with the current filters. */
function computeGems(): GemResult {
  const res: GemResult = { cls: new Map(), gems: 0, near: 0, small: 0, list: [] }
  for (const f of geo!.features) {
    const code = String(f.id)
    const v = judge(f.properties, gemFilters)
    res.cls.set(code, v.cls)
    if (v.cls === 3) continue
    res.small++
    if (v.cls === 1) res.near++
    if (v.cls === 2) {
      res.gems++
      res.list.push({ code, name: String(f.properties.name ?? ''), net: v.checks.find((c) => c.crit === 'net')?.value ?? null })
    }
  }
  res.list.sort((a, b) => (b.net ?? -1) - (a.net ?? -1) || a.name.localeCompare(b.name))
  return res
}

/** Colour through feature-state, so the map shows exactly what computeGems counted. */
let painted: { geo: unknown; cls: Map<string, number> } | null = null
function paintGems(map: maplibregl.Map, r: GemResult) {
  // only the places whose class changed; everything after a country switch (new features)
  const prev = painted && painted.geo === geo ? painted.cls : null
  if (!prev) map.removeFeatureState({ source: 'munis' })
  r.cls.forEach((cls, id) => {
    if (prev?.get(id) !== cls) map.setFeatureState({ source: 'munis', id }, { gem: cls })
  })
  painted = { geo, cls: r.cls }
}

function gemHeadline(r: GemResult): string {
  const n = (x: number) => x.toLocaleString('en')
  const places = country === 'fr' ? 'communes' : 'municipalities'
  const among = gemFilters.pop === null
    ? `all ${n(r.small)} ${places}`
    : `the ${n(r.small)} ${places} under ${n(gemFilters.pop)} inhabitants`
  return `<b>${n(r.gems)}</b> gems and <b>${n(r.near)}</b> near misses among ${among}.`
}

function renderGemList(map: maplibregl.Map, r: GemResult | null) {
  const box = $('#gems-list')
  if (!r || !r.gems) {
    box.innerHTML = r ? '<p class="more">No gem with these settings: loosen a threshold.</p>' : ''
    return
  }
  const shown = r.list.slice(0, 100)
  box.innerHTML =
    `<h2>Gems${gemFilters.net ? ', fastest internet first' : ''}</h2><ol>` +
    shown.map((g) => `<li><button type="button" data-code="${g.code}"><span>${g.name}</span>${g.net !== null ? `<span class="muted">${Math.round(g.net)} Mbps</span>` : ''}</button></li>`).join('') +
    '</ol>' +
    (r.list.length > shown.length ? `<p class="more">and ${(r.list.length - shown.length).toLocaleString('en')} more on the map</p>` : '')
  box.querySelectorAll<HTMLButtonElement>('li button').forEach((b) => b.addEventListener('click', () => zoomTo(map, b.dataset.code!)))
}

function zoomTo(map: maplibregl.Map, code: string) {
  const f = geo?.features.find((x) => String(x.id) === code)
  if (!f) return
  let [w, s, e, n] = [180, 90, -180, -90]
  const walk = (c: unknown): void => {
    if (typeof (c as number[])[0] === 'number') {
      const [x, y] = c as number[]
      w = Math.min(w, x); e = Math.max(e, x); s = Math.min(s, y); n = Math.max(n, y)
    } else (c as unknown[]).forEach(walk)
  }
  walk((f.geometry as { coordinates: unknown }).coordinates)
  map.fitBounds([[w, s], [e, n]], { padding: panelPadding(), maxZoom: 11 })
}

const GEM_TIER_TEXT = () => ({
  city: CITY_TEXT[country],
  air: AIRPORT_TEXT,
  hosp: country === 'fr' ? HOSPITAL_TEXT_FR : HOSPITAL_TEXT,
})

function options(sel: HTMLSelectElement, items: [string, string][], value: string) {
  sel.innerHTML = items.map(([v, l]) => `<option value="${v}">${l}</option>`).join('')
  sel.value = items.some(([v]) => v === value) ? value : items[0][0]
}

/** Fill the gem controls from gemFilters (tier labels depend on the country). */
function renderGemControls() {
  const f = gemFilters
  const text = GEM_TIER_TEXT()
  const inp = (id: string) => $<HTMLInputElement>(id)
  const sel = (id: string) => $<HTMLSelectElement>(id)
  const time = (list: number[]) => list.map((m) => [String(m), fmtMinutes(m)] as [string, string])
  options(sel('#g-pop'), [...POP_CHOICES.map((p) => [String(p), p.toLocaleString('en')] as [string, string]), ['any', 'any size']],
    f.pop === null ? 'any' : String(withChoice(POP_CHOICES, f.pop)))
  // an unticked criterion keeps the values its selects show, so ticking it again brings them back
  const shownNum = (id: string) => Number(sel(id).value) || null
  const net = f.net ?? { kind: (sel('#g-net-kind').value || GEM_DEFAULTS.net!.kind) as NetKind, min: shownNum('#g-net-min') ?? GEM_DEFAULTS.net!.min }
  inp('#g-net-on').checked = !!f.net
  options(sel('#g-net-min'), NET_CHOICES.map((m) => [String(m), String(m)]), String(withChoice(NET_CHOICES, net.min)))
  sel('#g-net-kind').value = net.kind
  inp('#g-est').checked = f.est
  inp('#g-summer').checked = f.summer
  const limit = (key: 'city' | 'air' | 'hosp', choices: number[]) => {
    const d = GEM_DEFAULTS[key] as Limit
    const l = f[key] ?? { tier: (shownNum(`#g-${key}-tier`) ?? d.tier) as Tier, max: shownNum(`#g-${key}-max`) ?? d.max }
    inp(`#g-${key}-on`).checked = !!f[key]
    options(sel(`#g-${key}-tier`), ([1, 2, 3] as Tier[]).map((t) => [String(t), text[key][t].label]), String(l.tier))
    options(sel(`#g-${key}-max`), time(choices), String(withChoice(choices, l.max)))
  }
  limit('city', TIME_CHOICES)
  limit('air', TIME_CHOICES)
  limit('hosp', HOSP_TIME_CHOICES)
  const price = (key: 'rent' | 'buy', choices: number[], fmt: (v: number) => string) => {
    const d = { kind: 'house' as HomeKind, max: key === 'rent' ? 8 : 1500 }
    const l = f[key] ?? { kind: (sel(`#g-${key}-kind`).value || d.kind) as HomeKind, max: shownNum(`#g-${key}-max`) ?? d.max }
    inp(`#g-${key}-on`).checked = !!f[key]
    sel(`#g-${key}-kind`).value = l.kind
    options(sel(`#g-${key}-max`), choices.map((v) => [String(v), fmt(v)]), String(withChoice(choices, l.max)))
  }
  price('rent', RENT_CHOICES, (v) => `€${v}`)
  price('buy', BUY_CHOICES, (v) => `€${v.toLocaleString('en')}`)
  for (const [on, row] of [['#g-net-on', 'net'], ['#g-city-on', 'city'], ['#g-air-on', 'air'], ['#g-hosp-on', 'hosp'],
    ['#g-rent-on', 'rent'], ['#g-buy-on', 'buy']] as const) {
    inp(on).closest('.g-row')!.classList.toggle('off', !f[row])
  }
}

/** A value from the hash that is not one of the choices snaps to the nearest one. */
function withChoice(choices: number[], v: number): number {
  return choices.reduce((best, c) => (Math.abs(c - v) < Math.abs(best - v) ? c : best), choices[0])
}

function readGemControls(): GemFilters {
  const inp = (id: string) => $<HTMLInputElement>(id)
  const val = (id: string) => $<HTMLSelectElement>(id).value
  const limit = (key: string): Limit | null =>
    inp(`#g-${key}-on`).checked ? { tier: Number(val(`#g-${key}-tier`)) as Tier, max: Number(val(`#g-${key}-max`)) } : null
  const price = (key: string): PriceLimit | null =>
    inp(`#g-${key}-on`).checked ? { kind: val(`#g-${key}-kind`) as HomeKind, max: Number(val(`#g-${key}-max`)) } : null
  return {
    pop: val('#g-pop') === 'any' ? null : Number(val('#g-pop')),
    net: inp('#g-net-on').checked ? { kind: val('#g-net-kind') as 'fixed', min: Number(val('#g-net-min')) } : null,
    est: inp('#g-est').checked,
    city: limit('city'),
    air: limit('air'),
    summer: inp('#g-summer').checked,
    hosp: limit('hosp'),
    rent: price('rent'),
    buy: price('buy'),
  }
}

function gemTooltip(p: Record<string, unknown>): string {
  const v = judge(p, gemFilters)
  const name = String(p.name ?? '')
  const pop = typeof p.pop === 'number' ? `${p.pop.toLocaleString('en')} inhabitants` : ''
  const label: Record<Check['crit'], string> = {
    net: 'Internet', city: 'City', air: 'Airport', hosp: 'Hospital', rent: 'Rent', buy: 'Price to buy',
  }
  const failed = v.checks.filter((c) => !c.ok)
  const verdict =
    v.cls === 3 ? `Over ${gemFilters.pop!.toLocaleString('en')} inhabitants: not a gem`
      : v.cls === 2 ? '<b>Gem</b>: meets everything'
        : v.cls === 1 ? `<b>Near miss</b>: ${label[failed[0].crit].toLowerCase()}`
          : `Misses ${failed.map((c) => label[c.crit].toLowerCase()).join(', ')}`
  const dest = (c: Check): string => {
    const f = gemFilters
    if (c.crit === 'city' && f.city) {
      if ((p.dt as number) > 0 && (p.dt as number) <= f.city.tier) return 'is one'
      const city = data?.cities[p[`c${f.city.tier}`] as number]
      return city ? `to ${withCountry(city[1], foreignIso(city[0]))}${viaText(data?.gateways, p[`v${f.city.tier}`])}` : ''
    }
    if (c.crit === 'air' && f.air) {
      const v = f.summer ? 's' : 'y'
      const a = airports?.airports[p[`${v}a${f.air.tier}`] as number]
      return a ? `to ${withCountry(a[1], a[2])}${viaText(airports?.gateways, p[`v${v}${f.air.tier}`])}` : ''
    }
    if (c.crit === 'hosp' && f.hosp) {
      if (c.value === 0) return 'in town'
      const h = hospitals?.hospitals[p[`hi${f.hosp.tier}`] as number]
      return h ? `to ${h[1]}` : ''
    }
    return ''
  }
  const row = (c: Check) => {
    const f = gemFilters
    const mark = c.ok ? '<span class="ok">✓</span>' : '<span class="ko">✗</span>'
    let value: string
    let limit: string
    if (c.crit === 'net') {
      value = c.value === null ? 'no speed data' : `${c.est ? '≈ ' : ''}${Math.round(c.value)} Mbps${c.est ? ' (estimate)' : ''}`
      limit = `≥ ${f.net!.min} Mbps`
    } else if (c.crit === 'rent' || c.crit === 'buy') {
      const lp = f[c.crit]!
      const rent = c.crit === 'rent'
      const fmt = (v: number) => (rent ? `€${v.toFixed(1)}` : `€${Math.round(v).toLocaleString('en')}`)
      value = c.value === null
        ? 'no figure'
        : `${c.scope ? '≈ ' : ''}${fmt(c.value)}/m²${rent ? ' a month' : ''}, ${!rent && housing?.params.buy_all_dwellings ? 'any home' : lp.kind}${c.scope ? ` (${SCOPE_TEXT[c.scope]})` : ''}`
      limit = `≤ ${fmt(lp.max)}`
    } else {
      const l = f[c.crit]!
      value = c.value === null ? 'none within 3 h' : c.value === 0 ? '' : fmtMinutes(c.value)
      limit = `≤ ${fmtMinutes(l.max)}`
    }
    return `<br>${mark} ${label[c.crit]}: ${[value, dest(c)].filter(Boolean).join(' ')}${c.ok ? '' : ` <span class="muted">(${limit})</span>`}`
  }
  return `<b>${name}</b>${pop ? `<br><span class="muted">${pop}</span>` : ''}<br>${verdict}` + v.checks.map(row).join('')
}

let panelPadding: () => maplibregl.PaddingOptions = () => ({ top: 0, bottom: 0, left: 0, right: 0 })

function writeHash() {
  const plain = location.pathname + location.search
  const hash = mode === 'gems' ? `#${country}/gems?${formatHash(gemFilters)}` : `#${country}/${mode}`
  history.replaceState(null, '', country === 'es' && mode === 'cities' ? plain : hash)
}

function renderViews(map: maplibregl.Map, padding: () => maplibregl.PaddingOptions) {
  const box = $('#jump')
  box.innerHTML = VIEWS[country].map((v) => `<button data-view="${v.id}">${v.label}</button>`).join('')
  box.querySelectorAll<HTMLButtonElement>('button').forEach((b) =>
    b.addEventListener('click', () =>
      map.fitBounds(VIEWS[country].find((v) => v.id === b.dataset.view)!.bounds, { padding: padding() }),
    ),
  )
}

/** Switch country: reload its boundaries and city data; its other datasets load when their mode is shown. */
async function setCountry(map: maplibregl.Map, cc: Country, padding: () => maplibregl.PaddingOptions) {
  if (cc === country && !loading) return
  const g = ++gen
  country = cc
  setDataCountry(cc)
  loading = true
  airports = internet = hospitals = housing = undefined
  hideTooltip()
  refresh(map)
  const loaded = await loadData()
  if (g !== gen) return // a newer switch is under way
  // the old country's gem classes would colour the new one's communes sharing a code
  if (map.getSource('munis')) map.removeFeatureState({ source: 'munis' })
  painted = null
  geo = loaded.geo
  data = loaded.cities
  muniNames.clear()
  loaded.names.forEach((v, k) => muniNames.set(k, v))
  loading = false
  provincesGeo = loaded.provinces as FeatureCollection
  // the map may still be loading its style: its load handler then adds the sources from geo/provincesGeo
  ;(map.getSource('munis') as maplibregl.GeoJSONSource | undefined)?.setData(geo)
  ;(map.getSource('provinces') as maplibregl.GeoJSONSource | undefined)?.setData(provincesGeo)
  renderViews(map, padding)
  map.fitBounds(VIEWS[cc][0].bounds, { padding: padding() })
  await setMode(map, mode)
}

function setTier(map: maplibregl.Map, t: Tier) {
  tier = tiers[mode] = t
  refresh(map)
}

async function setMode(map: maplibregl.Map, m: Mode) {
  mode = m
  tier = tiers[m]
  writeHash()
  if (loading) return refresh(map) // the country's data will apply this mode when it arrives
  if (m === 'airports') await ensureAirports(map)
  if (m === 'internet') await ensureInternet(map)
  if (m === 'hospitals') await ensureHospitals(map)
  if (m === 'housing') await ensureHousing(map)
  if (m === 'gems') await Promise.all([ensureAirports(map), ensureInternet(map), ensureHospitals(map), ensureHousing(map)])
  if (mode !== m) return // another mode was chosen while this one loaded
  refresh(map)
}

function tooltipHTML(p: Record<string, unknown>, at?: [number, number]): string {
  if (mode === 'gems') return gemTooltip(p)
  if (mode === 'housing') return housingTooltip(p, !!housing?.params.buy_all_dwellings)
  if (mode === 'internet') return internetTooltip(p, tier, mobile, internet)
  if (mode === 'hospitals') {
    return hospitals
      ? hospitalTooltip(hospitals, p, tier, fmtMinutes, (c) => muniNames.get(c) ?? '')
      : `<b>${String(p.name ?? '')}</b>`
  }
  if (mode === 'airports') {
    return airports ? airportTooltip(airports, p, tier, summer, fmtMinutes, at) : `<b>${String(p.name ?? '')}</b>`
  }
  const name = String(p.name ?? '')
  const pop = typeof p.pop === 'number' ? `${p.pop.toLocaleString('en')} inhabitants` : ''
  if (p.t1 === undefined) return `<b>${name}</b><br><span class="muted">No travel data</span>`
  if ((p.dt as number) > 0 && (p.dt as number) <= tier) return `<b>${name}</b><br>${pop ? pop + '<br>' : ''}<span class="muted">Main city</span>`
  const t = p[`t${tier}`] as number
  const ci = p[`c${tier}`] as number
  const city = data && ci >= 0 ? data.cities[ci] : null
  const cityName = city ? (city[5] ? `${city[1]} (${city[5]} metro)` : withCountry(city[1], foreignIso(city[0]))) : ''
  const max = data?.params.max_minutes ?? 180
  const via = p[`v${tier}`]
  return (
    `<b>${name}</b>${pop ? `<br><span class="muted">${pop}</span>` : ''}` +
    `<br><span class="big">${via !== undefined ? '≈ ' : ''}${fmtMinutes(t, max)}</span>` +
    (city ? `<br>to ${cityName}${viaText(data?.gateways, via)}` : `<br><span class="muted">no ${CITY_TEXT[country][tier].noun} within ${max / 60} h</span>`)
  )
}

/** "PT" for a city abroad ("PT:porto"), null at home. */
function foreignIso(code: string): string | null {
  return code.includes(':') ? code.split(':')[0] : null
}

function showTooltip(x: number, y: number, html: string) {
  const el = $('#tooltip')
  el.innerHTML = html
  el.hidden = false
  const w = el.offsetWidth
  const h = el.offsetHeight
  const left = Math.min(x + 14, window.innerWidth - w - 8)
  const top = y + h + 20 > window.innerHeight ? y - h - 14 : y + 14
  el.style.transform = `translate(${Math.max(8, left)}px, ${Math.max(8, top)}px)`
}

function hideTooltip() {
  $('#tooltip').hidden = true
}

async function main() {
  renderLegend()
  // browsers may restore a ticked checkbox on reload: start from what is shown
  summer = $<HTMLInputElement>('#summer').checked
  mobile = $<HTMLInputElement>('#mobile').checked
  flats = $<HTMLInputElement>('#flats').checked
  const [style, loaded] = await Promise.all([loadStyle(), loadData()])
  geo = loaded.geo
  data = loaded.cities
  loaded.names.forEach((v, k) => muniNames.set(k, v))
  provincesGeo = loaded.provinces as FeatureCollection

  const narrow = window.innerWidth < 700
  if (narrow) $('#panel').classList.add('collapsed')
  // padding that keeps the map clear of the panel (bottom sheet on phones, left card on desktop)
  const padding = () => {
    const r = $('#panel').getBoundingClientRect()
    return narrow
      ? { top: 16, bottom: window.innerHeight - r.top + 8, left: 8, right: 8 }
      : { top: 30, bottom: 30, left: r.right + 20, right: 30 }
  }
  panelPadding = padding
  const map = new maplibregl.Map({
    container: 'map',
    style,
    center: [-3.7, 40.2],
    zoom: 4.5,
    attributionControl: { compact: true },
  })
  map.fitBounds(VIEWS[country][0].bounds, { padding: padding(), animate: false })
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')

  map.on('load', () => {
    // put the choropleth under the basemap's first label layer
    const firstSymbol = map.getStyle().layers.find((l) => l.type === 'symbol')?.id
    map.addSource('munis', {
      type: 'geojson',
      data: geo!,
      promoteId: 'code',
      attribution:
        'Travel times © <a href="https://traveltime.com">TravelTime</a> · Boundaries © IGN · Population © INE · Stops © OpenStreetMap · Speed tests © Ookla · Coverage © SETID / Arcep · Hospitals © Ministerio de Sanidad / FINESS, DREES · Communes © INSEE, Etalab',
    })
    map.addSource('provinces', { type: 'geojson', data: provincesGeo! })
    map.addSource('dests', { type: 'geojson', data: destGeoJSON() })

    map.addLayer(
      {
        id: 'muni-fill', type: 'fill', source: 'munis',
        paint: { 'fill-color': currentFill(), 'fill-opacity': 0.88 },
      },
      firstSymbol,
    )
    map.addImage('hatch', hatchImage())
    map.addLayer(
      {
        id: 'muni-est', type: 'fill', source: 'munis',
        filter: internetEstimateFilter(tier, mobile),
        layout: { visibility: mode === 'internet' ? 'visible' : 'none' },
        paint: { 'fill-pattern': 'hatch' },
      },
      firstSymbol,
    )
    map.addLayer(
      {
        id: 'muni-line', type: 'line', source: 'munis',
        paint: { 'line-color': '#ffffff', 'line-width': ['interpolate', ['linear'], ['zoom'], 5, 0.1, 9, 0.8], 'line-opacity': 0.6 },
      },
      firstSymbol,
    )
    map.addLayer(
      { id: 'prov-line', type: 'line', source: 'provinces', paint: { 'line-color': '#57554f', 'line-width': 0.6, 'line-opacity': 0.5 } },
      firstSymbol,
    )
    map.addLayer({
      id: 'muni-hover', type: 'line', source: 'munis',
      paint: { 'line-color': '#1f1e1c', 'line-width': ['case', ['boolean', ['feature-state', 'hover'], false], 1.6, 0] },
    })
    map.addLayer({
      id: 'city-dot', type: 'circle', source: 'dests',
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, ['match', ['get', 'tier'], 1, 4, 2.5], 9, ['match', ['get', 'tier'], 1, 7, 5]],
        // airports nobody reaches (no transit link in the data) are drawn faded
        'circle-color': ['case', ['==', ['coalesce', ['get', 'reach'], 1], 0], '#d6d4ce', '#ffffff'],
        'circle-stroke-color': ['case', ['==', ['coalesce', ['get', 'reach'], 1], 0], '#8a877f', '#1f1e1c'],
        'circle-stroke-width': 1.5,
      },
    })
    if (typeof style === 'string') {
      map.addLayer({
        id: 'city-label', type: 'symbol', source: 'dests',
        minzoom: 5,
        filter: ['any', ['==', ['get', 'tier'], 1], ['>=', ['zoom'], 6.5]],
        layout: {
          'text-field': ['get', 'name'],
          'text-font': ['Noto Sans Bold'],
          'text-size': ['match', ['get', 'tier'], 1, 13, 11],
          'text-offset': [0, 0.9],
          'text-anchor': 'top',
          'text-optional': true,
        },
        paint: { 'text-color': '#1f1e1c', 'text-halo-color': '#ffffff', 'text-halo-width': 1.5 },
      })
    }

    let hovered: string | number | undefined
    const setHover = (id?: string | number) => {
      if (hovered !== undefined) map.setFeatureState({ source: 'munis', id: hovered }, { hover: false })
      hovered = id
      if (id !== undefined) map.setFeatureState({ source: 'munis', id }, { hover: true })
    }
    map.on('mousemove', 'muni-fill', (e) => {
      const f = e.features?.[0]
      if (!f) return
      map.getCanvas().style.cursor = 'crosshair'
      setHover(f.id)
      showTooltip(e.point.x, e.point.y, tooltipHTML(f.properties as Record<string, unknown>, [e.lngLat.lng, e.lngLat.lat]))
    })
    map.on('mouseleave', 'muni-fill', () => {
      map.getCanvas().style.cursor = ''
      setHover(undefined)
      hideTooltip()
    })
    // touch: tap shows the tooltip
    map.on('click', 'muni-fill', (e) => {
      const f = e.features?.[0]
      if (!f) return
      setHover(f.id)
      showTooltip(e.point.x, e.point.y, tooltipHTML(f.properties as Record<string, unknown>, [e.lngLat.lng, e.lngLat.lat]))
    })
    map.on('movestart', hideTooltip)
    refresh(map) // layers exist now: estimate hatching, and gem feature-states, need them
  })

  document.querySelectorAll<HTMLButtonElement>('.tiers button').forEach((b) =>
    b.addEventListener('click', () => setTier(map, Number(b.dataset.tier) as Tier)),
  )
  document.querySelectorAll<HTMLButtonElement>('.modes button').forEach((b) =>
    b.addEventListener('click', () => setMode(map, b.dataset.mode as Mode)),
  )
  $<HTMLInputElement>('#mobile').addEventListener('change', (e) => {
    mobile = (e.target as HTMLInputElement).checked
    refresh(map)
  })
  $<HTMLInputElement>('#flats').addEventListener('change', (e) => {
    flats = (e.target as HTMLInputElement).checked
    refresh(map)
  })
  $<HTMLInputElement>('#summer').addEventListener('change', (e) => {
    summer = (e.target as HTMLInputElement).checked
    refresh(map)
  })
  renderViews(map, padding)
  document.querySelectorAll<HTMLButtonElement>('.countries button').forEach((b) =>
    b.addEventListener('click', () => setCountry(map, b.dataset.country as Country, padding)),
  )
  let gemTimer = 0
  const onGemChange = () => {
    clearTimeout(gemTimer)
    gemTimer = window.setTimeout(() => {
      gemFilters = readGemControls()
      writeHash()
      refresh(map)
    }, 100)
  }
  $('#gems-controls').addEventListener('change', onGemChange)
  $('#g-reset').addEventListener('click', () => {
    gemFilters = { ...GEM_DEFAULTS }
    writeHash()
    refresh(map)
  })
  $('#collapse').addEventListener('click', () => {
    $('#panel').classList.toggle('collapsed')
    map.fitBounds(VIEWS[country][0].bounds, { padding: padding() })
  })

  await setMode(map, mode)
}

main()
