"""Curated definition of "main city" tiers.

Codes are INE municipality codes (5 digits). Populations for the
"over 100k" and "over 50k" rules are refreshed from INE in
build_places.py; the lists below are the fixed, judgement-based part.

Tier 1  Metros:          the 6 municipalities over 500k inhabitants.
Tier 2  Regional hubs:   50 provincial capitals + Ceuta, Melilla,
                         Mérida and Santiago (regional capitals that are
                         not provincial capitals) + every municipality
                         over 100k. Suburbs over 100k stay destinations
                         but are labelled with their metro.
Tier 3  All urban areas: tier 2 + every municipality over 50k (the
                         Eurostat threshold for a Functional Urban Area
                         core city).

Tiers are nested: tier 1 is a subset of tier 2, which is a subset of tier 3.
"""

METROS = {
    "28079": "Madrid",
    "08019": "Barcelona",
    "46250": "València",
    "41091": "Sevilla",
    "50297": "Zaragoza",
    "29067": "Málaga",
}

PROVINCIAL_CAPITALS = {
    "15030": "A Coruña",
    "02003": "Albacete",
    "03014": "Alacant",
    "04013": "Almería",
    "05019": "Ávila",
    "06015": "Badajoz",
    "08019": "Barcelona",
    "48020": "Bilbao",
    "09059": "Burgos",
    "10037": "Cáceres",
    "11012": "Cádiz",
    "12040": "Castelló de la Plana",
    "13034": "Ciudad Real",
    "14021": "Córdoba",
    "16078": "Cuenca",
    "17079": "Girona",
    "18087": "Granada",
    "19130": "Guadalajara",
    "21041": "Huelva",
    "22125": "Huesca",
    "23050": "Jaén",
    "35016": "Las Palmas de Gran Canaria",
    "24089": "León",
    "25120": "Lleida",
    "26089": "Logroño",
    "27028": "Lugo",
    "28079": "Madrid",
    "29067": "Málaga",
    "30030": "Murcia",
    "32054": "Ourense",
    "33044": "Oviedo",
    "34120": "Palencia",
    "07040": "Palma",
    "31201": "Pamplona/Iruña",
    "36038": "Pontevedra",
    "37274": "Salamanca",
    "20069": "Donostia/San Sebastián",
    "38038": "Santa Cruz de Tenerife",
    "39075": "Santander",
    "40194": "Segovia",
    "41091": "Sevilla",
    "42173": "Soria",
    "43148": "Tarragona",
    "44216": "Teruel",
    "45168": "Toledo",
    "46250": "València",
    "47186": "Valladolid",
    "01059": "Vitoria-Gasteiz",
    "49275": "Zamora",
    "50297": "Zaragoza",
}

OTHER_REGIONAL_CAPITALS = {
    "51001": "Ceuta",
    "52001": "Melilla",
    "06083": "Mérida",
    "15078": "Santiago de Compostela",
}

# Non-capital municipalities over 100k inhabitants (INE padrón 2024).
# Used as a fallback when the live INE download fails; when it works,
# the >100k rule is applied to the fresh figures instead.
# Value: (name, metro it belongs to or None if it is its own hub).
OVER_100K_FALLBACK = {
    "36057": ("Vigo", None),
    "33024": ("Gijón", None),
    "08101": ("L'Hospitalet de Llobregat", "Barcelona"),
    "03065": ("Elx", None),
    "08015": ("Badalona", "Barcelona"),
    "30016": ("Cartagena", None),
    "08279": ("Terrassa", "Barcelona"),
    "11020": ("Jerez de la Frontera", None),
    "08187": ("Sabadell", "Barcelona"),
    "28092": ("Móstoles", "Madrid"),
    "28005": ("Alcalá de Henares", "Madrid"),
    "28058": ("Fuenlabrada", "Madrid"),
    "28074": ("Leganés", "Madrid"),
    "28065": ("Getafe", "Madrid"),
    "28007": ("Alcorcón", "Madrid"),
    "29069": ("Marbella", None),
    "41038": ("Dos Hermanas", "Sevilla"),
    "28148": ("Torrejón de Ardoz", "Madrid"),
    "28106": ("Parla", "Madrid"),
    "28006": ("Alcobendas", "Madrid"),
    "08121": ("Mataró", "Barcelona"),
    "08245": ("Santa Coloma de Gramenet", "Barcelona"),
    "43123": ("Reus", None),
    "35026": ("Telde", "Las Palmas de Gran Canaria"),
    "38023": ("San Cristóbal de La Laguna", "Santa Cruz de Tenerife"),
    "11004": ("Algeciras", None),
    "48013": ("Barakaldo", "Bilbao"),
    "04079": ("Roquetas de Mar", "Almería"),
    "28123": ("Rivas-Vaciamadrid", "Madrid"),
    "03133": ("Torrevieja", None),
}

# Metro labels for municipalities that may cross the 50k/100k line from
# fresh INE data. Keyed by INE province code: a destination in one of
# these provinces within METRO_RADIUS_KM of the metro core gets the label.
METRO_CORES = {
    "Madrid": ("28079", "28"),
    "Barcelona": ("08019", "08"),
    "València": ("46250", "46"),
    "Sevilla": ("41091", "41"),
    "Bilbao": ("48020", "48"),
    "Málaga": ("29067", "29"),
}
METRO_RADIUS_KM = 25
