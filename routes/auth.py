"""Connexion, déconnexion, changement de mot de passe, aide."""

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from metier import booleen
from metier.comptes import changer_mot_de_passe, erreur_mot_de_passe, lire_comptes, verifier_connexion
from metier.journal import tracer
from routes import stockage

bp = Blueprint("auth", __name__)


def _suite_sure(suite):
    """N'accepte que les chemins internes (évite les redirections vers un autre site)."""
    if suite and suite.startswith("/") and not suite.startswith("//") and suite not in ("/?", "/"):
        return suite
    return url_for("tableau_de_bord.accueil")


def _nouvelle_session(compte_id=None, visiteur=False):
    jeton_csrf = session.get("jeton_csrf")
    session.clear()
    session["jeton_csrf"] = jeton_csrf
    if compte_id:
        session["compte_id"] = compte_id
    if visiteur:
        session["visiteur"] = True
    session.permanent = True


@bp.route("/connexion", methods=["GET", "POST"])
def connexion():
    st = stockage()
    aucun_compte = not lire_comptes(st)
    identifiant = request.form.get("identifiant", "").strip()
    mot_de_passe = request.form.get("mot_de_passe", "")
    if request.method == "POST":
        if request.form.get("action") == "visiteur" or (not identifiant and not mot_de_passe):
            # sans identifiant : consultation du tableau de bord et du rétroplanning
            _nouvelle_session(visiteur=True)
            flash("Vous consultez l'application sans identifiant : tableau de bord et rétroplanning, "
                  "sans modification possible.", "info")
            return redirect(url_for("tableau_de_bord.accueil"))
        if not identifiant:
            flash("Saisir votre identifiant (ou laisser les deux champs vides pour consulter sans identifiant).",
                  "erreur")
            return render_template("connexion.html", identifiant=identifiant, aucun_compte=aucun_compte)
        compte = verifier_connexion(st, identifiant, mot_de_passe)
        if compte:
            _nouvelle_session(compte_id=compte["id"])
            return redirect(_suite_sure(request.args.get("suite")))
        flash("Identifiant ou mot de passe incorrect, ou compte désactivé.", "erreur")
    return render_template("connexion.html", identifiant=identifiant, aucun_compte=aucun_compte)


@bp.route("/deconnexion")
def deconnexion():
    visiteur = session.get("visiteur")
    session.clear()
    if not visiteur:
        flash("Vous êtes déconnecté.", "info")
    return redirect(url_for("auth.connexion"))


@bp.route("/mot-de-passe", methods=["GET", "POST"])
def mot_de_passe():
    obligatoire = booleen(g.compte.get("doit_changer_mdp"))
    if request.method == "POST":
        actuel = request.form.get("actuel", "")
        nouveau = request.form.get("nouveau", "")
        confirmation = request.form.get("confirmation", "")
        erreur = None
        if not verifier_connexion(stockage(), g.compte["identifiant"], actuel):
            erreur = "Le mot de passe actuel est incorrect."
        elif nouveau == actuel:
            erreur = "Le nouveau mot de passe doit être différent de l'actuel."
        else:
            erreur = erreur_mot_de_passe(nouveau, confirmation)
        if erreur:
            flash(erreur, "erreur")
            return render_template("mot_de_passe.html", obligatoire=obligatoire)
        changer_mot_de_passe(stockage(), g.compte["id"], nouveau)
        tracer(stockage(), g.compte["nom"], "Comptes", g.compte["id"],
               {"mot de passe": ("", "modifié")})
        flash("Mot de passe modifié.", "succes")
        return redirect(url_for("tableau_de_bord.accueil"))
    return render_template("mot_de_passe.html", obligatoire=obligatoire)


@bp.route("/aide")
def aide():
    return render_template("aide.html")
