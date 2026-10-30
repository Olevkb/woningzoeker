"""Zoekt via PDOK (de officiële adressendienst van de overheid) op in welke wijk een woning ligt."""

import logging
import re

import requests

from .model import Woning
from .opslag import Opslag

log = logging.getLogger(__name__)

PDOK = "https://api.pdok.nl/bzk/locatieserver/search/v3_1"
VELDEN = "wijknaam,buurtnaam,gemeentenaam,straatnaam,huis_nlt,postcode"


def _plat(tekst: str) -> str:
    return re.sub(r"[^a-z]", "", tekst.lower())


class Locatie:
    def __init__(self, opslag: Opslag, sessie: requests.Session):
        self.opslag = opslag
        self.sessie = sessie

    def bepaal(self, w: Woning) -> tuple[list[str], str]:
        """Geeft (mogelijke wijken, buurt). Eén wijk = zeker; meer = straat loopt door meerdere wijken.

        Vult ook straat/huisnummer/postcode aan als die via een losse tekst (hint) gevonden zijn.
        """
        plaats = w.plaats or "Amsterdam"
        pogingen = []
        if w.postcode:
            pogingen.append((f"pc:{w.postcode}:{w.huisnummer}", "free", {"q": f"{w.postcode} {w.huisnummer}".strip(), "rows": 1}, None))
        if w.lat is not None and w.lon is not None:
            pogingen.append((f"ll:{float(w.lat):.4f},{float(w.lon):.4f}", "reverse", {"lat": w.lat, "lon": w.lon, "rows": 1}, None))
        if w.straat:
            rows = 1 if w.huisnummer else 30
            q = f"{w.straat} {w.huisnummer} {plaats}"
            pogingen.append((f"st:{q}".lower(), "free", {"q": q, "rows": rows}, w.straat))
        for hint in w.hints:
            q = f"{hint[:120]} {plaats}"
            # zonder huisnummer: alle adressen van de straat bekijken, want lange straten lopen door meerdere wijken
            rows = 1 if re.search(r"\d", hint) else 30
            pogingen.append((f"tx{rows}:{q}".lower(), "free", {"q": q, "rows": rows}, hint))

        for sleutel, pad, params, controle in pogingen:
            uitkomst = self._cached(sleutel, pad, params, controle, plaats)
            if not uitkomst["wijken"]:
                continue
            if uitkomst.get("straat") and isinstance(controle, str) and controle is not w.straat:
                w.straat = uitkomst["straat"]
                # huisnummer van PDOK alleen overnemen als het ook echt in de advertentie staat
                nr = (uitkomst.get("huisnummer") or "").split("-")[0]
                direct_na_straat = rf"{re.escape(w.straat)}\W{{0,3}}{re.escape(nr)}\b"
                w.huisnummer = uitkomst["huisnummer"] if nr and re.search(direct_na_straat, controle, re.I) else ""
            if w.huisnummer and not w.postcode:  # alleen bij een exact adres, anders gaat de straat-info verloren
                w.postcode = uitkomst.get("postcode", "")
            return uitkomst["wijken"], uitkomst.get("buurt", "")
        return [], ""

    def _cached(self, sleutel, pad, params, controle, plaats) -> dict:
        bewaard = self.opslag.geo_haal(sleutel)
        if bewaard is not None:
            return bewaard
        try:
            soort = {"fq": "type:adres"} if pad == "free" else {"type": "adres"}
            r = self.sessie.get(f"{PDOK}/{pad}", params={"fl": VELDEN, **soort, **params}, timeout=20)
            r.raise_for_status()
            docs = r.json()["response"]["docs"]
        except (requests.RequestException, ValueError, KeyError) as e:
            log.warning("PDOK-opzoeking mislukt (%s): %s", sleutel, e)
            return {"wijken": []}  # niet bewaren, volgende keer opnieuw proberen
        if pad == "free":
            docs = [d for d in docs if (d.get("gemeentenaam") or "").lower() == plaats.lower()]
        if controle is not None:
            # alleen accepteren als de gevonden straat echt in de tekst voorkomt
            docs = [d for d in docs if d.get("straatnaam") and _plat(d["straatnaam"]) in _plat(controle)]
        uitkomst = self._uitkomst(docs)
        self.opslag.geo_bewaar(sleutel, uitkomst)
        return uitkomst

    @staticmethod
    def _uitkomst(docs) -> dict:
        wijken = []
        for d in docs:
            if d.get("wijknaam") and d["wijknaam"] not in wijken:
                wijken.append(d["wijknaam"])
        if not wijken:
            return {"wijken": []}
        eerste = docs[0]
        uitkomst = {"wijken": wijken, "buurt": eerste.get("buurtnaam", "") if len(wijken) == 1 else ""}
        if len(docs) == 1:
            uitkomst |= {"straat": eerste.get("straatnaam", ""), "huisnummer": eerste.get("huis_nlt", ""), "postcode": eerste.get("postcode", "")}
        return uitkomst
