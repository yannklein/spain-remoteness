# Setting: green and picturesque

Date: 2026-11-23 · Status: approved 2026-11-23 ("both", "go ahead")

## Intent
The remote worker wants a small town or village with plenty of green in and around it, and a picturesque place:
an old village with character *and* a beautiful setting ("both"). "Picturesque" is subjective, so the map gives
separate signals to combine on the gems map, never one beauty score.

## Signals (per municipality, around the town centre)

| View | Signal | Source |
|---|---|---|
| **Green** | Nature % within 3 km: tree cover, shrubland, grassland, wetland, mangroves, moss | ESA WorldCover 2021, read at 80 m (CC BY 4.0) |
| | July greenness: mean NDVI within 3 km, July 2021-2025 | MODIS MOD13A1/MYD13A1 500 m, NASA, via the Planetary Computer |
| **Setting** | Relief: highest minus lowest point within 5 km; elevation | Copernicus DEM GLO-90 |
| | Water: % within 3 km (lakes, wide rivers, sea) | WorldCover |
| **Character, Spain** | Los Pueblos más Bonitos | The association's list |
| | Conjunto histórico; BIC count | Wikidata |
| **Character, France** | Plus Beaux Villages | data.gouv, 2026 |
| | Petites Cités de Caractère | data.gouv, 2023 |
| | Sites patrimoniaux remarquables | AC4 easements, Géoportail de l'Urbanisme |
| | Monuments historiques count | Mérimée |

## Map and gems
- **Setting map:**
  - buttons Green | Character | Setting;
  - a checkbox "How green in July instead" on the Green view;
  - character is categorical: label > protected historic centre > 5+ listed buildings > 1-4 > none.
- **Gems criteria, all off by default:**
  - nature ≥ X%;
  - July NDVI ≥ X;
  - relief ≥ X m;
  - "character" (a label or a protected historic centre);
  - "water nearby" (≥ 1% water within 3 km).

## Left out (calls made during the build)
- **Flower towns (Villes et Villages Fleuris):** the only national open list (2022) has 404 of the 4,000+ labelled communes.
- **Natura 2000:** too common to discriminate (a quarter of Spain) and too big for the free disk.
- **"Not spoilt" (motorway, industry, quarry next door):** needs a national OpenStreetMap or Corine extraction. Only the built-up % is shown.
- **Spanish heritage via Wikidata:** the association's own list replaces Wikidata's incomplete one (85 of 126). Wikidata's BIC and conjunto histórico entries are mostly but not completely located.
