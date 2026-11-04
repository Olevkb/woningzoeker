"""Controleert de eisen uit docs/eisen.md. Draaien met: python -m unittest -v

De wijktests vragen PDOK om echte adressen op en hebben dus internet nodig.
"""

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import requests
import yaml

from woningzoeker.filters import Filter
from woningzoeker.locatie import Locatie
from woningzoeker.model import Woning
from woningzoeker.opslag import Opslag

CFG = yaml.safe_load((Path(__file__).resolve().parent.parent / "config.yaml").read_text(encoding="utf-8"))


def woning(**kw) -> Woning:
    basis = dict(bron="test", id="1", url="https://example.org", plaats="Amsterdam", prijs=2400, slaapkamers=2, m2=70)
    return Woning(**{**basis, **kw})


class Budget(unittest.TestCase):
    """Budget per aantal bewoners (eisen 1)."""

    f = Filter(CFG)

    def test_twee_personen(self):
        self.assertIsNone(self.f.basis(woning(prijs=2600)))
        self.assertIsNotNone(self.f.basis(woning(prijs=2650)))  # onbekend = kale huur
        self.assertIsNotNone(self.f.basis(woning(prijs=2650, prijs_soort="kaal")))
        self.assertIsNone(self.f.basis(woning(prijs=2700, prijs_soort="service")))
        self.assertIsNone(self.f.basis(woning(prijs=2900, prijs_soort="alles")))
        self.assertIsNotNone(self.f.basis(woning(prijs=2950, prijs_soort="alles")))

    def test_meer_slaapkamers(self):
        self.assertIsNone(self.f.basis(woning(prijs=3250, slaapkamers=3)))
        self.assertIsNotNone(self.f.basis(woning(prijs=3300, slaapkamers=3)))
        self.assertIsNone(self.f.basis(woning(prijs=4200, slaapkamers=4)))
        self.assertIsNone(self.f.basis(woning(prijs=4200, slaapkamers=6)))  # meer dan 4: budget van 4
        self.assertIsNotNone(self.f.basis(woning(prijs=4300, slaapkamers=6)))
        self.assertIsNone(self.f.basis(woning(prijs=3200, slaapkamers=None, kamers=4)))  # 4 kamers ≈ 3 slaapkamers

    def test_label_extra_huisgenoot(self):
        w = woning(prijs=3000, slaapkamers=3)
        self.assertIsNone(self.f.basis(w))
        self.f.tekst(w)
        self.assertTrue(any(l.startswith("👥 alleen betaalbaar met 3 personen") for l in w.labels), w.labels)
        w = woning(prijs=2500, slaapkamers=3)  # past ook met 2: geen label
        self.f.tekst(w)
        self.assertFalse(any(l.startswith("👥") for l in w.labels), w.labels)

    def test_prijs_per_persoon(self):
        self.assertEqual(self.f.per_persoon(woning(prijs=2525), 2), 1000)
        self.assertEqual(self.f.per_persoon(woning(prijs=3525), 3), 1000)


class Basis(unittest.TestCase):
    f = Filter(CFG)

    def test_kamers_en_m2(self):
        self.assertIsNotNone(self.f.basis(woning(slaapkamers=1)))
        self.assertIsNotNone(self.f.basis(woning(prijs=350, slaapkamers=0)))  # parkeerplek bij Homecrew (30 okt)
        # aantal kamers onbekend: in de lijst nog niet afwijzen (advertentie komt nog), daarna wel
        onbekend = woning(slaapkamers=None, kamers=None)
        self.assertIsNone(self.f.basis(onbekend, voorlopig=True))
        self.assertEqual(self.f.basis(onbekend), "aantal slaapkamers onbekend")
        self.assertIsNotNone(self.f.basis(woning(slaapkamers=None, kamers=2)))
        self.assertIsNone(self.f.basis(woning(slaapkamers=None, kamers=3)))
        self.assertIsNotNone(self.f.basis(woning(m2=40)))

    def test_inschrijving_personen_short_stay(self):
        self.assertIsNotNone(self.f.basis(woning(inschrijving=False)))
        self.assertIsNotNone(self.f.basis(woning(max_personen=1)))
        self.assertIsNone(self.f.basis(woning(max_personen=2)))
        start = datetime(2026, 12, 1)
        self.assertIsNotNone(self.f.basis(woning(beschikbaar=start, einddatum=start + timedelta(days=90))))
        self.assertIsNone(self.f.basis(woning(beschikbaar=start, einddatum=start + timedelta(days=365))))

    def test_geen_zelfstandige_woning(self):
        self.assertIsNotNone(self.f.basis(woning(soort="kamer")))
        self.assertIsNotNone(self.f.basis(woning(soort="studio")))


