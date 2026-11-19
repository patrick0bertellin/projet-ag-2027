"""Rapport d'activité 2026 — perspectives 2027 : fiches de contribution par pôle.

Reprise du rapport 2025 (donnees/reprise_rapport_2025.json) : les engagements annoncés pour
2026, à bilanter (Réalisé / En cours / Reporté / Abandonné), les indicateurs clés avec leur
valeur 2025 en référence, et pour chaque pôle sa commission et sa présentation, à relire.
Le pôle « Général » regroupe l'introduction, les chiffres du CDOS 78 et les perspectives générales.

Colonne « prevu » de l'onglet Engagements : « oui » (ou vide) pour un engagement annoncé dans le
rapport 2025, « non » pour une action réalisée ou engagée en 2026 sans avoir été prévue
(état Réalisé ou En cours ; identifiant N…). Les indicateurs ajoutés en 2026 ont un identifiant A….

Statuts d'une fiche : Non commencée → Brouillon → Soumise → Validée. Le responsable du pôle
(rôle Contribution) modifie sa fiche tant qu'elle n'est pas soumise ; le Chef de projet peut
toujours la modifier, la valider ou la renvoyer en brouillon.
"""

import json
from pathlib import Path

from metier.droits import CHEF, CONTRIBUTION, LECTURE, roles_du_compte

FICHIER_REPRISE = Path(__file__).resolve().parent.parent / "donnees" / "reprise_rapport_2025.json"
ETATS_ENGAGEMENT = ["Réalisé", "En cours", "Reporté", "Abandonné"]
ETATS_NON_PREVU = ["Réalisé", "En cours"]
DATE_LIMITE = "2027-01-08"  # tâche T016 : contributions des pôles
NON_COMMENCEE, BROUILLON, SOUMISE, VALIDEE = "Non commencée", "Brouillon", "Soumise", "Validée"
STATUTS = [NON_COMMENCEE, BROUILLON, SOUMISE, VALIDEE]
GENERAL = "Général"
ORDRE = [GENERAL, "Pôle 1", "Pôle 2", "Pôle 3", "Pôle 4", "Pôle 5", "Communication", "Formation"]
CHAMPS_FICHE = ["commission", "presentation", "bilan", "perspectives"]

RESPONSABLES = {
    GENERAL: "Pierre TREGUIER, Patrick BERTELLIN",
    "Pôle 1": "Thierry GREGORI",
    "Pôle 2": "Jacques GIFFARD",
    "Pôle 3": "Joël MANCEL",
    "Pôle 4": "Jacques POLENI",
    "Pôle 5": "Marion EVRARD",
    "Communication": "Marion EVRARD",
    "Formation": "Louis SERVILLE",
}


class SaisieInvalide(Exception):
    def __init__(self, erreurs):
        super().__init__("; ".join(erreurs))
        self.erreurs = erreurs


def est_prevu(engagement):
    """Engagement annoncé dans le rapport 2025 (prevu vide ou « oui ») ; « non » : action non prévue."""
    return (engagement.get("prevu") or "oui").strip().lower() != "non"


def lire_reprise():
    return json.loads(FICHIER_REPRISE.read_text(encoding="utf-8"))


def _rang(pole):
    return ORDRE.index(pole) if pole in ORDRE else len(ORDRE)


