"""Curated list of airports reachable from Spanish municipalities.

Tiers are nested (1 is a subset of 2, which is a subset of 3):

Tier 1  Intercontinental: at least one scheduled route longer than 4,000 km
        (great-circle). Captures the Americas, the Gulf and Asia; leaves
        out Morocco, Turkey or Israel, which behave like European routes.
Tier 2  Europe: at least one scheduled route to another European country.
Tier 3  Any airport: any scheduled passenger flight, domestic included.

Each airport has two tiers:
  tier_year    counting only routes operated in both IATA seasons
  tier_summer  also counting seasonal routes (summer-only, or winter-only
               in the Canaries where winter is the high season)
None means "not a destination in that mode".

Excluded on purpose: airports without scheduled passenger flights (they are
kept below with both tiers None and the reason), heliports (Ceuta, Algeciras),
Moroccan airports next to Ceuta and Melilla (Tanger, Nador: restricted and
irregular border crossings, no reliable transit data).

`zone` follows common.zone(): "mainland", "melilla" or "island:<Name>" with
the island names of data/places.json. Coordinates are the passenger terminal
(or its rail/metro stop), not the runway.

Routes were checked in November 2026 against airport/airline announcements
and the regional press for the winter 2026-27 and summer 2026 schedules.
"verify" in a note marks a tier set from incomplete evidence.
"""

