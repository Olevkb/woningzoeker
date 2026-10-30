import re
from datetime import datetime

from bs4 import BeautifulSoup

from ..model import Woning, getal
from ..web import Web
from . import Bron


class Wonen123(Bron):
    """Makelaarsketen; klein aanbod in Amsterdam, maar vaak niet op de grote sites."""

    naam = "123Wonen"
    URL = "https://www.123wonen.nl/huurwoningen/in/amsterdam"

    def zoek(self, web: Web) -> list[Woning]:
        uit = []
        for c in BeautifulSoup(web.html(self.URL), "html.parser").select(".pandlist-container"):
            m = re.search(r"location\.href='([^']+)'", c.get("onclick", ""))
            if not m:
                continue
            url = m.group(1)
            specs = {}
            for li in c.select(".pand-specs li"):
                spans = li.find_all("span")
                if len(spans) >= 2:
                    specs[spans[0].get_text(strip=True)] = spans[-1].get_text(" ", strip=True)
            titel = c.select_one(".pand-title")
            adres = c.select_one(".pand-address")
            prijs = c.select_one(".pand-price")
            foto = c.select_one(".pand-image")
            uit.append(
                Woning(
                    bron=self.naam,
                    id=url.rstrip("/").rsplit("/", 1)[-1],
                    url=url,
                    straat=adres.get_text(strip=True) if adres else "",
                    plaats=titel.get_text(strip=True).split(",")[0] if titel else "",
                    prijs=getal(prijs.get_text()) if prijs else None,
                    slaapkamers=getal(specs.get("Slaapkamers")),
                    m2=getal(specs.get("Woonoppervlakte")),
                    soort=specs.get("Type", "").lower(),
                    geplaatst=_datum(specs.get("Aangeboden sinds")),
                    foto=foto.get("data-src", "") if foto else "",
                )
            )
        return uit

    def details(self, web: Web, w: Woning) -> None:
        soup = BeautifulSoup(web.html(w.url), "html.parser")
        tekst = soup.get_text(" ", strip=True)
        if m := re.search(r"Kamers\s+(\d+)", tekst):
            w.kamers = int(m.group(1))
        # kleinste blok dat de prijsdetails bevat = de omschrijving
        blokken = [b.get_text(" ", strip=True) for b in soup.find_all(["div", "section", "article"])]
        blokken = [b for b in blokken if "Huurprijs:" in b and len(b) > 300]
        if blokken:
            w.omschrijving = min(blokken, key=len)
            # "inclusief warmte, exclusief elektra" telt als excl. (strengste grens)
            if m := re.search(r"Huurprijs:(.*?)(Servicekosten|Waarborgsom|$)", w.omschrijving, re.I):
                zin = m.group(1).lower()
                w.prijs_incl = False if "exclusief" in zin else True if "inclusief" in zin else None


def _datum(tekst: str | None) -> datetime | None:
    try:
        return datetime.strptime(tekst.strip(), "%d-%m-%Y") if tekst else None
    except ValueError:
        return None
