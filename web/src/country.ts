/** The selected country's data folder: every dataset of a country lives in ./data/<cc>/ (self-contained). */
export type Country = 'es' | 'fr'

let current: Country = 'es'

export function setDataCountry(cc: Country) {
  current = cc
}

export function dataUrl(file: string): string {
  return `./data/${current}/${file}`
}
