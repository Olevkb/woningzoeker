"""Koppelt de woningzoeker aan jouw Telegram. Draai: python setup_telegram.py"""

import sys
import time
from pathlib import Path

import requests

ENV = Path(__file__).resolve().parent / ".env"


def api(token, methode, **params):
    return requests.get(f"https://api.telegram.org/bot{token}/{methode}", params=params, timeout=40).json()


def bewaar(waarden: dict):
    regels = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
    regels = [r for r in regels if r.split("=", 1)[0].strip() not in waarden]
    regels += [f"{k}={v}" for k, v in waarden.items()]
    ENV.write_text("\n".join(regels) + "\n", encoding="utf-8")


def main():
    print(
        "Stap 1: open Telegram op je telefoon en zoek @BotFather (met blauw vinkje).\n"
        "Stap 2: stuur /newbot, kies een naam (bv. 'Mijn Woningzoeker') en een gebruikersnaam die eindigt op 'bot'.\n"
        "Stap 3: BotFather stuurt je een token, zoiets als 123456789:ABCdef...\n"
    )
    token = input("Plak hier het token en druk op Enter: ").strip()
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
    main()
