"""Modèle de mise en forme de l'export Excel des adhérents.

L'export part d'un vrai fichier du CDOS (couleurs, polices, mises en forme
conditionnelles, filtres, zones d'impression, en-têtes et pieds de page, propriétés
« Synthèse ») dont on a vidé les lignes de données : aucune donnée personnelle n'est
conservée dans le modèle. Seuls les numéros de catégorie de l'onglet Voix sont gardés : ils
portent la couleur de chaque catégorie, reprise à l'export.

- Modèle par défaut : donnees/modele_adherents.xlsx (tiré du fichier du 18/11/2026).
- À chaque import, la mise en forme du fichier importé peut devenir le nouveau modèle :
  il est alors enregistré, vidé, dans l'onglet « Modeles » du Google Sheet.
"""

import base64
import io
from copy import copy
from pathlib import Path

import openpyxl

from metier.adherents import normaliser_nom

MODELE_PAR_DEFAUT = Path(__file__).resolve().parent.parent / "donnees" / "modele_adherents.xlsx"
ONGLETS_DONNEES = ("Adhésion", "Voix", "Coordonnées")
TAILLE_MORCEAU = 40000  # caractères par cellule (limite Google : 50 000)


def onglet(classeur, nom):
    for feuille in classeur.worksheets:
        if normaliser_nom(feuille.title) == normaliser_nom(nom):
            return feuille
    return None


def ligne_total(feuille):
    """Numéro de la ligne « Total » / « Totaux » de la colonne A ; à défaut, la ligne qui suit la dernière."""
    for ligne in range(2, feuille.max_row + 1):
        texte = normaliser_nom(feuille.cell(row=ligne, column=1).value)
        if texte.split(" ")[0] in ("total", "totaux"):
            return ligne
    return feuille.max_row + 1


# Colonnes attendues par l'export (lettre -> mot présent dans l'en-tête)
COLONNES_ATTENDUES = {
    "Adhésion": {"A": "organisme", "B": "reglement", "C": "montant", "D": "clubs", "E": "licences",
                 "F": "feminines"},
    "Coordonnées": {"B": "adherent", "C": "president", "D": "mail"},
}


def structure_reconnue(classeur):
    """Les colonnes du classeur sont-elles dans l'ordre que l'export sait remplir ?"""
    for nom, colonnes in COLONNES_ATTENDUES.items():
        feuille = onglet(classeur, nom)
        for lettre, mot in colonnes.items():
            if mot not in normaliser_nom(feuille[f"{lettre}1"].value):
                return False
    return True


def colonne_categorie(feuille):
    """Numéro de la colonne dont l'en-tête est « Catégorie » (None si absente)."""
    for cellule in feuille[1]:
        if normaliser_nom(cellule.value) == "categorie":
            return cellule.column
    return None


def styles_categories(feuille):
    """{numéro de catégorie: style de cellule} lus dans la colonne Catégorie du modèle."""
    colonne = colonne_categorie(feuille)
    styles = {}
    if colonne is None:
        return styles
    for ligne in range(2, ligne_total(feuille)):
        cellule = feuille.cell(row=ligne, column=colonne)
        try:
            numero = int(cellule.value)
        except (TypeError, ValueError):
            continue
        styles.setdefault(numero, copy(cellule._style))
    return styles


def nettoyer_modele(fichier):
    """Classeur (bytes) vidé de ses lignes de données, ou None si la structure n'est pas reconnue."""
    try:
        classeur = openpyxl.load_workbook(fichier)
    except Exception:
        return None
    for nom in ONGLETS_DONNEES:
        feuille = onglet(classeur, nom)
        if feuille is None:
            return None
        total = ligne_total(feuille)
        if total < 3:  # aucune ligne de données dont reprendre la mise en forme
            return None
        garder = colonne_categorie(feuille) if nom == "Voix" else None
        for ligne in feuille.iter_rows(min_row=2, max_row=total - 1):
            for cellule in ligne:
                if cellule.column == garder:
                    continue  # numéros de catégorie conservés : ils portent la couleur de chaque catégorie
                cellule.value = None
                cellule.comment = None
    if not structure_reconnue(classeur):
        return None
    sortie = io.BytesIO()
    classeur.save(sortie)
    return sortie.getvalue()


def lire_modele(stockage):
    """Modèle enregistré dans le Sheet (onglet Modeles), sinon le modèle par défaut."""
    morceaux = sorted(
        (l for l in stockage.lire("Modeles") if l.get("nom") == "adherents" and l.get("contenu")),
        key=lambda l: int(l.get("partie") or 0),
    )
    if morceaux:
        try:
            return base64.b64decode("".join(m["contenu"] for m in morceaux)), morceaux[0].get("fichier", "")
        except ValueError:
            pass
    return MODELE_PAR_DEFAUT.read_bytes(), "modèle par défaut"


def enregistrer_modele(stockage, contenu, nom_fichier, auteur, quand):
    texte = base64.b64encode(contenu).decode("ascii")
    autres = [l for l in stockage.lire("Modeles") if l.get("nom") != "adherents"]
    morceaux = [
        {"nom": "adherents", "partie": i, "fichier": nom_fichier, "maj_par": auteur, "maj_le": quand,
         "contenu": texte[debut:debut + TAILLE_MORCEAU]}
        for i, debut in enumerate(range(0, len(texte), TAILLE_MORCEAU))
    ]
    if "Modeles" in stockage.onglets_manquants():
        stockage.preparer_onglets()
    stockage.remplacer_tout("Modeles", autres + morceaux)