class Tekst(unittest.TestCase):
    f = Filter(CFG)

    def check(self, tekst, **kw):
        w = woning(omschrijving=tekst, **kw)
        return self.f.tekst(w), w.labels

    def test_uitsluiten(self):
        for t in [
            "Mooi appartement. Geen studenten.",
            "Not suitable for students or sharers",
            "No students allowed",
            "Only for working professionals",
            "Company let only",
            "Seniorenwoning voor 55+",
            "Geschikt voor max 1 persoon",
            "Alleen geschikt voor een stel",
            "Couples only",
            "Geen woningdelers",
            "Inschrijving is niet mogelijk op dit adres",
            "Registration not possible",
            "Antikraak woonruimte via leegstandsbeheer",
            "Kamer met gedeelde keuken en badkamer",
            "Geen garantstellers",
            "Guarantors are not accepted",
            "Eigen inkomen vereist",
            "Short stay apartment, max 3 months",
            "Huurperiode: maximaal 4 maanden",
            # echte gevallen van kamer.nl (30 okt): kamer in gedeelde woning, en geen huurtoeslag
            "Aantal huisgenoten 0 Huiskamer Gedeeld Toilet Gedeeld Keuken Gedeeld",
            "Borg € 1.575,00 Huurtoeslag mogelijk Niet mogelijk Voorwaarden",
            # koopwoningen tussen het huuraanbod (BIC, Alcoco, 2 nov): '€ 325.000' mag nooit als huur doorgaan
            "Palamedesstraat 3-3A Woonoppervlakte 28 m 2 Aantal slaapkamers 1 Koopprijs € 325.000,- k.k.",
            "Te koop Ennemaborg 39 Amsterdam €545000,- kosten koper 72 m²",
        ]:
            self.assertIsNotNone(self.check(t)[0], t)

    def test_niet_te_streng(self):
        for t in [
            "Studenten welkom met garantsteller",
            "Suitable for 2 persons, students allowed",
            "Geschikt voor 1 of 2 personen",
            "Woningdelers toegestaan",
            "Suitable for a couple or two sharers",
            "Geen garantsteller nodig",
            "Waarborgsom maximaal 2 maanden huur",  # geen short stay
            "Huurperiode: minimaal 12 maanden",
            "Wasmachine in bruikleen",
        ]:
            self.assertIsNone(self.check(t)[0], t)

    def test_inkomenseis_drie_gevallen(self):
        reden, labels = self.check("Inkomenseis: 3x de kale huur bruto per maand, garantsteller mogelijk.")
        self.assertIsNone(reden)
        self.assertTrue(any(l.startswith("🤝") and "3× huur" in l for l in labels), labels)
        self.assertFalse(any(l.startswith("⚠️") for l in labels))

        reden, labels = self.check("Bruto maandinkomen van minimaal 4 x de huur.")
        self.assertIsNone(reden)
        self.assertTrue(labels[0].startswith("⚠️ INKOMENSEIS 4× HUUR"), labels)  # groot label bovenaan

        reden, _ = self.check("Inkomen 4x de huur, geen garantstellers.")
        self.assertIsNotNone(reden)

        # echt geval van kamer.nl: '3,0 x maandhuur' en 'garantiestelling'
        reden, labels = self.check("Minimaal inkomen 3,0 x maandhuur bruto. Huur voor onbepaalde tijd; een garantiestelling is mogelijk.")
        self.assertIsNone(reden)
        self.assertTrue(any(l.startswith("🤝") and "3,0× huur" in l for l in labels), labels)

    def test_onbepaalde_tijd_is_niet_tijdelijk(self):
        _, labels = self.check("Overeenkomst Onbepaalde tijd Te huur")
        self.assertFalse(any(l.startswith("⏳") for l in labels), labels)
        _, labels = self.check("Huurovereenkomst voor bepaalde tijd")
        self.assertTrue(any(l.startswith("⏳") for l in labels), labels)

    def test_labels(self):
        _, labels = self.check("Tijdelijk contract, huurperiode 24 maanden. Jongerencontract.")
        for verwacht in ("⏳ tijdelijk contract (24 maanden)", "🎓 jongeren-/campuscontract"):
            self.assertTrue(any(l.startswith(verwacht) for l in labels), (verwacht, labels))

    def test_lage_huur_wordt_gemeld_met_een_vlag(self):
        # Saffierstraat en Granaatstraat via Rentola (4 nov): niet weglaten, wel opvallen
        for prijs in (932, 764):
            reden, labels = self.check("Mooi appartement met twee slaapkamers.", prijs=prijs)
            self.assertIsNone(reden)
            self.assertTrue(any(l.startswith("🚩 erg lage huur") for l in labels), labels)
        _, labels = self.check("Mooi appartement met twee slaapkamers.", prijs=933)
        self.assertFalse(any(l.startswith("🚩 erg lage huur") for l in labels), labels)
        self.assertTrue(any(l.startswith("🏷 middenhuur") for l in labels), labels)
        self.assertEqual(self.check("Mooi appartement met twee slaapkamers.", prijs=2400)[1], [])

    def test_gemeubileerd(self):
        self.assertEqual(self.check("Overeenkomst Onbepaalde tijd Te huur Oplevering Gemeubileerd")[0], "gemeubileerd")
        self.assertEqual(self.check("Fully furnished apartment")[0], "gemeubileerd")
        reden, labels = self.check("Kan gemeubileerd of gestoffeerd worden opgeleverd")  # keuze: wel melden
        self.assertIsNone(reden)
        self.assertTrue(any(l.startswith("🛋") for l in labels), labels)

    def test_echte_advertenties_30_oktober(self):
        """Zinnen uit advertenties die op 30 oktober ten onrechte als melding binnenkwamen."""
        valeriusstraat = ("Looking for working professionals or retiree; quiet, respectful and looking to call the "
                          "apartment their 'home'.  No  students will be accepted. Contract will start ASAP.")
        self.assertIsNotNone(self.check(valeriusstraat)[0])
        self.assertIsNotNone(self.check("No  students will be accepted.")[0])  # dubbele spatie
        self.assertIsNotNone(self.check("Looking for working professionals or retiree")[0])
        self.assertIsNotNone(self.check("De woning zal niet aan delers worden verhuurd.")[0])  # Heemstedestraat
        self.assertIsNotNone(self.check("- Goede ligging - Niet geschikt om te delen - Inkomenseis 3x de huur")[0])
        # Kerkstraat: terecht gemeld; 'twee slaapkamers' in woorden, inkomenseis zonder garantsteller → waarschuwing
        kerkstraat = ("Geschikt voor 2 woningdelers OMSCHRIJVING / INDELING Entree op de derde verdieping; twee "
                      "slaapkamers aan de achterzijde van de woning. Inkomenseis: netto minimaal 2,5 keer de huurprijs")
        reden, labels = self.check(kerkstraat)
        self.assertIsNone(reden)
        self.assertTrue(labels[0].startswith("⚠️ INKOMENSEIS 2,5× HUUR"), labels)

    def test_ongemeubileerd_is_niet_gemeubileerd(self):
        for t in ["Ongemeubileerd appartement", "Unfurnished apartment", "Semi-furnished, un-furnished on request"]:
            _, labels = self.check(t)
            self.assertFalse(any("gemeubileerd" in l for l in labels), (t, labels))

    def test_middenhuur(self):
        _, labels = self.check("", prijs=1150)
        self.assertTrue(any(l.startswith("🏷 middenhuur") for l in labels), labels)
        _, labels = self.check("", prijs=2400)
        self.assertFalse(any(l.startswith("🏷") for l in labels), labels)

    def test_rode_vlaggen(self):
        _, labels = self.check("Waarborgsom: 3 maanden huur. Bemiddelingskosten € 500.", prijs=2000)
        self.assertTrue(any("waarborgsom 3.0×" in l for l in labels), labels)
        self.assertTrue(any("bemiddelingskosten" in l for l in labels), labels)
        _, labels = self.check("Waarborgsom 2 maanden. Geen bemiddelingskosten. No agency fee.", prijs=2000)
        self.assertFalse(any(l.startswith("🚩") for l in labels), labels)
        _, labels = self.check("I live abroad, I will send the keys by mail after payment via Western Union")
        self.assertTrue(any("oplichting" in l for l in labels), labels)
        _, labels = self.check("Onderhuur voor een jaar")
        self.assertTrue(any("onderhuur" in l for l in labels), labels)

    def test_later_beschikbaar(self):
        _, labels = self.check("", beschikbaar=datetime.now() + timedelta(days=120))
        self.assertTrue(any(l.startswith("📅") for l in labels), labels)
        _, labels = self.check("", beschikbaar=datetime.now() + timedelta(days=20))
        self.assertFalse(any(l.startswith("📅") for l in labels), labels)


