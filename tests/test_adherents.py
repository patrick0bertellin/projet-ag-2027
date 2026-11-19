"""Adhérents : référentiel CNOSF, lecture de l'Excel, import avec aperçu, export, écrans."""

import io

import openpyxl
import pytest

from metier.adherents import FICHIER_CNOSF, lire_comites, rapprocher_federation
from metier.excel_adherents import FichierInvalide, exporter_adherents, lire_adherents, lire_cnosf
from metier.import_adherents import appliquer, calculer_operations
from metier.projet import BAREME_PAR_DEFAUT

FEDERATIONS = lire_cnosf(FICHIER_CNOSF)


def classeur(adhesion, voix=None, coordonnees=None, ordre_voix=None):
    """Classeur au format du fichier du CDOS : (nom, règlement, montant, clubs, licences, féminines, élu)."""
    wb = openpyxl.Workbook()
    a = wb.active
    a.title = "Adhésion"
    a.append(["ORGANISME \nmise à jour du 28/08/2026", "Mode de règlement", "Montant", "Nombre de Clubs",
              "Nombre de licences", "Nombre de féminines", "Elu du Comité"])
    for ligne in adhesion:
        a.append(list(ligne))
    a.append(["Total", 3, 450, 10, 1000, 100])
    v = wb.create_sheet("Voix")
    v.append(["ORGANISME", "Nombre de licences", "Catégorie", "1 voix", "+1", "+2", "+3", "+5", "Total voix des membres"])
    noms = ordre_voix or [l[0] for l in adhesion]
    for nom in noms:
        cat, total = (voix or {}).get(nom, (None, None))
        v.append([nom, None, cat, 1, None, None, None, None, total])
    v.append(["Totaux", 1000])
    c = wb.create_sheet("Coordonnées")
    c.append(["ORGANISME", "Adhérent 2026", "Nom prénom du président", "Mail Président"])
    for nom in noms:
        president, mail = (coordonnees or {}).get(nom, ("", ""))
        c.append([nom, "OUI", president, mail])
    wb.create_sheet("tec").append(["Virement"])
    sortie = io.BytesIO()
    wb.save(sortie)
    sortie.seek(0)
    return sortie


ADHESION = [
    ("AVIRON", "Virement", 150, 7, 1419, 582, "Karine"),
    ("BASKET BALL", "HelloAsso", 150, 57, 13240, 3344, None),
    ("TENNIS", "Virement", 150, 155, 46040, "61&!", None),
    ("MEDAILLES (CODYM)", None, None, None, None, None, None),
]
VOIX = {"AVIRON": (1, 7), "BASKET BALL": (1, 9), "TENNIS": (2, 4), "MEDAILLES (CODYM)": (1, 2)}
COORD = {"AVIRON": ("DUPONT Anne", "\xa0Anne.Dupont@exemple.fr "), "TENNIS": ("MARTIN Luc", "luc@exemple")}


@pytest.fixture
def stockage_cnosf(stockage):
    stockage.remplacer_tout("Federations", FEDERATIONS)
    return stockage


def _importer(stockage, fichier, choix=None, selection=None):
    lecture = lire_adherents(fichier)
    operations = calculer_operations(lecture, lire_comites(stockage), FEDERATIONS, BAREME_PAR_DEFAUT, choix)
    if selection is None:
        selection = {op["cle"] for op in operations}
    appliquer(stockage, operations, selection, "Test")
    return operations


# ------------------------------------------------------------------ référentiel
def test_referentiel_cnosf():
    assert len(FEDERATIONS) == 111
    assert {f["categorie"] for f in FEDERATIONS} == {"1", "2", "3", "4", "5"}


