"""Foreign cities and airports reached through border stations ("gateways").

TravelTime barely routes across borders (see countries/<cc>_crossborder.py). For each country, a
gateway is a stop on the home side with a scheduled cross-border service. TravelTime measures the
trip to it like any destination; a hop adds the scheduled ride to the foreign city or airport plus
TRANSFER_MIN to change. The estimate counts only where it beats the measured time (if any) and stays
within the 3 h cap; via records which gateway it went through, so outputs can mark it as an estimate.
"""

import importlib

TRANSFER_MIN = 10   # minutes added at the gateway to change onto the cross-border service
GATEWAY_KM = 250    # origins searched around a gateway: 3 h minus the shortest useful hop
DIRECT_KM = 60      # foreign cities are also measured directly, for the rare links TravelTime has


def config(cc):
    """The country's countries/<cc>_crossborder module, or None if it has none."""
    name = f"countries.{cc}_crossborder"
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as e:
        if e.name != name:
            raise  # a broken import inside the config must not silently switch cross-border off
        return None


def gateway_city_tiers(cfg, locate, tier_of):
    """{gateway: tier of the home city it stands in, or None}. locate(lng, lat) -> municipality code."""
    out = {}
    for g, (_name, lat, lng) in (cfg.GATEWAYS.items() if cfg else []):
        code = locate(lng, lat)
        out[g] = tier_of(code) if code else None
    return out


def hops_for_tier(hops, city_tier, tier):
    """Hops usable for the nearest city of `tier`: not through a gateway inside a home city that already
    counts at that tier (the trip passes through it, so it is never the foreign city that is nearest)."""
    return [h for h in hops if not (city_tier.get(h[0]) and city_tier[h[0]] <= tier)]


def gateway_ids(cfg):
    return list(cfg.GATEWAYS) if cfg else []


def gateway_dests(cfg):
    return [{"code": f"GW:{g}", "name": name, "lat": lat, "lng": lng, "zone": "mainland", "max_km": GATEWAY_KM}
            for g, (name, lat, lng) in (cfg.GATEWAYS.items() if cfg else [])]


def foreign_city_dests(cfg):
    return [{"code": code, "name": name, "tier": tier, "lat": lat, "lng": lng, "pop": pop,
             "zone": "mainland", "max_km": DIRECT_KM, "urban": True}
            for code, (name, tier, lat, lng, pop) in (cfg.FOREIGN_CITIES.items() if cfg else [])]


def apply_hops(results, hops, muni_codes, max_seconds):
    """Add gateway estimates to results ({dest: {muni: seconds}}) in place; return {dest: {muni: gateway}}.

    Cached result dicts are copied before being changed.
    """
    via = {}
    for gw, dest, ride, _service, _source in hops:
        base = results.get(f"GW:{gw}", {})
        if dest not in via:
            results[dest] = dict(results.get(dest, {}))
            via[dest] = {}
        target, marks = results[dest], via[dest]
        extra = (ride + TRANSFER_MIN) * 60
        for m, t in base.items():
            if m not in muni_codes:
                continue
            est = t + extra
            if est <= max_seconds and est < target.get(m, max_seconds + 1):
                target[m] = est
                marks[m] = gw
    return via


def via_slots(rows, ordered, via, gateways, width=2):
    """{muni: None, or the gateway index per (minutes, destination index) slot, -1 where measured}."""
    gidx = {g: i for i, g in enumerate(gateways)}
    out = {}
    for m, row in rows.items():
        slots = []
        for k in range(0, len(row), width):
            i = row[k + 1]
            g = via.get(ordered[i]["code"], {}).get(m) if i >= 0 else None
            slots.append(gidx[g] if g is not None else -1)
        out[m] = slots if any(s >= 0 for s in slots) else None
    return out


def gateway_list(cfg):
    """[[id, name, lat, lng]] as written to the JSON outputs."""
    return [[g, name, lat, lng] for g, (name, lat, lng) in (cfg.GATEWAYS.items() if cfg else [])]
