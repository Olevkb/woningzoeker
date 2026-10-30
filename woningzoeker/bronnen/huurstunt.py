import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .. import tekst as t
from ..model import Woning, getal, postcode_schoon
from ..web import Web, jsonld, zoek_type
from . import Bron, tijdstip

ADVERTENTIE = re.compile(r"/huren/in/[^/]+/[^/]+/[A-Za-z0-9]{4,}/?$")
SOORTEN = {"huurwoning": "huis", "woning": "huis"}


class Huurstunt(Bron):
    """Verzamelsite. De lijst toont standaard de nieuwste advertenties eerst."""

    naam = "Huurstunt"
    URL = "https://www.huurstunt.nl/huren/amsterdam/"

    def zoek(self, web: Web) -> list[Woning]:
        html = web.html(self.URL)
        kaarten = self._kaarten(html)
        uit = []
        for item in zoek_type(jsonld(html), "RealEstateListing"):
            url = item.get("url")
            if not url or not ADVERTENTIE.search(url):
                continue
            # bv. "Appartement te huur in Amsterdam | Witte de Withstraat | prijs: € 3.200 excl."
            naam = item.get("name", "")
            delen = [d.strip() for d in naam.split("|")]
            soort = delen[0].split(" te huur")[0].strip().lower()
            m = re.search(r"te huur in (.+)$", delen[0])
            fotos = item.get("image") or []
            foto = fotos[0] if fotos else ""
            m2, kamers = kaarten.get(url.rstrip("/"), (None, None))
            uit.append(
                Woning(
                    bron=self.naam,
                    id=url.rstrip("/").rsplit("/", 1)[-1],
                    url=url,
                    straat=delen[1] if len(delen) > 1 else "",
                    plaats=m.group(1) if m else "",
                    prijs=getal((item.get("offers") or {}).get("price")),
                    prijs_soort="service" if "incl" in naam.lower() else "kaal" if "excl" in naam.lower() else None,
                    kamers=kamers,
                    m2=m2,
                    soort=SOORTEN.get(soort, soort),
                    geplaatst=tijdstip(item.get("datePosted")),
                    foto=foto.get("url", "") if isinstance(foto, dict) else foto,
                )
            )
        return uit

    def _kaarten(self, html: str) -> dict[str, tuple[int | None, int | None]]:
        """m² en aantal kamers staan alleen op de kaartjes in de lijst, niet in de gestructureerde data."""
        kaarten = {}
        for a in BeautifulSoup(html, "html.parser").select("a[href]"):
            url = urljoin(self.URL, a["href"]).rstrip("/")
            if not ADVERTENTIE.search(url) or url in kaarten:
                continue
            kaart = a
            for _ in range(8):
                if re.search(r"\d+\s*m2", kaart.get_text(" ")) or kaart.parent is None:
                    break
                kaart = kaart.parent
            tekst = kaart.get_text(" ", strip=True)
            if len(tekst) > 1000:
                continue
            m2 = re.search(r"(\d+)\s*m2", tekst)
            kamers = re.search(r"(\d+)\s*kamers?", tekst)
            kaarten[url] = (getal(m2.group(1)) if m2 else None, getal(kamers.group(1)) if kamers else None)
        return kaarten

    def details(self, web: Web, w: Woning) -> None:
        html = web.html(w.url)
        for obj in zoek_type(jsonld(html), "Apartment", "House", "Residence", "SingleFamilyResidence", "Room"):
            adres = obj.get("address") or {}
            w.postcode = postcode_schoon(adres.get("postalCode")) or w.postcode
            w.lat = obj.get("latitude") or (obj.get("geo") or {}).get("latitude") or w.lat
            w.lon = obj.get("longitude") or (obj.get("geo") or {}).get("longitude") or w.lon
            w.omschrijving = obj.get("description") or w.omschrijving
            w.m2 = getal((obj.get("floorSize") or {}).get("value")) or w.m2
            break
        tekst = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        if m := re.search(r"Aantal slaapkamers:\s*(\d+)", tekst):
            w.slaapkamers = int(m.group(1))
        if m := re.search(r"Aantal kamers:\s*(\d+)", tekst):
            w.kamers = int(m.group(1))
        t.vul_aan(w, w.omschrijving, ook_prijs=False)
