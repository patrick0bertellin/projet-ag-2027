"""Paramètres du projet (onglet Projet) et listes (onglet Parametres)."""

from datetime import timedelta

from metier import entier
from metier.dates import ajouter_mois, lire_date

# Valeurs du projet : clé -> (libellé, valeur par défaut)
CHAMPS_PROJET = {
    "nom": ("Nom du projet", "Projet AG 2027"),
    "evenement": ("Événement", "Assemblée générale ordinaire du CDOS 78"),
    "date_ag": ("Date de l'AG", "2027-03-20"),
    "lieu": ("Lieu de l'AG", "Le Port-Marly"),
    "delai_convocation_jours": ("Délai de convocation (jours avant l'AG)", "30"),
    "delai_seconde_ag_jours": ("Délai de la seconde AG (jours après l'AG)", "21"),
    "ecart_cnosf_jours": ("Écart minimal avant l'AG du CNOSF (jours)", "45"),
    "delai_prefecture_mois": ("Délai de déclaration en préfecture (mois)", "3"),
    "tache_convocation": ("Tâche « envoi de la convocation » (contrôle du butoir)", "T021"),
    "date_ca": ("Date de la réunion du CA (contrôle des 10 jours)", ""),
    "tache_convocation_ca": ("Tâche « convocation du CA »", ""),
    "valideur_communication": ("Valideur des actions de communication", "Siham"),
    "montant_cotisation": ("Montant de la cotisation (€)", "150"),
    "approbation_fraction": ("Majorité d'approbation (fraction des voix exprimées)", "2/3"),
}

CHAMPS_NUMERIQUES = {
    "montant_cotisation", "delai_convocation_jours", "delai_seconde_ag_jours", "ecart_cnosf_jours", "delai_prefecture_mois",
}

STATUTS_TACHE = ["À faire", "En cours", "Fait", "Bloqué", "Sans objet"]
STATUTS_TERMINES = {"Fait", "Sans objet"}

LISTES_PAR_DEFAUT = {
    "phases": [
        "Phase 1 – Cadrage",
        "Phase 2 – Clôture et préparation",
        "Phase 3 – Convocation et mobilisation",
        "Phase 4 – Derniers jours et jour J",
        "Phase 5 – Si le quorum n'est pas atteint",
        "Phase 6 – Après l'AG",
    ],
    "categories": [
        "Pilotage", "Budget", "Communication", "Quorum et adhésions",
        "Rapport d'activité", "Logistique",
    ],
    "statuts": STATUTS_TACHE,
    "poles": ["Général", "Pôle 1", "Pôle 2", "Pôle 3", "Pôle 4", "Pôle 5", "Communication", "Formation"],
    "canaux": [
        "Mail nominatif", "Téléphone", "Site www.cdos78.fr", "LinkedIn", "Facebook",
        "Instagram", "Communiqué de presse",
    ],
}

LIBELLES_LISTES = {
    "phases": "Phases",
    "categories": "Catégories",
    "statuts": "Statuts des tâches",
    "poles": "Pôles (rapport d'activité)",
    "canaux": "Canaux de communication",
}

# Barème des voix (art. 6) : 1 voix par membre ; +1 de 1 à 2 000 licenciés, +2 de 2 001
# à 10 000, +3 au-delà de 10 000 ; +5 pour la catégorie 1 (fédérations olympiques).
# Chaque seuil = nombre de licenciés à partir duquel le bonus s'applique.
BAREME_PAR_DEFAUT = {
    "voix_base": 1,
    "voix_bonus_categorie_1": 5,
    "seuils": [(1, 1), (2001, 2), (10001, 3)],
}


def lire_projet(stockage):
    """Dictionnaire des valeurs du projet, complété par les valeurs par défaut."""
    valeurs = {cle: defaut for cle, (_, defaut) in CHAMPS_PROJET.items()}
    for ligne in stockage.lire("Projet"):
        cle = ligne.get("cle", "").strip()
        if cle:
            valeurs[cle] = ligne.get("valeur", "").strip()
    return valeurs


def lignes_projet(valeurs):
    """Lignes de l'onglet Projet à partir d'un dictionnaire de valeurs."""
    lignes = []
    for cle, (libelle, defaut) in CHAMPS_PROJET.items():
        lignes.append({"cle": cle, "valeur": valeurs.get(cle, defaut), "libelle": libelle})
    return lignes


