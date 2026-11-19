"""Lecture et écriture des fichiers Excel : adhérents (Adhésion, Voix, Coordonnées, tec)
et référentiel des fédérations du CNOSF.

Les onglets sont lus par leur nom et les colonnes par leur en-tête ; les lignes des
trois onglets sont rapprochées par le nom de l'organisme, jamais par leur position.
"""

import io
import re
from copy import copy
from datetime import date, datetime, timezone

import openpyxl
from openpyxl.formatting.formatting import ConditionalFormattingList
from openpyxl.worksheet.datavalidation import DataValidation

from metier.adherents import (
    MODES_REGLEMENT, mail_valide, nettoyer_mail, nettoyer_texte, normaliser_nom,
)
from metier.modele_excel import MODELE_PAR_DEFAUT, ligne_total, onglet, styles_categories


class FichierInvalide(Exception):
    """Le fichier ne peut pas être lu (format, onglet ou colonne manquant)."""


# Colonnes reconnues : champ -> mots à trouver dans l'en-tête normalisé
COLONNES_ADHESION = {
    "nom": ["organisme"],
    "mode_reglement": ["reglement"],
    "montant": ["montant"],
    "clubs": ["clubs"],
    "licencies": ["licences", "licencies"],
    "feminines": ["feminines"],
    "elu_referent": ["elu"],
    "federation": ["federation cnosf"],
}
COLONNES_VOIX = {"nom": ["organisme"], "categorie_excel": ["categorie"], "voix_excel": ["total voix"]}
COLONNES_COORDONNEES = {"nom": ["organisme"], "mail_president": ["mail"], "president": ["president"]}
OBLIGATOIRES = {"Adhésion": ["nom", "mode_reglement", "licencies"], "Voix": ["nom"], "Coordonnées": ["nom"]}
CHAMPS_NUMERIQUES = {"licencies", "clubs", "feminines", "montant"}


def _ouvrir(fichier):
    try:
        return openpyxl.load_workbook(fichier, data_only=True, read_only=False)
    except Exception as exc:
        raise FichierInvalide(f"Le fichier n'est pas un classeur Excel lisible (.xlsx) : {exc}") from exc


def _onglet(classeur, nom):
    for feuille in classeur.worksheets:
        if normaliser_nom(feuille.title) == normaliser_nom(nom):
            return feuille
    return None


def _reperer_colonnes(entetes, colonnes):
    """{champ: index} ; un champ prend la première colonne dont l'en-tête contient un des mots."""
    trouves, pris = {}, set()
    # « mail » avant « president » : l'en-tête « Mail Président » contient les deux
    for champ in sorted(colonnes, key=lambda c: c != "mail_president"):
        for i, entete in enumerate(entetes):
            texte = normaliser_nom(entete)
            if i not in pris and any(m in texte for m in colonnes[champ]):
                trouves[champ] = i
                pris.add(i)
                break
    return trouves


def _lignes(feuille, colonnes):
    lignes = list(feuille.iter_rows(values_only=True))
    for num, ligne in enumerate(lignes[:10]):
        if any("organisme" in normaliser_nom(c) for c in ligne if c is not None):
            index = _reperer_colonnes(ligne, colonnes)
            resultat = []
            for brute in lignes[num + 1:]:
                nom = nettoyer_texte(brute[index["nom"]] if index["nom"] < len(brute) else "")
                if not nom or normaliser_nom(nom).split(" ")[0] in ("total", "totaux"):
                    continue
                resultat.append({champ: (brute[i] if i < len(brute) else None) for champ, i in index.items()})
            return index, resultat
    raise FichierInvalide(f"Onglet « {feuille.title} » : ligne d'en-tête « ORGANISME » introuvable.")


def _nombre(valeur):
    """(valeur, anomalie) : entier, vide, ou None si illisible."""
    if valeur is None or str(valeur).strip() in ("", "-"):
        return "", None
    if isinstance(valeur, bool):
        return None, f"valeur illisible « {valeur} »"
    if isinstance(valeur, (int, float)):
        return int(round(valeur)), None
    texte = str(valeur).replace("\xa0", "").replace(" ", "").replace(",", ".").replace("€", "")
    try:
        return int(round(float(texte))), None
    except ValueError:
        return None, f"valeur illisible « {valeur} »"


