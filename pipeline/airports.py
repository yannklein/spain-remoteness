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
the island names of data/places.json. Coordinates are the airport's public
transport stop from OpenStreetMap (named in the note as "stop: ..."): TravelTime
cannot attach a point inside a terminal to its walking network, so terminal
points came out unreachable even from the next town. Airports with no stop in
OSM keep their terminal point and may come out unreachable, which matches the
lack of a public transport link (Badajoz, Castellón, Salamanca, León...).

Routes were checked in November 2026 against airport/airline announcements
and the regional press for the winter 2026-27 and summer 2026 schedules.
"verify" in a note marks a tier set from incomplete evidence.
"""

# iata, name, country, lat, lng, tier_year, tier_summer, zone, note
AIRPORTS = [
    # --- Spain, mainland -------------------------------------------------
    ("ABC", "Albacete", "ES", 38.9485, -1.8635, None, None, "mainland",
     "no scheduled routes found for 2026 (verify)"),
    ("AGP", "Málaga-Costa del Sol", "ES", 36.67773, -4.49019, 1, 1, "mainland",
     "year: Air Transat YUL (~5,900 km); summer: United EWR, Gulf Air BAH; stop: Aeropuerto"),
    ("ALC", "Alicante-Elche", "ES", 38.28756, -0.55278, 2, 2, "mainland",
     "year: many UK/European routes; stop: Aeroport d'Alacant-Elx Miguel Hernández"),
    ("BCN", "Barcelona-El Prat", "ES", 41.28835, 2.07294, 1, 1, "mainland",
     "year: intercontinental hub; stop: Aeroport T1 - Arribades"),
    ("BIO", "Bilbao", "ES", 43.30539, -2.90561, 2, 1, "mainland",
     "year: European routes; summer: United EWR (~5,800 km); stop: Aireportua Irteerak"),
    ("BJZ", "Badajoz", "ES", 38.8913, -6.8213, 3, 3, "mainland",
     "year: Air Nostrum MAD/BCN, Binter Canarias"),
    ("CDT", "Castellón", "ES", 40.2139, 0.0733, 2, 2, "mainland",
     "year: Ryanair STN, CRL, OTP, CLJ (non-AENA)"),
    ("CQM", "Ciudad Real", "ES", 38.8564, -3.9700, None, None, "mainland",
     "no scheduled passenger flights (private, non-AENA)"),
    ("EAS", "San Sebastián", "ES", 43.35685, -1.79308, 3, 2, "mainland",
     "year: MAD/BCN; Volotea Florence from Sep 2026 (verify if year-round); stop: Aireportua"),
    ("GRO", "Girona-Costa Brava", "ES", 41.89651, 2.76609, 2, 2, "mainland",
     "year: Ryanair European routes; stop: Aeroport de Girona"),
    ("GRX", "Granada-Jaén", "ES", 37.19105, -3.77580, 2, 2, "mainland",
     "year: Wizz Air London (Jul 2026), Volotea Porto (verify winter); stop: unnamed bus stop"),
    ("HSK", "Huesca-Pirineos", "ES", 42.0761, -0.3164, None, None, "mainland",
     "no scheduled passenger flights"),
    ("ILD", "Lleida-Alguaire", "ES", 41.72893, 0.54309, 3, 2, "mainland",
     "year: Air Nostrum PMI; seasonal: Jet2 UK (non-AENA); stop: Aeroport"),
    ("LCG", "A Coruña", "ES", 43.30311, -8.38158, 2, 2, "mainland",
     "year: Milan 2x weekly (verify); stop: Aeroporto da Coruña"),
    ("LEI", "Almería", "ES", 36.84835, -2.37116, 3, 2, "mainland",
     "year: domestic + Binter; summer: Jet2 STN; Luton route ended Oct 2026; stop: Parada de ALSA Aeropuerto Almeria"),
    ("LEN", "León", "ES", 42.58900, -5.65194, 3, 3, "mainland",
     "year: Vueling BCN; point moved 300 m to attach to TravelTime's network"),
    ("LEU", "Andorra-La Seu d'Urgell", "ES", 42.33860, 1.41649, 3, 3, "mainland",
     "year: Air Nostrum MAD/PMI 2x weekly; contract ends 1 Jan 2027; point moved 600 m to attach to TravelTime's network"),
    ("MAD", "Madrid-Barajas", "ES", 40.46791, -3.57176, 1, 1, "mainland",
     "year: intercontinental hub; stop: Aeropuerto T1-T2-T3"),
    ("MJV", "Murcia-San Javier", "ES", 37.7750, -0.8124, None, None, "mainland",
     "closed to civil traffic since 2019 (replaced by RMU)"),
    ("ODB", "Córdoba", "ES", 37.84464, -4.84332, 3, 3, "mainland",
     "year: Binter Canarias; stop: Aeropuerto (Terminal)"),
    ("OVD", "Asturias", "ES", 43.55862, -6.03127, 3, 2, "mainland",
     "Ryanair left in 2026; seasonal KLM AMS (verify year-round European routes); stop: unnamed bus stop"),
    ("PNA", "Pamplona", "ES", 42.76982, -1.63719, 3, 3, "mainland",
     "year: domestic only; 2025 international tender got no bids; stop: Aeropuerto de Pamplona - Noáin; point moved 300 m to attach to TravelTime's network"),
    ("REU", "Reus", "ES", 41.14720, 1.15231, 2, 2, "mainland",
     "mostly seasonal UK routes (verify winter service); stop: Aeroport"),
    ("RGS", "Burgos", "ES", 42.3576, -3.6207, None, None, "mainland",
     "no scheduled passenger flights in 2026"),
    ("RJL", "Logroño-Agoncillo", "ES", 42.45597, -2.31551, 3, 3, "mainland",
     "year: MAD, Vueling BCN; summer: Binter LPA, PMI; stop: Aeropuerto Agoncillo"),
    ("RMU", "Región de Murcia", "ES", 37.80427, -1.13251, 2, 2, "mainland",
     "year: UK routes; stop: Aeropuerto Internacional Región de Murcia"),
    ("SCQ", "Santiago-Rosalía de Castro", "ES", 42.89188, -8.42174, 2, 1, "mainland",
     "year: European routes (verify); summer: United EWR from May 2026; stop: Aeroporto"),
    ("SDR", "Santander", "ES", 43.42330, -3.82536, 2, 2, "mainland",
     "year: Ryanair STN, CRL, DUB (after 2025 cuts); stop: Aeropuerto de Santander"),
    ("SLM", "Salamanca", "ES", 40.9521, -5.5020, None, 3, "mainland",
     "summer only: Volotea PMI"),
    ("SVQ", "Sevilla", "ES", 37.42381, -5.89983, 2, 2, "mainland",
     "year: European routes; stop: Autobús aeropuerto"),
    ("TEV", "Teruel", "ES", 40.4120, -1.2183, None, None, "mainland",
     "aircraft storage/MRO, no passenger flights"),
    ("VGO", "Vigo", "ES", 42.22597, -8.63288, 3, 3, "mainland",
     "no route outside Spain since Ryanair left London in Jan 2026; stop: Aeroporto de Peinador"),
    ("VIT", "Vitoria", "ES", 42.88411, -2.73083, 2, 2, "mainland",
     "year: Ryanair CRL, BGY (verify winter); stop: Aeropuerto"),
    ("VLC", "Valencia", "ES", 39.49219, -0.47437, 2, 2, "mainland",
     "year: European routes; stop: Aeroport"),
    ("VLL", "Valladolid", "ES", 41.70609, -4.84452, 3, 3, "mainland",
     "year: Vueling BCN, Binter LPA/TFN; stop: Aeropuerto (Salidas)"),
    ("XRY", "Jerez", "ES", 36.75124, -6.06633, 2, 2, "mainland",
     "year: Eurowings BER/HAM through winter 2026-27; stop: Aeropuerto de Jerez"),
    ("ZAZ", "Zaragoza", "ES", 41.66297, -1.00682, 2, 2, "mainland",
     "year: Ryanair European routes; stop: Aeropuerto - Terminal"),
    # --- Spain, Melilla and islands -------------------------------------
    ("MLN", "Melilla", "ES", 35.2798, -2.9563, 3, 3, "melilla",
     "year: MAD, AGP, ALC, SVQ..."),
    ("ACE", "Lanzarote", "ES", 28.95135, -13.60864, 2, 2, "island:Lanzarote",
     "year: UK/European routes; stop: Aeropuerto T1"),
    ("FUE", "Fuerteventura", "ES", 28.45234, -13.86991, 2, 2, "island:Fuerteventura",
     "year: UK/European routes; stop: Aeropuerto"),
    ("GMZ", "La Gomera", "ES", 28.0296, -17.2146, 3, 3, "island:La Gomera",
     "year: Binter TFN"),
    ("IBZ", "Eivissa", "ES", 38.87708, 1.36886, 2, 2, "island:Eivissa",
     "year: European routes (verify winter); stop: Aeroport (arribades)"),
    ("LPA", "Gran Canaria", "ES", 27.93942, -15.39025, 2, 1, "island:Gran Canaria",
     "year: European routes; winter: Air Transat YUL/YYZ; stop: Aeropuerto Sur"),
    ("MAH", "Menorca", "ES", 39.86918, 4.23132, 2, 2, "island:Menorca",
     "year: London Gatwick in winter 2026-27; stop: Aeroport; point moved 600 m to attach to TravelTime's network"),
    ("PMI", "Palma de Mallorca", "ES", 39.54801, 2.72857, 2, 1, "island:Mallorca",
     "year: European routes; summer: United EWR, Etihad AUH; stop: Aeroport - Arribades"),
    ("SPC", "La Palma", "ES", 28.62180, -17.75242, 3, 2, "island:La Palma",
     "year: Binter; European routes mostly winter-only; stop: Aeropuerto"),
    ("TFN", "Tenerife Norte", "ES", 28.48796, -16.34534, 2, 1, "island:Tenerife",
     "year: Binter Portugal routes (verify); Plus Ultra CCS resumed Sep 2026; stop: Aeropuerto Norte"),
    ("TFS", "Tenerife Sur", "ES", 28.04859, -16.57682, 2, 1, "island:Tenerife",
     "year: UK/European routes; winter: Air Canada YYZ/YUL; stop: Aeropuerto Tenerife Sur"),
    ("VDE", "El Hierro", "ES", 27.81351, -17.88478, 3, 3, "island:El Hierro",
     "year: Binter TFN/LPA; stop: Aeropuerto"),
    # --- Foreign airports near the border --------------------------------
    ("BGC", "Bragança", "PT", 41.8578, -6.7071, None, None, "mainland",
     "single domestic route, almost no transit access from Spain"),
    ("BIQ", "Biarritz", "FR", 43.47208, -1.53239, 2, 2, "mainland",
     "year: Ryanair/easyJet London through winter 2026-27 — no cross-border transit in TravelTime data (Nov 2026 check); stop: Aéroport de Biarritz - Bus TXIK TXAK"),
    ("FAO", "Faro", "PT", 37.02138, -7.96884, 2, 1, "mainland",
     "year: UK/European routes; summer: United EWR; winter: Air Transat YUL — no cross-border transit in TravelTime data (Nov 2026 check); stop: Aeroporto Faro"),
    ("GIB", "Gibraltar", "GI", 36.1512, -5.3497, 2, 2, "mainland",
     "year: London, Manchester, Bristol"),
    ("LDE", "Tarbes-Lourdes-Pyrénées", "FR", 43.18614, 0.00342, 2, 2, "mainland",
     "year: Ryanair STN in winter 2026-27, Volotea ORY; stop: Aéroport"),
    ("LIS", "Lisbon", "PT", 38.76823, -9.12833, 1, 1, "mainland",
     "year: intercontinental hub — no cross-border transit in TravelTime data (Nov 2026 check); stop: Lisboa (Aeroporto)"),
    ("OPO", "Porto", "PT", 41.23718, -8.66972, 1, 1, "mainland",
     "year: TAP/United/Air Transat transatlantic — no cross-border transit in TravelTime data (Nov 2026 check); stop: Aeroporto"),
    ("PGF", "Perpignan", "FR", 42.74093, 2.86706, 2, 2, "mainland",
     "year: Ryanair London/Brussels (verify winter) — no cross-border transit in TravelTime data (Nov 2026 check); stop: Aéroport"),
    ("PUF", "Pau-Pyrénées", "FR", 43.38212, -0.41327, 3, 3, "mainland",
     "year: domestic French routes (verify); stop: Aéroport Pau Pyrénées"),
    ("TLS", "Toulouse-Blagnac", "FR", 43.63095, 1.37447, 1, 1, "mainland",
     "year: Air Canada YUL (~5,500 km, verify winter), many European routes — no cross-border transit in TravelTime data (Nov 2026 check); stop: Aéroport"),
    ("VRL", "Vila Real", "PT", 41.2743, -7.7205, None, None, "mainland",
     "single domestic route, almost no transit access from Spain"),
]

# Shown on the page and stored in airports.json params.notes.
NOTES = [
    "Cross-border public transport to Portugal and France is missing from TravelTime's "
    "data (Nov 2026 check: no Spanish municipality reaches Lisbon, Porto, Faro, Biarritz, "
    "Perpignan or Toulouse), so those airports never come out nearest. Gibraltar works on foot.",
    "Some Spanish airports have no public transport link in TravelTime's data (Murcia-Corvera, "
    "Lleida-Alguaire, Castellón, Salamanca, El Hierro, La Gomera, Melilla) and never come out "
    "nearest. Where an airport bus is missing from the data, times are mostly walking (e.g. Maó).",
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
