# Eisen woningzoeker (versie 3, 30 oktober 2026)

Akkoord gegeven en ingebouwd op 30 oktober 2026. De instellingen staan in `config.yaml`; elke eis heeft een test in `tests/test_filters.py`.

## 1. Budget

De huurtoeslag is **€525 voor de hele woning**, dus die wordt verdeeld over het aantal bewoners. Met meer bewoners mag het bedrag per persoon ook lager. Liever minder dan het maximum.

| Slaapkamers = bewoners | Max p.p. alles incl. | Totaal incl. toeslag | **Max kale huur** | Incl. servicekosten | Incl. alles |
|---|---|---|---|---|---|
| 2 | €1.200 | 2 × €1.200 + €525 = €2.925 | **€2.600** | €2.750 | €2.925 |
| 3 | €1.000 | 3 × €1.000 + €525 = €3.525 | **€3.250** | €3.400 | €3.525 |
| 4 | €1.000 | 4 × €1.000 + €525 = €4.525 | **€4.200** | €4.350 | €4.525 |

- Staat er niet bij of de prijs incl. of excl. is, dan telt hij als kale huur (strengste).
- De zoeker kijkt naar wat er met het aantal slaapkamers mogelijk is. Bijvoorbeeld: 3 slaapkamers voor €3.000 → melden met label 👥 "betaalbaar met 3 personen". Met 3 of meer bewoners heeft de verhuurder een omzettingsvergunning nodig.
- Elke melding toont de prijs per persoon na toeslag, voor 2 personen en (bij 3+ slaapkamers) ook voor 3. Goedkoopste bovenaan.
- De €2.600 en €3.250 lukken alleen mét huurtoeslag, daarom zijn "zelfstandig" en "inschrijven mogelijk" harde eisen.

## 2. Harde eisen (anders geen melding)

1. **Wijk**: zie de lijst hieronder.
2. **Prijs**: zie budget.
3. **Minimaal 2 slaapkamers** (of minimaal 3 kamers als het aantal slaapkamers niet vermeld is).
4. **Minimaal 45 m²**.
5. **Huurtoeslag mogelijk**: zelfstandige woning (eigen voordeur, keuken, badkamer), inschrijven toegestaan, en een echt huurcontract. Antikraak, leegstandsbeheer en bruikleen vallen af.
6. **Studenten toegestaan**. Valt af bij: "geen studenten", "professionals only", "alleen werkenden", "company let / via werkgever", "55+ / seniorenwoning".
7. **Geschikt voor vrienden**. Valt af bij: "max 1 persoon", "alleen voor een stel / couples only", "geen woningdelers".
8. **Garantsteller uitgesloten**. Valt af bij: "geen garantsteller", "guarantor not accepted", "eigen inkomen vereist". (Een inkomenseis zónder die uitsluiting wordt wel gemeld, zie 3.)
9. **Geen short stay**: contracten korter dan 6 maanden vallen af.

Staat iets niet in de advertentie, dan valt hij niet af. Alleen wat er expliciet staat telt.

## 3. Inkomenseis: drie gevallen

| Wat staat er | Wat de zoeker doet |
|---|---|
| Inkomenseis + garantsteller toegestaan (bv. "inkomen 3× huur of garantsteller") | melden met 🤝 **garantsteller toegestaan** |
| Inkomenseis, garantsteller wordt **niet genoemd** | melden, met bovenaan in hoofdletters: ⚠️ **INKOMENSEIS 4× HUUR – GARANTSTELLER NIET GENOEMD, VRAAG DIT EERST NA** |
| Garantsteller expliciet uitgesloten | niet melden (eis 8) |

Waarom het middelste geval niet wegfilteren: veel verhuurders noemen alleen hun standaard-inkomenseis, maar accepteren in de praktijk wel een garantsteller. Eén mailtje of belletje maakt dat duidelijk. Na een week kijken we hoe vaak dit label voorkomt en of het iets oplevert.

## 4. Overige labels

