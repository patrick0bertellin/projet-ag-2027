"""Règles de gestion du projet AG (indépendantes de Flask et du Google Sheet)."""


def booleen(valeur):
    """Interprète « oui », « TRUE », « 1 », « x »… comme vrai."""
    return str(valeur or "").strip().lower() in {"oui", "o", "true", "vrai", "1", "x", "yes"}


def entier(valeur, defaut=0):
    try:
        return int(float(str(valeur).replace(",", ".").strip()))
    except (TypeError, ValueError):
        return defaut


def decimal(valeur, defaut=0.0):
    try:
        texte = str(valeur).replace(" ", "").replace(" ", "").replace("€", "").replace(",", ".")
        return float(texte)
    except (TypeError, ValueError):
        return defaut
