"""Règles de gestion : dates, butoirs, avancement, voix, quorum, cohérence, import."""

import json
from datetime import date

from metier.dates import ajouter_mois, date_fr
from metier.droits import noms_responsables
from metier.import_json import CHEMIN_PAR_DEFAUT
from metier.projet import BAREME_PAR_DEFAUT, butoir, butoirs, lire_projet
from metier.quorum import seuil_approbation, seuil_quorum, synthese, voix_du_comite
from metier.taches import (
    avancement_global, avancement_par, controles_coherence, en_retard, lire_taches, preparer, prochaines,
)


# ------------------------------------------------------------------ dates
def test_date_fr():
    assert date_fr(date(2027, 2, 15)) == "lundi 15 février 2027"
    assert date_fr("2027-03-20") == "samedi 20 mars 2027"
    assert date_fr("2027-04-01") == "jeudi 1er avril 2027"
    assert date_fr("") == ""


def test_ajouter_mois_fin_de_mois():
    assert ajouter_mois(date(2027, 1, 31), 1) == date(2027, 2, 28)
    assert ajouter_mois(date(2027, 11, 15), 3) == date(2028, 2, 15)


# ------------------------------------------------------------------ butoirs
def test_butoirs_ag_2027(stockage):
    projet = lire_projet(stockage)
    assert projet["date_ag"] == "2027-03-20"
    assert butoir(projet, "convocation") == date(2027, 2, 18)
    assert butoir(projet, "seconde_ag") == date(2027, 4, 10)
    assert butoir(projet, "cnosf") == date(2027, 5, 4)
    assert butoir(projet, "prefecture") == date(2027, 6, 20)


def test_butoirs_recalcules_si_la_date_change():
    projet = {"date_ag": "2028-03-25", "delai_convocation_jours": "30", "delai_seconde_ag_jours": "21",
              "ecart_cnosf_jours": "45", "delai_prefecture_mois": "3"}
    dates = {b["cle"]: b["date"] for b in butoirs(projet)}
    assert dates["convocation"] == date(2028, 2, 24)
    assert dates["seconde_ag"] == date(2028, 4, 15)
    assert dates["prefecture"] == date(2028, 6, 25)


def test_butoirs_delai_parametrable():
    projet = {"date_ag": "2027-03-20", "delai_convocation_jours": "40"}
    assert butoir(projet, "convocation") == date(2027, 2, 8)


# ------------------------------------------------------------------ import
def test_import_46_taches_conformes_au_json(stockage):
    source = {t["id"]: t for t in json.loads(CHEMIN_PAR_DEFAUT.read_text(encoding="utf-8"))["taches"]}
    taches = lire_taches(stockage)
    assert len(taches) == 46
    for t in taches:
        attendu = source[t["id"]]
        assert t["phase"] == attendu["phase"]
        assert t["date_cible"] == attendu["date_cible"]
        assert t["responsables"] == attendu["responsables"]
        assert t["_approx"] == attendu["date_approx"]


def test_import_taches_conditionnelles(stockage):
    conditionnelles = {t["id"] for t in lire_taches(stockage) if t["_conditionnelle"]}
    assert conditionnelles == {"T037", "T038"}


def test_reimport_conserve_le_suivi(stockage):
    from metier.import_json import importer

    stockage.mettre_a_jour("Taches", "id", "T002", {"statut": "En cours", "avancement": "40", "commentaire": "ok"})
    importer(stockage, conserver_suivi=True)
    t = next(t for t in lire_taches(stockage) if t["id"] == "T002")
    assert (t["statut"], t["avancement"], t["commentaire"]) == ("En cours", "40", "ok")
    importer(stockage, conserver_suivi=False)
    t = next(t for t in lire_taches(stockage) if t["id"] == "T002")
    assert t["statut"] == "À faire"


def test_reimport_ne_touche_pas_la_date_ag_sans_reinitialisation(stockage):
    from metier.import_json import importer

    stockage.mettre_a_jour("Projet", "cle", "date_ag", {"valeur": "2027-03-27"})
    importer(stockage)
    assert lire_projet(stockage)["date_ag"] == "2027-03-27"
    importer(stockage, reinitialiser_parametres=True)
    assert lire_projet(stockage)["date_ag"] == "2027-03-20"


