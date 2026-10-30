"""Leest de e-mailalerts van sites die scripts blokkeren (Pararius, Funda, Huurwoningen.nl) uit een Gmail-inbox.

De inbox wordt alleen gelezen: er wordt niets verwijderd, verplaatst of als gelezen gemarkeerd.
"""

import email
import email.utils
import hashlib
import imaplib
import logging
import os
import re
from email.policy import default
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .. import tekst as t
from ..model import Woning
from ..web import USER_AGENT, Web
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
        self._omleidingen: dict[str, str] = {}

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
        afzender = str(bericht.get("From", "")).lower()
        portaal = next((v for k, v in PORTALEN.items() if k in afzender), None)
        if portaal is None:
            return []
        naam, patroon = portaal
        deel = bericht.get_body(preferencelist=("html", "plain"))
        if deel is None:
            return []
        inhoud = deel.get_content()
        ontvangen = tijdstip(email.utils.parsedate_to_datetime(bericht["Date"]).isoformat()) if bericht["Date"] else None
        soup = BeautifulSoup(inhoud, "html.parser") if deel.get_content_type() == "text/html" else None
        if soup is None:
            return []

        kaarten: dict[str, tuple] = {}
        for a in soup.find_all("a", href=True):
            echt = self._doel(a["href"], patroon)
            if not echt or not patroon.search(echt):
                continue
            kaart = _kaart(a, soup)
            tekst = kaart.get_text(" ", strip=True)
            if echt not in kaarten or len(tekst) > len(kaarten[echt][1]):
                img = kaart.find("img")
                kaarten[echt] = (a["href"], tekst, img.get("src", "") if img else "")

        uit = []
        for echt, (link, tekst, foto) in kaarten.items():
            pad = urlparse(echt).path.rstrip("/")
            w = Woning(bron=naam, id=pad or hashlib.sha1(tekst.encode()).hexdigest()[:12], url=echt, geplaatst=ontvangen, foto=foto)
            t.vul_aan(w, tekst)
            w.omschrijving = tekst  # alles wat de alert over de woning zegt gaat door de tekstfilters
            straat, nr, pc = adres_uit_url(echt)
            w.straat, w.huisnummer = t.adres(tekst)
            if not w.straat and straat:
                w.straat, w.huisnummer = straat, nr
            w.postcode = w.postcode or pc
            w.hints = [x for x in (f"{straat} {nr}".strip(), tekst[:200]) if x]
            if re.search(r"\bAmsterdam\b", tekst + echt, re.I):
                w.plaats = "Amsterdam"
            if re.search(r"/(kamer|room)[^/]*-te-huur/|/kamer-|/room-", echt):
                w.soort = "kamer"
            w.labels.append(f"❔ via {naam}-alert: voorwaarden (studenten, garantsteller, inschrijving) niet gecontroleerd")
            uit.append(w)
        return uit

    def _doel(self, href: str, patroon) -> str:
        """De echte advertentielink. Alerts gebruiken vaak doorstuurlinks; die volgen we zonder de site zelf te openen."""
        if not href.startswith("http"):
            return ""
        if patroon.search(href):
            return href.split("?")[0]
        if href in self._omleidingen:
            return self._omleidingen[href]
        url, doel = href, ""
        try:
            for _ in range(5):
                r = requests.head(url, allow_redirects=False, timeout=10, headers={"User-Agent": USER_AGENT})
                volgende = r.headers.get("Location")
                if not volgende:
                    break
                url = urljoin(url, volgende)
                if patroon.search(url):
                    doel = url.split("?")[0]
                    break
        except requests.RequestException:
            pass
        self._omleidingen[href] = doel
        return doel


def _map_alle_mail(imap) -> str:
    """Naam van de map 'Alle e-mail'; die verschilt per taal ([Gmail]/All Mail, [Gmail]/Alle e-mail, ...)."""
    status, mappen = imap.list()
    for regel in mappen or []:
        regel = regel.decode(errors="replace")
        if "\\All" in regel:
            naam = regel.rsplit(' "/" ', 1)[-1].strip()
            return naam if naam.startswith('"') else f'"{naam}"'
    return "INBOX"


def _kaart(a, soup):
    """Het blok rond een link in de e-mail (meestal een tabelcel) met prijs, adres en kenmerken."""
    kaart = a
    for _ in range(8):
        ouder = kaart.parent
        if ouder is None or ouder is soup:
            break
        if len(ouder.get_text(" ", strip=True)) > 600:
            break
        kaart = ouder
    return kaart
