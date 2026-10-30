"""Koppelt de woningzoeker aan je Gmail, zodat hij de alerts van Pararius, Funda en Huurwoningen.nl kan lezen.

Draai: python setup_gmail.py
"""

import getpass
import imaplib
import sys
from pathlib import Path

ENV = Path(__file__).resolve().parent / ".env"


def bewaar(waarden: dict):
    regels = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
    regels = [r for r in regels if r.split("=", 1)[0].strip() not in waarden]
    regels += [f"{k}={v}" for k, v in waarden.items()]
    ENV.write_text("\n".join(regels) + "\n", encoding="utf-8")


def main():
    print(
        "De woningzoeker heeft een 'app-wachtwoord' nodig: een apart wachtwoord van 16 letters dat alleen\n"
        "je mail mag lezen. Je gewone Gmail-wachtwoord werkt hier niet (en hoort hier ook niet).\n\n"
        "Stap 1: zet verificatie in twee stappen aan: https://myaccount.google.com/signinoptions/two-step-verification\n"
        "Stap 2: maak een app-wachtwoord aan:         https://myaccount.google.com/apppasswords\n"
        "        Naam: 'woningzoeker'. Google toont dan 16 letters.\n"
    )
    adres = input("Je Gmail-adres: ").strip()
    wachtwoord = getpass.getpass("Plak het app-wachtwoord (je ziet niets tijdens het plakken, dat klopt): ").replace(" ", "")
    try:
        with imaplib.IMAP4_SSL("imap.gmail.com") as imap:
            imap.login(adres, wachtwoord)
    except imaplib.IMAP4.error:
        sys.exit("Inloggen lukt niet. Controleer het adres en maak eventueel een nieuw app-wachtwoord aan.")
    bewaar({"GMAIL_ADRES": adres, "GMAIL_APP_WACHTWOORD": wachtwoord})
    print("\nGelukt! Opgeslagen in .env. Test het met:  python -m woningzoeker --test-gmail")


if __name__ == "__main__":
    main()
