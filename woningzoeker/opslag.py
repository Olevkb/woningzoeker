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

    def is_leeg(self) -> bool:
        return self.db.execute("SELECT 1 FROM gezien LIMIT 1").fetchone() is None

    def is_gezien(self, sleutel: str) -> bool:
        return self.db.execute("SELECT 1 FROM gezien WHERE sleutel = ?", (sleutel,)).fetchone() is not None

    def al_gemeld_elders(self, w: Woning, dagen: int) -> bool:
        grens = (datetime.now() - timedelta(days=dagen)).isoformat()
        rij = self.db.execute(
            "SELECT 1 FROM gezien WHERE dubbel = ? AND gemeld = 1 AND sleutel != ? AND tijd > ?",
            (w.dubbel_sleutel, w.sleutel, grens),
        ).fetchone()
        return rij is not None

    def markeer(self, w: Woning, gemeld: bool, reden: str = ""):
        self.db.execute(
            "INSERT OR REPLACE INTO gezien (sleutel, dubbel, gemeld, reden, url, tijd) VALUES (?, ?, ?, ?, ?, ?)",
            (w.sleutel, w.dubbel_sleutel, int(gemeld), reden, w.url, datetime.now().isoformat()),
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
