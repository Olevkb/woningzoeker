"""Herkenning van prijs/kamers/adres in vrije tekst, links en e-mailalerts. Draaien met: python -m unittest -v"""

import unittest
from email.message import EmailMessage
from email.utils import format_datetime
from datetime import datetime, timezone

from woningzoeker import tekst as t
from woningzoeker.bronnen.gmail import Gmail
from woningzoeker.bronnen.makelaar import adres_uit_url


class Tekst(unittest.TestCase):
    def test_kaartjes(self):
        gevallen = [
            # tekst, prijs, m2, slaapkamers, kamers
            ("€2.400 Bedrooms 2 Size 96 m²", 2400, 96, 2, None),
            ("Woonoppervlak 27,7 m² Inhoud 70 m³ Aantal kamers 1 kamers € 932,93 Huurprijs per maand", 932, 27, None, 1),
            ("Bedrooms 2 Bathrooms 1 Size 80 sq. m.", None, 80, 2, None),
            ("3-kamer appartement, 2 slaapkamers, 72m2, € 2.250 p.m. excl.", 2250, 72, 2, 3),
            ("Borg € 5.000 | Huurprijs € 2.100,- per maand | 4 kamers", 2100, None, None, 4),
        ]
        for tekst, prijs, m2, slpk, kamers in gevallen:
            with self.subTest(tekst=tekst):
                self.assertEqual(t.prijs(tekst), prijs)
                self.assertEqual(t.m2(tekst), m2)
                self.assertEqual(t.slaapkamers(tekst), slpk)
                self.assertEqual(t.kamers(tekst), kamers)

    def test_kamers_in_woorden(self):
        self.assertEqual(t.slaapkamers("twee slaapkamers aan de achterzijde"), 2)
        self.assertEqual(t.slaapkamers("Twee ruime slaapkamers"), 2)
        self.assertEqual(t.slaapkamers("A bright two-bedroom apartment"), 2)
        self.assertEqual(t.slaapkamers("Lovely 3-bed flat"), 3)
        self.assertEqual(t.slaapkamers("één slaapkamer en een studeerkamer"), 1)
        self.assertIsNone(t.slaapkamers("een ruime slaapkamer"))  # 'een' is hier een lidwoord
        self.assertEqual(t.kamers("Driekamerappartement op de tweede verdieping"), 3)

    def test_prijssoort(self):
        gevallen = {
            "€ 2.250 p.m. excl.": "kaal",
            "€ 2850 excl. utilities": "kaal",
            "€ 2.250 per maand inclusief servicekosten": "service",
            "€ 2.250 incl. servicekosten, excl. g/w/e": "service",
            "€ 1.950 all-in": "alles",
            "€ 1.950 incl. gas, water en licht": "alles",
            "€ 1.950 incl.": "service",
            "€ 1.950 per maand": None,
            "Borg € 5.000 excl. | Huur € 2.100 incl. servicekosten": "service",  # kijkt naar het huurbedrag
        }
        for tekst, soort in gevallen.items():
            with self.subTest(tekst=tekst):
                self.assertEqual(t.prijs_soort(tekst, t.prijs(tekst)), soort)

    def test_postcode(self):
        self.assertEqual(t.postcode("Weesperzijde 12, 1091 EL Amsterdam"), "1091EL")
        self.assertEqual(t.postcode("€ 2450 PM"), "")  # bedrag is geen postcode

    def test_datums(self):
        self.assertEqual(t.beschikbaar("Beschikbaar per 01-12-2026"), datetime(2026, 12, 1))
        self.assertEqual(t.beschikbaar("Available from 1 January 2027"), datetime(2027, 1, 1))
        self.assertEqual(t.beschikbaar("Beschikbaarheid: februari 2027"), datetime(2027, 2, 1))
        self.assertEqual(t.beschikbaar("Ingangsdatum: 2026-11-15"), datetime(2026, 11, 15))
        self.assertEqual(t.beschikbaar("Beschikbaar: per direct").date(), datetime.now().date())
        self.assertIsNone(t.beschikbaar("Bouwjaar 1930"))

    def test_borg(self):
        self.assertEqual(t.borg_maanden("Waarborgsom: 2 maanden kale huur", 2000), 2.0)
        self.assertEqual(t.borg_maanden("Deposit € 6.000", 2000), 3.0)
        self.assertIsNone(t.borg_maanden("Geen vermelding", 2000))

    def test_adres_zonder_voorvoegsel(self):
        self.assertEqual(t.adres("Appartement Weesperzijde 112"), ("Weesperzijde", "112"))
        self.assertEqual(t.adres("Nieuw Jacob Catskade 35F"), ("Jacob Catskade", "35F"))

    def test_verhuurd(self):
        self.assertTrue(t.is_verhuurd("Onder optie | 1059 AW Amsterdam"))
        self.assertFalse(t.is_verhuurd("Nieuw | 1059 AW Amsterdam | te huur"))


