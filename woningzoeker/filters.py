"""Bepaalt of een woning aan jullie eisen voldoet (uitleg: docs/eisen.md, instellingen: config.yaml)."""

import re
from datetime import datetime, timedelta

from . import tekst as t
from .model import Woning

GEEN_WONING = {"kamer", "studio", "parkeerplaats", "garage", "berging", "woonboot ligplaats"}
MIDDENHUUR = (932.93, 1228.07)  # 2026; daarvoor is in Amsterdam een huisvestingsvergunning nodig
SHORT_STAY = timedelta(days=183)
LATER_BESCHIKBAAR = timedelta(days=60)

_FEE = re.compile(r"bemiddelingskosten|makelaarskosten|contractkosten|agency fee|agent'?s? fee|placement fee|booking fee", re.I)
_GEEN_FEE_VOOR = re.compile(r"\b(geen|no|zonder|without|free of|gratis)\b[^.]{0,15}$", re.I)
_GEEN_FEE_NA = re.compile(r"^\s*:?\s*(geen|nvt|n\.v\.t\.|none|nihil|€\s?0\b)", re.I)
_GEMEUBILEERD = re.compile(r"(?<!on)gemeubileerd|(?<!un)(?<!un-)(?<!semi-)(?<!semi )furnished", re.I)
_OOK_ONGEMEUBILEERD = re.compile(r"ongemeubileerd|unfurnished|gestoffeerd|upholstered|\bkaal\b|\bshell\b", re.I)
_DUUR = re.compile(r"(?:huurperiode|rental period|tijdelijk|temporary|contract|lease)[^.]{0,40}?\b(\d{1,2})\s*(maanden|months|jaar|years)\b", re.I)


def _patronen(lijst):
    return [re.compile(p, re.I) for p in (lijst or [])]


def _labels(mapping):
    return [(re.compile(p, re.I), label) for p, label in (mapping or {}).items()]


def _volgorde(label: str) -> int:
    return 0 if label.startswith("⚠️") else 1 if label.startswith("🚩") else 2


