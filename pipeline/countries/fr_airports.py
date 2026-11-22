"""Curated airports reachable from metropolitan France (same rules as Spain's list).

Tier 1  Intercontinental: at least one scheduled route longer than 4,000 km
        (incl. overseas France: Antilles, Réunion).
Tier 2  Europe: at least one scheduled route to another European country.
Tier 3  Any airport: any scheduled passenger flight.
tier_year counts routes operated in both IATA seasons; tier_summer also counts
seasonal ones (summer-only, or winter-only ski routes for Grenoble/Chambéry).

Foreign airports within reach of the border are listed (Geneva, Luxembourg,
Charleroi, Karlsruhe/Baden-Baden, Saarbrücken, Girona, San Sebastián,
Barcelona, and through border stations Zürich, Brussels, Frankfurt, Bilbao). Basel-Mulhouse (BSL) lies on French soil. Corsica is its own zone.

Coordinates are approximate terminal points; compute_airports' pre-check and
the stop/nudge step move them where TravelTime can't attach (see README).
Routes checked November 2026 from airport/airline announcements and press;
"verify" marks a tier set from incomplete evidence (Ryanair cut many French
regional routes in 2025-26).
"""

# iata, name, country, lat, lng, tier_year, tier_summer, zone, note
AIRPORTS = [
    # --- mainland France -------------------------------------------------
    ("AGF", "Agen-La Garenne", "FR", 44.1747, 0.5906, 3, 3, "mainland", "year: Paris-Orly"),
    ("AUR", "Aurillac", "FR", 44.8914, 2.4219, 3, 3, "mainland", "year: Paris-Orly (PSO)"),
    ("AVN", "Avignon-Provence", "FR", 43.9073, 4.9018, None, 2, "mainland", "seasonal UK routes (verify)"),
    ("BES", "Brest Bretagne", "FR", 48.4479, -4.4185, 2, 2, "mainland", "year: European routes (verify winter)"),
    ("BIQ", "Biarritz Pays Basque", "FR", 43.4683, -1.5311, 2, 2, "mainland", "year: London through winter 2026-27"),
    ("BOD", "Bordeaux-Mérignac", "FR", 44.8283, -0.7156, 1, 1, "mainland", "year: Air Transat Montréal (~5,600 km)"),
    ("BSL", "EuroAirport Basel-Mulhouse-Freiburg", "FR", 47.5996, 7.5291, 2, 2, "mainland", "year: European routes; on French soil"),
    ("BVA", "Paris-Beauvais", "FR", 49.4544, 2.1128, 2, 2, "mainland", "year: Ryanair/Wizz European routes"),
    ("BVE", "Brive-Vallée de la Dordogne", "FR", 45.0397, 1.4856, 3, 3, "mainland", "year: Paris-Orly; Ryanair left 2025"),
    ("BZR", "Béziers Cap d'Agde", "FR", 43.3235, 3.3539, 2, 2, "mainland", "Ryanair European routes (verify winter)"),
    ("CCF", "Carcassonne", "FR", 43.2160, 2.3063, 2, 2, "mainland", "Ryanair European routes (verify winter)"),
    ("CDG", "Paris-Charles de Gaulle", "FR", 49.0097, 2.5479, 1, 1, "mainland", "year: intercontinental hub"),
    ("CFE", "Clermont-Ferrand Auvergne", "FR", 45.7867, 3.1692, 2, 2, "mainland", "year: Amsterdam/Porto (verify)"),
    ("CFR", "Caen-Carpiquet", "FR", 49.1733, -0.4500, 3, 2, "mainland", "year: domestic; seasonal European"),
    ("CMF", "Chambéry-Savoie Mont Blanc", "FR", 45.6381, 5.8803, None, 2, "mainland", "winter-only ski routes (UK, NL)"),
    ("DCM", "Castres-Mazamet", "FR", 43.5563, 2.2892, 3, 3, "mainland", "year: Paris-Orly"),
    ("DLE", "Dole-Jura", "FR", 47.0427, 5.4351, 2, 2, "mainland", "Ryanair Porto/Morocco (verify)"),
    ("DNR", "Dinard-Pleurtuit-Saint-Malo", "FR", 48.5877, -2.0796, 2, 2, "mainland", "Ryanair London (verify winter)"),
    ("DOL", "Deauville-Normandie", "FR", 49.3653, 0.1543, None, 2, "mainland", "seasonal only (verify)"),
    ("EBU", "Saint-Étienne-Bouthéon", "FR", 45.5406, 4.2964, 3, 2, "mainland", "year: Algeria/Morocco? seasonal Porto (verify)"),
    ("EGC", "Bergerac-Dordogne-Périgord", "FR", 44.8253, 0.5186, None, 2, "mainland", "Ryanair left 2025; seasonal UK (verify)"),
    ("ETZ", "Metz-Nancy-Lorraine", "FR", 48.9821, 6.2513, 2, 2, "mainland", "year: Porto/Algeria (verify)"),
    ("FNI", "Nîmes-Alès-Camargue-Cévennes", "FR", 43.7574, 4.4163, 3, 2, "mainland", "winter: Fès/Marrakech only; summer: European"),
    ("GNB", "Grenoble Alpes-Isère", "FR", 45.3629, 5.3294, None, 2, "mainland", "winter-only ski routes (UK, NL)"),
    ("LDE", "Tarbes-Lourdes-Pyrénées", "FR", 43.1787, -0.0064, 2, 2, "mainland", "year: Ryanair London Stansted"),
    ("LIG", "Limoges-Bellegarde", "FR", 45.8628, 1.1794, 2, 2, "mainland", "Ryanair UK (verify winter)"),
    ("LIL", "Lille-Lesquin", "FR", 50.5633, 3.0897, 2, 2, "mainland", "year: European routes"),
    ("LPY", "Le Puy-Loudes", "FR", 45.0807, 3.7629, 3, 3, "mainland", "year: Paris-Orly (PSO)"),
    ("LRH", "La Rochelle-Île de Ré", "FR", 46.1792, -1.1953, 2, 2, "mainland", "UK routes (verify winter)"),
    ("LRT", "Lorient Bretagne Sud", "FR", 47.7606, -3.4400, 3, 3, "mainland", "domestic (verify)"),
    ("LYS", "Lyon-Saint Exupéry", "FR", 45.7256, 5.0811, 1, 1, "mainland", "year: Emirates Dubai (~5,200 km, verify)"),
    ("MPL", "Montpellier-Méditerranée", "FR", 43.5762, 3.9630, 2, 2, "mainland", "year: European routes"),
    ("MRS", "Marseille Provence", "FR", 43.4393, 5.2214, 2, 1, "mainland", "summer: Air Transat Montréal (verify)"),
    ("NCE", "Nice Côte d'Azur", "FR", 43.6584, 7.2159, 1, 1, "mainland", "year: Emirates Dubai (verify); summer: Delta Boston"),
    ("NTE", "Nantes Atlantique", "FR", 47.1532, -1.6107, 2, 1, "mainland", "summer: Air Transat Québec/Montréal"),
    ("ORY", "Paris-Orly", "FR", 48.7262, 2.3652, 1, 1, "mainland", "year: Air Caraïbes/French bee/Corsair long-haul"),
    ("PGF", "Perpignan-Rivesaltes", "FR", 42.7404, 2.8707, 2, 2, "mainland", "Ryanair UK/Belgium (verify winter)"),
    ("PIS", "Poitiers-Biard", "FR", 46.5877, 0.3066, 2, 2, "mainland", "Ryanair London (verify winter)"),
    ("PUF", "Pau-Pyrénées", "FR", 43.3800, -0.4186, 3, 3, "mainland", "domestic (verify)"),
    ("RDZ", "Rodez-Aveyron", "FR", 44.4079, 2.4827, 3, 3, "mainland", "year: Paris; Dublin dropped 2026"),
    ("RNS", "Rennes-Saint-Jacques", "FR", 48.0695, -1.7348, 2, 2, "mainland", "year: Amsterdam (verify)"),
    ("SXB", "Strasbourg-Entzheim", "FR", 48.5383, 7.6282, 2, 2, "mainland", "year: Amsterdam/Porto (verify); Ryanair left 2025"),
    ("TLN", "Toulon-Hyères", "FR", 43.0973, 6.1460, 3, 2, "mainland", "year: Paris; seasonal European"),
    ("TLS", "Toulouse-Blagnac", "FR", 43.6291, 1.3638, 1, 1, "mainland", "year: Air Canada Montréal (verify); Réunion from June 2026"),
    ("TUF", "Tours Val de Loire", "FR", 47.4322, 0.7276, 2, 2, "mainland", "Ryanair Porto/London (verify)"),
    ("UIP", "Quimper-Bretagne", "FR", 47.9750, -4.1678, 3, 3, "mainland", "year: Paris-Orly (verify)"),
    ("XCR", "Châlons-Vatry", "FR", 48.7733, 4.2061, None, 2, "mainland", "seasonal only (verify)"),
    ("LAI", "Lannion", "FR", 48.7544, -3.4716, None, None, "mainland", "no scheduled flights since 2018"),
    # --- Corsica ------------------------------------------------------------
    ("AJA", "Ajaccio Napoléon Bonaparte", "FR", 41.9236, 8.8029, 3, 2, "island:Corse", "year: mainland France; seasonal European"),
    ("BIA", "Bastia-Poretta", "FR", 42.5527, 9.4838, 3, 2, "island:Corse", "year: mainland France; seasonal European"),
    ("CLY", "Calvi-Sainte-Catherine", "FR", 42.5308, 8.7931, 3, 2, "island:Corse", "year: mainland France; seasonal European"),
    ("FSC", "Figari-Sud Corse", "FR", 41.5006, 9.0978, 3, 2, "island:Corse", "year: mainland France; seasonal European"),
    # --- foreign airports near the border -----------------------------------
    ("BCN", "Barcelona-El Prat", "ES", 41.28835, 2.07294, 1, 1, "mainland", "year: intercontinental hub"),
    ("CRL", "Brussels South Charleroi", "BE", 50.4592, 4.4538, 2, 2, "mainland", "year: European routes"),
    ("EAS", "San Sebastián", "ES", 43.35685, -1.79308, 3, 2, "mainland", "year: Madrid/Barcelona"),
    ("FKB", "Karlsruhe/Baden-Baden", "DE", 48.7794, 8.0805, 2, 2, "mainland", "year: European routes"),
    ("GRO", "Girona-Costa Brava", "ES", 41.89651, 2.76609, 2, 2, "mainland", "year: Ryanair European routes"),
    ("GVA", "Geneva", "CH", 46.2381, 6.1090, 1, 1, "mainland", "year: Emirates Dubai, Etihad; summer: United Newark"),
    ("LUX", "Luxembourg", "LU", 49.6266, 6.2115, 2, 2, "mainland", "year: European routes"),
    ("SCN", "Saarbrücken", "DE", 49.2146, 7.1095, 3, 2, "mainland", "year: Berlin/Hamburg; seasonal holiday routes"),
    # reached only through border stations (countries/fr_crossborder.py)
    ("ZRH", "Zürich", "CH", 47.4504, 8.5625, 1, 1, "mainland", "year: intercontinental hub"),
    ("BRU", "Brussels", "BE", 50.8986, 4.4840, 1, 1, "mainland", "year: intercontinental routes"),
    ("FRA", "Frankfurt", "DE", 50.0512, 8.5706, 1, 1, "mainland", "year: intercontinental hub"),
    ("BIO", "Bilbao", "ES", 43.3011, -2.9106, 2, 2, "mainland", "year: European routes"),
]