def lire_adherents(fichier):
    """Lit le classeur des adhérents.

    Renvoie {"organismes": [...], "anomalies": [...]} ; chaque organisme contient
    nom, valeurs (champs du comité), categorie_excel, voix_excel et anomalies.
    """
    classeur = _ouvrir(fichier)
    donnees, anomalies = {}, []
    for nom_onglet, colonnes in (("Adhésion", COLONNES_ADHESION), ("Voix", COLONNES_VOIX),
                                 ("Coordonnées", COLONNES_COORDONNEES)):
        feuille = _onglet(classeur, nom_onglet)
        if feuille is None:
            raise FichierInvalide(f"Onglet « {nom_onglet} » absent du fichier.")
        index, lignes = _lignes(feuille, colonnes)
        manquantes = [c for c in OBLIGATOIRES[nom_onglet] if c not in index]
        if manquantes:
            raise FichierInvalide(f"Onglet « {nom_onglet} » : colonne(s) introuvable(s) : {', '.join(manquantes)}.")
        donnees[nom_onglet] = {}
        for ligne in lignes:
            cle = normaliser_nom(ligne["nom"])
            if cle in donnees[nom_onglet]:
                anomalies.append(f"Onglet « {nom_onglet} » : « {nettoyer_texte(ligne['nom'])} » apparaît deux fois.")
            donnees[nom_onglet][cle] = ligne

    organismes = []
    for cle, ligne in donnees["Adhésion"].items():
        o = {"cle": cle, "nom": nettoyer_texte(ligne["nom"]), "valeurs": {}, "anomalies": [],
             "categorie_excel": None, "voix_excel": None}
        for champ in ("mode_reglement", "elu_referent", "federation"):
            if champ in ligne:
                o["valeurs"][champ] = nettoyer_texte(ligne[champ])
        if o["valeurs"].get("mode_reglement") == "-":
            o["valeurs"]["mode_reglement"] = ""
        for champ in ("licencies", "clubs", "feminines", "montant"):
            if champ in ligne:
                valeur, anomalie = _nombre(ligne[champ])
                if anomalie:
                    o["anomalies"].append(f"{champ} : {anomalie} (valeur ignorée)")
                else:
                    o["valeurs"][champ] = valeur
        voix = donnees["Voix"].get(cle)
        if voix is None:
            o["anomalies"].append("absent de l'onglet Voix")
        else:
            o["categorie_excel"] = _nombre(voix.get("categorie_excel"))[0] or None
            o["voix_excel"] = _nombre(voix.get("voix_excel"))[0]
        coord = donnees["Coordonnées"].get(cle)
        if coord is None:
            o["anomalies"].append("absent de l'onglet Coordonnées")
        else:
            o["valeurs"]["president"] = nettoyer_texte(coord.get("president"))
            mail = nettoyer_mail(coord.get("mail_president"))
            o["valeurs"]["mail_president"] = mail
            if mail and not mail_valide(mail):
                o["anomalies"].append(f"mail du président invalide « {mail} »")
        organismes.append(o)

    for nom_onglet in ("Voix", "Coordonnées"):
        for cle, ligne in donnees[nom_onglet].items():
            if cle not in donnees["Adhésion"]:
                anomalies.append(f"« {nettoyer_texte(ligne['nom'])} » est dans l'onglet {nom_onglet} "
                                 "mais pas dans l'onglet Adhésion : ignoré.")
    if not organismes:
        raise FichierInvalide("Aucun organisme trouvé dans l'onglet Adhésion.")
    return {"organismes": organismes, "anomalies": anomalies}