class Filter:
    def __init__(self, cfg: dict):
        z = cfg["zoeken"]
        self.plaats = (z.get("plaats") or "").lower()
        self.budget = {int(n): grenzen for n, grenzen in z["budget"].items()}
        self.max_bewoners = max(self.budget)
        self.min_slaapkamers = z.get("min_slaapkamers", 0)
        self.min_kamers = z.get("min_kamers", 0)
        self.min_m2 = z.get("min_m2", 0)
        self.gemeubileerd = z.get("gemeubileerd", "label")
        self.wijken = {x.lower() for x in z.get("wijken") or []}
        self.toeslag = (cfg.get("huurtoeslag") or {}).get("per_maand", 0)
        tk = cfg.get("tekst") or {}
        self.uitsluiten = _patronen(tk.get("uitsluiten"))
        self.inkomenseis = _patronen(tk.get("inkomenseis"))
        self.garantsteller = _patronen(tk.get("garantsteller"))
        self.oplichting = _patronen(tk.get("oplichting"))
        self.labels = _labels(tk.get("pluspunten")) + _labels(tk.get("letop")) + _labels(tk.get("rode_vlaggen"))

    # --- budget ---

    def bewoners(self, w: Woning) -> int:
        """Hoeveel mensen er maximaal kunnen wonen: één per slaapkamer (minimaal 2)."""
        slpk = w.slaapkamers if w.slaapkamers is not None else (w.kamers - 1 if w.kamers else 2)
        return max(2, min(slpk, self.max_bewoners))

    def grens(self, bewoners: int, soort: str | None) -> int:
        return self.budget[bewoners][soort or "kaal"]

    def nodig_bewoners(self, w: Woning) -> int | None:
        """Met hoeveel bewoners de woning binnen het budget valt, of None als dat nooit lukt."""
        for n in range(2, self.bewoners(w) + 1):
            if n in self.budget and w.prijs <= self.grens(n, w.prijs_soort):
                return n
        return None

    def per_persoon(self, w: Woning, bewoners: int) -> float:
        return (w.prijs - self.toeslag) / bewoners

    # --- harde eisen ---

    def basis(self, w: Woning, voorlopig: bool = False) -> str | None:
        """Snelle controle op de harde eisen. Geeft de reden van afwijzing, of None als hij door mag.

        voorlopig: controle op alleen de gegevens uit de lijst; wat ontbreekt (zoals de prijs) komt misschien nog
        van de advertentiepagina, dus dat is nog geen reden om af te wijzen.
        """
        if self.plaats and w.plaats and w.plaats.lower() != self.plaats:
            return f"ligt in {w.plaats}"
        if w.soort in GEEN_WONING:
            return f"is een {w.soort}"
        if w.prijs is None:
            return None if voorlopig else "geen prijs"
        if self.nodig_bewoners(w) is None:
            n = self.bewoners(w)
            return f"te duur (€{w.prijs} {w.prijs_soort or 'kaal'}, max €{self.grens(n, w.prijs_soort)} bij {n} slaapkamers)"
        if w.slaapkamers is not None:
            if w.slaapkamers < self.min_slaapkamers:
                return f"{w.slaapkamers} slaapkamer(s)"
        elif w.kamers is not None:
            if w.kamers < self.min_kamers:
                return f"{w.kamers} kamer(s)"
        elif not voorlopig:
            # de advertentiepagina is gelezen en nog steeds geen aantal kamers: dan is 2 slaapkamers niet zeker
            return "aantal slaapkamers onbekend"
        if w.m2 is not None and 0 < w.m2 < self.min_m2:
            return f"te klein ({w.m2} m²)"
        if w.inschrijving is False:
            return "inschrijven niet mogelijk"
        if w.max_personen is not None and w.max_personen < 2:
            return f"max {w.max_personen} persoon"
        if w.beschikbaar and w.einddatum and w.einddatum - w.beschikbaar < SHORT_STAY:
            return f"short stay (tot {w.einddatum:%d-%m-%Y})"
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

    # --- tekst van de advertentie ---

    def tekst(self, w: Woning) -> str | None:
        """Past de uitsluitingen uit config.yaml toe en zet de labels. Geeft de reden van afwijzing of None."""
        # dubbele spaties en regeleindes plat maken: 'No  students' moet ook herkend worden
        tekst = re.sub(r"\s+", " ", w.omschrijving or "")
        for p in self.uitsluiten:
            if m := p.search(tekst):
                return f"tekst: '{m.group(0)}'"

        labels = list(w.labels)
        if _GEMEUBILEERD.search(tekst):
            if _OOK_ONGEMEUBILEERD.search(tekst):
                labels.append("🛋 gemeubileerd, mogelijk ook zonder meubels: vraag het na")
            elif self.gemeubileerd == "uitsluiten":
                return "gemeubileerd"
            else:
                labels.append("🛋 gemeubileerd")
        self._inkomen(tekst, labels)
        for p, label in self.labels:
            if p.search(tekst) and label not in labels:
                labels.append(label)
        if "⏳ tijdelijk contract" in labels:
            duur = f"tot {w.einddatum:%d-%m-%Y}" if w.einddatum else ""
            if not duur and (m := _DUUR.search(tekst)):
                duur = f"{m.group(1)} {m.group(2)}"
            if duur:
                labels[labels.index("⏳ tijdelijk contract")] = f"⏳ tijdelijk contract ({duur})"

        n = self.nodig_bewoners(w) or 2
        if n > 2:
            labels.append(f"👥 alleen betaalbaar met {n} personen (verhuurder heeft dan een omzettingsvergunning nodig)")
        if (w.prijs_soort in (None, "kaal") and MIDDENHUUR[0] <= w.prijs <= MIDDENHUUR[1]) or re.search(r"middenhuur|middeldure huur|mid-?rent", tekst, re.I):
            labels.append("🏷 middenhuur: je hebt een huisvestingsvergunning van de gemeente nodig")
        if w.beschikbaar and w.beschikbaar - datetime.now() > LATER_BESCHIKBAAR:
            labels.append(f"📅 pas beschikbaar per {w.beschikbaar:%d-%m-%Y}")
        if (borg := t.borg_maanden(tekst, w.prijs)) and borg > 2.05:
            labels.append(f"🚩 waarborgsom {borg:.1f}× de huur: meer dan 2 maanden is niet toegestaan")
        if any(not _GEEN_FEE_VOOR.search(tekst[max(0, m.start() - 30): m.start()]) and not _GEEN_FEE_NA.search(tekst[m.end(): m.end() + 20])
               for m in _FEE.finditer(tekst)):
            labels.append("🚩 bemiddelingskosten voor de huurder: meestal niet toegestaan")
        if any(p.search(tekst) for p in self.oplichting):
            labels.append("🚩 signalen van oplichting: betaal nooit vóór bezichtiging en sleutels")
        w.labels = sorted(dict.fromkeys(labels), key=_volgorde)
        return None

    def _inkomen(self, tekst: str, labels: list[str]):
        """Inkomenseis met garantsteller → 🤝; zonder vermelding van garantsteller → grote waarschuwing."""
        eis = next((m for p in self.inkomenseis if (m := p.search(tekst))), None)
        garant = any(p.search(tekst) for p in self.garantsteller)
        if eis:
            keer = eis.group(1) if eis.lastindex and re.fullmatch(r"[\d.,]+", eis.group(1) or "") else ""
            eis_tekst = f"{keer}× huur" if keer else "genoemd"
            if garant:
                labels.append(f"🤝 garantsteller mogelijk (inkomenseis {eis_tekst})")
            else:
                labels.append(f"⚠️ INKOMENSEIS {eis_tekst.upper()} – GARANTSTELLER NIET GENOEMD, VRAAG DIT EERST NA")
        elif garant:
            labels.append("🤝 garantsteller mogelijk")