@pytest.mark.parametrize("nom,discipline", [
    ("AVIRON", "Aviron"), ("BASEBALL", "Baseball et Softball"), ("BASKET BALL", "Basketball"),
    ("COURSE ORIENTATION", "Course d'Orientation"), ("CLUBS OMNISPORTS (FFCO)", "Clubs Omnisports"),
    ("CYCLOTOURISME", "Cyclotourisme"), ("EQUITATION", "Equitation"), ("FOOTBALL", "Football"),
    ("GOLF", "Golf"), ("GYMNASTIQUE (CDY)", "Gymnastique"),
    ("GYMNASTIQUE VOLONTAIRE (CODEP EPGV)", "Sport Vitalité"), ("JUDO / KENDO", "Judo, Jujitsu, Kendo et D.A."),
    ("MEDAILLES (CODYM)", "Médaillés Jeunesse, Sports et Engagement associatif"),
    ("MONTAGNE ESCALADE", "Montagne et Escalade"), ("RUGBY", "Rugby"),
    ("SAVATE BOXE FRANCAISE", "Savate, Boxe française et D.A."), ("SPORT MILLIEU RURAL", "Sport en Milieu Rural"),
    ("SPORTS SOUS MARINS", "Etudes et Sports Sous-Marins"), ("TENNIS", "Tennis"),
    ("TENNIS DE TABLE", "Tennis de Table"), ("TIR A L'ARC", "Tir à l'Arc"), ("TWIRLING BATON", "Twirling Bâton"),
    ("UNSS", "UNSS"), ("USEP", "USEP"), ("VOILE", "Voile"),
])
def test_rapprochement_des_25_comites_du_cdos(nom, discipline):
    assert rapprocher_federation(nom, FEDERATIONS)["discipline"] == discipline


def test_pas_de_rapprochement_hasardeux():
    assert rapprocher_federation("COMITE INCONNU XYZ", FEDERATIONS) is None


# ------------------------------------------------------------------ lecture
def test_lecture_par_nom_et_nettoyage():
    fichier = classeur(ADHESION, VOIX, COORD, ordre_voix=["TENNIS", "AVIRON", "MEDAILLES (CODYM)", "BASKET BALL"])
    lecture = lire_adherents(fichier)
    par_nom = {o["nom"]: o for o in lecture["organismes"]}
    assert list(par_nom) == ["AVIRON", "BASKET BALL", "TENNIS", "MEDAILLES (CODYM)"]  # Total ignoré
    assert par_nom["AVIRON"]["valeurs"]["mail_president"] == "anne.dupont@exemple.fr"
    assert par_nom["TENNIS"]["categorie_excel"] == 2  # lu par le nom malgré l'ordre différent
    assert any("féminines" in a or "feminines" in a for a in par_nom["TENNIS"]["anomalies"])
    assert "feminines" not in par_nom["TENNIS"]["valeurs"]
    assert any("mail" in a for a in par_nom["TENNIS"]["anomalies"])
    assert par_nom["MEDAILLES (CODYM)"]["valeurs"]["mode_reglement"] == ""
    assert not lecture["anomalies"]  # « Totaux » de l'onglet Voix ignoré


def test_lecture_organisme_absent_d_un_onglet():
    lecture = lire_adherents(classeur(ADHESION, VOIX, COORD, ordre_voix=["AVIRON", "TENNIS", "MEDAILLES (CODYM)"]))
    basket = next(o for o in lecture["organismes"] if o["nom"] == "BASKET BALL")
    assert "absent de l'onglet Voix" in basket["anomalies"]


def test_fichier_sans_onglet_adhesion():
    wb = openpyxl.Workbook()
    wb.active.title = "Autre"
    sortie = io.BytesIO()
    wb.save(sortie)
    sortie.seek(0)
    with pytest.raises(FichierInvalide, match="Adhésion"):
        lire_adherents(sortie)


def test_fichier_non_excel():
    with pytest.raises(FichierInvalide):
        lire_adherents(io.BytesIO(b"pas un classeur"))


