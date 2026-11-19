"""Stockage en mémoire, même comportement que le Google Sheet (utilisé par les tests)."""

import copy

from stockage import LigneIntrouvable, StockageBase, normaliser
from stockage.schema import ONGLETS


class StockageMemoire(StockageBase):
    def __init__(self, onglets_presents=None):
        noms = ONGLETS.keys() if onglets_presents is None else onglets_presents
        self.donnees = {nom: [] for nom in noms}
        self.nb_lectures = 0

    def lire(self, onglet):
        self.nb_lectures += 1
        return copy.deepcopy(self.donnees.get(onglet, []))

    def onglets_manquants(self):
        return [nom for nom in ONGLETS if nom not in self.donnees]

    def _colonnes(self, onglet):
        if onglet not in self.donnees:
            raise LigneIntrouvable(f"Onglet « {onglet} » absent")
        return ONGLETS.get(onglet, [])

    def ajouter_lignes(self, onglet, lignes):
        colonnes = self._colonnes(onglet)
        self.donnees[onglet].extend(normaliser(l, colonnes) for l in lignes)

    def mettre_a_jour(self, onglet, cle, valeur_cle, champs):
        colonnes = self._colonnes(onglet)
        for ligne in self.donnees[onglet]:
            if ligne.get(cle) == str(valeur_cle):
                for k, v in champs.items():
                    if k in colonnes:
                        ligne[k] = "" if v is None else str(v)
                return
        raise LigneIntrouvable(f"{onglet} : aucune ligne {cle} = {valeur_cle}")

    def supprimer(self, onglet, cle, valeur_cle):
        self._colonnes(onglet)
        avant = len(self.donnees[onglet])
        self.donnees[onglet] = [l for l in self.donnees[onglet] if l.get(cle) != str(valeur_cle)]
        if len(self.donnees[onglet]) == avant:
            raise LigneIntrouvable(f"{onglet} : aucune ligne {cle} = {valeur_cle}")

    def remplacer_tout(self, onglet, lignes):
        colonnes = ONGLETS.get(onglet, [])
        self.donnees[onglet] = [normaliser(l, colonnes) for l in lignes]

    def preparer_onglets(self):
        crees = [nom for nom in ONGLETS if nom not in self.donnees]
        for nom in crees:
            self.donnees[nom] = []
        return {"crees": crees, "colonnes_ajoutees": {}}
