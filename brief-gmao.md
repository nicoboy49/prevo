# Brief Claude Code — GMAO « CSV + HTML »

Projet de Nicolas Briand (SELECTIS). Défi lancé par son groupe en formation : faire coder une GMAO complète par Claude. Le résultat sera livré au groupe et tournera d'abord sur le PC Windows de Nicolas.

Référence fonctionnelle : le cahier des charges « Cahier des charges — GMAO (base CSV, interface HTML) » rédigé dans Claude (Nicolas peut l'exporter en Markdown dans ce dossier sous `cahier-des-charges.md`). Ce brief en reprend tout ce qui est nécessaire pour coder et y ajoute les décisions prises ensuite. **En cas de doute, ce brief fait foi.**

---

## 1. Ce qu'on livre

Un dossier `gmao/` autonome, zippable, qui fonctionne de trois façons :

| Mode | Comment on le lance | Usage |
| --- | --- | --- |
| **Dossier** | Ouvrir `index.html` dans Chrome ou Edge, choisir le dossier `donnees/` | Un seul poste, zéro installation |
| **Serveur** | Double-clic sur `Lancer_GMAO.bat` (ou `lancer.sh`) | Plusieurs postes + téléphones sur le réseau local, QR codes utilisables |
| **Démo** | Bouton « Essayer avec les données de démo » à l'écran d'accueil | Présentation, aucun enregistrement (export ZIP possible) |

Plus : un guide utilisateur (`GUIDE.html`, imprimable), une fiche technique des CSV (`FICHE_TECHNIQUE_CSV.md`), un jeu de données de démo réaliste.

## 2. Contraintes non négociables

- **Pas de Rust, pas de framework, pas de build.** HTML5 + CSS3 + JavaScript « vanilla » côté client, Python 3 (bibliothèque standard uniquement) côté serveur. Si `/chantier` est utilisé, ce choix de stack prime sur son défaut.
- **Doit marcher en `file://`** : scripts classiques (`<script src>`), pas de modules ES, pas de `fetch` vers des fichiers locaux en mode dossier.
- **Bibliothèques embarquées en local** dans `js/lib/` (aucun CDN, l'atelier peut être hors ligne) : PapaParse (CSV), **ECharts** (graphiques, copie fournie dans `reference-design/vendor/echarts.min.js`), qrcode-generator (QR), jsQR (lecture QR par caméra), JSZip (export ZIP). Licences conservées dans `js/lib/LICENCES.txt`.
- **Interface entièrement en français**, code commenté en français, noms de variables explicites.
- **Un fichier JS par module** (M1 à M10, IA, dictée) + un module commun d'accès aux données + un module commun d'interface.
- Navigateurs cibles : dernières versions de Chrome et Edge (Windows). En mode serveur, les téléphones Android/iOS doivent pouvoir créer une DI et consulter une fiche.
- Responsive de 360 px (téléphone, écran DI) à 1920 px. Police 16 px minimum, contrastes lisibles en atelier.

## 2 bis. Design — reprendre le style « Cockpit » de la charte Cockpit

Nicolas veut la même identité visuelle que sa charte Cockpit. Le dossier `reference-design/` en contient une copie : `style.css` (charte complète), `index.html` (structure d'en-tête, navigation, cartes), `favicon.svg`, la police Sora (`polices/`), ECharts (`vendor/`) et `app-extrait-theme-et-utilitaires.js` (palette des graphiques `T`, formats de nombres et dates en français, `echapper`, `memo`).

- **Reprendre tels quels** : variables CSS (`--fond`, `--carte`, `--bleu`, `--cyan`, `--vert`, `--rouge`, `--ambre`, `--violet`, `--rayon`…), police Sora embarquée, boutons (`.btn-primaire`, `.btn-secondaire`, `.btn-fantome`, `.btn-danger`), champs, cartes (`.carte`, `.grille` 12 colonnes, `.c4`…`.c12`), barre de navigation à icônes SVG, bandeau d'indicateurs (`.instruments`), alertes (`.alerte.attention`, `.alerte.important`), légendes et « Voir les valeurs » sous chaque graphique, réglages ECharts du thème `T`.
- **Adapter** : logo carré dégradé avec une clé ou un engrenage à la place du « € » (favicon assorti) ; navigation plus longue (13 écrans) → menu latéral repliable sur grand écran et barre du bas sur téléphone, avec les mêmes icônes trait ; la DI sur téléphone doit rester simple et à gros boutons.
- **Couleurs de priorité** prises dans la charte : P1 `--rouge`, P2 `--ambre`, P3 `--cyan`, P4 `--muted`. Toujours accompagnées du libellé (P1…P4), jamais la couleur seule.
- **Thème clair obligatoire pour l'impression** (bon de travail A4, étiquettes QR, liste « à commander ») : feuille `@media print` en noir sur blanc, sans fond sombre. Un thème clair à l'écran est un plus (bouton dans Paramètres) pour les ateliers très éclairés, mais le sombre reste le défaut.

## 3. Arborescence cible

```
gmao/
  index.html
  GUIDE.html
  FICHE_TECHNIQUE_CSV.md
  Lancer_GMAO.bat
  lancer.sh
  serveur.py
  css/style.css
  js/lib/...            (bibliothèques tierces)
  js/donnees.js         (schéma + accès aux données, commun aux 3 modes)
  js/stockage-*.js      (un adaptateur par mode)
  js/interface.js       (helpers d'écran : tableaux, formulaires, fenêtres, notifications)
  js/modules/*.js       (un fichier par module métier)
  js/app.js             (démarrage, navigation, profils)
  donnees/              (les CSV)
    documents/          (photos, notices, rapports)
    sauvegardes/AAAA-MM-JJ/
```

## 4. Stockage — les trois modes

Une seule interface interne (`charger(table)`, `enregistrer(table, lignes, versionAttendue)`, `listerVersions()`, `ecrireDocument(nom, blob)`, `lireDocument(nom)`), trois adaptateurs.

**Format CSV (tous modes)** : séparateur `;`, UTF-8 **avec BOM**, première ligne = en-têtes, dates ISO `AAAA-MM-JJ` ou `AAAA-MM-JJ HH:MM`, décimales avec point dans le fichier (virgule à l'affichage), guillemets RFC 4180. Une ligne n'est jamais supprimée : champ `actif` ou statut `Annulé`. Le fichier doit rester éditable dans Excel puis relisible sans erreur (accents compris).

**Mode dossier** : API File System Access (`showDirectoryPicker`). Mémoriser le handle dans IndexedDB pour proposer « Reprendre le dossier précédent » (avec `requestPermission`). Fichier `verrou.txt` (nom du poste + heure) : avertir si une autre session semble ouverte, sans bloquer.

**Mode serveur** : détecté automatiquement quand la page est servie en `http(s)` et que `/api/ping` répond.

**Mode démo** : données de démo embarquées dans un fichier JS généré, tout en mémoire, bandeau permanent « Démo — rien n'est enregistré », bouton « Exporter en ZIP ». Doit aussi accepter un import de CSV par glisser-déposer (secours si l'API dossier est indisponible).

**Écritures concurrentes (indispensable en mode serveur)** : toute modification passe par une fonction de mutation `modifier(table, fonction)`. On applique la fonction aux lignes en mémoire, puis on enregistre avec la version connue du fichier. Si le serveur répond « conflit » (fichier modifié entre-temps), on recharge la table, on réapplique la même fonction, on réessaie (3 fois maximum, puis message clair). Les identifiants (`DI-2026-0042`…) sont calculés **dans** la fonction, donc recalculés à chaque essai. Rafraîchissement automatique des tables modifiées par d'autres postes toutes les 30 s (via `listerVersions`).

**Sauvegarde** : à la première écriture de chaque journée, copie de tous les CSV dans `donnees/sauvegardes/AAAA-MM-JJ/`. Restauration depuis Paramètres.

**Pièces jointes** : rangées dans `donnees/documents/`, le CSV ne garde que le nom de fichier. Photos redimensionnées côté navigateur (1280 px max, JPEG) avant envoi.

## 5. Serveur local et installateur

**`serveur.py`** (Python 3.8+, bibliothèque standard seulement) :
- Sert le dossier `gmao/` en statique, écoute sur `0.0.0.0:8080` (port modifiable en argument, port suivant si occupé).
- API : `GET /api/ping`, `GET /api/versions` (date de modification de chaque CSV), `GET /api/csv/<table>`, `PUT /api/csv/<table>` avec en-tête de version attendue (409 si conflit), `GET|PUT /api/documents/<nom>`, `POST /api/sauvegarde`, `GET /api/info` (adresse IP réseau local pour les QR codes), `POST /api/ia` (relais vers le fournisseur d'IA configuré, voir §8).
- Écriture atomique (fichier temporaire puis renommage). Refus de tout chemin hors de `donnees/` (pas de `..`), noms de tables limités à la liste du schéma, taille maximale des envois (10 Mo).
- Affiche au démarrage l'adresse locale et l'adresse réseau, ouvre le navigateur sur la GMAO.
- Pas d'authentification : usage réseau local uniquement, le guide le dit clairement.

**`Lancer_GMAO.bat`** (double-clic, lisible par un humain, commenté) :
1. Vérifie la présence de Python (`py` ou `python`).
2. Absent → propose de l'installer avec `winget install Python.Python.3.12` (demande confirmation), sinon indique le lien officiel.
3. Lance `serveur.py`, qui ouvre le navigateur.
4. L'écran d'accueil de la GMAO affiche alors un QR code de l'adresse réseau pour connecter les téléphones.

Rappel dans le guide : au premier lancement, autoriser Python dans le pare-feu Windows sur **réseau privé**.

`lancer.sh` : équivalent Mac/Linux, sans installation automatique.

## 6. Modèle de données — 22 fichiers

| Fichier | Champs |
| --- | --- |
| `localisations.csv` | id, libelle, parent_id, type (site / atelier / ligne) |
| `equipements.csv` | id, repere, designation, localisation_id, parent_id, marque, modele, num_serie, date_mes, criticite (A/B/C), statut (en service / arrêt / rebut), heures_fonct_jour, habilitation_requise, consignation, document, actif |
| `demandes.csv` | id, date_heure, demandeur, equipement_id, symptome, impact (sécurité / arrêt / dégradé / gêne), description, photo, statut, motif_decision, date_decision, ot_id |
| `ordres_travail.csv` | id, origine (DI / préventif / urgence / manuel), di_id, gamme_id, equipement_id, type (correctif immédiat / correctif différé / préventif systématique / préventif conditionnel / amélioration / réglementaire), priorite (P1–P4), statut, motif_attente, titre, travail_a_faire, consignes, date_creation, date_prevue, technicien_id, temps_prevu_h, date_debut, date_fin, arret_production (0/1), duree_arret_h, symptome_code, cause_code, remede_code, compte_rendu, remise_service (0/1), cout_soustraitance, date_cloture_tech, date_cloture_admin, motif_annulation, ot_lie_id |
| `ot_operations.csv` | id, ot_id, ordre, operation, valeur_attendue, fait (0/1), valeur_mesuree |
| `ot_pieces.csv` | id, ot_id, article_id, quantite_prevue |
| `ot_temps.csv` | id, ot_id, technicien_id, date, heures |
| `gammes.csv` | id, equipement_id, libelle, declencheur (date / compteur / seuil), periodicite_jours, compteur_id, periodicite_unites, seuil, avance_jours, derniere_realisation, releve_derniere_realisation, prochaine_echeance, temps_prevu_h, consignes, actif |
| `gamme_operations.csv` | id, gamme_id, ordre, operation, valeur_attendue |
| `articles.csv` | id, reference, designation, fabricant, ref_fabricant, emplacement, unite, stock, stock_securite, point_commande, qte_commande, delai_jours, prix_unitaire, fournisseur_id, critique (0/1), actif |
| `article_equipement.csv` | id, article_id, equipement_id, quantite |
| `mouvements_stock.csv` | id, date, article_id, type (entrée / sortie / inventaire / retour), quantite, ot_id, utilisateur, commentaire |
| `techniciens.csv` | id, nom, prenom, metier, taux_horaire, capacite_h_semaine, actif |
| `habilitations.csv` | id, technicien_id, intitule (ex. BR, B2V, H0V, CACES R489…), date_obtention, date_echeance |
| `compteurs.csv` | id, equipement_id, libelle, unite |
| `releves.csv` | id, compteur_id, date, valeur, utilisateur |
| `controles_reglementaires.csv` | id, equipement_id, nature, texte_reference, periodicite_mois, organisme, derniere_date, prochaine_date, rapport, observations, observations_levees (0/1) |
| `codes_defaillance.csv` | id, famille (symptôme / cause / remède), code, libelle |
| `fournisseurs.csv` | id, nom, contact, telephone, email |
| `achats.csv` | id, date, article_id, fournisseur_id, quantite, prix_unitaire, statut (demandée / commandée / reçue), date_reception |
| `parametres.csv` | cle, valeur (nom de l'entreprise, délais par priorité, heures de fonctionnement par défaut, tolérance de respect du préventif, réglages IA et dictée…) |
| `journal.csv` | id, date_heure, poste, profil, table, id_ligne, action — trace de chaque modification |

Clés lisibles et préfixées (`EQ-0001`, `DI-2026-0042`, `OT-2026-0107`, `ART-0012`…). Le stock d'un article est **recalculé à partir des mouvements** (un inventaire fixe une valeur absolue) ; la colonne `stock` est réécrite pour rester lisible dans Excel. Contrôle des clés étrangères au chargement : une référence cassée est signalée dans un écran « Contrôle de la base », jamais ignorée en silence.

## 7. Règles de gestion

- **RG1 — DI** : `Nouvelle` → `Acceptée` (crée un OT) · `Regroupée` (rattachée à un OT ouvert du même équipement) · `Différée` · `Refusée` (motif obligatoire, visible du demandeur).
- **RG2 — Priorité** = criticité × impact. Un impact « sécurité » donne toujours P1 + bandeau rouge. Modifiable par le responsable avec motif. Délais par défaut (paramètres) : P1 immédiat, P2 24 h, P3 7 jours, P4 prochain arrêt.

  | Criticité \ Impact | Gêne | Dégradé | Arrêt |
  | --- | --- | --- | --- |
  | A | P2 | P1 | P1 |
  | B | P3 | P2 | P1 |
  | C | P4 | P3 | P2 |

- **RG3 — Statuts OT** : `Créé` → `Préparé` → `Planifié` → `En cours` → `Clôturé techniquement` → `Clôturé administrativement`, plus `En attente` (motif obligatoire) et `Annulé` (motif obligatoire, jamais effacé). OT d'urgence : `Créé` → `En cours` directement. Passage à `Planifié` refusé si une pièce prévue manque en stock (proposer `En attente` motif « pièce »).
- **RG4 — Clôture technique** bloquée sans : date de fin, temps passés, code cause, code remède, compte rendu ≥ 10 caractères (« RAS » refusé sur un correctif), case « remis en service en sécurité ». La procédure de consignation de l'équipement s'affiche sur l'OT avec le rappel : cocher une case ne consigne rien. **Clôture administrative** = OT verrouillé ; une reprise se fait par un nouvel OT lié (`ot_lie_id`).
- **RG5 — Préventif** : à l'ouverture (et sur bouton), chaque gamme active échue (date − avance, compteur atteint, ou seuil dépassé) génère **un seul** OT si aucun OT ouvert n'existe pour elle, avec ses opérations copiées dans `ot_operations`. À la clôture, `derniere_realisation` = date de fin réelle et l'échéance est recalculée depuis cette date. Une anomalie vue pendant un préventif crée une DI liée en un clic.
- **RG6 — Stock** : toute sortie est imputée à un OT ; stock négatif refusé ; point de commande = consommation pendant le délai + stock de sécurité ; sous ce seuil, l'article passe dans « À commander » (et peut générer une demande d'achat).
- **RG7 — Coût d'un OT** = Σ heures × taux horaire + Σ pièces × prix unitaire + sous-traitance.
- **RG8 — Habilitations** : si l'équipement a une `habilitation_requise`, affecter l'OT à un technicien sans habilitation valide à la date prévue affiche un **avertissement** (pas un blocage), tracé dans le journal. Les habilitations échues ou à moins de 60 jours sont signalées sur l'accueil.
- **RG9 — Contrôles réglementaires** séparés du préventif. Statut calculé : à jour / à planifier (≤ 30 j) / en retard / observations à lever.

## 8. Profils

Choix à l'ouverture, mémorisé sur le poste : **Demandeur** (créer et suivre ses DI), **Technicien** (choisi dans la liste : ses OT, exécution, compte rendu, sorties de pièces, clôture technique), **Responsable** (tout le reste). Sans serveur d'authentification, c'est une adaptation des écrans, pas une sécurité : le dire dans « À propos ».

## 9. Écrans

E1 Accueil (compteurs : DI à traiter, OT en retard, P1 ouverts, préventifs de la semaine, articles à commander, VGP sous 30 j, habilitations à renouveler ; QR de connexion en mode serveur) · E2 Nouvelle DI (5 champs, équipement par recherche ou scan QR, photo) · E3 Liste des DI · E4 Liste des OT (filtres, tri, couleurs P1 rouge / P2 orange / P3 jaune / P4 gris, export CSV) · E5 Fiche OT (onglets Préparation, Exécution, Compte rendu, Historique équipement ; impression A4 « bon de travail ») · E6 Planning semaine par technicien avec glisser-déposer et charge/capacité · E7 Parc (arborescence, fiche équipement complète, impression d'étiquettes QR par lot) · E8 Préventif (gammes, calendrier 12 semaines, éditeur de check-list) · E9 Magasin (articles, mouvements, inventaire, à commander, achats) · E10 Contrôles réglementaires · E11 Indicateurs · E12 Paramètres (codes, délais, entreprise, IA, dictée, sauvegardes, contrôle de la base, export ZIP) · E13 À propos.

**QR codes** : en mode serveur, le QR encode l'URL réseau de la fiche équipement avec un bouton « Signaler un problème » (un téléphone le scanne avec son appareil photo). En mode dossier, le QR encode `GMAO:<id>` et se lit avec la caméra du poste via jsQR. Le repère est toujours imprimé en clair sous le code.

**Signature** : en bas du menu, un badge discret « Développé par Claude (Anthropic) à la demande de Nicolas Briand — SELECTIS », qui ouvre « À propos » (version, date, modes de stockage, licences des bibliothèques, rappel sur les limites de sécurité).

## 10. Assistant IA (bonus optionnel)

Désactivé par défaut. Chaque utilisateur l'active dans Paramètres et choisit son fournisseur :
- **Ollama local** (par défaut, adresse `http://localhost:11434`, modèle conseillé `qwen2.5:7b`) ;
- **toute API compatible OpenAI** (LM Studio, Mistral, Groq, OpenAI…) : URL, modèle, clé.

Règles :
- **Un fournisseur distant affiche un avertissement explicite** à l'activation et une icône permanente « données envoyées à <fournisseur> ». Ollama local affiche « reste sur ce PC ».
- Clé API stockée uniquement dans le navigateur du poste (jamais dans les CSV, jamais renvoyée par le serveur).
- En mode serveur, les appels passent par `/api/ia` (téléphones compris). En mode dossier, appel direct, avec l'indication dans le guide de régler `OLLAMA_ORIGINS` pour Ollama.
- **L'IA propose, l'humain valide** : chaque suggestion s'affiche dans un encadré avec « Utiliser » / « Modifier » / « Ignorer ». Elle ne remplit jamais seule un champ obligatoire, ne change aucun statut.
- Si le fournisseur ne répond pas, les boutons IA se masquent ; la GMAO fonctionne à l'identique.
- Délai d'attente et indicateur de progression (un PC sans carte graphique peut mettre plusieurs dizaines de secondes).

Fonctions :
1. **DI** : reformuler une demande vague en symptôme clair, proposer l'impact.
2. **Compte rendu** : transformer des notes en vrac en compte rendu structuré (constat, cause, action, pièces, reste à faire).
3. **Codes de défaillance** : proposer symptôme / cause / remède **uniquement parmi la liste existante** (réponse JSON validée contre `codes_defaillance.csv`, tout code inconnu est rejeté).
4. **Gamme** : proposer une check-list de départ à partir de la désignation de l'équipement.
5. **Fiche équipement** : résumé de l'historique (pannes récurrentes, dernières interventions).

Prompts dans un fichier séparé `js/modules/ia-prompts.js`, en français, faciles à modifier.

## 11. Dictée vocale (bonus, signalée, non bloquée)

Bouton micro sur les champs texte longs (description de DI, compte rendu, notes). Utilise la reconnaissance vocale du navigateur (Web Speech API, `fr-FR`). **À la première utilisation sur un poste**, avertissement clair : « Dans Chrome et Edge, la voix est envoyée aux serveurs de Google ou Microsoft pour être transcrite. » Puis l'utilisateur choisit librement ; option pour désactiver la dictée dans Paramètres. Bouton masqué si le navigateur ne la propose pas. Combinable avec l'IA : dicter ses notes, puis « Rédiger le compte rendu ».

## 12. Indicateurs (E11 et accueil)

MTBF = temps de fonctionnement / nombre de pannes (OT correctifs avec arrêt) · MTTR = temps total de réparation / nombre de réparations · Disponibilité = MTBF / (MTBF + MTTR) · Durée d'arrêt · Part du préventif (heures) · Respect du préventif (tolérance paramétrable) · OT en retard · Délai de prise en charge par priorité · Coûts par équipement et par mois · Valeur du stock. Si le temps de fonctionnement est inconnu, afficher « non calculable » et pourquoi, jamais un chiffre faux.

Graphiques : Pareto pannes et durée d'arrêt (top 10), évolution mensuelle correctif vs préventif sur 12 mois, MTBF / MTTR des équipements A, répartition des causes, charge vs capacité par technicien sur 4 semaines. Sélecteur de période, export image et CSV. Pas de double axe ; légende dès 2 séries ; palette lisible par les daltoniens ; couleurs de statut réservées aux statuts.

## 13. Données de démo

Atelier fictif cohérent : 1 site, 3 ateliers, ~30 équipements (compresseur à vis, pompes, convoyeurs, presse, tour CN, pont roulant, armoires électriques, chariot élévateur…), 4 techniciens avec habilitations variées (dont une échue et une à renouveler), ~50 articles (dont 3 sous le point de commande), 10 gammes, codes de défaillance, contrôles réglementaires (pont roulant, chariot, installation électrique — dont un en retard), 6 mois d'historique fictif qui donnent des indicateurs crédibles. Aucune donnée réelle de personne ou d'entreprise.

## 14. Lots et recette

Livrer par lots ; **un lot n'est terminé que si tous ses scénarios passent**, testés automatiquement (Playwright ou équivalent, navigateur Chromium headless) en mode serveur et en mode démo. Le mode dossier se teste via un adaptateur simulé + une vérification manuelle par Nicolas.

1. **Lot 1 — Socle** : 3 modes de stockage, mutation avec gestion de conflit, serveur, installateur, profils, M1 Parc, M2 DI, M3 OT complet.
2. **Lot 2 — Préventif et magasin** : M4 gammes et génération, M5 magasin, sorties de pièces depuis l'OT, achats.
3. **Lot 3 — Pilotage** : M6 indicateurs, planning, étiquettes QR, contrôles réglementaires, habilitations.
4. **Lot 4 — Bonus** : assistant IA, dictée, guide utilisateur, fiche technique, finitions.

Scénarios de recette (au minimum) :
- [ ] Panne sur pompe : DI (fuite, dégradé) → acceptée P2 → OT préparé avec kit garniture → planifié → exécuté → clôturé ; stock du kit −1 ; OT dans l'historique de la pompe.
- [ ] Clôture refusée avec « RAS » et sans code cause, message clair.
- [ ] Gamme mensuelle échue : un seul OT même après trois rechargements ; à la clôture, échéance au mois suivant.
- [ ] Sortie de pièce qui rendrait le stock négatif refusée ; passage sous le point de commande → « À commander ».
- [ ] Aller-retour Excel : ajout d'un équipement dans `equipements.csv` sous Excel, relecture sans erreur, accents compris.
- [ ] Indicateurs du jeu de démo identiques à un calcul à la main sur 3 équipements.
- [ ] Sauvegarde : supprimer une ligne par erreur, restaurer, retrouver la ligne.
- [ ] **Conflit** : deux navigateurs créent une DI au même moment → deux DI distinctes, aucune perte.
- [ ] **Téléphone** : depuis un second appareil (viewport 375 px), scan d'URL QR → fiche équipement → DI créée avec photo, visible sur le PC en moins de 30 s.
- [ ] **Habilitation** : affecter un OT électrique (habilitation BR requise) à un technicien sans BR valide → avertissement affiché et tracé.
- [ ] **IA** : avec un faux fournisseur de test, un code de défaillance inventé par l'IA est rejeté ; sans fournisseur, aucun bouton IA visible.
- [ ] **Serveur** : une requête `PUT /api/documents/../serveur.py` est refusée.

## 14 bis. Dépôt GitHub public

Le projet sera publié sur un dépôt GitHub public, à la fois outil libre et vitrine du savoir-faire de Nicolas (cahier des charges, règles métier, recette, pilotage d'une IA).

- **Licence MIT** pour le code (`LICENSE` à la racine, titulaire : Nicolas Briand — SELECTIS). Bibliothèques tierces sous leur propre licence, regroupées dans `js/lib/LICENCES.txt` : ECharts (Apache 2.0, conserver le NOTICE), police Sora (OFL, joindre le texte de licence), PapaParse, qrcode-generator, jsQR, JSZip.
- **`.gitignore`** dès le premier commit : `donnees/*` sauf le jeu de démo (`!donnees/demo/` ou équivalent), `donnees/sauvegardes/`, `donnees/documents/`, `verrou.txt`, `.chantier/`, `__pycache__/`, fichiers d'éditeur. Jamais de données réelles d'atelier, jamais de clé d'API, jamais d'adresse personnelle dans le dépôt.
- **Garder `reference-design/` hors du dépôt** (ajouté au `.gitignore`) : le design est repris dans `css/` et `js/lib/`, le dossier de référence ne sert qu'au développement.
- **`README.md` en français**, soigné, c'est la page vitrine :
  1. ce qu'est l'outil, en trois lignes, avec une capture d'écran du tableau de bord (données de démo) ;
  2. « Essayer en 30 secondes » (mode démo) puis les deux modes d'installation ;
  3. fonctionnalités par module ;
  4. format des données (renvoi vers `FICHE_TECHNIQUE_CSV.md`) ;
  5. **« Comment ce projet a été fait »** : cahier des charges et règles métier rédigés par Nicolas Briand, formateur en maintenance industrielle (SELECTIS), avec Claude ; code entièrement généré par Claude Code (Anthropic) à partir de ce cahier des charges, lot par lot, chaque lot validé par des scénarios de recette automatisés. Ton factuel, sans exagération ;
  6. limites connues (pas d'authentification, usage réseau local) ;
  7. licence et crédits.
- Messages de commit en français, un commit par étape cohérente ; un tag par lot terminé (`lot-1`, `lot-2`…) puis `v1.0.0`.
- Pas de push sans accord de Nicolas : Claude Code prépare le dépôt local, Nicolas crée le dépôt GitHub et valide la première publication.

## 15. Laissé au jugement de Claude Code

Détails visuels hors charte Cockpit (§2 bis), découpage interne des fichiers, nom de l'application (proposer 2–3 noms à Nicolas avant de figer). **Demander à Nicolas avant** : tout ajout de dépendance hors liste, tout changement du format CSV, toute fonction qui enverrait des données hors du réseau local en dehors de l'IA distante choisie par l'utilisateur.