# iata, name, country, lat, lng, tier_year, tier_summer, zone, note
AIRPORTS = [
    # --- Spain, mainland -------------------------------------------------
    ("ABC", "Albacete", "ES", 38.9485, -1.8635, None, None, "mainland",
     "no scheduled routes found for 2026 (verify)"),
    ("AGP", "Málaga-Costa del Sol", "ES", 36.6782, -4.4991, 1, 1, "mainland",
     "year: Air Transat YUL (~5,900 km); summer: United EWR, Gulf Air BAH"),
    ("ALC", "Alicante-Elche", "ES", 38.2853, -0.5597, 2, 2, "mainland",
     "year: many UK/European routes"),
    ("BCN", "Barcelona-El Prat", "ES", 41.2887, 2.0731, 1, 1, "mainland",
     "year: intercontinental hub"),
    ("BIO", "Bilbao", "ES", 43.3015, -2.9106, 2, 1, "mainland",
     "year: European routes; summer: United EWR (~5,800 km)"),
    ("BJZ", "Badajoz", "ES", 38.8913, -6.8213, 3, 3, "mainland",
     "year: Air Nostrum MAD/BCN, Binter Canarias"),
    ("CDT", "Castellón", "ES", 40.2139, 0.0733, 2, 2, "mainland",
     "year: Ryanair STN, CRL, OTP, CLJ (non-AENA)"),
    ("CQM", "Ciudad Real", "ES", 38.8564, -3.9700, None, None, "mainland",
     "no scheduled passenger flights (private, non-AENA)"),
    ("EAS", "San Sebastián", "ES", 43.3565, -1.7906, 3, 2, "mainland",
     "year: MAD/BCN; Volotea Florence from Sep 2026 (verify if year-round)"),
    ("GRO", "Girona-Costa Brava", "ES", 41.9010, 2.7606, 2, 2, "mainland",
     "year: Ryanair European routes"),
    ("GRX", "Granada-Jaén", "ES", 37.1887, -3.7774, 2, 2, "mainland",
     "year: Wizz Air London (Jul 2026), Volotea Porto (verify winter)"),
    ("HSK", "Huesca-Pirineos", "ES", 42.0761, -0.3164, None, None, "mainland",
     "no scheduled passenger flights"),
    ("ILD", "Lleida-Alguaire", "ES", 41.7282, 0.5351, 3, 2, "mainland",
     "year: Air Nostrum PMI; seasonal: Jet2 UK (non-AENA)"),
    ("LCG", "A Coruña", "ES", 43.3021, -8.3773, 2, 2, "mainland",
     "year: Milan 2x weekly (verify)"),
    ("LEI", "Almería", "ES", 36.8439, -2.3701, 3, 2, "mainland",
     "year: domestic + Binter; summer: Jet2 STN; Luton route ended Oct 2026"),
    ("LEN", "León", "ES", 42.5890, -5.6556, 3, 3, "mainland",
     "year: Vueling BCN"),
    ("LEU", "Andorra-La Seu d'Urgell", "ES", 42.3386, 1.4092, 3, 3, "mainland",
     "year: Air Nostrum MAD/PMI 2x weekly; contract ends 1 Jan 2027"),
    ("MAD", "Madrid-Barajas", "ES", 40.4685, -3.5711, 1, 1, "mainland",
     "year: intercontinental hub"),
    ("MJV", "Murcia-San Javier", "ES", 37.7750, -0.8124, None, None, "mainland",
     "closed to civil traffic since 2019 (replaced by RMU)"),
    ("ODB", "Córdoba", "ES", 37.8420, -4.8488, 3, 3, "mainland",
     "year: Binter Canarias"),
    ("OVD", "Asturias", "ES", 43.5636, -6.0346, 3, 2, "mainland",
     "Ryanair left in 2026; seasonal KLM AMS (verify year-round European routes)"),
    ("PNA", "Pamplona", "ES", 42.7700, -1.6463, 3, 3, "mainland",
     "year: domestic only; 2025 international tender got no bids"),
    ("REU", "Reus", "ES", 41.1474, 1.1672, 2, 2, "mainland",
     "mostly seasonal UK routes (verify winter service)"),
    ("RGS", "Burgos", "ES", 42.3576, -3.6207, None, None, "mainland",
     "no scheduled passenger flights in 2026"),
    ("RJL", "Logroño-Agoncillo", "ES", 42.4609, -2.3222, 3, 3, "mainland",
     "year: MAD, Vueling BCN; summer: Binter LPA, PMI"),
    ("RMU", "Región de Murcia", "ES", 37.8030, -1.1250, 2, 2, "mainland",
     "year: UK routes"),
    ("SCQ", "Santiago-Rosalía de Castro", "ES", 42.8963, -8.4152, 2, 1, "mainland",
     "year: European routes (verify); summer: United EWR from May 2026"),
    ("SDR", "Santander", "ES", 43.4271, -3.8200, 2, 2, "mainland",
     "year: Ryanair STN, CRL, DUB (after 2025 cuts)"),
    ("SLM", "Salamanca", "ES", 40.9521, -5.5020, None, 3, "mainland",
     "summer only: Volotea PMI"),
    ("SVQ", "Sevilla", "ES", 37.4180, -5.8931, 2, 2, "mainland",
     "year: European routes"),
    ("TEV", "Teruel", "ES", 40.4120, -1.2183, None, None, "mainland",
     "aircraft storage/MRO, no passenger flights"),
    ("VGO", "Vigo", "ES", 42.2318, -8.6268, 3, 3, "mainland",
     "no route outside Spain since Ryanair left London in Jan 2026"),
    ("VIT", "Vitoria", "ES", 42.8828, -2.7245, 2, 2, "mainland",
     "year: Ryanair CRL, BGY (verify winter)"),
    ("VLC", "Valencia", "ES", 39.4893, -0.4816, 2, 2, "mainland",
     "year: European routes"),
    ("VLL", "Valladolid", "ES", 41.7061, -4.8519, 3, 3, "mainland",
     "year: Vueling BCN, Binter LPA/TFN"),
    ("XRY", "Jerez", "ES", 36.7446, -6.0601, 2, 2, "mainland",
     "year: Eurowings BER/HAM through winter 2026-27"),
    ("ZAZ", "Zaragoza", "ES", 41.6662, -1.0416, 2, 2, "mainland",
     "year: Ryanair European routes"),
    # --- Spain, Melilla and islands -------------------------------------
    ("MLN", "Melilla", "ES", 35.2798, -2.9563, 3, 3, "melilla",
     "year: MAD, AGP, ALC, SVQ..."),
    ("ACE", "Lanzarote", "ES", 28.9455, -13.6052, 2, 2, "island:Lanzarote",
     "year: UK/European routes"),
    ("FUE", "Fuerteventura", "ES", 28.4527, -13.8638, 2, 2, "island:Fuerteventura",
     "year: UK/European routes"),
    ("GMZ", "La Gomera", "ES", 28.0296, -17.2146, 3, 3, "island:La Gomera",
     "year: Binter TFN"),
    ("IBZ", "Eivissa", "ES", 38.8729, 1.3731, 2, 2, "island:Eivissa",
     "year: European routes (verify winter)"),
    ("LPA", "Gran Canaria", "ES", 27.9319, -15.3866, 2, 1, "island:Gran Canaria",
     "year: European routes; winter: Air Transat YUL/YYZ"),
    ("MAH", "Menorca", "ES", 39.8626, 4.2186, 2, 2, "island:Menorca",
     "year: London Gatwick in winter 2026-27"),
    ("PMI", "Palma de Mallorca", "ES", 39.5517, 2.7388, 2, 1, "island:Mallorca",
     "year: European routes; summer: United EWR, Etihad AUH"),
    ("SPC", "La Palma", "ES", 28.6265, -17.7556, 3, 2, "island:La Palma",
     "year: Binter; European routes mostly winter-only"),
    ("TFN", "Tenerife Norte", "ES", 28.4827, -16.3415, 2, 1, "island:Tenerife",
     "year: Binter Portugal routes (verify); Plus Ultra CCS resumed Sep 2026"),
    ("TFS", "Tenerife Sur", "ES", 28.0445, -16.5725, 2, 1, "island:Tenerife",
     "year: UK/European routes; winter: Air Canada YYZ/YUL"),
    ("VDE", "El Hierro", "ES", 27.8148, -17.8871, 3, 3, "island:El Hierro",
     "year: Binter TFN/LPA"),
    # --- Foreign airports near the border --------------------------------
    ("BGC", "Bragança", "PT", 41.8578, -6.7071, None, None, "mainland",
     "single domestic route, almost no transit access from Spain"),
    ("BIQ", "Biarritz", "FR", 43.4683, -1.5311, 2, 2, "mainland",
     "year: Ryanair/easyJet London through winter 2026-27"),
    ("FAO", "Faro", "PT", 37.0170, -7.9690, 2, 1, "mainland",
     "year: UK/European routes; summer: United EWR; winter: Air Transat YUL"),
    ("GIB", "Gibraltar", "GI", 36.1512, -5.3497, 2, 2, "mainland",
     "year: London, Manchester, Bristol"),
    ("LDE", "Tarbes-Lourdes-Pyrénées", "FR", 43.1787, -0.0064, 2, 2, "mainland",
     "year: Ryanair STN in winter 2026-27, Volotea ORY"),
    ("LIS", "Lisbon", "PT", 38.7681, -9.1286, 1, 1, "mainland",
     "year: intercontinental hub"),
    ("OPO", "Porto", "PT", 41.2370, -8.6700, 1, 1, "mainland",
     "year: TAP/United/Air Transat transatlantic"),
    ("PGF", "Perpignan", "FR", 42.7404, 2.8707, 2, 2, "mainland",
     "year: Ryanair London/Brussels (verify winter)"),
    ("PUF", "Pau-Pyrénées", "FR", 43.3800, -0.4186, 3, 3, "mainland",
     "year: domestic French routes (verify)"),
    ("TLS", "Toulouse-Blagnac", "FR", 43.6291, 1.3638, 1, 1, "mainland",
     "year: Air Canada YUL (~5,500 km, verify winter), many European routes"),
    ("VRL", "Vila Real", "PT", 41.2743, -7.7205, None, None, "mainland",
     "single domestic route, almost no transit access from Spain"),
]

FIELDS = ("iata", "name", "country", "lat", "lng", "tier_year", "tier_summer", "zone", "note")


def destinations():
    """Airports that are a destination in at least one mode, as dicts.

    `code` is prefixed so it never collides with 5-digit INE municipality codes.
    """
    out = []
    for a in AIRPORTS:
        d = dict(zip(FIELDS, a))
        if d["tier_year"] is None and d["tier_summer"] is None:
            continue
        d["code"] = "AIR:" + d["iata"]
        out.append(d)
    return out
