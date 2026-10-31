"""Beleefd ophalen van webpagina's: respecteert robots.txt en vraagt niet te vaak."""

import json
import logging
import re
import time
import urllib.robotparser
from urllib.parse import urlparse

import requests

log = logging.getLogger(__name__)

USER_AGENT = "woningzoeker/1.0 (persoonlijk zoekscript; respecteert robots.txt)"
MIN_PAUZE_PER_SITE = 3.0  # seconden tussen twee verzoeken naar dezelfde site
ROBOTS_GELDIG = 6 * 3600


class Geweigerd(Exception):
    """De site staat dit adres niet toe voor scripts (robots.txt)."""


class Web:
    def __init__(self):
        self.sessie = requests.Session()
        self.sessie.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8"})
        self._robots: dict[str, tuple[urllib.robotparser.RobotFileParser, float]] = {}
        self._laatste: dict[str, float] = {}

    def _mag(self, url: str) -> bool:
        p = urlparse(url)
        host = f"{p.scheme}://{p.netloc}"
        rp, opgehaald = self._robots.get(host, (None, 0.0))
        if rp is None or time.time() - opgehaald > ROBOTS_GELDIG:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.sessie.get(f"{host}/robots.txt", timeout=20)
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except requests.RequestException:
                rp.parse([])
            self._robots[host] = (rp, time.time())
        return rp.can_fetch(USER_AGENT, url)

    def get(self, url: str) -> requests.Response:
        return self._vraag("GET", url)

    def post_json(self, url: str, data: dict) -> dict:
        """Voor sites die hun aanbod via een eigen zoek-API leveren (zelfde regels: robots.txt en pauze)."""
        return self._vraag("POST", url, json=data).json()

    def _vraag(self, methode: str, url: str, **kw) -> requests.Response:
        if not self._mag(url):
            raise Geweigerd(url)
        host = urlparse(url).netloc
        wacht = MIN_PAUZE_PER_SITE - (time.time() - self._laatste.get(host, 0))
        if wacht > 0:
            time.sleep(wacht)
        self._laatste[host] = time.time()
        r = self.sessie.request(methode, url, timeout=30, **kw)
        r.raise_for_status()
        return r

    def html(self, url: str) -> str:
        return self.get(url).text


def jsonld(html: str) -> list:
    """Alle JSON-LD blokken (gestructureerde data) uit een pagina."""
    uit = []
    for blok in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S):
        try:
            uit.append(json.loads(blok))
        except json.JSONDecodeError:
            continue
    return uit


def zoek_type(data, *types: str) -> list[dict]:
    """Alle JSON-LD objecten van een bepaald @type, waar ze ook genest zitten."""
    gevonden = []

    def loop(o):
        if isinstance(o, dict):
            t = o.get("@type")
            if t in types or (isinstance(t, list) and set(t) & set(types)):
                gevonden.append(o)
            for v in o.values():
                loop(v)
        elif isinstance(o, list):
            for v in o:
                loop(v)

    loop(data)
    return gevonden


def next_data(html: str) -> dict:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    return json.loads(m.group(1)) if m else {}
