"""Haalt prijs, m², kamers, postcode, beschikbaarheid en borg uit vrije tekst (makelaarssites, e-mailalerts)."""

import re
from datetime import datetime

from .model import Woning

_BEDRAG = r"(?:€|EUR|eur)\s?(\d{1,2}(?:[.,]\d{3})+|\d{3,5})(?:[.,](?:\d{2}|-{1,2}))?"
_PER_MAAND = r"(?:per\s+maand|per\s+month|p\.?\s?m\.?\b|p/m|p/mnd|/\s?mnd|/\s?maand|/\s?month|mnd\b|maand|month)"
_POSTCODE = re.compile(r"(?<![\d.,€])(?<!€\s)(?<!EUR\s)\b([1-9]\d{3}) ?([A-Z]{2})\b")
_VERHUURD = re.compile(r"\b(verhuurd|rented(?: out)?|onder optie|under option|gereserveerd|reserved|let agreed)\b", re.I)

_INCL = r"incl(?:\.|usief|uding)?\s*"
_SOORT_PATRONEN = [
    ("service", _INCL + r"(?:de\s+)?(?:servicekosten|service ?costs|service charges|service fee)"),
    ("alles", r"all[- ]?in\b|utilities included|" + _INCL + r"(?:alle kosten|g/?w/?[el]\b|gwl|gwe|gas|energie|nutsvoorzieningen|(?:all )?utilities|everything)"),
    ("kaal", r"\bexcl(?:\.|usief|uding)?\b|kale huur|basic rent|bare rent"),
    ("service", r"\bincl(?:\.|usief|uding)?\b"),
]

_MAANDEN = {
    "januari": 1, "january": 1, "jan": 1, "februari": 2, "february": 2, "feb": 2, "maart": 3, "march": 3, "mrt": 3,
    "mar": 3, "april": 4, "apr": 4, "mei": 5, "may": 5, "juni": 6, "june": 6, "jun": 6, "juli": 7, "july": 7,
    "jul": 7, "augustus": 8, "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9, "oktober": 10,
    "october": 10, "okt": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}
_MAAND = "(" + "|".join(sorted(_MAANDEN, key=len, reverse=True)) + r")\.?"


def bedrag(tekst: str) -> int:
    return int(re.sub(r"[.,]", "", tekst))


def prijs(tekst: str) -> int | None:
    """Huurprijs: bij voorkeur een bedrag gevolgd door 'per maand' e.d., anders het eerste realistische bedrag."""
    for m in re.finditer(_BEDRAG + r"[^€\d]{0,25}?" + _PER_MAAND, tekst, re.I):
        if 300 <= (b := bedrag(m.group(1))) <= 20000:
            return b
    for m in re.finditer(r"(?:huur(?:prijs)?|rent|price|prijs)\s*:?\s*" + _BEDRAG, tekst, re.I):
        if 300 <= (b := bedrag(m.group(1))) <= 20000:
            return b
    for m in re.finditer(_BEDRAG, tekst):
        if 300 <= (b := bedrag(m.group(1))) <= 20000:
            return b
    return None


def prijs_soort(tekst: str, huurprijs: int | None = None) -> str | None:
    """Wat er in de prijs zit, gelezen direct achter het bedrag: 'kaal', 'service', 'alles' of None."""
    venster = ""
    for m in re.finditer(_BEDRAG, tekst):
        if huurprijs is None or bedrag(m.group(1)) == huurprijs:
            venster = tekst[m.start(): m.end() + 80]
            break
    for soort, patroon in _SOORT_PATRONEN:
        if venster and re.search(patroon, venster, re.I):
            return soort
    return None


# getallen in woorden; 'een' bewust niet, dat is meestal een lidwoord ('een ruime slaapkamer')
_WOORDGETALLEN = {"één": 1, "one": 1, "twee": 2, "two": 2, "drie": 3, "three": 3, "vier": 4, "four": 4, "vijf": 5, "five": 5}
_WOORDGETAL = r"\b(" + "|".join(_WOORDGETALLEN) + r")"


