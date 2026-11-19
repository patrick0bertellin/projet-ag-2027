"""Import et ré-import de donnees/projet_ag_2027.json dans le stockage."""

import json
from pathlib import Path

from metier.projet import (
    BAREME_PAR_DEFAUT, CHAMPS_PROJET, LISTES_PAR_DEFAUT, lignes_parametres, lignes_projet,
)

CHEMIN_PAR_DEFAUT = Path(__file__).resolve().parent.parent / "donnees" / "projet_ag_2027.json"

DOCUMENTS_AG = [
    "Rapport d'activité", "Rapport moral", "Rapport financier", "Comptes 2026",
    "Rapport du commissaire aux comptes", "Budget 2027", "Projet de PV de l'AG 2026",
    "Modèle de mandat", "Convocation",
]

# Champs de suivi conservés lors d'un ré-import
CHAMPS_SUIVI = ("statut", "avancement", "commentaire", "depend_de", "poids", "maj_par", "maj_le")


def charger_json(chemin=None):
    with open(chemin or CHEMIN_PAR_DEFAUT, encoding="utf-8") as f:
        return json.load(f)


def lignes_taches(donnees):
    lignes = []
    for t in donnees.get("taches", []):
        conditionnelle = "quorum n'est pas atteint" in t.get("phase", "")
        lignes.append({
            "id": t["id"],
            "phase": t.get("phase", ""),
            "echeance_texte": t.get("echeance_texte", ""),
            "date_cible": t.get("date_cible", ""),
            "date_approx": "oui" if t.get("date_approx") else "non",
            "action": t.get("action", ""),
            "responsables": t.get("responsables", ""),
            "base": t.get("base", ""),
            "categorie": t.get("categorie", ""),
            "statut": t.get("statut", "À faire"),
            "avancement": t.get("avancement", 0),
            "commentaire": "",
            "depend_de": "",
            "poids": 1,
            "conditionnelle": "oui" if conditionnelle else "non",
            "maj_par": "",
            "maj_le": "",
        })
    return lignes


def lignes_reference(donnees):
    lignes = []
    for i, r in enumerate(donnees.get("regles_statutaires", []), start=1):
        lignes.append({"type": "regle_statutaire", "ordre": i, "titre": r.get("article", ""),
                       "texte": r.get("regle", ""), "complement": r.get("consequence", "")})
    for i, texte in enumerate(donnees.get("ordre_du_jour", []), start=1):
        lignes.append({"type": "ordre_du_jour", "ordre": i, "texte": texte})
    for i, texte in enumerate(donnees.get("points_de_vigilance", []), start=1):
        lignes.append({"type": "point_de_vigilance", "ordre": i, "texte": texte})
    for i, p in enumerate(donnees.get("publics", []), start=1):
        lignes.append({"type": "public", "ordre": i, "titre": p.get("public", ""),
                       "texte": p.get("message", ""), "complement": p.get("a_l_ag", ""),
                       "complement2": p.get("canaux", "")})
    for i, c in enumerate(donnees.get("canaux", []), start=1):
        lignes.append({"type": "canal", "ordre": i, "titre": c.get("canal", ""),
                       "texte": c.get("usage", ""), "complement": c.get("contenus", "")})
    for i, texte in enumerate(donnees.get("_notes", []), start=1):
        lignes.append({"type": "note", "ordre": i, "texte": texte})
    return lignes


def importer(stockage, donnees=None, conserver_suivi=True, reinitialiser_parametres=False):
    """Charge le JSON. Renvoie un compte rendu {onglet: nombre de lignes}.

    - conserver_suivi : garde statut, avancement, commentaire… des tâches déjà présentes.
    - reinitialiser_parametres : réécrit Projet et Parametres ; sinon ils ne sont écrits
      que s'ils sont vides (premier import).
    """
    donnees = donnees or charger_json()
    compte_rendu = {}

    if reinitialiser_parametres or not stockage.lire("Projet"):
        valeurs = {cle: defaut for cle, (_, defaut) in CHAMPS_PROJET.items()}
        projet = donnees.get("projet", {})
        for cle in ("nom", "evenement", "date_ag", "lieu"):
            if projet.get(cle):
                valeurs[cle] = projet[cle]
        lignes = lignes_projet(valeurs)
        stockage.remplacer_tout("Projet", lignes)
        compte_rendu["Projet"] = len(lignes)

    if reinitialiser_parametres or not stockage.lire("Parametres"):
        listes = {k: list(v) for k, v in LISTES_PAR_DEFAUT.items()}
        phases = []
        for t in donnees.get("taches", []):
            if t.get("phase") and t["phase"] not in phases:
                phases.append(t["phase"])
        listes["phases"] = phases or listes["phases"]
        categories = list(listes["categories"])
        for t in donnees.get("taches", []):
            if t.get("categorie") and t["categorie"] not in categories:
                categories.append(t["categorie"])
        listes["categories"] = categories
        canaux = [c.get("canal") for c in donnees.get("canaux", []) if c.get("canal")]
        listes["canaux"] = canaux or listes["canaux"]
        lignes = lignes_parametres(listes, BAREME_PAR_DEFAUT)
        stockage.remplacer_tout("Parametres", lignes)
        compte_rendu["Parametres"] = len(lignes)

    taches = lignes_taches(donnees)
    if conserver_suivi:
        existantes = {t.get("id"): t for t in stockage.lire("Taches")}
        for t in taches:
            ancienne = existantes.get(t["id"])
            if ancienne:
                for champ in CHAMPS_SUIVI:
                    if str(ancienne.get(champ, "")).strip():
                        t[champ] = ancienne[champ]
    stockage.remplacer_tout("Taches", taches)
    compte_rendu["Taches"] = len(taches)

    communication = [
        {"id": f"K{i:03d}", "date_texte": c.get("date_texte", ""), "date_cible": c.get("date_cible", ""),
         "action": c.get("action", ""), "canaux": c.get("canaux", ""),
         "responsables": c.get("responsables", ""), "statut": "Validée", "propose_par": "v05"}
        for i, c in enumerate(donnees.get("calendrier_communication", []), start=1)
    ]
    if not conserver_suivi or not stockage.lire("Communication"):
        stockage.remplacer_tout("Communication", communication)
        compte_rendu["Communication"] = len(communication)

    if not conserver_suivi or not stockage.lire("Questions"):
        questions = [{"id": f"Q{i:02d}", "question": q, "etat": "Ouverte"}
                     for i, q in enumerate(donnees.get("questions_a_trancher", []), start=1)]
        stockage.remplacer_tout("Questions", questions)
        compte_rendu["Questions"] = len(questions)

    if not conserver_suivi or not stockage.lire("Documents"):
        documents = [{"id": f"D{i:02d}", "document": d, "statut": "À produire"}
                     for i, d in enumerate(DOCUMENTS_AG, start=1)]
        stockage.remplacer_tout("Documents", documents)
        compte_rendu["Documents"] = len(documents)

    reference = lignes_reference(donnees)
    stockage.remplacer_tout("Reference", reference)
    compte_rendu["Reference"] = len(reference)
    return compte_rendu
