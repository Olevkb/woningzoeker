"""Koppelt de woningzoeker aan jouw Telegram.

    python setup_telegram.py           bot aanmaken en aan je eigen chat koppelen
    python setup_telegram.py --groep   meldingen voortaan naar een groep sturen (bot moet al in de groep zitten)
"""

import getpass
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests

MAP = Path(__file__).resolve().parent
ENV = MAP / ".env"
GH = shutil.which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"


def api(token, methode, **params):
    return requests.get(f"https://api.telegram.org/bot{token}/{methode}", params=params, timeout=40).json()


def bewaar(waarden: dict):
    regels = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
    regels = [r for r in regels if r.split("=", 1)[0].strip() not in waarden]
    regels += [f"{k}={v}" for k, v in waarden.items()]
    ENV.write_text("\n".join(regels) + "\n", encoding="utf-8")


def lees_env() -> dict:
    regels = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
    return dict(r.split("=", 1) for r in regels if "=" in r and not r.lstrip().startswith("#"))


def groep():
    """Zoekt de groep waar de bot in zit en stuurt de meldingen voortaan daarheen (ook op GitHub)."""
    token = lees_env().get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        sys.exit("Er staat nog geen bot in .env. Draai eerst: python setup_telegram.py")
    naam = api(token, "getMe")["result"]["username"]
    print(f"Zorg dat @{naam} in de groep zit en stuur daar dit bericht:  /start@{naam}")
    print("Ik wacht maximaal 3 minuten...")
    eind = time.time() + 180
    while time.time() < eind:
        for update in api(token, "getUpdates", timeout=20, allowed_updates='["message","my_chat_member"]').get("result", []):
            for soort in ("message", "my_chat_member"):
                chat = (update.get(soort) or {}).get("chat") or {}
                if chat.get("type") in ("group", "supergroup"):
                    return koppel_groep(token, chat)
    sys.exit("Geen groep gevonden. Zit de bot in de groep en heb je /start@" + naam + " gestuurd? Probeer het opnieuw.")


def koppel_groep(token: str, chat: dict):
    chat_id = chat["id"]
    antwoord = api(token, "sendMessage", chat_id=chat_id, text="✅ Gekoppeld! Vanaf nu komen de woningmeldingen in deze groep.")
    nieuw = (antwoord.get("parameters") or {}).get("migrate_to_chat_id")
    if nieuw:  # Telegram heeft de groep omgezet naar een supergroep, met een nieuw ID
        chat_id = nieuw
        antwoord = api(token, "sendMessage", chat_id=chat_id, text="✅ Gekoppeld! Vanaf nu komen de woningmeldingen in deze groep.")
    if not antwoord.get("ok"):
        sys.exit(f"Kon geen bericht in de groep zetten: {antwoord.get('description')}")
    bewaar({"TELEGRAM_CHAT_ID": chat_id})
    print(f"\nGekoppeld met de groep '{chat.get('title', '')}'. Opgeslagen in .env.")
    print("De scan op GitHub krijgt het nieuwe adres...")
    if subprocess.run([GH, "secret", "set", "TELEGRAM_CHAT_ID", "--body", str(chat_id)], cwd=MAP).returncode != 0:
        sys.exit("Doorgeven aan GitHub is niet gelukt. Probeer: gh secret set -f .env")
    print("Klaar! De volgende scan stuurt zijn meldingen naar de groep.")


def main():
    print(
        "Stap 1: open Telegram op je telefoon en zoek @BotFather (met blauw vinkje).\n"
        "Stap 2: stuur /newbot, kies een naam (bv. 'Mijn Woningzoeker') en een gebruikersnaam die eindigt op 'bot'.\n"
        "Stap 3: BotFather stuurt je een token, zoiets als 123456789:ABCdef...\n"
    )
    token = getpass.getpass("Plak hier het token en druk op Enter (je ziet niets tijdens het plakken, dat klopt): ").strip()
    mij = api(token, "getMe")
    if not mij.get("ok"):
        sys.exit("Dat token werkt niet. Kopieer het nog eens precies uit het bericht van BotFather.")
    naam = mij["result"]["username"]
    print(f"\nGelukt, je bot heet @{naam}.")
    print(f"Stap 4: open in Telegram de chat met @{naam}, druk op Start en stuur een bericht (bv. 'hoi').")
    print("Ik wacht maximaal 3 minuten op je bericht...")

    eind = time.time() + 180
    while time.time() < eind:
        for update in api(token, "getUpdates", timeout=20).get("result", []):
            chat = (update.get("message") or {}).get("chat") or {}
            if chat.get("id"):
                bewaar({"TELEGRAM_BOT_TOKEN": token, "TELEGRAM_CHAT_ID": chat["id"]})
                api(token, "sendMessage", chat_id=chat["id"], text="✅ Gekoppeld! Hier komen je woningmeldingen.")
                print(f"\nGekoppeld met {chat.get('first_name', 'jou')}. Opgeslagen in .env, je krijgt nu een testbericht.")
                return
    sys.exit("Geen bericht ontvangen. Draai het script opnieuw en stuur je bot een bericht.")


if __name__ == "__main__":
    groep() if "--groep" in sys.argv else main()