def lire_cnosf(fichier):
    """Lit le référentiel CNOSF : onglet « Disciplines », colonnes Catégorie, Libellé, Discipline, Fédération, Site."""
    classeur = _ouvrir(fichier)
    feuille = _onglet(classeur, "Disciplines") or classeur.worksheets[0]
    lignes = list(feuille.iter_rows(values_only=True))
    for num, ligne in enumerate(lignes[:15]):
        textes = [normaliser_nom(c) for c in ligne]
        if "categorie" in textes and "discipline" in textes:
            i = {nom: textes.index(nom) for nom in ("categorie", "discipline")}
            i["libelle"] = next((k for k, t in enumerate(textes) if t.startswith("libelle")), None)
            i["federation"] = next((k for k, t in enumerate(textes) if t.startswith("federation")), None)
            i["site"] = next((k for k, t in enumerate(textes) if "site" in t), None)
            federations = []
            for brute in lignes[num + 1:]:
                def val(cle):
                    k = i.get(cle)
                    return nettoyer_texte(brute[k]) if k is not None and k < len(brute) else ""
                categorie, discipline = val("categorie"), val("discipline")
                if not discipline or not categorie.isdigit():
                    continue
                federations.append({"categorie": categorie, "libelle_categorie": val("libelle"),
                                    "discipline": discipline, "federation": val("federation"),
                                    "site": val("site")})
            if not federations:
                raise FichierInvalide("Aucune fédération trouvée dans le référentiel.")
            return federations
    raise FichierInvalide("En-têtes « Catégorie » et « Discipline » introuvables dans le référentiel.")


# ------------------------------------------------------------------ export
# L'export remplit un modèle (fichier du CDOS vidé de ses données) : couleurs, polices,
# filtres, mises en forme conditionnelles, zones d'impression, en-têtes/pieds de page
# et propriétés du document sont ceux du fichier d'origine.

REFERENCE = re.compile(r"(?<![A-Za-z_\d.])((?:'[^']+'|[A-Za-zÀ-ÿ_][\wÀ-ÿ.]*)!)?(\$?)([A-Z]{1,3})(\$?)(\d+)(?![\d(\w])")


def _decaleur(total_modele, total_nouveau):
    """Fonction qui recalcule un numéro de ligne du modèle pour le nouveau nombre de lignes."""
    def ligne(r):
        if r >= total_modele:
            return r + total_nouveau - total_modele
        if r == total_modele - 1:
            return total_nouveau - 1
        if r >= 2:
            return min(r, total_nouveau - 1)
        return r

    def formule(texte):
        if not isinstance(texte, str):
            return texte

        def remplacer(m):
            feuille, d1, col, d2, num = m.groups()
            if feuille and normaliser_nom(feuille.strip("'!")) == "tec":
                return m.group(0)
            return f"{feuille or ''}{d1}{col}{d2}{ligne(int(num))}"

        # on ne touche pas au texte entre guillemets ("OUI", "x"…)
        morceaux = texte.split('"')
        return '"'.join(REFERENCE.sub(remplacer, m) if i % 2 == 0 else m for i, m in enumerate(morceaux))

    return ligne, formule


def _preparer_feuille(feuille, nb_lignes):
    """Mémorise les styles du modèle, vide la feuille et renvoie (styles, total, outils)."""
    total_modele = ligne_total(feuille)
    total = nb_lignes + 2
    largeur = max(feuille.max_column, 1)
    styles_donnees = [
        ([copy(feuille.cell(row=r, column=c)._style) for c in range(1, largeur + 1)],
         feuille.row_dimensions[r].height)
        for r in range(2, total_modele)
    ]
    bas = [
        ([(feuille.cell(row=r, column=c).value, copy(feuille.cell(row=r, column=c)._style))
          for c in range(1, largeur + 1)], feuille.row_dimensions[r].height)
        for r in range(total_modele, feuille.max_row + 1)
    ]
    ligne, formule = _decaleur(total_modele, total)
    regles = [(str(cf.sqref), cf.rules) for cf in feuille.conditional_formatting]
    filtre = feuille.auto_filter.ref
    impression = feuille.print_area
    hauteurs = {}
    feuille.delete_rows(2, feuille.max_row)
    for r in list(feuille.row_dimensions):
        if r >= 2:
            del feuille.row_dimensions[r]

    # lignes de données : styles du modèle, répétés si le modèle a moins de lignes
    for i in range(nb_lignes if styles_donnees else 0):
        styles, hauteur = styles_donnees[i % len(styles_donnees)]
        for c, style in enumerate(styles, start=1):
            feuille.cell(row=2 + i, column=c)._style = copy(style)
        hauteurs[2 + i] = hauteur
    # ligne des totaux et pied (quorum…) recopiés sous les données, formules décalées
    for decalage, (cellules, hauteur) in enumerate(bas):
        for c, (valeur, style) in enumerate(cellules, start=1):
            cellule = feuille.cell(row=total + decalage, column=c)
            cellule._style = copy(style)
            cellule.value = formule(valeur)
        hauteurs[total + decalage] = hauteur
    for r, hauteur in hauteurs.items():
        if hauteur:
            feuille.row_dimensions[r].height = hauteur

    # filtres, zone d'impression et mises en forme conditionnelles suivent les lignes
    def plage(texte):
        return " ".join(formule(p) for p in texte.split())

    if filtre:
        feuille.auto_filter.ref = plage(filtre)
    if impression:
        zones = [z.split("!")[-1] for z in impression.split(",")]
        feuille.print_area = ",".join(plage(z) for z in zones)
    feuille.conditional_formatting = ConditionalFormattingList()
    for zone, liste in regles:
        nouvelle_zone = plage(zone)
        for regle in liste:
            regle.formula = [formule(f) for f in regle.formula]
            feuille.conditional_formatting.add(nouvelle_zone, regle)
    return total, formule