def _eerste(patronen, tekst, laag, hoog) -> int | None:
    for p in patronen:
        for m in re.finditer(p, tekst, re.I):
            n = _WOORDGETALLEN.get(m.group(1).lower()) or int(m.group(1))
            if laag <= n <= hoog:
                return n
    return None


# (?<![\d.,]) voorkomt dat '€2.400 Bedrooms' als '00 bedrooms' gelezen wordt
_GETAL = r"(?<![\d.,])(\d{1,2})"


def m2(tekst: str) -> int | None:
    return _eerste(
        [r"(?<![\d.,])(\d{2,3})(?:[.,]\d{1,2})?\s?(?:m²|m2\b|m\s2\b|m\^2|sq\.?\s?m|sqm|square met|vierkante meter)",
         r"\b(?:woonoppervlakte|oppervlakte|size|surface)\s*:?\s*(\d{2,3})\b"],
        tekst, 15, 400,
    )


# Een kenmerkenlijst is 'label getal' (Kamers 2 Slaapkamers 1) of 'getal label' (4 kamers 3 slaapkamers).
# Staat er geen getal vóór het label, dan hoort het getal erna bij dat label.
_NA_LABEL = r"(?<!\d\s)(?<!\d)\b"
_KAMERS_WAARDE = re.compile(_NA_LABEL + r"((?:aantal\s+)?(?:kamers|rooms))\s*:?\s*(\d{1,2})(?=\s+(?:aantal\s+)?(?:slaapkamers?|bedrooms?)\b)", re.I)


def _kenmerken(tekst: str) -> str:
    tekst = re.sub(r"(\d)\s?m\s([23])\b", lambda m: m[1] + ("m²" if m[2] == "2" else "m³"), tekst)  # '61m 2', '153m 3'
    return _KAMERS_WAARDE.sub(r"\1 \2 |", tekst)  # 'Kamers 2 Slaapkamers 1': die 2 is het aantal kamers


def slaapkamers(tekst: str) -> int | None:
    # 0 telt mee: 'Slaapkamers 0' is een studio, parkeerplek of berging
    tekst = _kenmerken(tekst)
    return _eerste(
        [_GETAL + r"\s*(?:slaapkamers?|bedrooms?|slpk)\b", r"\b(?:slaapkamers?|bedrooms?)\s*:?\s*(\d{1,2})\b",
         _GETAL + r"-bed(?:room)?\b",
         _WOORDGETAL + r"[\s-]+(?:(?:ruime|grote|kleine|aparte|spacious|large|small|separate|double)\s+)?(?:slaapkamers?|bedrooms?)\b"],
        tekst, 0, 12,
    )


def kamers(tekst: str) -> int | None:
    tekst = _kenmerken(tekst)
    return _eerste(
        [_NA_LABEL + r"(?:aantal )?kamers\s*:?\s*(\d{1,2})\b", _NA_LABEL + r"rooms\s*:?\s*(\d{1,2})\b",
         _GETAL + r"\s*(?:-\s*)?(?:kamers?|rooms?)\b",
         _WOORDGETAL + r"[\s-]?kamer"],
        tekst, 1, 15,
    )


def postcode(tekst: str) -> str:
    m = _POSTCODE.search(tekst)
    return f"{m.group(1)}{m.group(2)}" if m else ""


def is_verhuurd(tekst: str) -> bool:
    return bool(_VERHUURD.search(tekst))


