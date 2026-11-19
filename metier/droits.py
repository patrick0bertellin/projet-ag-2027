"""Rôles, onglets visibles et droits de modification."""

import re

CHEF = "chef_projet"
COMMUNICATION = "communication"
BUDGET = "budget"
CONTRIBUTION = "contribution"
LECTURE = "lecture"

ROLES = {
    CHEF: "Chef de projet",
    COMMUNICATION: "Communication",
    BUDGET: "Budget",
    CONTRIBUTION: "Contribution",
    LECTURE: "Lecture",
}

TOUS = set(ROLES)

# Visiteur : personne entrée sans identifiant. Ce n'est pas un rôle attribuable à un compte ;
# il ne voit que le tableau de bord et le rétroplanning, en consultation seule.
VISITEUR = "visiteur"
COMPTE_VISITEUR = {"id": VISITEUR, "identifiant": "", "nom": "Visiteur (consultation)", "alias": "",
                   "roles": VISITEUR, "actif": "oui", "doit_changer_mdp": "non"}

# Onglets du bandeau : (clé, libellé, endpoint Flask, rôles autorisés)
ONGLETS = [
    ("tableau_de_bord", "Tableau de bord", "tableau_de_bord.accueil", TOUS | {VISITEUR}),
    ("retroplanning", "Rétroplanning", "retroplanning.liste", TOUS | {VISITEUR}),
    ("communication", "Communication", "a_venir.communication", {CHEF, COMMUNICATION, LECTURE}),
    ("rapport", "Rapport d'activité", "rapport.liste", {CHEF, CONTRIBUTION, LECTURE}),
    ("budget", "Budget", "a_venir.budget", {CHEF, BUDGET, LECTURE}),
    ("adherents", "Adhérents", "adherents.liste", {CHEF, BUDGET, LECTURE, VISITEUR}),
    ("documents", "Documents", "a_venir.documents", TOUS),
    ("parametres", "Paramètres", "parametres.accueil", {CHEF}),
    ("comptes", "Comptes", "comptes.liste", {CHEF}),
]

# Catégorie de tâches confiée à un rôle
CATEGORIE_DU_ROLE = {COMMUNICATION: "Communication", BUDGET: "Budget"}

RESPONSABLES_DE_POLE = "responsables de pôle"


def roles_du_compte(compte):
    if not compte:
        return set()
    if est_visiteur(compte):
        return {VISITEUR}
    texte = compte.get("roles", "") if isinstance(compte, dict) else ""
    return {r.strip() for r in re.split(r"[,;]", texte) if r.strip() in ROLES}


def est_visiteur(compte):
    return isinstance(compte, dict) and compte.get("id") == VISITEUR


def est_chef(compte):
    return CHEF in roles_du_compte(compte)


def onglets_visibles(compte):
    roles = roles_du_compte(compte)
    return [o for o in ONGLETS if roles & o[3]]


def peut_voir(compte, cle_onglet):
    return any(o[0] == cle_onglet for o in onglets_visibles(compte))


def noms_responsables(texte):
    """« Pierre (Patrick), BE (à programmer) » -> ["Pierre", "Patrick", "BE"]."""
    noms = []
    for morceau in re.split(r"[,;/]", texte or ""):
        morceau = morceau.strip()
        if not morceau:
            continue
        principal = re.sub(r"\(.*?\)", "", morceau).strip()
        if principal:
            noms.append(principal)
        for entre in re.findall(r"\((.*?)\)", morceau):
            entre = entre.strip()
            if entre and entre[0].isupper():  # « (Patrick) » oui, « (à programmer) » non
                noms.append(entre)
    return noms


def alias_du_compte(compte):
    """Noms sous lesquels le compte apparaît dans les responsables (alias, sinon prénom)."""
    texte = (compte or {}).get("alias", "").strip()
    if not texte:
        texte = ((compte or {}).get("nom", "").strip().split(" ") or [""])[0]
    return {a.strip().lower() for a in texte.split(",") if a.strip()}


def est_responsable(compte, tache):
    if not compte or est_visiteur(compte):
        return False
    noms = {n.lower() for n in noms_responsables(tache.get("responsables", ""))}
    if alias_du_compte(compte) & noms:
        return True
    return RESPONSABLES_DE_POLE in noms and CONTRIBUTION in roles_du_compte(compte)


def peut_modifier_suivi(compte, tache):
    """Statut, avancement et commentaire : responsable de la tâche, rôle de la catégorie, ou chef."""
    roles = roles_du_compte(compte)
    if VISITEUR in roles:
        return False
    if CHEF in roles:
        return True
    if est_responsable(compte, tache):
        return True
    return any(CATEGORIE_DU_ROLE.get(r) == tache.get("categorie") for r in roles)


def peut_gerer_adherents(compte):
    """Importer, exporter, créer et modifier les comités adhérents : Chef de projet et Budget."""
    return bool(roles_du_compte(compte) & {CHEF, BUDGET})


def peut_suivre_presence(compte):
    """Réponses au sondage de participation et présence le jour de l'AG : Chef de projet seulement."""
    return est_chef(compte)


def peut_gerer_taches(compte):
    """Créer, supprimer ou redater une tâche : Chef de projet seulement."""
    return est_chef(compte)