def _ecrire(feuille, ligne, valeurs):
    for colonne, valeur in enumerate(valeurs, start=1):
        if valeur is not None:
            feuille.cell(row=ligne, column=colonne, value=valeur)


def exporter_adherents(comites, annee_adhesion, fraction="2/3", modele=None):
    """Classeur Excel (bytes) au format du fichier des adhérents (Adhésion, Voix, Coordonnées, tec).

    `modele` : contenu d'un classeur modèle (par défaut donnees/modele_adherents.xlsx).
    Les formules de l'onglet Voix retrouvent chaque organisme par son nom (INDEX/EQUIV),
    respectent les bornes du barème et ne comptent que les comités à jour.
    """
    num, den = fraction.split("/") if "/" in fraction else ("2", "3")
    actifs = [c for c in comites if c["_actif"]]
    classeur = openpyxl.load_workbook(io.BytesIO(modele) if modele else MODELE_PAR_DEFAUT)
    nb = max(len(actifs), 1)
    fin = nb + 1

    # --- Adhésion
    adh = onglet(classeur, "Adhésion")
    total, _ = _preparer_feuille(adh, nb)
    adh["A1"] = re.sub(r"\d{1,2}/\d{1,2}/\d{4}", date.today().strftime("%d/%m/%Y"), str(adh["A1"].value or "")) \
        or f"ORGANISME \nmise à jour du {date.today().strftime('%d/%m/%Y')}"
    if not adh["H1"].value:  # colonne ajoutée par l'application, au style de la colonne G
        adh["H1"]._style = copy(adh["G1"]._style)
        adh["H1"] = "Fédération CNOSF"
        adh.column_dimensions["H"].width = 30
        for r in range(2, fin + 1):
            adh.cell(row=r, column=8)._style = copy(adh.cell(row=r, column=7)._style)
        if adh.auto_filter.ref:
            adh.auto_filter.ref = re.sub(r":\$?[A-Z]+", ":H", adh.auto_filter.ref, count=1)
    for i, c in enumerate(actifs, start=2):
        _ecrire(adh, i, [c.get("nom"), c.get("mode_reglement") or None, _num(c.get("montant")),
                         _num(c.get("clubs")), _num(c.get("licencies")), _num(c.get("feminines")),
                         c.get("elu_referent") or None, c.get("federation") or None])
    adh.data_validations.dataValidation = []
    tec = onglet(classeur, "tec")
    nb_modes = tec.max_row if tec is not None else len(MODES_REGLEMENT) + 1
    validation = DataValidation(type="list", formula1=f"tec!$A$1:$A${nb_modes}", allow_blank=True)
    adh.add_data_validation(validation)
    validation.add(f"B2:B{fin}")

    # --- Voix
    voix = onglet(classeur, "Voix")
    couleurs_categories = styles_categories(voix)
    _preparer_feuille(voix, nb)
    _entetes_en_clair(voix, adh)
    for i, c in enumerate(actifs, start=2):
        trouve = f"MATCH($A{i},Adhésion!$A:$A,0)"
        _ecrire(voix, i, [
            c.get("nom"),
            f"=INDEX(Adhésion!$E:$E,{trouve})",
            c["_categorie"] or None,
            1,
            f"=IF(AND(B{i}>=1,B{i}<=2000),1,0)",
            f"=IF(AND(B{i}>2000,B{i}<=10000),2,0)",
            f"=IF(B{i}>10000,3,0)",
            f"=IF(C{i}=1,5,0)",
            f'=IF(OR(INDEX(Adhésion!$B:$B,{trouve})="",INDEX(Adhésion!$B:$B,{trouve})="-"),0,SUM(D{i}:H{i}))',
            "x" if c["_present"] else None,
            f'=IF(J{i}="",0,I{i})',
        ])
        if c["_categorie"] in couleurs_categories:  # couleur de la catégorie, comme dans le fichier importé
            voix.cell(row=i, column=3)._style = copy(couleurs_categories[c["_categorie"]])
    _pied_voix(voix, total, num, den)

    # --- Coordonnées
    coord = onglet(classeur, "Coordonnées")
    _preparer_feuille(coord, nb)
    _entetes_en_clair(coord, adh)
    if annee_adhesion:
        coord["B1"] = re.sub(r"\b20\d\d\b", str(annee_adhesion), str(coord["B1"].value or "Adhérent"))
    for i, c in enumerate(actifs, start=2):
        trouve = f"MATCH($A{i},Adhésion!$A:$A,0)"
        _ecrire(coord, i, [c.get("nom"),
                           f'=IF(OR(INDEX(Adhésion!$B:$B,{trouve})="",INDEX(Adhésion!$B:$B,{trouve})="-"),"NON","OUI")',
                           c.get("president") or None, c.get("mail_president") or None])

    classeur.properties.modified = datetime.now(timezone.utc).replace(tzinfo=None)
    classeur.properties.lastModifiedBy = "Application AG 2027"
    sortie = io.BytesIO()
    classeur.save(sortie)
    return sortie.getvalue()


