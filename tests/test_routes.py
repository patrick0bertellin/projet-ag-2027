"""Parcours dans l'application : connexion, tableau de bord, rétroplanning, paramètres, comptes."""

from metier.comptes import creer, trouver_par_identifiant
from metier.projet import lire_projet
from metier.taches import lire_taches
from tests.conftest import MDP


def texte(reponse):
    return reponse.get_data(as_text=True)


def test_redirection_vers_connexion(client):
    reponse = client.get("/")
    assert reponse.status_code == 302
    assert "/connexion" in reponse.headers["Location"]


def test_connexion_refusee_garde_l_identifiant(client):
    reponse = client.post("/connexion", data={"identifiant": "patrick", "mot_de_passe": "faux"})
    assert reponse.status_code == 200
    assert "incorrect" in texte(reponse)
    assert 'value="patrick"' in texte(reponse)


def test_identifiant_sans_majuscules_ni_espaces(client):
    reponse = client.post("/connexion", data={"identifiant": "  PATRICK ", "mot_de_passe": MDP})
    assert reponse.status_code == 302


def test_compte_desactive_refuse(client, stockage):
    stockage.mettre_a_jour("Comptes", "id", trouver_par_identifiant(stockage, "pierre")["id"], {"actif": "non"})
    client.post("/connexion", data={"identifiant": "pierre", "mot_de_passe": MDP})
    assert client.get("/").status_code == 302


def test_changement_de_mot_de_passe_obligatoire(client, stockage):
    creer(stockage, "nouveau", "Nouveau", ["lecture"], "initial-123")
    client.post("/connexion", data={"identifiant": "nouveau", "mot_de_passe": "initial-123"})
    reponse = client.get("/retroplanning/")
    assert reponse.status_code == 302 and "/mot-de-passe" in reponse.headers["Location"]
    reponse = client.post("/mot-de-passe", data={"actuel": "initial-123", "nouveau": "court", "confirmation": "court"})
    assert "au moins 8" in texte(reponse)
    client.post("/mot-de-passe", data={"actuel": "initial-123", "nouveau": "personnel-456",
                                       "confirmation": "personnel-456"})
    assert client.get("/retroplanning/").status_code == 200
    assert trouver_par_identifiant(stockage, "nouveau")["doit_changer_mdp"] == "non"


def test_bandeau_et_onglets(connexion):
    page = texte(connexion("contrib").get("/"))
    assert "Projet AG 2027" in page and "Resp Pôle" in page and "Se déconnecter" in page
    assert "Rapport d&#39;activité" in page or "Rapport d'activité" in page
    nav = page.split('<nav class="onglets">')[1].split("</nav>")[0]
    assert "Rapport d" in nav and "Documents" in nav
    assert ">Budget<" not in nav and ">Paramètres<" not in nav and ">Adhérents<" not in nav


def test_tableau_de_bord(connexion):
    page = texte(connexion("chef").get("/"))
    assert "Butoir de la convocation" in page
    assert "jeudi 18 février 2027" in page
    assert "Avancement par phase" in page
    assert "Questions à trancher (5)" in page
    assert "Mes tâches" not in page  # pas pour le Chef de projet


def test_tableau_de_bord_mes_taches(connexion):
    page = texte(connexion("budget").get("/"))
    assert "Mes tâches" in page
    assert "Clôture de l&#39;exercice 2026" in page or "Clôture de l'exercice 2026" in page


def test_retroplanning_liste_et_filtres(connexion):
    client = connexion("lecture")
    page = texte(client.get("/retroplanning/"))
    assert "46 tâche(s) sur 46" in page
    assert "Phase 6 – Après l&#39;AG" in page or "Phase 6 – Après l'AG" in page
    assert "échéance un dimanche" in page
    page = texte(client.get("/retroplanning/?categorie=Budget"))
    assert "9 tâche(s) sur 46" in page
    page = texte(client.get("/retroplanning/?responsable=Louis&statut=À faire"))
    assert "9 tâche(s) sur 46" in page
    page = texte(client.get("/retroplanning/?q=commissaire"))
    assert "T018" in page and "T002" not in page


def test_gantt(connexion):
    page = texte(connexion("lecture").get("/retroplanning/gantt"))
    assert "Frise des jalons" in page and "T035" in page and 'class="repere ag"' in page


def test_mise_a_jour_du_suivi_et_journal(connexion, stockage):
    client = connexion("chef")
    client.post("/retroplanning/T003", data={"statut": "Fait", "avancement": "30", "commentaire": "lancé",
                                             "phase": "Phase 1 – Cadrage", "categorie": "Rapport d'activité",
                                             "action": "Lancer la production des rapports de l'AG",
                                             "date_cible": "2026-11-23", "echeance_texte": "Lundi 23 novembre 2026",
                                             "responsables": "Patrick", "base": "Art. 8", "poids": "1"})
    t = next(t for t in lire_taches(stockage) if t["id"] == "T003")
    assert t["statut"] == "Fait" and t["avancement"] == "100" and t["maj_par"] == "Patrick Test"
    journal = [l for l in stockage.lire("Journal") if l["id"] == "T003"]
    champs = {l["champ"]: (l["ancienne"], l["nouvelle"]) for l in journal}
    assert champs["statut"] == ("À faire", "Fait")
    assert champs["commentaire"] == ("", "lancé")
    assert all(l["utilisateur"] == "Patrick Test" for l in journal)


