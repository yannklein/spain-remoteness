/** The selected country's data folder: every dataset of a country lives in ./data/<cc>/ (self-contained). */
export type Country = 'es' | 'fr'

let current: Country = 'es'

export function setDataCountry(cc: Country) {
  current = cc
}

export function dataUrl(file: string): string {
  return `./data/${current}/${file}`
}

export function dataCountry(): Country {
  return current
}

/** Countries of foreign destinations (ISO codes, as in "PT:porto" or an airport's country). */
export const COUNTRY_NAMES: Record<string, string> = {
  ES: 'Spain', FR: 'France', PT: 'Portugal', AD: 'Andorra', GI: 'Gibraltar', CH: 'Switzerland', LU: 'Luxembourg',
  BE: 'Belgium', DE: 'Germany', IT: 'Italy', MC: 'Monaco',
}

/** "Porto (Portugal)" for a destination abroad, the plain name at home. */
export function withCountry(name: string, iso: string | null | undefined): string {
  return iso && iso.toLowerCase() !== current && COUNTRY_NAMES[iso] ? `${name} (${COUNTRY_NAMES[iso]})` : name
}

/** Border station an estimate went through: [id, name, lat, lng]. */
export type Gateway = [string, string, number, number]

export function viaText(gateways: Gateway[] | undefined, g: unknown): string {
  return typeof g === 'number' && g >= 0 && gateways?.[g] ? ` <span class="muted">via ${gateways[g][1]} (estimate)</span>` : ''
}
