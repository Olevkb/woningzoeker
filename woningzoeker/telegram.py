"""Meldingen naar je telefoon via een eigen Telegram-bot."""

import html
import json
import logging
import re
import unicodedata
from datetime import datetime
from urllib.parse import quote, quote_plus

import requests

from .model import Woning

log = logging.getLogger(__name__)


class Telegram:
    def __init__(self, token: str, chat_id: str):
        self.url = f"https://api.telegram.org/bot{token}"
        self.chat_id = chat_id

    def _stuur(self, methode: str, **data) -> dict:
        r = requests.post(f"{self.url}/{methode}", json={"chat_id": self.chat_id, **data}, timeout=30)
        antwoord = r.json()
        nieuw = (antwoord.get("parameters") or {}).get("migrate_to_chat_id")
        if not antwoord.get("ok") and nieuw:
            # Telegram heeft de groep omgezet naar een supergroep, met een nieuw ID: daar naartoe sturen
            log.warning("Telegram-groep heeft een nieuw ID (%s). Leg het vast met: python setup_telegram.py --groep", nieuw)
            self.chat_id = nieuw
            return self._stuur(methode, **data)
        if not antwoord.get("ok"):
            raise RuntimeError(f"Telegram {methode}: {antwoord.get('description')}")
        return antwoord

    def tekst(self, tekst: str):
        self._stuur("sendMessage", text=tekst, parse_mode="HTML", disable_web_page_preview=True)

    def woning(self, w: Woning, cfg: dict):
        knoppen = knoppen_voor(w)
        if w.onzeker:  # voorwaarden niet te controleren: kort bericht, zonder foto, zodat het opvalt
            self._stuur("sendMessage", text=opmaak_kort(w, cfg), parse_mode="HTML", reply_markup=knoppen,
                        disable_web_page_preview=True)
            return
        tekst = opmaak(w, cfg)
        if w.foto:
            try:
                self._stuur("sendPhoto", photo=w.foto, caption=tekst, parse_mode="HTML", reply_markup=knoppen)
                return
            except (RuntimeError, requests.RequestException):
                pass  # foto werd niet geaccepteerd, stuur dan alleen tekst
        self._stuur("sendMessage", text=tekst, parse_mode="HTML", reply_markup=knoppen, disable_web_page_preview=True)

    def gratis_route(self, w: Woning):
        """Eerder gemeld via een betaalde site, en nu ook gevonden op een site waar reageren gratis is."""
        site, url = w.gratis_bij
        tekst = f"🆓 <b>{html.escape(w.adres or w.straat or 'Woning')}</b> ({euro(w.prijs)}) staat nu ook bij {html.escape(site)}: daar is reageren gratis"
        self._stuur("sendMessage", text=tekst, parse_mode="HTML", disable_web_page_preview=True,
                    reply_markup={"inline_keyboard": [[{"text": f"👉 Bekijk bij {site}", "url": url}]]})


# Verzamelsites waar reageren meestal een betaald account vraagt. Rentola en Kamer.nl nemen vooral over van Pararius
# en Kamernet (Rentola, 4 nov: 10 van de 16 woningen stonden met dezelfde prijs en m² op Pararius).
BETAALD_REAGEREN = {
    "Rentola": "rentola.nl",
    "Huurstunt": "huurstunt.nl",
    "Kamernet": "kamernet.nl",
    "Kamer.nl": "kamer.nl",
}


# Funda schrijft straatnamen voluit: '1e Jan Steenstraat' bestaat daar alleen als 'eerste-jan-steenstraat'
_VOLUIT = {"1e": "eerste", "2e": "tweede", "3e": "derde", "4e": "vierde", "5e": "vijfde",
           "pr": "prins", "st": "sint", "burg": "burgemeester"}


def _slug(tekst: str) -> str:
    """'Nieuwmarkt/Lastage' -> 'nieuwmarkt-lastage', zoals Pararius en Funda hun adressen schrijven."""
    plat = unicodedata.normalize("NFD", tekst).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", plat).strip("-")


def pararius_zoeken(w: Woning) -> str:
    """Zelfde buurt en prijs op Pararius (op straat zoeken kan daar niet): geeft meestal een handvol woningen.

    Niets in die buurt binnen de prijs? Dan toont Pararius heel Amsterdam; bij ±50 gebeurde dat vaak, bij ±150 zelden.
    """
    # straat zonder huisnummer die door meerdere wijken loopt: dan heel Amsterdam binnen dezelfde prijs
    plek = f"buurt-{_slug(w.wijk)}/" if w.wijk and len({wijk for wijk, _ in w.buurten}) <= 1 else ""
    return f"https://www.pararius.nl/huurwoningen/amsterdam/{plek}{w.prijs - 150}-{w.prijs + 150}"


def funda_zoeken(w: Woning) -> str:
    """Alle huurwoningen in dezelfde straat op Funda."""
    straat = re.sub(r"\b(\w+)\.?(?=\s)", lambda m: _VOLUIT.get(m[1].lower(), m[1]), w.straat)
    return "https://www.funda.nl/zoeken/huur?selected_area=" + quote(json.dumps([f"amsterdam/straat-{_slug(straat)}"]))


