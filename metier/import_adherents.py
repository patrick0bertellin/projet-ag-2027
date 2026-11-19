"""Import d'un fichier Excel des adhérents : calcul des différences, puis application.

1. lire_adherents() lit le fichier (metier.excel_adherents).
2. calculer_operations() compare au contenu de l'onglet Comites : nouveaux, modifiés,
   identiques, absents (à désactiver), avec les anomalies.
3. appliquer() écrit les opérations cochées et les trace dans le Journal.

Les champs gérés par l'application (fédération déjà choisie, inscription, représentant,
mandat, présence, date de règlement) ne sont jamais écrasés par un import.
"""

from metier.adherents import (
    ONGLET_SYNCHRO, categorie_du_comite, index_federations, noms_connus, nouvel_identifiant, rapprocher_federation,
)
from metier.dates import horodatage
from metier.quorum import voix_du_comite

CHAMPS_IMPORT = ["nom", "mode_reglement", "montant", "clubs", "licencies", "feminines",
                 "elu_referent", "president", "mail_president"]
LIBELLES_CHAMPS = {
    "nom": "nom", "mode_reglement": "règlement", "montant": "montant", "clubs": "clubs",
    "licencies": "licences", "feminines": "féminines", "elu_referent": "élu référent",
    "president": "président", "mail_president": "mail", "federation": "fédération CNOSF",
    "categorie": "catégorie", "actif": "actif",
}


def correspondances(lecture, comites):
    """{clé organisme: id du comité reconnu} et la liste des organismes non reconnus."""
    reconnus, inconnus = {}, []
    for o in lecture["organismes"]:
        trouve = next((c for c in comites if o["cle"] in noms_connus(c)), None)
        if trouve:
            reconnus[o["cle"]] = trouve["id"]
        else:
            inconnus.append(o)
    return reconnus, inconnus


def calculer_operations(lecture, comites, federations, bareme, choix=None):
    """Liste des opérations. choix : {clé organisme non reconnu: "nouveau" ou id de comité}."""
    choix = choix or {}
    index = index_federations(federations)
    par_id = {c["id"]: c for c in comites}
    reconnus, _ = correspondances(lecture, comites)
    for cle, valeur in choix.items():
        if valeur and valeur != "nouveau" and valeur in par_id:
            reconnus[cle] = valeur
    operations, vus = [], set()

    for o in lecture["organismes"]:
        valeurs = {k: ("" if v is None else str(v)) for k, v in o["valeurs"].items()}
        federation_excel = valeurs.pop("federation", "")
        if federation_excel and federation_excel not in index:
            o["anomalies"].append(f"fédération CNOSF « {federation_excel} » inconnue du référentiel (ignorée)")
            federation_excel = ""
        valeurs["nom"] = o["nom"]
        identifiant = reconnus.get(o["cle"])
        anomalies = list(o["anomalies"])

        if identifiant:
            vus.add(identifiant)
            actuel = par_id[identifiant]
            changements = {
                champ: (actuel.get(champ, "") or "", valeurs[champ])
                for champ in CHAMPS_IMPORT
                if champ in valeurs and str(actuel.get(champ, "") or "") != valeurs[champ]
            }
            if federation_excel and federation_excel != actuel.get("federation"):
                changements["federation"] = (actuel.get("federation", ""), federation_excel)
            if not actuel["_actif"]:
                changements["actif"] = ("non", "oui")
            apres = dict(actuel, **{k: v[1] for k, v in changements.items()})
            type_op = ("reactive" if "actif" in changements else "modifie") if changements else "identique"
            operation = {"cle": f"o:{o['cle']}", "type": type_op, "nom": o["nom"], "comite_id": identifiant,
                         "nom_actuel": actuel.get("nom"), "changements": changements}
        else:
            federation = federation_excel or (rapprocher_federation(o["nom"], federations) or {}).get("discipline", "")
            apres = dict(valeurs, federation=federation, actif="oui")
            if not federation and o.get("categorie_excel"):
                apres["categorie"] = str(o["categorie_excel"])
                anomalies.append("aucune fédération CNOSF reconnue : catégorie de l'Excel reprise")
            elif not federation:
                anomalies.append("aucune fédération CNOSF reconnue : catégorie à saisir")
            operation = {"cle": f"o:{o['cle']}", "type": "nouveau", "nom": o["nom"], "comite_id": None,
                         "nouveau": apres, "changements": {k: ("", v) for k, v in apres.items() if v}}

        categorie = categorie_du_comite(apres, index)
        if o.get("categorie_excel") and categorie and int(o["categorie_excel"]) != categorie:
            anomalies.append(f"catégorie {o['categorie_excel']} dans l'Excel, {categorie} selon le CNOSF "
                             f"({apres.get('federation')})")
        if o.get("voix_excel") not in (None, ""):
            voix = voix_du_comite(categorie, apres.get("licencies"), bareme)
            if int(o["voix_excel"]) != voix:
                anomalies.append(f"{o['voix_excel']} voix dans l'Excel, {voix} selon le calcul de l'application")
        operation["anomalies"] = anomalies
        operations.append(operation)

    for c in comites:
        if c["id"] not in vus and c["_actif"]:
            operations.append({"cle": f"a:{c['id']}", "type": "absent", "nom": c.get("nom"), "comite_id": c["id"],
                               "changements": {"actif": ("oui", "non")}, "anomalies": []})
    ordre = {"nouveau": 0, "reactive": 1, "modifie": 2, "absent": 3, "identique": 4}
    return sorted(operations, key=lambda op: (ordre[op["type"]], op["nom"] or ""))


