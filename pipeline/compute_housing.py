"""Housing prices per municipality: rent and purchase, €/m².

Spain
  rent  SERPAVI (Ministerio de Vivienda), municipal medians from lease deposits / tax returns, houses (VU)
        and flats (VC); latest year of 2022-2024 with a value (>= 10 leases).
  buy   coarse: Ministry appraisal value of free-market housing for towns over 25,000 (latest quarter),
        the province average elsewhere. All dwellings, so houses = flats.
France
  rent  ANIL "carte des loyers" 2025: advertised rents incl. charges predicted for every commune; a
        prediction pooled over an area, with R² < 0.5 or < 30 listings counts as an area model.
  buy   DVF statistics (Etalab), 10 half-years: median €/m² of house / flat sales. None in Alsace-Moselle.
A municipality without its own figure gets the count-weighted mean of municipalities within 10 km
(>= 10 leases or 5 sales in total), marked "nearby".

Scopes: 0 own, 1 nearby, 2 province average, 3 area model.
Usage: python pipeline/compute_housing.py --country es|fr
"""

import argparse
import csv
import difflib
import io
import math
import re
import unicodedata
import urllib.request
from datetime import datetime, timezone

from common import add_country_arg, dump_json, haversine_km, load_json, paths, write_csv

NEARBY_KM = 10
MIN_LEASES, MIN_SALES = 10, 5
YEARS = (24, 23, 22)
KEYS = ("rh", "rf", "bh", "bf")   # rent house, rent flat, buy house, buy flat
SCOPE_NAMES = {0: "own", 1: "nearby", 2: "province", 3: "area"}
NO_DVF = ("57", "67", "68")
PLAUSIBLE_EUR_M2 = (200, 30000)   # DVF medians outside this come from a few odd sales (e.g. 220,000 €/m² from 5 sales)       # Alsace-Moselle: land register outside DVF

SERPAVI_URL = ("https://cdn.mivau.gob.es/portal-web-mivau/vivienda/serpavi/"
               "2026-03_09_bd_SERPAVI_2011-2024%20-%20DEFINITIVO%20WEB_v2.xlsx")
APPRAISAL_TOWNS_URL = "https://cdn.transportes.gob.es/estadistica/BoletinOnline2/35103500.xls"
APPRAISAL_PROVINCES_URL = "https://cdn.mivau.gob.es/portal-web-mivau/Datos_MIVAU/CSV/VDP006_01.csv"
ANIL_URLS = {
    "rh": "https://static.data.gouv.fr/resources/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025/20251211-145039/pred-mai-mef-dhup.csv",
    "rf": "https://static.data.gouv.fr/resources/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025/20251211-145010/pred-app-mef-dhup.csv",
}
DVF_URL = "https://data-pipeline-open.s3.sbg.io.cloud.ovh.net/dvf/stats_whole_period.csv"


def _num(v):
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return None


# ---- Spain ----------------------------------------------------------------------------------------

def read_serpavi(header, rows):
    """{code: {"rh": (median, leases, year), "rf": ...}} from the SERPAVI municipal sheet."""
    col = {h: i for i, h in enumerate(header)}
    out = {}
    for r in rows:
        got = {}
        for key, kind in (("rf", "VC"), ("rh", "VU")):
            for yy in YEARS:
                v = col.get(f"ALQM2_LV_M_{kind}_{yy}")
                n = col.get(f"BI_ALVHEPCO_T{kind}_{yy}")
                val = _num(r[v]) if v is not None else None
                if val is None:
                    continue
                got[key] = (round(val, 2), int(_num(r[n]) or 0), 2000 + yy)
                break
        if got:
            out[str(r[col["CUMUN"]]).zfill(5)] = got
    return out


def read_appraisal_sheet(rows):
    """[(province, town, €/m² all dwellings, appraisals)] from one quarter's sheet (towns > 25,000)."""
    out, province, started = [], None, False
    for r in rows:
        cells = [str(c).strip() for c in r]
        if len(cells) < 6:
            continue
        if not started:
            started = cells[1] == "" and cells[3].startswith("Hasta")
            continue
        if cells[1]:
            province = cells[1]
        total = _num(cells[5])
        if not cells[2] or total is None:
            continue
        n = _num(cells[9]) if len(cells) > 9 else None
        if n is None:
            n = sum(_num(c) or 0 for c in cells[7:9])
        out.append((province, cells[2], total, int(n)))
    return out


def normalise(name):
    """'Ejido (El)', 'Campello, el' and 'El Ejido' -> 'el ejido'; accents and punctuation dropped."""
    s = name.strip()
    m = re.match(r"^(.*)\s*\(([^)]+)\)$", s) or re.match(r"^(.*),\s*(el|la|los|las|l'|els|les|o|a|os|as)$", s, re.I)
    if m:
        s = f"{m.group(2)} {m.group(1)}"
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


