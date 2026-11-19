"""Adhérents : liste des comités, voix, quorum, fiche, import et export Excel, référentiel CNOSF."""

import base64
import json
import os
import secrets
import tempfile
import time
from pathlib import Path

from flask import (
    Blueprint, Response, abort, flash, g, redirect, render_template, request, url_for,
)

from metier import booleen, entier
from metier.adherents import (
    LIBELLES_CATEGORIES, MODES_REGLEMENT, ONGLET_SYNCHRO, a_relancer, mail_valide, lire_comites, lire_federations,
    modifications_non_exportees, nettoyer_mail, nettoyer_texte, normaliser_nom, nouvel_identifiant,
)
from metier.dates import horodatage, lire_date
from metier.droits import est_visiteur, peut_gerer_adherents, peut_suivre_presence
from metier.excel_adherents import FichierInvalide, exporter_adherents, lire_adherents, lire_cnosf
from metier.import_adherents import LIBELLES_CHAMPS, calculer_operations, appliquer, correspondances
from metier.journal import differences, historique, tracer
from metier.modele_excel import MODELE_PAR_DEFAUT, enregistrer_modele, lire_modele, nettoyer_modele
from metier.projet import lire_bareme, lire_projet
from metier.quorum import lire_fraction, seuil_approbation, synthese
from metier.sondage import (
    LIBELLES_REPONSES, SondageInvalide, cle_reponse, completer_avec_sondage, fusionner, lire_fichier,
    synthese_sondage,
)
from routes import nom_utilisateur, onglet_requis, stockage

bp = Blueprint("adherents", __name__, url_prefix="/adherents")

DOSSIER_IMPORTS = Path(tempfile.gettempdir()) / "projet_ag_2027_imports"
DUREE_IMPORT = 3600  # un import en attente de validation expire au bout d'une heure

CHAMPS_FICHE = ["nom", "federation", "categorie", "licencies", "clubs", "feminines", "mode_reglement",
                "montant", "date_reglement", "elu_referent", "president", "mail_president", "actif"]


def _exiger_gestion():
    if not peut_gerer_adherents(g.compte):
        abort(403)


# ------------------------------------------------------------------ liste
@bp.route("/")
@onglet_requis("adherents")
def liste():
    st = stockage()
    projet = lire_projet(st)
    comites = lire_comites(st)
    reponses = st.lire("Sondage")
    non_rapprochees = completer_avec_sondage(comites, reponses)
    resume = synthese(comites)
    non_a_jour, non_inscrits = a_relancer(comites)
    fraction = "/".join(str(x) for x in lire_fraction(projet.get("approbation_fraction")))
    suivi = None
    if peut_suivre_presence(g.compte):
        suivi = synthese_sondage(comites, non_rapprochees)
        suivi["nb_lignes"] = len(reponses)
    return render_template(
        "adherents.html",
        visiteur=est_visiteur(g.compte),
        suivi=suivi,
        libelles_reponses=LIBELLES_REPONSES,
        date_ag=projet.get("date_ag"),
        actifs=[c for c in comites if c["_actif"]],
        inactifs=[c for c in comites if not c["_actif"]],
        resume=resume,
        non_a_jour=non_a_jour,
        non_inscrits=non_inscrits,
        fraction=fraction,
        approbation_si_tous=seuil_approbation(resume["total_voix"], fraction),
        nb_federations=len(lire_federations(st)),
        peut_gerer=peut_gerer_adherents(g.compte),
        categories=LIBELLES_CATEGORIES,
        bareme=lire_bareme(st),
        synchro=modifications_non_exportees(st, comites),
    )


@bp.route("/approbation")
@onglet_requis("adherents")
def approbation():
    """Petit calcul : voix « pour » nécessaires pour un nombre de voix exprimées."""
    projet = lire_projet(stockage())
    exprimees = entier(request.args.get("exprimees"), 0)
    return {"exprimees": exprimees, "seuil": seuil_approbation(exprimees, projet.get("approbation_fraction"))}


