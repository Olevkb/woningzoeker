"""Algemene scanner voor makelaarssites: één lijstpagina + een patroon voor de advertentielinks (zie makelaars.yaml)."""

import re
from urllib.parse import unquote, urljoin, urlparse

from bs4 import BeautifulSoup

from .. import tekst as t
from ..model import Woning, getal, postcode_schoon
from ..web import Web, jsonld, zoek_type
from . import Bron

WEG = ["script", "style", "noscript", "form", "select", "nav", "header", "footer", "svg", "iframe", "button"]


class Makelaar(Bron):
    def __init__(self, naam: str, url: str, link: str, plaats: str = "", alleen: str = ""):
        self.naam = naam
        self.url = url
        self.link = re.compile(link)
        self.plaats = plaats  # vaste plaatsnaam als de lijst al op die plaats gefilterd is
        self.alleen = re.compile(alleen, re.I) if alleen else None
        self.aantal_links = 0

    def gezond(self, woningen) -> bool:
        # alles verhuurd of buiten Amsterdam is normaal; géén advertentielinks betekent dat de site veranderd is
        return self.aantal_links > 0

    def zoek(self, web: Web) -> list[Woning]:
        soup = BeautifulSoup(web.html(self.url), "html.parser")
        links = {}
        for a in soup.find_all("a", href=True):
            url = urljoin(self.url, a["href"]).split("#")[0]
            if self.link.search(urlparse(url).path) and urlparse(url).netloc == urlparse(self.url).netloc:
                links.setdefault(url, a)
        self.aantal_links = len(links)
        uit = []
        for url, a in links.items():
            kaart = _kaart(a, self.link)
            tekst = kaart.get_text(" ", strip=True)
            if t.is_verhuurd(tekst) or (self.alleen and not self.alleen.search(f"{tekst} {unquote(url)}")):
                continue
            w = Woning(bron=self.naam, id=urlparse(url).path.rstrip("/"), url=url, plaats=self.plaats)
            straat, nr, pc = _adres_uit_url(url)
            w.postcode = pc
            t.vul_aan(w, tekst)
            titel = kaart.find(["h1", "h2", "h3", "h4", "strong"])
            titeltekst = titel.get_text(" ", strip=True) if titel else ""
            # de straat uit de link is het betrouwbaarst; PDOK controleert hem later
            w.hints = [x for x in (f"{straat} {nr}".strip(), titeltekst, tekst[:200]) if x]
            w.straat, w.huisnummer = (straat, nr) if straat else t.adres(titeltekst)
            if not w.plaats and re.search(r"\bAmsterdam\b", tekst + url, re.I):
                w.plaats = "Amsterdam"
            img = kaart.find("img")
            if img:
                w.foto = urljoin(url, img.get("data-src") or img.get("src") or "")
            uit.append(w)
        return uit

    def details(self, web: Web, w: Woning) -> None:
        details(web, w)


def details(web: Web, w: Woning) -> None:
    """Advertentiepagina van een willekeurige site: eerst gestructureerde data, daarna de tekst."""
    html = web.html(w.url)
    soup = BeautifulSoup(html, "html.parser")
    for obj in zoek_type(jsonld(html), "Offer", "Apartment", "House", "Residence", "SingleFamilyResidence",
                         "RealEstateListing", "Product", "Accommodation"):
        adres = obj.get("address") if isinstance(obj.get("address"), dict) else {}
        w.postcode = w.postcode or postcode_schoon(adres.get("postalCode"))
        w.prijs = w.prijs or getal(obj.get("price"))
        w.m2 = w.m2 or getal((obj.get("floorSize") or {}).get("value") if isinstance(obj.get("floorSize"), dict) else None)
        w.kamers = w.kamers or getal(_waarde(obj.get("numberOfRooms")))
        w.slaapkamers = w.slaapkamers or getal(_waarde(obj.get("numberOfBedrooms")))
        if isinstance(obj.get("description"), str) and len(obj["description"]) > len(w.omschrijving):
            w.omschrijving = obj["description"]
    if not w.foto and (og := soup.find("meta", property="og:image")):
        w.foto = og.get("content", "")
    for el in soup(WEG):
        el.decompose()
    hoofd = soup.find("main") or soup.body
    tekst = hoofd.get_text(" ", strip=True) if hoofd else ""
    if len(tekst) < 300:  # sommige sites hebben een lege <main> of zelfs twee <body>-tags
        tekst = soup.get_text(" ", strip=True)
    t.vul_aan(w, tekst, ook_prijs=w.prijs is None)
    if len(tekst) > len(w.omschrijving):
        w.omschrijving = tekst[:8000]