def datum(tekst: str) -> datetime | None:
    """Eerste datum in de tekst: 1-12-2026, 2026-12-01, 1 december 2026, December 1, 2026 of december 2026."""
    patronen = [
        (r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})\b", lambda m: (int(m[3]), int(m[2]), int(m[1]))),
        (r"\b(\d{4})-(\d{2})-(\d{2})\b", lambda m: (int(m[1]), int(m[2]), int(m[3]))),
        (r"\b(\d{1,2})(?:st|nd|rd|th|e)?\s+" + _MAAND + r"\s+(\d{4})\b", lambda m: (int(m[3]), _MAANDEN[m[2].lower()], int(m[1]))),
        (r"\b" + _MAAND + r"\s+(\d{1,2}),?\s+(\d{4})\b", lambda m: (int(m[3]), _MAANDEN[m[1].lower()], int(m[2]))),
        (r"\b" + _MAAND + r"\s+(\d{4})\b", lambda m: (int(m[2]), _MAANDEN[m[1].lower()], 1)),
    ]
    gevonden = []
    for patroon, delen in patronen:
        for m in re.finditer(patroon, tekst, re.I):
            try:
                gevonden.append((m.start(), datetime(*delen(m))))
            except ValueError:
                continue
    return min(gevonden)[1] if gevonden else None


def beschikbaar(tekst: str) -> datetime | None:
    """Ingangsdatum, gelezen na 'beschikbaar', 'available', 'ingangsdatum' e.d."""
    for m in re.finditer(r"\b(beschikbaar(?:heid)?|available|availability|ingangsdatum|aanvaarding|start date|move[- ]in)\b", tekst, re.I):
        stuk = tekst[m.end(): m.end() + 45]
        if re.match(r"\W{0,5}(per direct|direct|immediately|now|nu)\b", stuk, re.I):
            return datetime.now()
        if d := datum(stuk):
            return d
    return None


def borg_maanden(tekst: str, huurprijs: int | None) -> float | None:
    """Waarborgsom uitgedrukt in maanden kale huur."""
    for m in re.finditer(r"\b(waarborgsom|borg(?:som)?|security deposit|deposit)\b", tekst, re.I):
        stuk = tekst[m.end(): m.end() + 45]
        if mm := re.match(r"\D{0,25}?(\d(?:[.,]\d)?)\s*(?:x\s*)?(?:maanden|maand|months?|maal|keer)\b", stuk, re.I):
            return float(mm.group(1).replace(",", "."))
        if huurprijs and (mm := re.match(r"\D{0,25}?" + _BEDRAG, stuk)):
            return bedrag(mm.group(1)) / huurprijs
    return None


_VOORVOEGSELS = r"^(?:(?:te huur|for rent|nieuw|new|appartement|apartment|huis|house|woning|studio|bovenwoning|benedenwoning|penthouse|maisonnette|eengezinswoning)\b\s*[:|\-–]?\s*)+"


def adres(tekst: str) -> tuple[str, str]:
    """'Appartement Albert Cuypstraat 12-2' -> ('Albert Cuypstraat', '12-2'). Leeg als er geen straat met nummer in staat."""
    # huisnummer met toevoeging: 12, 35F, 12-2, 12/H, 12 H, 12 hs (maar niet '112 1091' = nummer + postcode)
    m = re.search(r"([A-Z][\w.'’\- ]{2,40}?)\s+(\d{1,4}(?:[A-Za-z]{1,2}\b|\s?[-/]\s?[A-Za-z0-9]{1,4}|\s[A-Za-z]{1,3}\b)?)(?!\d)", tekst)
    if not m or re.search(r"€|\d", m.group(1)):
        return "", ""
    straat = re.sub(_VOORVOEGSELS, "", m.group(1).strip(), flags=re.I).strip()
    return (straat, m.group(2).replace(" ", "")) if len(straat) >= 3 else ("", "")


def vul_aan(w: Woning, tekst: str, ook_prijs: bool = True):
    """Vult alleen velden die nog leeg zijn."""
    if ook_prijs and w.prijs is None:
        w.prijs = prijs(tekst)
    if w.prijs_soort is None:
        w.prijs_soort = prijs_soort(tekst, w.prijs)
    if w.m2 is None:
        w.m2 = m2(tekst)
    if w.slaapkamers is None:
        w.slaapkamers = slaapkamers(tekst)
    if w.kamers is None:
        w.kamers = kamers(tekst)
    if not w.postcode:
        w.postcode = postcode(tekst)
    if w.beschikbaar is None:
        w.beschikbaar = beschikbaar(tekst)