# ------------------------------------------------------------------ import
def test_premier_import(stockage_cnosf):
    operations = _importer(stockage_cnosf, classeur(ADHESION, VOIX, COORD))
    assert [op["type"] for op in operations] == ["nouveau"] * 4
    tennis = next(op for op in operations if op["nom"] == "TENNIS")
    assert any("catégorie 2 dans l'Excel, 1 selon le CNOSF" in a for a in tennis["anomalies"])
    assert any("4 voix dans l'Excel, 9 selon le calcul" in a for a in tennis["anomalies"])
    comites = {c["nom"]: c for c in lire_comites(stockage_cnosf)}
    assert comites["AVIRON"]["id"] == "C01" and comites["AVIRON"]["_voix"] == 7
    assert comites["TENNIS"]["_categorie"] == 1 and comites["TENNIS"]["_voix"] == 9
    assert not comites["MEDAILLES (CODYM)"]["_a_jour"]
    journal = [l for l in stockage_cnosf.lire("Journal") if l["onglet"] == "Comites"]
    assert len(journal) == 4


def test_reimport_modifications_absents_et_reactivation(stockage_cnosf):
    _importer(stockage_cnosf, classeur(ADHESION, VOIX, COORD))
    stockage_cnosf.mettre_a_jour("Comites", "id", "C01", {"inscrit": "oui", "representant": "A. Dupont"})
    modifie = [
        ("AVIRON", "Virement", 150, 7, 2500, 600, "Karine"),          # licences changées
        ("BASKET BALL", "HelloAsso", 150, 57, 13240, 3344, None),     # identique
        ("MEDAILLES (CODYM)", "Chèque", 150, None, None, None, None),  # a payé
    ]                                                                 # TENNIS absent
    operations = _importer(stockage_cnosf, classeur(modifie, VOIX, COORD))
    types = {op["nom"]: op["type"] for op in operations}
    assert types == {"AVIRON": "modifie", "BASKET BALL": "identique", "MEDAILLES (CODYM)": "modifie",
                     "TENNIS": "absent"}
    comites = {c["nom"]: c for c in lire_comites(stockage_cnosf)}
    assert comites["AVIRON"]["licencies"] == "2500" and comites["AVIRON"]["_voix"] == 8
    assert comites["AVIRON"]["inscrit"] == "oui" and comites["AVIRON"]["representant"] == "A. Dupont"
    assert comites["MEDAILLES (CODYM)"]["_a_jour"]
    assert not comites["TENNIS"]["_actif"]
    operations = _importer(stockage_cnosf, classeur(ADHESION, VOIX, COORD))
    assert next(op for op in operations if op["nom"] == "TENNIS")["type"] == "reactive"
    assert {c["nom"]: c for c in lire_comites(stockage_cnosf)}["TENNIS"]["_actif"]


def test_import_partiel_seulement_les_lignes_cochees(stockage_cnosf):
    _importer(stockage_cnosf, classeur(ADHESION, VOIX, COORD), selection={"o:aviron"})
    assert [c["nom"] for c in lire_comites(stockage_cnosf)] == ["AVIRON"]


def test_renommage_memorise(stockage_cnosf):
    _importer(stockage_cnosf, classeur(ADHESION, VOIX, COORD))
    renomme = [("BASKETBALL YVELINES",) + ADHESION[1][1:]] + [ADHESION[0], ADHESION[2], ADHESION[3]]
    fichier = classeur(renomme, VOIX, COORD)
    lecture = lire_adherents(fichier)
    sans_choix = calculer_operations(lecture, lire_comites(stockage_cnosf), FEDERATIONS, BAREME_PAR_DEFAUT)
    assert {op["nom"]: op["type"] for op in sans_choix}["BASKETBALL YVELINES"] == "nouveau"
    _importer(stockage_cnosf, classeur(renomme, VOIX, COORD), choix={"basketball yvelines": "C02"})
    basket = next(c for c in lire_comites(stockage_cnosf) if c["id"] == "C02")
    assert basket["nom"] == "BASKETBALL YVELINES"
    assert "BASKET BALL" in basket["noms_import"]
    # au prochain import, l'ancien nom comme le nouveau sont reconnus
    operations = _importer(stockage_cnosf, classeur(ADHESION, VOIX, COORD))
    assert {op["nom"]: op["type"] for op in operations}["BASKET BALL"] == "modifie"


