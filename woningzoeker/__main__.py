"""Start de woningzoeker.

    python -m woningzoeker                  één scan, meldingen naar Telegram (zo draait hij op GitHub)
    python -m woningzoeker --loop           blijft scannen volgens het interval in config.yaml
    python -m woningzoeker --droog          één scan, toont matches hier in plaats van op je telefoon
    python -m woningzoeker --test           stuurt een testbericht naar Telegram
    python -m woningzoeker --test-makelaars controleert of elke makelaar in makelaars.yaml nog werkt
    python -m woningzoeker --test-gmail     toont wat er uit de e-mailalerts gelezen wordt
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

import yaml

from .bronnen import Bron, maak_bronnen
from .filters import Filter
from .locatie import Locatie
from .model import Woning
from .opslag import Opslag
from .telegram import Telegram, opmaak
from .web import Geweigerd, Web

MAP = Path(__file__).resolve().parent.parent
FOUTEN_VOOR_WAARSCHUWING = 6  # zoveel mislukte scans op rij van één site = melding sturen
# afwijzingen die over de woning zelf gaan en dus ook gelden als dezelfde woning op een andere site staat
VOORWAARDEN = ("tekst:", "inschrijven", "max ", "short stay")

log = logging.getLogger("woningzoeker")


def laad_env():
    """Leest geheimen uit .env (als ze niet al als omgevingsvariabele bestaan, zoals op GitHub)."""
    pad = MAP / ".env"
    if not pad.exists():
        return
    for regel in pad.read_text(encoding="utf-8").splitlines():
        if "=" in regel and not regel.lstrip().startswith("#"):
            k, v = regel.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))


def laad_config() -> dict:
    return yaml.safe_load((MAP / "config.yaml").read_text(encoding="utf-8"))


class Zoeker:
    def __init__(self, cfg: dict, melder: Telegram | None):
        self.cfg = cfg
        self.melder = melder
        self.web = Web()
        self.opslag = Opslag(MAP / "data" / "woningzoeker.db")
        self.locatie = Locatie(self.opslag, self.web.sessie)

    def scan(self, droog: bool = False) -> int:
        cfg = self.cfg
        s = cfg["scan"]
        filt = Filter(cfg)
        eerste = self.opslag.is_leeg()
        if eerste:
            log.info("Eerste scan: alleen advertenties van de afgelopen %s uur worden gemeld.", s["eerste_scan_max_uren"])
        teller = self.opslag.meta_haal("teller", {"bekeken": 0, "gemeld": 0})
        matches: list[Woning] = []
        for bron in maak_bronnen(s["bronnen"], MAP / "makelaars.yaml"):
            woningen = self._haal(bron, droog)
            nieuw = [w for w in woningen if not self.opslag.is_gezien(w.sleutel)]
            log.info("%s: %d advertenties, %d nieuw", bron.naam, len(woningen), len(nieuw))
            for w in nieuw:
                teller["bekeken"] += 1
                reden = self._beoordeel(w, bron, filt, eerste)
                if reden:
                    log.info("  ✗ %-28s €%-5s %s", (w.adres or w.straat)[:28], w.prijs, reden)
                    if not droog:
                        self.opslag.markeer(w, False, reden)
                elif any(m.dubbel_sleutel == w.dubbel_sleutel or (w.adres_sleutel and m.adres_sleutel == w.adres_sleutel) for m in matches):
                    log.info("  = %-28s staat ook op een andere site", (w.adres or w.straat)[:28])
                    if not droog:
                        self.opslag.markeer(w, False, "dubbel in deze scan")
                else:
                    log.info("  ✓ %-28s €%-5s %s", (w.adres or w.straat)[:28], w.prijs, w.wijk)
                    matches.append(w)

        matches.sort(key=lambda w: filt.per_persoon(w, filt.nodig_bewoners(w) or 2))  # goedkoopste p.p. eerst
        limiet = s.get("max_meldingen_per_scan", 15)
        for w in matches[:limiet]:
            if droog:
                print("\n" + opmaak(w, cfg) + f"\n{w.url}")
                continue
            try:
                self.melder.woning(w, cfg)
                self.opslag.markeer(w, True)
                teller["gemeld"] += 1
            except Exception as e:  # volgende scan opnieuw proberen
                log.error("Melding mislukt voor %s: %s", w.url, e)
        if len(matches) > limiet and not droog:
            self.melder.tekst(f"… en nog {len(matches) - limiet} passende woningen. Die volgen bij de volgende scan.")
        if not droog:
            self.opslag.meta_bewaar("teller", teller)
            self._dagelijks(teller)
        return len(matches)

    def _dagelijks(self, teller: dict):
        """Eén keer per dag: laten weten dat hij nog draait, en het geheugen opruimen."""
        vorige = self.opslag.meta_haal("laatste_update")
        if vorige is None:
            self.opslag.meta_bewaar("laatste_update", datetime.now().isoformat())
            return
        if datetime.now() - datetime.fromisoformat(vorige) < timedelta(hours=24):
            return
        if self.melder:
            self.melder.tekst(
                f"🟢 Nog actief. Afgelopen dag {teller['bekeken']} nieuwe advertenties bekeken, {teller['gemeld']} gemeld."
            )
        self.opslag.meta_bewaar("teller", {"bekeken": 0, "gemeld": 0})
        self.opslag.meta_bewaar("laatste_update", datetime.now().isoformat())
        self.opslag.opruimen()

    def _haal(self, bron: Bron, droog: bool) -> list[Woning]:
        try:
            woningen = bron.zoek(self.web)
            probleem = "" if bron.gezond(woningen) else "geen advertenties gevonden (is de site veranderd?)"
        except Geweigerd:
            woningen, probleem = [], "de site staat scripts niet (meer) toe volgens robots.txt"
        except Exception as e:
            woningen, probleem = [], f"{type(e).__name__}: {e}"
        fouten = self.opslag.meta_haal("fouten", {})
        if not probleem:
            if fouten.pop(bron.naam, None) is not None and not droog:
                self.opslag.meta_bewaar("fouten", fouten)
            return woningen
        log.warning("%s: %s", bron.naam, probleem)
        if droog:
            return woningen
        fouten[bron.naam] = fouten.get(bron.naam, 0) + 1
        self.opslag.meta_bewaar("fouten", fouten)
        if fouten[bron.naam] == FOUTEN_VOOR_WAARSCHUWING and self.melder:
            self.melder.tekst(f"⚠️ {bron.naam} werkt al {FOUTEN_VOOR_WAARSCHUWING} scans niet: {probleem}")
        return woningen

    def _beoordeel(self, w: Woning, bron: Bron, filt: Filter, eerste: bool) -> str | None:
        s = self.cfg["scan"]
        if reden := filt.basis(w, voorlopig=True):
            return reden
        # eerst met de gegevens uit de lijst kijken of de wijk al afvalt; scheelt pagina's ophalen
        wijken, buurt = self.locatie.bepaal(w)
        if len(wijken) == 1 and (reden := filt.wijk(w, wijken, buurt, definitief=False)):
            return reden
        try:
            bron.details(self.web, w)
        except Exception as e:
            log.debug("Details %s mislukt: %s", w.url, e)
        if reden := filt.basis(w):
            return reden
        wijken, buurt = self.locatie.bepaal(w)
        w.labels = [x for x in w.labels if x.startswith("❔")]  # label van de bron zelf (e-mailalert) bewaren
        if reden := filt.wijk(w, wijken, buurt, definitief=True):
            return reden
        # dezelfde woning al op een andere site gezien? Dan geldt wat daar in de advertentie stond.
        if elders := self.opslag.elders(w, s.get("dubbel_dagen", 14)):
            andere_bron, gemeld, reden_elders = elders
            if gemeld:
                return f"al gemeld via {andere_bron}"
            if reden_elders.startswith(VOORWAARDEN):
                return f"{reden_elders} (volgens {andere_bron})"
        if reden := filt.tekst(w):
            return reden
        if eerste and w.geplaatst and w.geplaatst < datetime.now() - timedelta(hours=s["eerste_scan_max_uren"]):
            return "eerste scan: te oud"
        return None


def test_makelaars():
    from .bronnen.makelaar import Makelaar

    web = Web()
    lijst = yaml.safe_load((MAP / "makelaars.yaml").read_text(encoding="utf-8"))["makelaars"]
    for m in lijst:
        b = Makelaar(**m)
        try:
            ws = b.zoek(web)
            status = "OK " if b.gezond(ws) else "?? "
            print(f"{status} {b.naam:22} {b.aantal_links:3} links, {len(ws):3} beschikbaar")
            for w in ws[:2]:
                print(f"       €{w.prijs} | {w.m2} m² | {w.straat} {w.huisnummer} | {w.url}")
        except Exception as e:
            print(f"FOUT {b.naam:22} {type(e).__name__}: {e}")


def test_gmail():
    from .bronnen.gmail import Gmail

    g = Gmail()
    if not g.adres or not g.wachtwoord:
        sys.exit("GMAIL_ADRES en GMAIL_APP_WACHTWOORD ontbreken in .env")
    # alleen lokaal: een kopie van de alerts, om de inlezer op de echte opmaak af te stemmen (data/ staat niet op GitHub)
    map_ = MAP / "data" / "alerts"
    map_.mkdir(parents=True, exist_ok=True)
    berichten = list(g.berichten())
    print(f"{len(berichten)} alertmail(s) van Pararius/Funda/Huurwoningen.nl in de afgelopen dagen:\n")
    for i, bericht in enumerate(berichten, 1):
        ws = g.uit_bericht(bericht)
        print(f"{i:2}. {bericht['Date'][:22]} | {str(bericht['From'])[:35]:35} | {str(bericht['Subject'])[:55]} → {len(ws)} woning(en) herkend")
        for w in ws:
            print(f"      €{w.prijs} {w.prijs_soort or '?'} | {w.m2} m² | kamers {w.kamers} slpk {w.slaapkamers} | {w.straat} {w.huisnummer} {w.postcode} | {w.url}")
        (map_ / f"alert-{i:02}.eml").write_bytes(bericht.as_bytes())
    if berichten:
        print(f"\nKopieën bewaard in {map_}")


def main():
    p = argparse.ArgumentParser(prog="woningzoeker")
    p.add_argument("--loop", action="store_true", help="blijf scannen")
    p.add_argument("--droog", action="store_true", help="toon matches hier, stuur niets en onthoud niets")
    p.add_argument("--test", action="store_true", help="stuur een testbericht naar Telegram")
    p.add_argument("--test-makelaars", action="store_true", help="controleer makelaars.yaml")
    p.add_argument("--test-gmail", action="store_true", help="toon wat er uit de e-mailalerts gelezen wordt")
    args = p.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    (MAP / "data").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%d-%m %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            RotatingFileHandler(MAP / "data" / "woningzoeker.log", maxBytes=2_000_000, backupCount=2, encoding="utf-8"),
        ],
    )
    laad_env()
    if args.test_makelaars:
        return test_makelaars()
    if args.test_gmail:
        return test_gmail()

    melder = None
    if not args.droog:
        token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
        if not token or not chat:
            if os.environ.get("GITHUB_ACTIONS") == "true":
                log.warning("Telegram is nog niet gekoppeld (secrets ontbreken); deze scan wordt overgeslagen.")
                return
            sys.exit("TELEGRAM_BOT_TOKEN en TELEGRAM_CHAT_ID ontbreken. Draai eerst: python setup_telegram.py")
        melder = Telegram(token, chat)
    if args.test:
        melder.tekst("✅ De woningzoeker kan je berichten sturen.")
        print("Testbericht verstuurd.")
        return

    zoeker = Zoeker(laad_config(), melder)
    if args.loop and melder:
        melder.tekst("🟢 Woningzoeker gestart. Je krijgt hier een bericht zodra er een passende woning online komt.")
    while True:
        try:
            zoeker.scan(droog=args.droog)
        except Exception:
            log.exception("Scan mislukt")
        if not args.loop:
            break
        try:
            zoeker.cfg = laad_config()  # wijzigingen in config.yaml gelden direct
        except Exception as e:
            log.error("config.yaml kon niet gelezen worden, oude instellingen blijven gelden: %s", e)
        s = zoeker.cfg["scan"]
        minuten = s["nacht_interval_minuten"] if datetime.now().hour < 7 else s["interval_minuten"]
        log.info("Volgende scan over %d minuten.", minuten)
        time.sleep(minuten * 60)


if __name__ == "__main__":
    main()
