# Jeux de fichiers d'exemple des formats de données

Ces jeux servent aux tests des migrations (format 1 vers 2 vers 3), de la garde « données plus récentes » et de
l'import ZIP, en mode serveur comme en mode dossier. Données fictives, petites (12 enregistrements au plus par
table, `parametres.csv` entier), reproductibles octet pour octet.

- Les produire : `python -I outils/generer_fixtures_formats.py` depuis la racine (il vide et réécrit ce dossier,
  sauf ce fichier). Il lit `tests/fixtures/v1/` et les étiquettes git `v1.1.0` et `v1.2.0`.
- Les utiliser : `from jeux_formats import JEUX, copier_jeu` (dans `tests/`) puis
  `copier_jeu("f3-v1.2.0", dossier_temporaire)`. Ne jamais lire ni écrire un jeu en place, ni toucher à des
  données réelles : toujours une copie dans un dossier temporaire.
- Les tables sont tronquées par enregistrements CSV (une cellule entre guillemets avec sauts de ligne reste
  entière) : des références vers des enregistrements retirés peuvent donc pendre (une ligne de `ot_pieces.csv`
  qui cite un OT absent, par exemple). C'est normal ; un lecteur ne doit pas s'en servir pour juger la migration.
- Une variante est un dossier avec `variante.json` (`base`, `description`, `supprimer`, `vider`) et seulement les
  fichiers qui changent : `copier_jeu` compose la base, superpose les fichiers, supprime puis vide.
- Fichiers CSV : UTF-8 avec BOM, séparateur `;`, fins de ligne CRLF, apostrophe de protection en tête de certaines
  cellules, dates AAAA-MM-JJ (sauf `windows-1252`). Git ne les convertit jamais (`.gitattributes`).
- Courriels et numéros de téléphone : le générateur remplace de façon déterministe ceux qui ne seraient pas
  fictifs (`.example`, plages réservées de l'ARCEP) ; les démos actuelles n'en contiennent aucun.

## Jeux de base

**f1** : les quatre fichiers de `tests/fixtures/v1/` (`demandes`, `equipements`, `ordres_travail`, `parametres`),
format 1 (avant le lot 2) : `version_schema;'1` dans `parametres.csv` (une base sans la clé vaut aussi 1). Rien n'est abîmé. Un lecteur doit
reconnaître le format 1, et migrer vers 2 puis 3 (tables manquantes créées vides, colonnes ajoutées).

**f2-v1.1.0** : `donnees/demo/` de l'étiquette `v1.1.0`, format 2 (versions 1.0 et 1.1), 22 tables,
`version_schema;'2`. Pas de `wiki_pages.csv`, `wiki_journal.csv`, ni de colonne `ordres_travail.astuce`. Rien
n'est abîmé. Un lecteur doit la migrer vers 3 : deux tables vides, une colonne `astuce` vide, `version_schema` à 3.

**f3-v1.2.0** : `donnees/demo/` de l'étiquette `v1.2.0`, format 3 (1.2.0 et 2.0 bêta), 24 tables,
`version_schema;'3`. Rien n'est abîmé. Un lecteur doit la relire sans rien changer (aller-retour identique).

## Variantes (toutes tirées de f3-v1.2.0, sauf la première qui l'enrichit)

**f3-v2.0.0** : f3-v1.2.0 plus, dans `parametres.csv`, les clés de la 2.0 (`mode_solo`, `cloture_une_etape`,
`solo_technicien_id`), et `acces/comptes.json` (`{"version": 1, "comptes": [...]}`, format écrit par `serveur.py`)
avec un compte responsable fictif : identifiant `claire.essai`, mot de passe de test `essai-formats-prevo`
(scrypt N=2^15, r=8, p=3, sel fixe). Format de données toujours 3 : un lecteur ne doit ni migrer ni toucher à
`acces/`, et les données plus les comptes se relisent à l'identique. Ne jamais réutiliser ce compte ni ce mot de
passe hors des tests.

**vide** : `equipements.csv` de 0 octet (fichier créé puis jamais écrit). Un lecteur doit le traiter comme une
table sans en-tête ni lignes (ou signaler clairement un fichier vide), sans planter ni écraser les autres tables.

**entete-tronque** : l'en-tête de `ordres_travail.csv` est coupé au milieu du nom de colonne `temps_prevu_h`
(il finit par `temps_pr`) ; les lignes de données sont intactes et plus larges que l'en-tête. Un lecteur doit
refuser ou signaler le fichier (colonnes illisibles), sans perdre de données ni écrire un fichier réduit.

**colonnes-manquantes** : `equipements.csv` sans les colonnes `modele` et `valeur_remplacement`. Un lecteur doit
les compléter (valeurs vides) et relire les autres colonnes sans décalage.

**colonnes-en-trop** : `equipements.csv` avec une colonne inconnue `colonne_maison` au milieu (après
`designation`) et une autre, `note_maison`, en fin de table. Un lecteur doit les conserver à la réécriture, à leur
place, et ne pas les confondre avec une colonne du schéma.

**sans-bom** : tous les fichiers sans BOM UTF-8. Un lecteur doit les lire comme les autres (UTF-8) ; à la
réécriture, le BOM est remis.

**table-absente** : sans `wiki_pages.csv` ni `articles.csv` (22 tables). Un lecteur doit traiter une table absente
comme vide (sans erreur) et ne la créer qu'à la première écriture.

**melange** : `ordres_travail.csv` au format 2 (sans la colonne `astuce`) dans une base dont `version_schema`
vaut 3, comme après une copie partielle de fichiers. Un lecteur doit compléter la colonne manquante sans
changer le numéro de format.

**windows-1252** : `equipements.csv` enregistré en Windows-1252, sans BOM, dates `date_mes` en JJ/MM/AAAA, comme
après un enregistrement par Excel (les caractères hors Windows-1252 sont devenus `?`). Un lecteur doit détecter
l'encodage, relire les dates en AAAA-MM-JJ, et réécrire en UTF-8 avec BOM.

**plus-recent** : données d'une version plus récente : `version_schema;'4`, colonne inconnue
`nouvelle_colonne_v4` en fin d'`ordres_travail.csv`, table inconnue `pieces_v4.csv` (3 colonnes, 2 lignes). Un
lecteur doit refuser d'écrire (garde « données plus récentes », demande de mettre Prévo à jour) et ne rien
modifier ; en lecture seule, il peut ouvrir ce qu'il connaît.