# ------------------------------------------------------------------ export
def test_export_puis_reimport_sans_difference(stockage_cnosf):
    _importer(stockage_cnosf, classeur(ADHESION, VOIX, COORD))
    contenu = exporter_adherents(lire_comites(stockage_cnosf), 2026)
    wb = openpyxl.load_workbook(io.BytesIO(contenu))
    assert wb.sheetnames[:4] == ["Adhésion", "Voix", "Coordonnées", "tec"]
    voix = wb["Voix"]
    assert voix["E2"].value == "=IF(AND(B2>=1,B2<=2000),1,0)"
    assert voix["F2"].value == "=IF(AND(B2>2000,B2<=10000),2,0)"
    assert "MATCH($A2,Adhésion!$A:$A,0)" in voix["B2"].value
    assert voix["C2"].value == 1  # catégorie CNOSF
    lecture = lire_adherents(io.BytesIO(contenu))
    operations = calculer_operations(lecture, lire_comites(stockage_cnosf), FEDERATIONS, BAREME_PAR_DEFAUT)
    assert {op["type"] for op in operations} == {"identique"}


# ------------------------------------------------------------------ écrans
def test_acces_adherents_par_role(connexion):
    assert connexion("lecture").get("/adherents/").status_code == 200
    assert connexion("lecture").get("/adherents/import").status_code == 403
    assert connexion("lecture").post("/adherents/nouveau", data={"nom": "X"}).status_code == 403
    assert connexion("budget").get("/adherents/import").status_code == 200
    assert connexion("contrib").get("/adherents/").status_code == 403
    assert connexion("com").get("/adherents/").status_code == 403


def test_parcours_import_par_les_ecrans(connexion, stockage_cnosf):
    client = connexion("budget")
    reponse = client.post("/adherents/import", data={"fichier": (classeur(ADHESION, VOIX, COORD), "membres.xlsx")},
                          content_type="multipart/form-data")
    assert reponse.status_code == 302 and "/adherents/import/" in reponse.headers["Location"]
    apercu = client.get(reponse.headers["Location"])
    page = apercu.get_data(as_text=True)
    assert "4 organismes lus" in page and "selon le CNOSF" in page
    assert lire_comites(stockage_cnosf) == []  # rien d'écrit avant validation
    client.post(reponse.headers["Location"], data={
        "action": "appliquer", "operations": ["o:aviron", "o:basket ball", "o:tennis", "o:medailles codym"]})
    assert len(lire_comites(stockage_cnosf)) == 4
    page = client.get("/adherents/").get_data(as_text=True)
    assert "Total des voix" in page and "en attente" in page
    # 7 (aviron) + 9 (basket) + 9 (tennis) ; CODYM en attente
    assert '<div class="tuile-valeur">25</div>' in page
    assert client.get(reponse.headers["Location"]).status_code == 302  # import déjà appliqué


def test_import_fichier_invalide_message(connexion):
    reponse = connexion("chef").post("/adherents/import", data={"fichier": (io.BytesIO(b"x"), "a.txt")},
                                     content_type="multipart/form-data")
    assert "format .xlsx" in reponse.get_data(as_text=True)


def test_fiche_comite_erreur_garde_la_saisie_puis_enregistre(connexion, stockage_cnosf):
    _importer(stockage_cnosf, classeur(ADHESION, VOIX, COORD))
    client = connexion("chef")
    code = next(c["id"] for c in lire_comites(stockage_cnosf) if c["nom"] == "TENNIS")
    donnees = {"nom": "TENNIS", "federation": "Tennis", "licencies": "12 000x", "mode_reglement": "Virement",
               "president": "MARTIN Luc", "actif": "oui"}
    page = client.post(f"/adherents/{code}", data=donnees).get_data(as_text=True)
    assert "nombre entier" in page and 'value="12 000x"' in page
    donnees["licencies"] = "12 000"
    client.post(f"/adherents/{code}", data=donnees)
    tennis = next(c for c in lire_comites(stockage_cnosf) if c["id"] == code)
    assert tennis["licencies"] == "12000" and tennis["montant"] == "150"


