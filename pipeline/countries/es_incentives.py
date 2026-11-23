"""Incentives for living or setting up in a Spanish municipality (checked November 2026).

Tax breaks: regional income-tax (IRPF) deductions tied to the municipality, for the 2025 tax year, from the
Agencia Tributaria's "Manual práctico de Renta 2025, Parte 2: Deducciones autonómicas" (published 21 Oct 2026),
with the official municipality lists it links to. Grants: standing programmes open to anyone moving in.
Left out: deductions about children, nurseries, transport, internet, second homes or renting a place out;
Galicia's "aldeas modelo" (project-based); Castilla y León's family-move grant (2026 terms not confirmed).

Each offer: id, kind (tax | grant | business), region, title, amount, conditions, age_max (an age limit:
"under N"), valid, source, provinces (INE province codes it can apply in) and cover, one of:
  {"pop_lt": n} / {"pop_le": n}       municipalities under / up to n inhabitants (current INE population)
  {"region": True}                    every municipality of the provinces
  {"list": key}                       an official list, parsed by compute_incentives.py
  {"codes": {...}}                    INE codes from the official text
  {"cyl_rural": True}                 Castilla y León: up to 10,000, or 3,000 within 30 km of the province capital
"""

MANUAL = ("https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IRPF/"
          "IRPF-2025-Deducciones-autonomicas/ManualRenta2025Parte2_es_es.pdf")
AEAT_LISTS = "https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IRPF/IRPF-2025-Deducciones-autonomicas/"
LISTS = {
    "aragon_rango_x": AEAT_LISTS + "CA_Aragon/Asentamientos_Rango_X.pdf",
    "asturias_concejos": AEAT_LISTS + "CA_Principado_Asturias/Concejos_riesgo_despoblamiento_crisis_demografica.pdf",
    "clm_residence": AEAT_LISTS + "CA_Castilla_La_Mancha/Municipios_despoblacion.pdf",
    "clm_purchase": AEAT_LISTS + "CA_Castilla_La_Mancha/Municipios_despoblacion_extrema_e_intensa_1.pdf",
    "clm_move": AEAT_LISTS + "CA_Castilla_La_Mancha/Municipios_despoblacion_extrema_e_intensa_2.pdf",
    "clm_rent": AEAT_LISTS + "CA_Castilla_La_Mancha/Municipios_distancia.pdf",
    "valencia_fund": ("https://terramapas.icv.gva.es/17_RiesgoDespoblamiento?request=GetFeature&service=WFS&version=2.0.0"
                      "&typename=Beneficiarios.2025&outputformat=csv"),
    "rioja_small": MANUAL,   # annex at the end of La Rioja's deductions
}

ARAGON, ASTURIAS, CANTABRIA, MADRID, RIOJA = ["22", "44", "50"], ["33"], ["39"], ["28"], ["26"]
CLM, EXTREMADURA, VALENCIA = ["02", "13", "16", "19", "45"], ["06", "10"], ["03", "12", "46"]
CYL = ["05", "09", "24", "34", "37", "40", "42", "47", "49"]
# the national housing plan runs through each region; the Basque Country and Navarre run their own plans
ALL_SPAIN = [f"{i:02d}" for i in range(1, 53) if f"{i:02d}" not in ("01", "20", "31", "48")]

# Orden PRE/1/2025 (BOC 3 Jan 2025): municipalities at risk, at serious risk, with special treatment
CANTABRIA_AT_RISK = {
    "39003", "39004", "39007", "39010", "39014", "39015", "39017", "39021", "39029", "39032", "39033", "39045", "39046",
    "39053", "39058", "39063", "39067", "39070", "39072", "39082", "39089", "39092", "39093", "39097", "39098", "39100",
    "39013", "39034", "39039", "39049", "39050", "39051", "39065", "39071", "39077", "39083", "39086", "39094", "39096",
    "39088", "39101",
}

TAX_YEAR = "2025 tax year (Renta 2025)"
SRC = "Agencia Tributaria, Manual Renta 2025 (deducciones autonómicas)"

