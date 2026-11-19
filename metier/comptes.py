"""Comptes utilisateurs : création, connexion, mot de passe (haché avec werkzeug)."""

import re

from werkzeug.security import check_password_hash, generate_password_hash

from metier import booleen
from metier.dates import horodatage
from metier.droits import CONTRIBUTION, ROLES

LONGUEUR_MIN_MDP = 8


def lire_comptes(stockage):
    return [c for c in stockage.lire("Comptes") if c.get("id")]


def trouver(stockage, identifiant):
    for c in lire_comptes(stockage):
        if c["id"] == identifiant:
            return c
    return None


def normaliser_identifiant(identifiant):
    return " ".join((identifiant or "").split()).lower()


def trouver_par_identifiant(stockage, identifiant):
    """Recherche sans tenir compte des majuscules ni des espaces en trop."""
    cle = normaliser_identifiant(identifiant)
    if not cle:
        return None
    for c in lire_comptes(stockage):
        if normaliser_identifiant(c.get("identifiant")) == cle:
            return c
    return None


def verifier_connexion(stockage, identifiant, mot_de_passe):
    """Renvoie le compte si l'identifiant et le mot de passe sont bons et le compte actif."""
    compte = trouver_par_identifiant(stockage, identifiant)
    if not compte or not booleen(compte.get("actif")):
        return None
    if not compte.get("mdp_hash") or not check_password_hash(compte["mdp_hash"], mot_de_passe or ""):
        return None
    return compte


def erreur_mot_de_passe(mot_de_passe, confirmation=None):
    if len(mot_de_passe or "") < LONGUEUR_MIN_MDP:
        return f"Le mot de passe doit contenir au moins {LONGUEUR_MIN_MDP} caractères."
    if confirmation is not None and mot_de_passe != confirmation:
        return "Les deux mots de passe ne sont pas identiques."
    return None


def valider(stockage, donnees, identifiant=None, creation=False):
    """Liste des erreurs de saisie d'un compte."""
    erreurs = []
    if not donnees.get("nom", "").strip():
        erreurs.append("Le nom est obligatoire.")
    if not normaliser_identifiant(donnees.get("identifiant")):
        erreurs.append("L'identifiant est obligatoire.")
    else:
        autre = trouver_par_identifiant(stockage, donnees["identifiant"])
        if autre and autre["id"] != identifiant:
            erreurs.append("Cet identifiant est déjà utilisé par un autre compte.")
    roles = donnees.get("roles", [])
    if not roles:
        erreurs.append("Choisir au moins un rôle.")
    if any(r not in ROLES for r in roles):
        erreurs.append("Rôle inconnu.")
    if CONTRIBUTION in roles and not donnees.get("pole", "").strip():
        erreurs.append("Un compte Contribution doit être rattaché à un pôle.")
    mdp = donnees.get("mot_de_passe", "")
    if creation or mdp:
        message = erreur_mot_de_passe(mdp)
        if message:
            erreurs.append(message)
    return erreurs


def nouvel_identifiant(comptes):
    numeros = [int(m.group(1)) for c in comptes if (m := re.fullmatch(r"C(\d+)", c.get("id", "")))]
    return f"C{(max(numeros) if numeros else 0) + 1:03d}"


def creer(stockage, identifiant, nom, roles, mot_de_passe, courriel="", alias="", pole="", doit_changer=True):
    compte = {
        "id": nouvel_identifiant(lire_comptes(stockage)),
        "identifiant": " ".join(identifiant.split()),
        "nom": nom.strip(),
        "alias": alias.strip(),
        "courriel": courriel.strip().lower(),
        "roles": ",".join(roles),
        "pole": pole.strip(),
        "mdp_hash": generate_password_hash(mot_de_passe),
        "actif": "oui",
        "doit_changer_mdp": "oui" if doit_changer else "non",
        "cree_le": horodatage(),
    }
    stockage.ajouter("Comptes", compte)
    return compte


def changer_mot_de_passe(stockage, identifiant, mot_de_passe):
    stockage.mettre_a_jour("Comptes", "id", identifiant, {
        "mdp_hash": generate_password_hash(mot_de_passe),
        "doit_changer_mdp": "non",
    })