def butoirs(projet):
    """Butoirs recalculés à partir de la date de l'AG et des délais en paramètre."""
    date_ag = lire_date(projet.get("date_ag"))
    if date_ag is None:
        return []
    conv = entier(projet.get("delai_convocation_jours"), 30)
    seconde = entier(projet.get("delai_seconde_ag_jours"), 21)
    cnosf = entier(projet.get("ecart_cnosf_jours"), 45)
    pref = entier(projet.get("delai_prefecture_mois"), 3)
    return [
        {"cle": "convocation", "libelle": f"Butoir de la convocation (J-{conv})",
         "date": date_ag - timedelta(days=conv)},
        {"cle": "ag", "libelle": "Assemblée générale", "date": date_ag},
        {"cle": "seconde_ag", "libelle": f"Seconde AG au plus tard (J+{seconde})",
         "date": date_ag + timedelta(days=seconde)},
        {"cle": "cnosf", "libelle": f"AG du CNOSF au plus tôt (J+{cnosf})",
         "date": date_ag + timedelta(days=cnosf)},
        {"cle": "prefecture", "libelle": f"Déclaration en préfecture (AG + {pref} mois)",
         "date": ajouter_mois(date_ag, pref)},
    ]


def butoir(projet, cle):
    for b in butoirs(projet):
        if b["cle"] == cle:
            return b["date"]
    return None


def lire_listes(stockage):
    """Listes paramétrables ; une liste absente de l'onglet garde sa valeur par défaut."""
    lignes = stockage.lire("Parametres")
    listes = {}
    for ligne in sorted(lignes, key=lambda l: (l.get("liste", ""), entier(l.get("ordre"), 0))):
        nom = ligne.get("liste", "").strip()
        valeur = ligne.get("valeur", "").strip()
        if nom in LISTES_PAR_DEFAUT and valeur:
            listes.setdefault(nom, []).append(valeur)
    for nom, defaut in LISTES_PAR_DEFAUT.items():
        listes.setdefault(nom, list(defaut))
    listes["statuts"] = list(STATUTS_TACHE)  # la logique dépend de ces libellés
    return listes


def lire_bareme(stockage):
    bareme = {
        "voix_base": BAREME_PAR_DEFAUT["voix_base"],
        "voix_bonus_categorie_1": BAREME_PAR_DEFAUT["voix_bonus_categorie_1"],
        "seuils": [],
    }
    for ligne in stockage.lire("Parametres"):
        nom = ligne.get("liste", "").strip()
        if nom == "voix_base":
            bareme["voix_base"] = entier(ligne.get("valeur"), 1)
        elif nom == "voix_bonus_categorie_1":
            bareme["voix_bonus_categorie_1"] = entier(ligne.get("valeur"), 5)
        elif nom == "voix_seuils_licencies" and ligne.get("valeur", "").strip():
            bareme["seuils"].append((entier(ligne.get("valeur")), entier(ligne.get("complement"))))
    if not bareme["seuils"]:
        bareme["seuils"] = list(BAREME_PAR_DEFAUT["seuils"])
    bareme["seuils"].sort()
    return bareme


def lignes_parametres(listes, bareme):
    """Lignes de l'onglet Parametres (listes + barème)."""
    lignes = []
    for nom in LISTES_PAR_DEFAUT:
        if nom == "statuts":
            valeurs = STATUTS_TACHE
        else:
            valeurs = listes.get(nom, LISTES_PAR_DEFAUT[nom])
        for i, v in enumerate(valeurs, start=1):
            lignes.append({"liste": nom, "ordre": i, "valeur": v, "complement": ""})
    lignes.append({"liste": "voix_base", "ordre": 1, "valeur": bareme["voix_base"], "complement": ""})
    lignes.append({"liste": "voix_bonus_categorie_1", "ordre": 1,
                   "valeur": bareme["voix_bonus_categorie_1"], "complement": ""})
    for i, (seuil, bonus) in enumerate(bareme["seuils"], start=1):
        lignes.append({"liste": "voix_seuils_licencies", "ordre": i, "valeur": seuil, "complement": bonus})
    return lignes