# ------------------------------------------------------------------ chargement initial
def charger_reprise(stockage, quand="", qui=""):
    """Charge engagements, indicateurs et fiches de contribution s'ils ne sont pas déjà là, et complète
    les fiches sans titre (commission, présentation 2025). Ne remplace jamais une saisie : relancer est sans effet.
    Renvoie le nombre de lignes ajoutées (ou complétées) par onglet.
    """
    if any(o in stockage.onglets_manquants() for o in ("Engagements", "Indicateurs", "Contributions")):
        stockage.preparer_onglets()
    reprise = lire_reprise()
    ajouts = {}
    for onglet, lignes in (("Engagements", reprise["engagements"]), ("Indicateurs", reprise["indicateurs"])):
        connus = {l.get("id") for l in stockage.lire(onglet)}
        nouvelles = [l for l in lignes if l["id"] not in connus]
        if nouvelles:
            stockage.ajouter_lignes(onglet, nouvelles)
        ajouts[onglet] = len(nouvelles)

    fiches = stockage.lire("Contributions")
    poles_connus = {l.get("pole") for l in fiches}
    nouvelles = [{"pole": pole, "responsable": responsable, "statut": NON_COMMENCEE, "date_limite": DATE_LIMITE,
                  "maj_par": qui, "maj_le": quand} for pole, responsable in RESPONSABLES.items()
                 if pole not in poles_connus]
    completees = 0
    for fiche in fiches + nouvelles:
        modele = reprise.get("fiches", {}).get(fiche.get("pole"))
        if modele and not fiche.get("titre"):
            for champ in ("titre", "commission", "presentation"):
                if not fiche.get(champ):
                    fiche[champ] = modele[champ]
            completees += fiche in fiches
    if nouvelles or completees:
        stockage.remplacer_tout("Contributions", fiches + nouvelles)
    ajouts["Contributions"] = len(nouvelles) + completees
    return ajouts


# ------------------------------------------------------------------ droits
def pole_du_compte(compte):
    return (compte or {}).get("pole", "")


def peut_voir_fiche(compte, pole):
    roles = roles_du_compte(compte)
    return bool(roles & {CHEF, LECTURE}) or (CONTRIBUTION in roles and pole_du_compte(compte) == pole)


def peut_modifier_fiche(compte, fiche):
    roles = roles_du_compte(compte)
    if CHEF in roles:
        return True
    return (CONTRIBUTION in roles and pole_du_compte(compte) == fiche.get("pole")
            and (fiche.get("statut") or NON_COMMENCEE) in (NON_COMMENCEE, BROUILLON))


def peut_valider(compte):
    return CHEF in roles_du_compte(compte)


# ------------------------------------------------------------------ lecture
def lire_fiches(stockage):
    return sorted(stockage.lire("Contributions"), key=lambda f: _rang(f.get("pole")))


def lire_vue(stockage, pole):
    """Fiche d'un pôle avec ses engagements, actions non prévues et indicateurs (None si le pôle est inconnu)."""
    fiche = next((f for f in stockage.lire("Contributions") if f.get("pole") == pole), None)
    if fiche is None:
        return None
    fiche["statut"] = fiche.get("statut") or NON_COMMENCEE
    engagements = [l for l in stockage.lire("Engagements") if l.get("pole") == pole]
    return {
        "fiche": fiche,
        "engagements": [l for l in engagements if est_prevu(l)],
        "non_prevues": [l for l in engagements if not est_prevu(l)],
        "indicateurs": [l for l in stockage.lire("Indicateurs") if l.get("pole") == pole],
    }


def etat_par_pole(stockage):
    """Pour chaque pôle : responsable, statut, engagements bilantés / total, indicateurs renseignés / total."""
    engagements, indicateurs = stockage.lire("Engagements"), stockage.lire("Indicateurs")
    resultat = []
    for fiche in lire_fiches(stockage):
        pole = fiche.get("pole")
        e = [l for l in engagements if l.get("pole") == pole and est_prevu(l)]
        i = [l for l in indicateurs if l.get("pole") == pole]
        resultat.append({
            "pole": pole, "titre": fiche.get("titre") or pole, "responsable": fiche.get("responsable", ""),
            "statut": fiche.get("statut") or NON_COMMENCEE, "date_limite": fiche.get("date_limite", ""),
            "maj_le": fiche.get("maj_le", ""), "maj_par": fiche.get("maj_par", ""),
            "engagements": len(e), "engagements_bilantes": sum(1 for l in e if l.get("etat")),
            "non_prevues": sum(1 for l in engagements if l.get("pole") == pole and not est_prevu(l)),
            "indicateurs": len(i), "indicateurs_renseignes": sum(1 for l in i if l.get("valeur_annee")),
        })
    return resultat