class AdresUitLink(unittest.TestCase):
    def test_links(self):
        gevallen = {
            "https://www.vanderlinden.nl/huurwoning/Wijnsilostraat-12-Amsterdam/2561/": ("Wijnsilostraat", "12", ""),
            "https://www.expathousing.com/available-properties/anna-blamansingel-1102sx-amsterdam-3346/": ("Anna Blamansingel", "", "1102SX"),
            "https://www.expathousing.com/available-properties/burgemeester-fockstraat-1063-cz-amsterdam-3180/": ("Burgemeester Fockstraat", "", "1063CZ"),
            "https://www.vastgoednederland.nl/huurwoningen/amsterdam/woning-673747-jacob-catskade-35f": ("Jacob Catskade", "35f", ""),
            "https://www.smitenheinen.nl/woningaanbod/huur/amsterdam/rijnsburgstraat-36-4-amsterdam": ("Rijnsburgstraat", "36-4", ""),
            "https://hausing.com/for-rent/albert-cuypstraat-dhw5r": ("Albert Cuypstraat", "", ""),
            "https://hausing.com/for-rent/smts": ("", "", ""),
            "https://hausing.com/for-rent/leiduinstraat-iwlsn": ("Leiduinstraat", "", ""),
        }
        for url, verwacht in gevallen.items():
            with self.subTest(url=url):
                self.assertEqual(adres_uit_url(url), verwacht)


class EmailAlert(unittest.TestCase):
    def test_pararius_alert(self):
        html = """<html><body><table>
          <tr><td><a href="https://www.pararius.nl/appartement-te-huur/amsterdam/1a2b3c4d/weesperzijde?utm_source=alert">
              <img src="https://casco.pararius.nl/foto.jpg"></a>
            <a href="https://www.pararius.nl/appartement-te-huur/amsterdam/1a2b3c4d/weesperzijde?utm_source=alert">Appartement Weesperzijde 112</a>
            <p>1091 EL Amsterdam (Weesperzijde)</p><p>€ 2.300 per maand</p><p>78 m² · 3 kamers</p></td></tr>
          <tr><td><a href="https://www.pararius.nl/kamer-te-huur/amsterdam/9z8y7x6w/kinkerstraat">Kamer Kinkerstraat 5</a>
            <p>1053 DR Amsterdam</p><p>€ 900 per maand</p><p>14 m² · 1 kamer</p></td></tr>
        </table></body></html>"""
        bericht = EmailMessage()
        bericht["From"] = "Pararius <noreply@pararius.nl>"
        bericht["Date"] = format_datetime(datetime.now(timezone.utc))
        bericht.set_content("zie html")
        bericht.add_alternative(html, subtype="html")

        woningen = Gmail().uit_bericht(bericht)
        self.assertEqual(len(woningen), 2)
        w = next(x for x in woningen if "weesperzijde" in x.url)
        self.assertEqual(w.bron, "Pararius")
        self.assertEqual(w.url, "https://www.pararius.nl/appartement-te-huur/amsterdam/1a2b3c4d/weesperzijde")
        self.assertEqual((w.prijs, w.m2, w.kamers, w.postcode, w.plaats), (2300, 78, 3, "1091EL", "Amsterdam"))
        self.assertEqual((w.straat, w.huisnummer), ("Weesperzijde", "112"))
        self.assertEqual(w.foto, "https://casco.pararius.nl/foto.jpg")
        self.assertIn("€ 2.300 per maand", w.omschrijving)  # de tekst uit de mail gaat door de tekstfilters
        self.assertTrue(w.labels[0].startswith("❔ via Pararius-alert"))
        kamer = next(x for x in woningen if "kinkerstraat" in x.url)
        self.assertEqual(kamer.soort, "kamer")

    def test_budget_per_slaapkamer_geldt_ook_voor_alerts(self):
        """Een alert tot €4.200 bevat ook dure kleine woningen; die moeten er alsnog uit."""
        from pathlib import Path

        import yaml

        from woningzoeker.filters import Filter

        cfg = yaml.safe_load((Path(__file__).resolve().parent.parent / "config.yaml").read_text(encoding="utf-8"))
        kaarten = {
            "duur-2-slpk": ("€ 4.000 per maand", "85 m² · 2 slaapkamers", False),
            "4-slpk": ("€ 4.000 per maand", "130 m² · 4 slaapkamers", True),
            "5-kamers": ("€ 4.000 per maand", "120 m² · 5 kamers", True),  # 5 kamers ≈ 4 slaapkamers
            "3-slpk-te-duur": ("€ 3.400 per maand", "95 m² · 3 slaapkamers", False),
            "goedkoop-2-slpk": ("€ 2.450 per maand", "70 m² · 2 slaapkamers", True),
            "onbekend": ("€ 4.000 per maand", "110 m²", False),  # kamers niet vermeld → budget voor 2
        }
        html = "<table>" + "".join(
            f'<tr><td><a href="https://www.funda.nl/detail/huur/amsterdam/appartement-{slug}-1/43{i:06}/">Appartement Teststraat {i}</a>'
            f"<p>1071 AB Amsterdam</p><p>{prijs}</p><p>{maten}</p></td></tr>"
            for i, (slug, (prijs, maten, _)) in enumerate(kaarten.items(), 1)
        ) + "</table>"
        bericht = EmailMessage()
        bericht["From"] = "Funda <noreply@funda.nl>"
        bericht["Date"] = format_datetime(datetime.now(timezone.utc))
        bericht.set_content("zie html")
        bericht.add_alternative(html, subtype="html")

        filt = Filter(cfg)
        for w in Gmail().uit_bericht(bericht):
            slug = next(s for s in kaarten if s in w.url)
            with self.subTest(slug):
                self.assertEqual(filt.basis(w) is None, kaarten[slug][2], (slug, filt.basis(w)))

    def test_funda_link_geeft_adres(self):
        self.assertEqual(
            adres_uit_url("https://www.funda.nl/detail/huur/amsterdam/appartement-weesperzijde-112-h/43123456/"),
            ("Weesperzijde", "112-h", ""),
        )


if __name__ == "__main__":
    unittest.main()
