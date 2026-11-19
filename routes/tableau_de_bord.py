"""Tableau de bord."""

from flask import Blueprint, g, render_template

from metier import decimal
from metier.dates import aujourd_hui, jours_entre, libelle_compte_a_rebours
from metier.droits import est_chef, est_responsable
from metier.adherents import lire_comites
from metier.projet import butoir, lire_listes, lire_projet
from metier.quorum import synthese
from metier.sondage import completer_avec_sondage
from metier.taches import (
    avancement_global, avancement_par, en_retard, lire_taches, ouverte, prochain_jalon, prochaines,
)
from routes import stockage

bp = Blueprint("tableau_de_bord", __name__)

STATUTS_CONTRIBUTION = ["Non commencée", "Brouillon", "Soumise", "Validée"]


def compte_a_rebours(libelle, date_cible, ref, detail=""):
    if date_cible is None:
        return {"libelle": libelle, "date": None, "texte": "—", "detail": detail, "passe": False}
    nb = jours_entre(ref, date_cible)
    return {"libelle": libelle, "date": date_cible, "texte": libelle_compte_a_rebours(nb),
            "detail": detail, "passe": nb < 0}


@bp.route("/")
def accueil():
    st = stockage()
    ref = aujourd_hui()
    projet = lire_projet(st)
    listes = lire_listes(st)
    taches = lire_taches(st)

    jalon = prochain_jalon(taches, projet, ref)
    rebours = [
        compte_a_rebours("Assemblée générale", butoir(projet, "ag"), ref, projet.get("lieu", "")),
        compte_a_rebours("Butoir de la convocation", butoir(projet, "convocation"), ref),
        compte_a_rebours("Prochain jalon", jalon["date"] if jalon else None, ref,
                         jalon["libelle"] if jalon else ""),
    ]

    mes_taches = []
    if not est_chef(g.compte):
        mes_taches = [t for t in taches if ouverte(t) and est_responsable(g.compte, t)]

    comites = lire_comites(st)
    completer_avec_sondage(comites, st.lire("Sondage"))
    quorum = synthese(comites) if comites else None

    lignes_budget = st.lire("Budget")
    budget = None
    if lignes_budget:
        budget = {c: sum(decimal(l.get(c)) for l in lignes_budget) for c in ("prevu", "engage", "realise")}

    fiches = {l.get("pole"): l.get("statut") or "Non commencée" for l in st.lire("Contributions")}
    contributions = [{"pole": p, "statut": fiches.get(p, "Non commencée")} for p in listes["poles"]]

    questions = [q for q in st.lire("Questions") if q.get("etat", "Ouverte") != "Tranchée"]

    return render_template(
        "tableau_de_bord.html",
        projet=projet,
        rebours=rebours,
        avancement=avancement_global(taches),
        par_phase=avancement_par(taches, "phase", listes["phases"]),
        par_categorie=avancement_par(taches, "categorie", listes["categories"]),
        retard=en_retard(taches, ref),
        a_venir=prochaines(taches, ref, 14),
        mes_taches=mes_taches,
        quorum=quorum,
        budget=budget,
        contributions=contributions,
        questions=questions,
        nb_taches=len(taches),
        aujourd_hui=ref,
    )
