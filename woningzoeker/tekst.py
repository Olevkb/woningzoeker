"""Haalt prijs, m², kamers en postcode uit vrije tekst (makelaarssites, e-mailalerts)."""

import re

from .model import Woning

_BEDRAG = r"(?:€|EUR|eur)\s?(\d{1,2}(?:[.,]\d{3})+|\d{3,5})(?:[.,](?:\d{2}|-{1,2}))?"
_PER_MAAND = r"(?:per\s+maand|per\s+month|p\.?\s?m\.?\b|p/m|p/mnd|/\s?mnd|/\s?maand|/\s?month|mnd\b|maand|month)"
_POSTCODE = re.compile(r"(?<![\d.,€])(?<!€\s)(?<!EUR\s)\b([1-9]\d{3}) ?([A-Z]{2})\b")
_VERHUURD = re.compile(r"\b(verhuurd|rented(?: out)?|onder optie|under option|gereserveerd|reserved|let agreed)\b", re.I)


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


def incl_excl(tekst: str) -> bool | None:
    m = re.search(_BEDRAG + r".{0,40}?\b(incl|inclusief|including|excl|exclusief|excluding)", tekst, re.I | re.S)
    if not m:
        return None
    return m.group(2).lower().startswith("incl")


def _eerste(patronen, tekst, laag, hoog) -> int | None:
    for p in patronen:
        for m in re.finditer(p, tekst, re.I):
            if laag <= (n := int(m.group(1))) <= hoog:
                return n
    return None


# (?<![\d.,]) voorkomt dat '€2.400 Bedrooms' als '00 bedrooms' gelezen wordt
_GETAL = r"(?<![\d.,])(\d{1,2})"


def m2(tekst: str) -> int | None:
    return _eerste(
        [r"(?<![\d.,])(\d{2,3})(?:[.,]\d{1,2})?\s?(?:m²|m2\b|m\^2|sq\.?\s?m|sqm|square met|vierkante meter)",
         r"\b(?:woonoppervlakte|oppervlakte|size|surface)\s*:?\s*(\d{2,3})\b"],
        tekst, 15, 400,
    )


def slaapkamers(tekst: str) -> int | None:
    return _eerste(
        [_GETAL + r"\s*(?:slaapkamers?|bedrooms?|slpk)\b", r"\b(?:slaapkamers?|bedrooms?)\s*:?\s*(\d{1,2})\b"], tekst, 1, 12
    )


def kamers(tekst: str) -> int | None:
    return _eerste(
        [r"\b(?:aantal )?kamers\s*:?\s*(\d{1,2})\b", r"\brooms\s*:?\s*(\d{1,2})\b", _GETAL + r"\s*(?:-\s*)?(?:kamers?|rooms?)\b"],
        tekst, 1, 15,
    )


def postcode(tekst: str) -> str:
    m = _POSTCODE.search(tekst)
    return f"{m.group(1)}{m.group(2)}" if m else ""


def is_verhuurd(tekst: str) -> bool:
    return bool(_VERHUURD.search(tekst))


def adres(tekst: str) -> tuple[str, str]:
    """'Albert Cuypstraat 12-2' -> ('Albert Cuypstraat', '12-2'). Leeg als er geen straat met nummer in staat."""
    m = re.search(r"([A-Z][\w.'’\- ]{2,40}?)\s+(\d{1,4}(?:\s?[-/]?\s?[A-Za-z0-9]{1,4})?)\b", tekst)
    if not m or re.search(r"€|\d", m.group(1)):
        return "", ""
    return m.group(1).strip(), m.group(2).replace(" ", "")


def vul_aan(w: Woning, tekst: str, ook_prijs: bool = True):
    """Vult alleen velden die nog leeg zijn."""
    if ook_prijs and w.prijs is None:
        w.prijs = prijs(tekst)
    if w.prijs_incl is None:
        w.prijs_incl = incl_excl(tekst)
    if w.m2 is None:
        w.m2 = m2(tekst)
    if w.slaapkamers is None:
        w.slaapkamers = slaapkamers(tekst)
    if w.kamers is None:
        w.kamers = kamers(tekst)
    if not w.postcode:
        w.postcode = postcode(tekst)
