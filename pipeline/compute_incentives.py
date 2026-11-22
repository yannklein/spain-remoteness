"""Incentives per municipality: tax breaks, grants and business exemptions (see countries/<cc>_incentives.py).

Spain: the offers' coverage comes from population rules or the official lists the tax agency links to
(PDFs read with `pdftotext -layout`, from poppler), Valencia's open data and Orden PRE/1/2025 for Cantabria.
France: the ministry's FRR / FRR+ commune list.
Usage: python pipeline/compute_incentives.py --country es|fr
"""

import argparse
import csv
import importlib
import io
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

from common import add_country_arg, dump_json, haversine_km, load_json, paths, write_csv
from compute_housing import _names, normalise

KINDS = ("tax", "grant", "business")
CLM_PROVINCES = {"ALBACETE", "CIUDAD REAL", "CUENCA", "GUADALAJARA", "TOLEDO"}


def _by_name(munis, prefixes):
    out = {}
    for m in munis:
        if m["code"][:2] in prefixes:
            for n in _names(m["name"]):
                out.setdefault(n, m["code"])
    return out


def parse_rango_x(text, munis):
    """{code: None (the municipality's own settlement is listed) or "partial"} for Aragón's Rango X list."""
    names = _by_name(munis, ("22", "44", "50"))
    seen, unmatched = {}, set()
    for line in text.split("\n"):
        parts = [p.strip() for p in re.split(r"\s{2,}", line.strip()) if p.strip()]
        if len(parts) != 3 or parts[2] not in ("HUESCA", "TERUEL", "ZARAGOZA"):
            continue
        settlement, muni = normalise(parts[0]), normalise(parts[1])
        code = names.get(muni)
        if code is None:
            unmatched.add(parts[1])
            continue
        own = settlement == muni or settlement in _names(parts[1])
        seen[code] = None if (own or seen.get(code, "partial") is None) else "partial"
    if unmatched:
        print(f"Rango X: {len(unmatched)} municipalities not matched: {sorted(unmatched)[:20]}", file=sys.stderr)
    return seen


def parse_concejos(text, munis):
    names = _by_name(munis, ("33",))
    out, unmatched = {}, []
    for line in text.split("\n"):
        parts = [p.strip() for p in re.split(r"\s{2,}", line.strip()) if p.strip()]
        if len(parts) == 2 and parts[1].startswith("Concejos"):
            code = names.get(normalise(parts[0]))
            if code:
                out[code] = None
            else:
                unmatched.append(parts[0])
    if unmatched:
        print(f"Asturias: concejos not matched: {unmatched}", file=sys.stderr)
    return out


def parse_clm(text):
    """{INE code: value} from a Castilla-La Mancha list (percentage or euros), best value per code, zeros dropped."""
    out = {}
    for line in text.split("\n"):
        if not any(p in line for p in CLM_PROVINCES):
            continue
        code = re.search(r"(?<!\d)(\d{5})(?!\d)", line)
        last = re.search(r"(\d+)\s*$", line)
        if code and last and int(last.group(1)) > 0 and last.start() != code.start():
            out[code.group(1)] = max(out.get(code.group(1), 0), int(last.group(1)))
    return out


def parse_valencia(text):
    csv.field_size_limit(sys.maxsize)
    return {r["cod_ine_mun"].zfill(5) for r in csv.DictReader(io.StringIO(text)) if r.get("fondo_coop_mun_2025") == "S"}


def parse_rioja(text):
    """INE codes of La Rioja's 'pequeños municipios' (first annex of its deductions in the tax manual)."""
    lines = text.split("\n")
    starts = [i for i, l in enumerate(lines) if l.strip().startswith("Anexo: Relación de municipios de La Rioja con")]
    start = next((i for i in starts if "pequeños municipios" in " ".join(lines[i:i + 6])), None)
    if start is None:
        return set()
    end = next((i for i in starts if i > start), len(lines))
    codes = set()
    for line in lines[start:end]:
        for c, _ in re.findall(r"(?<!\S)(\d{1,4})\s+([A-ZÁÉÍÓÚÑa-záéíóúñ][^\d]*)", line):
            codes.add("26" + f"{int(c) // 10:03d}")
    return codes


def covered(cover, provinces, munis, capitals):
    """Set of codes for the rule-based covers (pop_lt, pop_le, region, codes, cyl_rural)."""
    inside = [m for m in munis if m["code"][:2] in provinces]
    if "pop_lt" in cover:
        return {m["code"] for m in inside if (m.get("pop") or 0) < cover["pop_lt"]}
    if "pop_le" in cover:
        return {m["code"] for m in inside if (m.get("pop") or 0) <= cover["pop_le"]}
    if cover.get("region"):
        return {m["code"] for m in inside}
    if "codes" in cover:
        return set(cover["codes"]) & {m["code"] for m in inside}
    if cover.get("cyl_rural"):
        out = set()
        for m in inside:
            cap = capitals.get(m["code"][:2])
            near = cap and haversine_km(m["lat"], m["lng"], cap[0], cap[1]) < 30
            if (m.get("pop") or 0) <= (3000 if near else 10000):
                out.add(m["code"])
        return out
    raise ValueError(f"unknown cover {cover}")