# ------------------------------------------------------------------ saisie
NB_LIGNES_VIDES = 3  # lignes libres proposées pour les actions non prévues et les nouveaux indicateurs


def lire_formulaire(form, vue):
    """Applique le formulaire à la vue (copie) et renvoie (vue, erreurs). Rien n'est écrit."""
    nouvelle = {
        "fiche": dict(vue["fiche"]),
        "engagements": [dict(l) for l in vue["engagements"]],
        "non_prevues": [],
        "indicateurs": [],
    }
    erreurs = []
    for champ in CHAMPS_FICHE:
        if champ in form:
            nouvelle["fiche"][champ] = form.get(champ, "").strip()
    for l in nouvelle["engagements"]:
        l["etat"] = form.get(f"etat_{l['id']}", l.get("etat", "")).strip()
        l["commentaire"] = form.get(f"commentaire_{l['id']}", l.get("commentaire", "")).strip()
        if l["etat"] and l["etat"] not in ETATS_ENGAGEMENT:
            erreurs.append(f"État inconnu pour « {l['engagement']} ».")
    # actions non prévues : lignes existantes (identifiant N…) puis lignes libres ; texte vide = supprimée
    for n in range(len(vue["non_prevues"]) + NB_LIGNES_VIDES):
        texte = form.get(f"np_texte_{n}", "").strip()
        ligne = {"id": form.get(f"np_id_{n}", "").strip(), "pole": vue["fiche"]["pole"], "engagement": texte,
                 "etat": form.get(f"np_etat_{n}", "").strip(), "commentaire": form.get(f"np_commentaire_{n}", "").strip(),
                 "prevu": "non"}
        if not texte:
            if ligne["etat"] or ligne["commentaire"]:
                erreurs.append(f"Action non prévue n° {n + 1} : décrire l'action (ou vider la ligne).")
                nouvelle["non_prevues"].append(ligne)
            continue
        if ligne["etat"] not in ETATS_NON_PREVU:
            erreurs.append(f"Action non prévue « {texte} » : préciser son état (Réalisé ou En cours).")
        nouvelle["non_prevues"].append(ligne)
    for l in vue["indicateurs"]:
        l = dict(l)
        if l["id"].startswith("A"):  # indicateur ajouté en 2026 : nom modifiable, supprimé si vidé
            l["indicateur"] = form.get(f"nom_{l['id']}", l.get("indicateur", "")).strip()
            if not l["indicateur"]:
                continue
        l["valeur_annee"] = form.get(f"valeur_{l['id']}", l.get("valeur_annee", "")).strip()
        l["source"] = form.get(f"source_{l['id']}", l.get("source", "")).strip()
        nouvelle["indicateurs"].append(l)
    for n in range(NB_LIGNES_VIDES):
        nom = form.get(f"ni_nom_{n}", "").strip()
        valeur, source = form.get(f"ni_valeur_{n}", "").strip(), form.get(f"ni_source_{n}", "").strip()
        if nom:
            nouvelle["indicateurs"].append({"id": "", "pole": vue["fiche"]["pole"], "indicateur": nom,
                                            "valeur_reference": form.get(f"ni_reference_{n}", "").strip(),
                                            "valeur_annee": valeur, "source": source})
        elif valeur or source:
            erreurs.append(f"Nouvel indicateur n° {n + 1} : donner son nom (ou vider la ligne).")
    return nouvelle, erreurs


def _nouvel_id(prefixe, lignes):
    nums = [int(l["id"][1:]) for l in lignes if str(l.get("id", "")).startswith(prefixe) and l["id"][1:].isdigit()]
    return f"{prefixe}{max(nums, default=0) + 1:03d}"