# ------------------------------------------------------------------ fiche
def _valider_fiche(valeurs, comites, identifiant, federations):
    erreurs = []
    if not valeurs["nom"]:
        erreurs.append("Le nom de l'organisme est obligatoire.")
    elif any(normaliser_nom(c.get("nom")) == normaliser_nom(valeurs["nom"]) and c["id"] != identifiant
             for c in comites):
        erreurs.append("Un autre comité porte déjà ce nom.")
    for champ, libelle in (("licencies", "Nombre de licences"), ("clubs", "Nombre de clubs"),
                           ("feminines", "Nombre de féminines"), ("montant", "Montant")):
        if valeurs[champ] and not valeurs[champ].replace(" ", "").isdigit():
            erreurs.append(f"« {libelle} » doit être un nombre entier.")
    if valeurs["mode_reglement"] and valeurs["mode_reglement"] not in MODES_REGLEMENT:
        erreurs.append("Mode de règlement inconnu.")
    if valeurs["date_reglement"] and lire_date(valeurs["date_reglement"]) is None:
        erreurs.append("La date de règlement n'est pas valide.")
    if valeurs["mail_president"] and not mail_valide(valeurs["mail_president"]):
        erreurs.append("Le mail du président n'est pas valide.")
    if valeurs["federation"] and valeurs["federation"] not in {f["discipline"] for f in federations}:
        erreurs.append("Fédération inconnue du référentiel CNOSF.")
    if not valeurs["federation"] and valeurs["categorie"] not in {"1", "2", "3", "4", "5"}:
        erreurs.append("Sans fédération CNOSF, choisir la catégorie (1 à 5).")
    return erreurs


def _lire_fiche(form):
    valeurs = {c: nettoyer_texte(form.get(c, "")) for c in CHAMPS_FICHE}
    valeurs["mail_president"] = nettoyer_mail(form.get("mail_president", ""))
    valeurs["actif"] = "oui" if form.get("actif") else "non"
    return valeurs


def _fiche(comite, valeurs, erreurs, creation):
    st = stockage()
    federations = lire_federations(st)
    return render_template(
        "comite.html", comite=comite, valeurs=valeurs, erreurs=erreurs, creation=creation,
        federations=federations, categories=LIBELLES_CATEGORIES, modes=MODES_REGLEMENT,
        peut_gerer=peut_gerer_adherents(g.compte),
        historique=historique(st, "Comites", comite["id"]) if comite else [],
    )


@bp.route("/nouveau", methods=["GET", "POST"])
@onglet_requis("adherents")
def nouveau():
    _exiger_gestion()
    st = stockage()
    valeurs = {c: "" for c in CHAMPS_FICHE}
    valeurs["actif"] = "oui"
    erreurs = []
    if request.method == "POST":
        valeurs = _lire_fiche(request.form)
        comites = lire_comites(st)
        federations = lire_federations(st)
        erreurs = _valider_fiche(valeurs, comites, None, federations)
        if not erreurs:
            _completer_montant(valeurs, lire_projet(st))
            valeurs["id"] = nouvel_identifiant(comites)
            valeurs["noms_import"] = valeurs["nom"]
            valeurs["maj_par"], valeurs["maj_le"] = nom_utilisateur(), horodatage()
            st.ajouter("Comites", valeurs)
            tracer(st, nom_utilisateur(), "Comites", valeurs["id"], {"création": ("", valeurs["nom"])})
            flash(f"Comité « {valeurs['nom']} » ajouté. Le fichier Excel n'est plus à jour : "
                  "pensez à l'exporter.", "attention")
            return redirect(url_for("adherents.liste"))
    return _fiche(None, valeurs, erreurs, creation=True)


def _completer_montant(valeurs, projet):
    """Avant enregistrement : nombres sans espaces ; montant par défaut si le règlement est saisi."""
    for champ in ("licencies", "clubs", "feminines", "montant"):
        valeurs[champ] = valeurs[champ].replace(" ", "")
    if valeurs.get("mode_reglement") and not valeurs.get("montant"):
        valeurs["montant"] = projet.get("montant_cotisation", "")


