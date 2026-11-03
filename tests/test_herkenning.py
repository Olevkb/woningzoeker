"""Herkenning van prijs/kamers/adres in vrije tekst, links en e-mailalerts. Draaien met: python -m unittest -v"""

import unittest
from email.message import EmailMessage
from email.utils import format_datetime
from datetime import datetime, timezone

from woningzoeker import tekst as t
from woningzoeker.bronnen.gmail import Gmail
from woningzoeker.bronnen.makelaar import adres_uit_url
from woningzoeker.locatie import zelfde_straat


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

    def test_kenmerkenlijst_label_of_getal_eerst(self):
        # echte teksten van 2 november; 'Kamers 2 Slaapkamers 1' werd gelezen als 2 slaapkamers
        gevallen = [
            # tekst, kamers, slaapkamers, m2
            ("Woonoppervlakte 61m 2 Inhoud 153m 3 Kamers 2 Slaapkamers 1 Woonlagen 1", 2, 1, 61),  # HB Housing
            ("Appartement 4 kamers 3 slaapkamers 1 badkamer Bouwjaar 2025 125 m² gebruiksoppervlakte", 4, 3, 125),  # Horatio
            ("Apartment 3 rooms 2 bedrooms 1 Bathroom Construction year 1910 103 m² liveable area", 3, 2, 103),
            ("Woonoppervlakte 71 m 2 Slaapkamers 2 Prijs € 4.250,- p/m", None, 2, 71),  # BIC Vastgoed
            ("Oppervlakte 80 m 2 Aantal kamers 1 Aantal slaapkamers 0 Beschikbaar per", 1, 0, 80),  # Hoen
            ("Kamers: 3 Slaapkamers: 2", 3, 2, None),
        ]
        for tekst, kamers, slpk, m2 in gevallen:
            with self.subTest(tekst=tekst):
                self.assertEqual((t.kamers(tekst), t.slaapkamers(tekst), t.m2(tekst)), (kamers, slpk, m2))

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


class Maatwerkbronnen(unittest.TestCase):
    def test_vbt_woning(self):
        from woningzoeker.bronnen.vbt import Vbt

        huis = {  # opbouw zoals de API van vb&t hem op 31 oktober teruggaf
            "id": "abc123", "url": "/woning/amsterdam-westerdoksdijk-259b", "image": "/images/x/westerdoksdijk",
            "address": {"city": "Amsterdam", "house": "Westerdoksdijk 259-B"},
            "prices": {"category": "rent", "rental": {"price": 1950, "serviceCharges": 120, "securityDeposit": 0, "minMonths": 12}},
            "status": {"name": "available", "code": 1}, "attributes": {"type": {"category": "apartment"}},
            "plot": 77, "rooms": 3, "acceptance": "2026-12-01T00:00:00.000Z", "coordinate": [4.89, 52.38], "usps": [],
        }
        w = Vbt()._woning(huis)
        self.assertEqual((w.straat, w.huisnummer, w.prijs, w.prijs_soort, w.kamers, w.m2, w.soort), ("Westerdoksdijk", "259-B", 1950, "kaal", 3, 77, "appartement"))
        self.assertIsNone(Vbt()._woning({**huis, "status": {"name": "rentinuse"}}))  # al verhuurd
        self.assertIsNone(Vbt()._woning({**huis, "address": {"city": "Rotterdam", "house": "Coolsingel 1"}}))

    def test_status_van_advertentiepagina_wint(self):
        from pathlib import Path

        import yaml

        from woningzoeker.filters import Filter
        from woningzoeker.model import Woning

        cfg = yaml.safe_load((Path(__file__).resolve().parent.parent / "config.yaml").read_text(encoding="utf-8"))
        w = Woning(bron="Vesteda", id="1", url="x", plaats="Amsterdam", prijs=2040, slaapkamers=2, m2=97, status="gereserveerd")
        self.assertEqual(Filter(cfg).basis(w), "gereserveerd")


