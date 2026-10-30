"""Herkenning van prijs/kamers/adres in vrije tekst, links en e-mailalerts. Draaien met: python -m unittest -v"""

import unittest
from email.message import EmailMessage
from email.utils import format_datetime
from datetime import datetime, timezone

from woningzoeker import tekst as t
from woningzoeker.bronnen.gmail import Gmail
from woningzoeker.bronnen.makelaar import _adres_uit_url


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

    def test_incl_excl_en_postcode(self):
        self.assertFalse(t.incl_excl("€ 2.250 p.m. excl."))
        self.assertTrue(t.incl_excl("€ 2.250 per maand inclusief servicekosten"))
        self.assertEqual(t.postcode("Weesperzijde 12, 1091 EL Amsterdam"), "1091EL")
        self.assertEqual(t.postcode("€ 2450 PM"), "")  # bedrag is geen postcode

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
                self.assertEqual(_adres_uit_url(url), verwacht)


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
        self.assertEqual(w.foto, "https://casco.pararius.nl/foto.jpg")
        kamer = next(x for x in woningen if "kinkerstraat" in x.url)
        self.assertEqual(kamer.soort, "kamer")


if __name__ == "__main__":
    unittest.main()