def test_ajout_manuel_sans_federation_exige_une_categorie(connexion, stockage_cnosf):
    client = connexion("chef")
    page = client.post("/adherents/nouveau", data={"nom": "NOUVEAU COMITE", "actif": "oui"}).get_data(as_text=True)
    assert "choisir la catégorie" in page
    client.post("/adherents/nouveau", data={"nom": "NOUVEAU COMITE", "categorie": "3", "licencies": "500",
                                            "mode_reglement": "Chèque", "actif": "oui"})
    nouveau = lire_comites(stockage_cnosf)[0]
    assert nouveau["id"] == "C01" and nouveau["_categorie"] == 3 and nouveau["_voix"] == 2


def test_export_par_les_ecrans(connexion, stockage_cnosf):
    _importer(stockage_cnosf, classeur(ADHESION, VOIX, COORD))
    reponse = connexion("lecture").get("/adherents/export")
    assert reponse.status_code == 200
    assert "spreadsheetml" in reponse.headers["Content-Type"]
    assert openpyxl.load_workbook(io.BytesIO(reponse.data))["Adhésion"]["A2"].value == "AVIRON"


def test_referentiel_affiche(connexion, stockage_cnosf):
    page = connexion("lecture").get("/adherents/referentiel").get_data(as_text=True)
    assert "111 fédérations" in page and "Fédérations olympiques" in page


def _jeton(reponse):
    return reponse.get_data(as_text=True).split('name="jeton_csrf" value="')[1].split('"')[0]


def test_parcours_import_avec_controle_du_jeton_actif(stockage_cnosf):
    """Comme dans l'application réelle : chaque formulaire doit porter le jeton de la session."""
    from app import create_app
    from tests.conftest import MDP

    client = create_app({"TESTING": True, "SECRET_KEY": "t"}, stockage=stockage_cnosf).test_client()
    jeton = _jeton(client.get("/connexion"))
    client.post("/connexion", data={"identifiant": "louis", "mot_de_passe": MDP, "jeton_csrf": jeton})
    jeton = _jeton(client.get("/adherents/import"))
    reponse = client.post("/adherents/import", content_type="multipart/form-data", data={
        "jeton_csrf": jeton, "fichier": (classeur(ADHESION, VOIX, COORD), "membres.xlsx")})
    assert reponse.status_code == 302
    apercu = client.get(reponse.headers["Location"])
    jeton = _jeton(apercu)
    reponse = client.post(reponse.headers["Location"], data={
        "jeton_csrf": jeton, "action": "appliquer",
        "operations": ["o:aviron", "o:basket ball", "o:tennis", "o:medailles codym"]})
    assert reponse.status_code == 302, reponse.get_data(as_text=True)[:300]
    assert len(lire_comites(stockage_cnosf)) == 4


# ------------------------------------------------------------------ mise en forme du fichier d'origine
def test_export_garde_la_mise_en_forme_du_fichier_cdos(stockage_cnosf):
    _importer(stockage_cnosf, classeur(ADHESION, VOIX, COORD))
    wb = openpyxl.load_workbook(io.BytesIO(exporter_adherents(lire_comites(stockage_cnosf), 2026)))
    assert wb.properties.title == "Adhésions membres du CDOS-78"  # propriétés « Synthèse »
    assert wb.sheetnames == ["Adhésion", "Voix", "Coordonnées", "tec"]
    adh, voix, coord = wb["Adhésion"], wb["Voix"], wb["Coordonnées"]
    # 4 comités : données lignes 2 à 5, totaux ligne 6
    assert adh["A6"].value == "Total" and adh["E6"].value == "=SUM(E2:E5)"
    assert adh.auto_filter.ref == "A1:H7" and adh.print_area == "'Adhésion'!$A$1:$G$6"
    assert adh.oddHeader.center.text == "Membres du CDOS-78\nAdhésions" and adh.oddFooter.right.text == "&F"
    assert adh.sheet_properties.tabColor.rgb == "FF00B050" and adh.sheet_view.zoomScale == 120
    assert adh["C2"].number_format == '#,##0\\ "€"' and adh["A1"].font.b
    assert [(str(d.sqref), d.formula1) for d in adh.data_validations.dataValidation] == [("B2:B5", "tec!$A$1:$A$4")]
    assert voix.freeze_panes == "A2" and voix["A2"].font.sz == 9 and voix["A1"].value.startswith("ORGANISME")
    zones = {str(cf.sqref): [r.formula for r in cf.rules] for cf in voix.conditional_formatting}
    assert zones["I2:I5"] == [["(B2>0)"]]
    assert zones["I9"] == [['I9="NON"'], ['I9="OUI"']]  # « quorum atteint ? » : la règle #REF! est réparée
    assert voix["I8"].value == "=ROUNDUP(I6/2,0)" and voix["I9"].value == '=IF(K6>=I8,"OUI","NON")'
    assert voix["I11"].value == "=ROUNDUP(K6*2/3,0)"
    assert "B2:B5" in {str(cf.sqref) for cf in coord.conditional_formatting}
    assert coord["B1"].value == "Adhérent 2026"


