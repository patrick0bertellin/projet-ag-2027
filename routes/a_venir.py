"""Écrans prévus aux lots 2 et 3 : page d'attente, avec les droits définitifs par rôle."""

from flask import Blueprint, render_template

from routes import onglet_requis, stockage

bp = Blueprint("a_venir", __name__)


def _page(titre, lot, contenu, apercu=None):
    return render_template("a_venir.html", titre=titre, lot=lot, contenu=contenu, apercu=apercu or [])


@bp.route("/communication")
@onglet_requis("communication")
def communication():
    lignes = stockage().lire("Communication")
    return _page("Communication", 2, "Calendrier de communication, propositions et validation des actions.",
                 [f"{l.get('date_texte')} – {l.get('action')} ({l.get('canaux')})" for l in lignes])


@bp.route("/budget")
@onglet_requis("budget")
def budget():
    return _page("Budget", 2, "Lignes du budget de l'AG : prévu, engagé, réalisé.")


@bp.route("/documents")
@onglet_requis("documents")
def documents():
    st = stockage()
    apercu = [f"{d.get('document')} – {d.get('statut')}" for d in st.lire("Documents")]
    apercu += [f"Question ouverte : {q.get('question')}" for q in st.lire("Questions")
               if q.get("etat", "Ouverte") != "Tranchée"]
    return _page("Documents", 2, "Dossier de l'AG, règles statutaires, ordre du jour, questions à trancher.",
                 apercu)
