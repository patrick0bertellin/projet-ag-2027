"""Comptes (Chef de projet) : création, modification, désactivation."""

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from metier.comptes import creer, lire_comptes, trouver, valider
from metier.droits import CHEF, ROLES
from metier.journal import differences, tracer
from metier.projet import lire_listes
from routes import nom_utilisateur, onglet_requis, stockage

bp = Blueprint("comptes", __name__, url_prefix="/comptes")


def _saisie(form):
    return {
        "identifiant": " ".join(form.get("identifiant", "").split()),
        "nom": form.get("nom", "").strip(),
        "alias": form.get("alias", "").strip(),
        "courriel": form.get("courriel", "").strip().lower(),
        "roles": [r for r in form.getlist("roles") if r],
        "pole": form.get("pole", "").strip(),
        "actif": "oui" if form.get("actif") else "non",
        "mot_de_passe": form.get("mot_de_passe", ""),
    }


def _formulaire(valeurs, erreurs, creation, identifiant=None):
    return render_template(
        "compte.html", valeurs=valeurs, erreurs=erreurs, creation=creation, identifiant=identifiant,
        roles=ROLES, poles=lire_listes(stockage())["poles"],
    )


@bp.route("/")
@onglet_requis("comptes")
def liste():
    comptes = sorted(lire_comptes(stockage()), key=lambda c: c.get("nom", "").lower())
    return render_template("comptes.html", comptes=comptes, roles=ROLES)


@bp.route("/nouveau", methods=["GET", "POST"])
@onglet_requis("comptes")
def nouveau():
    st = stockage()
    valeurs = {"roles": [], "actif": "oui"}
    erreurs = []
    if request.method == "POST":
        valeurs = _saisie(request.form)
        erreurs = valider(st, valeurs, creation=True)
        if not erreurs:
            compte = creer(st, valeurs["identifiant"], valeurs["nom"], valeurs["roles"], valeurs["mot_de_passe"],
                           courriel=valeurs["courriel"], alias=valeurs["alias"], pole=valeurs["pole"])
            tracer(st, nom_utilisateur(), "Comptes", compte["id"],
                   {"création": ("", f"{compte['nom']} ({compte['roles']})")})
            flash(f"Compte de {compte['nom']} créé. Communiquez-lui son mot de passe initial : "
                  "il devra le changer à la première connexion.", "succes")
            return redirect(url_for("comptes.liste"))
    return _formulaire(valeurs, erreurs, creation=True)


@bp.route("/<identifiant>", methods=["GET", "POST"])
@onglet_requis("comptes")
def modifier(identifiant):
    st = stockage()
    compte = trouver(st, identifiant)
    if compte is None:
        abort(404)
    valeurs = dict(compte, roles=[r for r in compte.get("roles", "").split(",") if r])
    erreurs = []
    if request.method == "POST":
        valeurs = _saisie(request.form)
        erreurs = valider(st, valeurs, identifiant=identifiant)
        if identifiant == g.compte["id"]:
            if CHEF not in valeurs["roles"]:
                erreurs.append("Vous ne pouvez pas retirer votre propre rôle de Chef de projet.")
            if valeurs["actif"] != "oui":
                erreurs.append("Vous ne pouvez pas désactiver votre propre compte.")
        if not erreurs:
            champs = {k: valeurs[k] for k in ("identifiant", "nom", "alias", "courriel", "pole", "actif")}
            champs["roles"] = ",".join(valeurs["roles"])
            changements = differences(compte, champs, champs.keys())
            if valeurs["mot_de_passe"]:
                champs["mdp_hash"] = generate_password_hash(valeurs["mot_de_passe"])
                champs["doit_changer_mdp"] = "oui"
                changements["mot de passe"] = ("", "réinitialisé")
            if changements:
                st.mettre_a_jour("Comptes", "id", identifiant, champs)
                tracer(st, nom_utilisateur(), "Comptes", identifiant, changements)
                flash(f"Compte de {champs['nom']} enregistré.", "succes")
            else:
                flash("Aucune modification.", "info")
            return redirect(url_for("comptes.liste"))
    return _formulaire(valeurs, erreurs, creation=False, identifiant=identifiant)