class Wijken(unittest.TestCase):
    """Echte adressen binnen en buiten het zoekgebied."""

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
            dict(straat="Vrolikstraat", huisnummer="64"),  # Oost, voorbij de Wibautstraat
            dict(straat="Nageljongenstraat", huisnummer="42", postcode="1033PE"),  # Noord
            dict(straat="Sumatrakade", huisnummer="100"),  # Oostelijk Havengebied
            dict(straat="Kattenburgerstraat", huisnummer="5"),  # Oostelijke Eilanden: bewust niet
            # wel de goede wijk (Haarlemmerbuurt, Nieuwmarkt/Lastage), maar een uitgesloten buurt
            dict(straat="Westerdoksdijk", huisnummer="259", postcode="1013AD"),  # Westerdokseiland (31 okt)
            dict(straat="Prinseneiland", huisnummer="20"),  # Westelijke eilanden
            dict(straat="Oosterdokskade", huisnummer="5"),  # Oosterdokseiland
        ]:
            reden, wijken = self.wijk(**kw)
            self.assertIsNotNone(reden, (kw, wijken))


class Elders(unittest.TestCase):
    """Dezelfde woning op twee sites: afwijzing op de ene site geldt ook voor de andere."""

    def test_koppeling(self):
        with tempfile.TemporaryDirectory() as tmp:
            opslag = Opslag(Path(tmp) / "t.db")
            makelaar = woning(bron="Hausing", id="a", straat="Weesperzijde", huisnummer="112-2", prijs=2300)
            opslag.markeer(makelaar, False, "tekst: 'geen studenten'")
            alert = woning(bron="Pararius", id="b", straat="Weesperzijde", huisnummer="112", prijs=2350)
            self.assertEqual(opslag.elders(alert, 14)[:3], ("Hausing", False, "tekst: 'geen studenten'"))
            anders = woning(bron="Funda", id="c", straat="Weesperzijde", huisnummer="40", prijs=2350)
            self.assertIsNone(opslag.elders(anders, 14))
            opslag.db.close()

    def test_prijsverlaging_wordt_opnieuw_bekeken(self):
        """Foeliedwarsstraat 2 (Hausing): eerst €2.750 te duur, op 2 november €2.600."""
        with tempfile.TemporaryDirectory() as tmp:
            opslag = Opslag(Path(tmp) / "t.db")
            w = woning(bron="Hausing", id="foelie", straat="Foeliedwarsstraat", prijs=2750)
            self.assertEqual(opslag.opnieuw_bekijken(w), (True, None))  # nieuw
            opslag.markeer(w, False, "te duur")
            self.assertEqual(opslag.opnieuw_bekijken(w), (False, None))  # zelfde prijs: niet opnieuw
            w.prijs = 2600
            self.assertEqual(opslag.opnieuw_bekijken(w), (True, 2750))  # goedkoper: opnieuw, met de oude prijs
            opslag.markeer(w, True)
            w.prijs = 2700
            self.assertEqual(opslag.opnieuw_bekijken(w), (False, None))  # duurder: niet opnieuw
            opslag.db.close()

    def test_alert_neemt_afwijzing_van_elders_over(self):
        """Stadionweg, 2 november: Pararius zei '5 kamers', Rentola wist dat het 3 slaapkamers waren (te duur)."""
        from woningzoeker.__main__ import oordeel_elders

        alert = woning(bron="Pararius", id="p", straat="Stadionweg", prijs=3500, kamers=5, slaapkamers=None)
        rentola = ("Rentola", False, "te duur (€3500 kaal, max €3250 bij 3 slaapkamers)", "https://rentola.nl/x")
        self.assertIn("te duur", oordeel_elders(alert, rentola))
        self.assertIn("volgens Rentola", oordeel_elders(alert, rentola))
        # wat alleen over die andere site zegt dat iets ontbrak, telt niet
        self.assertIsNone(oordeel_elders(alert, ("Rentola", False, "wijk onbekend", "x")))
        self.assertIsNone(oordeel_elders(alert, ("Rentola", False, "aantal slaapkamers onbekend", "x")))
        # tussen twee gewone sites blijft het als voorheen: alleen afwijzingen over de voorwaarden
        hausing = woning(bron="Hausing", id="h", straat="Stadionweg", prijs=3500)
        self.assertIsNone(oordeel_elders(hausing, rentola))
        self.assertIsNotNone(oordeel_elders(hausing, ("Rentola", False, "tekst: 'no students'", "x")))
        self.assertEqual(oordeel_elders(alert, ("Rentola", True, "", "x")), "al gemeld via Rentola")


if __name__ == "__main__":
    unittest.main()
