import re

from bs4 import BeautifulSoup

from ..model import Woning, getal, postcode_schoon
from ..web import Web, jsonld, zoek_type
from . import Bron, tijdstip

SOORTEN = {"Apartment": "appartement", "House": "huis", "SingleFamilyResidence": "huis", "Room": "kamer"}


class Rentola(Bron):
    """Verzamelsite met aanbod van veel makelaars. Nieuwste advertenties eerst."""

    naam = "Rentola"
    URL = "https://rentola.nl/huren?location=amsterdam&order=desc"

    def zoek(self, web: Web) -> list[Woning]:
        uit = []
        for lijst in zoek_type(jsonld(web.html(self.URL)), "ItemList"):
            for el in lijst.get("itemListElement", []):
                item = el.get("item") or {}
                url = item.get("url") or el.get("url")
                if not url:
                    continue
                aanbod = item.get("offers") or {}
                obj = aanbod.get("itemOffered") or {}
                adres = obj.get("address") or {}
                regel = adres.get("streetAddress", "")
                m = re.match(r"(.+?)\s+(\d+\S*)$", regel.split(",")[0].strip())
                straat, nr = (m.group(1), m.group(2)) if m else (regel.split(",")[0].strip(), "")
                geo = obj.get("geo") or {}
                foto = item.get("image")
                uit.append(
                    Woning(
                        bron=self.naam,
                        id=url.rstrip("/").rsplit("-", 1)[-1],
                        url=url,
                        straat=straat,
                        huisnummer=nr,
                        postcode=postcode_schoon(regel),
                        plaats=adres.get("addressLocality", ""),
                        lat=geo.get("latitude"),
                        lon=geo.get("longitude"),
                        prijs=getal(aanbod.get("price")),
                        # Rentola noemt het 'bedrooms', maar het is het totaal aantal kamers
                        kamers=getal((obj.get("numberOfBedrooms") or {}).get("value")),
                        m2=getal((obj.get("floorSize") or {}).get("value")),
                        soort=SOORTEN.get(obj.get("@type"), str(obj.get("@type", "")).lower()),
                        geplaatst=tijdstip(aanbod.get("validFrom")),
                        foto=foto[0] if isinstance(foto, list) else (foto or ""),
                    )
                )
        return uit

    def details(self, web: Web, w: Woning) -> None:
        html = web.html(w.url)
        for obj in zoek_type(jsonld(html), "RealEstateListing"):
            if obj.get("description"):
                w.omschrijving = obj["description"]
                break
        tekst = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        m = re.search(r"slaapkamers\s+(\d+)", tekst, re.I)
        if m:
            w.slaapkamers = int(m.group(1))