def _waarde(x):
    return x.get("value") if isinstance(x, dict) else x


def _kaart(a, link_patroon):
    """Het kaartje rond een link: zo ver omhoog als kan zonder een andere advertentie mee te pakken."""
    kaart = a
    eigen = urlparse(a["href"]).path.rstrip("/")
    for _ in range(8):
        ouder = kaart.parent
        if ouder is None or ouder.name in ("body", "html"):
            break
        andere = {
            urlparse(x["href"]).path.rstrip("/")
            for x in ouder.find_all("a", href=True)
            if link_patroon.search(urlparse(x["href"]).path)
        } - {eigen}
        if andere or len(ouder.get_text(" ", strip=True)) > 1500:
            break
        kaart = ouder
    return kaart


_GEEN_STRAAT = {"amsterdam", "woning", "huurwoning", "huurwoningen", "woningen", "wonen", "appartement", "apartment",
                "huis", "house", "kamer", "studio", "te", "huur", "huren", "ref", "for", "rent", "rental", "rentals",
                "object", "item", "netherlands", "woningaanbod", "aanbod", "available", "properties", "listings",
                "residential", "nl", "en", "page"}


def _adres_uit_url(url: str) -> tuple[str, str, str]:
    """Straat, huisnummer en postcode uit een link.

    '/huurwoning/Wijnsilostraat-12-Amsterdam/2561/'            -> ('Wijnsilostraat', '12', '')
    '/available-properties/anna-blamansingel-1102sx-amsterdam'  -> ('Anna Blamansingel', '', '1102SX')
    '/huurwoningen/amsterdam/woning-673747-jacob-catskade-35f'  -> ('Jacob Catskade', '35f', '')
    """
    postcode = ""
    for deel in reversed([d for d in unquote(urlparse(url).path).split("/") if d]):
        tokens = [x for x in re.split(r"[-_+ ]", deel.lower()) if x]
        if not postcode:
            for i, x in enumerate(tokens):
                if re.fullmatch(r"[1-9]\d{3}[a-z]{2}", x):
                    postcode = x.upper()
                elif re.fullmatch(r"[1-9]\d{3}", x) and i + 1 < len(tokens) and re.fullmatch(r"[a-z]{2}", tokens[i + 1]):
                    postcode = f"{x}{tokens[i + 1]}".upper()
        # langste reeks woorden zonder cijfers = de straat
        beste, huidig, beste_eind = [], [], 0
        for i, x in enumerate(tokens + ["0"]):
            if x.isalpha() and len(x) >= 2 and x not in _GEEN_STRAAT:
                huidig.append(x)
            else:
                if len("".join(huidig)) > len("".join(beste)):
                    beste, beste_eind = huidig, i
                huidig = []
        # laatste woord zonder klinkers (na de eerste letter) is een willekeurige code, bv. 'leiduinstraat-iwlsn'
        if len(beste) > 1 and not re.search(r"[aeiouy]", beste[-1][1:]):
            beste = beste[:-1]
        if len("".join(beste)) < 5 or re.fullmatch(r"[a-f]+", "".join(beste)):
            continue
        nr = ""
        rest = tokens[beste_eind:]
        is_postcode = len(rest) > 1 and re.fullmatch(r"[1-9]\d{3}", rest[0]) and re.fullmatch(r"[a-z]{2}", rest[1])
        if rest and not is_postcode and re.fullmatch(r"\d{1,4}[a-z]?", rest[0]):
            nr = rest[0]
            if len(rest) > 1 and re.fullmatch(r"[a-z0-9]{1,2}", rest[1]) and rest[1] not in _GEEN_STRAAT:
                nr += f"-{rest[1]}"
        return " ".join(x.capitalize() for x in beste), nr, postcode
    return "", "", postcode