# Castilian names in the Ministry's sheet -> the co-official names used by INE/IGN
ALIASES = {"elche": "elx", "alicante": "alacant", "castellon de la plana": "castello de la plana",
           "palma de mallorca": "palma", "lerida": "lleida", "gerona": "girona", "orense": "ourense",
           "la coruna": "a coruna", "villarreal": "vila real", "sagunto": "sagunt", "jativa": "xativa",
           "javea": "xabia", "villajoyosa": "la vila joiosa", "san vicente del raspeig": "sant vicent del raspeig",
           "vitoria": "vitoria gasteiz", "mahon": "mao", "ibiza": "eivissa", "santa eulalia del rio": "santa eularia des riu",
           "san antonio abad": "sant antoni de portmany", "san sebastian": "donostia", "san cristobal laguna":
           "san cristobal de la laguna", "santa cruz detenerife": "santa cruz de tenerife", "calpe": "calp",
           "alcoy": "alcoi", "almazora": "almassora", "pamplona": "pamplona iruna"}

MIN_TOWN_POP = 15000   # the sheet lists towns over 25,000; a little margin for towns that shrank


def _names(name):
    out = set()
    for part in name.split("/"):
        n = normalise(part)
        out |= {n, ALIASES.get(n, n)}
    return out


def match_towns(towns, munis, provinces=None):
    """{code: (value, appraisals)} for the towns > 25,000, matched by name across the country.

    The sheet's province column is unreliable (wrapped, misspelt, misaligned), so it only breaks ties.
    """
    big = [(m, _names(m["name"])) for m in munis if (m.get("pop") or 0) >= MIN_TOWN_POP]
    matched, unmatched = {}, []
    for prov, town, value, n in towns:
        keys = _names(town)
        hit = [m for m, names in big if keys & names]
        if len(hit) > 1 and provinces:
            hit = [m for m in hit if m["code"][:2] == provinces.get(normalise(prov))] or hit
        if not hit:   # spelling variants (Almuñecar / Almuñécar handled above): closest name, strict
            scored = max(((difflib.SequenceMatcher(None, k, nm).ratio(), m) for m, names in big for k in keys
                          for nm in names), key=lambda x: x[0], default=(0, None))
            hit = [scored[1]] if scored[0] >= 0.85 else []
        if len(hit) == 1:
            matched[hit[0]["code"]] = (value, n)
        else:
            unmatched.append(f"{town} ({prov})")
    return matched, unmatched


# single-province regions appear only as region totals; matched by region name, since their CODAUTO is
# unreliable (Navarra is 15, Murcia blank)
SINGLE_PROVINCE_REGIONS = {"asturias": "33", "madrid": "28", "navarra": "31", "murcia": "30"}


def read_province_csv(text):
    """('2026 Q2', {cpro: €/m²}) for the latest quarter of free-market housing."""
    rows = []
    for r in csv.DictReader(io.StringIO(text.lstrip("\ufeff")), delimiter=";"):
        if r["Régimen"] != "Libre" or _num(r["Valor"]) is None:
            continue
        if r["CPRO"] in ("", "null"):
            # single-province regions (Madrid, Asturias, Murcia, Navarra) appear only as region totals
            region = normalise(r.get("Comunidad_Autónoma") or "").split(" ")[0]
            if r["Provincia"] != "Total CCAA" or region not in SINGLE_PROVINCE_REGIONS:
                continue
            r = dict(r, CPRO=SINGLE_PROVINCE_REGIONS[region])
        rows.append(r)
    last = max((int(r["Año"]), int(r["Trimestre"])) for r in rows)
    vals = {r["CPRO"].zfill(2): _num(r["Valor"]) for r in rows if (int(r["Año"]), int(r["Trimestre"])) == last}
    return f"{last[0]} Q{last[1]}", vals


def province_names(text):
    """{normalised province name: cpro} as the Ministry writes them."""
    return {normalise(r["Provincia"]): r["CPRO"].zfill(2)
            for r in csv.DictReader(io.StringIO(text.lstrip("\ufeff")), delimiter=";") if r["CPRO"] not in ("", "null")}


# ---- France ---------------------------------------------------------------------------------------

