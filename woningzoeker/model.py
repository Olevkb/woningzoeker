import re
from dataclasses import dataclass, field
from datetime import datetime

# Wat er in de prijs zit: "kaal" (servicekosten komen erbij), "service" (incl. servicekosten),
# "alles" (incl. gas/water/licht) of None (niet vermeld → telt als kaal).
PRIJSSOORTEN = ("kaal", "service", "alles")


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
    prijs_soort: str | None = None
    kamers: int | None = None
    slaapkamers: int | None = None
    m2: int | None = None
    soort: str = ""  # appartement, huis, kamer, studio, ...
    geplaatst: datetime | None = None
    beschikbaar: datetime | None = None  # ingangsdatum
    einddatum: datetime | None = None  # bij tijdelijke huur
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
        return f"{_plat(self.straat)}|{self.prijs}"

    @property
    def adres_sleutel(self) -> str:
        """Straat + huisnummer (alleen het getal), leeg als het huisnummer onbekend is."""
        nr = re.match(r"\d+", self.huisnummer or "")
        return f"{_plat(self.straat)}|{nr.group(0)}" if nr and self.straat else ""


def _plat(tekst: str) -> str:
    return re.sub(r"[^a-z]", "", (tekst or "").lower())


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
