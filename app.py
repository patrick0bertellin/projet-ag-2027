"""Application Flask « Projet AG 2027 » du CDOS 78."""

import logging
import os
import secrets

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for

from config import Config, lire_version
from metier import booleen
from metier.comptes import trouver
from metier.dates import date_courte, date_fr, horodatage
from metier.adherents import normaliser_nom
from metier.droits import (
    COMPTE_VISITEUR, ROLES, est_chef, est_visiteur, onglets_visibles, peut_gerer_adherents, roles_du_compte,
)
from stockage import StockageIndisponible

journal = logging.getLogger(__name__)

# Pages accessibles sans être connecté, ou avant d'avoir changé son mot de passe
ENDPOINTS_PUBLICS = {"auth.connexion", "static", "sante"}
ENDPOINTS_MDP = ENDPOINTS_PUBLICS | {"auth.mot_de_passe", "auth.deconnexion"}
# Pages ouvertes au visiteur entré sans identifiant (consultation seule, aucune modification)
ENDPOINTS_VISITEUR = ENDPOINTS_PUBLICS | {"auth.deconnexion", "auth.aide", "tableau_de_bord.accueil",
                                         "retroplanning.liste", "retroplanning.gantt", "retroplanning.tache",
                                         "adherents.liste", "adherents.approbation", "adherents.referentiel"}


def creer_stockage(config):
    from stockage.sheet import StockageSheet

    return StockageSheet(
        config["SHEET_ID"],
        service_account_json=config["SERVICE_ACCOUNT_JSON"],
        chemin_cle=config["GOOGLE_APPLICATION_CREDENTIALS"],
        duree_cache=config["DUREE_CACHE"],
    )


def create_app(config=None, stockage=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["VERIFIER_CSRF"] = True
    if config:
        app.config.update(config)
    if not app.config["SECRET_KEY"]:
        journal.warning("SECRET_KEY non définie : clé temporaire (les sessions sont perdues au redémarrage).")
        app.config["SECRET_KEY"] = secrets.token_hex(32)
    app.config["VERSION"] = lire_version()

    app.extensions["stockage"] = stockage if stockage is not None else creer_stockage(app.config)

    from routes.a_venir import bp as bp_a_venir
    from routes.adherents import bp as bp_adherents
    from routes.auth import bp as bp_auth
    from routes.comptes import bp as bp_comptes
    from routes.parametres import bp as bp_parametres
    from routes.rapport import bp as bp_rapport
    from routes.retroplanning import bp as bp_retroplanning
    from routes.tableau_de_bord import bp as bp_tableau

    for bp in (bp_auth, bp_tableau, bp_retroplanning, bp_parametres, bp_comptes, bp_adherents, bp_rapport, bp_a_venir):
        app.register_blueprint(bp)

    app.jinja_env.filters["date_fr"] = date_fr
    app.jinja_env.filters["date_courte"] = date_courte
    app.jinja_env.filters["booleen"] = booleen
    app.jinja_env.filters["normaliser"] = normaliser_nom

    @app.before_request
    def charger_utilisateur():
        g.compte = None
        if request.endpoint in ("static", "sante"):
            return None
        identifiant = session.get("compte_id")
        if identifiant:
            compte = trouver(app.extensions["stockage"], identifiant)
            if compte and booleen(compte.get("actif")):
                g.compte = compte
            else:
                session.clear()
        elif session.get("visiteur"):
            g.compte = dict(COMPTE_VISITEUR)
        if request.method == "POST" and app.config["VERIFIER_CSRF"]:
            attendu = session.get("jeton_csrf")
            if not attendu or not secrets.compare_digest(request.form.get("jeton_csrf", ""), attendu):
                abort(400, "Formulaire expiré : recharger la page et recommencer.")
        if g.compte is None and request.endpoint not in ENDPOINTS_PUBLICS:
            suite = request.full_path.rstrip("?")
            return redirect(url_for("auth.connexion", suite=suite) if suite != "/" else url_for("auth.connexion"))
        if est_visiteur(g.compte):
            if request.method == "POST" and request.endpoint != "auth.connexion":
                abort(403)
            if request.endpoint not in ENDPOINTS_VISITEUR:
                flash("Cette page est réservée aux personnes connectées avec leurs identifiants.", "attention")
                return redirect(url_for("auth.connexion"))
        if g.compte and booleen(g.compte.get("doit_changer_mdp")) and request.endpoint not in ENDPOINTS_MDP:
            return redirect(url_for("auth.mot_de_passe"))
        return None

    @app.context_processor
    def contexte_commun():
        if "jeton_csrf" not in session:
            session["jeton_csrf"] = secrets.token_hex(16)
        manquants = []
        if g.get("compte") and est_chef(g.compte):
            try:
                manquants = app.extensions["stockage"].onglets_manquants()
            except StockageIndisponible:
                manquants = []
        return {
            "version": app.config["VERSION"],
            "compte": g.get("compte"),
            "onglets": onglets_visibles(g.get("compte")),
            "libelles_roles": ROLES,
            "mes_roles": [ROLES[r] for r in ROLES if r in roles_du_compte(g.get("compte"))],
            "onglets_manquants": manquants,
            "gere_adherents": peut_gerer_adherents(g.get("compte")),
            "jeton_csrf": session["jeton_csrf"],
        }

    @app.route("/sante")
    def sante():
        return {"etat": "ok", "version": app.config["VERSION"]}

    @app.errorhandler(StockageIndisponible)
    def stockage_indisponible(exc):
        journal.error("Stockage indisponible : %s", exc)
        return render_template("erreur.html", titre="Google Sheet indisponible", message=str(exc)), 503

    @app.errorhandler(400)
    def requete_invalide(exc):
        return render_template("erreur.html", titre="Requête invalide", message=exc.description), 400

    @app.errorhandler(403)
    def interdit(exc):
        return render_template("erreur.html", titre="Accès refusé",
                               message="Votre rôle ne permet pas d'accéder à cette page ou à cette action."), 403

    @app.errorhandler(413)
    def trop_gros(exc):
        return render_template("erreur.html", titre="Fichier trop volumineux",
                               message="Le fichier dépasse 5 Mo."), 413

    @app.errorhandler(404)
    def introuvable(exc):
        return render_template("erreur.html", titre="Page introuvable",
                               message="Cette page ou cet élément n'existe pas."), 404

    if stockage is None:
        enregistrer_version(app)
    return app


def enregistrer_version(app):
    """Écrit la version dans l'onglet « version » si elle n'y figure pas encore."""
    try:
        st = app.extensions["stockage"]
        if "version" in st.onglets_manquants():
            return
        deja = {l.get("version") for l in st.lire("version")}
        if app.config["VERSION"] not in deja:
            st.ajouter("version", {"version": app.config["VERSION"], "horodatage": horodatage()})
    except Exception as exc:  # le démarrage ne doit pas échouer pour ça
        journal.warning("Version non écrite dans le Sheet : %s", exc)


if __name__ == "__main__":
    application = create_app()
    application.run(host="127.0.0.1", port=application.config["PORT"],
                    debug=os.environ.get("FLASK_DEBUG", "1") == "1")
