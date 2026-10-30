# Woningzoeker Amsterdam

Scant elke 5 minuten huursites, makelaars en e-mailalerts op nieuwe huurwoningen die bij jullie passen. Je krijgt meteen een Telegram-bericht met foto, prijs, wijk, prijs per persoon na huurtoeslag en een directe link. Draait gratis op GitHub, ook als je laptop uit staat.

## Waar hij zoekt

**Huurportalen**: Rentola, Huurstunt, Kamernet, 123Wonen.

**Makelaars, verhuurders en verzamelsites** (`makelaars.yaml`): 27 bronnen, waaronder Hausing, Van der Linden, JLG, Homecrew, HousingNet, Vastgoed Nederland, Woonnet, Huurzone en Kamer.nl. Het volledige overzicht, ook van wat (nog) niet lukt, staat in `docs/bronnen.md`.

**E-mailalerts** van sites die scripts blokkeren: Pararius, Funda, Huurwoningen.nl. De zoeker leest je Gmail (alleen lezen, hij verwijdert of verplaatst niets) en haalt de alerts door dezelfde filters.

Elke site wordt beleefd benaderd: de zoeker houdt zich aan robots.txt, vraagt niet vaker dan nodig en omzeilt geen beveiliging.

### Alerts instellen op Pararius, Funda en Huurwoningen.nl

Maak op elke site een account met je Gmail-adres, zoek op Amsterdam, huur, tot €2.900, 2+ slaapkamers, en sla de zoekopdracht op met e-mailmelding **direct** (niet dagelijks). Stel de alerts gerust breder in dan nodig: de zoeker filtert zelf op wijk, prijs en voorwaarden.

## Wat er gefilterd wordt

De volledige eisen met uitleg staan in `docs/eisen.md`, de instellingen in `config.yaml`. Kort:

- **Budget per aantal bewoners** (€525 huurtoeslag voor de hele woning): 2 slaapkamers max €2.600 kale huur, 3 max €3.250, 4 max €4.200.
- **Minimaal 2 slaapkamers en 45 m²**, in jullie wijken: Centrum (incl. Jordaan, Haarlemmerbuurt, Plantage), De Pijp, Zuid en Weesperzijde (Amstel tot Wibautstraat). De wijk wordt per adres opgezocht bij PDOK, de officiële adressendienst van de overheid.
- **Overgeslagen:** geen huurtoeslag mogelijk (kamer, gedeelde keuken/badkamer, antikraak, niet inschrijven), geen studenten of alleen werkenden, niet voor vrienden ("max 1 persoon", "alleen een stel"), garantsteller uitgesloten, short stay.
- **Inkomenseis zonder garantsteller:** wel gemeld, met een grote waarschuwing bovenaan.
- **Labels:** 🤝 garantsteller mogelijk, ⏳ tijdelijk, 🛋 gemeubileerd, 🏷 middenhuur (vergunning nodig), 📅 later beschikbaar, 👥 alleen met extra huisgenoot, 🚩 borg/bemiddelingskosten/onderhuur/oplichting, ❔ alleen uit e-mailalert bekend.

Aanpassen kan op GitHub zelf: open `config.yaml`, klik op het potloodje, wijzig en klik op *Commit changes*. De volgende scan gebruikt het meteen.

## Eenmalig instellen

Alles in PowerShell, vanuit deze map.

1. Benodigdheden installeren:
   ```powershell
   python -m pip install --user -r requirements.txt
   ```
2. Telegram koppelen (maakt je eigen bot aan via @BotFather):
   ```powershell
   python setup_telegram.py
   ```
3. Gmail koppelen (met een app-wachtwoord, niet je gewone wachtwoord):
   ```powershell
   python setup_gmail.py
   ```
4. De geheimen naar GitHub sturen, zodat de scan daar kan inloggen. Ze komen versleuteld in je repository-instellingen en zijn niet openbaar:
   ```powershell
   & "C:\Program Files\GitHub CLI\gh.exe" secret set -f .env
   ```

Daarna start de scan vanzelf elke 5 minuten. Je krijgt elke dag een "nog actief"-bericht, en als een site langere tijd niet werkt krijg je een waarschuwing.

## Handige commando's

| Commando | Wat |
|---|---|
| `python -m woningzoeker --droog` | één scan, matches hier tonen in plaats van versturen |
| `python -m woningzoeker --test` | testbericht naar je telefoon |
| `python -m woningzoeker --test-makelaars` | controleren of elke makelaar nog werkt |
| `python -m woningzoeker --test-gmail` | tonen wat er uit je e-mailalerts gelezen wordt |
| `python -m unittest -v` | alle tests draaien |

De scans op GitHub bekijk je in het tabblad **Actions** van je repository. Daar kun je ook handmatig een scan starten (*Run workflow*).

## Een makelaar toevoegen

Voeg in `makelaars.yaml` een blok toe met de naam, de pagina met het huuraanbod en het patroon van de advertentielinks, en controleer het met `--test-makelaars`.

## Tips om kans te maken

- Reageer binnen een uur, met een korte standaardtekst klaar in je notities: wie jullie zijn, studie, garantsteller, inkomen garantsteller, gewenste ingangsdatum.
- Houd een map klaar met ID, inschrijvingsbewijs studie, werkgeversverklaring of loonstroken en een garantstellingsverklaring van je garantsteller.
- Betaal nooit iets vóór een bezichtiging en sleutels. Bij 🚩 extra opletten.