# ------------------------------------------------------------------ avancement
def _t(**champs):
    base = {"id": "T", "statut": "À faire", "avancement": "0", "poids": "1", "conditionnelle": "non",
            "responsables": "Patrick", "date_cible": "2027-01-05", "date_approx": "non"}
    base.update(champs)
    return preparer(base)


def test_avancement_pondere():
    taches = [_t(avancement="100", poids="3"), _t(avancement="0", poids="1")]
    assert avancement_global(taches) == 75


def test_avancement_fait_vaut_100_et_exclusions():
    taches = [
        _t(statut="Fait", avancement="0"),
        _t(avancement="0"),
        _t(statut="Sans objet", avancement="0"),
        _t(conditionnelle="oui", avancement="0"),
    ]
    assert avancement_global(taches) == 50


def test_avancement_initial_v05(stockage):
    taches = lire_taches(stockage)
    # 1 tâche faite sur 44 comptées (46 moins les 2 conditionnelles)
    assert avancement_global(taches) == round(100 / 44)
    phases = avancement_par(taches, "phase", [])
    assert any(p["sans_calcul"] for p in phases)  # phase 5 entièrement conditionnelle


def test_retards_et_prochaines_echeances():
    ref = date(2027, 1, 10)
    taches = [
        _t(id="A", date_cible="2027-01-05"),
        _t(id="B", date_cible="2027-01-05", statut="Fait"),
        _t(id="C", date_cible="2027-01-20"),
        _t(id="D", date_cible="2027-02-20"),
        _t(id="E", date_cible="2027-01-05", conditionnelle="oui"),
    ]
    assert [t["id"] for t in en_retard(taches, ref)] == ["A"]
    assert [t["id"] for t in prochaines(taches, ref, 14)] == ["C"]


# ------------------------------------------------------------------ voix et quorum
def test_voix_du_comite_bornes_du_bareme():
    bareme = BAREME_PAR_DEFAUT
    assert voix_du_comite("3", 0, bareme) == 1          # aucun licencié : 1 voix de membre
    assert voix_du_comite("3", 1, bareme) == 2
    assert voix_du_comite("3", 2000, bareme) == 2       # « jusqu'à 2 000 »
    assert voix_du_comite("3", 2001, bareme) == 3
    assert voix_du_comite("3", 10000, bareme) == 3      # « de 2 001 à 10 000 »
    assert voix_du_comite("3", 10001, bareme) == 4
    assert voix_du_comite("1", 1419, bareme) == 7       # aviron
    assert voix_du_comite("1", 46040, bareme) == 9      # tennis
    assert voix_du_comite(5, 57807, bareme) == 4        # clubs omnisports


def test_seuil_quorum_moitie_des_voix():
    assert seuil_quorum(204) == 102  # AG 2026
    assert seuil_quorum(146) == 73
    assert seuil_quorum(147) == 74


def test_seuil_approbation_deux_tiers_des_exprimees():
    assert seuil_approbation(90, "2/3") == 60
    assert seuil_approbation(91, "2/3") == 61
    assert seuil_approbation(146, "2/3") == 98
    assert seuil_approbation(100, "1/2") == 50
    assert seuil_approbation(0) == 0


def test_synthese_quorum_compte_seulement_les_comites_a_jour_et_actifs():
    from metier.adherents import preparer_comite

    def comite(**champs):
        return preparer_comite(dict({"id": "C", "actif": "oui"}, **champs), {}, BAREME_PAR_DEFAUT)

    comites = [
        comite(categorie="1", licencies="0", mode_reglement="Virement", inscrit="oui"),   # 6
        comite(categorie="2", licencies="1500", mode_reglement="Chèque", inscrit="non"),  # 2
        comite(categorie="2", licencies="1500", mode_reglement="", inscrit="oui"),        # en attente
        comite(categorie="2", licencies="1500", mode_reglement="-"),                      # en attente
        comite(categorie="1", licencies="5000", mode_reglement="Virement", actif="non"),  # désactivé
    ]
    s = synthese(comites)
    assert s["total_voix"] == 8
    assert s["seuil"] == 4
    assert s["voix_inscrites"] == 6
    assert s["marge"] == 2
    assert s["nb_en_attente"] == 2 and s["voix_en_attente"] == 4
    assert s["atteint"]


