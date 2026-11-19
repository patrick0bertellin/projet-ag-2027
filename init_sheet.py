"""Prépare le Google Sheet : crée les onglets, importe le JSON, crée le premier compte.

Usage :
    python init_sheet.py                  # onglets + import (suivi conservé) + compte chef si aucun compte
    python init_sheet.py --sans-import    # onglets seulement
    python init_sheet.py --reinitialiser  # réécrit aussi Projet et Parametres
    python init_sheet.py --sans-compte    # ne crée pas le premier compte

Le Sheet doit avoir été créé à la main dans le Drive et partagé en Éditeur avec
le compte de service (un compte de service ne peut pas créer de fichier).

Pour le premier compte, les variables CHEF_NOM, CHEF_IDENTIFIANT, CHEF_COURRIEL et CHEF_MDP sont
utilisées si elles existent ; sinon les valeurs sont demandées dans le terminal.
"""

import argparse
import getpass
import os
import sys

from app import creer_stockage
from config import Config
from metier.adherents import FICHIER_CNOSF, lire_federations
from metier.comptes import creer, erreur_mot_de_passe, lire_comptes
from metier.droits import CHEF
from metier.excel_adherents import lire_cnosf
from metier.import_json import charger_json, importer
from stockage import StockageIndisponible


def demander(libelle, variable, secret=False, defaut=""):
    valeur = os.environ.get(variable, "").strip()
    if valeur:
        return valeur
    invite = f"{libelle}{f' [{defaut}]' if defaut else ''} : "
    valeur = (getpass.getpass(invite) if secret else input(invite)).strip()
    return valeur or defaut


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sans-import", action="store_true")
    parser.add_argument("--reinitialiser", action="store_true")
    parser.add_argument("--sans-compte", action="store_true", help="ne pas créer le premier compte")
    args = parser.parse_args()

    config = {k: getattr(Config, k) for k in dir(Config) if k.isupper()}
    try:
        st = creer_stockage(config)
        rapport = st.preparer_onglets()
    except StockageIndisponible as exc:
        print(f"ERREUR : {exc}")
        return 1
    print("Onglets créés :", ", ".join(rapport["crees"]) or "aucun")
    for onglet, colonnes in rapport["colonnes_ajoutees"].items():
        print(f"Colonnes ajoutées à {onglet} : {', '.join(colonnes)}")
    if st.supprimer_onglet_vide("Feuille 1"):
        print("Onglet vide « Feuille 1 » supprimé.")

    if not args.sans_import:
        compte_rendu = importer(st, charger_json(), conserver_suivi=True,
                                reinitialiser_parametres=args.reinitialiser)
        print("Import :", ", ".join(f"{k} {v}" for k, v in compte_rendu.items()))

    if not lire_federations(st):
        federations = lire_cnosf(FICHIER_CNOSF)
        st.remplacer_tout("Federations", federations)
        print(f"Référentiel CNOSF chargé : {len(federations)} fédérations.")

    if not args.sans_compte and not lire_comptes(st):
        print("\nAucun compte : création du compte Chef de projet.")
        nom = demander("Nom", "CHEF_NOM", defaut="Patrick")
        identifiant = demander("Identifiant de connexion", "CHEF_IDENTIFIANT", defaut=nom.split(" ")[0])
        courriel = demander("Courriel (facultatif)", "CHEF_COURRIEL")
        mdp = demander("Mot de passe initial (8 caractères au moins)", "CHEF_MDP", secret=True)
        erreur = erreur_mot_de_passe(mdp)
        if erreur or not identifiant:
            print(f"ERREUR : {erreur or 'identifiant vide'} ; compte non créé.")
            return 1
        creer(st, identifiant, nom, [CHEF], mdp, courriel=courriel, alias=nom.split(" ")[0])
        print(f"Compte créé pour {nom} (identifiant « {identifiant} ») ; mot de passe à changer à la première connexion.")
    print("Terminé.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
