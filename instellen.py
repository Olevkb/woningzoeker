"""Eenmalig instellen, in één keer: Telegram koppelen, Gmail koppelen, gegevens naar GitHub sturen, eerste scan starten.

Draai vanuit deze map:  python instellen.py
Stappen die al gedaan zijn (staan al in .env) worden overgeslagen, dus opnieuw draaien kan altijd.
"""

import shutil
import subprocess
import sys
from pathlib import Path

MAP = Path(__file__).resolve().parent
ENV = MAP / ".env"
GH = shutil.which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"


def in_env(*sleutels) -> bool:
    regels = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
    aanwezig = {r.split("=", 1)[0].strip() for r in regels if "=" in r}
    return all(s in aanwezig for s in sleutels)


def stap(nummer: int, titel: str):
    print(f"\n{'=' * 60}\nStap {nummer} van 4: {titel}\n{'=' * 60}\n")


def draai(*opdracht, fout: str):
    if subprocess.run(opdracht, cwd=MAP).returncode != 0:
        sys.exit(f"\n{fout}\nDraai 'python instellen.py' gerust opnieuw; wat al gelukt is wordt overgeslagen.")


def main():
    stap(1, "Telegram koppelen")
    if in_env("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        print("Al gedaan, overgeslagen.")
    else:
        draai(sys.executable, "setup_telegram.py", fout="Telegram koppelen is niet gelukt.")

    stap(2, "Gmail koppelen")
    if in_env("GMAIL_ADRES", "GMAIL_APP_WACHTWOORD"):
        print("Al gedaan, overgeslagen.")
    else:
        draai(sys.executable, "setup_gmail.py", fout="Gmail koppelen is niet gelukt.")

    stap(3, "Gegevens versleuteld naar GitHub sturen")
    draai(GH, "secret", "set", "-f", str(ENV), fout="Versturen naar GitHub is niet gelukt. Ben je ingelogd? (gh auth login)")

    stap(4, "Eerste scan starten")
    draai(GH, "workflow", "run", "scan.yml", fout="De scan kon niet gestart worden.")
    print(
        "\nKlaar! De eerste scan draait nu op GitHub (duurt een paar minuten).\n"
        "Daarna scant hij elke 5 minuten vanzelf. Passende woningen komen in Telegram binnen."
    )


if __name__ == "__main__":
    main()
