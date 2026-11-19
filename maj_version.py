"""Régénère version.txt (aaaammjj-hhmm, heure de Paris) : à lancer à chaque livraison."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

version = datetime.now(ZoneInfo("Europe/Paris")).strftime("%Y%m%d-%H%M")
(Path(__file__).resolve().parent / "version.txt").write_text(version + "\n", encoding="utf-8")
print(version)
