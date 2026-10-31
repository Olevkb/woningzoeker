"""vb&t Verhuurmakelaars: aanbod via de API van de eigen site (toegestaan in robots.txt).

De API toont heel Nederland, niet op datum gesorteerd en zonder plaatsfilter. Daarom alle pagina's, maar één keer per uur.
"""

from urllib.parse import urljoin

from .. import tekst as t
from ..model import Woning, postcode_schoon
from ..web import Web
from . import Bron, tijdstip

BASIS = "https://vbtverhuurmakelaars.nl"
SOORTEN = {"apartment": "appartement", "house": "huis", "room": "kamer", "studio": "studio"}
MAX_PAGINAS = 60


class Vbt(Bron):
    naam = "vb&t Verhuurmakelaars"
    interval_minuten = 60

    def zoek(self, web: Web) -> list[Woning]:
        eerste = web.get(f"{BASIS}/api/properties/12/1?search=true").json()
        huizen = list(eerste.get("houses", []))
        for pagina in range(2, min(eerste.get("pageCount", 1), MAX_PAGINAS) + 1):
            huizen += web.get(f"{BASIS}/api/properties/12/{pagina}?search=true").json().get("houses", [])
        return [w for h in huizen if (w := self._woning(h))]

    def _woning(self, h: dict) -> Woning | None:
        adres = h.get("address") or {}
        prijzen = h.get("prices") or {}
        huur = prijzen.get("rental") or {}
        if adres.get("city") != "Amsterdam" or (h.get("status") or {}).get("name") != "available" or prijzen.get("category") != "rent":
            return None
        straat, nr = t.adres(adres.get("house", ""))
        x, y = (h.get("coordinate") or [None, None])[:2]
        soort = ((h.get("attributes") or {}).get("type") or {}).get("category", "")
        w = Woning(
            bron=self.naam,
            id=h["id"],
            url=urljoin(BASIS, h.get("url", "")),
            straat=straat or adres.get("house", ""),
            huisnummer=nr,
            plaats="Amsterdam",
            lat=y,
            lon=x,
            prijs=huur.get("price") or None,
            prijs_soort="kaal",  # servicekosten staan apart in de API
            kamers=h.get("rooms") or None,
            m2=h.get("plot") or None,
            soort=SOORTEN.get(soort, soort),
            beschikbaar=tijdstip(h.get("acceptance")),
            foto=urljoin(BASIS, h.get("image", "")),
        )
        teksten = [u.get("text", "") for u in h.get("usps") or []]
        if huur.get("securityDeposit") and w.prijs:
            teksten.append(f"Waarborgsom € {huur['securityDeposit']}")
        w.omschrijving = " ".join(teksten)
        return w

    def details(self, web: Web, w: Woning) -> None:
        """De API per woning: exact adres en de volledige omschrijving (voor de tekstfilters)."""
        slug = w.url.rstrip("/").rsplit("/", 1)[-1]
        huis = web.get(f"{BASIS}/api/property/{slug}").json().get("house") or {}
        adres = huis.get("address") or {}
        w.postcode = postcode_schoon(adres.get("postalCode")) or w.postcode
        if adres.get("number"):
            w.huisnummer = f"{adres['number']}{adres.get('suffix') or ''}"
        teksten = []

        def verzamel(o):
            if isinstance(o, str) and len(o) > 150:
                teksten.append(o)
            elif isinstance(o, dict):
                for v in o.values():
                    verzamel(v)
            elif isinstance(o, list):
                for v in o:
                    verzamel(v)

        verzamel(huis)
        w.omschrijving = " ".join([w.omschrijving, *teksten])
        t.vul_aan(w, w.omschrijving, ook_prijs=False)