# ------------------------------------------------------------------ responsables et cohérence
def test_noms_responsables():
    assert noms_responsables("Pierre (Patrick)") == ["Pierre", "Patrick"]
    assert noms_responsables("BE (à programmer)") == ["BE"]
    assert noms_responsables("Siham, Marion Lebel, Responsables de pôle") == [
        "Siham", "Marion Lebel", "Responsables de pôle"]


def test_coherence_v05_signale_le_dimanche_28_fevrier(stockage):
    alertes = controles_coherence(lire_taches(stockage), lire_projet(stockage))
    messages = {(a["id"], a["message"].split(" (")[0]) for a in alertes}
    assert ("T025", "échéance un dimanche") in messages
    # les dates approximatives (fin de mois) ne déclenchent pas l'alerte du dimanche
    assert not any(a["id"] == "T012" for a in alertes)
    # la convocation (T021, 15 février) est avant le butoir du 18 février
    assert not any(a["niveau"] == "grave" for a in alertes)


def test_coherence_convocation_apres_butoir_et_dependance():
    projet = {"date_ag": "2027-03-20", "tache_convocation": "T2"}
    taches = [
        _t(id="T1", date_cible="2027-02-10"),
        _t(id="T2", date_cible="2027-02-19", depend_de="T3"),
        _t(id="T3", date_cible="2027-02-25"),
        _t(id="T4", responsables="", date_cible="2027-02-11"),
    ]
    alertes = controles_coherence(taches, projet)
    textes = " | ".join(f"{a['id']} {a['message']}" for a in alertes)
    assert "T2 convocation prévue" in textes
    assert "avant la tâche dont elle dépend" in textes
    assert "T4 tâche sans responsable" in textes


def test_coherence_ca_moins_de_10_jours():
    projet = {"date_ag": "2027-03-20", "date_ca": "2027-02-02", "tache_convocation_ca": "T1"}
    taches = [_t(id="T1", date_cible="2027-01-26")]
    assert any("moins de 10 jours" in a["message"] for a in controles_coherence(taches, projet))


# ------------------------------------------------------------------ rapport d'activité : reprise 2025
def test_reprise_du_rapport_2025_sans_doublon(stockage):
    from metier.rapport import charger_reprise, etat_par_pole, lire_reprise

    reprise = lire_reprise()
    assert len({e["id"] for e in reprise["engagements"]}) == len(reprise["engagements"])
    assert any("Chevreuse" in e["engagement"] and e["pole"] == "Pôle 1" for e in reprise["engagements"])
    ajouts = charger_reprise(stockage)
    assert ajouts["Engagements"] == len(reprise["engagements"]) and ajouts["Contributions"] == 8
    assert charger_reprise(stockage) == {"Engagements": 0, "Indicateurs": 0, "Contributions": 0}
    pole1 = next(p for p in etat_par_pole(stockage) if p["pole"] == "Pôle 1")
    assert pole1["responsable"] == "Thierry GREGORI" and pole1["engagements"] == 7
    assert pole1["engagements_bilantes"] == 0 and pole1["statut"] == "Non commencée"


def test_actions_non_prevues_comptees_a_part(stockage):
    from metier.rapport import charger_reprise, etat_par_pole

    charger_reprise(stockage)
    stockage.ajouter_lignes("Engagements", [{"id": "E900", "pole": "Pôle 1", "engagement": "Atelier imprévu",
                                             "etat": "Réalisé", "prevu": "non"}])
    pole1 = next(p for p in etat_par_pole(stockage) if p["pole"] == "Pôle 1")
    assert pole1["engagements"] == 7 and pole1["non_prevues"] == 1
