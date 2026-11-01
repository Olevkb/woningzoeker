"""Leest de e-mailalerts van sites die scripts blokkeren (Pararius, Funda, Huurwoningen.nl) uit een Gmail-inbox.

De inbox wordt alleen gelezen: er wordt niets verwijderd, verplaatst of als gelezen gemarkeerd.
"""

import email
import email.utils
import imaplib
import logging
import os
import re
from email.policy import default
from bs4 import BeautifulSoup

from .. import tekst as t
from ..model import Woning
from ..web import Web
from . import Bron, tijdstip
from .makelaar import adres_uit_url

log = logging.getLogger(__name__)

PORTALEN = {
    # afzenderdomein: (naam, patroon voor een advertentielink op de site zelf)
    "pararius": ("Pararius", re.compile(r"pararius\.(nl|com)/(appartement|huis|studio|kamer|woning)[^/]*-te-huur/")),
    "funda": ("Funda", re.compile(r"funda\.nl/(detail/huur|huur)/")),
    "huurwoningen": ("Huurwoningen.nl", re.compile(r"huurwoningen\.(nl|com)/huren/")),
}
ZOEK_DAGEN = 3


class Gmail(Bron):
    naam = "Gmail"

    def __init__(self):
        self.adres = os.environ.get("GMAIL_ADRES", "")
        self.wachtwoord = os.environ.get("GMAIL_APP_WACHTWOORD", "").replace(" ", "")

    def gezond(self, woningen) -> bool:
        return True  # geen nieuwe alerts is normaal; inlogfouten komen als foutmelding

    def zoek(self, web: Web) -> list[Woning]:
        if not self.adres or not self.wachtwoord:
            log.info("Gmail: nog niet gekoppeld (GMAIL_ADRES / GMAIL_APP_WACHTWOORD ontbreken), overgeslagen.")
            return []
        uit = []
        for bericht in self.berichten():
            uit.extend(self.uit_bericht(bericht))
        return uit

    def berichten(self):
        """Alerts van de afgelopen dagen, uit 'Alle e-mail' (dus ook als Gmail ze in een tabblad of archief zet)."""
        afzenders = " OR ".join(f"from:{d}" for d in PORTALEN)
        with imaplib.IMAP4_SSL("imap.gmail.com") as imap:
            imap.login(self.adres, self.wachtwoord)
            imap.select(_map_alle_mail(imap), readonly=True)
            status, data = imap.uid("search", None, "X-GM-RAW", f'"newer_than:{ZOEK_DAGEN}d ({afzenders})"')
            if status != "OK":
                raise RuntimeError(f"zoeken in Gmail mislukt: {status}")
            for uid in data[0].split()[-60:]:
                status, inhoud = imap.uid("fetch", uid, "(BODY.PEEK[])")
                if status == "OK" and inhoud and isinstance(inhoud[0], tuple):
                    yield email.message_from_bytes(inhoud[0][1], policy=default)

    def uit_bericht(self, bericht) -> list[Woning]:
        """Alle woningen uit één alertmail, gelezen uit de mail zelf (de site wordt niet geopend)."""
        afzender = str(bericht.get("From", "")).lower()
        portaal = next((v for k, v in PORTALEN.items() if k in afzender), None)
        if portaal is None:
            return []
        naam, patroon = portaal
        deel = bericht.get_body(preferencelist=("html",))
        if deel is None:
            return []
        soup = BeautifulSoup(deel.get_content(), "html.parser")
        ontvangen = tijdstip(email.utils.parsedate_to_datetime(bericht["Date"]).isoformat()) if bericht["Date"] else None

        # per woning één blok: de foto-link en de titel-link horen bij hetzelfde blok; voorkeur voor de titel
        kaarten: dict[int, tuple] = {}
        for a in soup.find_all("a", href=True):
            if not a["href"].startswith("http"):
                continue
            kaart = _kaart(a)
            if kaart is None:
                continue
            eerder = kaarten.get(id(kaart))
            if eerder is None or (not eerder[1].get_text(strip=True) and a.get_text(strip=True)):
                kaarten[id(kaart)] = (kaart, a)

        uit, gebruikte_fotos = [], set()
        for kaart, a in kaarten.values():
            tekst = kaart.get_text(" ", strip=True)
            titel = a.get_text(" ", strip=True)
            # alerts gebruiken doorstuurlinks (die scripts weigeren); in je browser leiden ze gewoon naar de advertentie
            link = a["href"].split("?")[0] if patroon.search(a["href"]) else a["href"]
            w = Woning(bron=naam, id="", url=link, geplaatst=ontvangen, foto=_foto(kaart))
            t.vul_aan(w, tekst)
            if w.prijs is None:
                continue  # geen woning (bv. reclame voor een abonnement)
            if not w.foto:
                # Funda zet de foto in een eigen blok boven de tekst: neem de dichtstbijzijnde nog ongebruikte foto
                img = kaart.find_previous("img", src=lambda s: _is_foto(s) and s not in gebruikte_fotos)
                w.foto = img["src"] if img else ""
            gebruikte_fotos.add(w.foto)
            w.omschrijving = tekst  # alles wat de alert over de woning zegt gaat door de tekstfilters
            straat, nr, pc = adres_uit_url(link) if patroon.search(link) else ("", "", "")
            w.straat, w.huisnummer = t.adres(titel)
            if not w.straat and re.fullmatch(r"[A-Z][\w.'’ -]{2,40}", titel):
                w.straat = titel  # alleen een straatnaam, zonder huisnummer
            if not w.straat and straat:
                w.straat, w.huisnummer = straat, nr
            w.postcode = w.postcode or pc
            w.hints = [x for x in (f"{w.straat} {w.huisnummer}".strip(), tekst[:200]) if x]
            if re.search(r"\bAmsterdam\b", tekst, re.I):
                w.plaats = "Amsterdam"
            if re.search(r"/(kamer|room)[^/]*-te-huur/|/kamer-|/room-", link):
                w.soort = "kamer"
            # vaste sleutel per woning, ook als dezelfde woning in een latere mail met een andere link staat
            w.id = f"{re.sub(r'[^a-z0-9]', '', w.straat.lower())}-{w.huisnummer}-{w.postcode}-{w.prijs}"
            w.labels.append(f"❔ via {naam}-alert: voorwaarden (studenten, garantsteller, inschrijving) niet gecontroleerd")
            uit.append(w)
        return uit