class Melding(unittest.TestCase):
    def test_zoek_de_makelaar_alleen_bij_betaalde_verzamelsites(self):
        from urllib.parse import parse_qs, urlparse

        from woningzoeker.model import Woning
        from woningzoeker.telegram import knoppen_voor

        rentola = Woning(bron="Rentola", id="1", url="https://rentola.nl/listings/x", straat="Kerkstraat", huisnummer="256-1", plaats="Amsterdam")
        knoppen = knoppen_voor(rentola)["inline_keyboard"]
        self.assertEqual(len(knoppen), 2)
        zoek = parse_qs(urlparse(knoppen[1][0]["url"]).query)["q"][0]
        self.assertIn('"Kerkstraat 256-1" Amsterdam huur', zoek)
        self.assertIn("-site:rentola.nl", zoek)

        hausing = Woning(bron="Hausing", id="2", url="https://hausing.com/for-rent/x", straat="Kerkstraat", plaats="Amsterdam")
        self.assertEqual(len(knoppen_voor(hausing)["inline_keyboard"]), 1)  # bij de makelaar zelf: geen extra knop


class Onzeker(unittest.TestCase):
    def test_wanneer_zelf_checken(self):
        from woningzoeker.__main__ import onzeker_reden
        from woningzoeker.model import Woning
        from woningzoeker.telegram import opmaak_kort

        lang = "Ruim appartement met twee slaapkamers. " * 20
        alert = Woning(bron="Pararius", id="1", url="x", straat="Stadionweg", prijs=3500, omschrijving=lang)
        self.assertIn("samenvatting", onzeker_reden(alert))
        alert.labels.append("✅ voorwaarden gecontroleerd via Hausing")  # wel gecontroleerd via een andere site
        self.assertEqual(onzeker_reden(alert), "")
        rentola = Woning(bron="Rentola", id="2", url="x", straat="Kerkstraat", prijs=2600, omschrijving="")
        self.assertIn("geen beschrijving", onzeker_reden(rentola))
        makelaar = Woning(bron="Hausing", id="3", url="x", straat="Kerkstraat", prijs=2600, omschrijving=lang)
        self.assertEqual(onzeker_reden(makelaar), "")

        rentola.onzeker, rentola.wijk, rentola.slaapkamers, rentola.m2 = onzeker_reden(rentola), "Grachtengordel-Zuid", 2, 72
        tekst = opmaak_kort(rentola, {"huurtoeslag": {"per_maand": 525}})
        self.assertTrue(tekst.startswith("❔ <b>ZELF CHECKEN</b>"))
        self.assertIn("Kerkstraat", tekst)
        self.assertIn("€2.600 · 2 slaapkamers · 72 m² · via Rentola", tekst)


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
        self.assertEqual(w.labels, [])  # onzekerheid wordt bij het melden bepaald (kort ZELF CHECKEN-bericht)
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

    def test_echte_pararius_opmaak_31_oktober(self):
        """Opmaak van de echte Pararius-alert: doorstuurlinks, alleen een straatnaam als titel, foto als achtergrond."""

        def kaart(n, straat, adres, prijs, maten):
            link = f"https://url2220.pararius.nl/ls/click?upn=u001.test{n}"
            return f"""<table class="listing-card"><tr><td><table class="listing-card__inner">
              <tr class="listing-card-image"><td height="180" style="background-image:url('https://casco.pararius.nl/{n}.jpg')">
                <a href="{link}"><span></span></a></td></tr>
              <tr class="listing-card-content"><td><div>
                <a href="{link}"><span><strong>{straat}</strong></span></a><br>
                <span class="listing-card-content-address">{adres}</span><br>
                <strong>{prijs}</strong><br> {maten}</div></td></tr></table></td></tr></table>"""

        html = (
            '<a href="https://url2220.pararius.nl/ls/click?upn=u001.plus">Lees meer over de voordelen van Pararius+</a>'
            "<p>Pararius+ voor € 29,95 per maand</p>"
            + kaart(1, "Vespuccistraat", "1057CM Amsterdam (De Baarsjes)", "€ 2.050 per maand", "61 m² · 3 kamers · Bouwjaar 1926")
            + kaart(2, "Kanaalstraat", "1054XG Amsterdam (Overtoomse Sluis)", "€ 2.400 per maand", "70 m² · 3 kamers · Bouwjaar 1910")
            + '<a href="https://url2220.pararius.nl/ls/click?upn=u001.alle">Bekijk alle woningen</a>'
            + '<a href="https://url2220.pararius.nl/ls/click?upn=u001.uit">Uitschrijven</a>'
        )
        bericht = EmailMessage()
        bericht["From"] = "Pararius <noreply@pararius.nl>"
        bericht["Date"] = format_datetime(datetime.now(timezone.utc))
        bericht.set_content("zie html")
        bericht.add_alternative(html, subtype="html")

        woningen = Gmail().uit_bericht(bericht)
        self.assertEqual([w.straat for w in woningen], ["Vespuccistraat", "Kanaalstraat"])  # geen reclame, geen knoppen
        w = woningen[0]
        self.assertEqual((w.prijs, w.m2, w.kamers, w.postcode, w.plaats), (2050, 61, 3, "1057CM", "Amsterdam"))
        self.assertEqual(w.url, "https://url2220.pararius.nl/ls/click?upn=u001.test1")
        self.assertEqual(w.foto, "https://casco.pararius.nl/1.jpg")
        self.assertEqual(w.id, "vespuccistraat--1057CM-2050")  # vast, ook als dezelfde woning later met een andere link komt

    def test_echte_funda_opmaak_1_november(self):
        """Funda-alert: foto in een eigen blok boven de tekst, doorstuurlinks via links.funda.nl."""

        def woning(n, foto, regels):
            link = f"https://links.funda.nl/s/c/test{n}"
            return (f'<table><tr><td class="pmr0"><table><tr><td class="col-lg-12-img"><a href="{link}"><img src="{foto}"></a>'
                    f'</td></tr></table></td></tr></table><table><tr><td><a href="{link}">{regels[0]}</a><br>'
                    + "<br>".join(regels[1:]) + "</td></tr></table>")

        html = (
            '<img src="https://library.iterable.com/2349/11011/funda-logo.png">'
            + woning(1, "https://cloud.funda.nl/tiara-media/aaa/1", ["Reyer Anslostraat 14 3", "1054 KV Amsterdam", "€ 2.450 /maand", "54 m² • 3 kamers"])
            + woning(2, "https://cloud.funda.nl/tiara-media/bbb/2", ["Durgerdammerdijk 1014 A", "1026 CR Amsterdam", "€ 2.540 /maand", "135 m² • 2 kamers"])
        )
        bericht = EmailMessage()
        bericht["From"] = "Funda <notificaties@service.funda.nl>"
        bericht["Date"] = format_datetime(datetime.now(timezone.utc))
        bericht.set_content("zie html")
        bericht.add_alternative(html, subtype="html")

        a, b = Gmail().uit_bericht(bericht)
        self.assertEqual((a.straat, a.postcode, a.prijs, a.m2, a.kamers), ("Reyer Anslostraat", "1054KV", 2450, 54, 3))
        self.assertEqual(a.foto, "https://cloud.funda.nl/tiara-media/aaa/1")  # eigen foto, niet het logo
        self.assertEqual(b.foto, "https://cloud.funda.nl/tiara-media/bbb/2")

    def test_funda_link_geeft_adres(self):
        self.assertEqual(
            adres_uit_url("https://www.funda.nl/detail/huur/amsterdam/appartement-weesperzijde-112-h/43123456/"),
            ("Weesperzijde", "112-h", ""),
        )



