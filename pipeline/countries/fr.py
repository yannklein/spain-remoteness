"""Metropolitan France: what differs from Spain.

Communes are INSEE codes (strings: "01001", "2A004"). Corsica is its own zone;
every other commune is mainland (ferries to small islands are left to TravelTime).
"""

NAME = "France"
BBOX = (-5.3, 41.3, 9.6, 51.15)  # lng/lat box around metropolitan France incl. Corsica

METRO_DEPARTMENTS = [f"{i:02d}" for i in range(1, 96) if i != 20] + ["2A", "2B"]

# Central communes of the 22 métropoles (by law), as (department, name).
METROPOLES = {
    ("75", "Paris"), ("13", "Marseille"), ("69", "Lyon"), ("31", "Toulouse"), ("06", "Nice"),
    ("44", "Nantes"), ("34", "Montpellier"), ("67", "Strasbourg"), ("33", "Bordeaux"), ("59", "Lille"),
    ("35", "Rennes"), ("38", "Grenoble"), ("76", "Rouen"), ("83", "Toulon"), ("42", "Saint-Étienne"),
    ("29", "Brest"), ("54", "Nancy"), ("37", "Tours"), ("63", "Clermont-Ferrand"), ("45", "Orléans"),
    ("21", "Dijon"), ("57", "Metz"),
}

# Préfecture of each metropolitan department, as (department, name).
PREFECTURES = {
    ("01", "Bourg-en-Bresse"), ("02", "Laon"), ("03", "Moulins"), ("04", "Digne-les-Bains"), ("05", "Gap"),
    ("06", "Nice"), ("07", "Privas"), ("08", "Charleville-Mézières"), ("09", "Foix"), ("10", "Troyes"),
    ("11", "Carcassonne"), ("12", "Rodez"), ("13", "Marseille"), ("14", "Caen"), ("15", "Aurillac"),
    ("16", "Angoulême"), ("17", "La Rochelle"), ("18", "Bourges"), ("19", "Tulle"), ("2A", "Ajaccio"),
    ("2B", "Bastia"), ("21", "Dijon"), ("22", "Saint-Brieuc"), ("23", "Guéret"), ("24", "Périgueux"),
    ("25", "Besançon"), ("26", "Valence"), ("27", "Évreux"), ("28", "Chartres"), ("29", "Quimper"),
    ("30", "Nîmes"), ("31", "Toulouse"), ("32", "Auch"), ("33", "Bordeaux"), ("34", "Montpellier"),
    ("35", "Rennes"), ("36", "Châteauroux"), ("37", "Tours"), ("38", "Grenoble"), ("39", "Lons-le-Saunier"),
    ("40", "Mont-de-Marsan"), ("41", "Blois"), ("42", "Saint-Étienne"), ("43", "Le Puy-en-Velay"),
    ("44", "Nantes"), ("45", "Orléans"), ("46", "Cahors"), ("47", "Agen"), ("48", "Mende"), ("49", "Angers"),
    ("50", "Saint-Lô"), ("51", "Châlons-en-Champagne"), ("52", "Chaumont"), ("53", "Laval"), ("54", "Nancy"),
    ("55", "Bar-le-Duc"), ("56", "Vannes"), ("57", "Metz"), ("58", "Nevers"), ("59", "Lille"),
    ("60", "Beauvais"), ("61", "Alençon"), ("62", "Arras"), ("63", "Clermont-Ferrand"), ("64", "Pau"),
    ("65", "Tarbes"), ("66", "Perpignan"), ("67", "Strasbourg"), ("68", "Colmar"), ("69", "Lyon"),
    ("70", "Vesoul"), ("71", "Mâcon"), ("72", "Le Mans"), ("73", "Chambéry"), ("74", "Annecy"),
    ("75", "Paris"), ("76", "Rouen"), ("77", "Melun"), ("78", "Versailles"), ("79", "Niort"), ("80", "Amiens"),
    ("81", "Albi"), ("82", "Montauban"), ("83", "Toulon"), ("84", "Avignon"), ("85", "La Roche-sur-Yon"),
    ("86", "Poitiers"), ("87", "Limoges"), ("88", "Épinal"), ("89", "Auxerre"), ("90", "Belfort"),
    ("91", "Évry-Courcouronnes"), ("92", "Nanterre"), ("93", "Bobigny"), ("94", "Créteil"), ("95", "Cergy"),
}

VIEWS = {"metropole": [[-5.3, 41.3], [9.6, 51.15]], "corse": [[8.5, 41.3], [9.6, 43.1]]}


def zone_of(dep):
    return "island:Corse" if dep in ("2A", "2B") else "mainland"
