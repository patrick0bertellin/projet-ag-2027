"""Rapport d'activité : avancement des fiches par pôle, saisie d'une fiche, export Word du rapport compilé."""

from urllib.parse import quote

from flask import Blueprint, Response, abort, flash, g, redirect, render_template, request, url_for

from metier.dates import horodatage
from metier.droits import CONTRIBUTION, roles_du_compte
from metier.journal import historique, tracer
from metier.rapport import (
    ETATS_ENGAGEMENT, ETATS_NON_PREVU, NB_LIGNES_VIDES, SOUMISE, STATUTS, VALIDEE, etat_par_pole,
    lire_formulaire, lire_vue, peut_modifier_fiche, peut_valider, peut_voir_fiche, pole_du_compte,
    statut_apres, enregistrer,
)
from routes import nom_utilisateur, onglet_requis, stockage

bp = Blueprint("rapport", __name__, url_prefix="/rapport")

MESSAGES = {
    "enregistrer": "Fiche « {pole} » enregistrée en brouillon.",
    "soumettre": "Fiche « {pole} » soumise au Chef de projet : elle n'est plus modifiable par le pôle.",
    "valider": "Fiche « {pole} » validée.",
    "renvoyer": "Fiche « {pole} » renvoyée en brouillon au responsable du pôle.",
}


def _onglets_fiches(st):
    """Fiches proposées en sous-onglets : toutes, ou seulement celle de son pôle pour un compte Contribution."""
    fiches = etat_par_pole(st)
    if _seulement_son_pole(g.compte):
        fiches = [f for f in fiches if f["pole"] == pole_du_compte(g.compte)]
    return fiches


def _seulement_son_pole(compte):
    """Un compte Contribution sans Chef ni Lecture ne voit que la fiche de son pôle."""
    roles = roles_du_compte(compte)
    return roles == {CONTRIBUTION}


@bp.route("/", strict_slashes=False)
@onglet_requis("rapport")
def liste():
    poles = _onglets_fiches(stockage())
    return render_template(
        "rapport.html", poles=poles, onglets_fiches=poles, statuts=STATUTS, peut_exporter=not _seulement_son_pole(g.compte),
        sans_pole=_seulement_son_pole(g.compte) and not pole_du_compte(g.compte),
    )


@bp.route("/fiche/<path:pole>", methods=["GET", "POST"])
@onglet_requis("rapport")
def fiche(pole):
    st = stockage()
    if not peut_voir_fiche(g.compte, pole):
        abort(403)
    vue = lire_vue(st, pole)
    if vue is None:
        abort(404)
    erreurs = []
    if request.method == "POST":
        action = request.form.get("action", "enregistrer")
        statut_actuel = vue["fiche"]["statut"]
        modifiable = peut_modifier_fiche(g.compte, vue["fiche"])
        if not modifiable and not (peut_valider(g.compte) and action in ("valider", "renvoyer")):
            abort(403)
        nouveau = statut_apres(action, statut_actuel, g.compte)
        if nouveau is None:
            abort(400)
        saisie, erreurs = lire_formulaire(request.form, vue) if modifiable else (vue, [])
        commentaire = request.form.get("commentaire_validation", "").strip() if action == "renvoyer" else None
        if action == "renvoyer" and not commentaire:
            erreurs.append("Indiquer au responsable du pôle ce qu'il faut revoir.")
        if erreurs:
            return _page(saisie, erreurs, modifiable, request.form.get("commentaire_validation", ""))
        changements = enregistrer(st, saisie, nouveau, nom_utilisateur(), horodatage(), commentaire)
        tracer(st, nom_utilisateur(), "Contributions", pole, changements)
        flash(MESSAGES[action].format(pole=vue["fiche"].get("titre") or pole)
              if changements or action != "enregistrer" else "Aucune modification.", "info")
        return redirect(url_for("rapport.fiche", pole=pole))
    return _page(vue, erreurs, peut_modifier_fiche(g.compte, vue["fiche"]))


def _page(vue, erreurs, modifiable, commentaire_validation=""):
    fiche = vue["fiche"]
    return render_template(
        "fiche_rapport.html", vue=vue, fiche=fiche, onglets_fiches=_onglets_fiches(stockage()), pole_actif=fiche["pole"], erreurs=erreurs, modifiable=modifiable,
        peut_valider=peut_valider(g.compte), etats=ETATS_ENGAGEMENT, etats_non_prevu=ETATS_NON_PREVU,
        nb_lignes_vides=NB_LIGNES_VIDES, soumise=fiche["statut"] == SOUMISE, validee=fiche["statut"] == VALIDEE,
        commentaire_validation=commentaire_validation,
        historique=historique(stockage(), "Contributions", fiche["pole"], limite=15),
    )


@bp.route("/export")
@onglet_requis("rapport")
def export():
    if _seulement_son_pole(g.compte):
        abort(403)
    from metier.export_rapport import exporter_rapport

    contenu = exporter_rapport(stockage())
    nom = f"{horodatage()[:10]}-Rapport_Activites_2026_Perspectives_2027_CDOS78 compilé.docx"
    return Response(
        contenu,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(nom)}"},
    )
