"""Tâches du rétroplanning : lecture typée, avancement, retards, contrôles de cohérence."""

import re
from datetime import timedelta

from metier import booleen, decimal, entier
from metier.dates import date_fr, est_dimanche, lire_date
from metier.droits import noms_responsables
from metier.projet import STATUTS_TERMINES, butoir


def preparer(ligne):
    """Ajoute à une ligne brute du Sheet des champs typés (préfixés par _)."""
    t = dict(ligne)
    t["_date"] = lire_date(t.get("date_cible"))
    t["_approx"] = booleen(t.get("date_approx"))
    t["_conditionnelle"] = booleen(t.get("conditionnelle"))
    t["_avancement"] = avancement_effectif(t)
    t["_poids"] = decimal(t.get("poids"), 1.0) if str(t.get("poids", "")).strip() else 1.0
    t["_responsables"] = noms_responsables(t.get("responsables", ""))
    t["_termine"] = t.get("statut") in STATUTS_TERMINES
    return t


def lire_taches(stockage):
    taches = [preparer(l) for l in stockage.lire("Taches") if l.get("id")]
    return trier(taches)


def trier(taches):
    return sorted(taches, key=lambda t: (t["_date"] is None, t["_date"] or 0, t.get("id", "")))


def avancement_effectif(t):
    if t.get("statut") == "Fait":
        return 100
    return max(0, min(100, entier(t.get("avancement"), 0)))


def comptee(t):
    """Une tâche compte dans l'avancement sauf si elle est conditionnelle ou sans objet."""
    return not t["_conditionnelle"] and t.get("statut") != "Sans objet"


def avancement_global(taches):
    """Moyenne des avancements pondérée par la colonne poids (1 par défaut)."""
    retenues = [t for t in taches if comptee(t)]
    total_poids = sum(t["_poids"] for t in retenues)
    if not total_poids:
        return 0
    return round(sum(t["_avancement"] * t["_poids"] for t in retenues) / total_poids)


def avancement_par(taches, champ, ordre):
    """Avancement par phase ou par catégorie, dans l'ordre des listes en paramètre."""
    groupes = {}
    for t in taches:
        groupes.setdefault(t.get(champ, "") or "(non renseigné)", []).append(t)
    noms = [n for n in ordre if n in groupes] + sorted(n for n in groupes if n not in ordre)
    resultat = []
    for nom in noms:
        liste = groupes[nom]
        retenues = [t for t in liste if comptee(t)]
        resultat.append({
            "nom": nom,
            "avancement": avancement_global(liste),
            "nb": len(liste),
            "nb_faites": sum(1 for t in liste if t.get("statut") == "Fait"),
            "sans_calcul": not retenues,
        })
    return resultat


def ouverte(t):
    return not t["_termine"] and not t["_conditionnelle"]


def en_retard(taches, ref):
    return [t for t in taches if ouverte(t) and t["_date"] and t["_date"] < ref]


def prochaines(taches, ref, nb_jours=14):
    fin = ref + timedelta(days=nb_jours)
    return [t for t in taches if ouverte(t) and t["_date"] and ref <= t["_date"] <= fin]


def filtrer(taches, categorie="", responsable="", statut="", recherche=""):
    resultat = taches
    if categorie:
        resultat = [t for t in resultat if t.get("categorie") == categorie]
    if responsable:
        resultat = [t for t in resultat if responsable in t["_responsables"]]
    if statut:
        resultat = [t for t in resultat if t.get("statut") == statut]
    if recherche:
        mots = recherche.lower().split()
        def texte(t):
            return " ".join(str(t.get(c, "")) for c in
                            ("id", "action", "responsables", "base", "commentaire", "echeance_texte")).lower()
        resultat = [t for t in resultat if all(m in texte(t) for m in mots)]
    return resultat


def grouper_par_phase(taches, phases):
    groupes = {}
    for t in taches:
        groupes.setdefault(t.get("phase", "") or "(sans phase)", []).append(t)
    noms = [p for p in phases if p in groupes] + sorted(p for p in groupes if p not in phases)
    return [(nom, groupes[nom]) for nom in noms]


def tous_les_responsables(taches):
    noms = set()
    for t in taches:
        noms.update(t["_responsables"])
    return sorted(noms, key=str.lower)


def nouvel_identifiant(taches):
    numeros = [int(m.group(1)) for t in taches if (m := re.fullmatch(r"T(\d+)", t.get("id", "")))]
    return f"T{(max(numeros) if numeros else 0) + 1:03d}"


def controles_coherence(taches, projet):
    """Alertes affichées en tête du rétroplanning."""
    alertes = []
    par_id = {t["id"]: t for t in taches}

    for t in taches:
        if t["_conditionnelle"] or t.get("statut") == "Sans objet":
            continue
        if not t["_responsables"]:
            alertes.append(_alerte(t, "tâche sans responsable"))
        if t["_date"] is None:
            alertes.append(_alerte(t, "tâche sans date cible"))
        elif not t["_approx"] and est_dimanche(t["_date"]):
            alertes.append(_alerte(t, f"échéance un dimanche ({date_fr(t['_date'])})"))
        for dep_id in re.split(r"[,; ]+", t.get("depend_de", "") or ""):
            dep = par_id.get(dep_id.strip())
            if dep_id.strip() and dep is None:
                alertes.append(_alerte(t, f"dépendance {dep_id} introuvable"))
            elif dep and dep["_date"] and t["_date"] and t["_date"] < dep["_date"]:
                alertes.append(_alerte(
                    t, f"prévue le {date_fr(t['_date'])}, avant la tâche dont elle dépend "
                       f"({dep['id']}, {date_fr(dep['_date'])})"))

    date_butoir = butoir(projet, "convocation")
    convocation = par_id.get((projet.get("tache_convocation") or "").strip())
    if convocation and date_butoir and convocation["_date"] and convocation["_date"] > date_butoir:
        alertes.append(_alerte(
            convocation, f"convocation prévue le {date_fr(convocation['_date'])}, "
                         f"après le butoir du {date_fr(date_butoir)}", niveau="grave"))

    date_ca = lire_date(projet.get("date_ca"))
    conv_ca = par_id.get((projet.get("tache_convocation_ca") or "").strip())
    if date_ca and conv_ca and conv_ca["_date"] and (date_ca - conv_ca["_date"]).days < 10:
        alertes.append(_alerte(
            conv_ca, f"CA du {date_fr(date_ca)} convoqué moins de 10 jours avant", niveau="grave"))
    return alertes


def _alerte(tache, message, niveau="attention"):
    return {"id": tache.get("id", ""), "action": tache.get("action", ""), "message": message, "niveau": niveau}


def prochain_jalon(taches, projet, ref):
    """Prochain jalon : butoir statutaire, ou tâche ouverte ayant une base statutaire."""
    from metier.projet import butoirs

    candidats = [(b["date"], b["libelle"]) for b in butoirs(projet) if b["date"] >= ref]
    candidats += [
        (t["_date"], f"{t['id']} – {t['action']}")
        for t in taches
        if ouverte(t) and t["_date"] and t["_date"] >= ref and (t.get("base") or "").strip()
    ]
    if not candidats:
        return None
    d, libelle = min(candidats, key=lambda c: c[0])
    return {"date": d, "libelle": libelle}