def knoppen_voor(w: Woning) -> dict:
    rij = [{"text": "👉 Bekijk advertentie", "url": w.url}]
    if w.adres:
        kaart = f"https://www.google.com/maps/search/?api=1&query={quote_plus(f'{w.adres}, {w.plaats or 'Amsterdam'}')}"
        rij.append({"text": "🗺 Kaart", "url": kaart})
    knoppen = [rij]
    if w.gratis_bij:
        knoppen.insert(0, [{"text": f"🆓 Gratis reageren via {w.gratis_bij[0]}", "url": w.gratis_bij[1]}])
    elif w.bron in BETAALD_REAGEREN and not w.gratis_reageren:
        zoek = []
        if w.prijs:
            zoek.append({"text": "🔎 Zoek op Pararius", "url": pararius_zoeken(w)})
        if w.straat:
            zoek.append({"text": "🔎 Zoek op Funda", "url": funda_zoeken(w)})
        if zoek:
            knoppen.append(zoek)
    return {"inline_keyboard": knoppen}


def route_regel(w: Woning) -> str:
    """Hoe je op een betaalde site toch gratis kunt reageren, of dat dat waarschijnlijk niet kan."""
    if w.bron not in BETAALD_REAGEREN:
        return ""
    if w.gratis_bij:
        return f"🆓 staat ook bij {html.escape(w.gratis_bij[0])}: daar is reageren gratis"
    if w.gratis_reageren:
        return f"🆓 op deze advertentie mag iedereen gratis reageren via {html.escape(w.bron)}"
    if w.verhuurder == "particulier":
        return f"🙋 particuliere verhuurder: staat waarschijnlijk alleen op {html.escape(w.bron)}, en reageren kost daar geld"
    if w.verhuurder:
        wie = "makelaar" if w.verhuurder == "makelaar" else html.escape(w.verhuurder)
        return f"🏢 {wie}: staat vaak ook op Pararius of Funda (🔎), daar is reageren gratis"
    return f"💳 reageren via {html.escape(w.bron)} kost geld, maar hij staat vaak ook op Pararius of Funda (🔎): daar is het gratis"


def opmaak_kort(w: Woning, cfg: dict) -> str:
    """Kort bericht voor een woning waarvan de voorwaarden niet te controleren waren."""
    e = html.escape
    plek = " · ".join(x for x in (w.wijk, w.buurt if w.buurt != w.wijk else "") if x)
    maten = " · ".join(x for x in (
        f"{w.slaapkamers} slaapkamers" if w.slaapkamers else f"{w.kamers} kamers" if w.kamers else "",
        f"{w.m2} m²" if w.m2 else "",
    ) if x)
    regels = [
        f"❔ <b>ZELF CHECKEN</b>: studenten/delers/garantsteller niet te controleren ({e(w.onzeker)})",
        f"🏠 <b>{e(w.adres or w.straat or 'Woning')}</b>" + (f" · {e(plek)}" if plek else ""),
        f"💶 {euro(w.prijs)}" + (f" · {maten}" if maten else "") + f" · via {e(w.bron)}",
    ]
    if route := route_regel(w):
        regels.append(route)
    regels.extend(e(label) for label in w.labels)
    return "\n".join(regels)


def euro(bedrag: float) -> str:
    return f"€{bedrag:,.0f}".replace(",", ".")


def hoe_lang_geleden(moment: datetime | None) -> str:
    if moment is None:
        return ""
    minuten = int((datetime.now() - moment).total_seconds() // 60)
    if minuten < 1:
        return "zojuist"
    if minuten < 60:
        return f"{minuten} min geleden"
    if minuten < 48 * 60:
        return f"{minuten // 60} uur geleden"
    return f"{minuten // (24 * 60)} dagen geleden"


def opmaak(w: Woning, cfg: dict) -> str:
    e = html.escape
    # grote waarschuwingen (⚠️) bovenaan, vetgedrukt
    regels = [f"<b>{e(label)}</b>" for label in w.labels if label.startswith("⚠️")]
    regels.append(f"🏠 <b>{e(w.adres or w.straat or 'Woning')}</b>")
    plek = [w.wijk] if w.wijk else []
    if w.buurt and w.buurt != w.wijk:
        plek.append(w.buurt)
    if plek:
        regels.append(f"📍 {e(' · '.join(plek))}")

    if w.prijs:
        soort = {"kaal": " kale huur", "service": " incl. servicekosten", "alles": " incl. alles"}.get(w.prijs_soort, " (incl./excl. onbekend)")
        regels.append(f"💶 <b>{euro(w.prijs)}</b>{soort}")
        toeslag = (cfg.get("huurtoeslag") or {}).get("per_maand", 0)
        slaapkamers = w.slaapkamers or (w.kamers - 1 if w.kamers else 2)
        pp = [f"{euro((w.prijs - toeslag) / n)} p.p. met {n}" for n in (2, 3) if n <= max(2, slaapkamers)]
        regels.append(f"👤 ≈ {' · '.join(pp)} (na €{toeslag} toeslag)")

    maten = []
    if w.kamers:
        maten.append(f"{w.kamers} kamers")
    if w.slaapkamers:
        maten.append(f"{w.slaapkamers} slaapkamers")
    if w.m2:
        maten.append(f"{w.m2} m²")
    if maten:
        regels.append("🛏 " + " · ".join(maten))

    bron = f"via {e(w.bron)}"
    geleden = hoe_lang_geleden(w.geplaatst)
    regels.append(f"🕒 {geleden + ' · ' if geleden else ''}{bron}")
    if route := route_regel(w):
        regels.append(route)
    regels.extend(e(label) for label in w.labels if not label.startswith("⚠️"))
    return "\n".join(regels)
