"""Stockage dans le Google Sheet « CDOS78 - Projet AG 2027 ».

- Onglets lus par leur nom ; un onglet absent donne une liste vide (pas d'erreur 500).
- Lecture groupée de tous les onglets en un appel (values_batch_get), mise en cache
  quelques secondes pour ménager le quota de l'API ; toute écriture vide le cache.
- Écritures en mode RAW : les dates restent des textes « aaaa-mm-jj ».
"""

import json
import logging
import threading
import time

import gspread
from google.oauth2.service_account import Credentials
from gspread.utils import rowcol_to_a1

from stockage import LigneIntrouvable, StockageBase, StockageIndisponible
from stockage.schema import ONGLETS

journal = logging.getLogger(__name__)

PORTEES = ["https://www.googleapis.com/auth/spreadsheets"]


def creer_client(service_account_json="", chemin_cle=""):
    """Client gspread à partir du contenu JSON (Render) ou d'un chemin de fichier (local)."""
    if service_account_json:
        infos = json.loads(service_account_json)
        identifiants = Credentials.from_service_account_info(infos, scopes=PORTEES)
    elif chemin_cle:
        identifiants = Credentials.from_service_account_file(chemin_cle, scopes=PORTEES)
    else:
        raise StockageIndisponible(
            "Aucune clé de compte de service : définir SERVICE_ACCOUNT_JSON "
            "ou GOOGLE_APPLICATION_CREDENTIALS."
        )
    return gspread.authorize(identifiants)


