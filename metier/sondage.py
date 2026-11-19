"""Sondage de participation à l'AG (réponses au formulaire de la convocation).

Source actuelle : le fichier Excel des réponses, importé par le Chef de projet dans
l'onglet « Sondage » du Google Sheet. Plus tard : lecture directe du Google Sheet des
réponses (mêmes colonnes, même traitement : `lire_lignes` reçoit des lignes de valeurs).

Chaque réponse est rapprochée d'un comité membre par le nom de l'organisme (mots
significatifs, sigle entre parenthèses, fédération CNOSF), ou à la main par le Chef de
projet quand le rapprochement automatique échoue. La réponse la plus récente compte.

Réponses possibles : présent (le président représente son organisme), représenté
(le président désigne un représentant de son organisme), absent (sans représentant).
"""

import re
from datetime import datetime

from metier.adherents import mots, nettoyer_mail, nettoyer_texte, normaliser_nom

PRESENT, REPRESENTE, ABSENT, AUTRE = "present", "represente", "absent", "autre"
LIBELLES_REPONSES = {
    PRESENT: "Présent (le président)",
    REPRESENTE: "Représenté",
    ABSENT: "Absent, sans représentant",
    AUTRE: "Réponse à vérifier",
}
VIENNENT = {PRESENT, REPRESENTE}

# champ -> textes cherchés dans l'en-tête normalisé ; l'ordre compte : « prénom » et les colonnes
# du représentant sont prises avant « nom », qui prend alors la colonne restante
COLONNES = [
    ("horodatage", ["horodateur", "horodatage"]),
    ("organisme", ["organisme"]),
    ("rep_nom", ["nom de mon representant"]),
    ("rep_prenom", ["prenom de mon representant"]),
    ("rep_mail", ["mail de mon representant"]),
    ("rep_fonction", ["fonction de mon representant"]),
    ("mail_president", ["mail president", "mail du president"]),
    ("reponse", ["en tant que president", "je serai"]),
    ("prenom", ["prenom"]),
    ("nom", ["nom"]),
]

# mots sans valeur pour reconnaître un organisme
MOTS_VIDES = {
    "comite", "departemental", "departementale", "cd", "cdos", "yvelines", "78", "de", "des", "du", "la", "le",
    "les", "l", "d", "et", "en", "sur", "au", "aux", "federation", "francaise", "ff", "union", "association",
}


class SondageInvalide(Exception):
    """Le fichier du sondage ne peut pas être lu."""


def type_reponse(texte):
    t = normaliser_nom(texte)
    if t.startswith("present"):
        return PRESENT
    if "ne designe pas" in t:
        return ABSENT
    if "designe" in t:
        return REPRESENTE
    return AUTRE


def _horodatage(valeur):
    if isinstance(valeur, datetime):
        return valeur.strftime("%Y-%m-%d %H:%M:%S")
    return nettoyer_texte(valeur)


def lire_lignes(lignes):
    """Lignes de valeurs (en-tête compris) -> réponses (dictionnaires de l'onglet Sondage)."""
    for num, entete in enumerate(lignes[:5]):
        textes = [normaliser_nom(c) for c in entete]
        if any("organisme" in t for t in textes):
            index, pris = {}, set()
            for champ, attendus in COLONNES:
                for i, t in enumerate(textes):
                    if i not in pris and any(a in t for a in attendus):
                        index[champ] = i
                        pris.add(i)
                        break
            if "horodatage" not in index and 0 not in pris:
                index["horodatage"] = 0  # 1re colonne d'un formulaire : l'horodatage
            if "reponse" not in index:
                raise SondageInvalide("Colonne « En tant que Président, je serai » introuvable.")
            reponses = []
            for brute in lignes[num + 1:]:
                def val(champ):
                    i = index.get(champ)
                    return brute[i] if i is not None and i < len(brute) else None
                organisme = nettoyer_texte(val("organisme"))
                if not organisme:
                    continue
                reponses.append({
                    "horodatage": _horodatage(val("horodatage")), "organisme": organisme,
                    "nom": nettoyer_texte(val("nom")), "prenom": nettoyer_texte(val("prenom")),
                    "mail_president": nettoyer_mail(val("mail_president")),
                    "reponse": nettoyer_texte(val("reponse")),
                    "rep_nom": nettoyer_texte(val("rep_nom")), "rep_prenom": nettoyer_texte(val("rep_prenom")),
                    "rep_mail": nettoyer_mail(val("rep_mail")), "rep_fonction": nettoyer_texte(val("rep_fonction")),
                })
            return reponses
    raise SondageInvalide("Ligne d'en-tête avec « ORGANISME » introuvable.")


