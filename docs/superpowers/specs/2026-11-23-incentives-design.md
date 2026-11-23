# Incentives: what you get for moving to a municipality

Date: 2026-11-23 · Status: approved 2026-11-23 ("A", "go ahead")

## Intent
Show, for a remote worker choosing where to live, which tax breaks, grants and business incentives apply in each
municipality. This is option A, "what's on offer here", not B, a personal estimate.

## Design (as approved)
- **Map:**
  - Incentives map with buttons Tax breaks | Grants | Business;
  - a checkbox "I'm under 35" shows the offers limited to people under 35 or 36;
  - colours by the number of offers of that kind;
  - the tooltip lists each offer with its amount (and the municipality's own figure where it varies);
  - the method notes list every offer with conditions, validity and source.
- **Data:** curated offers in `pipeline/countries/{es,fr}_incentives.py`. Coverage comes from a population rule or an official list.
- **Scope:**
  - **Spain:** residence, moving, rent, purchase and self-employed deductions tied to the municipality (2025 tax year); standing grants (Extremadura's digital nomads, the national under-35 purchase grant).
  - **France:** FRR / FRR+ business exemptions.
  - **Left out:** children, nurseries, transport, internet and second homes; Galicia's aldeas modelo; Castilla y León's family-move grant (2026 terms not confirmed).
- **Gems:** "at least one tax break / grant / business offer / offer of any kind", counting offers open to all ages. Off by default.

## Known limits
- **Amounts** are as the law states them, not euros per person.
- **Population thresholds** use the current INE population, not the date each law uses. Local entities within larger municipalities that qualify (Extremadura, Aragón) are not shown separately.
- **Freshness:** offers change yearly. La Rioja's rural-employment deduction was struck down for 2026 onwards and is not included.

## Review fixes (2026-11-23)
- **La Rioja:** the annex is now read across page headers, and codes are checked against names (two typos in the manual). All 145 small municipalities are covered, up from 91.
- **Decisive conditions added to offers and shown in the tooltip:**
  - Castilla y León: a home under €150,000, new build or renovation, income limits;
  - Madrid: €1,546.50 a year cap;
  - Castilla-La Mancha: €12,000 base cap;
  - Aragón: income limit;
  - stay periods.
- **Added:** Extremadura's rural home purchase (10%) and rural rent (€1,500); Asturias's purchase in concejos at risk; young-person rent rates in rural Castilla-La Mancha (official distance list) and Castilla y León.
- **Valencia:** municipalities in the fund this year or the previous one, as the law says.
- **Partial coverage:** Aragón municipalities where only some settlements qualify are listed but not counted. Every age-limited offer, including under 40, shows only with the age box.
- **The Basque Country and Navarre** read "not covered" rather than "none".
- **Still a limit:** Castilla y León's 30 km rule is computed as a straight line, not from the Junta's official list.