@bp.route("/<identifiant>", methods=["GET", "POST"])
@onglet_requis("adherents")
def fiche(identifiant):
    st = stockage()
    comites = lire_comites(st)
    comite = next((c for c in comites if c["id"] == identifiant), None)
    if comite is None:
        abort(404)
    valeurs = {c: comite.get(c, "") for c in CHAMPS_FICHE}
    valeurs["actif"] = "oui" if comite["_actif"] else "non"
    erreurs = []
    if request.method == "POST":
        _exiger_gestion()
        valeurs = _lire_fiche(request.form)
        erreurs = _valider_fiche(valeurs, comites, identifiant, lire_federations(st))
        if not erreurs:
            _completer_montant(valeurs, lire_projet(st))
            avant = dict(comite, actif="oui" if comite["_actif"] else "non")
            changements = differences(avant, valeurs, CHAMPS_FICHE)
            if changements:
                valeurs["maj_par"], valeurs["maj_le"] = nom_utilisateur(), horodatage()
                st.mettre_a_jour("Comites", "id", identifiant, valeurs)
                tracer(st, nom_utilisateur(), "Comites", identifiant,
                       {LIBELLES_CHAMPS.get(k, k): v for k, v in changements.items()})
                flash(f"Comité « {valeurs['nom']} » mis à jour : "
                      + ", ".join(LIBELLES_CHAMPS.get(k, k) for k in changements)
                      + ". Le fichier Excel n'est plus à jour : pensez à l'exporter.", "attention")
            else:
                flash("Aucune modification.", "info")
            return redirect(url_for("adherents.liste"))
    return _fiche(comite, valeurs, erreurs, creation=False)


# ------------------------------------------------------------------ export
@bp.route("/export")
@onglet_requis("adherents")
def export():
    st = stockage()
    projet = lire_projet(st)
    date_ag = lire_date(projet.get("date_ag"))
    annee = (date_ag.year - 1) if date_ag else ""
    fraction = "/".join(str(x) for x in lire_fraction(projet.get("approbation_fraction")))
    comites = lire_comites(st)
    modele, _ = lire_modele(st)
    try:
        contenu = exporter_adherents(comites, annee, fraction, modele)
    except Exception:  # modèle enregistré illisible : repli sur le modèle livré avec l'application
        contenu = exporter_adherents(comites, annee, fraction, MODELE_PAR_DEFAUT.read_bytes())
    nom = f"{horodatage()[:10]}-Membres CDOS-{annee} - Adhésions.xlsx"
    tracer(st, nom_utilisateur(), ONGLET_SYNCHRO, "export",
           {"fichier exporté": ("", f"{sum(1 for c in comites if c['_actif'])} comités")})
    return Response(
        contenu,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{_encoder(nom)}"},
    )


def _encoder(nom):
    from urllib.parse import quote

    return quote(nom)


# ------------------------------------------------------------------ import
def _nettoyer_imports():
    DOSSIER_IMPORTS.mkdir(exist_ok=True)
    for fichier in DOSSIER_IMPORTS.glob("*.json"):
        if time.time() - fichier.stat().st_mtime > DUREE_IMPORT:
            fichier.unlink(missing_ok=True)


def _chemin_import(jeton):
    if not jeton.isalnum():
        abort(404)
    return DOSSIER_IMPORTS / f"{jeton}.json"


@bp.route("/import", methods=["GET", "POST"])
@onglet_requis("adherents")
def importer():
    _exiger_gestion()
    erreurs = []
    if request.method == "POST":
        fichier = request.files.get("fichier")
        if not fichier or not fichier.filename:
            erreurs.append("Choisir un fichier Excel (.xlsx).")
        elif not fichier.filename.lower().endswith(".xlsx"):
            erreurs.append("Le fichier doit être au format .xlsx.")
        else:
            try:
                lecture = lire_adherents(fichier.stream)
            except FichierInvalide as exc:
                erreurs.append(str(exc))
            else:
                _nettoyer_imports()
                jeton = secrets.token_hex(12)
                lecture["nom_fichier"] = fichier.filename
                lecture["auteur"] = g.compte["id"]
                fichier.stream.seek(0)
                modele = nettoyer_modele(fichier.stream)
                lecture["modele"] = base64.b64encode(modele).decode("ascii") if modele else ""
                _chemin_import(jeton).write_text(json.dumps(lecture, ensure_ascii=False), encoding="utf-8")
                os.chmod(_chemin_import(jeton), 0o600)
                return redirect(url_for("adherents.apercu", jeton=jeton))
    st = stockage()
    return render_template("import_adherents.html", erreurs=erreurs,
                           synchro=modifications_non_exportees(st, lire_comites(st)))