def test_modele_sans_aucune_donnee_personnelle(stockage_cnosf):
    from metier.modele_excel import MODELE_PAR_DEFAUT, nettoyer_modele

    _importer(stockage_cnosf, classeur(ADHESION, VOIX, COORD))
    export = exporter_adherents(lire_comites(stockage_cnosf), 2026)
    for contenu in (MODELE_PAR_DEFAUT.read_bytes(), nettoyer_modele(io.BytesIO(export))):
        wb = openpyxl.load_workbook(io.BytesIO(contenu))
        textes = " ".join(str(c.value) for ws in wb.worksheets for row in ws.iter_rows(min_row=2) for c in row
                          if c.value is not None)
        assert "@" not in textes and "DUPONT" not in textes and "AVIRON" not in textes


def test_modele_refuse_si_colonnes_deplacees():
    from metier.modele_excel import nettoyer_modele

    # le classeur de test n'a pas la colonne « Adhérent » attendue en B de Coordonnées… si on la déplace
    wb = openpyxl.load_workbook(classeur(ADHESION, VOIX, COORD))
    wb["Adhésion"]["B1"] = "Montant"
    sortie = io.BytesIO()
    wb.save(sortie)
    assert nettoyer_modele(io.BytesIO(sortie.getvalue())) is None


def test_import_peut_devenir_le_modele_des_exports(connexion, stockage_cnosf):
    from metier.modele_excel import lire_modele

    wb = openpyxl.load_workbook(classeur(ADHESION, VOIX, COORD))
    wb["Adhésion"].sheet_properties.tabColor = "FF123456"
    fichier = io.BytesIO()
    wb.save(fichier)
    fichier.seek(0)
    client = connexion("chef")
    reponse = client.post("/adherents/import", data={"fichier": (fichier, "membres.xlsx")},
                          content_type="multipart/form-data")
    assert "Reprendre la mise en forme" in client.get(reponse.headers["Location"]).get_data(as_text=True)
    client.post(reponse.headers["Location"], data={"action": "appliquer", "garder_modele": "oui",
                                                    "operations": ["o:aviron", "o:tennis"]})
    assert lire_modele(stockage_cnosf)[1] == "membres.xlsx"
    export = client.get("/adherents/export").data
    assert openpyxl.load_workbook(io.BytesIO(export))["Adhésion"].sheet_properties.tabColor.rgb == "FF123456"


# ------------------------------------------------------------------ alerte de mise à jour
def test_alerte_apres_mise_a_jour_jusqu_a_l_export(connexion, stockage_cnosf):
    client = connexion("chef")
    reponse = client.post("/adherents/import", data={"fichier": (classeur(ADHESION, VOIX, COORD), "m.xlsx")},
                          content_type="multipart/form-data")
    client.post(reponse.headers["Location"], data={
        "action": "appliquer", "operations": ["o:aviron", "o:basket ball", "o:tennis", "o:medailles codym"]})
    page = client.get("/adherents/").get_data(as_text=True)
    assert "depuis le dernier" not in page  # juste après l'import, application et fichier concordent
    assert "Cliquer sur le nom d'un organisme pour ouvrir sa fiche et le mettre à jour" in page
    assert "Seuls les comités à jour de leur cotisation" not in page  # ancien rappel retiré

    code = next(c["id"] for c in lire_comites(stockage_cnosf) if c["nom"] == "TENNIS")
    page = client.post(f"/adherents/{code}", follow_redirects=True, data={
        "nom": "TENNIS", "federation": "Tennis", "licencies": "47000", "mode_reglement": "Virement",
        "montant": "150", "clubs": "155", "president": "MARTIN Luc", "mail_president": "luc@exemple.fr",
        "actif": "oui"}).get_data(as_text=True)
    assert "« TENNIS » mis à jour : licences, mail." in page and "pensez à l&#39;exporter" in page
    assert "1 comité(s) mis à jour dans l'application depuis le dernier" in page
    assert "Un import remplacera ces valeurs" in client.get("/adherents/import").get_data(as_text=True)

    client.get("/adherents/export")
    assert "depuis le dernier" not in client.get("/adherents/").get_data(as_text=True)


