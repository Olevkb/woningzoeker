"""Bepaalt of een woning aan jouw voorwaarden uit config.yaml voldoet."""

import re

from .model import Woning

GEEN_WONING = {"kamer", "studio", "parkeerplaats", "garage", "berging", "woonboot ligplaats"}


def _patronen(lijst):
    return [re.compile(p, re.I) for p in (lijst or [])]


def _labels(mapping):
    return [(re.compile(p, re.I), label) for p, label in (mapping or {}).items()]


class Filter:
    def __init__(self, cfg: dict):
        z = cfg["zoeken"]
        self.plaats = (z.get("plaats") or "").lower()
        self.max_excl = z["max_huur_excl"]
        self.max_incl = z.get("max_huur_incl", self.max_excl)
        self.min_slaapkamers = z.get("min_slaapkamers", 0)
        self.min_kamers = z.get("min_kamers", 0)
        self.min_m2 = z.get("min_m2", 0)
        self.wijken = {x.lower() for x in z.get("wijken") or []}
        t = cfg.get("tekst") or {}
        self.uitsluiten = _patronen(t.get("uitsluiten"))
        self.oplichting = _patronen(t.get("oplichting"))
        self.labels = _labels(t.get("pluspunten")) + _labels(t.get("letop"))

    def basis(self, w: Woning) -> str | None:
        """Snelle controle op de harde eisen. Geeft de reden van afwijzing, of None als hij door mag."""
        if self.plaats and w.plaats and w.plaats.lower() != self.plaats:
            return f"ligt in {w.plaats}"
        if w.soort in GEEN_WONING:
            return f"is een {w.soort}"
        if w.prijs is None:
            return "geen prijs"
        grens = self.max_incl if w.prijs_incl else self.max_excl
        if w.prijs > grens:
            return f"te duur (€{w.prijs})"
        if w.slaapkamers is not None:
            if w.slaapkamers < self.min_slaapkamers:
                return f"{w.slaapkamers} slaapkamer(s)"
        elif w.kamers is not None and w.kamers < self.min_kamers:
            return f"{w.kamers} kamer(s)"
        if w.m2 is not None and 0 < w.m2 < self.min_m2:
            return f"te klein ({w.m2} m²)"
        if w.inschrijving is False:
            return "inschrijven niet mogelijk"
        if w.max_personen is not None and w.max_personen < 2:
            return f"max {w.max_personen} persoon"
        return None

    def wijk(self, w: Woning, wijken: list[str], buurt: str, definitief: bool) -> str | None:
        if not wijken:
            return "wijk onbekend" if definitief else None
        goed = [x for x in wijken if x.lower() in self.wijken]
        if not goed:
            return f"wijk {', '.join(wijken[:3])}"
        w.wijk = goed[0]
        w.buurt = buurt
        if len(wijken) > 1:
            w.labels.append("📍 straat loopt door meerdere wijken, check het adres")
        return None

    def tekst(self, w: Woning) -> str | None:
        tekst = w.omschrijving or ""
        for p in self.uitsluiten:
            m = p.search(tekst)
            if m:
                return f"tekst: '{m.group(0)}'"
        for p, label in self.labels:
            if p.search(tekst) and label not in w.labels:
                w.labels.append(label)
        if any(p.search(tekst) for p in self.oplichting):
            w.labels.append("🚩 let op: signalen van oplichting, betaal nooit vóór bezichtiging")
        if w.slaapkamers is None and w.kamers is None:
            w.labels.append("❓ aantal kamers niet vermeld")
        return None
