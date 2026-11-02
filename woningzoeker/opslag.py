"""Geheugen van de zoeker: welke advertenties al gezien/gemeld zijn, plus een cache van wijk-opzoekingen."""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from .model import Woning


class Opslag:
    def __init__(self, pad: Path):
        pad.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(pad)
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS gezien (
                sleutel TEXT PRIMARY KEY,
                dubbel TEXT,
                gemeld INTEGER NOT NULL,
                reden TEXT,
                url TEXT,
                tijd TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS gezien_dubbel ON gezien(dubbel);
            CREATE TABLE IF NOT EXISTS geo (
                sleutel TEXT PRIMARY KEY,
                data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS meta (
                sleutel TEXT PRIMARY KEY,
                waarde TEXT
            );
            """
        )
        kolommen = {r[1] for r in self.db.execute("PRAGMA table_info(gezien)")}
        for kolom, soort in (("adres", "TEXT"), ("bron", "TEXT"), ("prijs", "INTEGER")):  # toegevoegd na de eerste versie
            if kolom not in kolommen:
                self.db.execute(f"ALTER TABLE gezien ADD COLUMN {kolom} {soort}")
        self.db.execute("CREATE INDEX IF NOT EXISTS gezien_adres ON gezien(adres)")
        self.db.commit()

    def is_leeg(self) -> bool:
        return self.db.execute("SELECT 1 FROM gezien LIMIT 1").fetchone() is None

    def is_gezien(self, sleutel: str) -> bool:
        return self.db.execute("SELECT 1 FROM gezien WHERE sleutel = ?", (sleutel,)).fetchone() is not None

    def opnieuw_bekijken(self, w: Woning) -> tuple[bool, int | None]:
        """(moet bekeken worden, vorige prijs). Nieuw → ja; prijs omlaag → ja, met de oude prijs erbij."""
        rij = self.db.execute("SELECT gemeld, prijs FROM gezien WHERE sleutel = ?", (w.sleutel,)).fetchone()
        if rij is None:
            return True, None
        gemeld, vorige = rij
        if vorige is None:  # opgeslagen voordat prijzen bewaard werden: eenmalig opnieuw, tenzij al gemeld
            return not gemeld, None
        if w.prijs and w.prijs < vorige:
            return True, vorige
        return False, None

    def elders(self, w: Woning, dagen: int) -> tuple[str, bool, str, str] | None:
        """Dezelfde woning op een andere site (zelfde straat + prijs, of zelfde adres): (bron, gemeld, reden, url)."""
        grens = (datetime.now() - timedelta(days=dagen)).isoformat()
        rij = self.db.execute(
            "SELECT bron, gemeld, reden, url FROM gezien WHERE (dubbel = ? OR (adres != '' AND adres = ?)) "
            "AND bron != ? AND tijd > ? ORDER BY gemeld DESC, tijd DESC LIMIT 1",
            (w.dubbel_sleutel, w.adres_sleutel, w.bron, grens),
        ).fetchone()
        return (rij[0], bool(rij[1]), rij[2] or "", rij[3] or "") if rij else None

    def markeer(self, w: Woning, gemeld: bool, reden: str = ""):
        self.db.execute(
            "INSERT OR REPLACE INTO gezien (sleutel, dubbel, adres, bron, gemeld, reden, url, tijd, prijs) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (w.sleutel, w.dubbel_sleutel, w.adres_sleutel, w.bron, int(gemeld), reden, w.url, datetime.now().isoformat(), w.prijs),
        )
        self.db.commit()

    def geo_haal(self, sleutel: str) -> dict | None:
        rij = self.db.execute("SELECT data FROM geo WHERE sleutel = ?", (sleutel,)).fetchone()
        return json.loads(rij[0]) if rij else None

    def geo_bewaar(self, sleutel: str, data: dict):
        self.db.execute("INSERT OR REPLACE INTO geo VALUES (?, ?)", (sleutel, json.dumps(data)))
        self.db.commit()

    def meta_haal(self, sleutel: str, standaard=None):
        rij = self.db.execute("SELECT waarde FROM meta WHERE sleutel = ?", (sleutel,)).fetchone()
        return json.loads(rij[0]) if rij else standaard

    def meta_bewaar(self, sleutel: str, waarde):
        self.db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (sleutel, json.dumps(waarde)))
        self.db.commit()

    def opruimen(self, dagen: int = 60):
        """Houdt het bestand klein: oude advertenties vergeten."""
        grens = (datetime.now() - timedelta(days=dagen)).isoformat()
        self.db.execute("DELETE FROM gezien WHERE tijd < ?", (grens,))
        self.db.commit()
        self.db.execute("VACUUM")