def enregistrer(stockage, vue, statut, utilisateur, quand, commentaire_validation=None):
    """Écrit la fiche et ses lignes (une réécriture par onglet) et renvoie les changements pour le journal."""
    pole = vue["fiche"]["pole"]
    changements = {}

    engagements = stockage.lire("Engagements")
    avant = {l["id"]: l for l in engagements if l.get("pole") == pole}
    autres = [l for l in engagements if l.get("pole") != pole]
    lignes = []
    for l in vue["engagements"] + vue["non_prevues"]:
        l = dict(l)
        if not l.get("id"):
            l["id"] = _nouvel_id("N", engagements + lignes)
            changements[f"{l['id']} ajoutée"] = ("", l["engagement"])
        else:
            ancien = avant.get(l["id"], {})
            for champ in ("engagement", "etat", "commentaire"):
                if (ancien.get(champ) or "") != (l.get(champ) or ""):
                    changements[f"{l['id']} {champ}"] = (ancien.get(champ, ""), l.get(champ, ""))
        lignes.append(l)
    for ident in set(avant) - {l["id"] for l in lignes}:
        changements[f"{ident} supprimée"] = (avant[ident].get("engagement", ""), "")
    stockage.remplacer_tout("Engagements", sorted(autres + lignes, key=lambda l: (_rang(l.get("pole")), l["id"])))

    indicateurs = stockage.lire("Indicateurs")
    avant = {l["id"]: l for l in indicateurs if l.get("pole") == pole}
    autres = [l for l in indicateurs if l.get("pole") != pole]
    lignes = []
    for l in vue["indicateurs"]:
        l = dict(l)
        if not l.get("id"):
            l["id"] = _nouvel_id("A", indicateurs + lignes)
            changements[f"{l['id']} ajouté"] = ("", l["indicateur"])
        else:
            ancien = avant.get(l["id"], {})
            for champ in ("indicateur", "valeur_annee", "source"):
                if (ancien.get(champ) or "") != (l.get(champ) or ""):
                    changements[f"{l['id']} {champ}"] = (ancien.get(champ, ""), l.get(champ, ""))
        lignes.append(l)
    for ident in set(avant) - {l["id"] for l in lignes}:
        changements[f"{ident} supprimé"] = (avant[ident].get("indicateur", ""), "")
    stockage.remplacer_tout("Indicateurs", sorted(autres + lignes, key=lambda l: (
        _rang(l.get("pole")), l["id"].startswith("A"), l["id"])))

    fiche = dict(vue["fiche"])
    ancienne = next((f for f in stockage.lire("Contributions") if f.get("pole") == pole), {})
    for champ in CHAMPS_FICHE:
        if (ancienne.get(champ) or "") != (fiche.get(champ) or ""):
            changements[champ] = (ancienne.get(champ, ""), fiche.get(champ, ""))
    if (ancienne.get("statut") or NON_COMMENCEE) != statut:
        changements["statut"] = (ancienne.get("statut") or NON_COMMENCEE, statut)
    fiche.update(statut=statut, maj_par=utilisateur, maj_le=quand)
    if statut == VALIDEE:
        fiche.update(valide_par=utilisateur, valide_le=quand)
    if commentaire_validation is not None:
        fiche["commentaire_validation"] = commentaire_validation
    stockage.mettre_a_jour("Contributions", "pole", pole, fiche)
    return changements


def statut_apres(action, statut_actuel, compte):
    """Statut résultant d'une action du formulaire, ou None si l'action n'est pas permise."""
    if action == "enregistrer":
        return BROUILLON if statut_actuel == NON_COMMENCEE else statut_actuel
    if action == "soumettre":
        return SOUMISE if statut_actuel in (NON_COMMENCEE, BROUILLON) else None
    if action == "valider" and peut_valider(compte):
        return VALIDEE if statut_actuel == SOUMISE else None
    if action == "renvoyer" and peut_valider(compte):
        return BROUILLON if statut_actuel in (SOUMISE, VALIDEE) else None
    return None
