# Cahier des charges – Application « Projet AG 2027 » (CDOS 78)

Version 1 – 18 novembre 2026
Document de référence : `docs/2026-11-20-Retroplanning_AGO_CDOS78_v05.docx`
Données de départ : `donnees/projet_ag_2027.json` (46 tâches, calendrier de communication, règles statutaires, ordre du jour, points de vigilance, questions à trancher, extraits de la v05)

## 1. Objet

Piloter la préparation de l'Assemblée générale ordinaire du CDOS 78 du **samedi 20 mars 2027 au Port-Marly** : suivre l'avancement des tâches du rétroplanning, la communication, le budget, le quorum et la constitution du rapport d'activité 2026 – perspectives 2027.

L'application doit pouvoir être réutilisée pour l'AG 2028 : la date de l'AG et les délais statutaires sont des paramètres, pas des valeurs écrites dans le code.

## 2. Utilisateurs et rôles

Un compte peut avoir plusieurs rôles.

| Rôle | Personnes (indicatif) | Droits |
|---|---|---|
| Chef de projet | Patrick | Tout : tâches, paramètres, comptes, validation des actions et des contributions, exports |
| Communication | Siham (coordination), Marion Lebel (prestataire) | Tâches de la catégorie Communication ; calendrier de communication ; proposer des actions ; Siham valide les actions proposées (paramètre « valideur communication ») |
| Budget | Louis | Tâches de la catégorie Budget ; lignes budgétaires (prévu / engagé / réalisé) ; suivi des cotisations |
| Contribution | Responsables de pôle | Leur seule fiche de contribution au rapport d'activité (leur pôle) ; commentaires sur leurs tâches |
| Lecture | Pierre (Président), membres du BE | Consultation de tout, sans modification |

Règles :
- Chaque utilisateur modifie le statut, l'avancement et le commentaire des tâches dont il est responsable, quel que soit son rôle.
- Seul le Chef de projet crée, supprime ou redate une tâche.
- Toute modification est tracée dans un journal (qui, quand, quoi, ancienne et nouvelle valeur).

## 3. Bandeau du haut (navigation)

Logo CDOS 78 et titre « Projet AG 2027 » à gauche ; à droite, le nom de l'utilisateur connecté, « Aide », « Se déconnecter » et la version (`aaaammjj-hhmm`, heure de Paris).

Onglets, affichés selon les rôles :

1. **Tableau de bord** – tous
2. **Rétroplanning** – tous
3. **Communication** – Chef de projet, Communication, Lecture
4. **Rapport d'activité** – Chef de projet, Contribution, Lecture
5. **Budget** – Chef de projet, Budget, Lecture
6. **Quorum** – Chef de projet, Budget, Lecture
7. **Documents** – tous
8. **Paramètres** – Chef de projet
9. **Comptes** – Chef de projet

## 4. Écrans

### 4.1 Tableau de bord
- Comptes à rebours : J-x avant l'AG, avant le butoir de convocation (J-30), avant le prochain jalon.
- Avancement global (moyenne pondérée des tâches, hors tâches conditionnelles comme la seconde AG) et avancement par phase et par catégorie (barres).
- Tâches en retard (date dépassée, non faites), en rouge, et tâches des 14 prochains jours.
- Jauge du quorum : voix des comités inscrits comparées au seuil (la moitié du total des voix).
- Budget : prévu, engagé, réalisé.
- Contributions au rapport d'activité : état par pôle (non commencée, brouillon, soumise, validée).
- Questions à trancher encore ouvertes.
- Pour un utilisateur qui n'est pas Chef de projet : en tête, « Mes tâches » (ses tâches ouvertes, triées par date).

### 4.2 Rétroplanning
- Liste des tâches groupées par phase, triées par date ; filtres par catégorie, responsable, statut ; recherche texte.
- Colonnes : échéance, action, responsables, base statutaire, statut, avancement %, commentaire.
- Vue Gantt / frise des jalons (comme le graphique du document v05), l'AG mise en évidence.
- Statuts : À faire, En cours, Fait, Bloqué, Sans objet. Une date « approximative » (période comme « Décembre 2026 ») est signalée par un « ~ ».
- Contrôles de cohérence affichés en bandeau d'alerte : tâche sans responsable, tâche après sa dépendance, échéance un dimanche, convocation après le butoir J-30, CA convoqué moins de 10 jours avant.
- Export Word du rétroplanning au format CDOS 78 (lot 3).

### 4.3 Communication
- Calendrier de communication (date, action, canal, responsables) issu de la v05.
- Proposer une action (Marion Lebel) → statut « Proposée » → « Validée » ou « Refusée » par la coordinatrice (Siham) ou le Chef de projet → « Réalisée » avec lien de la publication.
- Canaux : Mail nominatif, Téléphone, Site www.cdos78.fr, LinkedIn, Facebook, Instagram, Communiqué de presse.
- Rappel permanent de la règle de rédaction : seuls les comités sportifs départementaux des Yvelines à jour de leur cotisation à la date de l'AG votent.

### 4.4 Rapport d'activité
- Une fiche par pôle (5 pôles + Communication + Formation, liste en paramètre) remplie par son responsable :
  - bilan 2026 (texte),
  - chiffres clés : indicateur, valeur 2025 (référence), valeur 2026, source,
  - état des engagements annoncés en 2026 (Réalisé / En cours / Reporté / Abandonné + commentaire),
  - perspectives 2027,
  - photos (lot 3).
