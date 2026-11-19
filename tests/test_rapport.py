"""Rapport d'activité : fiches de contribution par pôle, droits, statuts, export Word."""

import io

import docx
import pytest

from metier.rapport import charger_reprise, lire_vue


@pytest.fixture
def reprise(stockage):
    charger_reprise(stockage)
    return stockage


def _formulaire(stockage, pole, **champs):
    """Formulaire tel que l'envoie la page : valeurs actuelles, puis les champs donnés."""
    vue = lire_vue(stockage, pole)
    data = {k: vue["fiche"].get(k, "") for k in ("commission", "presentation", "bilan", "perspectives")}
    for l in vue["engagements"]:
        data[f"etat_{l['id']}"], data[f"commentaire_{l['id']}"] = l.get("etat", ""), l.get("commentaire", "")
    for n, l in enumerate(vue["non_prevues"]):
        data.update({f"np_id_{n}": l["id"], f"np_texte_{n}": l["engagement"], f"np_etat_{n}": l["etat"],
                     f"np_commentaire_{n}": l.get("commentaire", "")})
    for l in vue["indicateurs"]:
        data[f"valeur_{l['id']}"], data[f"source_{l['id']}"] = l.get("valeur_annee", ""), l.get("source", "")
        if l["id"].startswith("A"):
            data[f"nom_{l['id']}"] = l["indicateur"]
    data.update(champs)
    return data


def test_reprise_complete_les_fiches(reprise):
    fiche = lire_vue(reprise, "Pôle 1")["fiche"]
    assert fiche["titre"].startswith("PÔLE 1") and "GREGORI" in fiche["commission"] and fiche["presentation"]
    assert charger_reprise(reprise) == {"Engagements": 0, "Indicateurs": 0, "Contributions": 0}


def test_contribution_ne_voit_que_son_pole(reprise, connexion):
    c = connexion("contrib")
    page = c.get("/rapport").get_data(as_text=True)
    assert "PÔLE 1" in page and "PÔLE 2" not in page and "Exporter" not in page
    assert c.get("/rapport/fiche/Pôle 1").status_code == 200
    assert c.get("/rapport/fiche/Pôle 2").status_code == 403
    assert c.get("/rapport/export").status_code == 403


def test_saisie_brouillon_non_prevues_et_indicateurs(reprise, connexion):
    c = connexion("contrib")
    premier = lire_vue(reprise, "Pôle 1")["engagements"][0]["id"]
    r = c.post("/rapport/fiche/Pôle 1", data=_formulaire(
        reprise, "Pôle 1", **{f"etat_{premier}": "Réalisé", "bilan": "Une belle année",
                             "np_texte_0": "Journée sport-santé", "np_etat_0": "En cours",
                             "ni_nom_0": "Nouveaux sites", "ni_valeur_0": "2", "action": "enregistrer"}))
    assert r.status_code == 302
    vue = lire_vue(reprise, "Pôle 1")
    assert vue["fiche"]["statut"] == "Brouillon" and vue["fiche"]["bilan"] == "Une belle année"
    assert vue["engagements"][0]["etat"] == "Réalisé"
    assert [(l["id"], l["prevu"]) for l in vue["non_prevues"]] == [("N001", "non")]
    assert vue["indicateurs"][-1]["id"] == "A001" and vue["indicateurs"][-1]["valeur_annee"] == "2"
    assert any(l["onglet"] == "Contributions" and l["id"] == "Pôle 1" for l in reprise.lire("Journal"))
    # vider la description supprime l'action non prévue ; vider le nom supprime l'indicateur ajouté
    c.post("/rapport/fiche/Pôle 1", data=_formulaire(reprise, "Pôle 1", np_texte_0="", np_etat_0="",
                                                    nom_A001="", action="enregistrer"))
    vue = lire_vue(reprise, "Pôle 1")
    assert vue["non_prevues"] == [] and not any(l["id"] == "A001" for l in vue["indicateurs"])


def test_erreur_reaffiche_les_valeurs_saisies(reprise, connexion):
    c = connexion("contrib")
    r = c.post("/rapport/fiche/Pôle 1", data=_formulaire(reprise, "Pôle 1", bilan="Texte à garder",
                                                         np_texte_0="Action sans état", action="enregistrer"))
    page = r.get_data(as_text=True)
    assert r.status_code == 200 and "préciser son état" in page
    assert "Texte à garder" in page and "Action sans état" in page
    assert lire_vue(reprise, "Pôle 1")["fiche"]["bilan"] == ""


def test_soumission_puis_validation_ou_renvoi(reprise, client):
    from tests.conftest import connecter

    connecter(client, "contrib")
    client.post("/rapport/fiche/Pôle 1", data=_formulaire(reprise, "Pôle 1", action="soumettre"))
    assert lire_vue(reprise, "Pôle 1")["fiche"]["statut"] == "Soumise"
    # soumise : le pôle ne peut plus modifier
    r = client.post("/rapport/fiche/Pôle 1", data=_formulaire(reprise, "Pôle 1", bilan="x", action="enregistrer"))
    assert r.status_code == 403
    client.get("/deconnexion")
    connecter(client, "chef")
    r = client.post("/rapport/fiche/Pôle 1", data=_formulaire(reprise, "Pôle 1", action="renvoyer"))
    assert "Indiquer au responsable" in r.get_data(as_text=True)
    client.post("/rapport/fiche/Pôle 1", data=_formulaire(reprise, "Pôle 1", action="renvoyer",
                                                          commentaire_validation="Compléter les chiffres"))
    fiche = lire_vue(reprise, "Pôle 1")["fiche"]
    assert fiche["statut"] == "Brouillon" and fiche["commentaire_validation"] == "Compléter les chiffres"
    client.post("/rapport/fiche/Pôle 1", data=_formulaire(reprise, "Pôle 1", action="soumettre"))
    client.post("/rapport/fiche/Pôle 1", data=_formulaire(reprise, "Pôle 1", action="valider"))
    fiche = lire_vue(reprise, "Pôle 1")["fiche"]
    assert fiche["statut"] == "Validée" and fiche["valide_par"] == "Patrick Test"


def test_lecture_consulte_sans_modifier(reprise, connexion):
    c = connexion("lecture")
    page = c.get("/rapport/fiche/Pôle 2").get_data(as_text=True)
    assert "Consultation seule" in page and "Soumettre" not in page
    assert c.post("/rapport/fiche/Pôle 2", data={"action": "enregistrer"}).status_code == 403


def test_export_word_du_rapport_compile(reprise, connexion):
    c = connexion("chef")
    c.post("/rapport/fiche/Pôle 1", data=_formulaire(reprise, "Pôle 1", bilan="Une belle année",
                                                     perspectives="Atelier à Rambouillet\nAtelier à Poissy"))
    r = c.get("/rapport/export")
    assert r.status_code == 200 and "wordprocessingml" in r.mimetype
    d = docx.Document(io.BytesIO(r.data))
    textes = [p.text for p in d.paragraphs]
    assert "RAPPORT D'ACTIVITÉ 2026 — PERSPECTIVES 2027" in textes
    assert "INTRODUCTION" in textes and "PÔLE 1 — SPORT SANTÉ & BIEN-ÊTRE" in textes
    assert "PERSPECTIVES GÉNÉRALES 2027" in textes
    assert "Atelier à Rambouillet" in textes and "[à compléter]" in textes
    perspectives = next(p for p in d.paragraphs if p.text == "Atelier à Poissy")
    assert perspectives.style.name == "liste pat"
    assert any("Prescri'forme" in t.cell(1, 0).text for t in d.tables)