def lire_fichier(fichier):
    import openpyxl

    try:
        classeur = openpyxl.load_workbook(fichier, data_only=True)
    except Exception as exc:
        raise SondageInvalide(f"Le fichier n'est pas un classeur Excel lisible (.xlsx) : {exc}") from exc
    feuille = classeur.worksheets[0]
    return lire_lignes([list(l) for l in feuille.iter_rows(values_only=True)])


def cle_reponse(r):
    return f"{r.get('horodatage', '')}|{normaliser_nom(r.get('organisme'))}"


def fusionner(nouvelles, anciennes):
    """Garde les rapprochements faits à la main (comite_id) des réponses déjà connues."""
    manuels = {cle_reponse(r): r.get("comite_id", "") for r in anciennes if r.get("comite_id")}
    for r in nouvelles:
        r["comite_id"] = manuels.get(cle_reponse(r), "")
    return nouvelles


# ------------------------------------------------------------------ rapprochement
ARTICLES = {"de", "du", "des", "la", "le", "les", "l", "d", "et", "en", "au", "aux"}


def _racine(mot):
    return mot[:-1] if len(mot) > 3 and mot.endswith("s") else mot  # « sports » = « sport »


def _significatifs(texte):
    return {_racine(m) for m in normaliser_nom(texte).split() if m not in MOTS_VIDES and len(m) > 1}


def _sigles(texte):
    """Sigles entre parenthèses, mot par mot : « (CODEP EPGV) » -> {codep, epgv}."""
    return {m for s in re.findall(r"\(([^)]+)\)", texte or "") for m in normaliser_nom(s).split()}


def _initiales(texte):
    """« Union Nationale du Sport Scolaire » -> « unss »."""
    sans_parentheses = re.sub(r"\([^)]*\)", " ", texte or "")
    return "".join(m[0] for m in normaliser_nom(sans_parentheses).split()
                   if m not in ARTICLES and m not in {"comite", "departemental", "departementale"})


def rapprocher(reponse, comites):
    """Comité correspondant à une réponse (ou None). Rapprochement manuel prioritaire.

    Dans l'ordre : sigle commun, initiales égales au nom du comité (UNSS), puis la majorité
    stricte des mots significatifs de la réponse retrouvés dans le nom ou la fédération.
    """
    if reponse.get("comite_id"):
        return next((c for c in comites if c["id"] == reponse["comite_id"]), None)
    organisme = reponse.get("organisme") or ""
    sigles = _sigles(organisme)
    initiales = _initiales(organisme)
    cherches = _significatifs(re.sub(r"\([^)]*\)", " ", organisme))
    meilleur, score_max = None, 0.0
    for c in comites:
        noms = [c.get("nom", "")] + [n for n in (c.get("noms_import") or "").split("|") if n]
        connus = _significatifs(c.get("federation"))
        for n in noms:
            connus |= _significatifs(n) | _sigles(n)
        if sigles & connus or (len(initiales) > 2 and initiales in {normaliser_nom(n) for n in noms}):
            return c
        if not cherches or not connus:
            continue
        score = len(cherches & connus) / len(cherches)
        if score > score_max or (score == score_max and meilleur and len(connus) < len(meilleur[1])):
            meilleur, score_max = (c, connus), score
    return meilleur[0] if meilleur and score_max > 0.5 else None


def completer_avec_sondage(comites, reponses):
    """Ajoute à chaque comité sa dernière réponse (_reponse) et en déduit l'inscription.

    Renvoie les réponses non rapprochées d'un comité membre actif.
    """
    actifs = [c for c in comites if c["_actif"]]
    non_rapprochees = []
    for r in sorted(reponses, key=lambda r: r.get("horodatage", "")):
        r["_type"] = type_reponse(r.get("reponse"))
        comite = rapprocher(r, actifs)
        if comite is None:
            non_rapprochees.append(r)
            continue
        comite["_reponse"] = r  # la plus récente l'emporte (tri par horodatage)
    for c in comites:
        r = c.get("_reponse")
        if r:
            c["_inscrit"] = r["_type"] in VIENNENT
    return non_rapprochees


def synthese_sondage(comites, non_rapprochees):
    actifs = [c for c in comites if c["_actif"]]
    compte = {t: [c for c in actifs if c.get("_reponse") and c["_reponse"]["_type"] == t] for t in LIBELLES_REPONSES}
    return {
        "nb_reponses": sum(len(v) for v in compte.values()),
        "par_type": {t: len(v) for t, v in compte.items()},
        "voix_par_type": {t: sum(c["_voix"] for c in v if c["_a_jour"]) for t, v in compte.items()},
        "sans_reponse": [c for c in actifs if not c.get("_reponse")],
        "non_rapprochees": non_rapprochees,
    }