def _map_alle_mail(imap) -> str:
    """Naam van de map 'Alle e-mail'; die verschilt per taal ([Gmail]/All Mail, [Gmail]/Alle e-mail, ...)."""
    status, mappen = imap.list()
    for regel in mappen or []:
        regel = regel.decode(errors="replace")
        if "\\All" in regel:
            naam = regel.rsplit(' "/" ', 1)[-1].strip()
            return naam if naam.startswith('"') else f'"{naam}"'
    return "INBOX"


_HUURPRIJS = re.compile(r"€\s?\d[\d.,]*(?:,-)?\s*(?:per\s+maand|/\s?maand|p/m|p\.m\.|/\s?mnd|per\s+month|/\s?month)", re.I)


def _kaart(a):
    """Het blok van één woning rond een link: zo groot mogelijk, zolang er precies één huurprijs in staat.

    Geeft None voor links die niet bij een woning horen (afmelden, 'bekijk alle woningen', reclame).
    """
    kaart, gevonden = a, None
    for _ in range(14):
        tekst = kaart.get_text(" ", strip=True)
        prijzen = len(_HUURPRIJS.findall(tekst))
        if prijzen > 1 or len(tekst) > 800:
            break
        if prijzen == 1:
            gevonden = kaart
        if kaart.parent is None or kaart.parent.name in ("body", "html", "[document]"):
            break
        kaart = kaart.parent
    return gevonden


def _is_foto(src) -> bool:
    """Een echte woningfoto, geen logo, icoon of meet-pixel van de mailverzender."""
    return bool(src) and src.startswith("http") and not re.search(
        r"logo|icon|pixel|spacer|track|/eo/|/open|iterable\.com|spmailtechno|\.gif\b|1x1", src, re.I
    )


def _foto(kaart) -> str:
    img = kaart.find("img", src=True)
    if img:
        return img["src"]
    for el in kaart.find_all(style=True):
        if m := re.search(r"url\(['\"]?(https?://[^'\")]+)", el["style"]):
            return m.group(1)
    return ""
