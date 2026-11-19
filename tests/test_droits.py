"""Droits par rôle : onglets, modification des tâches, pages réservées au Chef de projet."""

import pytest

from metier.droits import onglets_visibles, peut_gerer_taches, peut_modifier_suivi
from metier.taches import lire_taches

ONGLETS_ATTENDUS = {
    "chef_projet": {"tableau_de_bord", "retroplanning", "communication", "rapport", "budget", "adherents",
                    "documents", "parametres", "comptes"},
    "communication": {"tableau_de_bord", "retroplanning", "communication", "documents"},
    "budget": {"tableau_de_bord", "retroplanning", "budget", "adherents", "documents"},
    "contribution": {"tableau_de_bord", "retroplanning", "rapport", "documents"},
    "lecture": {"tableau_de_bord", "retroplanning", "communication", "rapport", "budget", "adherents",
                "documents"},
}


@pytest.mark.parametrize("role", ONGLETS_ATTENDUS)
def test_onglets_par_role(role):
    assert {o[0] for o in onglets_visibles({"roles": role})} == ONGLETS_ATTENDUS[role]


def test_plusieurs_roles_cumulent_les_onglets():
    cles = {o[0] for o in onglets_visibles({"roles": "communication,budget"})}
    assert {"communication", "budget", "adherents"} <= cles
    assert "parametres" not in cles


def _tache(stockage, identifiant):
    return next(t for t in lire_taches(stockage) if t["id"] == identifiant)


def test_modification_du_suivi_selon_responsable_et_role(stockage):
    louis = {"nom": "Louis Test", "alias": "Louis", "roles": "budget"}
    pierre = {"nom": "Pierre Test", "alias": "Pierre", "roles": "lecture"}
    siham = {"nom": "Siham Test", "alias": "Siham", "roles": "communication"}
    contrib = {"nom": "Resp Pôle", "alias": "", "roles": "contribution", "pole": "Pôle 1"}
    assert peut_modifier_suivi(louis, _tache(stockage, "T007"))        # Budget, responsable
    assert peut_modifier_suivi(louis, _tache(stockage, "T040"))        # catégorie Budget, pas responsable
    assert not peut_modifier_suivi(louis, _tache(stockage, "T005"))    # Communication
    assert peut_modifier_suivi(pierre, _tache(stockage, "T004"))       # Lecture mais responsable
    assert not peut_modifier_suivi(pierre, _tache(stockage, "T002"))
    assert peut_modifier_suivi(siham, _tache(stockage, "T013"))
    assert peut_modifier_suivi(contrib, _tache(stockage, "T016"))      # « Responsables de pôle »
    assert not peut_modifier_suivi(contrib, _tache(stockage, "T002"))


def test_seul_le_chef_gere_les_taches():
    assert peut_gerer_taches({"roles": "chef_projet"})
    for role in ("communication", "budget", "contribution", "lecture"):
        assert not peut_gerer_taches({"roles": role})


@pytest.mark.parametrize("qui,url,code", [
    ("lecture", "/parametres/", 403),
    ("lecture", "/comptes/", 403),
    ("contrib", "/budget", 403),
    ("contrib", "/adherents/", 403),
    ("contrib", "/communication", 403),
    ("contrib", "/rapport", 200),
    ("com", "/communication", 200),
    ("com", "/budget", 403),
    ("budget", "/adherents/", 200),
    ("budget", "/rapport", 403),
    ("chef", "/parametres/", 200),
    ("chef", "/comptes/", 200),
    ("lecture", "/retroplanning/nouvelle", 403),
])
def test_acces_aux_pages(connexion, qui, url, code):
    assert connexion(qui).get(url).status_code == code


def test_lecture_ne_peut_pas_modifier_une_tache_dont_il_n_est_pas_responsable(connexion, stockage):
    client = connexion("lecture")
    reponse = client.post("/retroplanning/T002", data={"statut": "Fait", "avancement": "100"})
    assert reponse.status_code == 403
    assert _tache(stockage, "T002")["statut"] == "À faire"


def test_responsable_ne_peut_pas_redater(connexion, stockage):
    client = connexion("budget")
    client.post("/retroplanning/T007", data={"statut": "En cours", "avancement": "20",
                                             "date_cible": "2027-06-01", "action": "piratage"})
    t = _tache(stockage, "T007")
    assert t["statut"] == "En cours"
    assert t["date_cible"] == "2026-12-31"  # champ réservé au Chef de projet ignoré
    assert t["action"].startswith("Confirmer")


def test_non_chef_ne_peut_pas_supprimer(connexion, stockage):
    assert connexion("com").post("/retroplanning/T005/supprimer").status_code == 403
    assert len(lire_taches(stockage)) == 46
