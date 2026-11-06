'use strict';
// Textes anglais de Prévo : anglais britannique, locale en-GB (chantier multilingue, Lot 3, T264).
// Mêmes sections que js/i18n/fr.js, dans le même ordre : une section par domaine. On traduit par groupes de domaines,
// une tâche par groupe, chacune dans ses sections seulement : jamais deux tâches sur les mêmes lignes. Dans chaque
// bloc : les clés de la même section de fr.js, triées, une par ligne, chaînes entre apostrophes simples, échappements
// gardés (jamais d'espace insécable écrit en clair : \u00a0, \u202f), mêmes variables {…} que le français ; un
// pluriel { one, other } là où le français en a un, un texte simple ailleurs. Vocabulaire : docs/GLOSSAIRE.md.
// Clé absente : texte français affiché (avertissement dans la console). L'aide longue (aide.*) ira dans
// js/i18n/aide/en.js. Contrôle : py -X utf8 outils/controler_textes.py --langue en [--domaine <domaine>].
// L'anglais n'est pas encore déclaré dans js/i18n/langues.js : rien ne charge ce fichier pour l'instant.

// ==== section commun ====
I18n.ajouter('en', {
  'commun.bouton.actualiser': 'Refresh',
  'commun.bouton.ajouter': 'Add',
  'commun.bouton.annuler': 'Cancel',
  'commun.bouton.continuer': 'Continue',
  'commun.bouton.desactiver': 'Deactivate',
  'commun.bouton.enregistrer': 'Save',
  'commun.bouton.fermer': 'Close',
  'commun.bouton.imprimer': 'Print',
  'commun.bouton.modifier': 'Edit',
  'commun.champ.article': 'Item',
  'commun.champ.commentaire': 'Comment',
  'commun.champ.criticite': 'Criticality',
  'commun.champ.date': 'Date',
  'commun.champ.designation': 'Designation',
  'commun.champ.equipement': 'Equipment',
  'commun.champ.prenom': 'First name',
  'commun.champ.priorite': 'Priority',
  'commun.champ.prix_unitaire': 'Unit price',
  'commun.champ.quantite': 'Quantity',
  'commun.champ.reference': 'Reference',
  'commun.champ.repere': 'Tag',
  'commun.champ.statut': 'Status',
  'commun.champ.symptome': 'Symptom',
  'commun.champ.technicien': 'Technician',
  'commun.liste.non_choisi': '(none selected)',
  'commun.message.aucune_modification': 'No changes to save.',
  'commun.message.champ_obligatoire': 'required field',
  'commun.message.erreur_inconnue': 'unknown error',
  'commun.message.fichier_trop_volumineux': 'This file is too large (9 MB maximum).',
  'commun.message.ot_introuvable': 'Work order {otId} cannot be found.',
  'commun.message.saisi_sur_autre_poste': 'It may have been entered on another workstation: refresh.',
  'commun.message.serveur_a_repondu': 'The server replied “{status}”.',
});
// ==== fin commun ====

