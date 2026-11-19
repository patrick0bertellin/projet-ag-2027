"""Calcul des voix, du quorum et de la majorité d'approbation (statuts art. 6 et 7).

Voix d'un comité : 1 voix par membre ; +1, +2 ou +3 selon le nombre de licenciés
(barème en paramètre) ; +5 pour la catégorie 1. Seuls les comités à jour de leur
cotisation (mode de règlement renseigné) comptent. Quorum de participation : la
moitié au moins du total des voix des comités à jour, constatée sur les voix
présentes. Ni procuration ni vote par correspondance.
"""

from metier import entier


def voix_du_comite(categorie, licencies, bareme):
    licencies = entier(licencies)
    bonus = 0
    for seuil, valeur in sorted(bareme["seuils"]):
        if licencies >= seuil:
            bonus = valeur
    voix = bareme["voix_base"] + bonus
    if entier(categorie) == 1:
        voix += bareme["voix_bonus_categorie_1"]
    return voix


def arrondi_superieur(numerateur, denominateur):
    return -(-numerateur // denominateur)


def seuil_quorum(total_voix):
    """La moitié au moins du total des voix (arrondie au supérieur)."""
    return arrondi_superieur(total_voix, 2)


def lire_fraction(texte, defaut=(2, 3)):
    """« 2/3 » -> (2, 3)."""
    try:
        num, den = (int(x) for x in str(texte).replace(" ", "").split("/"))
        if num > 0 and den > 0 and num <= den:
            return num, den
    except ValueError:
        pass
    return defaut


def seuil_approbation(voix_exprimees, fraction="2/3"):
    """Voix « pour » nécessaires : fraction des voix exprimées, arrondie au supérieur."""
    num, den = lire_fraction(fraction)
    return arrondi_superieur(voix_exprimees * num, den)


def synthese(comites):
    """Synthèse à partir des comités préparés (voir metier.adherents.preparer_comite)."""
    actifs = [c for c in comites if c["_actif"]]
    a_jour = [c for c in actifs if c["_a_jour"]]
    total = sum(c["_voix"] for c in a_jour)
    inscrites = sum(c["_voix"] for c in a_jour if c["_inscrit"])
    presentes = sum(c["_voix"] for c in a_jour if c["_present"])
    seuil = seuil_quorum(total)
    return {
        "nb_comites": len(actifs),
        "nb_a_jour": len(a_jour),
        "nb_en_attente": len(actifs) - len(a_jour),
        "voix_en_attente": sum(c["_voix"] for c in actifs if not c["_a_jour"]),
        "total_voix": total,
        "seuil": seuil,
        "voix_inscrites": inscrites,
        "voix_presentes": presentes,
        "marge": inscrites - seuil,
        "atteint": total > 0 and inscrites >= seuil,
        "quorum_constate": total > 0 and presentes >= seuil,
    }
