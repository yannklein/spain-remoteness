"""Cities and airports across Spain's borders, reached through border stations ("gateways").

TravelTime does not route into Portugal, France or Andorra from Spain (Nov 2026 probe: no station
across the border is reachable, not even Hendaye on foot from Irun). So each foreign destination is
reached as: TravelTime time to a Spanish gateway stop + the scheduled ride from it (HOPS) + 10 min to
change (crossborder.TRANSFER_MIN). Ride times are the fastest regular weekday service; "verify"
marks a time taken from general knowledge of the line rather than a timetable checked in Nov 2026.
Lisbon is left out: no public transport reaches it from Spain within 3 h; so is Puigcerdà→Toulouse (2 h 44 by
TER plus the change is over the cap).
"""

# id: (name, lat, lng) - the stop a hop starts from, on the Spanish side
GATEWAYS = {
    "irun": ("Irun station", 43.33921, -1.80058),
    "figueres-vilafant": ("Figueres-Vilafant station", 42.2647, 2.94268),
    "portbou": ("Portbou station", 42.42469, 3.15781),
    "puigcerda": ("Puigcerdà station", 42.42955, 1.92483),
    "la-seu": ("La Seu d'Urgell bus station", 42.3597, 1.45998),
    "vigo": ("Vigo-Urzáiz bus station", 42.2353, -8.7128),
    "tui": ("Tui, international bridge", 42.03686, -8.64752),
    "badajoz": ("Badajoz bus station", 38.86672, -6.97436),
    "huelva": ("Huelva bus station", 37.2577, -6.9530),
    "sevilla": ("Sevilla Plaza de Armas bus station", 37.39185, -6.00392),
    "ayamonte": ("Ayamonte ferry pier", 37.2097, -7.4062),
    "salamanca": ("Salamanca bus station", 40.96992, -5.67596),
}

# code: (name, tier, lat, lng, population) - tiers by Spain's rule (capitals and >100k: 2; >500k: 1; >50k: 3)
FOREIGN_CITIES = {
    "FR:toulouse": ("Toulouse", 1, 43.6114, 1.45365, 511_000),
    "FR:bordeaux": ("Bordeaux", 2, 44.82582, -0.55607, 261_000),
    "FR:perpignan": ("Perpignan", 2, 42.69620, 2.87900, 120_000),
    "FR:pau": ("Pau", 2, 43.29182, -0.36881, 77_000),
    "FR:tarbes": ("Tarbes", 2, 43.2412, 0.0702, 42_000),
    "FR:foix": ("Foix", 2, 42.9686, 1.6064, 10_000),
    "FR:bayonne": ("Bayonne", 3, 43.49676, -1.47045, 52_000),
    "AD:andorra-la-vella": ("Andorra la Vella", 2, 42.50476, 1.52145, 24_000),
    "PT:porto": ("Porto", 2, 41.14874, -8.58546, 232_000),
    "PT:braga": ("Braga", 2, 41.54881, -8.4341, 193_000),
    "PT:viana-do-castelo": ("Viana do Castelo", 2, 41.6943, -8.8297, 85_000),
    "PT:faro": ("Faro", 2, 37.0193, -7.9399, 67_000),
    "PT:evora": ("Évora", 2, 38.56802, -7.91758, 53_000),
    "PT:guarda": ("Guarda", 2, 40.5376, -7.2688, 40_000),
}

# (gateway, destination code, ride minutes, service, source)
HOPS = [
    ("irun", "FR:bayonne", 50, "walk/Euskotren to Hendaye + TER", "verify"),
    ("irun", "AIR:BIQ", 60, "Hendaye TER to Biarritz + airport bus", "verify"),
    ("irun", "FR:pau", 130, "Hendaye TER, change at Bayonne", "verify"),
    ("irun", "FR:tarbes", 165, "Hendaye TER, change at Bayonne", "verify"),
    ("irun", "FR:bordeaux", 145, "Hendaye TER/TGV", "verify"),
    ("figueres-vilafant", "FR:perpignan", 25, "AVE/TGV", "verify"),
    ("figueres-vilafant", "AIR:PGF", 55, "AVE/TGV to Perpignan + airport bus", "verify"),
    ("figueres-vilafant", "FR:toulouse", 150, "AVE/TGV, change at Narbonne", "verify"),
    ("portbou", "FR:perpignan", 50, "TER Portbou-Cerbère-Perpignan", "verify"),
    ("puigcerda", "FR:foix", 100, "Rodalies R3 to Latour-de-Carol + TER (1h26-1h40)", "SNCF timetable 2026"),
    ("la-seu", "AD:andorra-la-vella", 33, "Hife bus, about hourly", "Hife timetable via aggregators 2026"),
    ("vigo", "PT:porto", 125, "Alsa/Autna bus (Celta train replaced by bus to Valença until Apr 2027)", "aggregators 2026"),
    ("vigo", "AIR:OPO", 115, "Alsa/Autna bus to Porto airport (1h55)", "aggregators 2026"),
    ("vigo", "PT:braga", 95, "bus", "verify"),
    ("tui", "PT:viana-do-castelo", 75, "walk the bridge to Valença + CP regional", "verify"),
    ("tui", "PT:porto", 155, "walk the bridge to Valença + CP regional", "verify"),
    ("huelva", "PT:faro", 85, "Alsa/FlixBus (1h20-1h30)", "aggregators 2026"),
    ("huelva", "AIR:FAO", 90, "Alsa to Faro airport (1h27)", "aggregators 2026"),
    ("sevilla", "PT:faro", 165, "Alsa/FlixBus (2h43)", "aggregators 2026"),
    ("sevilla", "AIR:FAO", 160, "Alsa to Faro airport (2h30-2h59)", "aggregators 2026"),
    ("ayamonte", "PT:faro", 95, "ferry to Vila Real de Santo António + CP Algarve line", "verify"),
    ("badajoz", "PT:evora", 75, "Alsa/FlixBus (1h14)", "aggregators 2026"),
    ("salamanca", "PT:guarda", 110, "Alsa/Internorte bus (1h44)", "aggregators 2026"),
]