def _entetes_en_clair(feuille, adh):
    """En-têtes « =Adhésion!A1 » remplacés par leur texte : un fichier jamais ouvert dans Excel
    n'a pas de valeur calculée, et la relecture de l'export doit retrouver « ORGANISME »."""
    for cellule in feuille[1]:
        texte = cellule.value if isinstance(cellule.value, str) else ""
        if texte.startswith("=") and normaliser_nom(texte.split("!")[0]) == "adhesion":
            cellule.value = adh[cellule.value.split("!")[-1].replace("$", "")].value


def _pied_voix(voix, total, num, den):
    """Quorums sous les totaux : formules corrigées (arrondi supérieur, 2/3 des voix exprimées)."""
    style_libelle = copy(voix.cell(row=total + 2, column=8)._style)
    style_valeur = copy(voix.cell(row=total + 2, column=9)._style)
    lignes = {
        2: ("Quorum participation (1/2 du total voix des membres)", f"=ROUNDUP(I{total}/2,0)"),
        3: ("Quorum participation atteint ?", f'=IF(K{total}>=I{total + 2},"OUI","NON")'),
        5: (f"Quorum approbation ({num}/{den} des voix exprimées)", f"=ROUNDUP(K{total}*{num}/{den},0)"),
        6: ("Quorum approbation atteint ?",
            f'=IF(I{total + 7}="","",IF(I{total + 7}>=I{total + 5},"OUI","NON"))'),
        7: ("Voix « pour » obtenues (à saisir)", None),
    }
    for decalage, (libelle, formule) in lignes.items():
        r = total + decalage
        if not voix.cell(row=r, column=8).has_style:
            voix.cell(row=r, column=8)._style = copy(style_libelle)
            voix.cell(row=r, column=9)._style = copy(style_valeur)
        voix.cell(row=r, column=8, value=libelle)
        voix.cell(row=r, column=9, value=formule)
    # mises en forme « atteint ? » cassées dans le fichier d'origine (#REF!) : vert si OUI, rouge si NON
    for cf in voix.conditional_formatting:
        for regle in cf.rules:
            if any("#REF!" in f for f in regle.formula):
                cellule = str(cf.sqref).split(":")[0]
                regle.formula = [f'{cellule}="NON"' if "<" in regle.formula[0] and ">=" not in regle.formula[0]
                                 else f'{cellule}="OUI"']


def _num(valeur):
    texte = str(valeur if valeur is not None else "").strip()
    if not texte:
        return None
    try:
        return int(float(texte))
    except ValueError:
        return texte