def read_anil(rows):
    """{code: (€/m² incl. charges, listings in the commune, scope)}: scope 3 where the prediction is weak."""
    from hospitals_fr import commune_of
    parts = {}
    for r in rows:
        v = _num(r.get("loypredm2"))
        if v is None:
            continue
        n = int(_num(r.get("nbobs_com")) or 0)
        r2 = _num(r.get("R2_adj")) or 0
        weak = r.get("TYPPRED") != "commune" or r2 < 0.5 or n < 30
        code = r["INSEE_C"]
        parts.setdefault(commune_of(code[:2], code[2:]), []).append((v, n, weak))
    out = {}
    for code, ps in parts.items():   # Paris, Lyon, Marseille: arrondissements, weighted by listings
        n = sum(x[1] for x in ps)
        v = sum(x[0] * x[1] for x in ps) / n if n else sum(x[0] for x in ps) / len(ps)
        weak_share = (sum(x[1] for x in ps if x[2]) / n) if n else 1
        out[code] = (round(v, 2), n, 3 if weak_share > 0.5 or n < 30 else 0)
    return out


def read_dvf(rows):
    """{code: {"bh": (median €/m², sales), "bf": ...}} for communes with at least MIN_SALES sales."""
    out = {}
    for r in rows:
        if r.get("echelle_geo") != "commune":
            continue
        got = {}
        for key, kind in (("bh", "maison"), ("bf", "appartement")):
            n = int(_num(r.get(f"nb_ventes_whole_{kind}")) or 0)
            v = _num(r.get(f"med_prix_m2_whole_{kind}"))
            if v is not None and n >= MIN_SALES and PLAUSIBLE_EUR_M2[0] <= v <= PLAUSIBLE_EUR_M2[1]:
                got[key] = (v, n)
        if got:
            out[r["code_geo"]] = got
    return out


# ---- shared ---------------------------------------------------------------------------------------

def pool_nearby(points, own, min_count, km=NEARBY_KM):
    """{code: (value, count)} for points without an own value: count-weighted mean of own values within km."""
    cell = 0.1
    grid = {}
    for c, (val, n) in own.items():
        if c in points:
            lng, lat = points[c]
            grid.setdefault((math.floor(lng / cell), math.floor(lat / cell)), []).append((c, val, n))
    out = {}
    for c, (lng, lat) in points.items():
        if c in own:
            continue
        rx = math.ceil(km / (111.32 * math.cos(math.radians(lat)) * cell)) + 1
        ry = math.ceil(km / (111.32 * cell)) + 1
        gx, gy = math.floor(lng / cell), math.floor(lat / cell)
        s = n_tot = 0
        for x in range(gx - rx, gx + rx + 1):
            for y in range(gy - ry, gy + ry + 1):
                for c2, val, n in grid.get((x, y), ()):
                    plng, plat = points[c2]
                    if haversine_km(lat, lng, plat, plng) <= km:
                        s += val * n
                        n_tot += n
        if n_tot >= min_count:
            out[c] = (round(s / n_tot, 2), n_tot)
    return out


def build_output(places, values, params):
    """values: {code: {key: (value, count, scope)}} -> JSON with rows
    [rent_house, rent_flat, buy_house, buy_flat, scope x4, count x4, population]."""
    m = {}
    for mu in places["municipalities"]:
        v = values.get(mu["code"], {})
        row_v, row_s, row_n = [], [], []
        for k in KEYS:
            got = v.get(k)
            if got is None:
                row_v.append(None), row_s.append(None), row_n.append(None)
                continue
            val = round(got[0], 1) if k.startswith("r") else int(round(got[0], -1))
            row_v.append(val), row_s.append(got[2]), row_n.append(got[1])
        m[mu["code"]] = row_v + row_s + row_n + [mu.get("pop")]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "params": dict(params, nearby_km=NEARBY_KM, population_year=places["meta"].get("population_year")),
        # code -> [rent_house, rent_flat, buy_house, buy_flat, s_rh, s_rf, s_bh, s_bf, n_rh, n_rf, n_bh, n_bf, population]
        # €/m² (rent per month); scope 0 own, 1 nearby, 2 province average, 3 area model; count = leases/listings/sales
        "m": m,
    }


def housing_csv_rows(output, munis):
    header = ["code", "name", "province", "population", "rent_house", "rent_flat", "buy_house", "buy_flat",
              "rent_house_source", "rent_flat_source", "buy_house_source", "buy_flat_source",
              "rent_house_n", "rent_flat_n", "buy_house_n", "buy_flat_n"]
    rows = []
    for mu in munis:
        r = output["m"].get(mu["code"]) or [None] * 13
        rows.append([mu["code"], mu["name"], mu.get("province"), mu.get("pop")] + r[0:4]
                    + [SCOPE_NAMES.get(s) if s is not None else None for s in r[4:8]] + r[8:12])
    return header, rows