OFFERS = [
    # --- tax breaks for living there -------------------------------------------------------------
    dict(id="ext_residence", kind="tax", region="Extremadura", provinces=EXTREMADURA, cover={"pop_lt": 3000},
         title="Living in a municipality under 3,000 inhabitants",
         amount="15% of the regional share of income tax",
         conditions="Taxable income up to €28,000 (€45,000 joint). Also in local entities under 3,000 within larger municipalities.",
         age_max=None, valid=TAX_YEAR, source=SRC),
    dict(id="ext_move", kind="tax", region="Extremadura", provinces=EXTREMADURA, cover={"region": True},
         title="Moving your residence to Extremadura",
         amount="50% of the regional share of income tax (75% under 36)",
         conditions="Moved to Extremadura from 1 January 2025; applies in the year of the move and the 2 following; stay 3 years.",
         age_max=None, valid=TAX_YEAR, source=SRC),
    dict(id="clm_residence", kind="tax", region="Castilla-La Mancha", provinces=CLM, cover={"list": "clm_residence"},
         title="Living in a sparsely populated rural zone",
         amount="10-25% of the regional share of income tax, by zone and size (see the figure for this municipality)",
         conditions="Registered and holding a health card in the municipality.",
         age_max=None, valid=TAX_YEAR, source=SRC),
    dict(id="clm_move", kind="tax", region="Castilla-La Mancha", provinces=CLM, cover={"list": "clm_move"},
         title="Moving here for work",
         amount="€500 in the year of the move and the next",
         conditions="Move for work (employed or self-employed); stay 4 years; taxable income up to €22,946 (€31,485 joint); capped at the regional tax on your work and business income.",
         age_max=None, valid=TAX_YEAR, source=SRC),
    dict(id="clm_purchase", kind="tax", region="Castilla-La Mancha", provinces=CLM, cover={"list": "clm_purchase"},
         title="Buying or renovating your home in a rural zone",
         amount="15% of what you pay for it, on up to €12,000 a year (at most €1,800)",
         conditions="Sparsely populated zone, municipality under 5,000 inhabitants; bought or renovated from 2021.",
         age_max=None, valid=TAX_YEAR, source=SRC),
    dict(id="aragon_residence", kind="tax", region="Aragón", provinces=ARAGON, cover={"list": "aragon_rango_x"},
         title="Living in a settlement at extreme risk of depopulation",
         amount="€600 a year",
         conditions="Taxable income under €35,000 (€50,000 joint), savings income up to €4,000; stay 5 years.",
         age_max=None, valid=TAX_YEAR, source=SRC),
    dict(id="aragon_purchase", kind="tax", region="Aragón", provinces=ARAGON, cover={"pop_lt": 3000},
         title="Buying or renovating a first home in a small municipality",
         amount="5% of what you pay for it (7.5% in settlements at high or extreme risk)",
         conditions="First home; municipality under 3,000 (or a separate local entity); taxable income after allowances under €21,000 (€35,000 joint).",
         age_max=36, valid=TAX_YEAR, source=SRC),
    dict(id="valencia_residence", kind="tax", region="Comunitat Valenciana", provinces=VALENCIA, cover={"list": "valencia_fund"},
         title="Living in a municipality at risk of depopulation",
         amount="€330 a year, plus €132-264 with children",
         conditions="Municipality in the 2025 depopulation fund.",
         age_max=None, valid=TAX_YEAR, source=SRC),
    dict(id="cantabria_residence", kind="tax", region="Cantabria", provinces=CANTABRIA, cover={"codes": CANTABRIA_AT_RISK},
         title="Living in a municipality at risk of depopulation",
         amount="20% of the regional share of income tax, up to €500",
         conditions="Under 40; resident the whole year (Orden PRE/1/2025 list).",
         age_max=40, valid=TAX_YEAR, source=SRC),
    dict(id="cantabria_rent", kind="tax", region="Cantabria", provinces=CANTABRIA, cover={"codes": CANTABRIA_AT_RISK},
         title="Renting your home in a municipality at risk of depopulation",
         amount="20% of the rent, up to €600 (€1,200 joint)",
         conditions="Orden PRE/1/2025 list.", age_max=None, valid=TAX_YEAR, source=SRC),
    dict(id="cantabria_move", kind="tax", region="Cantabria", provinces=CANTABRIA, cover={"codes": CANTABRIA_AT_RISK},
         title="Moving here for work",
         amount="€500 in the year of the move and the next",
         conditions="Move for work, employed or self-employed, from elsewhere in Spain; stay 4 years; capped at the regional tax on your work and business income.",
         age_max=None, valid=TAX_YEAR, source=SRC),
    dict(id="asturias_rent", kind="tax", region="Asturias", provinces=ASTURIAS, cover={"list": "asturias_concejos"},
         title="Renting your home in a concejo at risk of depopulation",
         amount="30% of the rent, up to €1,500",
         conditions="Taxable income up to €35,000 (€45,000 joint).", age_max=None, valid=TAX_YEAR, source=SRC),
    dict(id="asturias_move", kind="tax", region="Asturias", provinces=ASTURIAS, cover={"region": True},
         title="Moving your tax residence to Asturias for work",
         amount="15% of the moving costs, up to €1,000",
         conditions="Not resident in Asturias in the previous 4 years; stay 3 more years.",
         age_max=None, valid=TAX_YEAR, source=SRC),
    dict(id="madrid_move", kind="tax", region="Comunidad de Madrid", provinces=MADRID, cover={"pop_lt": 2500},
         title="Moving to a municipality under 2,500 inhabitants",
         amount="€1,000 in the year of the move and the next",
         conditions="Buying or renting your home there; stay 3 more years; household income limits.",
         age_max=35, valid=TAX_YEAR, source=SRC),
    dict(id="madrid_purchase", kind="tax", region="Comunidad de Madrid", provinces=MADRID, cover={"pop_lt": 2500},
         title="Buying your home in a municipality under 2,500 inhabitants",
         amount="10% of the price, spread over up to 10 years, at most €1,546.50 a year",
         conditions="Bought from 2024; stay 3 more years; household income up to €30,930 per member.",
         age_max=35, valid=TAX_YEAR, source=SRC),
    dict(id="cyl_purchase", kind="tax", region="Castilla y León", provinces=CYL, cover={"cyl_rural": True},
         title="Buying or renovating a first home in the rural area",
         amount="15% of what you pay for it",
         conditions="First home worth under €150,000, new build or renovation, bought from 2023; income after allowances up to €18,900 (€31,500 joint); up to 10,000 inhabitants (3,000 within 30 km of the province capital).",
         age_max=36, valid=TAX_YEAR, source=SRC),
    dict(id="rioja_purchase", kind="tax", region="La Rioja", provinces=RIOJA, cover={"list": "rioja_small"},
         title="Buying, building or renovating your home in a small municipality",
         amount="5% of what you pay, up to €452 a year", conditions="Bought from 2017.",
         age_max=None, valid=TAX_YEAR, source=SRC),
    dict(id="rioja_rent", kind="tax", region="La Rioja", provinces=RIOJA, cover={"list": "rioja_small"},
         title="Renting your home in a small municipality",
         amount="20% of the rent, up to €400", conditions="Income limits apply.",
         age_max=36, valid=TAX_YEAR, source=SRC),
    dict(id="ext_purchase_rural", kind="tax", region="Extremadura", provinces=EXTREMADURA, cover={"pop_lt": 3000},
         title="Buying or renovating your home in a municipality under 3,000 inhabitants",
         amount="10% of what you pay for it (less any regional grant)",
         conditions="Bought or renovated from 2022; also in local entities under 3,000 within larger municipalities.",
         age_max=None, valid=TAX_YEAR, source=SRC),
    dict(id="ext_rent_rural", kind="tax", region="Extremadura", provinces=EXTREMADURA, cover={"pop_lt": 3000},
         title="Renting your home in a municipality under 3,000 inhabitants",
         amount="30% of the rent, up to €1,500 (instead of €1,000 elsewhere)",
         conditions="Under 36 (or certain other groups, e.g. large families, disability); income limits.",
         age_max=36, valid=TAX_YEAR, source=SRC),
    dict(id="asturias_purchase", kind="tax", region="Asturias", provinces=ASTURIAS, cover={"list": "asturias_concejos"},
         title="Buying or renovating your home in a concejo at risk of depopulation",
         amount="5% of what you pay for it (10% if 35 or under, or a large or single-parent family)",
         conditions="Taxable income up to €35,000 (€45,000 joint).", age_max=None, valid=TAX_YEAR, source=SRC),
    dict(id="clm_rent_young", kind="tax", region="Castilla-La Mancha", provinces=CLM, cover={"list": "clm_rent"},
         title="Renting your home in a small or remote municipality",
         amount="Up to €612 a year (instead of €500 elsewhere)",
         conditions="Up to 2,500 inhabitants, or up to 10,000 more than 30 km from a town over 50,000 (official list); income limits.",
         age_max=36, valid=TAX_YEAR, source=SRC),
    dict(id="cyl_rent_young", kind="tax", region="Castilla y León", provinces=CYL, cover={"cyl_rural": True},
         title="Renting your home in the rural area",
         amount="25% of the rent, up to €612 (instead of 20% up to €459)",
         conditions="Up to 10,000 inhabitants (3,000 within 30 km of the province capital); income limits.",
         age_max=36, valid=TAX_YEAR, source=SRC),
    # --- business / self-employed ----------------------------------------------------------------
    dict(id="asturias_selfemployed", kind="business", region="Asturias", provinces=ASTURIAS, cover={"list": "asturias_concejos"},
         title="Setting up as self-employed in a concejo at risk of depopulation",
         amount="€1,000", conditions="Registered as self-employed in the year, for at least a year; income limits.",
         age_max=None, valid=TAX_YEAR, source=SRC),
    # --- grants ----------------------------------------------------------------------------------
    dict(id="ext_nomads", kind="grant", region="Extremadura", provinces=EXTREMADURA, cover={"region": True},
         title="Digital nomads: moving to Extremadura to work remotely",
         amount="Up to €10,000 (2026-2027 call)",
         conditions="Living outside Extremadura when applying; register in a municipality and stay 2 years; employed or self-employed remote work.",
         age_max=None, valid="Call published October 2026; check it is still open",
         source="Junta de Extremadura (SEXPE), https://www.juntaex.es/w/nueva-convocatoria-nomadas-digitales"),
    dict(id="es_young_purchase", kind="grant", region="Spain", provinces=ALL_SPAIN, cover={"pop_le": 10000},
         title="Buying a first home in a municipality of up to 10,000 inhabitants",
         amount="Up to €15,000 (at most 20% of the price)",
         conditions="35 or under; first home; through each region's call (Plan Estatal de Vivienda 2026-2030).",
         age_max=36, valid="Real Decreto 326/2026; regional calls from 2026",
         source="BOE, Real Decreto 326/2026 (Plan Estatal de Vivienda 2026-2030)"),
]
