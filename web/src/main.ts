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
import { dataUrl, setDataCountry, type Country } from './country'

type Mode = 'cities' | 'airports' | 'internet' | 'hospitals'

// [code, name, tier, lat, lng, metro, population]
type City = [string, string, number, number, number, string | null, number | null]

interface Remoteness {
  generated_at: string
  params: { arrival: string; endpoint: string; max_minutes: number; population_year: number | null; notes: string[] }
  cities: City[]
  // code -> [t1, c1, t2, c2, t3, c3, urban (any tier), population]; t = minutes, -1 = over the cap
  m: Record<string, [number, number, number, number, number, number, 0 | 1, number | null]>
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

const MODES: Mode[] = ['cities', 'airports', 'internet', 'hospitals']
// hash: "#fr/hospitals", "#es/airports"; old links ("#airports") mean Spain
const [hashCountry, hashMode] = location.hash.slice(1).includes('/') ? location.hash.slice(1).split('/') : ['es', location.hash.slice(1)]
let country: Country = hashCountry === 'fr' ? 'fr' : 'es'
setDataCountry(country)
let mode: Mode = MODES.find((m) => m === hashMode) ?? 'cities'
const tiers: Record<Mode, Tier> = { cities: 2, airports: 2, internet: 1, hospitals: 2 }
let tier: Tier = tiers[mode]
let summer = false
let data: Remoteness | null = null
let airports: AirportsData | null | undefined // undefined = not loaded yet
let internet: InternetData | null | undefined
let hospitals: HospitalsData | null | undefined
const muniNames = new Map<string, string>()
let mobile = false
let geo: FeatureCollection<Geometry, Record<string, unknown>> | null = null

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

/** Hatch layer on top of municipalities whose value is an estimate (internet mode only). */
function applyEstimateLayer(map: maplibregl.Map) {
  if (!map.getLayer('muni-est')) return
  map.setLayoutProperty('muni-est', 'visibility', mode === 'internet' ? 'visible' : 'none')
  if (mode === 'internet') map.setFilter('muni-est', internetEstimateFilter(tier, mobile))
}

function currentFill(): ExpressionSpecification {
  if (mode === 'internet') return internetFill(tier, mobile, COLORS.slice(1), INTERNET_NODATA)
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

  try {
    data = null
    const r = await fetch(dataUrl('remoteness.json'))
    if (r.ok) data = (await r.json()) as Remoteness
  } catch {
    data = null
  }

  // tier in which each municipality counts as a main city (tiers are nested)
  const cityTier = new Map((data?.cities ?? []).map((c) => [c[0], c[2]]))
  for (const f of g.features) {
    const code = String(f.id)
    const p: Record<string, unknown> = { code, name: f.properties?.name }
    const row = data?.m[code]
    if (row) {
      ;[p.t1, p.c1, p.t2, p.c2, p.t3, p.c3, , p.pop] = row
    }
    p.dt = cityTier.get(code) ?? 0
    f.properties = p
    muniNames.set(code, String(p.name ?? ''))
  }
  return { geo: g, provinces }
}

/** Load hospitals.json once and merge its values into the municipality features. */
async function ensureHospitals(map: maplibregl.Map) {
  if (hospitals !== undefined) return
  hospitals = await loadHospitals()
  if (!hospitals || !geo) return
  for (const f of geo.features) {
    const row = hospitals.m[String(f.id)]
    if (row) Object.assign(f.properties, hospitalProps(row))
  }
  ;(map.getSource('munis') as maplibregl.GeoJSONSource | undefined)?.setData(geo)
}

async function ensureAirports(map: maplibregl.Map) {
  if (airports !== undefined) return
  airports = await loadAirports()
  if (!airports || !geo) return
  for (const f of geo.features) {
    const row = airports.m[String(f.id)]
    if (row) Object.assign(f.properties, airportProps(row))
  }
  const src = map.getSource('munis') as maplibregl.GeoJSONSource | undefined
  src?.setData(geo)
}

/** Load internet.json once and merge its values into the municipality features. */
async function ensureInternet(map: maplibregl.Map) {
  if (internet !== undefined) return
  internet = await loadInternet()
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
  if (mode === 'internet') return { type: 'FeatureCollection', features: [] }
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
  const labels = ['< 30 min', '30–60', '60–90', '90 min–2 h', '2 h–2 h 30', '2 h 30–3 h', '3 h+ / no service']
  $('#legend').innerHTML =
    COLORS.map((c, i) => item(c, labels[i])).join('') +
    (mode === 'cities' ? item(URBAN, 'City of the selected tier') : '')
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
  $('#mobile-wrap').hidden = mode !== 'internet'
  const noun = `<strong>${text[tier].noun.replace(/^an? /, '')}</strong>`
  $('#lead').innerHTML =
    mode === 'internet'
      ? `Average ${noun}${tier === 3 ? '' : ' speed'} per municipality from Speedtest by Ookla, measured locally or estimated from nearby tests (hatched), last 4 quarters.`
      : `Public transport time from each municipality to the nearest ${noun}, best connection of a weekday.`
  $('#tier-help').textContent = text[tier].help

  const h =
    mode === 'cities'
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
  const missing = { cities: !data, airports: airports === null, internet: internet === null, hospitals: hospitals === null }[mode]
  s.hidden = !missing
  s.innerHTML = {
    cities: 'Travel times have not been computed yet. Run <code>python3 pipeline/compute_times.py</code>.',
    airports: 'Airport travel times have not been computed yet. Run <code>python3 pipeline/compute_airports.py</code>.',
    internet: 'Internet speeds have not been computed yet. Run <code>python3 pipeline/compute_internet.py</code>.',
    hospitals: 'Hospital travel times have not been computed yet. Run <code>python3 pipeline/compute_hospitals.py</code>.',
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
  if (map.getLayer('muni-fill')) {
    map.setPaintProperty('muni-fill', 'fill-color', currentFill())
    applyEstimateLayer(map)
    ;(map.getSource('dests') as maplibregl.GeoJSONSource).setData(destGeoJSON())
  }
  hideTooltip()
}

function writeHash() {
  const plain = location.pathname + location.search
  history.replaceState(null, '', country === 'es' && mode === 'cities' ? plain : `#${country}/${mode}`)
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
  if (cc === country) return
  country = cc
  setDataCountry(cc)
  airports = internet = hospitals = undefined
  muniNames.clear()
  hideTooltip()
  const loaded = await loadData()
  geo = loaded.geo
  ;(map.getSource('munis') as maplibregl.GeoJSONSource).setData(geo)
  ;(map.getSource('provinces') as maplibregl.GeoJSONSource).setData(loaded.provinces)
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
  if (m === 'airports') await ensureAirports(map)
  if (m === 'internet') await ensureInternet(map)
  if (m === 'hospitals') await ensureHospitals(map)
  refresh(map)
}

function tooltipHTML(p: Record<string, unknown>, at?: [number, number]): string {
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
  const cityName = city ? (city[5] ? `${city[1]} (${city[5]} metro)` : city[1]) : ''
  const max = data?.params.max_minutes ?? 180
  return (
    `<b>${name}</b>${pop ? `<br><span class="muted">${pop}</span>` : ''}` +
    `<br><span class="big">${fmtMinutes(t, max)}</span>` +
    (city ? `<br>to ${cityName}` : `<br><span class="muted">no ${CITY_TEXT[country][tier].noun} within ${max / 60} h</span>`)
  )
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
  const [style, loaded] = await Promise.all([loadStyle(), loadData()])
  geo = loaded.geo
  const provinces = loaded.provinces

  const narrow = window.innerWidth < 700
  if (narrow) $('#panel').classList.add('collapsed')
  // padding that keeps the map clear of the panel (bottom sheet on phones, left card on desktop)
  const padding = () => {
    const r = $('#panel').getBoundingClientRect()
    return narrow
      ? { top: 16, bottom: window.innerHeight - r.top + 8, left: 8, right: 8 }
      : { top: 30, bottom: 30, left: r.right + 20, right: 30 }
  }
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
    map.addSource('provinces', { type: 'geojson', data: provinces })
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
  $<HTMLInputElement>('#summer').addEventListener('change', (e) => {
    summer = (e.target as HTMLInputElement).checked
    refresh(map)
  })
  renderViews(map, padding)
  document.querySelectorAll<HTMLButtonElement>('.countries button').forEach((b) =>
    b.addEventListener('click', () => setCountry(map, b.dataset.country as Country, padding)),
  )
  $('#collapse').addEventListener('click', () => {
    $('#panel').classList.toggle('collapsed')
    map.fitBounds(VIEWS[country][0].bounds, { padding: padding() })
  })

  await setMode(map, mode)
}

main()
