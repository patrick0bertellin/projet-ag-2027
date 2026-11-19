"""Comités adhérents et référentiel des fédérations du CNOSF.

Un comité est identifié par un code fixe (C01, C02…), jamais par sa ligne ou son nom.
Sa catégorie vient de sa fédération dans le référentiel CNOSF ; à défaut, de la
catégorie saisie à la main. Il est à jour de cotisation si le mode de règlement est
renseigné (« - » = en attente).
"""

import re
import unicodedata
from pathlib import Path

from metier import booleen, entier
from metier.quorum import voix_du_comite

FICHIER_CNOSF = Path(__file__).resolve().parent.parent / "donnees" / "2026-11-13-Disciplines_categories_CNOSF.xlsx"

MODES_REGLEMENT = ["Virement", "HelloAsso", "Chèque"]
LIBELLES_CATEGORIES = {
    1: "Fédérations olympiques",
    2: "Fédérations nationales sportives (non olympiques)",
    3: "Fédérations multisports ou affinitaires",
    4: "Fédérations scolaires ou universitaires",
    5: "Membres associés",
}

MOTS_VIDES = {
    "de", "la", "le", "les", "et", "des", "du", "d", "l", "a", "au", "aux", "en", "sur", "pour",
    "federation", "francaise", "francais", "france", "nationale", "national", "union", "comite",
    "departemental", "yvelines",
}


# ------------------------------------------------------------------ noms
def normaliser_nom(texte):
    """« Tir à l'Arc » -> « tir a l arc » (sans accents, minuscules, ponctuation en espaces)."""
    texte = unicodedata.normalize("NFKD", str(texte or "")).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", texte.lower()).split())


def mots(texte):
    return {m for m in normaliser_nom(texte).split() if m not in MOTS_VIDES}


def nettoyer_texte(valeur):
    """Supprime espaces insécables et espaces en trop."""
    return " ".join(str(valeur or "").replace("\xa0", " ").split())


def nettoyer_mail(valeur):
    return nettoyer_texte(valeur).replace(" ", "").lower()


def mail_valide(mail):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", mail or ""))


def est_a_jour(mode_reglement):
    mode = nettoyer_texte(mode_reglement)
    return bool(mode) and mode != "-"


# ------------------------------------------------------------------ référentiel CNOSF
def lire_federations(stockage):
    return [f for f in stockage.lire("Federations") if f.get("discipline")]


def index_federations(federations):
    return {f["discipline"]: f for f in federations}


def rapprocher_federation(nom, federations):
    """Fédération CNOSF la plus proche d'un nom de comité (ou None).

    Score : part des mots du comité retrouvés dans la discipline ou le nom de la
    fédération ; à égalité, la fédération la plus courte (« Tennis » avant
    « Tennis de Table »). « BASKET BALL » est rapproché de « Basketball » par le
    nom collé.
    """
    mots_comite = mots(nom)
    colle = normaliser_nom(nom).replace(" ", "")
    meilleur, meilleur_score = None, (0, 0)
    for f in federations:
        if normaliser_nom(f["discipline"]).replace(" ", "") == colle:
            return f
        mots_f = mots(f["discipline"]) | mots(f.get("federation", ""))
        if not mots_comite or not mots_f:
            continue
        communs = len(mots_comite & mots_f)
        score = (communs / len(mots_comite), -len(mots(f["discipline"])))
        if communs and score > meilleur_score:
            meilleur, meilleur_score = f, score
    return meilleur if meilleur_score[0] >= 0.5 else None


# ------------------------------------------------------------------ comités
def categorie_du_comite(comite, federations_par_discipline):
    federation = federations_par_discipline.get(comite.get("federation", ""))
    if federation:
        return entier(federation.get("categorie"))
    return entier(comite.get("categorie"))


def preparer_comite(ligne, federations_par_discipline, bareme):
    c = dict(ligne)
    c["_categorie"] = categorie_du_comite(c, federations_par_discipline)
    c["_actif"] = booleen(c.get("actif", "oui")) if str(c.get("actif", "")).strip() else True
    c["_a_jour"] = est_a_jour(c.get("mode_reglement"))
    c["_voix"] = voix_du_comite(c["_categorie"], c.get("licencies"), bareme)
    c["_inscrit"] = booleen(c.get("inscrit"))
    c["_present"] = booleen(c.get("present"))
    return c


def lire_comites(stockage, bareme=None, federations=None):
    from metier.projet import lire_bareme

    bareme = bareme or lire_bareme(stockage)
    federations = lire_federations(stockage) if federations is None else federations
    index = index_federations(federations)
    comites = [preparer_comite(l, index, bareme) for l in stockage.lire("Comites") if l.get("id")]
    return sorted(comites, key=lambda c: normaliser_nom(c.get("nom")))


def nouvel_identifiant(comites):
    numeros = [int(m.group(1)) for c in comites if (m := re.fullmatch(r"C(\d+)", c.get("id", "")))]
    return f"C{(max(numeros) if numeros else 0) + 1:02d}"


def noms_connus(comite):
    """Nom actuel et anciens noms vus à l'import (colonne noms_import, séparés par « | »)."""
    noms = {normaliser_nom(comite.get("nom"))}
    noms.update(normaliser_nom(n) for n in (comite.get("noms_import") or "").split("|") if n.strip())
    noms.discard("")
    return noms


def a_relancer(comites):
    """Comités actifs non à jour, puis à jour non inscrits, triés par voix décroissantes."""
    actifs = [c for c in comites if c["_actif"]]
    non_a_jour = sorted((c for c in actifs if not c["_a_jour"]), key=lambda c: -c["_voix"])
    non_inscrits = sorted((c for c in actifs if c["_a_jour"] and not c["_inscrit"]), key=lambda c: -c["_voix"])
    return non_a_jour, non_inscrits


# ------------------------------------------------------------------ concordance avec le fichier Excel
ONGLET_SYNCHRO = "Excel adherents"  # valeur de la colonne « onglet » du Journal pour les imports/exports


def modifications_non_exportees(stockage, comites):
    """Comités modifiés dans l'application depuis le dernier export (ou import) du fichier Excel.

    Renvoie {"dernier": ligne du Journal ou None, "comites": [{id, nom, quand, qui, champs}]}.
    """
    journal = stockage.lire("Journal")  # ajouts successifs : l'ordre des lignes est l'ordre chronologique
    positions = [i for i, l in enumerate(journal) if l.get("onglet") == ONGLET_SYNCHRO]
    dernier = journal[positions[-1]] if positions else None
    noms = {c["id"]: c.get("nom") for c in comites}
    modifies = {}
    for l in journal[positions[-1] + 1 if positions else 0:]:
        if l.get("onglet") == "Comites" and l.get("id") in noms:
            m = modifies.setdefault(l["id"], {"id": l["id"], "nom": noms[l["id"]], "quand": "", "qui": "",
                                              "champs": []})
            if l.get("horodatage", "") >= m["quand"]:
                m["quand"], m["qui"] = l.get("horodatage", ""), l.get("utilisateur", "")
            if l.get("champ") not in m["champs"]:
                m["champs"].append(l.get("champ"))
    return {"dernier": dernier, "comites": sorted(modifies.values(), key=lambda m: m["quand"], reverse=True)}