class Postcode(unittest.TestCase):
    def test_postcode_moet_bij_de_straat_horen(self):
        # Keizerskroon (2 nov): onder elke woning staat de postcode van het kantoor; die mag de wijk niet bepalen
        self.assertFalse(zelfde_straat("Barkentijnkade", "Keizersgracht"))
        self.assertTrue(zelfde_straat("1e Jan Steenstraat", "Eerste Jan Steenstraat"))
        self.assertTrue(zelfde_straat("Hans Frankfurthersingel", "P. Hans Frankfurthersingel"))
        self.assertTrue(zelfde_straat("Pr. Hendrikkade", "Prins Hendrikkade"))
        self.assertTrue(zelfde_straat("", "Keizersgracht"))  # straat onbekend: postcode is alles wat we hebben



class Bronstatus(unittest.TestCase):
    class Web:
        def __init__(self, html):
            self._html = html

        def html(self, url):
            return self._html

    def test_niets_in_amsterdam_is_geen_storing(self):
        # Heimstaden (3 nov): de hele lijst stond in andere plaatsen; dat is geen kapotte site
        from woningzoeker.bronnen.makelaar import Makelaar
        m = Makelaar(naam="Heimstaden", url="https://heimstaden.com/nl/huurwoningen/", link=r"(?i)^/nl/huurwoningen/amsterdam-")
        lijst = '<a href="/nl/huurwoningen/ALMERE-98m2-f265d2aa/">Almere</a><a href="/nl/huurwoningen/Breda-85m2-5bafa1ff/">Breda</a>'
        self.assertEqual(m.zoek(self.Web(lijst)), [])
        self.assertTrue(m.gezond([]))
        m.zoek(self.Web('<a href="/nl/contact/">Contact</a>'))
        self.assertFalse(m.gezond([]))  # helemaal geen advertenties meer: dan is de site echt veranderd

    def test_waarschuwing_pas_na_twee_uur_en_bericht_als_het_weer_werkt(self):
        import tempfile
        from datetime import timedelta
        from pathlib import Path
        from woningzoeker.__main__ import Zoeker
        from woningzoeker.opslag import Opslag

        class Melder:
            berichten = []

            def tekst(self, t):
                self.berichten.append(t)

        class Bron:
            naam, werkt = "Koops", False

            def zoek(self, web):
                if not self.werkt:
                    raise TimeoutError("Read timed out")
                return []

            def gezond(self, woningen):
                return True

        z = Zoeker.__new__(Zoeker)
        z.opslag, z.melder, z.web = Opslag(Path(tempfile.mkdtemp()) / "t.db"), Melder(), None
        bron = Bron()
        z._haal(bron, droog=False)
        z._haal(bron, droog=False)
        self.assertEqual(z.melder.berichten, [])  # korte storing: niets melden
        fouten = z.opslag.meta_haal("fouten")
        fouten["Koops"]["sinds"] = (datetime.now() - timedelta(hours=2, minutes=1)).isoformat()
        z.opslag.meta_bewaar("fouten", fouten)
        z._haal(bron, droog=False)
        z._haal(bron, droog=False)
        self.assertEqual(len(z.melder.berichten), 1)  # één keer waarschuwen, niet bij elke scan
        self.assertIn("werkt al 2 uur niet", z.melder.berichten[0])
        bron.werkt = True
        z._haal(bron, droog=False)
        self.assertEqual(z.melder.berichten[-1], "✅ Koops werkt weer.")

    def test_oude_teller_na_eerdere_waarschuwing_niet_opnieuw_melden(self):
        import tempfile
        from datetime import timedelta
        from pathlib import Path
        from woningzoeker.__main__ import Zoeker
        from woningzoeker.opslag import Opslag

        class Melder:
            berichten = []

            def tekst(self, t):
                self.berichten.append(t)

        class Bron:
            naam = "Van der Linden"

            def zoek(self, web):
                raise ConnectionError("SSLError")

        z = Zoeker.__new__(Zoeker)
        z.opslag, z.melder, z.web = Opslag(Path(tempfile.mkdtemp()) / "t.db"), Melder(), None
        z.opslag.meta_bewaar("fouten", {"Van der Linden": 238})  # opslag van vóór 3 november
        z._haal(Bron(), droog=False)
        fouten = z.opslag.meta_haal("fouten")
        fouten["Van der Linden"]["sinds"] = (datetime.now() - timedelta(hours=5)).isoformat()
        z.opslag.meta_bewaar("fouten", fouten)
        z._haal(Bron(), droog=False)
        self.assertEqual(z.melder.berichten, [])

    def test_herstel_na_waarschuwing_uit_oude_opslag(self):
        import tempfile
        from pathlib import Path
        from woningzoeker.__main__ import Zoeker
        from woningzoeker.opslag import Opslag

        class Melder:
            berichten = []

            def tekst(self, t):
                self.berichten.append(t)

        class Bron:
            naam = "Heimstaden"

            def zoek(self, web):
                return []

            def gezond(self, woningen):
                return True

        z = Zoeker.__new__(Zoeker)
        z.opslag, z.melder, z.web = Opslag(Path(tempfile.mkdtemp()) / "t.db"), Melder(), None
        z.opslag.meta_bewaar("fouten", {"Heimstaden": 29, "Koops": 2})  # Heimstaden kreeg al een waarschuwing
        z._haal(Bron(), droog=False)
        self.assertEqual(z.melder.berichten, ["✅ Heimstaden werkt weer."])
        self.assertEqual(z.opslag.meta_haal("fouten"), {"Koops": 2})


if __name__ == "__main__":
    unittest.main()
