import maplibregl, { type ExpressionSpecification, type StyleSpecification } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { feature } from 'topojson-client'
import type { Topology, GeometryCollection } from 'topojson-specification'
import type { FeatureCollection, Geometry } from 'geojson'
import './style.css'

type Tier = 1 | 2 | 3

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

const TIER_TEXT: Record<Tier, { noun: string; help: string }> = {
  1: { noun: 'metro', help: 'Madrid, Barcelona, València, Sevilla, Zaragoza, Málaga.' },
  2: { noun: 'regional hub', help: 'Provincial and regional capitals plus every city over 100k.' },
  3: { noun: 'urban area', help: 'Regional hubs plus every municipality over 50k.' },
}

const VIEWS: Record<string, [[number, number], [number, number]]> = {
  peninsula: [[-9.6, 35.8], [4.5, 43.9]],
  canarias: [[-18.3, 27.5], [-13.3, 29.5]],
  baleares: [[1.1, 38.6], [4.4, 40.2]],
}

const BASE_STYLE = 'https://tiles.openfreemap.org/styles/positron'
const FALLBACK_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#f6f5f2' } }],
}

const $ = <T extends HTMLElement>(sel: string) => document.querySelector(sel) as T

let tier: Tier = 2
let data: Remoteness | null = null

function fmtMinutes(t: number, max = 180): string {
  if (t < 0) return `over ${max / 60} h (or no service)`
  if (t < 60) return `${t} min`
  const h = Math.floor(t / 60)
  const m = t % 60
  return m ? `${h} h ${String(m).padStart(2, '0')}` : `${h} h`
}

function fillColor(t: Tier): ExpressionSpecification {
  const key = `t${t}`
  const steps: (number | string)[] = [COLORS[0]]
  BINS.slice(0, -1).forEach((b, i) => steps.push(b, COLORS[i + 1]))
  return [
    'case',
    ['all', ['>', ['get', 'dt'], 0], ['<=', ['get', 'dt'], t]], URBAN,
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
  const topo = (await (await fetch('./data/municipalities.topo.json')).json()) as Topology
  const geo = feature(topo, topo.objects.municipalities as GeometryCollection) as FeatureCollection<
    Geometry,
    Record<string, unknown>
  >
  const provinces = feature(topo, topo.objects.provinces as GeometryCollection)

  try {
    const r = await fetch('./data/remoteness.json')
    if (r.ok) data = (await r.json()) as Remoteness
  } catch {
    data = null
  }

  // tier in which each municipality counts as a main city (tiers are nested)
  const cityTier = new Map((data?.cities ?? []).map((c) => [c[0], c[2]]))
  for (const f of geo.features) {
    const code = String(f.id)
    const p: Record<string, unknown> = { code, name: f.properties?.name }
    const row = data?.m[code]
    if (row) {
      ;[p.t1, p.c1, p.t2, p.c2, p.t3, p.c3, , p.pop] = row
    }
    p.dt = cityTier.get(code) ?? 0
    f.properties = p
  }
  return { geo, provinces }
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
  return `<b>${pct}%</b> ${who} are more than <b>1 hour</b> by public transport from a ${TIER_TEXT[t].noun}.`
}

function renderLegend() {
  const labels = ['< 30 min', '30–60', '60–90', '90 min–2 h', '2 h–2 h 30', '2 h 30–3 h', '3 h+ / no service']
  $('#legend').innerHTML =
    COLORS.map((c, i) => `<div><i style="background:${c}"></i>${labels[i]}</div>`).join('') +
    `<div><i style="background:${URBAN}"></i>City of the selected tier</div>`
}

function setTier(map: maplibregl.Map, t: Tier) {
  tier = t
  document.querySelectorAll<HTMLButtonElement>('.tiers button').forEach((b) => {
    b.setAttribute('aria-checked', String(Number(b.dataset.tier) === t))
  })
  $('#tier-noun').textContent = TIER_TEXT[t].noun
  $('#tier-help').textContent = TIER_TEXT[t].help
  const h = headline(t)
  const el = $('#headline')
  el.hidden = !h
  if (h) el.innerHTML = h
  if (map.getLayer('muni-fill')) {
    map.setPaintProperty('muni-fill', 'fill-color', fillColor(t))
    ;(map.getSource('cities') as maplibregl.GeoJSONSource).setData(cityGeoJSON(t))
  }
  hideTooltip()
}

function tooltipHTML(p: Record<string, unknown>): string {
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
    (city ? `<br>to ${cityName}` : `<br><span class="muted">no ${TIER_TEXT[tier].noun} within ${max / 60} h</span>`)
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
  const [style, { geo, provinces }] = await Promise.all([loadStyle(), loadData()])

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
  map.fitBounds(VIEWS.peninsula, { padding: padding(), animate: false })
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')

  map.on('load', () => {
    // put the choropleth under the basemap's first label layer
    const firstSymbol = map.getStyle().layers.find((l) => l.type === 'symbol')?.id
    map.addSource('munis', {
      type: 'geojson',
      data: geo,
      promoteId: 'code',
      attribution: 'Travel times © <a href="https://traveltime.com">TravelTime</a> · Boundaries © IGN · Population © INE',
    })
    map.addSource('provinces', { type: 'geojson', data: provinces })
    map.addSource('cities', { type: 'geojson', data: cityGeoJSON(tier) })

    map.addLayer({ id: 'muni-fill', type: 'fill', source: 'munis', paint: { 'fill-color': fillColor(tier), 'fill-opacity': 0.88 } }, firstSymbol)
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
      id: 'city-dot', type: 'circle', source: 'cities',
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, ['match', ['get', 'tier'], 1, 4, 2.5], 9, ['match', ['get', 'tier'], 1, 7, 5]],
        'circle-color': '#ffffff',
        'circle-stroke-color': '#1f1e1c',
        'circle-stroke-width': 1.5,
      },
    })
    if (typeof style === 'string') {
      map.addLayer({
        id: 'city-label', type: 'symbol', source: 'cities',
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
      showTooltip(e.point.x, e.point.y, tooltipHTML(f.properties as Record<string, unknown>))
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
      showTooltip(e.point.x, e.point.y, tooltipHTML(f.properties as Record<string, unknown>))
    })
    map.on('movestart', hideTooltip)
  })

  document.querySelectorAll<HTMLButtonElement>('.tiers button').forEach((b) =>
    b.addEventListener('click', () => setTier(map, Number(b.dataset.tier) as Tier)),
  )
  document.querySelectorAll<HTMLButtonElement>('.jump button').forEach((b) =>
    b.addEventListener('click', () => map.fitBounds(VIEWS[b.dataset.view!], { padding: padding() })),
  )
  $('#collapse').addEventListener('click', () => {
    $('#panel').classList.toggle('collapsed')
    map.fitBounds(VIEWS.peninsula, { padding: padding() })
  })

  if (data) {
    for (const t of [1, 2, 3] as Tier[]) {
      $(`#n${t}`).textContent = String(data.cities.filter((c) => c[2] <= t).length)
    }
    const d = new Date(data.generated_at)
    $('#meta').textContent =
      `Computed ${d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })} · ` +
      `${data.cities.length} cities · ${data.params.endpoint} endpoint` +
      (data.params.population_year ? ` · population ${data.params.population_year}` : '') +
      (data.params.notes.length ? ` · ${data.params.notes.join('; ')}` : '')
  } else {
    const s = $('#status')
    s.hidden = false
    s.innerHTML =
      'Travel times have not been computed yet. Run the <b>Compute travel times</b> workflow in the GitHub repo (it needs the TravelTime API secrets).'
  }
  setTier(map, tier)
}

main()