// ==== section schema ====
I18n.ajouter('en', {
  'schema.achats.article_id': 'Item',
  'schema.achats.date': 'Date',
  'schema.achats.date_reception': 'Date received',
  'schema.achats.fournisseur_id': 'Supplier',
  'schema.achats.id': 'ID',
  'schema.achats.prix_unitaire': 'Unit price',
  'schema.achats.quantite': 'Quantity',
  'schema.achats.statut': 'Status',
  'schema.article_equipement.article_id': 'Item',
  'schema.article_equipement.equipement_id': 'Equipment',
  'schema.article_equipement.id': 'ID',
  'schema.article_equipement.quantite': 'Quantity',
  'schema.articles.actif': 'Active',
  'schema.articles.critique': 'Critical item',
  'schema.articles.delai_jours': 'Supply lead time (days)',
  'schema.articles.designation': 'Designation',
  'schema.articles.emplacement': 'Bin location',
  'schema.articles.fabricant': 'Manufacturer',
  'schema.articles.fournisseur_id': 'Supplier',
  'schema.articles.id': 'ID',
  'schema.articles.point_commande': 'Reorder point',
  'schema.articles.prix_unitaire': 'Unit price',
  'schema.articles.qte_commande': 'Order quantity',
  'schema.articles.ref_fabricant': 'Manufacturer part number',
  'schema.articles.reference': 'Reference',
  'schema.articles.stock': 'Stock',
  'schema.articles.stock_securite': 'Safety stock',
  'schema.articles.unite': 'Unit',
  'schema.codes_defaillance.code': 'Code',
  'schema.codes_defaillance.famille': 'Family',
  'schema.codes_defaillance.id': 'ID',
  'schema.codes_defaillance.libelle': 'Label',
  'schema.compteurs.equipement_id': 'Equipment',
  'schema.compteurs.id': 'ID',
  'schema.compteurs.libelle': 'Label',
  'schema.compteurs.unite': 'Unit',
  'schema.controles_reglementaires.derniere_date': 'Last inspection date',
  'schema.controles_reglementaires.equipement_id': 'Equipment',
  'schema.controles_reglementaires.id': 'ID',
  'schema.controles_reglementaires.nature': 'Type of inspection',
  'schema.controles_reglementaires.observations': 'Observations',
  'schema.controles_reglementaires.observations_levees': 'Observations cleared',
  'schema.controles_reglementaires.organisme': 'Inspection body',
  'schema.controles_reglementaires.periodicite_mois': 'Interval (months)',
  'schema.controles_reglementaires.prochaine_date': 'Next inspection date',
  'schema.controles_reglementaires.rapport': 'Report',
  'schema.controles_reglementaires.texte_reference': 'Reference text',
  'schema.demandes.date_decision': 'Decision date',
  'schema.demandes.date_heure': 'Date and time of request',
  'schema.demandes.demandeur': 'Requester',
  'schema.demandes.description': 'Description',
  'schema.demandes.equipement_id': 'Equipment',
  'schema.demandes.id': 'ID',
  'schema.demandes.impact': 'Impact',
  'schema.demandes.motif_decision': 'Reason for decision',
  'schema.demandes.ot_id': 'Linked work order',
  'schema.demandes.ot_origine_id': 'Originating WO (preventive)',
  'schema.demandes.photo': 'Photo',
  'schema.demandes.statut': 'Status',
  'schema.demandes.symptome': 'Symptom observed',
  'schema.demandes.symptome_code': 'Symptom code',
  'schema.equipements.actif': 'Active',
  'schema.equipements.consignation': 'Isolation',
  'schema.equipements.criticite': 'Criticality',
  'schema.equipements.date_mes': 'Date in service',
  'schema.equipements.designation': 'Designation',
  'schema.equipements.document': 'Document',
  'schema.equipements.habilitation_requise': 'Authorisation required',
  'schema.equipements.heures_fonct_jour': 'Operating hours per day',
  'schema.equipements.id': 'ID',
  'schema.equipements.localisation_id': 'Location',
  'schema.equipements.marque': 'Make',
  'schema.equipements.modele': 'Model',
  'schema.equipements.num_serie': 'Serial number',
  'schema.equipements.parent_id': 'Parent equipment',
  'schema.equipements.repere': 'Tag',
  'schema.equipements.statut': 'Status',
  'schema.equipements.valeur_remplacement': 'Replacement value (€ excl. VAT)',
  'schema.fournisseurs.contact': 'Contact',
  'schema.fournisseurs.email': 'Email',
  'schema.fournisseurs.id': 'ID',
  'schema.fournisseurs.nom': 'Name',
  'schema.fournisseurs.telephone': 'Telephone',
  'schema.gamme_operations.gamme_id': 'Task list',
  'schema.gamme_operations.id': 'ID',
  'schema.gamme_operations.operation': 'Task',
  'schema.gamme_operations.ordre': 'Sequence',
  'schema.gamme_operations.valeur_attendue': 'Expected value',
  'schema.gammes.actif': 'Active',
  'schema.gammes.avance_jours': 'Lead time (days)',
  'schema.gammes.compteur_id': 'Meter',
  'schema.gammes.consignes': 'Instructions',
  'schema.gammes.declencheur': 'Trigger',
  'schema.gammes.derniere_realisation': 'Last completed',
  'schema.gammes.equipement_id': 'Equipment',
  'schema.gammes.id': 'ID',
  'schema.gammes.libelle': 'Label',
  'schema.gammes.periodicite_jours': 'Interval (days)',
  'schema.gammes.periodicite_unites': 'Interval (meter units)',
  'schema.gammes.prochaine_echeance': 'Next due date',
  'schema.gammes.releve_derniere_realisation': 'Meter reading at last completion',
  'schema.gammes.seuil': 'Threshold',
  'schema.gammes.temps_prevu_h': 'Planned time (hours)',
  'schema.habilitations.date_echeance': 'Expiry date',
  'schema.habilitations.date_obtention': 'Date obtained',
  'schema.habilitations.id': 'ID',
  'schema.habilitations.intitule': 'Name',
  'schema.habilitations.technicien_id': 'Technician',
  'schema.journal.action': 'Action',
  'schema.journal.date_heure': 'Date and time',
  'schema.journal.id': 'ID',
  'schema.journal.id_ligne': 'Row ID',
  'schema.journal.poste': 'Workstation',
  'schema.journal.profil': 'Profile',
  'schema.journal.table': 'Table',
  'schema.localisations.id': 'ID',
  'schema.localisations.libelle': 'Label',
  'schema.localisations.parent_id': 'Parent location',
  'schema.localisations.type': 'Type',
  'schema.mouvements_stock.article_id': 'Item',
  'schema.mouvements_stock.commentaire': 'Comment',
  'schema.mouvements_stock.date': 'Date and time',
  'schema.mouvements_stock.id': 'ID',
  'schema.mouvements_stock.ot_id': 'Work order',
  'schema.mouvements_stock.quantite': 'Quantity',
  'schema.mouvements_stock.type': 'Type',
  'schema.mouvements_stock.utilisateur': 'User',
  'schema.ordres_travail.anomalie_constatee': 'Fault found',
  'schema.ordres_travail.arret_production': 'Production stoppage',
  'schema.ordres_travail.astuce': 'Tip for next time',
  'schema.ordres_travail.cause_code': 'Cause code',
  'schema.ordres_travail.compte_rendu': 'Job report',
  'schema.ordres_travail.consignes': 'Instructions',
  'schema.ordres_travail.cout_soustraitance': 'Subcontracting cost',
  'schema.ordres_travail.date_cloture_admin': 'Administrative closure date',
  'schema.ordres_travail.date_cloture_tech': 'Technical closure date',
  'schema.ordres_travail.date_creation': 'Creation date',
  'schema.ordres_travail.date_debut': 'Start date',
  'schema.ordres_travail.date_fin': 'End date',
  'schema.ordres_travail.date_prevue': 'Planned date',
  'schema.ordres_travail.di_id': 'Work request',
  'schema.ordres_travail.duree_arret_h': 'Downtime (hours)',
  'schema.ordres_travail.equipement_id': 'Equipment',
  'schema.ordres_travail.gamme_id': 'Preventive task list',
  'schema.ordres_travail.id': 'ID',
  'schema.ordres_travail.motif_annulation': 'Reason for cancellation',
  'schema.ordres_travail.motif_attente': 'Reason for hold',
  'schema.ordres_travail.origine': 'Origin',
  'schema.ordres_travail.ot_lie_id': 'Linked work order',
  'schema.ordres_travail.priorite': 'Priority',
  'schema.ordres_travail.remede_code': 'Remedy code',
  'schema.ordres_travail.remise_service': 'Returned to service safely',
  'schema.ordres_travail.statut': 'Status',
  'schema.ordres_travail.symptome_code': 'Symptom code',
  'schema.ordres_travail.technicien_id': 'Technician',
  'schema.ordres_travail.temps_prevu_h': 'Planned time (hours)',
  'schema.ordres_travail.titre': 'Title',
  'schema.ordres_travail.travail_a_faire': 'Work to be done',
  'schema.ordres_travail.type': 'Type',
  'schema.ot_operations.fait': 'Done',
  'schema.ot_operations.id': 'ID',
  'schema.ot_operations.operation': 'Task',
  'schema.ot_operations.ordre': 'Sequence',
  'schema.ot_operations.ot_id': 'Work order',
  'schema.ot_operations.valeur_attendue': 'Expected value',
  'schema.ot_operations.valeur_mesuree': 'Measured value',
  'schema.ot_pieces.article_id': 'Item',
  'schema.ot_pieces.id': 'ID',
  'schema.ot_pieces.ot_id': 'Work order',
  'schema.ot_pieces.quantite_prevue': 'Planned quantity',
  'schema.ot_temps.date': 'Date',
  'schema.ot_temps.heures': 'Hours',
  'schema.ot_temps.id': 'ID',
  'schema.ot_temps.ot_id': 'Work order',
  'schema.ot_temps.technicien_id': 'Technician',
  'schema.parametres.cle': 'Key',
  'schema.parametres.valeur': 'Value',
  'schema.releves.compteur_id': 'Meter',
  'schema.releves.date': 'Date',
  'schema.releves.id': 'ID',
  'schema.releves.utilisateur': 'User',
  'schema.releves.valeur': 'Value',
  'schema.tables.achats': 'Purchases',
  'schema.tables.article_equipement': 'Parts by equipment',
  'schema.tables.articles': 'Items (spare parts)',
  'schema.tables.codes_defaillance': 'Failure codes',
  'schema.tables.compteurs': 'Meters',
  'schema.tables.controles_reglementaires': 'Statutory inspections',
  'schema.tables.demandes': 'Work requests',
  'schema.tables.equipements': 'Equipment',
  'schema.tables.fournisseurs': 'Suppliers',
  'schema.tables.gamme_operations': 'Task list tasks',
  'schema.tables.gammes': 'Preventive task lists',
  'schema.tables.habilitations': 'Authorisations',
  'schema.tables.journal': 'Change log',
  'schema.tables.localisations': 'Locations',
  'schema.tables.mouvements_stock': 'Stock movements',
  'schema.tables.ordres_travail': 'Work orders',
  'schema.tables.ot_operations': 'Work order tasks',
  'schema.tables.ot_pieces': 'Work order planned parts',
  'schema.tables.ot_temps': 'Time spent on work orders',
  'schema.tables.parametres': 'Settings',
  'schema.tables.releves': 'Meter readings',
  'schema.tables.techniciens': 'Technicians',
  'schema.tables.wiki_journal': 'Wiki log',
  'schema.tables.wiki_pages': 'Wiki pages',
  'schema.techniciens.actif': 'Active',
  'schema.techniciens.capacite_h_semaine': 'Capacity (hours per week)',
  'schema.techniciens.id': 'ID',
  'schema.techniciens.metier': 'Trade',
  'schema.techniciens.nom': 'Name',
  'schema.techniciens.prenom': 'First name',
  'schema.techniciens.taux_horaire': 'Hourly rate',
  'schema.wiki_journal.anterieure': 'Previous job',
  'schema.wiki_journal.changements': 'Changes',
  'schema.wiki_journal.contradictions': 'Contradictions',
  'schema.wiki_journal.cree_le': 'Created on',
  'schema.wiki_journal.date_intervention': 'Job date',
  'schema.wiki_journal.decide_le': 'Decided on',
  'schema.wiki_journal.decide_par': 'Decided by',
  'schema.wiki_journal.essais': 'Attempts',
  'schema.wiki_journal.id': 'ID',
  'schema.wiki_journal.modele': 'Model',
  'schema.wiki_journal.motif': 'Reason',
  'schema.wiki_journal.nature': 'Nature',
  'schema.wiki_journal.ordre': 'Processing order',
  'schema.wiki_journal.ot_id': 'Work order',
  'schema.wiki_journal.pages': 'Pages affected',
  'schema.wiki_journal.raisons': 'Reasons for declining',
  'schema.wiki_journal.statut': 'Status',
  'schema.wiki_journal.traite_le': 'Processed on',
  'schema.wiki_pages.article_id': 'Item',
  'schema.wiki_pages.cause_code': 'Cause code',
  'schema.wiki_pages.cle': 'Key (comparable title)',
  'schema.wiki_pages.cree_le': 'Created on',
  'schema.wiki_pages.derniere_entree': 'Last entry applied',
  'schema.wiki_pages.equipement_id': 'Equipment',
  'schema.wiki_pages.id': 'ID',
  'schema.wiki_pages.liens': 'Linked pages',
  'schema.wiki_pages.modele': 'Model',
  'schema.wiki_pages.modifie_le': 'Modified on',
  'schema.wiki_pages.origine': 'Origin',
  'schema.wiki_pages.ot_cites': 'WOs cited',
  'schema.wiki_pages.rattache_a': 'Attached to page',
  'schema.wiki_pages.statut': 'Status',
  'schema.wiki_pages.texte': 'Text',
  'schema.wiki_pages.titre': 'Title',
  'schema.wiki_pages.type': 'Type',
  'schema.wiki_pages.valide_le': 'Validated on',
  'schema.wiki_pages.valide_par': 'Validated by',
  'schema.wiki_pages.version': 'Version',
});
// ==== fin schema ====