def test_export_colore_la_categorie_comme_le_fichier_importe(stockage_cnosf):
    from metier.modele_excel import MODELE_PAR_DEFAUT

    modele = openpyxl.load_workbook(MODELE_PAR_DEFAUT)["Voix"]
    attendu = {}
    for ligne in range(2, 27):
        attendu.setdefault(modele.cell(row=ligne, column=3).value, modele.cell(row=ligne, column=3).fill.fgColor)
    _importer(stockage_cnosf, classeur(ADHESION, VOIX, COORD))
    voix = openpyxl.load_workbook(io.BytesIO(exporter_adherents(lire_comites(stockage_cnosf), 2026)))["Voix"]
    couleurs = {}
    for ligne in range(2, 6):
        cellule = voix.cell(row=ligne, column=3)
        couleurs[cellule.value] = cellule.fill.fgColor
        assert (cellule.fill.fgColor.theme, cellule.fill.fgColor.tint) == \
               (attendu[cellule.value].theme, attendu[cellule.value].tint)
    assert couleurs[1].theme != couleurs[5].theme  # une couleur par catégorie (CODYM en 5)


# ------------------------------------------------------------------ visiteur
def test_visiteur_consulte_les_adherents_sans_contacts(client, stockage_cnosf):
    _importer(stockage_cnosf, classeur(ADHESION, VOIX, COORD))
    client.post("/connexion", data={"action": "visiteur"})
    page = client.get("/adherents/").get_data(as_text=True)
    assert "Consultation seule : la liste des comités membres est tenue à jour" in page
    assert "Comprendre cette page" in page and "Cliquer sur le nom" not in page
    assert "AVIRON" in page and "Cliquer sur une ligne pour afficher le président" in page
    # contacts présents mais masqués : affichés au clic sur la ligne
    assert 'data-details="details-' in page and 'class="details-contacts"' in page and "DUPONT Anne" in page
    assert "hidden>" in page.split("DUPONT Anne")[0].rsplit("<tr", 1)[1]
    assert "/adherents/C0" not in page and "Exporter l'Excel" not in page  # ni fiche ni export
    code = lire_comites(stockage_cnosf)[0]["id"]
    assert client.get(f"/adherents/{code}").status_code == 302
    assert client.post(f"/adherents/{code}", data={"nom": "X"}).status_code == 403
    assert client.post("/adherents/presence", data={"presents": [code]}).status_code == 403
    assert "Sondage de participation" not in page


# ------------------------------------------------------------------ sondage et présence
def sondage(lignes):
    wb = openpyxl.Workbook()
    f = wb.active
    f.append(["https://www.helloasso.com/x", "ORGANISME", "Nom ", "Prénom", "Adresse Mail Président",
              "En tant que Président, je serai :", "Nom de mon Représentant", "Prénom de mon Représentant",
              "Adresse mail de mon Représentant", "Fonction de mon Représentant dans l'organisme"])
    for ligne in lignes:
        f.append(list(ligne) + [None] * (10 - len(ligne)))
    sortie = io.BytesIO()
    wb.save(sortie)
    sortie.seek(0)
    return sortie