GATEWAY_ONLY = {"ZRH", "BRU", "FRA", "BIO"}

FIELDS = ("iata", "name", "country", "lat", "lng", "tier_year", "tier_summer", "zone", "note")

NOTES = [
    "Cross-border public transport is mostly missing from TravelTime's data (Nov 2026). Airports across the border "
    "are reached through border stations instead (Annemasse, Saint-Louis, Strasbourg, Forbach, Thionville, Lille, "
    "Hendaye, Perpignan…): the time to the station plus the scheduled train or bus ride and 10 min to change. Those "
    "times are estimates (hatched). Basel-Mulhouse lies on French soil and is measured.",
]

# (commune, airport) pairs printed after each run: cross-border links depend on TravelTime's data.
BORDER_CHECKS = [("74010", "GVA"), ("57463", "LUX"), ("59350", "CRL"), ("67482", "FKB"),
                 ("66136", "GRO"), ("64260", "EAS"), ("68224", "BSL")]


def destinations():
    out = []
    for a in AIRPORTS:
        d = dict(zip(FIELDS, a))
        if d["tier_year"] is None and d["tier_summer"] is None:
            continue
        d["code"] = "AIR:" + d["iata"]
        if d["iata"] in GATEWAY_ONLY:
            d["max_km"] = 60  # TravelTime can't reach them from France: border stations do (countries/fr_crossborder.py)
        out.append(d)
    return out