def build_output(places, offers, cover, params):
    """cover: {offer id: {code: detail or None}} -> rows code -> [[offer index, detail], ...]."""
    m = {mu["code"]: [] for mu in places["municipalities"]}
    for i, o in enumerate(offers):
        for code, detail in sorted(cover.get(o["id"], {}).items()):
            if code in m:
                m[code].append([i, detail])
    keep = ("id", "kind", "region", "title", "amount", "conditions", "age_max", "valid", "source")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "params": params,
        # [id, kind, region, title, amount, conditions, age_max ("under N"), valid, source]
        "offers": [[o.get(k) for k in keep] for o in offers],
        # code -> [[offer index, detail for this municipality or null], ...]
        "m": m,
    }


def incentives_csv_rows(output, munis):
    header = ["code", "name", "province", "population", "n_tax", "n_grant", "n_business", "offers"]
    rows = []
    for mu in munis:
        got = output["m"].get(mu["code"], [])
        kinds = [output["offers"][i][1] for i, _ in got]
        rows.append([mu["code"], mu["name"], mu.get("province"), mu.get("pop")] + [kinds.count(k) for k in KINDS]
                    + ["; ".join(output["offers"][i][0] for i, _ in got)])
    return header, rows


def fetch(url, dest):
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "remoteness-map-pipeline/1.0"})
        with urllib.request.urlopen(req, timeout=300) as r:
            dest.write_bytes(r.read())
    return dest


def pdf_text(path):
    return subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, check=True).stdout.decode("utf-8", "replace")


def run_es(p, places, cfg):
    from cities import PROVINCIAL_CAPITALS
    munis = places["municipalities"]
    by_code = {m["code"]: m for m in munis}
    capitals = {c[:2]: (by_code[c]["lat"], by_code[c]["lng"]) for c in PROVINCIAL_CAPITALS if c in by_code}
    lists = {}
    for key, url in cfg.LISTS.items():
        f = fetch(url, p.incentives_cache / (key + (".csv" if key == "valencia_fund" else ".pdf")))
        if key == "valencia_fund":
            lists[key] = {c: None for c in parse_valencia(f.read_text(encoding="utf-8"))}
        elif key == "aragon_rango_x":
            lists[key] = {c: ("some of its settlements only" if d else None) for c, d in parse_rango_x(pdf_text(f), munis).items()}
        elif key == "asturias_concejos":
            lists[key] = parse_concejos(pdf_text(f), munis)
        elif key == "rioja_small":
            lists[key] = {c: None for c in parse_rioja(pdf_text(f))}
        elif key == "clm_residence":
            lists[key] = {c: f"{v}% here" for c, v in parse_clm(pdf_text(f)).items()}
        else:
            lists[key] = {c: None for c in parse_clm(pdf_text(f))}
    cover = {}
    for o in cfg.OFFERS:
        if "list" in o["cover"]:
            got = lists[o["cover"]["list"]]
            cover[o["id"]] = {c: d for c, d in got.items() if c[:2] in o["provinces"]}
        else:
            cover[o["id"]] = {c: None for c in covered(o["cover"], o["provinces"], munis, capitals)}
    return cover


def run_fr(p, places, cfg):
    import openpyxl
    wb = openpyxl.load_workbook(fetch(cfg.FRR_LIST, p.incentives_cache / "frr.xlsx"), read_only=True)
    cover = {o["id"]: {} for o in cfg.OFFERS}
    codes = {m["code"] for m in places["municipalities"]}
    for row in list(wb.worksheets[0].iter_rows(values_only=True))[1:]:
        code, cls = str(row[0]).zfill(5), row[3]
        offer = cfg.CLASSES.get(cls)
        if offer and code in codes:
            cover[offer][code] = "part of the commune only" if cls in cfg.PARTIAL else None
    return cover


def main():
    ap = argparse.ArgumentParser()
    add_country_arg(ap)
    args = ap.parse_args()
    p = paths(args.country)
    places = load_json(p.places)
    cfg = importlib.import_module(f"countries.{args.country}_incentives")
    cover = (run_es if args.country == "es" else run_fr)(p, places, cfg)
    out = build_output(places, cfg.OFFERS, cover, {"checked": "2026-11", "notes": (cfg.__doc__ or "").strip().split("\n\n")[0]})
    dump_json(out, p.incentives_json, compact=True)
    write_csv(p.incentives_csv, *incentives_csv_rows(out, places["municipalities"]))
    counts = {o["id"]: len(cover.get(o["id"], {})) for o in cfg.OFFERS}
    print(f"Wrote {p.incentives_json}: {counts}")


if __name__ == "__main__":
    main()
