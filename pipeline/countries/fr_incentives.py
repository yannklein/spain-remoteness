"""Incentives for setting up in a French commune (checked November 2026).

France has no tax break for simply living somewhere. The FRR zoning (France Ruralités Revitalisation,
article 44 quindecies A of the tax code) exempts new businesses and self-employed activities from profit
tax: 100% for 5 years, then 75%, 50% and 25%; micro-entrepreneurs qualify when creating or taking over a
business. FRR+ communes widen who is eligible; "FRR bénéficiaire" communes keep the same exemptions.
Source: the ministry's list of communes (10 July 2025) and its FAQ (July 2025).
"""

FRR_LIST = ("https://www.collectivites-locales.gouv.fr/files/files/3.%20Animer%20les%20territoires/"
            "5.%20La%20coh%C3%A9sion%20territoriale%20et%20l'am%C3%A9nagement%20du%20territoire/"
            "Liste%20communes%20FRR_juillet2025.xlsx")
SRC = "Ministère de l'Aménagement du territoire, liste des communes FRR (10 July 2025) and FAQ FRR"
FRR_AMOUNT = "No profit tax for 5 years, then 75%, 50% and 25% exemption"

# class in the ministry's list -> offer id
CLASSES = {"FRR socle": "frr", "FRR+": "frr_plus", "FRR bénéficiaire": "frr",
           "Classée FRR partiellement": "frr", "FRR bénéficiaire partiellement": "frr"}
PARTIAL = {"Classée FRR partiellement", "FRR bénéficiaire partiellement"}

OFFERS = [
    dict(id="frr", kind="business", region="France", title="Starting a business or freelance activity in an FRR commune",
         amount=FRR_AMOUNT,
         conditions="New or taken-over business (micro-entrepreneurs included when creating); local business taxes too if the commune decides.",
         age_max=None, valid="FRR zoning from 1 July 2024 (list of 10 July 2025)", source=SRC),
    dict(id="frr_plus", kind="business", region="France", title="Starting a business or freelance activity in an FRR+ commune",
         amount=FRR_AMOUNT + "; more kinds of business and operations eligible than in FRR",
         conditions="New or taken-over business; FRR+ applies from 1 January 2025.",
         age_max=None, valid="FRR+ list of 10 July 2025", source=SRC),
]
