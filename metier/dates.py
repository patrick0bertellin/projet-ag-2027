"""Dates : format français, heure de Paris, butoirs statutaires."""

import calendar
from datetime import date, datetime
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def maintenant():
    return datetime.now(PARIS)


def aujourd_hui():
    return maintenant().date()


def horodatage():
    return maintenant().strftime("%Y-%m-%d %H:%M:%S")


def lire_date(texte):
    """« 2027-03-20 » -> date ; vide ou invalide -> None."""
    if isinstance(texte, date):
        return texte
    texte = (texte or "").strip()
    if not texte:
        return None
    try:
        return date.fromisoformat(texte[:10])
    except ValueError:
        return None


def date_fr(d, avec_jour=True):
    """date(2027, 2, 15) -> « lundi 15 février 2027 »."""
    d = lire_date(d)
    if d is None:
        return ""
    jour = "1er" if d.day == 1 else str(d.day)
    texte = f"{jour} {MOIS[d.month - 1]} {d.year}"
    return f"{JOURS[d.weekday()]} {texte}" if avec_jour else texte


def date_courte(d):
    """date(2027, 2, 15) -> « 15/02/2027 »."""
    d = lire_date(d)
    return d.strftime("%d/%m/%Y") if d else ""


def mois_fr(d):
    d = lire_date(d)
    return f"{MOIS[d.month - 1]} {d.year}" if d else ""


def ajouter_mois(d, nb_mois):
    """Ajoute des mois en ramenant au dernier jour du mois si besoin (31 -> 30)."""
    mois = d.month - 1 + nb_mois
    annee = d.year + mois // 12
    mois = mois % 12 + 1
    jour = min(d.day, calendar.monthrange(annee, mois)[1])
    return date(annee, mois, jour)


def jours_entre(debut, fin):
    return (fin - debut).days


def libelle_compte_a_rebours(nb_jours):
    if nb_jours > 0:
        return f"J-{nb_jours}"
    if nb_jours == 0:
        return "Aujourd'hui"
    return f"J+{-nb_jours}"


def est_dimanche(d):
    d = lire_date(d)
    return d is not None and d.weekday() == 6