- ⏳ tijdelijk contract, met de duur
- 🎓 jongeren- of campuscontract (pluspunt voor studenten)
- 🛋 gemeubileerd (jullie liever niet)
- 🏷 middenhuur (€932,93–€1.228,07): je hebt een huisvestingsvergunning van de gemeente nodig
- 🚩 erg lage huur (onder €932,93): waarschijnlijk sociale huur of een kamer; wordt wel gemeld (besluit 4 nov)
- 📅 pas over meer dan 2 maanden beschikbaar
- 👥 alleen betaalbaar met een extra huisgenoot
- 🚩 waarborgsom hoger dan 2 maanden kale huur, bemiddelingskosten voor de huurder, onderhuur, of signalen van oplichting
- ❔ voorwaarden niet gecontroleerd (alleen bekend uit een e-mailalert)

## 5. E-mailalerts (Pararius, Funda, Huurwoningen.nl)

De alert bevat meestal alleen adres, prijs, m² en kamers. Eisen 1–4 controleert de zoeker op de mail zelf. Daarna zoekt hij dezelfde woning bij de makelaar (op adres en prijs) om de rest te controleren. Lukt dat niet, dan krijg je hem met ❔.

## 6. Wijken (officiële namen)

| Gebied | Wijken |
|---|---|
| Centrum | Burgwallen-Oude Zijde, Burgwallen-Nieuwe Zijde, Grachtengordel-West, Grachtengordel-Zuid, Jordaan, Haarlemmerbuurt, Nieuwmarkt/Lastage, De Weteringschans, Weesperbuurt/Plantage |
| De Pijp | Oude Pijp, Nieuwe Pijp, Zuid Pijp |
| Zuid | Museumkwartier, Willemspark, Schinkelbuurt, Hoofddorppleinbuurt, Stadionbuurt, Apollobuurt, Scheldebuurt, IJselbuurt, Rijnbuurt, Prinses Irenebuurt e.o., Zuidas |
| Oost | alleen Weesperzijde (Amstel tot Wibautstraat) |
| Niet (buurten binnen bovenstaande wijken, besloten 31 okt) | Westerdokseiland, Westelijke eilanden (Prinseneiland, Bickerseiland, Realeneiland), Planciusbuurt, Oosterdokseiland |
| Niet | o.a. Oostelijke Eilanden/Kadijken, Buitenveldert, Oud-West, Oosterparkbuurt, Spaarndammerbuurt, Noord, Nieuw-West, Zuidoost |

## 7. Besloten

- Oostelijke Eilanden/Kadijken: niet
- Marktplaats: niet
- Inkomenseis zonder vermelding van garantsteller: wel melden, met groot label (zie 3)
- Gemeubileerd: uitsluiten, tenzij ook ongemeubileerd aangeboden (31 okt)
- Aantal slaapkamers onbekend na het lezen van de advertentie: niet melden (31 okt)
- Mijn DAK (corporaties): niet, i.v.m. inschrijfduur/punten en middenhuur (31 okt)


Bronnen: [Rijksoverheid huurtoeslag 2026](https://www.rijksoverheid.nl/actueel/nieuws/2025/11/24/meer-mensen-in-aanmerking-huurtoeslag), [Belastingdienst](https://www.belastingdienst.nl/wps/wcm/connect/nl/huurtoeslag/content/huurtoeslag-verandert-vanaf-2026), [Huisvestingsverordening Amsterdam](https://lokaleregelgeving.overheid.nl/CVDR706038/), [Ymere over middenhuur](https://www.ymere.nl/ik-zoek/middenhuur-en-vrije-sector/toewijzingseisen-middenhuur-en-vrije-sector/).

## 9. Woningen waarvan de voorwaarden niet te controleren zijn (besloten 2 november)

Bij e-mailalerts van Pararius/Funda en bij Rentola-advertenties zonder beschrijving staat niet of studenten, delers of een garantsteller welkom zijn.

1. Staat dezelfde woning op een andere site die de zoeker al zag, dan geldt wat die site wist (bv. te duur bij 3 slaapkamers, "no students").
2. Staat hij daar maar is hij nog niet afgewezen, dan leest de zoeker daar de volledige advertentie en controleert hij álle eisen ("✅ voorwaarden gecontroleerd via …").
3. Lukt beide niet, dan komt de woning als kort bericht met **❔ ZELF CHECKEN** bovenaan, zonder foto.

Verder: gaat de prijs van een eerder afgewezen woning omlaag, dan wordt hij opnieuw bekeken en gemeld met "📉 prijs verlaagd".