// ==== section valeurs ====
I18n.ajouter('en', {
  'valeurs.achats.statut.commandée': 'ordered',
  'valeurs.achats.statut.demandée': 'requested',
  'valeurs.achats.statut.reçue': 'received',
  'valeurs.codes_defaillance.famille.cause': 'cause',
  'valeurs.codes_defaillance.famille.remède': 'remedy',
  'valeurs.codes_defaillance.famille.symptôme': 'symptom',
  'valeurs.demandes.impact.arrêt': 'stoppage',
  'valeurs.demandes.impact.dégradé': 'degraded',
  'valeurs.demandes.impact.gêne': 'disruption',
  'valeurs.demandes.impact.sécurité': 'safety',
  'valeurs.demandes.statut.Acceptée': 'Accepted',
  'valeurs.demandes.statut.Différée': 'Deferred',
  'valeurs.demandes.statut.Nouvelle': 'New',
  'valeurs.demandes.statut.Refusée': 'Declined',
  'valeurs.demandes.statut.Regroupée': 'Merged',
  'valeurs.equipements.criticite.A': 'A',
  'valeurs.equipements.criticite.B': 'B',
  'valeurs.equipements.criticite.C': 'C',
  'valeurs.equipements.statut.arrêt': 'stopped',
  'valeurs.equipements.statut.en service': 'in service',
  'valeurs.equipements.statut.rebut': 'scrapped',
  'valeurs.gammes.declencheur.compteur': 'meter',
  'valeurs.gammes.declencheur.date': 'date',
  'valeurs.gammes.declencheur.seuil': 'threshold',
  'valeurs.localisations.type.atelier': 'workshop',
  'valeurs.localisations.type.ligne': 'line',
  'valeurs.localisations.type.site': 'site',
  'valeurs.mouvements_stock.type.entrée': 'receipt',
  'valeurs.mouvements_stock.type.inventaire': 'stocktake',
  'valeurs.mouvements_stock.type.retour': 'return',
  'valeurs.mouvements_stock.type.sortie': 'issue',
  'valeurs.ordres_travail.origine.DI': 'work request',
  'valeurs.ordres_travail.origine.manuel': 'manual',
  'valeurs.ordres_travail.origine.préventif': 'preventive',
  'valeurs.ordres_travail.origine.urgence': 'emergency',
  'valeurs.ordres_travail.priorite.P1': 'P1',
  'valeurs.ordres_travail.priorite.P2': 'P2',
  'valeurs.ordres_travail.priorite.P3': 'P3',
  'valeurs.ordres_travail.priorite.P4': 'P4',
  'valeurs.ordres_travail.statut.Annulé': 'Cancelled',
  'valeurs.ordres_travail.statut.Clôturé administrativement': 'Administratively closed',
  'valeurs.ordres_travail.statut.Clôturé techniquement': 'Technically closed',
  'valeurs.ordres_travail.statut.Créé': 'Created',
  'valeurs.ordres_travail.statut.En attente': 'On hold',
  'valeurs.ordres_travail.statut.En cours': 'In progress',
  'valeurs.ordres_travail.statut.Planifié': 'Scheduled',
  'valeurs.ordres_travail.statut.Préparé': 'Prepared',
  'valeurs.ordres_travail.type.amélioration': 'improvement',
  'valeurs.ordres_travail.type.correctif différé': 'deferred corrective',
  'valeurs.ordres_travail.type.correctif immédiat': 'immediate corrective',
  'valeurs.ordres_travail.type.préventif conditionnel': 'condition-based preventive',
  'valeurs.ordres_travail.type.préventif systématique': 'fixed-interval preventive',
  'valeurs.ordres_travail.type.réglementaire': 'statutory',
  'valeurs.wiki_journal.nature.décision': 'decision',
  'valeurs.wiki_journal.nature.ingestion': 'ingestion',
  'valeurs.wiki_journal.nature.manuel': 'manual',
  'valeurs.wiki_journal.statut.appliquée': 'applied',
  'valeurs.wiki_journal.statut.en file': 'queued',
  'valeurs.wiki_journal.statut.refusée': 'declined',
  'valeurs.wiki_journal.statut.rejetée': 'rejected',
  'valeurs.wiki_journal.statut.rien à ajouter': 'nothing to add',
  'valeurs.wiki_journal.statut.validée': 'validated',
  'valeurs.wiki_journal.statut.à refaire': 'to be redone',
  'valeurs.wiki_journal.statut.à valider': 'to be validated',
  'valeurs.wiki_pages.origine.IA': 'AI',
  'valeurs.wiki_pages.origine.IA et manuel': 'AI and manual',
  'valeurs.wiki_pages.origine.manuel': 'manual',
  'valeurs.wiki_pages.statut.active': 'active',
  'valeurs.wiki_pages.statut.archivée': 'archived',
  'valeurs.wiki_pages.type.composant': 'component',
  'valeurs.wiki_pages.type.mode': 'failure mode',
  'valeurs.wiki_pages.type.savoir-faire': 'know-how',
  'valeurs.wiki_pages.type.équipement': 'equipment',
});
// ==== fin valeurs ====

