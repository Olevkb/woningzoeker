"""Eén module per huursite, plus de algemene makelaarsscanner en de Gmail-inlezer."""

from datetime import datetime
from pathlib import Path

import yaml

from ..model import Woning
from ..web import Web


class Bron:
    naam = ""
    interval_minuten = 0  # >0: deze bron maar zo vaak bekijken (voor zware bronnen), anders bij elke scan

    def zoek(self, web: Web) -> list[Woning]:
        raise NotImplementedError

    def details(self, web: Web, w: Woning) -> None:
        """Haalt de advertentiepagina op en vult ontbrekende gegevens aan (optioneel)."""

    def gezond(self, woningen: list[Woning]) -> bool:
        """False = de site gaf niets bruikbaars terug (waarschijnlijk veranderd of geblokkeerd)."""
        return bool(woningen)


def tijdstip(tekst: str | None) -> datetime | None:
    """ISO-tijd (met of zonder tijdzone) naar lokale tijd zonder tijdzone."""
    if not tekst:
        return None
    try:
        t = datetime.fromisoformat(tekst.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t.astimezone().replace(tzinfo=None) if t.tzinfo else t


def maak_bronnen(namen: list[str], makelaars_bestand: Path) -> list[Bron]:
    from .gmail import Gmail
    from .huurstunt import Huurstunt
    from .kamernet import Kamernet
    from .makelaar import Makelaar
    from .rentola import Rentola
    from .vbt import Vbt
    from .vesteda import Vesteda
    from .wonen123 import Wonen123

    vast = {"rentola": Rentola, "huurstunt": Huurstunt, "kamernet": Kamernet, "123wonen": Wonen123, "gmail": Gmail,
            "vesteda": Vesteda, "vbt": Vbt}
    uit = []
    for naam in namen:
        if naam == "makelaars":
            lijst = yaml.safe_load(makelaars_bestand.read_text(encoding="utf-8"))["makelaars"]
            uit.extend(Makelaar(**m) for m in lijst)
        else:
            uit.append(vast[naam]())
    return uit
