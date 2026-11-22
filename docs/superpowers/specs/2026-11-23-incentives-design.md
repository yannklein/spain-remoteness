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
