# Démarrer le Projet AG 2027 avec Claude Code

## 1. Installer Claude Code (une seule fois)

Dans le Terminal du Mac :

```bash
curl -fsSL https://claude.ai/install.sh | bash
claude --version
```

Puis dans PyCharm : Réglages → Plugins → Marketplace → chercher « Claude Code » (éditeur Anthropic) → Installer → redémarrer PyCharm.

## 2. Créer le projet

```bash
mkdir -p ~/pythonProject/projet-ag-2027
cd ~/pythonProject/projet-ag-2027
# dézipper ici le kit : CLAUDE.md, CAHIER_DES_CHARGES.md, DEMARRAGE.md, docs/, donnees/, static/
git init
```

Ouvrir le dossier dans PyCharm. Créer sur GitHub un dépôt privé vide `projet-ag-2027` (Claude Code peut faire le lien avec `git remote` ensuite).

## 3. Préparer Google (avant le lot 1)

1. Dans le Drive de comiteolympique78@gmail.com, créer un Google Sheet vide nommé **CDOS78 - Projet AG 2027**.
2. Dans Google Cloud, créer un compte de service dédié (par exemple `projet-ag-2027`) et télécharger sa clé JSON dans `~/pythonProject/projet-ag-2027/credentials/` (dossier jamais commité).
3. Partager le Sheet en **Éditeur** avec l'adresse du compte de service.
4. Noter l'identifiant du Sheet (la partie de l'URL entre `/d/` et `/edit`).

Claude Code peut te guider pas à pas pour ces étapes si besoin.

## 4. Lancer Claude Code et donner la première consigne

Dans le terminal intégré de PyCharm, dans le dossier du projet :

```bash
claude
```

Claude Code lit automatiquement `CLAUDE.md`. Colle ensuite cette consigne :

> Lis CLAUDE.md, CAHIER_DES_CHARGES.md et donnees/projet_ag_2027.json. Propose-moi d'abord le plan du lot 1 (arborescence, onglets du Google Sheet, routes, modèles de page) et les questions éventuelles, sans écrire de code. Après mon accord, réalise le lot 1 avec ses tests, puis lance l'application en local et dis-moi quoi vérifier.

## 5. Ensuite, à chaque lot

1. Tester sur http://localhost:5000 ce que Claude Code t'indique.
2. Demander les corrections directement dans Claude Code.
3. Quand c'est bon : « commit et push » (Claude Code vérifie que tous les nouveaux fichiers sont inclus).
4. Lot 1 validé : demander « prépare le déploiement sur Render » (variables d'environnement `SECRET_KEY`, `SHEET_ID`, `SERVICE_ACCOUNT_JSON`).
5. Passer au lot suivant : « réalise le lot 2 ».

## Différence avec la méthode actuelle

Plus de zip à télécharger et à recopier : Claude Code écrit les fichiers directement dans ton dossier, lance les tests et l'application, et fait les commits. Tu valides chaque modification dans PyCharm (vue des différences).
