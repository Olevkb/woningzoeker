import re
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Woning:
    bron: str  # naam van de site, bv. "Rentola"
    id: str  # uniek binnen de bron
    url: str
    straat: str = ""
    huisnummer: str = ""
    postcode: str = ""  # zonder spatie, bv. "1091EL"
    plaats: str = ""
    lat: float | None = None
    lon: float | None = None
    prijs: int | None = None
    prijs_incl: bool | None = None  # True = incl., False = excl., None = onbekend
    kamers: int | None = None
    slaapkamers: int | None = None
    m2: int | None = None
    soort: str = ""  # appartement, huis, kamer, studio, ...
    geplaatst: datetime | None = None
    foto: str = ""
    omschrijving: str = ""
    inschrijving: bool | None = None
    max_personen: int | None = None
    hints: list[str] = field(default_factory=list)  # losse tekst waar het adres waarschijnlijk in staat
    # ingevuld tijdens het filteren
    wijk: str = ""
    buurt: str = ""
    labels: list[str] = field(default_factory=list)

    @property
    def sleutel(self) -> str:
        return f"{self.bron}:{self.id}"

    @property
    def adres(self) -> str:
        return " ".join(x for x in (self.straat, self.huisnummer) if x)

    @property
    def dubbel_sleutel(self) -> str:
        """Herkent dezelfde woning op verschillende sites (straat + prijs)."""
        straat = re.sub(r"[^a-z]", "", self.straat.lower())
        return f"{straat}|{self.prijs}"


def postcode_schoon(tekst: str | None) -> str:
    m = re.search(r"\b(\d{4})\s?([A-Za-z]{2})\b", tekst or "")
    return f"{m.group(1)}{m.group(2).upper()}" if m else ""


def getal(tekst) -> int | None:
    """'€ 2.450,-' -> 2450, '72 m²' -> 72."""
    if tekst is None:
        return None
    if isinstance(tekst, (int, float)):
        return int(tekst)
    m = re.search(r"\d[\d.]*", str(tekst))
    return int(m.group(0).replace(".", "")) if m else None
