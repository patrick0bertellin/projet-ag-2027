"""Accès aux données : Google Sheet en production, mémoire pour les tests."""


class StockageIndisponible(Exception):
    """Le Google Sheet ne répond pas ou n'est pas accessible."""


class LigneIntrouvable(Exception):
    """Aucune ligne ne porte la clé demandée."""


class StockageBase:
    """Interface commune. Toutes les valeurs sont des chaînes de caractères."""

    def lire(self, onglet):
        """Liste de dictionnaires (une entrée par ligne). Onglet absent : liste vide."""
        raise NotImplementedError

    def onglets_manquants(self):
        raise NotImplementedError

    def ajouter(self, onglet, ligne):
        self.ajouter_lignes(onglet, [ligne])

    def ajouter_lignes(self, onglet, lignes):
        raise NotImplementedError

    def mettre_a_jour(self, onglet, cle, valeur_cle, champs):
        raise NotImplementedError

    def supprimer(self, onglet, cle, valeur_cle):
        raise NotImplementedError

    def remplacer_tout(self, onglet, lignes):
        raise NotImplementedError

    def preparer_onglets(self):
        """Crée les onglets manquants et complète les en-têtes. Renvoie un compte rendu."""
        raise NotImplementedError

    def vider_cache(self):
        pass


def normaliser(ligne, colonnes):
    """Ramène une ligne aux colonnes données, valeurs en chaînes."""
    return {c: "" if ligne.get(c) is None else str(ligne.get(c)) for c in colonnes}
