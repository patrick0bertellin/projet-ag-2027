"""Paramètres (Chef de projet) : projet, listes, barème des voix, import du JSON."""

from flask import Blueprint, flash, redirect, render_template, request, url_for

from metier import entier
from metier.dates import lire_date
from metier.import_json import charger_json, importer
from metier.journal import differences, tracer
from metier.projet import (
    CHAMPS_NUMERIQUES, CHAMPS_PROJET, LIBELLES_LISTES, LISTES_PAR_DEFAUT, butoirs, lignes_parametres,
    lignes_projet, lire_bareme, lire_listes, lire_projet,
)
from routes import nom_utilisateur, onglet_requis, stockage

bp = Blueprint("parametres", __name__, url_prefix="/parametres")


SECTIONS = {"projet": "Projet", "listes": "Listes", "bareme": "Barème des voix", "import": "Import v05"}


def _page(projet=None, listes_texte=None, bareme_texte=None, erreurs=None, section=""):
    st = stockage()
    projet_enregistre = lire_projet(st)
    projet = projet or projet_enregistre
    listes = lire_listes(st)
    bareme = lire_bareme(st)
    if listes_texte is None:
        listes_texte = {nom: "\n".join(listes[nom]) for nom in LISTES_PAR_DEFAUT}
    if bareme_texte is None:
        bareme_texte = {
            "voix_base": str(bareme["voix_base"]),
            "voix_bonus_categorie_1": str(bareme["voix_bonus_categorie_1"]),
            "seuils": "\n".join(f"{s};{b}" for s, b in bareme["seuils"]),
        }
    return render_template(
        "parametres.html",
        projet=projet,
        champs=CHAMPS_PROJET,
        numeriques=CHAMPS_NUMERIQUES,
        butoirs=butoirs(projet_enregistre),
        listes_texte=listes_texte,
        libelles_listes=LIBELLES_LISTES,
        bareme=bareme_texte,
        erreurs=erreurs or [],
        section=section if section in SECTIONS else "projet",
        sections=SECTIONS,
        onglets_absents=st.onglets_manquants(),
    )


@bp.route("/")
@onglet_requis("parametres")
def accueil():
    return _page(section=request.args.get("section", ""))


@bp.route("/projet", methods=["POST"])
@onglet_requis("parametres")
def projet():
    st = stockage()
    avant = lire_projet(st)
    saisie = {cle: request.form.get(cle, "").strip() for cle in CHAMPS_PROJET}
    erreurs = []
    if not saisie["nom"]:
        erreurs.append("Le nom du projet est obligatoire.")
    if lire_date(saisie["date_ag"]) is None:
        erreurs.append("La date de l'AG est obligatoire (format aaaa-mm-jj).")
    for cle in CHAMPS_NUMERIQUES:
        if not saisie[cle].isdigit():
            erreurs.append(f"« {CHAMPS_PROJET[cle][0]} » doit être un nombre entier positif.")
    from metier.quorum import lire_fraction

    if lire_fraction(saisie["approbation_fraction"], defaut=None) is None:
        erreurs.append("La majorité d'approbation doit être une fraction comme « 2/3 » ou « 1/2 ».")
    if saisie["date_ca"] and lire_date(saisie["date_ca"]) is None:
        erreurs.append("La date du CA n'est pas valide.")
    if erreurs:
        return _page(projet=saisie, erreurs=erreurs, section="projet")
    st.remplacer_tout("Projet", lignes_projet(saisie))
    tracer(st, nom_utilisateur(), "Projet", "projet", differences(avant, saisie, CHAMPS_PROJET))
    flash("Paramètres du projet enregistrés ; les butoirs sont recalculés.", "succes")
    return redirect(url_for("parametres.accueil", section="projet"))


def _lignes(texte):
    vus, valeurs = set(), []
    for ligne in (texte or "").splitlines():
        ligne = ligne.strip()
        if ligne and ligne not in vus:
            vus.add(ligne)
            valeurs.append(ligne)
    return valeurs


@bp.route("/listes", methods=["POST"])
@onglet_requis("parametres")
def listes():
    st = stockage()
    textes = {nom: request.form.get(nom, "") for nom in LISTES_PAR_DEFAUT if nom != "statuts"}
    nouvelles = {nom: _lignes(t) for nom, t in textes.items()}
    erreurs = [f"La liste « {LIBELLES_LISTES[n]} » ne peut pas être vide." for n, v in nouvelles.items() if not v]
    if erreurs:
        textes["statuts"] = "\n".join(LISTES_PAR_DEFAUT["statuts"])
        return _page(listes_texte=textes, erreurs=erreurs, section="listes")
    avant = lire_listes(st)
    st.remplacer_tout("Parametres", lignes_parametres(nouvelles, lire_bareme(st)))
    changements = {n: (" | ".join(avant.get(n, [])), " | ".join(v))
                   for n, v in nouvelles.items() if avant.get(n) != v}
    tracer(st, nom_utilisateur(), "Parametres", "listes", changements)
    flash("Listes enregistrées.", "succes")
    return redirect(url_for("parametres.accueil", section="listes"))


@bp.route("/bareme", methods=["POST"])
@onglet_requis("parametres")
def bareme():
    st = stockage()
    saisie = {c: request.form.get(c, "").strip() for c in ("voix_base", "voix_bonus_categorie_1", "seuils")}
    erreurs, seuils = [], []
    for c in ("voix_base", "voix_bonus_categorie_1"):
        if not saisie[c].isdigit():
            erreurs.append("Les voix de base et le bonus de catégorie 1 doivent être des nombres entiers.")
            break
    for ligne in _lignes(saisie["seuils"]):
        morceaux = [m.strip() for m in ligne.replace(",", ";").split(";")]
        if len(morceaux) != 2 or not all(m.isdigit() for m in morceaux):
            erreurs.append(f"Ligne de barème incorrecte : « {ligne} » (attendu : licenciés;bonus).")
        else:
            seuils.append((int(morceaux[0]), int(morceaux[1])))
    if erreurs:
        return _page(bareme_texte=saisie, erreurs=erreurs, section="bareme")
    avant = lire_bareme(st)
    nouveau = {"voix_base": entier(saisie["voix_base"]),
               "voix_bonus_categorie_1": entier(saisie["voix_bonus_categorie_1"]),
               "seuils": sorted(seuils)}
    st.remplacer_tout("Parametres", lignes_parametres(lire_listes(st), nouveau))
    tracer(st, nom_utilisateur(), "Parametres", "bareme_voix",
           {"barème": (str(avant), str(nouveau))} if avant != nouveau else {})
    flash("Barème des voix enregistré.", "succes")
    return redirect(url_for("parametres.accueil", section="bareme"))


@bp.route("/import", methods=["POST"])
@onglet_requis("parametres")
def import_json():
    st = stockage()
    if request.form.get("confirmation") != "oui":
        return _page(erreurs=["Cocher la case de confirmation pour lancer l'import."], section="import")
    if st.onglets_manquants():
        st.preparer_onglets()
    compte_rendu = importer(
        st, charger_json(),
        conserver_suivi=bool(request.form.get("conserver_suivi")),
        reinitialiser_parametres=bool(request.form.get("reinitialiser_parametres")),
    )
    tracer(st, nom_utilisateur(), "Import", "projet_ag_2027.json",
           {"import": ("", ", ".join(f"{k} : {v}" for k, v in compte_rendu.items()))})
    flash("Import terminé : " + ", ".join(f"{k} {v} lignes" for k, v in compte_rendu.items()) + ".", "succes")
    return redirect(url_for("parametres.accueil", section="import"))
