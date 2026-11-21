"""Rétroplanning : liste filtrée, frise (Gantt), fiche d'une tâche, création, suppression."""

from datetime import timedelta

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from metier import decimal, entier
from metier.dates import aujourd_hui, date_fr, horodatage, lire_date, mois_fr
from metier.droits import est_responsable, est_visiteur, peut_gerer_taches, peut_modifier_suivi
from metier.journal import differences, historique, tracer
from metier.projet import STATUTS_TACHE, butoirs, lire_listes, lire_projet
from metier.taches import (
    controles_coherence, en_retard, filtrer, grouper_par_phase, lire_taches, nouvel_identifiant,
    tous_les_responsables,
)
from routes import nom_utilisateur, stockage

bp = Blueprint("retroplanning", __name__, url_prefix="/retroplanning")

CHAMPS_SUIVI = ["statut", "avancement", "commentaire"]
CHAMPS_CHEF = ["phase", "echeance_texte", "date_cible", "date_approx", "action", "responsables",
               "base", "categorie", "depend_de", "poids", "conditionnelle"]


@bp.route("/")
def liste():
    st = stockage()
    projet = lire_projet(st)
    listes = lire_listes(st)
    toutes = lire_taches(st)
    filtres = {c: request.args.get(c, "").strip() for c in ("categorie", "responsable", "statut", "q")}
    taches = filtrer(toutes, filtres["categorie"], filtres["responsable"], filtres["statut"], filtres["q"])
    vue = request.args.get("vue", "")
    if vue == "retard":
        taches = en_retard(taches, aujourd_hui())
    elif vue == "miennes" and not est_visiteur(g.compte):
        taches = [t for t in taches if est_responsable(g.compte, t)]
    else:
        vue = ""
    return render_template(
        "retroplanning.html",
        groupes=grouper_par_phase(taches, listes["phases"]),
        nb=len(taches),
        nb_total=len(toutes),
        filtres=filtres,
        vue=vue,
        listes=listes,
        responsables=tous_les_responsables(toutes),
        alertes=controles_coherence(toutes, projet),
        peut_modifier={t["id"]: peut_modifier_suivi(g.compte, t) for t in toutes},
        peut_gerer=peut_gerer_taches(g.compte),
        butoirs=butoirs(projet),
    )


@bp.route("/gantt")
def gantt():
    st = stockage()
    projet = lire_projet(st)
    listes = lire_listes(st)
    taches = [t for t in lire_taches(st) if t["_date"]]
    jalons = butoirs(projet)
    dates = [t["_date"] for t in taches] + [b["date"] for b in jalons]
    if not dates:
        return render_template("gantt.html", vide=True)
    debut = min(dates).replace(day=1)
    derniere = max(dates)
    fin = (derniere.replace(day=28) + timedelta(days=4)).replace(day=1)  # 1er du mois suivant
    duree = (fin - debut).days or 1

    def position(d):
        return round((d - debut).days / duree * 100, 2)

    mois = []
    courant = debut
    while courant < fin:
        suivant = (courant.replace(day=28) + timedelta(days=4)).replace(day=1)
        mois.append({"libelle": mois_fr(courant), "gauche": position(courant),
                     "largeur": round((suivant - courant).days / duree * 100, 2)})
        courant = suivant

    lignes = []
    for phase, groupe in grouper_par_phase(taches, listes["phases"]):
        elements = []
        for t in groupe:
            if t["_approx"]:  # période : du début du mois à la date retenue
                debut_barre = t["_date"].replace(day=1)
                gauche = position(debut_barre)
                largeur = max(position(t["_date"] + timedelta(days=1)) - gauche, 0.6)
            else:
                gauche, largeur = position(t["_date"]), 0
            elements.append({"t": t, "gauche": gauche, "largeur": largeur})
        lignes.append((phase, elements))

    reperes = [dict(b, gauche=position(b["date"])) for b in jalons]
    aujourdhui = aujourd_hui()
    return render_template(
        "gantt.html", vide=False, mois=mois, lignes=lignes, reperes=reperes,
        aujourdhui=position(aujourdhui) if debut <= aujourdhui <= fin else None,
    )


def _tache_ou_404(st, identifiant):
    for t in lire_taches(st):
        if t["id"] == identifiant:
            return t
    abort(404)


def _lire_formulaire(form, champs):
    valeurs = {}
    for c in champs:
        if c in ("date_approx", "conditionnelle"):
            valeurs[c] = "oui" if form.get(c) else "non"
        else:
            valeurs[c] = form.get(c, "").strip()
    return valeurs