@bp.route("/import/<jeton>", methods=["GET", "POST"])
@onglet_requis("adherents")
def apercu(jeton):
    _exiger_gestion()
    chemin = _chemin_import(jeton)
    if not chemin.exists():
        flash("Cet import a expiré ou a déjà été appliqué : recommencer.", "attention")
        return redirect(url_for("adherents.importer"))
    lecture = json.loads(chemin.read_text(encoding="utf-8"))
    st = stockage()
    comites = lire_comites(st)
    federations = lire_federations(st)
    bareme = lire_bareme(st)
    _, inconnus = correspondances(lecture, comites)
    choix = {o["cle"]: request.values.get(f"choix_{o['cle']}", "nouveau") for o in inconnus}
    operations = calculer_operations(lecture, comites, federations, bareme, choix)

    if request.method == "POST" and request.form.get("action") == "appliquer":
        selection = set(request.form.getlist("operations"))
        compte_rendu = appliquer(st, operations, selection, nom_utilisateur(), lecture.get("nom_fichier", ""))
        if lecture.get("modele") and request.form.get("garder_modele"):
            enregistrer_modele(st, base64.b64decode(lecture["modele"]), lecture.get("nom_fichier", ""),
                               nom_utilisateur(), horodatage())
            flash("La mise en forme de ce fichier sera reprise par les prochains exports.", "info")
        chemin.unlink(missing_ok=True)
        flash("Import appliqué : " + ", ".join(
            f"{n} {libelle}" for libelle, n in (
                ("nouveau(x)", compte_rendu["nouveau"]), ("modifié(s)", compte_rendu["modifie"]),
                ("réactivé(s)", compte_rendu["reactive"]), ("désactivé(s)", compte_rendu["absent"]),
            )) + ".", "succes")
        return redirect(url_for("adherents.liste"))

    if request.method == "POST":
        selection = set(request.form.getlist("operations"))
    else:
        selection = {op["cle"] for op in operations if op["type"] != "identique"}
    deja_choisis = {v for v in choix.values() if v != "nouveau"}
    reconnus_ids = {op["comite_id"] for op in operations if op["type"] in ("modifie", "identique", "reactive")}
    candidats = [c for c in comites if c["id"] not in reconnus_ids or c["id"] in deja_choisis]
    return render_template(
        "apercu_import.html", code_import=jeton, lecture=lecture, operations=operations, inconnus=inconnus,
        choix=choix, candidats=candidats, libelles=LIBELLES_CHAMPS, selection=selection,
        synchro=modifications_non_exportees(st, comites),
        nb={t: sum(1 for op in operations if op["type"] == t)
            for t in ("nouveau", "modifie", "reactive", "absent", "identique")},
    )


# ------------------------------------------------------------------ sondage et présence (Chef de projet)
def _exiger_suivi():
    if not peut_suivre_presence(g.compte):
        abort(403)


@bp.route("/sondage", methods=["POST"])
@onglet_requis("adherents")
def importer_sondage():
    """Remplace les réponses par celles du fichier Excel du formulaire (rapprochements manuels gardés)."""
    _exiger_suivi()
    fichier = request.files.get("fichier")
    if not fichier or not fichier.filename.lower().endswith(".xlsx"):
        flash("Choisir le fichier Excel des réponses au sondage (.xlsx).", "erreur")
        return redirect(url_for("adherents.liste") + "#sondage")
    try:
        nouvelles = lire_fichier(fichier.stream)
    except SondageInvalide as exc:
        flash(str(exc), "erreur")
        return redirect(url_for("adherents.liste") + "#sondage")
    st = stockage()
    if "Sondage" in st.onglets_manquants():
        st.preparer_onglets()
    st.remplacer_tout("Sondage", fusionner(nouvelles, st.lire("Sondage")))
    tracer(st, nom_utilisateur(), "Sondage", "réponses", {"fichier importé": ("", f"{fichier.filename} : "
                                                                              f"{len(nouvelles)} réponses")})
    flash(f"{len(nouvelles)} réponses au sondage importées.", "succes")
    return redirect(url_for("adherents.liste") + "#sondage")