def test_erreur_de_saisie_reaffiche_les_valeurs(connexion, stockage):
    client = connexion("budget")
    reponse = client.post("/retroplanning/T007", data={"statut": "En cours", "avancement": "150",
                                                       "commentaire": "à garder"})
    assert reponse.status_code == 200
    page = texte(reponse)
    assert "entre 0 et 100" in page and "à garder" in page and 'value="150"' in page
    assert next(t for t in lire_taches(stockage) if t["id"] == "T007")["statut"] == "À faire"


def test_chef_cree_et_supprime_une_tache(connexion, stockage):
    client = connexion("chef")
    client.post("/retroplanning/nouvelle", data={
        "action": "Réserver le traiteur", "phase": "Phase 2 – Clôture et préparation", "categorie": "Logistique",
        "date_cible": "2027-02-01", "responsables": "Alexis", "statut": "À faire", "avancement": "0"})
    taches = lire_taches(stockage)
    assert len(taches) == 47
    nouvelle = next(t for t in taches if t["action"] == "Réserver le traiteur")
    assert nouvelle["id"] == "T047"
    assert nouvelle["echeance_texte"] == "Lundi 1er février 2027"
    client.post("/retroplanning/T047/supprimer")
    assert len(lire_taches(stockage)) == 46


def test_parametres_date_ag_recalcule_les_butoirs(connexion, stockage):
    client = connexion("chef")
    donnees = dict(lire_projet(stockage))
    donnees["date_ag"] = "2027-03-27"
    client.post("/parametres/projet", data=donnees)
    assert lire_projet(stockage)["date_ag"] == "2027-03-27"
    page = texte(client.get("/"))
    assert "jeudi 25 février 2027" in page  # nouveau butoir J-30


def test_parametres_erreur_garde_la_saisie(connexion, stockage):
    client = connexion("chef")
    donnees = dict(lire_projet(stockage), date_ag="", lieu="Versailles")
    reponse = client.post("/parametres/projet", data=donnees)
    assert "La date de l&#39;AG est obligatoire" in texte(reponse) or "La date de l'AG est obligatoire" in texte(reponse)
    assert 'value="Versailles"' in texte(reponse)
    assert lire_projet(stockage)["lieu"] == "Le Port-Marly"


def test_parametres_listes_et_bareme(connexion, stockage):
    from metier.projet import lire_bareme, lire_listes

    client = connexion("chef")
    client.post("/parametres/listes", data={
        "phases": "\n".join(lire_listes(stockage)["phases"]),
        "categories": "\n".join(lire_listes(stockage)["categories"]),
        "poles": "Sport santé\nHaut niveau\nCommunication",
        "canaux": "Mail nominatif"})
    assert lire_listes(stockage)["poles"] == ["Sport santé", "Haut niveau", "Communication"]
    client.post("/parametres/bareme", data={"voix_base": "1", "voix_bonus_categorie_1": "5",
                                            "seuils": "500;1\n2000;2\n8000;3"})
    assert lire_bareme(stockage)["seuils"] == [(500, 1), (2000, 2), (8000, 3)]
    assert lire_listes(stockage)["poles"] == ["Sport santé", "Haut niveau", "Communication"]


def test_reimport_depuis_parametres(connexion, stockage):
    client = connexion("chef")
    reponse = client.post("/parametres/import", data={"conserver_suivi": "1"})
    assert "confirmation" in texte(reponse)
    client.post("/parametres/import", data={"conserver_suivi": "1", "confirmation": "oui"})
    assert len(lire_taches(stockage)) == 46


def test_comptes_creation_et_modification(connexion, stockage):
    client = connexion("chef")
    reponse = client.post("/comptes/nouveau", data={"identifiant": "Patrick", "nom": "Marion Lebel",
                                                     "roles": ["communication"], "mot_de_passe": "provisoire1"})
    assert "déjà utilisé" in texte(reponse) and 'value="Marion Lebel"' in texte(reponse)
    client.post("/comptes/nouveau", data={"identifiant": "marion", "nom": "Marion Lebel", "alias": "Marion Lebel",
                                          "roles": ["communication"], "mot_de_passe": "provisoire1", "actif": "oui"})
    marion = trouver_par_identifiant(stockage, "marion")
    assert marion["roles"] == "communication" and marion["doit_changer_mdp"] == "oui"
    assert marion["mdp_hash"] and "provisoire1" not in marion["mdp_hash"]
    client.post(f"/comptes/{marion['id']}", data={"identifiant": "marion", "nom": "Marion Lebel",
                                                   "alias": "Marion Lebel", "roles": ["communication"]})
    assert trouver_par_identifiant(stockage, "marion")["actif"] == "non"


