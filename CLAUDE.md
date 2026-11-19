# CLAUDE.md – Projet AG 2027 (CDOS 78)

Instructions permanentes pour Claude Code dans ce dépôt.

## Contexte
- Application Flask de gestion du projet « AG 2027 » du CDOS 78 (Comité Départemental Olympique et Sportif des Yvelines).
- Le besoin complet est dans `CAHIER_DES_CHARGES.md`. Le document de référence est `docs/2026-11-20-Retroplanning_AGO_CDOS78_v05.docx` ; ses données sont déjà extraites dans `donnees/projet_ag_2027.json`.
- L'utilisateur s'appelle Patrick (Pat). Il travaille sur un MacBook Air M2 avec PyCharm, déploie via GitHub vers Render (gratuit, Frankfurt), et prépare une migration vers un VPS Infomaniak (Docker + nginx).

## Langue
- Interface, messages, commentaires de code et documentation en **français**.
- Noms de variables et de fonctions en français sans accents (`date_cible`, `taches_en_retard`).

## Méthode de travail
- Avancer **lot par lot** (voir le cahier des charges) ; à la fin de chaque lot : lancer les tests, lancer l'application en local, indiquer à Patrick quoi tester sur http://localhost:5000.
- Avant de proposer un commit, lancer `git status` et vérifier que **tous les fichiers nouveaux sont ajoutés** (templates, partials, config.py…) : par le passé, des fichiers non poussés ont provoqué des erreurs 500 sur Render (TemplateNotFound, module introuvable).
- Ne jamais committer `credentials/`, `.env`, ni une clé de compte de service. Si une clé apparaît dans un fichier ou un message, le signaler immédiatement.
- Poser une question à Patrick plutôt que deviner quand une règle de gestion n'est pas dans le cahier des charges.

## Conventions techniques
- Python 3.12, Flask, gunicorn, gspread + google-auth, werkzeug pour le hachage des mots de passe, python-docx pour les exports Word, pytest.
- Google Sheet comme base de données ; onglets lus **par leur nom**, jamais par leur position ; lecture tolérante si un onglet manque (message clair, pas de 500).
- Le compte de service ne peut pas créer de fichier Drive : le Sheet est créé par Patrick puis partagé avec le compte de service.
- Configuration par variables d'environnement : `SECRET_KEY`, `SHEET_ID`, `SERVICE_ACCOUNT_JSON` (contenu JSON) ou `GOOGLE_APPLICATION_CREDENTIALS` (chemin local).
- `version.txt` au format `aaaammjj-hhmm` en heure de Paris (Europe/Paris), régénéré à chaque livraison, affiché dans le bandeau.
- En cas d'erreur de saisie dans un formulaire : réafficher la page avec les valeurs saisies et le message, ne pas rediriger en vidant les champs.
- Dates affichées au format français (« lundi 15 février 2027 »).

## Charte graphique CDOS 78
- Logo : `static/logo_cdos78.png`.
- Bleu titres #2E5597, violet sous-titres #7030A0, en-têtes de tableau #0070C0 texte blanc gras centré, lignes alternées #D9D9D9, police Calibri (repli Carlito, sans-serif).

## Exports Word
- Partir d'un document CDOS 78 existant comme base (ici la v05), vider le corps et réutiliser ses styles nommés (Titre1, Titre2, Corps de texte, Paragraphe de liste, style de tableau Grille du tableau) ; ne pas recréer la mise en forme à la main.
- Titre1/Titre2 sont numérotés automatiquement : ne pas taper de numéros.

## Règles métier à ne pas oublier
- Seuls les comités sportifs départementaux des Yvelines membres du CDOS 78 et à jour de leur cotisation **à la date de l'AG** votent ; régularisation possible à l'accueil le jour même.
- La cotisation votée à une AG s'applique de cette AG jusqu'à l'AG suivante (pas du 1er janvier au 31 décembre).
- Voix : 1 de base, +1 à +3 selon le nombre de licenciés, +5 pour la catégorie 1 ; quorum = moitié du total des voix ; ni procuration ni vote par correspondance.
- Convocation au moins 30 jours avant l'AG ; seconde AG dans les 21 jours si le quorum n'est pas atteint.