// ==== section socle ====
I18n.ajouter('en', {
  'socle.analyser.ligne_contient_plus_valeurs': '{reperage}: this row contains more values than the header has columns; the value “{valeurIgnoree}” (column {colonneIgnoree}) is ignored.',
  'socle.analyser.ligne_structure_fichier_abimee': '{descriptionLibelle}, row {numero} of {fichier}: damaged file structure ({erreurMessage}), for example an unclosed quotation mark. The values in this row and the following ones may be shifted.',
  'socle.analyser.pas_utf_8_sans': '{descriptionLibelle}: {fichier} is not in UTF-8 (probably saved by Excel as “CSV (semicolon delimited)”); it was read as Windows-1252. It will be rewritten in UTF-8 the next time the table is changed.',
  'socle.analyser.reperage_champ_libelle_contient_lu_valeur': '{reperage}: “{champLibelle}” contains “{luValeur}”, {explication}.',
  'socle.app.gmao': 'CMMS',
  'socle.app.menu': 'Menu',
  'socle.app.propos': 'About',
  'socle.appliquer_repli.deplier_menu': 'Expand menu',
  'socle.appliquer_repli.replier_menu': 'Collapse menu',
  'socle.associer_colonnes.colonne_apparait_deux_fois': '{descriptionLibelle}: the column “{nomColonne}” appears twice in {fichier}; the second is kept separately under the name “{nomConserve}” and is not used by Prévo.',
  'socle.associer_colonnes.colonne_fait_pas_partie': '{descriptionLibelle}: the column “{nomConserve}” in {fichier} is not part of Prévo; it is kept as it is (rewritten at the end of the file).',
  'socle.associer_colonnes.colonne_numero': 'column {numero}',
  'socle.badge_priorite.priorite_code': 'Priority {code}',
  'socle.badge_priorite.priorite_inconnue': 'Unknown priority',
  'socle.bandeau_changement.donnees_ont_change_autre': 'Data has changed on another workstation',
  'socle.bandeau_demo.demo_rien_enregistre': 'Demo — nothing is saved',
  'socle.bandeau_fichiers_abimes.fichier_abime': 'Damaged file',
  'socle.bandeau_fichiers_abimes.fichiers_abimes': 'Damaged files',
  'socle.bandeau_fichiers_abimes.prevenez_responsable': '<b>{titre}: tell the manager.</b> {suite}',
  'socle.bandeau_fichiers_abimes.tant_ils_sont_pas': 'Until they are repaired, Prévo refuses any save that affects them, without losing anything.',
  'socle.bandeau_fichiers_abimes.tant_pas_repare_prevo': 'Until it is repaired, Prévo refuses any save that affects it, without losing anything.',
  'socle.bandeau_fichiers_abimes.tete_coupe_guillemet_non': '<b>{titre}: {fichiers}.</b> Truncated header, unclosed quotation mark or values beyond the header: Prévo no longer saves it, so that nothing is lost. Correct the file, restore a backup or import a ZIP; the details are in Settings › Database check.',
  'socle.bandeau_fichiers_laisses.fichier_abime_laisse_tel': 'Damaged file left as it is',
  'socle.bandeau_fichiers_laisses.fichiers_abimes_laisses_tels': 'Damaged files left as they are',
  'socle.bandeau_fichiers_laisses.tete_illisible_lignes_reecriture': '<b>{titre}: {fichiers}.</b> Unreadable header, or rows that a rewrite would lose: Prévo does not rewrite it to move it to format {version}. Correct the file, or restore a backup; the details are in Settings › Database check.',
  'socle.bandeau_format_en_attente.fichiers_donnees_sont_pas': '<b>The data files are not yet in format {courant}</b> (format {depart} found). The Prévo server updates them when it starts, after a backup; this browser does not touch them. If this message stays on screen, close Excel (and any program that has opened a data file), then restart Prévo. Until then, overdue preventive WOs are not generated automatically.',
  'socle.btn_base_demo.atelier_fictif_complet_pourrez': 'A complete fictional workshop, which you can edit or replace',
  'socle.btn_base_demo.partir_donnees_demo': 'Start from the demo data',
  'socle.btn_base_vide.23_fichiers_csv_seuls': '23 CSV files with only their column headers',
  'socle.btn_base_vide.creer_base_vide': 'Create an empty database',
  'socle.btn_demo.atelier_fictif_rien_enregistre': 'Fictional workshop, nothing is saved',
  'socle.btn_demo.essayer_donnees_demo': 'Try it with the demo data',
  'socle.btn_dossier.choisir_dossier_donnees': 'Choose the data folder',
  'socle.btn_dossier.fichiers_csv_restent_pc': 'The CSV files stay on this PC (Chrome or Edge)',
  'socle.btn_explications.explications': 'Explanations',
  'socle.btn_explications.revoir_explication_ecran': 'Review the explanation for this screen',
  'socle.btn_explications_mobile.explications_ecran': 'Explanations for this screen',
  'socle.btn_export_demo.exporter_zip': 'Export as ZIP',
  'socle.btn_replier.replier_menu': 'Collapse menu',
  'socle.btn_reprendre.reprendre_dossier_precedent': 'Resume the previous folder',
  'socle.btn_telecharger.gratuit_libre_installez_travailler': 'Free and open source: install it to work on your own data.',
  'socle.btn_telecharger.telecharger_prevo': 'Download Prévo',
  'socle.changer_profil.profil_libelle_affiche': 'Profile: {libelleAffiche}.',
  'socle.chargement.chargement': 'Loading…',
  'socle.charger_echarts.bibliotheque_graphiques_js_lib': 'The charts library (js/lib/echarts.min.js) could not be loaded.',
  'socle.charger_image.image_peut_pas_etre': 'This image cannot be read (unsupported format?).',
  'socle.charger_script_demo.jeu_demo_js_demo': 'The demo data set (js/demo-donnees.js) could not be loaded.',
  'socle.charger_sheet_js.bibliotheque_lecture_fichiers_excel': 'The Excel file reading library (js/lib/xlsx.full.min.js) could not be loaded.',
  'socle.choisir.choix_dossier': 'folder selection',
  'socle.confirmer.confirmation': 'Confirmation',
  'socle.confirmer.confirmer': 'Confirm',
  'socle.connexion_avec_compte.ai_compte': 'I have an account',
  'socle.connexion_changer.enregistrer_continuer': 'Save and continue',
  'socle.connexion_enrolement.entrez_nom': 'Enter your name',
  'socle.connexion_enrolement.nom_inscrit_demandes_appareil': 'Your name is recorded on your requests; this device will stay recognised without a password.',
  'socle.connexion_formulaire.forme_prenom_nom_donne': 'In the form first name.surname, given by the manager.',
  'socle.connexion_formulaire.identifiant': 'Username',
  'socle.connexion_formulaire.mot_passe': 'Password',
  'socle.connexion_formulaire.rester_connecte_appareil': 'Stay signed in on this device',
  'socle.connexion_mdp_deconnexion.deconnecter': 'Sign out',
  'socle.connexion_mot_de_passe_panneau.12_caracteres_moins_256': 'At least 12 characters, at most 256, no composition rules: a passphrase of several words is recommended.',
  'socle.connexion_mot_de_passe_panneau.confirmation': 'Confirmation',
  'socle.connexion_mot_de_passe_panneau.mot_passe_actuel_provisoire': 'Current password (temporary)',
  'socle.connexion_mot_de_passe_panneau.nouveau_mot_passe': 'New password',
  'socle.connexion_sous_titre.chaque_personne_compte_serveur': 'Each person has their own account; the server checks access rights.',
  'socle.connexion_titre.connexion': 'Sign in',
  'socle.connexion_valider.connecter': 'Sign in',
  'socle.constructor.action_refusee': 'Action refused.',
  'socle.constructor.donnees_viennent_version_plus': 'This data comes from a more recent version of Prévo (file format {format}; this version reads up to format {version}): it is opened read-only and nothing is saved. Open it with the latest version of Prévo.',
  'socle.constructor.fichier_abime_tete_coupe': 'The file {fichier} is damaged (truncated header, unclosed quotation mark or values beyond the header): Prévo no longer saves it, so that nothing is lost. Correct it, restore a backup or import a ZIP (Settings); the details are in Settings › Database check.',
  'socle.constructor.fichier_ete_modifie_meme': 'The file was changed at the same time on another workstation.',
  'socle.constructor.lecture_ecriture_fichier_impossible': 'The file cannot be read or written.',
  'socle.construire_menus.plus': 'More',
  'socle.controler_coherence.demande_acceptee_mais_aucun': 'Request {id}: it is “Accepted” but no work order is linked to it. Reopen it or link it to its work order.',
  'socle.controler_coherence.demande_acceptee_mais_ordre': 'Request {id}: it is “Accepted” but its work order “{ot_id}” does not exist.',
  'socle.controler_coherence.ordre_travail_vient_demande': 'Work order {id}: it comes from request “{di_id}”, which is “{statut}” (neither accepted nor merged). Accept or merge the request, or cancel the work order.',
  'socle.controler_coherence.sans_identifiant': '(no ID)',
  'socle.controler_identifiants.identifiant_apparait_plusieurs_fois': '{descriptionLibelle}: the ID “{cle}” appears several times in {fichier} (data row no. {numero}). Prévo only finds the first row: give the others a unique ID.',
  'socle.controler_identifiants.pas_identifiant_colonne_vide': '{descriptionLibelle}: the {reperageLigne} in {fichier} has no ID (column “{cle}” is empty). Fill it in or delete the row in the file.',
  'socle.controler_references.existe_mais_lieu': 'exists in {descriptionCibleLibelle} but with {familleTrouvee} instead of {filtre}',
  'socle.controler_references.existe_pas': 'does not exist in {descriptionCibleLibelle} ({filtre})',
  'socle.controler_references.existe_pas_sans_filtre': 'does not exist in {descriptionCibleLibelle}',
  'socle.controler_references.reperage_champ_libelle_vaut_valeur': '{reperage}: “{champLibelle}” is “{valeur}”, which {explication}.',
  'socle.controler_wiki.changements_illisibles': '(unreadable changes)',
  'socle.controler_wiki.cite_aucun_ot': 'it cites no WO.',
  'socle.controler_wiki.cite_ot_existe_pas': 'it cites WO “{ot}”, which does not exist.',
  'socle.controler_wiki.entree_journal_wiki_contradiction': { one: 'Wiki log entry {entreeId}: contradiction open for more than {n} day on page “{page}”.', other: 'Wiki log entry {entreeId}: contradiction open for more than {n} days on page “{page}”.' },
  'socle.controler_wiki.entree_journal_wiki_validee': 'Wiki log entry {entreeId}: it is “validated” but its changes are not in the pages ({pages}).',
  'socle.controler_wiki.lien_vers_page_inexistante': 'link to a page that does not exist or is archived (“{lien}”).',
  'socle.controler_wiki.meme_titre_page_deux': 'same title as page {page} (two active pages with the same key).',
  'socle.controler_wiki.page_wiki': 'Wiki page {id} (“{pageTitre}”): {message}',
  'socle.controler_wiki.rattachee_page_archivee': 'attached to the archived page “{mereTitre}” ({mereId}).',
  'socle.controler_wiki.sous_page_page_archivee': 'sub-page of the archived page “{mereTitre}” ({mereId}).',
  'socle.controler_wiki.type_page_retire_panne': 'page type withdrawn (“{pageType}”: a breakdown is a page calculated by Prévo); archive it.',
  'socle.creer.ajout_fichier': 'append to file',
  'socle.creer.aucune_table_restauree': 'none',
  'socle.creer.contenu_ajouter_doit_commencer': 'The content to append must start with the header row.',
  'socle.creer.contenu_ajouter_doit_etre': 'The content to append must be encoded in UTF-8.',
  'socle.creer.demo_rien_enregistre': 'Demo — nothing is saved',
  'socle.creer.document_existe_deja': 'The document {nom} already exists.',
  'socle.creer.document_porte_deja_nom': 'A document already has this name.',
  'socle.creer.dossier_name': 'Folder “{name}”',
  'socle.creer.enregistrement_document': 'saving the document',
  'socle.creer.enregistrement_table': 'saving the table',
  'socle.creer.fichier_csv_ete_modifie': 'The file {nomTable}.csv was changed by another workstation.',
  'socle.creer.fichier_csv_existe_deja': 'The file {nomTable}.csv already exists.',
  'socle.creer.fichier_csv_existe_plus': 'The file {nomTable}.csv no longer exists.',
  'socle.creer.fichier_csv_pas_utf': 'The file {nomTable}.csv is not in UTF-8 (resaved by Excel?).',
  'socle.creer.fichier_vient_etre_modifie': 'The file {nomFichier} has just been changed by another workstation.',
  'socle.creer.indisponible_mode_demo_rien': 'Unavailable in demo mode: nothing is saved.',
  'socle.creer.lecture_document': 'reading the document',
  'socle.creer.lecture_nom_fichiers_abimes': 'reading {fichier}',
  'socle.creer.lecture_table': 'reading the table',
  'socle.creer.lecture_versions': 'reading the versions',
  'socle.creer.liste_sauvegardes': 'list of backups',
  'socle.creer.mise_jour': 'update of {fichier}',
  'socle.creer.nom_document_invalide': 'Invalid document name: “{nom}”.',
  'socle.creer.poste_inconnu': 'Unknown workstation',
  'socle.creer.restauration': 'restore',
  'socle.creer.restauration_interrompue_table_tables': '{interrompueMessage} Restore interrupted at table {table}; tables already restored: {dejaRestaurees}. The state before the restore is in backup {copieSecurite}.',
  'socle.creer.sauvegarde': 'backup',
  'socle.creer.sauvegarde_avant_mise_jour': 'backup before the Prévo update',
  'socle.creer.sauvegarde_incomplete_copie_interrompue': 'The backup {nom} is incomplete (copy interrupted or in progress): choose another one.',
  'socle.creer.sauvegarde_introuvable': 'Backup not found: {nom}.',
  'socle.creer.serveur_host': 'Server {host}',
  'socle.creer.table_absente_sauvegarde': 'The table {table} is not in this backup.',
  'socle.creer.tables_doit_etre_liste': '“tables” must be a list of table names.',
  'socle.creer.tete_csv_different': 'The header of {nomTable}.csv is different.',
  'socle.creer.version_application_inconnue_rien': 'Unknown application version: nothing is backed up.',
  'socle.decaler_dates.stockage_demo_decaler_dates_dates_attendues': 'StockageDemo.decalerDates: dates expected in YYYY-MM-DD format.',
  'socle.deconnecter.appareil_enrole_sans_mot': 'This device is enrolled without a password: only the manager can revoke it (Team › Access).',
  'socle.definir_titre.prevo': 'Prévo',
  'socle.definir_titre.prevo_gmao': 'Prévo — CMMS',
  'socle.definir_titre.texte_prevo': '{texte} — Prévo',
  'socle.demander_base_vide.aucun_fichier_trouve': { one: 'The Prévo file was not found ({stockage}). What would you like to start with?', other: 'None of the {n} Prévo files was found ({stockage}). What would you like to start with?' },
  'socle.demander_motif.motif': 'Reason',
  'socle.demander_motif.motif_obligatoire': 'The reason is required.',
  'socle.demander_motif.valider': 'Confirm',
  'socle.demarrage.navigateur_sait_pas_ouvrir': '<b>This browser cannot open a folder.</b> To work on your files, use Chrome or Edge on a computer. In the meantime, the demo works here.',
  'socle.depuis_fichiers.impossible_lire_fichier': 'Cannot read the file {name}.',
  'socle.description_table.donnees_csv_table_inconnue': 'Donnees.csv: unknown table “{nomTable}”.',
  'socle.ecran.app_ecran_ecran_deja': 'App.ecran: the screen “{definitionId}” is already registered.',
  'socle.ecran.app_ecran_id_route': 'App.ecran: id, route (RegExp) and afficher(conteneur, parametres) are required.',
  'socle.ecran_base_vide.aucune_donnee_instant': 'No data yet',
  'socle.ecran_chargement.chargement_prevo': 'Loading Prévo…',
  'socle.ecran_demarrage.developpe_claude_anthropic_demande': 'Developed by Claude (Anthropic) at the request of Nicolas Briand — SELECTIS',
  'socle.ecran_demarrage.gmao_libre_atelier_demandes': 'Free CMMS for the workshop: requests, work orders, equipment register.',
  'socle.ecran_demarrage.prevo': 'Prévo',
  'socle.ecran_installation.installer_prevo': 'Install Prévo',
  'socle.ecran_profil.inscrit_journal_chaque_modification': 'Recorded in the change log with each change.',
  'socle.ecran_profil.nom_poste': 'Name of this workstation',
  'socle.ecran_profil.profil_adapte_ecrans_pas': 'The profile adapts the screens; it is not a security measure.',
  'socle.ecran_profil.utilise_poste': 'Who is using this workstation?',
  'socle.en_octets.contenu_fichier_illisible_texte': 'Unreadable file content (text or bytes expected).',
  'socle.en_octets.donnees_csv_octets_attendus': 'Donnees.csv: bytes expected (Uint8Array or ArrayBuffer).',
  'socle.en_octets.formats_manifeste_octets_attendus': 'Formats.manifeste: bytes expected (Uint8Array or ArrayBuffer).',
  'socle.en_octets.stockage_dossier_octets_attendus_uint': 'StockageDossier: bytes expected (Uint8Array or ArrayBuffer).',
  'socle.erreur_depuis_reponse.serveur_refuse_demande_code': 'The server refused the request (code {status}).',
  'socle.erreur_depuis_reponse.table': 'of this table',
  'socle.etat_poste.changer': 'change',
  'socle.etat_poste.changer_profil': 'Change profile',
  'socle.exiger_formats.donnees_registre_formats_js': 'Donnees: the formats registry (js/formats.js) must be loaded before js/donnees.js.',
  'socle.explication_valeur_illisible.fait_pas_partie_valeurs': 'is not one of the possible values ({valeurs})',
  'socle.explication_valeur_illisible.illisible': 'is unreadable',
  'socle.explication_valeur_illisible.pas_date_heure_valide': 'is not a valid date and time (accepted formats: 2024-03-15 08:30 or 15/03/2024 08:30)',
  'socle.explication_valeur_illisible.pas_date_valide_formats': 'is not a valid date (accepted formats: 2024-03-15 or 15/03/2024)',
  'socle.explication_valeur_illisible.pas_nombre_entier': 'is not a whole number',
  'socle.explication_valeur_illisible.pas_nombre_exemples_acceptes': 'is not a number (accepted examples: 7.5 or 7,5)',
  'socle.explication_valeur_illisible.pas_reconnu_comme_oui': 'is not recognised as yes or no (accepted values: 1, 0, oui, non, vrai, faux, x)',
  'socle.fichier_abime_depuis.depuis_le': { one: '{fichier}, since {date} ({n} day)', other: '{fichier}, since {date} ({n} days)' },
  'socle.fichier_abime_depuis.repere_aujourd_hui': '{fichier}, spotted today',
  'socle.html.ui_html_utilise_comme': 'UI.html is used as a template tag: UI.html`…`',
  'socle.installation_contenu.lecture_etat_installation': 'Reading the installation status…',
  'socle.installation_premiere_ligne.tant_installation_pas_terminee': 'Until the installation is complete, Prévo can only be reached from this PC.',
  'socle.installation_quitter.ouvrir_prevo_sans_terminer': 'Open Prévo without completing the installation (it stays reachable from this PC only)',
  'socle.lecture_seule.lecture_seule_donnees_viennent': '<b>Read-only: this data comes from a more recent version of Prévo</b> (file format {format}; this version reads up to format {version}). You can view it, but nothing is saved. Open it with the latest version of Prévo.',
  'socle.libelle_journal.demandeur_p_nom': 'Requester {nom}',
  'socle.libelle_journal.technicien_technicien_id': 'Technician {technicienId}',
  'socle.libelle_type.demandeur': 'Requester',
  'socle.libelle_type.responsable': 'Manager',
  'socle.libelle_type.technicien': 'Technician',
  'socle.lire_cellule.valeur_conservee_telle_quelle': '{explicationValeurIllisible}. Value kept as it is: to be corrected',
  'socle.lire_cellule.valeur_probablement_abimee_excel': 'value probably damaged by Excel (long number converted to scientific notation). Find the original value and enter it preceded by an apostrophe, for example \'123456789012345',
  'socle.lire_cellule.valeur_probablement_abimee_excel_formule': 'value probably damaged by Excel (text starting with “=”, “+” or “-” taken for a formula). Find the original text and enter it preceded by an apostrophe',
  'socle.liste_deroulante.choisir': '— Choose —',
  'socle.liste_deroulante.valeur_inconnue': '{valeurTexte} (unknown value)',
  'socle.menu.navigation_principale': 'Main navigation',
  'socle.message_conflit_persistant.fichier_modifie_meme_temps': 'The file {nomTable} is being changed at the same time on another workstation. Try again in a moment.',
  'socle.message_delai_depasse.serveur_prevo_met_trop': 'The Prévo server is taking too long to respond. Check the network, then try again; if you were saving, reload the page to see whether the change was made.',
  'socle.message_erreur.fichier_abime_prevenez_responsable': 'Damaged file: tell the manager. Nothing was saved; what you entered is still in the form.',
  'socle.message_erreur.fichier_abime_rien_ete': 'Damaged file: nothing was saved, so that nothing is lost; what you entered is still in the form. Restore today\'s backup (Settings › Backups) or import a ZIP; the details are in Settings › Database check.',
  'socle.message_erreur.fichier_abime_rien_ete_avec_fichier': 'Damaged file ({fichier}): nothing was saved, so that nothing is lost; what you entered is still in the form. Restore today\'s backup (Settings › Backups) or import a ZIP; the details are in Settings › Database check.',
  'socle.message_fichier_ouvert.fichier_dossier_donnees_ouvert': 'A file in the data folder is open in Excel or another program: close it, then try again.',
  'socle.message_fichier_ouvert.fichier_ouvert_excel_autre': 'The file “{nomFichier}” is open in Excel or another program: close it, then try again.',
  'socle.message_reponse_inattendue.reponse_inattendue_serveur_operation': 'Unexpected response from the server; the operation may have been done, reload the page.',
  'socle.message_serveur_injoignable.serveur_prevo_repond_pas': 'The Prévo server is not responding. Check that the server window is open on the PC.',
  'socle.mettre_ajour_boutons_profil.appareil_enrole': 'Enrolled device: {libelleAffiche}',
  'socle.mettre_ajour_boutons_profil.changer_profil': 'Change profile',
  'socle.mettre_ajour_boutons_profil.connecte_cliquer_deconnecter': 'Signed in: {libelleCompte}. Click to sign out.',
  'socle.mettre_ajour_boutons_profil.deconnecter': 'sign out',
  'socle.mettre_ajour_boutons_profil.deconnecter_bouton': 'Sign out',
  'socle.mettre_ajour_boutons_profil.profil_poste_cliquer_changer': 'Profile: {libelleAffiche} — workstation “{poste}”. Click to change.',
  'socle.migrer.formats_migrer_format_cible': 'Formats.migrer: unknown target format ({vers}); known formats: {premier} to {version}.',
  'socle.migrer.formats_migrer_format_depart': 'Formats.migrer: unreadable starting format ({de}).',
  'socle.migrer_au_format_courant.sans_sauvegarde_demo': 'without backup (demo)',
  'socle.migrer_au_format_courant.sauvegarde_avant_passage_format': 'Backup before moving to format {courant} is not possible: {messageSansPointFinal}; the update will be tried again the next time it is opened.',
  'socle.migrer_au_format_courant.sauvegarde_faite_juste_avant': 'backup {sauvegarde} made just before',
  'socle.note_donnees_demo.nulle_part_elles_vivent': 'Nowhere: it lives in this page and disappears when you close it. On your installation, it is CSV files on your PC, readable in Excel.',
  'socle.nouvel_id.donnees_nouvel_id_table_pas': 'Donnees.nouvelId: the table “{nomTable}” has no calculated ID.',
  'socle.ouvrir_fichiers_deposes.aucun_fichier_reconnu_fichiers': 'No file recognised: the files must be named equipements.csv, demandes.csv, ordres_travail.csv…',
  'socle.ouvrir_fichiers_deposes.fichiers_ignores_nom_inconnu': 'Files ignored (unknown or duplicate name): {fichiers}',
  'socle.ouvrir_plus.changer_profil': 'Change profile ({libelleAffiche})',
  'socle.ouvrir_plus.deconnecter_libelle_compte': 'Sign out ({libelleCompte})',
  'socle.ouvrir_plus.exporter_zip': 'Export as ZIP',
  'socle.passer_au_format_courant.fichiers_ont_pas_pu': '<b>The files could not be moved to format {version}.</b> {message} Until then, overdue preventive WOs are not generated automatically.',
  'socle.poste_aleatoire.poste_suffixe': 'Workstation-{suffixe}',
  'socle.probleme_colonne_absente.colonne_absente_sera_ajoutee': '{descriptionLibelle}: the column “{champNom}” ({champLibelle}) is missing from {fichier}; {suite}. It will be added the next time the table is changed.',
  'socle.probleme_colonne_absente.colonne_ajoutee_version_format': '{descriptionLibelle}: column “{champNom}” added by version {depuisVersion} of the format, written at the next save.',
  'socle.probleme_colonne_absente.valeur_defaut_utilisee': 'the default value “{valeurParDefaut}” is used',
  'socle.probleme_colonne_absente.valeur_laissee_vide': 'the value is left empty',
  'socle.probleme_table_laissee.abime_structure_fichier_valeurs': '{fichier} is damaged (file structure, or values beyond the header: see its other problems) and rewriting it would lose some of it',
  'socle.probleme_table_laissee.ligne_tete_incomplete_illisible': 'the header row of {fichier} is incomplete or unreadable (columns of format 1 are missing)',
  'socle.probleme_table_laissee.prevo_reecrit_pas_fichier': '{descriptionLibelle}: {raison}; Prévo does not rewrite this file to move it to format {version} and leaves it as it is. Correct it, or restore a backup.',
  'socle.profil_demandeur.demandeur': 'Requester',
  'socle.profil_demandeur.signaler_probleme_suivre_mes': 'Report a problem, follow my requests',
  'socle.profil_panneau_demandeur.nom': 'Your name',
  'socle.profil_panneau_demandeur.retour': 'Back',
  'socle.profil_panneau_technicien.choisissez_nom': 'Choose your name',
  'socle.profil_responsable.responsable': 'Manager',
  'socle.profil_responsable.tout_suivi_demandes_ot': 'Everything: requests, work orders, equipment register, settings',
  'socle.profil_technicien.mes_ordres_travail_comptes': 'My work orders, job reports',
  'socle.profil_technicien.technicien': 'Technician',
  'socle.qr_svg.bibliotheque_qrcode_absente_js': 'qrcode library missing (js/lib/qrcode.js).',
  'socle.qr_svg.qr_code': 'QR code: {texte}',
  'socle.raison_erreur.fichier_abime_prevenez_responsable': 'damaged file: tell the manager',
  'socle.raison_erreur.fichier_abime_rien_ete': 'damaged file, nothing was saved in it: restore today\'s backup or import a ZIP; the details are in Settings › Database check',
  'socle.raison_erreur.fichier_abime_rien_ete_avec_fichier': 'damaged file ({fichier}), nothing was saved in it: restore today\'s backup or import a ZIP; the details are in Settings › Database check',
  'socle.redimensionner_photo.photo_pas_pu_etre': 'The photo could not be converted.',
  'socle.remplir_liste_techniciens.aucun_technicien_actif_techniciens': 'No active technician in techniciens.csv: choose another profile.',
  'socle.remplir_phrases_balisees.developpe_claude_anthropic_demande': 'Developed by <b>Claude (Anthropic)</b> at the request of <b>Nicolas Briand — SELECTIS</b>',
  'socle.remplir_phrases_balisees.installer_prevo_assistant_comptes': '<a href="#/installation">Install Prévo (wizard)</a>: accounts, https, phones, start with the PC.',
  'socle.remplir_phrases_balisees.plusieurs_postes_telephones_lancez': 'Several workstations and phones? Run <b>Lancer_GMAO.bat</b> (Windows) or <b>lancer.sh</b> (Mac, Linux): server mode is recognised automatically.',
  'socle.rendre.ecran_pas_pu_afficher': '<b>This screen could not be displayed.</b> {message}',
  'socle.reperage_ligne.ligne_donnees_sans_identifiant': 'data row no. {numero} (no ID)',
  'socle.reprendre_dossier.acces_dossier_precedent_pas': 'Access to the previous folder was not granted. Choose the folder again.',
  'socle.route.aucun_ecran_correspond_adresse': 'No screen matches this address.',
  'socle.route.ecran_introuvable': 'Screen not found',
  'socle.route.ecran_pas_disponible_profil': 'The screen “{ecranTitre}” is not available for the {profil} profile.',
  'socle.sauvegarder_avant_format.mode_stockage_sait_pas': 'this storage mode cannot make a backup',
  'socle.sauvegarder_avant_format.stockage_pas_confirme_sauvegarde': 'the storage did not confirm the backup (no name returned)',
  'socle.sauvegarder_avant_mise_ajour.sauvegarde_avant_mise_jour': '<b>The “before the Prévo update” backup could not be made.</b> {message} It will be tried again the next time it is opened.',
  'socle.scanner_qr.impossible_ouvrir_camera_autorisation': 'Cannot open the camera (permission denied or camera in use).',
  'socle.scanner_qr.placez_qr_code_equipement': 'Place the equipment QR code in the frame.',
  'socle.scanner_qr.scan_camera_pas_disponible': 'Camera scanning is not available on this page. Use the phone camera.',
  'socle.scanner_qr.scanner_qr_code': 'Scan a QR code',
  'socle.selecteur_equipement.aucun_equipement_correspond': 'No equipment matches “{recherche}”.',
  'socle.selecteur_equipement.changer': 'Change',
  'socle.selecteur_equipement.equipements_trouves': 'Equipment found',
  'socle.selecteur_equipement.equipements_trouves_affiner': { one: '{n} item: type a few letters to narrow it down.', other: '{n} items: type a few letters to narrow it down.' },
  'socle.selecteur_equipement.qr_code_correspond_aucun': 'This QR code does not match any known equipment.',
  'socle.selecteur_equipement.rechercher_equipement': 'Search for equipment',
  'socle.selecteur_equipement.repere_nom': 'Tag or name',
  'socle.selecteur_equipement.scanner': 'Scan',
  'socle.suffixe_du_motif.motif_sauvegarde_refuse_motifs': 'Backup reason refused. Accepted reasons: {motifs}.',
  'socle.tableau.aucune_ligne_afficher': 'No rows to display.',
  'socle.texte_base_vide.aucun_23_fichiers_prevo': 'None of the 23 Prévo files was found.',
  'socle.titre_donnees.ou_sont_donnees': 'Where is your data?',
  'socle.titre_donnees_demo.ou_sont_donnees_demo': 'Where is this demo\'s data?',
  'socle.traduire_erreur.acces_refuse_dossier_donnees': 'Access denied to the data folder ({action}). Choose the folder again to grant permission again.',
  'socle.traduire_erreur.dossier_donnees_introuvable_ete': 'Data folder not found ({action}): has it been moved, renamed or unplugged?',
  'socle.traduire_erreur.lecture_ecriture_impossible_dossier': 'The data folder cannot be read or written ({action}).',
  'socle.valider_demandeur.indiquez_nom_permet_retrouver': 'Enter your name: it lets you find your requests again.',
  'socle.verifier_dossier_accessible.dossier_donnees_introuvable_inaccessible': 'The data folder cannot be found or reached (deleted, moved, USB drive or network share unplugged?). Plug it back in or choose the folder again.',
  'socle.verifier_formulaire.case_doit_etre_cochee': 'This box must be ticked.',
  'socle.verifier_formulaire.champ_obligatoire': 'This field is required.',
  'socle.verifier_formulaire.saisissez_nombre_entier_ex': 'Enter a whole number (e.g. 12).',
  'socle.verifier_formulaire.saisissez_nombre_ex_12': 'Enter a number (e.g. 12.5).',
  'socle.verifier_initialise.donnees_appelez_donnees_initialiser': 'Donnees: call Donnees.initialiser(adaptateur, …) before reading or writing.',
  'socle.verifier_nom_document.nom_document_refuse_lettres': 'Document name refused: letters, digits, “.”, “_” or “-”.',
  'socle.verifier_nom_document.nom_document_reserve_windows': 'Document name reserved by Windows.',
  'socle.verifier_nom_document.type_document_refuse_types': 'Document type refused. Accepted types: {types}.',
  'socle.verifier_nom_sauvegarde.nom_sauvegarde_invalide': 'Invalid backup name.',
  'socle.verifier_nom_table.table_inconnue': 'Unknown table: “{nomTable}”.',
  'socle.verifier_nom_table.table_inconnue_dossier': 'Unknown table: {table}.',
  'socle.verifier_verrou_dossier.dossier_semble_deja_ouvert': '<b>This folder seems to be already open on “{poste}”</b> (last sign of life: {heure}). Two workstations writing to the same folder can get in each other\'s way: close the other session if possible.',
  'socle.zone_depot.cliquer_choisir_demo_propres': 'or click to choose them: demo with your own files, nothing is saved',
  'socle.zone_depot.deposer_fichiers_csv_ici': 'Drop CSV files here',
});
// ==== fin socle ====