def test_contribution_exige_un_pole(connexion):
    reponse = connexion("chef").post("/comptes/nouveau", data={
        "identifiant": "x", "nom": "X", "roles": ["contribution"], "mot_de_passe": "provisoire1"})
    assert "rattaché à un pôle" in texte(reponse)


def test_chef_ne_peut_pas_se_desactiver(connexion, stockage):
    client = connexion("chef")
    moi = trouver_par_identifiant(stockage, "patrick")
    reponse = client.post(f"/comptes/{moi['id']}", data={"identifiant": "patrick", "nom": moi["nom"],
                                                         "roles": ["chef_projet"]})
    assert "désactiver votre propre compte" in texte(reponse)


def test_onglet_manquant_ne_provoque_pas_d_erreur(stockage, connexion):
    del stockage.donnees["Budget"]
    del stockage.donnees["Comites"]
    reponse = connexion("chef").get("/")
    assert reponse.status_code == 200
    assert "Onglets absents du Google Sheet : Budget, Comites" in texte(reponse)


def test_csrf_actif_par_defaut(stockage):
    from app import create_app

    app = create_app({"TESTING": True, "SECRET_KEY": "t"}, stockage=stockage)
    client = app.test_client()
    assert client.post("/connexion", data={"identifiant": "patrick", "mot_de_passe": MDP}).status_code == 400
    page = client.get("/connexion").get_data(as_text=True)
    jeton = page.split('name="jeton_csrf" value="')[1].split('"')[0]
    reponse = client.post("/connexion", data={"identifiant": "patrick", "mot_de_passe": MDP, "jeton_csrf": jeton})
    assert reponse.status_code == 302


def test_redirection_externe_refusee(client):
    reponse = client.post("/connexion?suite=//exemple.com", data={"identifiant": "patrick", "mot_de_passe": MDP})
    assert reponse.headers["Location"] == "/"


def test_tableau_de_bord_rapide(connexion, stockage):
    import time

    client = connexion("chef")
    debut = time.time()
    client.get("/")
    assert time.time() - debut < 3


# ------------------------------------------------------------------ visiteur sans identifiant
def test_page_de_connexion_explique_les_identifiants(client):
    page = client.get("/connexion").get_data(as_text=True)
    assert "communiqués par l'administrateur" in page and "Consulter sans identifiant" in page


def test_visiteur_sans_identifiant_consulte_seulement(client, stockage):
    reponse = client.post("/connexion", data={"identifiant": "", "mot_de_passe": ""})
    assert reponse.status_code == 302 and reponse.headers["Location"].endswith("/")
    assert client.get("/").status_code == 200
    assert client.get("/retroplanning/").status_code == 200
    tache = stockage.lire("Taches")[0]
    page = client.get(f"/retroplanning/{tache['id']}").get_data(as_text=True)
    assert "consultation seule" in page and 'name="statut"' not in page
    # aucune modification possible
    assert client.post(f"/retroplanning/{tache['id']}", data={"statut": "Fait"}).status_code == 403
    assert stockage.lire("Taches")[0].get("statut") == tache.get("statut")
    # les autres pages renvoient vers la connexion
    for chemin in ("/parametres/", "/comptes/", "/mot-de-passe", "/a-venir/documents", "/adherents/export",
                   "/adherents/import"):
        assert client.get(chemin).status_code == 302, chemin
    bandeau = client.get("/").get_data(as_text=True)
    assert "Visiteur (consultation)" in bandeau and "Déconnexion" in bandeau and "Paramètres" not in bandeau


def test_visiteur_par_le_bouton_puis_vraie_connexion(client):
    from tests.conftest import connecter

    client.post("/connexion", data={"action": "visiteur", "identifiant": "x"})
    assert "Visiteur (consultation)" in client.get("/").get_data(as_text=True)
    connecter(client, "chef")
    page = client.get("/").get_data(as_text=True)
    assert "Visiteur (consultation)" not in page and "Paramètres" in page


def test_mot_de_passe_sans_identifiant_refuse(client):
    page = client.post("/connexion", data={"identifiant": "", "mot_de_passe": "abc"}).get_data(as_text=True)
    assert "Saisir votre identifiant" in page


def test_aide_adaptee_au_visiteur(client):
    client.post("/connexion", data={"action": "visiteur"})
    page = client.get("/aide").get_data(as_text=True)
    assert "Consultation sans identifiant" in page and "Cliquer sur une ligne" in page
    assert "Chef de projet</strong> : tout" not in page
    assert page.count("Retour au tableau de bord") == 2


def test_aide_des_comptes_connectes(connexion):
    page = connexion("chef").get("/aide").get_data(as_text=True)
    assert "Visiteur</strong> (sans identifiant)" in page and "Sondage de participation" in page
    assert "Sondage de participation" not in connexion("lecture").get("/aide").get_data(as_text=True)