def download(url, dest):
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "remoteness-map-pipeline/1.0"})
        with urllib.request.urlopen(req, timeout=600) as r, open(dest, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
    return dest


def merge(values, key, got, scope=None):
    for c, t in got.items():
        values.setdefault(c, {})[key] = t if scope is None else (t[0], t[1], scope)


def run_es(p, places):
    import openpyxl
    import xlrd
    munis = places["municipalities"]
    wb = openpyxl.load_workbook(download(SERPAVI_URL, p.housing_cache / "serpavi.xlsx"), read_only=True)
    rows = wb["Municipios"].iter_rows(values_only=True)
    rent = read_serpavi(list(next(rows)), rows)
    values, years = {}, set()
    for key in ("rh", "rf"):
        own = {c: (v[key][0], v[key][1]) for c, v in rent.items() if key in v}
        years |= {v[key][2] for v in rent.values() if key in v}
        merge(values, key, own, 0)
        pts = {m["code"]: (m["lng"], m["lat"]) for m in munis}
        merge(values, key, pool_nearby(pts, own, MIN_LEASES), 1)
    prov_text = download(APPRAISAL_PROVINCES_URL, p.housing_cache / "appraisal_provinces.csv").read_text(encoding="utf-8-sig")
    period, prov = read_province_csv(prov_text)
    book = xlrd.open_workbook(str(download(APPRAISAL_TOWNS_URL, p.housing_cache / "appraisal_towns.xls")))
    sheet = book.sheet_by_name(book.sheet_names()[-1])
    towns, unmatched = match_towns(read_appraisal_sheet([sheet.row_values(i) for i in range(sheet.nrows)]),
                                   munis, province_names(prov_text))
    for m in munis:
        if m["code"] in towns:
            val, n, scope = towns[m["code"]][0], towns[m["code"]][1], 0
        elif m["code"][:2] in prov:
            val, n, scope = prov[m["code"][:2]], None, 2
        else:
            continue
        for key in ("bh", "bf"):
            values.setdefault(m["code"], {})[key] = (val, n, scope)
    if unmatched:
        print(f"{len(unmatched)} appraisal towns not matched: {', '.join(unmatched)}")
    notes = ["Rent: median of declared leases (SERPAVI), latest year 2022-2024 with at least 10 leases.",
             f"Buy: appraisal value of free-market housing ({period}), for towns over 25,000 inhabitants; elsewhere "
             "the province average. A coarse guide: villages are usually cheaper than their province."]
    return values, {"sources": ["SERPAVI 2011-2024 (MIVAU)", f"Valor tasado de vivienda {period} (MIVAU)"],
                    "buy_all_dwellings": True,
                    "rent_years": sorted(years), "buy_period": period, "notes": notes,
                    "unmatched_towns": unmatched}


def run_fr(p, places):
    munis = places["municipalities"]
    values = {}
    for key, url in ANIL_URLS.items():
        f = download(url, p.housing_cache / url.rsplit("/", 1)[1])
        merge(values, key, read_anil(csv.DictReader(io.StringIO(f.read_text(encoding="latin-1")), delimiter=";")))
    with open(download(DVF_URL, p.housing_cache / "dvf_stats_whole_period.csv"), encoding="utf-8") as fh:
        dvf = read_dvf(csv.DictReader(fh))
    pts = {m["code"]: (m["lng"], m["lat"]) for m in munis if m["code"][:2] not in NO_DVF}
    for key in ("bh", "bf"):
        own = {c: v[key] for c, v in dvf.items() if key in v}
        merge(values, key, own, 0)
        merge(values, key, pool_nearby(pts, own, MIN_SALES), 1)
    notes = ["Rent: advertised rents including charges, ANIL 2025 (leboncoin and SeLoger listings). Hatched where "
             "the commune has few listings and the figure comes from its area.",
             "Buy: median price per m² of sales recorded in DVF over the last 5 years. No DVF in Alsace-Moselle "
             "(Bas-Rhin, Haut-Rhin, Moselle)."]
    return values, {"sources": ["Carte des loyers 2025 (ANIL)", "DVF statistics (Etalab)"], "notes": notes}


def main():
    ap = argparse.ArgumentParser()
    add_country_arg(ap)
    args = ap.parse_args()
    p = paths(args.country)
    places = load_json(p.places)
    values, params = (run_es if args.country == "es" else run_fr)(p, places)
    out = build_output(places, values, params)
    dump_json(out, p.housing_json, compact=True)
    write_csv(p.housing_csv, *housing_csv_rows(out, places["municipalities"]))
    n = {k: sum(1 for r in out["m"].values() if r[i] is not None) for i, k in enumerate(KEYS)}
    own = {k: sum(1 for r in out["m"].values() if r[4 + i] == 0) for i, k in enumerate(KEYS)}
    print(f"Wrote {p.housing_json} and {p.housing_csv.name}: values {n}, own figures {own}")


if __name__ == "__main__":
    main()
