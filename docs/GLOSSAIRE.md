# Glossaire métier français → anglais

Ce glossaire fixe la traduction anglaise des termes métier de Prévo. Il sert aux traducteurs de `js/i18n/en.js` (un par groupe d'écrans) et à la relecture.

**Règle d'or : un terme français = une traduction anglaise, partout.** Même terme dans un menu, un bouton, un message d'erreur, un champ du schéma ou le wiki. Si un terme n'est pas dans la liste, prendre le plus proche et l'ajouter ici (une ligne) avant de continuer.

Autres règles :

- **Anglais britannique** (décision D151 : `en` = en-GB) : colour, organisation, catalogue, labour, programme, stocktake, cancelled. Mais on garde le terme que l'industrie britannique emploie vraiment (ex. « work order », « MTBF »).
- Termes anglais en minuscules, sauf noms propres (Prévo) et abréviations. La première lettre d'un libellé affiché suit l'usage de l'écran (majuscule en début de libellé, comme en français).
- Le genre et l'accord français disparaissent : « Acceptée » (demande) et « Accepté » (OT) donnent le même mot.
- Le pluriel anglais suit la forme `one` / `other` déjà utilisée par le dictionnaire.
- Les colonnes `tr`, `it` et `pt-PT` viendront au Lot 5 (décision D166) : le tableau gardera `fr` comme langue pivot.

## 1. Abréviations françaises : que fait-on en anglais ?

| fr | affiché en anglais | remarque |
|---|---|---|
| OT | WO | abréviation anglaise usuelle de « work order ». Écrire « work order » en toutes lettres à la première occurrence d'un écran ou dans une phrase d'aide. |
| DI | (pas d'abréviation) « work request » | « WR » n'est pas assez courant. Toujours en toutes lettres. |
| GMAO | CMMS | computerised maintenance management system ; en toutes lettres dans « À propos ». |
| MTBF, MTTR | MTBF, MTTR | identiques. Développer : mean time between failures / mean time to repair. |
| HT | excl. VAT | « (€ HT) » devient « (€ excl. VAT) ». Pas de « HT » en anglais britannique. |
| TTC | incl. VAT | |
| IA | AI | |
| RG (règle de gestion, « RG6 ») | « business rule 6 » | références internes dans les textes d'aide. Ne pas écrire « BR6 » : personne ne l'emploie. |
| P1 à P4 | P1 à P4 | inchangés (valeurs de liste). |
| A, B, C (criticité) | A, B, C | inchangés. |
| D24, D151… | D24, D151… | numéros de décision : inchangés. |
| CSV, ZIP, QR code, PC | idem | inchangés. |

## 2. Ordres de travail et demandes

| fr | en | remarque |
|---|---|---|
| ordre de travail (OT) | work order (WO) | la fiche de travail. Pluriel : work orders. |
| demande d'intervention (DI) | work request | émise par un demandeur ; peut donner un OT. |
| demande | request | forme courte de « demande d'intervention ». |
| demandeur | requester | personne qui signale un problème (profil « Demandeur »). |
| intervention | job | le travail réalisé sur site. « Intervention antérieure » (wiki) : previous job. |
| travail à faire | work to be done | champ de l'OT. |
| compte rendu | job report | rédigé à la fin de l'OT. |
| anomalie constatée | fault found | champ de l'OT : ce que le technicien a vu. |
| astuce pour la prochaine fois | tip for next time | champ libre de l'OT. |
| curatif | corrective | on ne dit pas « curative » en maintenance. |
| correctif | corrective | « correctif immédiat » : immediate corrective ; « correctif différé » : deferred corrective. |
| amélioration | improvement | type d'OT. |
| panne | breakdown | OT correctif qui a arrêté la production. « Failure » est réservé à « code de défaillance ». |
| symptôme | symptom | ce qu'on observe. |
| cause | cause | |
| remède | remedy | ce qui a été fait pour réparer. |
| code de défaillance | failure code | liste Symptôme / Cause / Remède. |
| famille (de code) | family | famille de code de défaillance. |
| origine (d'un OT) | origin | valeurs : DI, manuel, préventif, urgence. |
| urgence | emergency | valeur d'origine. |
| manuel | manual | |
| impact (d'une demande) | impact | valeurs : arrêt, dégradé, gêne, sécurité. |
| arrêt de production | production stoppage | champ de l'OT. |
| durée d'arrêt | downtime | en heures. |
| mettre en attente | put on hold | motif : « reason for hold ». |
| motif | reason | motif d'annulation, de refus, de report, de mise en attente. |
| remis en service en sécurité | returned to service safely | case à cocher de l'OT. |
| sous-traitance | subcontracting | coût de sous-traitance : subcontracting cost. |
| OT lié | linked work order | |
| ordre (d'une opération) | sequence | colonne « Ordre » des opérations ; pas « order » ni « position ». |
| repères (fiche d'un OT) | key details | bloc de la fiche OT ; sans rapport avec « repère » (tag) d'un équipement. |
| origine « DI » (liste des OT) | Request | valeur d'origine d'un OT né d'une demande. |
| RAS | NTR | « RAS » refusé sur un correctif : « NTR » ; le contrôle accepte aussi « nothing to report ». |
| prise en charge (d'un OT) | taken on | |
| poste (ligne du tableau de coûts d'un OT) | cost line | pas « item » : réservé à l'article du magasin. |
| bon de travail | work order sheet | fiche imprimée de l'OT ; pas « job sheet ». |
| geste (wiki) | task | un geste ou une méthode (page savoir-faire). |
| regrouper | merge | une demande « Regroupée » est fusionnée dans une autre. |
| différer | defer | demande « Différée ». |

## 3. Équipements et parc

| fr | en | remarque |
|---|---|---|
| équipement | equipment | machine ou installation. Jamais « asset » dans les libellés. |
| parc | equipment register | l'ensemble des équipements suivis. Le menu court dit « Equipment ». |
| repère | tag | identifiant lisible d'un équipement (ex. CP-01). « Equipment tag » si l'ambiguïté est possible. |
| localisation | location | arbre site > atelier > ligne. |
| site | site | type de localisation. |
| atelier | workshop | type de localisation ; pas « plant ». « PC atelier » : workshop PC. |
| ligne | line | ligne de production (type de localisation). Ne pas confondre avec la ligne d'un tableau (« row »). |
| criticité | criticality | valeurs A, B, C. |
| statut (d'un équipement) | status | valeurs : en service, arrêt, rebut. |
| en service | in service | |
| arrêt (statut équipement) | stopped | |
| rebut / mis au rebut | scrapped | |
| désignation | designation | nom descriptif d'un équipement ou d'un article. À ne pas confondre avec « description » (demandes). |
| marque | make | pas « brand ». |
| modèle | model | |
| numéro de série | serial number | |
| date de mise en service | date in service | pas « commissioning date » (réservé à la mise en route). |
| heures de fonctionnement par jour | operating hours per day | sert au calcul du temps requis. |
| valeur de remplacement | replacement value | |
| habilitation requise | authorisation required | |
| compteur | meter | heures de marche, cycles, etc. |
| relevé (de compteur) | meter reading | |
| fiche (d'un équipement, d'un OT) | record | « la fiche de l'équipement » : the equipment record. Pas « sheet ». |
| fiche technique | data sheet | document d'un équipement. |
| menus courts « Parc », « Contrôles » | Equipment, Inspections | la forme longue (parc) reste « equipment register ». |
| document (d'un équipement) | document | |
| articles par équipement | parts by equipment | table de liaison article / équipement. |
| actif (case) | active | un enregistrement inactif est « inactive », jamais « deleted ». |

## 4. Préventif et contrôles

| fr | en | remarque |
|---|---|---|
| préventif | preventive | adjectif et nom (« le préventif » : preventive maintenance). Pas d'abréviation PM/PPM. |
| gamme (de préventif) | task list | modèle récurrent de travail. Pluriel : task lists. Choix tranché (voir la dernière section). |
| opération (d'une gamme / d'un OT) | task | une ligne de la gamme. |
| préventif systématique | fixed-interval preventive | déclenché par le calendrier. |
| préventif conditionnel | condition-based preventive | déclenché par un compteur ou un seuil. |
| déclencheur | trigger | valeurs : date, compteur, seuil. |
| seuil | threshold | |
| périodicité | interval | en jours, en mois ou en unités de compteur. |
| fréquence | frequency | « fois par an » ; pour une durée entre deux passages, utiliser « interval ». |
| échéance | due date | « prochaine échéance » : next due date. « Échue » : overdue. |
| avance (jours) | lead time (days) | combien de jours avant l'échéance l'OT est créé. |
| dernière réalisation | last completed | |
| planifier | schedule | donner une date à un OT. Pas « plan ». |
| date prévue | planned date | |
| temps prévu | planned time | en heures. |
| respect du préventif | preventive compliance | part des OT préventifs faits à l'échéance. |
| part du préventif | preventive share | part des heures passées sur le préventif. |
| contrôle réglementaire | statutory inspection | vérification périodique imposée par un texte. |
| organisme de contrôle | inspection body | |
| texte de référence | reference text | le texte réglementaire (ex. arrêté, norme). |
| observations levées | observations cleared | |
| rapport (d'un contrôle) | report | |
| rapport mensuel | monthly report | « Report » seul reste réservé au rapport (contrôle ou mensuel) : le menu « Signaler » est « Report a problem ». |
| nature du contrôle | type of inspection | pas « nature of the inspection ». |
| check-list (d'une gamme) | checklist | un seul mot. |
| levée d'observations | clearing | action de lever les observations d'un contrôle. |
| figer (un rapport), rapport figé | finalise, finalised report | |
| fait marquant | highlight | rapport mensuel. |
| suggestion | suggestion | propositions S1 à S4 de l'écran préventif. |

## 5. Sécurité et habilitations

| fr | en | remarque |
|---|---|---|
| consignation | isolation | mise en sécurité d'une machine avant intervention (énergies coupées, cadenassées). Choix tranché (voir la dernière section). |
| déconsignation | de-isolation | remise sous énergie. |
| procédure de consignation | isolation procedure | champ « Consignation » de l'équipement : isolation. |
| cadenas | padlock | |
| consigne (de sécurité) | safety instruction | « consignes » d'une gamme ou d'un OT : instructions. |
| habilitation | authorisation | autorisation nominative (ex. habilitation électrique). Choix tranché (voir la dernière section). |
| date d'obtention | date obtained | |
| date d'échéance (habilitation) | expiry date | pour une habilitation ; « due date » reste pour le préventif. |
| intitulé | name | nom de l'habilitation. |
| sécurité | safety | valeur d'impact : « safety ». |
| permis de feu | hot work permit | |

## 6. Magasin et achats

| fr | en | remarque |
|---|---|---|
| magasin | stores | le lieu et l'écran. Pas « warehouse ». |
| stock | stock | pas « inventory ». |
| article | item | un article du magasin. |
| pièce (détachée) | spare part | « pièces prévues d'un OT » : planned parts. |
| référence | reference | référence interne de l'article. |
| référence fabricant | manufacturer part number | |
| fabricant | manufacturer | |
| fournisseur | supplier | pas « vendor ». |
| unité | unit | unité de stock. |
| point de commande | reorder point | seuil sous lequel on réapprovisionne. |
| stock de sécurité | safety stock | |
| quantité à commander | order quantity | |
| délai d'approvisionnement | supply lead time | |
| article critique | critical item | |
| mouvement (de stock) | stock movement | |
| entrée | receipt | mouvement de stock entrant. Pas « entry ». |
| sortie | issue | mouvement sortant (« issue to a work order »). |
| retour | return | |
| inventaire | stocktake | comptage du stock (usage britannique). |
| achat | purchase | |
| commande | order | verbe « commander » : to order. |
| réception | goods receipt | arrivée d'un achat ; le mouvement de stock qui en résulte est un « receipt ». |
| réceptionner | receive | |
| prix unitaire | unit price | |
| valeur du stock | stock value | |
| quantité | quantity | |
| emplacement (d'un article) | bin location | partout : colonne, fiche, étiquette, wiki (pas « bin », « position » ni « storage location »). « Rayon et casier » : aisle and bin. |
| rupture (de stock) | out of stock / stock-out | « out of stock » comme état ou libellé ; « stock-out » comme nom compté (« 2 stock-outs »). |
| écart (d'inventaire) | variance | |
| nomenclature | bill of materials | articles montés sur une machine. |

## 7. Équipe et accès

| fr | en | remarque |
|---|---|---|
| technicien | technician | pas « engineer ». |
| responsable | manager | profil qui voit tout et règle les paramètres. |
| profil | profile | Demandeur / Technicien / Responsable. |
| métier | trade | électricien, mécanicien… |
| capacité (heures par semaine) | capacity (hours per week) | |
| taux horaire | hourly rate | |
| utilisateur | user | |
| identifiant (de connexion) | username | de la forme prenom.nom. |
| identifiant (clé d'une ligne) | ID | colonne « Identifiant » du schéma : ID. |
| mot de passe | password | |
| se connecter / se déconnecter | sign in / sign out | pas « log in ». |
| compte | account | |
| poste (cet ordinateur ou un autre) | workstation | « Ce poste » : This workstation ; « Nom du poste » : Workstation name ; « changé sur un autre poste » : on another workstation. Jamais « computer » ni « this PC » pour le poste. « PC » reste « PC » quand le français dit PC (le PC atelier, le PC serveur). Ne désigne jamais un emploi. |
| accès | access | |
| paramètres | settings | |
| sauvegarde | backup | |
| journal des modifications | change log | table `journal`. |
| appareil | device | téléphone ou navigateur enrôlé ; ne pas confondre avec « poste » (workstation). |
| enrôler, enrôlement, appareil enrôlé | enrol, enrolment, enrolled device | orthographe britannique (un seul « l » à enrol, deux à enrolled). |
| révoquer | revoke | |
| fiche d'accès | access record | pas « access sheet ». |
| journal des connexions | sign-in log | |
| mandataire (inverse) | proxy (reverse proxy) | |
| tâche planifiée | scheduled task | tâche Windows de démarrage. |
| portée (de l'accès : « ce PC », atelier, dehors) | scope | |
| empreinte (d'un fichier, manifeste) | fingerprint | |
| copie de sécurité | safety copy | copie faite avant une restauration ; « Copie des sauvegardes » (dossier externe) : backup copy. |
| bombe de décompression | decompression bomb | |
| porte d'entrée | front door | accès réseau de Prévo ; « page de porte » : gateway page. |
| élévation (de droits) | elevation | |
| Mode Solo | Solo mode | |
| Appliquer et relancer | Apply and restart | |
| Démarrer avec la machine / avec le PC | Starting with the PC | libellé réel du réglage : « Starting with the PC, and sleep » ; question de l'assistant : « Start with the PC? ». |

## 8. Indicateurs

| fr | en | remarque |
|---|---|---|
| indicateur | indicator | |
| MTBF | MTBF | mean time between failures : temps moyen entre pannes. |
| MTTR | MTTR | mean time to repair : temps moyen de rétablissement. |
| disponibilité | availability | MTBF ÷ (MTBF + MTTR). |
| temps requis | required time | heures de fonctionnement × jours de la période. |
| temps passé | time spent | heures saisies sur un OT. « Temps passés sur OT » : time spent on work orders. |
| délai de prise en charge | response time | de la demande au début de l'intervention. |
| OT en retard | overdue work orders | |
| charge / capacité | workload / capacity | |
| coût | cost | main-d'œuvre : labour ; pièces : parts. |
| période | period | |
| non calculable | cannot be calculated | |
| pointage (temps) | time entry | ligne de temps passé sur un OT. |

## 9. Wiki

| fr | en | remarque |
|---|---|---|
| wiki | wiki | base de savoir de l'atelier, rédigée avec l'aide de l'IA. |
| page | page | |
| savoir-faire | know-how | type de page. |
| mode (type de page) | failure mode | |
| composant | component | |
| ingestion | ingestion | lecture d'un OT clôturé par l'IA. |
| journal du wiki | wiki log | |
| en file | queued | |
| à valider | to be validated | |
| appliquée / validée | applied / validated | |
| refusée | declined | décision humaine ; pas « rejected ». |
| rejetée | rejected | rejet automatique (contrôles). |
| à refaire | to be redone | |
| rien à ajouter | nothing to add | |
| archivée | archived | |
| rubrique | heading | titre `## …` d'une page ; pas « section » (réservé à l'écran). |
| ancrage | anchor | |
| requête (envoyée à l'IA) | AI request | pour ne pas confondre avec la demande (work request). |
| savoir-faire (pages) | know-how pages | |
| tranchée / à trancher | settled / to be settled | contradictions du wiki. |
| rang de traitement | processing order | colonne du journal du wiki. |
| Créée le / Traitée le / Décidé par | Created on / Processed on / Decided by | journal du wiki ; pour une suggestion, « Traitée le » : Dealt with on. |
| essai(s) | attempt(s) | pas « try » ni « trial ». |
| faits (suggestions) | events | pannes, anomalies, visites. |
| suggestion traitée | dealt with | |
| refus (de l'IA) | rejected | refus automatique ; comparer « refusée » : declined. |

## 10. Interface et actions courantes

| fr | en | remarque |
|---|---|---|
| accueil | home | |
| écran | screen | |
| menu | menu | |
| enregistrer | save | |
| annuler | cancel | bouton ; pour un OT : « cancel the work order ». |
| modifier | edit | |
| ajouter | add | |
| supprimer | delete | |
| désactiver | deactivate | |
| fermer | close | |
| continuer | continue | |
| confirmer | confirm | |
| actualiser | refresh | |
| imprimer | print | |
| importer / exporter | import / export | |
| valider | validate | validation humaine (wiki, formulaire). Si « Valider » ferme une saisie : « confirm ». |
| clôturer | close | « clôturer techniquement » : close technically ; « administrativement » : close administratively. |
| rouvrir | reopen | |
| démarrer | start | |
| accepter / refuser | accept / decline | demandes. |
| libellé | label | nom court. |
| titre | title | |
| description | description | |
| commentaire | comment | |
| observations | observations | |
| données de démo | demo data | |
| dossier de données | data folder | |
| dictée | dictation | saisie vocale. |
| signaler un problème | report a problem | |
| menu « Signaler » | Report a problem | le menu court a le même libellé que l'écran, pour ne pas entrer en collision avec « Report » (rapport). |
| lots 1 à 4 (À propos) | phases 1 to 4 | pas « batch ». |
| ligne (d'un fichier ou d'un tableau) | row | « line » reste pour la ligne de production, une ligne de journal ou de commande. |
| ligne refusée (import) | rejected | |
| doublon sûr / supposé | certain / probable duplicate | |
| feuilles du modèle | Data, Help | |
| aucun… pour le moment | no … yet | « Aucune demande pour le moment » : No requests yet. |
| (non choisi) | (none selected) | |
| champ obligatoire | required field | |
| abîmé (fichier) | damaged | « Fichier abîmé » : damaged file. |

## 11. Statuts et valeurs de listes

| fr | en | remarque |
|---|---|---|
| Créé | Created | OT. |
| Préparé | Prepared | OT : tout est prêt. |
| Planifié | Scheduled | OT. |
| En cours | In progress | OT. |
| En attente | On hold | OT. |
| Annulé | Cancelled | OT, orthographe britannique (deux « l »). |
| Clôturé techniquement | Technically closed | OT. |
| Clôturé administrativement | Administratively closed | OT. |
| Nouvelle | New | demande. |
| Acceptée | Accepted | demande. |
| Refusée | Declined | demande. |
| Différée | Deferred | demande. |
| Regroupée | Merged | demande. |
| P1 / P2 / P3 / P4 | P1 / P2 / P3 / P4 | priorités ; « Priorité P1 » : Priority P1. |
| arrêt / dégradé / gêne / sécurité | stoppage / degraded / disruption / safety | impact d'une demande. |
| entrée / sortie / inventaire / retour | receipt / issue / stocktake / return | types de mouvement de stock. |
| commandée / demandée / reçue | ordered / requested / received | statuts d'un achat. |
| date / compteur / seuil | date / meter / threshold | déclencheurs de gamme. |
| décision / ingestion / manuel | decision / ingestion / manual | nature d'une entrée du journal du wiki. |
| IA / IA et manuel / manuel | AI / AI and manual / manual | origine d'une page du wiki. |

## Choix tranchés par Nicolas (06/11/2026)

Nicolas a retenu les choix par défaut ci-dessous ; le glossaire ci-dessus les applique. L'autre option reste notée pour mémoire.

1. **consignation** : défaut « isolation » ; autre « lockout/tagout (LOTO) ». « Isolation » est le terme britannique (isolation, lock-off) ; LOTO est surtout américain.
2. **habilitation** : défaut « authorisation » ; autre « qualification » ou « certification ». « Authorised person » est l'usage britannique pour l'électricité ; « qualification » ferait penser à un diplôme.
3. **demande d'intervention (DI)** : défaut « work request » ; autre « maintenance request ». Plus court, et cohérent avec « work order ».
4. **gamme** : défaut « task list » ; autres « job plan » (IBM Maximo), « procedure ». « Task list » est neutre et couvre aussi les listes de contrôle.
5. **ordre de travail (OT)** : défaut « work order » (« WO ») ; autre « job » (« job card »). « Work order » est le terme standard des GMAO.
6. **repère** : défaut « tag » ; autres « asset number », « equipment ID ». « Tag » est court et courant dans les ateliers.
7. **parc** : défaut « equipment register » ; autres « asset register », « plant ». Le menu court dirait « Equipment » : à confirmer.
8. **magasin** : défaut « stores » ; autres « storeroom », « warehouse ». « Stores » est l'usage britannique en maintenance.
9. **contrôle réglementaire** : défaut « statutory inspection » ; autre « regulatory check ». « Statutory » est l'usage britannique pour les contrôles imposés par la loi.
10. **technicien** : défaut « technician » ; autre « engineer ». « Engineer » est très courant au Royaume-Uni (« maintenance engineer »), mais peut sembler trop élevé pour un technicien.
11. **responsable** : défaut « manager » ; autres « supervisor », « maintenance manager ». Le profil règle les paramètres : « manager » suffit.
12. **inventaire** (comptage de stock) : défaut « stocktake » ; autre « stock count ». « Stocktake » est britannique ; « inventory » serait un faux ami (= le stock).
13. **panne** : défaut « breakdown » ; autre « failure ». « Breakdown » est la panne vécue sur le terrain ; « failure » est gardé pour les codes de défaillance.
14. **poste** (autre ordinateur du réseau) : défaut « workstation » ; autres « device », « computer ». « Workstation » est un peu formel, mais sans ambiguïté.