@bp.route("/sondage/rapprocher", methods=["POST"])
@onglet_requis("adherents")
def rapprocher_reponse():
    """Rattache à la main une réponse au sondage à un comité membre."""
    _exiger_suivi()
    st = stockage()
    cle, comite_id = request.form.get("cle", ""), request.form.get("comite_id", "")
    if comite_id and comite_id not in {c["id"] for c in lire_comites(st)}:
        abort(400, "Comité inconnu.")
    lignes = st.lire("Sondage")
    for ligne in lignes:
        if cle_reponse(ligne) == cle:
            ligne["comite_id"] = comite_id
            st.remplacer_tout("Sondage", lignes)
            flash(f"Réponse de « {ligne.get('organisme')} » rattachée." if comite_id else "Rattachement retiré.",
                  "succes")
            break
    else:
        flash("Réponse introuvable : réimporter le fichier du sondage.", "attention")
    return redirect(url_for("adherents.liste") + "#sondage")


@bp.route("/presence", methods=["POST"])
@onglet_requis("adherents")
def presence():
    """Jour de l'AG : enregistre en une fois les comités présents (case cochée)."""
    _exiger_suivi()
    st = stockage()
    presents = set(request.form.getlist("presents"))
    lignes = [l for l in st.lire("Comites") if l.get("id")]
    quand, qui, journal = horodatage(), nom_utilisateur(), []
    for ligne in lignes:
        if ligne.get("actif", "oui") == "non":
            continue
        avant = "oui" if booleen(ligne.get("present")) else "non"
        apres = "oui" if ligne["id"] in presents else "non"
        if avant != apres:
            ligne["present"], ligne["maj_par"], ligne["maj_le"] = apres, qui, quand
            journal.append({"horodatage": quand, "utilisateur": qui, "onglet": "Comites", "id": ligne["id"],
                            "champ": "présent à l'AG", "ancienne": avant, "nouvelle": apres})
    if journal:
        st.remplacer_tout("Comites", lignes)
        st.ajouter_lignes("Journal", journal)
        flash(f"Présences enregistrées ({len(journal)} changement(s)).", "succes")
    else:
        flash("Aucun changement de présence.", "info")
    return redirect(url_for("adherents.liste") + "#presence")


# ------------------------------------------------------------------ référentiel CNOSF
@bp.route("/referentiel", methods=["GET", "POST"])
@onglet_requis("adherents")
def referentiel():
    st = stockage()
    erreurs = []
    if request.method == "POST":
        _exiger_gestion()
        fichier = request.files.get("fichier")
        if not fichier or not fichier.filename.lower().endswith(".xlsx"):
            erreurs.append("Choisir le fichier Excel du référentiel CNOSF (.xlsx).")
        else:
            try:
                federations = lire_cnosf(fichier.stream)
            except FichierInvalide as exc:
                erreurs.append(str(exc))
            else:
                avant = len(lire_federations(st))
                st.remplacer_tout("Federations", federations)
                tracer(st, nom_utilisateur(), "Federations", "référentiel CNOSF",
                       {"fédérations": (str(avant), str(len(federations)))})
                flash(f"Référentiel CNOSF mis à jour : {len(federations)} fédérations.", "succes")
                return redirect(url_for("adherents.referentiel"))
    federations = lire_federations(st)
    utilisees = {c.get("federation") for c in lire_comites(st, federations=federations)}
    return render_template("referentiel.html", federations=federations, erreurs=erreurs,
                           categories=LIBELLES_CATEGORIES, utilisees=utilisees,
                           peut_gerer=peut_gerer_adherents(g.compte))
