"""Controleert de filters. Draaien met: python -m unittest -v

De wijktests vragen PDOK om echte adressen op en hebben dus internet nodig.
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

import requests
import yaml

from woningzoeker.filters import Filter
from woningzoeker.locatie import Locatie
from woningzoeker.model import Woning
from woningzoeker.opslag import Opslag

CFG = yaml.safe_load((Path(__file__).resolve().parent.parent / "config.yaml").read_text(encoding="utf-8"))


def woning(**kw) -> Woning:
    basis = dict(bron="test", id="1", url="https://example.org", plaats="Amsterdam", prijs=2400, kamers=3, m2=70)
    return Woning(**{**basis, **kw})


class Basis(unittest.TestCase):
    f = Filter(CFG)

    def test_goede_woning(self):
        self.assertIsNone(self.f.basis(woning()))

    def test_prijs_excl_en_incl(self):
        self.assertIsNotNone(self.f.basis(woning(prijs=2700, prijs_incl=False)))
        self.assertIsNone(self.f.basis(woning(prijs=2700, prijs_incl=True)))
        self.assertIsNotNone(self.f.basis(woning(prijs=2700)))  # onbekend = streng

    def test_kamers(self):
        self.assertIsNotNone(self.f.basis(woning(kamers=2)))
        self.assertIsNotNone(self.f.basis(woning(slaapkamers=1, kamers=4)))
        self.assertIsNone(self.f.basis(woning(slaapkamers=3, kamers=None)))

    def test_inschrijving_en_personen(self):
        self.assertIsNotNone(self.f.basis(woning(inschrijving=False)))
        self.assertIsNotNone(self.f.basis(woning(max_personen=1)))
        self.assertIsNone(self.f.basis(woning(max_personen=2)))


class Tekst(unittest.TestCase):
    f = Filter(CFG)

    def check(self, tekst):
        w = woning(omschrijving=tekst)
        return self.f.tekst(w), w.labels

    def test_uitsluiten(self):
        for t in [
            "Mooi appartement. Geen studenten.",
            "Not suitable for students or sharers",
            "No students allowed",
            "Inschrijving is niet mogelijk op dit adres",
            "Registration not possible",
            "Geschikt voor max 1 persoon",
            "Geen woningdelers",
            "Only for working professionals",
        ]:
            self.assertIsNotNone(self.check(t)[0], t)

    def test_niet_te_streng(self):
        for t in [
            "Studenten welkom met garantsteller",
            "Suitable for 2 persons, students allowed",
            "Geschikt voor 1 of 2 personen",  # bevat '1 of 2', niet '1 persoon'
            "Woningdelers toegestaan",
        ]:
            self.assertIsNone(self.check(t)[0], t)

    def test_labels(self):
        _, labels = self.check("Studenten welkom, garantsteller vereist. Tijdelijk contract, gemeubileerd. Inkomen 3x de huur.")
        for verwacht in ("studenten welkom", "garantsteller", "tijdelijk", "gemeubileerd", "inkomenseis"):
            self.assertTrue(any(verwacht in l for l in labels), (verwacht, labels))

    def test_ongemeubileerd_is_niet_gemeubileerd(self):
        for t in ["Ongemeubileerd appartement", "Unfurnished apartment", "Semi-furnished, un-furnished on request"]:
            _, labels = self.check(t)
            self.assertFalse(any("gemeubileerd" in l for l in labels), (t, labels))

    def test_oplichting(self):
        _, labels = self.check("I live abroad, I will send the keys by mail after payment via Western Union")
        self.assertTrue(any("oplichting" in l for l in labels))


class Wijken(unittest.TestCase):
    """Echte adressen binnen en buiten je zoekgebied."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.loc = Locatie(Opslag(Path(cls.tmp.name) / "t.db"), requests.Session())
        cls.f = Filter(CFG)

    @classmethod
    def tearDownClass(cls):
        cls.loc.opslag.db.close()
        cls.tmp.cleanup()

    def wijk(self, **kw):
        w = woning(**kw)
        wijken, buurt = self.loc.bepaal(w)
        return self.f.wijk(w, wijken, buurt, definitief=True), wijken

    def test_binnen(self):
        for kw in [
            dict(straat="Weesperzijde", huisnummer="100", postcode="1091EL"),
            dict(straat="Ruyschstraat", huisnummer="20"),  # tussen Amstel en Wibautstraat
            dict(straat="Egelantiersgracht", huisnummer="163"),  # Jordaan
            dict(straat="Haarlemmerdijk", huisnummer="50"),
            dict(straat="Plantage Middenlaan", huisnummer="30"),
            dict(straat="Sarphatipark", huisnummer="30"),  # De Pijp
            dict(straat="Vossiusstraat", huisnummer="53"),  # Oud-Zuid
            dict(lat=52.3732192, lon=4.8922897),  # de Dam, alleen coördinaten
        ]:
            reden, wijken = self.wijk(**kw)
            self.assertIsNone(reden, (kw, wijken))

    def test_buiten(self):
        for kw in [
            dict(straat="Vrolikstraat", huisnummer="64"),  # Oost, maar voorbij de Wibautstraat
            dict(straat="Nageljongenstraat", huisnummer="42", postcode="1033PE"),  # Noord
            dict(straat="Sumatrakade", huisnummer="100"),  # Oostelijk Havengebied
        ]:
            reden, wijken = self.wijk(**kw)
            self.assertIsNotNone(reden, (kw, wijken))


if __name__ == "__main__":
    unittest.main()
