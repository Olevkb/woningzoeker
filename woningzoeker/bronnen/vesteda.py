"""Vesteda: grote verhuurder, levert zijn aanbod via de zoek-API van de eigen site (toegestaan in robots.txt)."""

import re
from urllib.parse import urljoin

from ..model import Woning, postcode_schoon
from ..web import Web
from . import Bron
from .makelaar import details

BESCHIKBAAR = {1, 4}  # 1 = beschikbaar, 4 = beschikbaar vanaf een latere datum; 2 = onder optie, 3 = verhuurd
ZOEK = {"placeType": 1, "sortType": 1, "radius": 5, "s": "Amsterdam", "sc": "woning",
        "latitude": 52.3675734, "longitude": 4.9041389, "filters": [], "priceFrom": 500, "priceTo": 9999}


class Vesteda(Bron):
    naam = "Vesteda"
    URL = "https://www.vesteda.com/api/units/search/facet"

    def zoek(self, web: Web) -> list[Woning]:
        uit = []
        for o in web.post_json(self.URL, ZOEK)["results"]["objects"]:
            if o.get("status") not in BESCHIKBAAR:
                continue
            w = Woning(
                bron=self.naam,
                id=str(o["id"]),
                url=urljoin("https://www.vesteda.com", o["url"]),
                straat=o.get("street") or "",
                huisnummer=f"{o.get('houseNumber') or ''}{o.get('houseNumberAddition') or ''}",
                postcode=postcode_schoon(o.get("postalCode")),
                plaats=o.get("city") or "",
                lat=o.get("latitude"),
                lon=o.get("longitude"),
                prijs=int(o["priceUnformatted"]) if o.get("priceUnformatted") else None,
                slaapkamers=o.get("numberOfBedRooms"),
                m2=o.get("size"),
                soort="appartement",
                foto=o.get("imageBig") or "",
            )
            # Vesteda's eigen kenmerken als tekst, zodat de gewone tekstfilters ze meenemen
            kenmerken = []
            if o.get("onlySixtyFivePlus") or (o.get("ageFrom") or 0) >= 55:
                kenmerken.append("Seniorenwoning")
            if not o.get("suitedForHomeSharers"):
                kenmerken.append("Volgens Vesteda niet geschikt voor woningdelers.")
            if o.get("onlyMiddleRent"):
                kenmerken.append("Middenhuur.")
            w.omschrijving = " ".join(kenmerken)
            uit.append(w)
        return uit

    def details(self, web: Web, w: Woning) -> None:
        kenmerken = w.omschrijving
        w.omschrijving = ""
        details(web, w)  # de advertentiepagina: inkomenseis, servicekosten, beschikbaarheid
        # de zoek-API zegt soms 'beschikbaar' terwijl de pagina bovenaan 'Gereserveerd' toont
        if m := re.search(r"\b(gereserveerd|verhuurd|onder optie)\b", w.omschrijving[:400], re.I):
            w.status = m.group(1).lower()
        w.omschrijving = f"{kenmerken} {w.omschrijving}"
