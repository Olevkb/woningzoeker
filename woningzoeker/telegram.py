"""Meldingen naar je telefoon via een eigen Telegram-bot."""

import html
import logging
from datetime import datetime
from urllib.parse import quote_plus

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
        tekst = opmaak(w, cfg)
        if w.foto:
            try:
                self._stuur("sendPhoto", photo=w.foto, caption=tekst, parse_mode="HTML", reply_markup=knoppen)
                return
            except (RuntimeError, requests.RequestException):
                pass  # foto werd niet geaccepteerd, stuur dan alleen tekst
        self._stuur("sendMessage", text=tekst, parse_mode="HTML", reply_markup=knoppen, disable_web_page_preview=True)


# Verzamelsites waar reageren meestal een betaald account vraagt. Dezelfde woning staat vaak ook bij de makelaar zelf.
BETAALD_REAGEREN = {
    "Rentola": "rentola.nl",
    "Huurstunt": "huurstunt.nl",
    "Kamernet": "kamernet.nl",
    "Kamer.nl": "kamer.nl",
}


def knoppen_voor(w: Woning) -> dict:
    rij = [{"text": "👉 Bekijk advertentie", "url": w.url}]
    if w.adres:
        kaart = f"https://www.google.com/maps/search/?api=1&query={quote_plus(f'{w.adres}, {w.plaats or 'Amsterdam'}')}"
        rij.append({"text": "🗺 Kaart", "url": kaart})
    knoppen = [rij]
    if w.bron in BETAALD_REAGEREN and w.straat:
        # zelfde adres zoeken, zonder de betaalde verzamelsites: zo kom je bij de makelaar, Pararius of Funda
        zonder = " ".join(f"-site:{d}" for d in BETAALD_REAGEREN.values())
        zoek = f'"{w.adres or w.straat}" {w.plaats or "Amsterdam"} huur {zonder}'
        knoppen.append([{"text": "🔎 Zoek de makelaar (gratis reageren)", "url": f"https://www.google.com/search?q={quote_plus(zoek)}"}])
    return {"inline_keyboard": knoppen}


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
    if w.bron in BETAALD_REAGEREN:
        regels.append(f"💳 reageren via {e(w.bron)} kost meestal geld; met 🔎 vind je vaak de makelaar zelf")
    regels.extend(e(label) for label in w.labels if not label.startswith("⚠️"))
    return "\n".join(regels)