class StockageSheet(StockageBase):
    def __init__(self, sheet_id, service_account_json="", chemin_cle="", duree_cache=60):
        if not sheet_id:
            raise StockageIndisponible("Variable SHEET_ID non définie.")
        self.sheet_id = sheet_id
        self.service_account_json = service_account_json
        self.chemin_cle = chemin_cle
        self.duree_cache = duree_cache
        self._classeur = None
        self._feuilles = {}  # nom -> Worksheet
        self._cache = None  # {nom: (entetes, lignes)}
        self._cache_le = 0.0
        self._verrou = threading.RLock()

    # ------------------------------------------------------------------ connexion
    def _ouvrir(self):
        if self._classeur is None:
            try:
                client = creer_client(self.service_account_json, self.chemin_cle)
                self._classeur = client.open_by_key(self.sheet_id)
            except StockageIndisponible:
                raise
            except Exception as exc:  # réseau, droits, identifiant erroné
                raise StockageIndisponible(
                    f"Impossible d'ouvrir le Google Sheet ({exc.__class__.__name__}). "
                    "Vérifier SHEET_ID et le partage avec le compte de service."
                ) from exc
        return self._classeur

    def _rafraichir_feuilles(self):
        try:
            self._feuilles = {f.title: f for f in self._ouvrir().worksheets()}
        except StockageIndisponible:
            raise
        except Exception as exc:
            raise StockageIndisponible(f"Lecture des onglets impossible : {exc}") from exc

    def _feuille(self, onglet):
        if onglet not in self._feuilles:
            self._rafraichir_feuilles()
        if onglet not in self._feuilles:
            raise LigneIntrouvable(f"Onglet « {onglet} » absent du Google Sheet")
        return self._feuilles[onglet]

    # ------------------------------------------------------------------ lecture
    def _charger(self):
        with self._verrou:
            if self._cache is not None and time.time() - self._cache_le < self.duree_cache:
                return self._cache
            self._rafraichir_feuilles()
            presents = [nom for nom in ONGLETS if nom in self._feuilles]
            cache = {}
            if presents:
                try:
                    reponse = _avec_nouvelles_tentatives(lambda: self._ouvrir().values_batch_get(
                        [f"'{nom}'" for nom in presents],
                        params={"valueRenderOption": "UNFORMATTED_VALUE"},
                    ))
                except Exception as exc:
                    raise StockageIndisponible(f"Lecture du Google Sheet impossible : {exc}") from exc
                for nom, plage in zip(presents, reponse.get("valueRanges", [])):
                    valeurs = plage.get("values", [])
                    cache[nom] = _en_dictionnaires(valeurs)
            self._cache = cache
            self._cache_le = time.time()
            return cache

    def lire(self, onglet):
        cache = self._charger()
        if onglet not in cache:
            return []
        _, lignes = cache[onglet]
        return [dict(l) for l in lignes]

    def onglets_manquants(self):
        cache = self._charger()
        return [nom for nom in ONGLETS if nom not in cache]

    def vider_cache(self):
        with self._verrou:
            self._cache = None

    # ------------------------------------------------------------------ écriture
    def _entetes_actuels(self, feuille):
        entetes = feuille.row_values(1)
        return [e.strip() for e in entetes]

    def _ecrire(self, action):
        with self._verrou:
            try:
                return _avec_nouvelles_tentatives(action)
            except (LigneIntrouvable, StockageIndisponible):
                raise
            except gspread.exceptions.APIError as exc:
                if _quota_depasse(exc):
                    raise StockageIndisponible(
                        "Quota d'écriture Google dépassé (60 écritures par minute) : "
                        "patienter une minute puis recommencer."
                    ) from exc
                raise StockageIndisponible(f"Écriture dans le Google Sheet impossible : {exc}") from exc
            except Exception as exc:
                raise StockageIndisponible(f"Écriture dans le Google Sheet impossible : {exc}") from exc
            finally:
                self._cache = None

    def ajouter_lignes(self, onglet, lignes):
        if not lignes:
            return

        def action():
            feuille = self._feuille(onglet)
            entetes = self._entetes_actuels(feuille)
            valeurs = [[_texte(l.get(c)) for c in entetes] for l in lignes]
            feuille.append_rows(valeurs, value_input_option="RAW", table_range="A1")

        self._ecrire(action)

    def mettre_a_jour(self, onglet, cle, valeur_cle, champs):
        def action():
            feuille = self._feuille(onglet)
            valeurs = feuille.get_all_values()
            if not valeurs:
                raise LigneIntrouvable(f"Onglet « {onglet} » vide")
            entetes = [e.strip() for e in valeurs[0]]
            if cle not in entetes:
                raise LigneIntrouvable(f"Colonne « {cle} » absente de l'onglet « {onglet} »")
            i_cle = entetes.index(cle)
            for num, ligne in enumerate(valeurs[1:], start=2):
                if len(ligne) > i_cle and str(ligne[i_cle]) == str(valeur_cle):
                    ligne = ligne + [""] * (len(entetes) - len(ligne))
                    for k, v in champs.items():
                        if k in entetes:
                            ligne[entetes.index(k)] = _texte(v)
                    fin = rowcol_to_a1(num, len(entetes))
                    feuille.update([ligne[: len(entetes)]], f"A{num}:{fin}", value_input_option="RAW")
                    return
            raise LigneIntrouvable(f"{onglet} : aucune ligne {cle} = {valeur_cle}")

        self._ecrire(action)

    def supprimer(self, onglet, cle, valeur_cle):
        def action():
            feuille = self._feuille(onglet)
            entetes = self._entetes_actuels(feuille)
            if cle not in entetes:
                raise LigneIntrouvable(f"Colonne « {cle} » absente de l'onglet « {onglet} »")
            colonne = feuille.col_values(entetes.index(cle) + 1)
            for num, valeur in enumerate(colonne[1:], start=2):
                if str(valeur) == str(valeur_cle):
                    feuille.delete_rows(num)
                    return
            raise LigneIntrouvable(f"{onglet} : aucune ligne {cle} = {valeur_cle}")

        self._ecrire(action)

    def remplacer_tout(self, onglet, lignes):
        def action():
            feuille = self._feuille(onglet)
            entetes = self._entetes_actuels(feuille) or ONGLETS[onglet]
            valeurs = [entetes] + [[_texte(l.get(c)) for c in entetes] for l in lignes]
            if feuille.row_count < len(valeurs) + 10:
                feuille.resize(rows=len(valeurs) + 100)
            feuille.clear()
            feuille.update(valeurs, "A1", value_input_option="RAW")

        self._ecrire(action)

    def preparer_onglets(self):
        """Crée les onglets manquants (avec en-têtes) et ajoute les colonnes manquantes."""

        def action():
            self._rafraichir_feuilles()
            classeur = self._ouvrir()
            crees, ajoutees = [], {}
            for nom, colonnes in ONGLETS.items():
                if nom not in self._feuilles:
                    feuille = classeur.add_worksheet(title=nom, rows=200, cols=max(len(colonnes), 10))
                    feuille.update([colonnes], "A1", value_input_option="RAW")
                    feuille.freeze(rows=1)
                    crees.append(nom)
                else:
                    feuille = self._feuilles[nom]
                    entetes = self._entetes_actuels(feuille)
                    manquantes = [c for c in colonnes if c not in entetes]
                    if manquantes:
                        nouvelles = entetes + manquantes
                        if feuille.col_count < len(nouvelles):
                            feuille.resize(cols=len(nouvelles))
                        feuille.update([nouvelles], "A1", value_input_option="RAW")
                        ajoutees[nom] = manquantes
            self._rafraichir_feuilles()
            return {"crees": crees, "colonnes_ajoutees": ajoutees}

        return self._ecrire(action)

    def supprimer_onglet_vide(self, nom):
        """Supprime un onglet s'il est vide (ex. « Feuille 1 » créé par défaut)."""

        def action():
            self._rafraichir_feuilles()
            feuille = self._feuilles.get(nom)
            if feuille is None or len(self._feuilles) < 2:
                return False
            if any(any(c for c in ligne) for ligne in feuille.get_all_values()):
                return False
            self._ouvrir().del_worksheet(feuille)
            self._rafraichir_feuilles()
            return True

        return self._ecrire(action)


ATTENTES_QUOTA = (2, 6)  # secondes entre deux tentatives quand Google renvoie 429


def _quota_depasse(exc):
    reponse = getattr(exc, "response", None)
    return getattr(reponse, "status_code", None) == 429


def _avec_nouvelles_tentatives(action):
    for attente in ATTENTES_QUOTA + (None,):
        try:
            return action()
        except gspread.exceptions.APIError as exc:
            if attente is None or not _quota_depasse(exc):
                raise
            journal.warning("Quota Google dépassé, nouvelle tentative dans %s s", attente)
            time.sleep(attente)
    return None


def _texte(valeur):
    if valeur is None:
        return ""
    if isinstance(valeur, bool):
        return "oui" if valeur else "non"
    return str(valeur)


def _en_dictionnaires(valeurs):
    if not valeurs:
        return [], []
    entetes = [str(e).strip() for e in valeurs[0]]
    lignes = []
    for brute in valeurs[1:]:
        if not any(str(c).strip() for c in brute):
            continue
        ligne = {}
        for i, entete in enumerate(entetes):
            if not entete:
                continue
            v = brute[i] if i < len(brute) else ""
            if isinstance(v, float) and v.is_integer():
                v = int(v)
            if isinstance(v, bool):
                v = "oui" if v else "non"
            ligne[entete] = str(v)
        lignes.append(ligne)
    return entetes, lignes