def _valider(valeurs, listes, identifiants_existants):
    erreurs = []
    if "statut" in valeurs and valeurs["statut"] not in STATUTS_TACHE:
        erreurs.append("Statut inconnu.")
    if "avancement" in valeurs:
        texte = valeurs["avancement"] or "0"
        if not texte.isdigit() or not 0 <= int(texte) <= 100:
            erreurs.append("L'avancement doit être un nombre entier entre 0 et 100.")
    if "action" in valeurs and not valeurs["action"]:
        erreurs.append("L'action est obligatoire.")
    if "phase" in valeurs and not valeurs["phase"]:
        erreurs.append("La phase est obligatoire.")
    if "categorie" in valeurs and not valeurs["categorie"]:
        erreurs.append("La catégorie est obligatoire.")
    if "date_cible" in valeurs and valeurs["date_cible"] and lire_date(valeurs["date_cible"]) is None:
        erreurs.append("La date cible n'est pas valide (format aaaa-mm-jj).")
    if "date_cible" in valeurs and not valeurs["date_cible"]:
        erreurs.append("La date cible est obligatoire.")
    if "poids" in valeurs and valeurs["poids"] and decimal(valeurs["poids"], -1) < 0:
        erreurs.append("Le poids doit être un nombre positif.")
    if valeurs.get("depend_de"):
        inconnues = [d for d in valeurs["depend_de"].replace(";", ",").replace(" ", ",").split(",")
                     if d and d not in identifiants_existants]
        if inconnues:
            erreurs.append(f"Dépendance inconnue : {', '.join(inconnues)}.")
    return erreurs


def _completer(valeurs):
    if valeurs.get("statut") == "Fait":
        valeurs["avancement"] = "100"
    if "avancement" in valeurs:
        valeurs["avancement"] = str(entier(valeurs["avancement"] or 0))
    if "date_cible" in valeurs and not valeurs.get("echeance_texte"):
        valeurs["echeance_texte"] = date_fr(valeurs["date_cible"]).capitalize()
    return valeurs


@bp.route("/<identifiant>", methods=["GET", "POST"])
def tache(identifiant):
    st = stockage()
    t = _tache_ou_404(st, identifiant)
    listes = lire_listes(st)
    peut_suivi = peut_modifier_suivi(g.compte, t)
    peut_gerer = peut_gerer_taches(g.compte)
    erreurs = []
    valeurs = dict(t)

    if request.method == "POST":
        if not peut_suivi:
            abort(403)
        champs = CHAMPS_SUIVI + (CHAMPS_CHEF if peut_gerer else [])
        saisies = _lire_formulaire(request.form, champs)
        valeurs.update(saisies)
        ids = {x["id"] for x in lire_taches(st)} - {identifiant}
        erreurs = _valider(saisies, listes, ids)
        if not erreurs:
            saisies = _completer(saisies)
            changements = differences(t, saisies, champs)
            if changements:
                saisies["maj_par"] = nom_utilisateur()
                saisies["maj_le"] = horodatage()
                st.mettre_a_jour("Taches", "id", identifiant, saisies)
                tracer(st, nom_utilisateur(), "Taches", identifiant, changements)
                flash(f"Tâche {identifiant} enregistrée.", "succes")
            else:
                flash("Aucune modification.", "info")
            return redirect(request.form.get("retour") or url_for("retroplanning.liste"))

    return render_template(
        "tache.html", t=t, valeurs=valeurs, erreurs=erreurs, listes=listes, statuts=STATUTS_TACHE,
        peut_suivi=peut_suivi, peut_gerer=peut_gerer, creation=False,
        historique=historique(st, "Taches", identifiant),
        retour=request.form.get("retour") or request.referrer or url_for("retroplanning.liste"),
    )


@bp.route("/nouvelle", methods=["GET", "POST"])
def nouvelle():
    if not peut_gerer_taches(g.compte):
        abort(403)
    st = stockage()
    listes = lire_listes(st)
    valeurs = {"statut": "À faire", "avancement": "0", "poids": "1", "phase": request.args.get("phase", "")}
    erreurs = []
    if request.method == "POST":
        saisies = _lire_formulaire(request.form, CHAMPS_SUIVI + CHAMPS_CHEF)
        valeurs.update(saisies)
        taches = lire_taches(st)
        erreurs = _valider(saisies, listes, {x["id"] for x in taches})
        if not erreurs:
            saisies = _completer(saisies)
            saisies["id"] = nouvel_identifiant(taches)
            saisies["maj_par"] = nom_utilisateur()
            saisies["maj_le"] = horodatage()
            st.ajouter("Taches", saisies)
            tracer(st, nom_utilisateur(), "Taches", saisies["id"], {"création": ("", saisies["action"])})
            flash(f"Tâche {saisies['id']} créée.", "succes")
            return redirect(url_for("retroplanning.liste"))
    return render_template(
        "tache.html", t=None, valeurs=valeurs, erreurs=erreurs, listes=listes, statuts=STATUTS_TACHE,
        peut_suivi=True, peut_gerer=True, creation=True, historique=[],
        retour=url_for("retroplanning.liste"),
    )


@bp.route("/<identifiant>/supprimer", methods=["POST"])
def supprimer(identifiant):
    if not peut_gerer_taches(g.compte):
        abort(403)
    st = stockage()
    t = _tache_ou_404(st, identifiant)
    st.supprimer("Taches", "id", identifiant)
    tracer(st, nom_utilisateur(), "Taches", identifiant, {"suppression": (t.get("action", ""), "")})
    flash(f"Tâche {identifiant} supprimée.", "succes")
    return redirect(url_for("retroplanning.liste"))

