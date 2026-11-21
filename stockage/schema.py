"""Structure du Google Sheet : onglets et colonnes attendues.

Les onglets sont toujours lus par leur nom, jamais par leur position.
Les colonnes sont repérées par l'en-tête de la ligne 1 : l'ordre peut changer.
"""

ONGLETS = {
    "Projet": ["cle", "valeur", "libelle"],
    "Parametres": ["liste", "ordre", "valeur", "complement"],
    "Taches": [
        "id", "phase", "echeance_texte", "date_cible", "date_approx", "action",
        "responsables", "base", "categorie", "statut", "avancement", "commentaire",
        "depend_de", "poids", "conditionnelle", "maj_par", "maj_le",
    ],
    "Communication": [
        "id", "date_texte", "date_cible", "action", "canaux", "responsables",
        "statut", "propose_par", "valide_par", "lien", "commentaire",
    ],
    "Budget": [
        "id", "poste", "fournisseur", "prevu", "engage", "realise", "date",
        "justificatif", "commentaire",
    ],
    "Comites": [
        "id", "nom", "federation", "categorie", "licencies", "clubs", "feminines", "mode_reglement",
        "montant", "date_reglement", "elu_referent", "president", "mail_president", "actif",
        "inscrit", "representant", "mandat_recu", "present", "noms_import", "maj_par", "maj_le",
    ],
    "Federations": ["categorie", "libelle_categorie", "discipline", "federation", "site"],
    "Sondage": ["horodatage", "organisme", "nom", "prenom", "mail_president", "reponse", "rep_nom", "rep_prenom",
                "rep_mail", "rep_fonction", "comite_id"],
    "Modeles": ["nom", "partie", "fichier", "maj_par", "maj_le", "contenu"],
    "Contributions": [
        "pole", "responsable", "statut", "titre", "commission", "presentation", "bilan", "perspectives",
        "date_limite", "maj_par", "maj_le", "valide_par", "valide_le", "commentaire_validation",
    ],
    "Indicateurs": ["id", "pole", "indicateur", "valeur_reference", "valeur_annee", "source"],
    "Engagements": ["id", "pole", "engagement", "etat", "commentaire", "prevu"],
    "Documents": ["id", "document", "statut", "lien", "commentaire"],
    "Questions": ["id", "question", "etat", "decision", "date_decision"],
    "Reference": ["type", "ordre", "titre", "texte", "complement", "complement2"],
    "Comptes": [
        "id", "identifiant", "nom", "alias", "courriel", "roles", "pole", "mot_de_passe", "mdp_hash", "actif",
        "doit_changer_mdp", "cree_le",
    ],
    "Journal": ["horodatage", "utilisateur", "onglet", "id", "champ", "ancienne", "nouvelle"],
    "version": ["version", "horodatage"],
}

# Colonne servant de clé pour retrouver une ligne
CLES = {
    "Projet": "cle",
    "Taches": "id",
    "Communication": "id",
    "Budget": "id",
    "Comites": "id",
    "Contributions": "pole",
    "Indicateurs": "id",
    "Engagements": "id",
    "Documents": "id",
    "Questions": "id",
    "Comptes": "id",
}