REPONSES = [
    ("2026-03-13 20:54:07", "Comité Départemental Aviron", "DUPONT", "Anne", "anne@exemple.fr",
     "Présent et je représenterai mon organisme"),
    ("2026-02-27 16:09:31", "Comité Départemental Tennis", "MARTIN", "Luc", "luc@exemple.fr",
     "Absent et je désigne un Représentant", "REIGNER", "Jean", "jean@exemple.fr", "Trésorier"),
    ("2026-03-17 14:08:23", "Comité Départemental Médaillés De La Jeunesse (CODYM)", "L", "S", "s@exemple.fr",
     "Absent et je ne désigne pas de Représentant"),
    ("2026-03-20 14:31:42", "Comité Départemental Volley-Ball", "M", "Y", "y@exemple.fr",
     "Présent et je représenterai mon organisme"),
]


def test_lecture_et_rapprochement_du_sondage(stockage_cnosf):
    from metier.sondage import completer_avec_sondage, lire_fichier

    _importer(stockage_cnosf, classeur(ADHESION, VOIX, COORD))
    reponses = lire_fichier(sondage(REPONSES))
    assert reponses[1]["rep_nom"] == "REIGNER" and reponses[1]["rep_fonction"] == "Trésorier"
    assert reponses[0]["nom"] == "DUPONT" and reponses[0]["prenom"] == "Anne"
    comites = lire_comites(stockage_cnosf)
    non_rapprochees = completer_avec_sondage(comites, reponses)
    par_nom = {c["nom"]: c for c in comites}
    assert par_nom["AVIRON"]["_reponse"]["_type"] == "present" and par_nom["AVIRON"]["_inscrit"]
    assert par_nom["TENNIS"]["_reponse"]["_type"] == "represente" and par_nom["TENNIS"]["_inscrit"]
    assert par_nom["MEDAILLES (CODYM)"]["_reponse"]["_type"] == "absent"  # par le sigle
    assert not par_nom["MEDAILLES (CODYM)"]["_inscrit"]
    assert "_reponse" not in par_nom["BASKET BALL"]  # « Volley-Ball » ne doit pas tomber sur le basket
    assert [r["organisme"] for r in non_rapprochees] == ["Comité Départemental Volley-Ball"]


def test_suivi_sondage_et_presence_reserve_au_chef(connexion, stockage_cnosf):
    _importer(stockage_cnosf, classeur(ADHESION, VOIX, COORD))
    client = connexion("budget")
    assert "Sondage de participation" not in client.get("/adherents/").get_data(as_text=True)
    assert client.post("/adherents/presence", data={}).status_code == 403
    assert client.post("/adherents/sondage", data={"fichier": (sondage(REPONSES), "s.xlsx")},
                       content_type="multipart/form-data").status_code == 403

    client = connexion("chef")
    client.post("/adherents/sondage", data={"fichier": (sondage(REPONSES), "s.xlsx")},
                content_type="multipart/form-data")
    page = client.get("/adherents/").get_data(as_text=True)
    assert "Sondage de participation et présence" in page and "REIGNER" in page and "Trésorier" in page
    assert "1 réponse(s) non rattachée(s)" in page
    # rattachement manuel, conservé après un nouvel import
    basket = next(c["id"] for c in lire_comites(stockage_cnosf) if c["nom"] == "BASKET BALL")
    client.post("/adherents/sondage/rapprocher", data={"cle": "2026-03-20 14:31:42|comite departemental volley ball",
                                                       "comite_id": basket})
    client.post("/adherents/sondage", data={"fichier": (sondage(REPONSES), "s.xlsx")},
                content_type="multipart/form-data")
    assert "non rattachée" not in client.get("/adherents/").get_data(as_text=True)
    # jour de l'AG : présences
    aviron = next(c["id"] for c in lire_comites(stockage_cnosf) if c["nom"] == "AVIRON")
    client.post("/adherents/presence", data={"presents": [aviron, basket]})
    presents = {c["nom"] for c in lire_comites(stockage_cnosf) if c["_present"]}
    assert presents == {"AVIRON", "BASKET BALL"}
    page = client.get("/adherents/").get_data(as_text=True)
    assert "Voix présentes (comités à jour) : <strong>16</strong>" in page  # 7 + 9