- Statut de la fiche : Non commencée, Brouillon, Soumise, Validée (validation par le Chef de projet), avec date limite (8 janvier 2027 dans la v05).
- Export Word du rapport d'activité compilé, au format CDOS 78 (lot 3).

### 4.5 Budget
- Lignes du budget de l'AG : poste, fournisseur, montant prévu, engagé, réalisé, date, justificatif (lien), commentaire.
- Totaux et écart prévu / réalisé ; alimentation du bilan de fin de projet (tâche « Établir le bilan… avant fin juin »).

### 4.6 Quorum
- Liste des comités membres : nom, catégorie (1 à 5), nombre de licenciés, voix (calculées : 1 de base, +1 à +3 selon le nombre de licenciés, +5 pour la catégorie 1 ; barème en paramètre), cotisation de la période en cours payée oui/non et date, inscrit à l'AG oui/non, représentant, mandat reçu.
- Total des voix, seuil du quorum, voix inscrites, marge ; liste des comités à relancer triée par nombre de voix.
- Le jour J : régularisation de la cotisation à l'accueil et émargement, puis liste des votants et décompte des voix arrêtés avant le constat du quorum.
- Rappel : la cotisation votée à l'AG s'applique de cette AG jusqu'à l'AG suivante (pas à l'année civile).

### 4.7 Documents
- Liste du dossier de l'AG avec statut et lien (Drive) : rapport d'activité, rapport moral, rapport financier, comptes 2026, rapport du commissaire aux comptes, budget 2027, projet de PV de l'AG 2026, modèle de mandat, convocation.
- Rappel des règles statutaires (tableau « Ce que disent les statuts »), de l'ordre du jour, des points de vigilance et des questions à trancher (chaque question : ouverte / tranchée + décision + date).

### 4.8 Paramètres (Chef de projet)
- Projet : nom, date et lieu de l'AG, délai de convocation (30 j), délai de seconde AG (21 j), écart minimal avant l'AG du CNOSF (45 j), délai de déclaration en préfecture (3 mois). Les butoirs sont recalculés à partir de la date de l'AG.
- Listes : phases, catégories, statuts, pôles, canaux, barème des voix, valideur communication.
- Import / ré-import des données depuis `projet_ag_2027.json`.

### 4.9 Comptes (Chef de projet)
- Créer, modifier, désactiver un compte : nom, courriel, rôles, pôle (pour Contribution), mot de passe initial.
- L'utilisateur change son mot de passe à la première connexion.

## 5. Données et architecture

- **Flask (Python 3.12)**, gabarits Jinja2, CSS simple aux couleurs CDOS 78 (bleu #2E5597, violet #7030A0, en-têtes de tableau #0070C0), police Calibri / Carlito.
- **Stockage : un Google Sheet « CDOS78 - Projet AG 2027 »**, comme les autres applications CDOS 78 ; onglets : Projet, Parametres, Taches, Communication, Budget, Comites, Contributions, Indicateurs, Engagements, Documents, Questions, Comptes, Journal, version. Les onglets sont lus par leur nom, jamais par leur position.
  - Le Sheet est créé à la main dans le Drive puis partagé en Éditeur avec le compte de service (un compte de service ne peut pas créer de fichier : quota Drive nul).
  - Un script `init_sheet.py` crée les onglets et charge `projet_ag_2027.json`.
- Mots de passe hachés (werkzeug), jamais en clair.
- Configuration par variables d'environnement (`SECRET_KEY`, `SHEET_ID`, `SERVICE_ACCOUNT_JSON`) ; `credentials/` et `.env` dans `.gitignore`.
- Mise en cache courte des lectures du Sheet (quota API).
- Hébergement : Render (gratuit, Frankfurt) dans un premier temps ; prévoir un `Dockerfile` pour la migration vers le VPS Infomaniak (Docker + nginx).
- Fichier `version.txt` (`aaaammjj-hhmm`, heure de Paris) affiché dans le bandeau et écrit dans l'onglet version au démarrage.

## 6. Découpage en lots

| Lot | Contenu | Résultat attendu |
|---|---|---|
| 1 | Socle : connexion, rôles, bandeau, Sheet, import JSON ; Rétroplanning ; Tableau de bord ; Paramètres ; Comptes | Patrick suit l'avancement avec les 46 tâches de la v05 |
| 2 | Communication ; Budget ; Quorum ; Documents et questions à trancher | Chaque responsable met à jour sa partie |
| 3 | Rapport d'activité (fiches par pôle) ; exports Word (rapport d'activité, rétroplanning) ; aide contextuelle ; rappels par mail des échéances (optionnel) | Le dossier de l'AG sort de l'application |

## 7. Critères de réception

- Les 46 tâches de la v05 apparaissent avec la bonne phase, la bonne date et les bons responsables.
- Changer la date de l'AG dans les Paramètres recalcule les butoirs affichés.
- Un utilisateur « Contribution » ne voit et ne modifie que la fiche de son pôle.
- Le tableau de bord se charge en moins de 3 secondes.
- Tests automatiques (pytest) sur les droits par rôle, le calcul des voix, le quorum, l'avancement et les butoirs.