// ==== section planning ====
I18n.ajouter('en', {
});
// ==== fin planning ====

// ==== section causes ====
I18n.ajouter('en', {
});
// ==== fin causes ====

// ==== section dictee ====
I18n.ajouter('en', {
});
// ==== fin dictee ====

// ==== section mise ====
I18n.ajouter('en', {
});
// ==== fin mise ====

// ==== section aide ====
I18n.ajouter('en', {
});
// ==== fin aide ====

// ==== section ordres ====
I18n.ajouter('en', {
});
// ==== fin ordres ====

// ==== section demandes ====
I18n.ajouter('en', {
});
// ==== fin demandes ====

// ==== section parc ====
I18n.ajouter('en', {
});
// ==== fin parc ====

// ==== section preventif ====
I18n.ajouter('en', {
});
// ==== fin preventif ====

// ==== section controles ====
I18n.ajouter('en', {
});
// ==== fin controles ====

// ==== section wiki ====
I18n.ajouter('en', {
});
// ==== fin wiki ====

// ==== section suggestions ====
I18n.ajouter('en', {
});
// ==== fin suggestions ====

// ==== section import ====
I18n.ajouter('en', {
});
// ==== fin import ====

// ==== section magasin ====
I18n.ajouter('en', {
});
// ==== fin magasin ====

