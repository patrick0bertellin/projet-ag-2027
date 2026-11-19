"""Configuration par variables d'environnement (fichier .env en local, jamais commité)."""

import os
from pathlib import Path

from dotenv import load_dotenv

RACINE = Path(__file__).resolve().parent
load_dotenv(RACINE / ".env")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "")
    SHEET_ID = os.environ.get("SHEET_ID", "")
    SERVICE_ACCOUNT_JSON = os.environ.get("SERVICE_ACCOUNT_JSON", "")
    GOOGLE_APPLICATION_CREDENTIALS = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    DUREE_CACHE = int(os.environ.get("DUREE_CACHE", "60"))
    PORT = int(os.environ.get("PORT", "5010"))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "") == "1"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 12  # 12 heures
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # fichiers Excel importés : 5 Mo au plus


def lire_version():
    try:
        return (RACINE / "version.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return "inconnue"