def appliquer(stockage, operations, selection, utilisateur, nom_fichier=""):
    """Écrit les opérations dont la clé est dans selection. Renvoie le nombre par type.

    L'onglet Comites est réécrit en une seule fois et le journal en un seul ajout,
    pour rester sous le quota d'écriture de l'API Google (60 par minute).
    """
    compte_rendu = {"nouveau": 0, "modifie": 0, "reactive": 0, "absent": 0}
    lignes = [l for l in stockage.lire("Comites") if l.get("id")]
    par_id = {l["id"]: l for l in lignes}
    quand = horodatage()
    journal = []
    for op in operations:
        if op["type"] == "identique" or op["cle"] not in selection:
            continue
        if op["type"] == "nouveau":
            ligne = dict(op["nouveau"])
            ligne["id"] = nouvel_identifiant(lignes)
            ligne["noms_import"] = op["nom"]
            ligne["maj_par"], ligne["maj_le"] = utilisateur, quand
            lignes.append(ligne)
            journal.append((ligne["id"], "création (import)", "", op["nom"]))
        else:
            ligne = par_id.get(op["comite_id"])
            if ligne is None:
                continue
            champs = {k: v[1] for k, v in op["changements"].items()}
            if "nom" in champs:
                connus = [n for n in (ligne.get("noms_import") or "").split("|") if n]
                for nom in (ligne.get("nom"), op["nom"]):
                    if nom and nom not in connus:
                        connus.append(nom)
                champs["noms_import"] = "|".join(connus)
            ligne.update(champs)
            ligne["maj_par"], ligne["maj_le"] = utilisateur, quand
            for champ, (ancienne, nouvelle) in op["changements"].items():
                journal.append((op["comite_id"], LIBELLES_CHAMPS.get(champ, champ) + " (import)", ancienne, nouvelle))
        compte_rendu[op["type"]] += 1
    if any(compte_rendu.values()):
        stockage.remplacer_tout("Comites", lignes)
    # la ligne « Excel adherents / import » marque le moment où l'application et le fichier concordent
    stockage.ajouter_lignes("Journal", [
        {"horodatage": quand, "utilisateur": utilisateur, "onglet": "Comites", "id": ident,
         "champ": champ, "ancienne": anc, "nouvelle": nouv}
        for ident, champ, anc, nouv in journal
    ] + [{"horodatage": quand, "utilisateur": utilisateur, "onglet": ONGLET_SYNCHRO, "id": "import",
          "champ": "fichier importé", "ancienne": "", "nouvelle": nom_fichier}])
    return compte_rendu