// ==== section indicateurs ====
I18n.ajouter('en', {
});
// ==== fin indicateurs ====

// ==== section rapport ====
I18n.ajouter('en', {
});
// ==== fin rapport ====

// ==== section accueil ====
I18n.ajouter('en', {
});
// ==== fin accueil ====

// ==== section equipe ====
I18n.ajouter('en', {
});
// ==== fin equipe ====

// ==== section acces ====
I18n.ajouter('en', {
});
// ==== fin acces ====

// ==== section connexion ====
I18n.ajouter('en', {
});
// ==== fin connexion ====

// ==== section poste ====
I18n.ajouter('en', {
});
// ==== fin poste ====

// ==== section apropos ====
I18n.ajouter('en', {
});
// ==== fin apropos ====

// ==== section installation ====
I18n.ajouter('en', {
});
// ==== fin installation ====

// ==== section porte ====
I18n.ajouter('en', {
});
// ==== fin porte ====

// ==== section parametres ====
I18n.ajouter('en', {
});
// ==== fin parametres ====

// ==== section sauvegardes ====
I18n.ajouter('en', {
});
// ==== fin sauvegardes ====

// ==== section zip ====
I18n.ajouter('en', {
});
// ==== fin zip ====

// ==== section serveur ====
I18n.ajouter('en', {
});
// ==== fin serveur ====

// ==== section ia ====
I18n.ajouter('en', {
});
// ==== fin ia ====
