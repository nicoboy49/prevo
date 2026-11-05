'use strict';
// Textes français de Prévo, langue de référence et de repli (chantier multilingue, D147 ; contrat du Lot 2).
// Un bloc par section, pour que les tâches d'extraction ne touchent jamais les mêmes lignes. Dans chaque bloc :
// clés triées, une par ligne, chaînes entre apostrophes simples, échappements gardés tels que dans la source
// (jamais d'espace insécable écrit en clair : \u00a0, \u202f).
// Clés : <domaine>.<écran ou composant>.<élément> ; commun.* pour les textes partagés ; schema.<table>.<champ> ;
// valeurs.<table>.<champ>.<valeur stockée>. Pluriel : { one: '{n} intervention', other: '{n} interventions' }
// (catégorie absente : other). L'aide longue (aide.*) est dans js/i18n/aide/fr.js.

// ==== section commun ====
I18n.ajouter('fr', {
  'commun.bouton.actualiser': 'Actualiser',
  'commun.bouton.ajouter': 'Ajouter',
  'commun.bouton.annuler': 'Annuler',
  'commun.bouton.continuer': 'Continuer',
  'commun.bouton.desactiver': 'Désactiver',
  'commun.bouton.enregistrer': 'Enregistrer',
  'commun.bouton.fermer': 'Fermer',
  'commun.bouton.imprimer': 'Imprimer',
  'commun.bouton.modifier': 'Modifier',
  'commun.champ.article': 'Article',
  'commun.champ.commentaire': 'Commentaire',
  'commun.champ.criticite': 'Criticité',
  'commun.champ.date': 'Date',
  'commun.champ.designation': 'Désignation',
  'commun.champ.equipement': 'Équipement',
  'commun.champ.prenom': 'Prénom',
  'commun.champ.priorite': 'Priorité',
  'commun.champ.prix_unitaire': 'Prix unitaire',
  'commun.champ.quantite': 'Quantité',
  'commun.champ.reference': 'Référence',
  'commun.champ.repere': 'Repère',
  'commun.champ.statut': 'Statut',
  'commun.champ.symptome': 'Symptôme',
  'commun.champ.technicien': 'Technicien',
  'commun.liste.non_choisi': '(non choisi)',
  'commun.message.aucune_modification': 'Aucune modification à enregistrer.',
  'commun.message.champ_obligatoire': 'champ obligatoire',
  'commun.message.erreur_inconnue': 'erreur inconnue',
  'commun.message.fichier_trop_volumineux': 'Ce fichier est trop volumineux (9 Mo au maximum).',
  'commun.message.ot_introuvable': 'L\'ordre de travail {otId} est introuvable.',
  'commun.message.saisi_sur_autre_poste': 'Il a peut-être été saisi sur un autre poste : actualisez.',
  'commun.message.serveur_a_repondu': 'Le serveur a répondu « {status} ».',
});
// ==== fin commun ====

// ==== section schema ====
I18n.ajouter('fr', {
});
// ==== fin schema ====

// ==== section valeurs ====
I18n.ajouter('fr', {
});
// ==== fin valeurs ====

// ==== section socle ====
I18n.ajouter('fr', {
});
// ==== fin socle ====

// ==== section planning ====
I18n.ajouter('fr', {
  'planning.a_planifier.glissez_carte_technicien_jour': 'Glissez une carte sur un technicien et un jour, ou utilisez « Planifier… ».',
  'planning.a_planifier.ot_prepare_sont_pas': 'OT « Préparé » qui ne sont pas dans la grille de cette semaine, les plus prioritaires d\'abord.',
  'planning.a_planifier.ot_prepares_apparaitront_ici': 'Les OT préparés apparaîtront ici.',
  'planning.a_planifier.planifier': 'À planifier',
  'planning.a_planifier.rien_planifier': 'Rien à planifier',
  'planning.carte_ot.planifier': 'Planifier…',
  'planning.carte_ot.prevu_date_prevue': 'prévu le {date_prevue}',
  'planning.carte_ot.retard': 'en retard',
  'planning.carte_ot.sans_titre': '(sans titre)',
  'planning.carte_ot.temps_non_prevu': 'temps non prévu',
  'planning.charge.capacite_h': '{capacite} h',
  'planning.charge.capacite_non_renseignee': 'capacité non renseignée',
  'planning.charge.charge_h_capacite': '{charge} h / {capacite}',
  'planning.charge.surcharge': 'surcharge',
  'planning.detail_piece.prevu_deja_sorti_ot': '{pieceLibelle} ({prevu} prévu(s), {sorti} déjà sorti(s) pour cet OT, {stock} en stock)',
  'planning.detail_piece.prevu_stock': { one: '{pieceLibelle} ({prevu} prévu(s), {stock} en stock)', other: '{pieceLibelle} ({prevu} prévu(s), {stock} en stock)' },
  'planning.ecran.changer_semaine': 'Changer de semaine',
  'planning.ecran.consultation_responsable_planifie': 'Consultation : le responsable planifie.',
  'planning.ecran.semaine': 'Cette semaine',
  'planning.ecran.semaine_du_au': 'Semaine du {debut} au {fin}.',
  'planning.ecran.semaine_precedente': '‹ Semaine précédente',
  'planning.ecran.semaine_suivante': 'Semaine suivante ›',
  'planning.ecran.titre': 'Planning',
  'planning.filtre.planning_seulement': 'Planning de {nomTechnicien} seulement.',
  'planning.filtre.voir_toute_equipe': 'Voir toute l\'équipe',
  'planning.grille.ajoutez_techniciens_ecran_equipe': 'Ajoutez des techniciens dans l\'écran Équipe.',
  'planning.grille.aucun_technicien_actif': 'Aucun technicien actif',
  'planning.grille.inactif': 'inactif',
  'planning.grille.planning_semaine_technicien': 'Planning de la semaine du {debut} au {fin}, par technicien',
  'planning.grille.technicien': 'Technicien',
  'planning.liste_par_jour.charge_semaine': 'Charge de la semaine',
  'planning.liste_par_jour.rien_prevu': 'Rien de prévu.',
  'planning.menu.libelle': 'Planning',
  'planning.mettre_en_attente_piece.mettre_attente': 'Mettre en attente {otId}',
  'planning.mettre_en_attente_piece.motif_mise_attente': 'Motif de mise en attente',
  'planning.mettre_en_attente_piece.ot_id_attente': '{otId} : En attente.',
  'planning.mettre_en_attente_piece.stock_insuffisant': 'stock insuffisant',
  'planning.noms_jours.dim': 'dim.',
  'planning.noms_jours.jeu': 'jeu.',
  'planning.noms_jours.lun': 'lun.',
  'planning.noms_jours.mar': 'mar.',
  'planning.noms_jours.mer': 'mer.',
  'planning.noms_jours.sam': 'sam.',
  'planning.noms_jours.ven': 'ven.',
  'planning.ouvrir_fenetre.annuler': 'Annuler',
  'planning.ouvrir_fenetre.choisir': 'Choisir…',
  'planning.ouvrir_fenetre.choisissez_date_prevue': 'Choisissez la date prévue.',
  'planning.ouvrir_fenetre.choisissez_technicien': 'Choisissez le technicien.',
  'planning.ouvrir_fenetre.date_prevue': 'Date prévue',
  'planning.ouvrir_fenetre.planifier': 'Planifier',
  'planning.ouvrir_fenetre.planifier_ot_id': 'Planifier {otId}',
  'planning.placer.succes_planifie': '{otId} planifié le {date} pour {nomTechnicien}.',
  'planning.placer.succes_replanifie': '{otId} replanifié le {date} pour {nomTechnicien}.',
  'planning.planifier.avertissement_habilitation': 'Avertissement habilitation : {message}.',
  'planning.planifier.ordre_travail_introuvable': 'L\'ordre de travail {otId} est introuvable.',
  'planning.planifier.ot_cree_preparez_abord': 'L\'OT {otId} est « Créé » : préparez-le d\'abord (fiche OT, onglet Préparation), puis planifiez-le.',
  'planning.planifier.ot_passe_autre_poste': 'L\'OT {otId} est passé « {ligneStatut} » sur un autre poste. Actualisez puis recommencez.',
  'planning.planifier.seul_ot_prepare_planifie': 'Seul un OT « Préparé » ou « Planifié » se place sur le planning : {otId} est « {ligneStatut} ».',
  'planning.refus.mettre_attente_motif_piece': 'Mettre en attente (motif : pièce)',
  'planning.refus.pas_ete_planifie': '<b>{otId} n\'a pas été planifié.</b> {erreurMessage}',
  'planning.verifier_demande.choisissez_date_prevue_valide': 'Choisissez une date prévue valide.',
  'planning.verifier_demande.choisissez_technicien': 'Choisissez un technicien.',
  'planning.verifier_demande.technicien_desactive_choisissez_technicien': 'Le technicien {technicienId} est désactivé : choisissez un technicien actif.',
});
// ==== fin planning ====

// ==== section causes ====
I18n.ajouter('fr', {
  'causes.calculer.equipement': 'cet équipement',
  'causes.calculer.equipements_meme_marque_modele': 'équipements de même marque et modèle ({marque} {modele})',
  'causes.encart.causes_frequentes_ici_cas': { one: 'Causes fréquentes ici — {n} cas', other: 'Causes fréquentes ici — {n} cas' },
  'causes.encart.pas_encore_assez_cas': 'Pas encore assez de cas pour ce symptôme ({total} sur {minimum})',
  'causes.encart.portee_libelle_portee': 'Portée : {libellePortee}',
  'causes.ligne_cause.cause_libelle_nombre_cas_total': { one: '<b>{causeLibelle}</b> — {n} cas sur {total}', other: '<b>{causeLibelle}</b> — {n} cas sur {total}' },
  'causes.ligne_cause.dernier_cas': '· dernier cas : {dernierCas}',
  'causes.ligne_cause.remede_plus_utilise': '· remède le plus utilisé : {remedeLibelle}',
  'causes.ligne_cause.voir_ot': '· voir les OT :',
  'causes.mention.statistique_historique_pas_diagnostic': 'Statistique de l\'historique, pas un diagnostic',
  'causes.mention_piste.peu_cas_prendre_comme': 'Peu de cas : à prendre comme une piste.',
  'causes.precision.calculee_ainsi_methode_wilson': 'Calculée ainsi (méthode de Wilson), une fourchette contient la vraie part de la cause 95 fois sur 100 ; elle se resserre quand les cas s\'accumulent.',
  'causes.precision.precision_chiffres': 'Précision de ces chiffres',
  'causes.suite_des_liens.n_autres': { one: 'et {n} autre', other: 'et {n} autres' },
  'causes.texte_fourchette.entre_cas': 'entre {bas} et {haut} des cas',
});
// ==== fin causes ====

// ==== section dictee ====
I18n.ajouter('fr', {
  'dictee.aide_clavier.dictee_utilisez_micro_clavier': 'Dictée : utilisez le micro du clavier de votre téléphone.',
  'dictee.avertir.continuer': 'Continuer',
  'dictee.avertir.desactiver_dictee': 'Désactiver la dictée',
  'dictee.avertir.dictee_desactivee_poste_reactivable': 'Dictée désactivée sur ce poste (réactivable dans « Ce poste »).',
  'dictee.avertir.dictee_vocale': 'Dictée vocale',
  'dictee.avertir.pouvez_desactiver_dictee_poste': 'Vous pouvez désactiver la dictée sur ce poste maintenant, ou plus tard dans « Ce poste ».',
  'dictee.avertissement_local.voix_transcrite_pc_envoyee': 'La voix est transcrite sur ce PC : elle n\'est envoyée nulle part.',
  'dictee.avertissement_nuage.chrome_edge_voix_envoyee': 'Dans Chrome et Edge, la voix est envoyée aux serveurs de Google ou Microsoft pour être transcrite.',
  'dictee.bouton_pour.dicter': 'Dicter',
  'dictee.bouton_pour.dicter_champ': 'Dicter dans ce champ',
  'dictee.demarrer.dictee_impossible': 'Dictée impossible : {raison}.',
  'dictee.demarrer.dictee_interrompue': 'Dictée interrompue ({error}).',
  'dictee.demarrer.erreur_inconnue': 'erreur inconnue',
  'dictee.marquer.arreter': 'Arrêter',
  'dictee.message_erreur.aucun_micro_trouve_appareil': 'Aucun micro trouvé sur cet appareil.',
  'dictee.message_erreur.aucune_parole_entendue_dictee': 'Aucune parole entendue : la dictée s\'est arrêtée.',
  'dictee.message_erreur.dictee_impossible_pas_connexion': 'Dictée impossible : pas de connexion au service de reconnaissance.',
  'dictee.message_erreur.francais_pas_propose_reconnaissance': 'Le français n\'est pas proposé par la reconnaissance de ce navigateur.',
  'dictee.message_erreur.micro_refuse_autorisez_micro': 'Micro refusé : autorisez le micro pour cette page, puis réessayez.',
});
// ==== fin dictee ====

// ==== section mise ====
I18n.ajouter('fr', {
  'mise.bandeau.disponible': 'Prévo {version} est disponible.',
  'mise.bandeau.disponible_date': 'Prévo {version} est disponible ({date}).',
  'mise.bandeau.ignorer_version': 'Ignorer cette version',
  'mise.bandeau.telecharger': 'Télécharger',
  'mise.ligne_apropos.demo_ligne_aucune_verification': 'Démo en ligne : aucune vérification.',
  'mise.ligne_apropos.disponible': '<b>Prévo {version} est disponible</b> — <a href="{adresse}" target="_blank" rel="noopener">télécharger</a>',
  'mise.ligne_apropos.disponible_date': '<b>Prévo {version} est disponible</b> ({date}) — <a href="{adresse}" target="_blank" rel="noopener">télécharger</a>',
  'mise.ligne_apropos.non_verifiee_responsable_peut': 'Non vérifiée : le responsable peut l\'autoriser dans Paramètres (« Me signaler les nouvelles versions »).',
  'mise.ligne_apropos.prevo_jour_verifie': 'Prévo est à jour (vérifié le {date}).',
  'mise.ligne_apropos.signalee_responsable_accueil_ici': 'Signalée au responsable, sur l\'accueil et ici.',
  'mise.ligne_apropos.verification_cours': 'Vérification en cours…',
  'mise.ligne_apropos.verification_impossible_aujourd_hui': 'Vérification impossible aujourd\'hui (prevo.pro injoignable) : rien d\'autre à faire.',
});
// ==== fin mise ====

// ==== section aide ====
I18n.ajouter('fr', {
  'aide.encart.compris': 'Compris',
  'aide.encart.en_savoir_plus': 'En savoir plus<span class="visuellement-cache"> (nouvel onglet)</span>',
  'aide.encart.essayez': '<b>Essayez :</b> {essayez}',
});
// ==== fin aide ====

// ==== section ordres ====
I18n.ajouter('fr', {
});
// ==== fin ordres ====

// ==== section demandes ====
I18n.ajouter('fr', {
});
// ==== fin demandes ====

// ==== section parc ====
I18n.ajouter('fr', {
});
// ==== fin parc ====

// ==== section preventif ====
I18n.ajouter('fr', {
});
// ==== fin preventif ====

// ==== section controles ====
I18n.ajouter('fr', {
});
// ==== fin controles ====

// ==== section wiki ====
I18n.ajouter('fr', {
});
// ==== fin wiki ====

// ==== section suggestions ====
I18n.ajouter('fr', {
});
// ==== fin suggestions ====

// ==== section import ====
I18n.ajouter('fr', {
  'import.action.creer': 'À créer',
  'import.action.doublon_suppose': 'Doublon supposé',
  'import.action.doublon_sur': 'Doublon sûr',
  'import.action.identique': 'Identique',
  'import.action.mettre_a_jour': 'À mettre à jour',
  'import.action.refusee': 'Refusée',
  'import.aide_modele.autres_titres_reconnus': 'Autres titres reconnus',
  'import.aide_modele.colonne': 'Colonne',
  'import.aide_modele.exemple': 'Exemple',
  'import.aide_modele.format': 'Format',
  'import.aide_modele.non': 'non',
  'import.aide_modele.obligatoire': 'Obligatoire',
  'import.aide_modele.oui': 'oui',
  'import.aide_modele.oui_non': 'oui ; non',
  'import.aide_modele.remplissez_feuille_donnees_gardez': 'Remplissez la feuille « Données » : gardez la ligne de titres, remplacez la ligne d\'exemple par vos données, une fiche par ligne. Les colonnes peuvent être dans un autre ordre ; Prévo les reconnaît par leur titre et vous montre tout avant d\'écrire.',
  'import.aide_modele.titre': 'Modèle « {type} » — Prévo {version}',
  'import.aide_modele.valeurs_permises': 'Valeurs permises',
  'import.alertes_colonnes.a_confirmer': { one: '<b>{n} colonne à confirmer :</b> vérifiez le champ choisi. En continuant, elle est importée telle quelle.', other: '<b>{n} colonnes à confirmer :</b> vérifiez le champ choisi. En continuant, elles sont importées telles quelles.' },
  'import.alertes_colonnes.aucune_colonne_importee_choisissez': 'Aucune colonne n\'est importée : choisissez le champ de Prévo d\'au moins une colonne.',
  'import.alertes_colonnes.sans_colonne': { one: '<b>Sans colonne :</b> {champs}. Les lignes qui créeraient une fiche sans ce champ obligatoire seront refusées.', other: '<b>Sans colonne :</b> {champs}. Les lignes qui créeraient une fiche sans ces champs obligatoires seront refusées.' },
  'import.annuler.annuler_import': 'Annuler l\'import',
  'import.annuler.annuler_import_tables_touchees': 'Annuler cet import ? Les tables touchées ({tables}) reviennent à leur état d\'avant l\'import : les modifications faites depuis l\'import, sur ces tables, seront perdues.',
  'import.annuler.aucun_import_annuler': 'Aucun import à annuler.',
  'import.annuler.aucune_sauvegarde_import_rien': 'Aucune sauvegarde de cet import : rien à restaurer.',
  'import.annuler.garder_import': 'Garder l\'import',
  'import.annuler.import_annule': 'Import annulé.',
  'import.appliquer_ia.aucune_proposition_ia_appliquer': 'Aucune proposition de l\'IA à appliquer.',
  'import.appliquer_ia.champ_propose_ia': 'champ proposé par l\'IA pour « {entete} »',
  'import.appliquer_ia.colonnes_proposees': { one: '{n} colonne proposée par l\'IA : vérifiez-les.', other: '{n} colonnes proposées par l\'IA : vérifiez-les.' },
  'import.appliquer_ia.proposee_ia_confirmer': 'proposée par l\'IA ({modele}) : à confirmer',
  'import.bilan.chaque_fiche_ecrite_notee': 'Chaque fiche écrite est notée au journal.',
  'import.bilan.cliquant_importer_prevo_ecrit': 'En cliquant sur « Importer », Prévo écrit :',
  'import.bilan.creations': { one: '{n} création', other: '{n} créations' },
  'import.bilan.demo_rien_ecrit_disque': 'Démo : rien n\'est écrit sur un disque. L\'état d\'avant l\'import est gardé en mémoire : « Annuler cet import » le rétablit.',
  'import.bilan.juste_avant_prevo_fait': 'Juste avant, Prévo fait une sauvegarde « Avant import » : « Annuler cet import » rend les tables touchées dans leur état d\'avant.',
  'import.bilan.mises_a_jour': { one: '{n} mise à jour', other: '{n} mises à jour' },
  'import.bilan.rien_importer_aucune_ligne': '<b>Rien à importer :</b> aucune ligne à créer ni à mettre à jour. Revenez à l\'aperçu (lignes refusées, case « Compléter et mettre à jour les fiches existantes ») ou à la correspondance des colonnes.',
  'import.cascade_equipements.boucle_equipement_deviendrait_propre': 'boucle : cet équipement deviendrait son propre ancêtre',
  'import.cascade_equipements.equipement_parent_refuse_ligne': 'équipement parent refusé (ligne {numero})',
  'import.champ.ancien_numero': 'Ancien n° d\'OT',
  'import.champ.atelier': 'Atelier',
  'import.champ.cause_code': 'Code cause',
  'import.champ.chemin': 'Chemin',
  'import.champ.chemin_localisation': 'Localisation',
  'import.champ.compteur': 'Compteur',
  'import.champ.fournisseur': 'Fournisseur',
  'import.champ.ligne': 'Ligne',
  'import.champ.operations': 'Opérations',
  'import.champ.parent': 'Équipement parent',
  'import.champ.remede_code': 'Code remède',
  'import.champ.site': 'Site',
  'import.champ.stock_initial': 'Stock initial',
  'import.champ.symptome_code': 'Code symptôme',
  'import.champ.temps_passe_h': 'Temps passé (heures)',
  'import.champ.valeur_attendue': 'Valeur attendue',
  'import.choisir_champ.champ_repris_colonne': 'champ repris par la colonne « {nomColonne} »',
  'import.choisir_champ.choisi_main': 'choisi à la main',
  'import.choisir_champ.ecartee_main': 'écartée à la main',
  'import.colonnes.champ_obligatoire': '{champ} (obligatoire)',
  'import.colonnes_par_champ.champ_choisi_deux_colonnes': 'Le champ « {champLibelle} » est choisi pour deux colonnes : gardez-en une seule.',
  'import.colonnes_par_champ.champ_inconnu': 'Champ « {cle} » inconnu pour « {descriptionLibelle} ».',
  'import.construire_ot.arret_production_absent_oui': 'Arrêt de production absent : « oui », car une durée d\'arrêt est donnée',
  'import.construire_ot.arret_production_non_malgre': 'Arrêt de production « non » malgré une durée d\'arrêt : laissé à « non »',
  'import.construire_ot.arret_production_sans_duree': 'Arrêt de production sans durée d\'arrêt : durée laissée vide (panne hors MTTR et disponibilité)',
  'import.construire_ot.code_laisse_vide': '{champ} « {valeur} » {erreur} : laissé vide (aucun code créé)',
  'import.construire_ot.date_creation_absente_date': 'Date de création absente : date de début reprise',
  'import.construire_ot.date_fin_absente_creation': 'Date de fin absente : date de création reprise',
  'import.construire_ot.date_fin_absente_debut': 'Date de fin absente : date de début reprise',
  'import.construire_ot.laisse_vide': '{erreur} : laissé vide',
  'import.construire_ot.priorite_absente': 'Priorité absente : « {priorite} » par défaut',
  'import.construire_ot.temps_passe_sans_technicien': 'Temps passé sans technicien : ligne de temps sans technicien',
  'import.construire_ot.titre_absent_debut_compte': 'Titre absent : début du compte rendu repris',
  'import.construire_ot.type_absent': 'Type absent : « {type} » par défaut',
  'import.controler.equipement_introuvable_prevo': 'équipement « {equipement} » introuvable dans Prévo',
  'import.controler.negatif': '{champ} : « {valeur} » ne peut pas être négatif',
  'import.controler.ni_date_creation_ni': 'ni date de création ni date de début : ligne refusée (la date de fin seule ne suffit pas)',
  'import.controler.titre_obligatoire_ni_titre': 'Titre obligatoire : ni titre ni compte rendu dans la ligne',
  'import.convertir.valeur_probablement_abimee_excel': 'valeur probablement abîmée par Excel',
  'import.convertir_choix.hors_valeurs': 'ne fait pas partie des valeurs permises ({valeurs})',
  'import.convertir_choix.lu_comme': '« {valeur} » lu comme « {trouvee} »',
  'import.correspondance.aucun_champ_reconnu': 'aucun champ reconnu',
  'import.correspondance.colonne_sans_titre': 'colonne sans titre',
  'import.correspondance.deux_colonnes': 'deux colonnes pour « {champ} » : « {premiere} » et « {seconde} »',
  'import.correspondance.meme_champ': 'même champ que la colonne « {entete} » ({champ}) : choisissez',
  'import.correspondance.non_utilisee_lors_import': 'non utilisée lors d\'un import précédent',
  'import.correspondance.plusieurs_champs': 'plusieurs champs possibles : {champs}',
  'import.correspondance.retenue_lors_import_precedent': 'retenue lors d\'un import précédent',
  'import.correspondance.synonyme_champ_libelle': 'synonyme de « {champLibelle} »',
  'import.correspondance.titre_proche': 'titre proche de « {meilleurLibelle} »',
  'import.correspondance.titre_reconnu': 'titre reconnu',
  'import.correspondance.titre_reconnu_mais_valeurs': 'titre reconnu, mais les valeurs ne ressemblent pas à : {champLibelle}',
  'import.decider.deja_prevo_mise_jour': 'déjà dans Prévo : mise à jour non demandée',
  'import.decouper_chemin.chemin_localisation_incomplet_niveau': 'chemin de localisation incomplet (un niveau est vide)',
  'import.decouper_chemin.plus_trois_niveaux_site': 'plus de trois niveaux (Site > Atelier > Ligne)',
  'import.demander_ia.appliquer_confirmer': 'Appliquer (à confirmer)',
  'import.demander_ia.toutes_colonnes_sont_reconnues': 'Toutes les colonnes sont reconnues : rien à demander à l\'IA.',
  'import.dependance.equipement_parent_refuse_ligne': 'équipement parent refusé (ligne {numero})',
  'import.dependance.fiche_liee_refusee_ligne': 'fiche liée refusée (ligne {numero})',
  'import.dependance.gamme_refusee_ligne': 'gamme refusée (ligne {numero})',
  'import.dependance.localisation_parente_refusee_ligne': 'localisation parente refusée (ligne {numero})',
  'import.detail.aucun_changement': 'Aucun changement.',
  'import.detail.importer_quand_meme': 'Importer quand même',
  'import.detail.meme_intervention_ligne_fichier': 'Même intervention que la ligne {ligne} du fichier.',
  'import.detail.meme_intervention_ligne_ot': 'Même intervention que la ligne {ligne} du fichier ({ot}).',
  'import.detail.meme_intervention_ot_deja': 'Même intervention que l\'OT {ot} déjà dans Prévo.',
  'import.detail.vide': '(vide)',
  'import.ecran.etapes_import': 'Étapes de l\'import',
  'import.ecran.importer_donnees': 'Importer des données',
  'import.ecran.parametres_importer_donnees': '<a href="#/parametres">Paramètres</a> › <span>Importer des données</span>',
  'import.ecran.reprenez_listes_existantes_excel': 'Reprenez vos listes existantes (Excel, OpenDocument, CSV) en cinq étapes : rien n\'est écrit dans Prévo avant la dernière, « Importer ».',
  'import.ecran.titre': 'Importer des données',
  'import.ecrire_table.identifiant_vient_etre_pris': 'L\'identifiant {nouvelleId} vient d\'être pris sur un autre poste : relancez l\'aperçu.',
  'import.erreur.apercu_impossible': 'Aperçu impossible : {raison}.',
  'import.erreur.import_impossible': 'Import impossible : {raison}.',
  'import.erreur.type_inconnu': 'Type de données inconnu : « {type} ».',
  'import.erreur_import.rien_ete_importe': '<b>Rien n\'a été importé.</b> {message}',
  'import.erreur_perime.donnees_ont_change_autre': 'Les données ont changé sur un autre poste depuis l\'aperçu : il a été recalculé. Vérifiez-le, puis relancez l\'import.',
  'import.etape_apercu.apercu_prevo_va_faire': 'Aperçu : ce que Prévo va faire',
  'import.etape_apercu.chaque_intervention_acceptee_devient': 'Chaque intervention acceptée devient un OT clôturé ; un OT déjà dans Prévo n\'est jamais modifié. Un doublon supposé n\'est importé que si vous cochez « Importer quand même ».',
  'import.etape_apercu.completer_mettre_jour_fiches': 'Compléter et mettre à jour les fiches existantes',
  'import.etape_apercu.rien_encore_ecrit_verifiez': 'Rien n\'est encore écrit. Vérifiez ce que deviendra chaque ligne du fichier ; les lignes refusées ne seront pas importées.',
  'import.etape_apercu.seules_colonnes_importees_remplies': 'Seules les colonnes importées et remplies qui changent sont écrites ; une cellule vide n\'efface rien. Décochée : les fiches déjà dans Prévo ne sont pas touchées, seules les nouvelles sont créées.',
  'import.etape_colonnes.champ_prevo': 'Champ de Prévo',
  'import.etape_colonnes.colonne_fichier': 'Colonne du fichier',
  'import.etape_colonnes.correspondance_colonnes_fichier_champs': 'Correspondance des colonnes du fichier avec les champs de Prévo',
  'import.etape_colonnes.exemples': 'Exemples',
  'import.etape_colonnes.prevo_rapproche_chaque_colonne': 'Prévo a rapproché chaque colonne d\'un champ d\'après son titre. Vérifiez le champ choisi pour chaque colonne : une colonne « non utilisée » n\'est pas importée.',
  'import.etape_colonnes.proposer_ia': 'Proposer avec l\'IA',
  'import.etape_colonnes.quelles_colonnes_importer': 'Quelles colonnes importer ?',
  'import.etape_importer.derniere_etape_seulement_ici': 'Dernière étape : c\'est seulement ici que Prévo écrit.',
  'import.etape_importer.importer': 'Importer',
  'import.etape_ou.choisir_fichier': 'Choisir un fichier',
  'import.etape_ou.collage_vide_copiez_cellules': 'Le collage est vide : copiez des cellules dans votre tableur, puis collez-les ici.',
  'import.etape_ou.collez_cellules_copiees_tableur': 'Ou collez les cellules copiées dans votre tableur',
  'import.etape_ou.deposez_fichier': 'Déposez le fichier ici',
  'import.etape_ou.formats_lus': 'Excel (.xlsx, .xls), OpenDocument (.ods), CSV ou texte (.csv, .tsv, .txt) ; 10 Mo et 20 000 lignes au plus.',
  'import.etape_ou.lire_collage': 'Lire le collage',
  'import.etape_ou.ou_viennent_donnees': 'D\'où viennent les données ?',
  'import.etape_ou.selectionnez_cellules_excel_libre_office': 'Sélectionnez les cellules dans Excel ou LibreOffice (avec la ligne des titres), copiez, collez ici.',
  'import.etape_ou.titres_colonnes_compris': 'Titres des colonnes compris',
  'import.etape_ou.type_choisi': 'Type choisi : <b>{type}</b>. Déposez le fichier exporté de votre tableur ou de l\'autre logiciel, ou collez les cellules copiées dans Excel.',
  'import.etape_quoi.import_type_donnees_reprendre': 'Un import = un type de données. Pour reprendre tout un atelier, commencez par les localisations et les équipements, puis les fournisseurs et les articles, les techniciens et leurs habilitations, les codes, compteurs, contrôles et gammes ; l\'historique des interventions en dernier.',
  'import.etape_quoi.modele_csv': 'Modèle .csv',
  'import.etape_quoi.modele_xlsx': 'Modèle .xlsx',
  'import.etape_quoi.pas_encore_fichier_telechargez': 'Pas encore de fichier ? Téléchargez un modèle à remplir : les titres des colonnes, une ligne d\'exemple et, dans le classeur, une feuille d\'aide (champs obligatoires, valeurs permises, formats).',
  'import.etape_quoi.type_donnees': 'Type de données',
  'import.etape_quoi.voulez_importer': 'Que voulez-vous importer ?',
  'import.etapes.apercu': 'Aperçu',
  'import.etapes.colonnes': 'Colonnes',
  'import.etapes.importer': 'Importer',
  'import.etapes.ou': 'D\'où',
  'import.etapes.quoi': 'Quoi',
  'import.explication.booleen': 'n\'est pas oui ou non (oui, non, x, 1, 0, vrai, faux)',
  'import.explication.date': 'n\'est pas une date (ex. 15/03/2024 ou 2024-03-15)',
  'import.explication.date_heure': 'n\'est pas une date et heure (ex. 15/03/2024 08:30)',
  'import.explication.decimal': 'n\'est pas un nombre (ex. 7,5)',
  'import.explication.entier': 'n\'est pas un nombre entier',
  'import.filtre.creer': 'À créer',
  'import.filtre.doublon_suppose': 'Doublons supposés',
  'import.filtre.doublon_sur': 'Doublons sûrs',
  'import.filtre.identique': 'Identiques',
  'import.filtre.mettre_a_jour': 'À mettre à jour',
  'import.filtre.refusee': 'Refusées',
  'import.filtre.tout': 'Toutes',
  'import.format.booleen': 'oui ou non',
  'import.format.choix': 'une des valeurs permises',
  'import.format.date': 'date JJ/MM/AAAA (ou AAAA-MM-JJ)',
  'import.format.date_heure': 'date et heure JJ/MM/AAAA HH:MM',
  'import.format.decimal': 'nombre (virgule ou point)',
  'import.format.entier': 'nombre entier',
  'import.format.texte': 'texte',
  'import.importer.import_arrete_cours_route': 'Import arrêté en cours de route.',
  'import.importer.import_termine': 'Import terminé.',
  'import.importer.import_termine_tables': { one: 'Import terminé : {n} table écrite.', other: 'Import terminé : {n} tables écrites.' },
  'import.importer.rien_importer_aucune_ligne': 'Rien à importer : aucune ligne à créer ni à mettre à jour.',
  'import.importer.sauvegarde_impossible': 'Sauvegarde avant l\'import impossible : rien n\'a été importé.',
  'import.importer.sauvegarde_impossible_raison': 'Sauvegarde avant l\'import impossible ({raison}) : rien n\'a été importé.',
  'import.lecture.aucun_fichier': 'Aucun fichier à lire.',
  'import.lecture.aucune_donnee': 'Le fichier ne contient aucune donnée.',
  'import.lecture.chiffre': 'Ce fichier est protégé par un mot de passe : ouvrez-le dans Excel, enregistrez-le sans mot de passe, puis recommencez.',
  'import.lecture.collage': 'Collage',
  'import.lecture.collage_vide': 'Le collage est vide.',
  'import.lecture.feuille': 'Feuille',
  'import.lecture.fichier_vide': 'Le fichier est vide.',
  'import.lecture.format_inconnu': 'format inconnu',
  'import.lecture.format_non_reconnu': 'Format non reconnu (« .{format} ») : Prévo lit les fichiers .csv, .tsv, .txt, .xlsx, .xls et .ods.',
  'import.lecture.illisible': 'Fichier illisible ({raison}).',
  'import.lecture.ligne_proposee': 'Proposée par Prévo : ligne {numero}.',
  'import.lecture.ligne_tete_titres_colonnes': 'Ligne d\'en-tête (titres des colonnes)',
  'import.lecture.tete_deux_lignes_titres': 'En-tête sur deux lignes (titres fusionnés)',
  'import.lecture.trop_colonnes': 'Trop de colonnes : la feuille « {feuille} » en a plus de {colonnes}.',
  'import.lecture.trop_grand': { one: 'Fichier trop grand (plus de {n} Mo). Découpez-le en plusieurs fichiers.', other: 'Fichier trop grand (plus de {n} Mo). Découpez-le en plusieurs fichiers.' },
  'import.lecture.trop_long': { one: 'Fichier trop long : plus de {lignes} ligne. Découpez-le en plusieurs fichiers.', other: 'Fichier trop long : plus de {lignes} lignes. Découpez-le en plusieurs fichiers.' },
  'import.lecture.trop_long_feuille': { one: 'Fichier trop long : la feuille « {feuille} » a plus de {lignes} ligne. Découpez-le en plusieurs fichiers.', other: 'Fichier trop long : la feuille « {feuille} » a plus de {lignes} lignes. Découpez-le en plusieurs fichiers.' },
  'import.ligne_colonne.champ_prevo': 'Champ de Prévo pour « {titre} »',
  'import.ligne_colonne.colonne_vide': '(colonne vide)',
  'import.ligne_colonne.entete_lettre': '<b class="import-entete">{entete}</b> <small class="import-lettre">colonne {lettre}</small>',
  'import.ligne_colonne.pas_importer': '— Ne pas importer —',
  'import.lire.fichier': 'fichier',
  'import.lire.fichier_illisible': 'Fichier illisible : {raison}.',
  'import.lire.lecture': 'Lecture de « {nom} »…',
  'import.lire_cellules.erreur': '{champ} : « {valeur} » {erreur}',
  'import.lire_cellules.note': '{champ} : {note}',
  'import.lire_cellules.obligatoire_cellule_vide': '{champ} obligatoire : cellule vide',
  'import.lire_cellules.obligatoire_sans_colonne': '{champ} obligatoire : aucune colonne ne le donne',
  'import.lire_ligne.doublon_suppose_ligne': 'Doublon supposé : même équipement, même date de création et même titre que la ligne {ligne} ; cochez « Importer quand même » pour l\'importer',
  'import.lire_ligne.doublon_suppose_ot': 'Doublon supposé : même équipement, même date de création et même titre que {ot} ; cochez « Importer quand même » pour l\'importer',
  'import.lire_ligne.doublon_sur_ligne': 'Doublon sûr : ancien n° « {numero} » déjà à la ligne {ligne} du fichier : ligne ignorée',
  'import.lire_ligne.doublon_sur_ot': 'Doublon sûr : ancien n° « {numero} » déjà dans Prévo ({ot}) : ligne ignorée',
  'import.lire_ligne.importee_quand_meme_ligne': 'Doublon supposé de la ligne {ligne} : importée quand même (case « Importer quand même » cochée)',
  'import.lire_ligne.importee_quand_meme_ot': 'Doublon supposé de {ot} : importée quand même (case « Importer quand même » cochée)',
  'import.lire_ligne.plafond': { one: 'au-delà de {n} ligne (plafond) : ligne non lue', other: 'au-delà de {n} lignes (plafond) : ligne non lue' },
  'import.modele.aide': 'Aide',
  'import.modele.donnees': 'Données',
  'import.modele.format_modele_inconnu_xlsx': 'Format de modèle inconnu : « {format} » (xlsx ou csv).',
  'import.navigation.retour': 'Retour',
  'import.nom_colonne.colonne_lettre_colonne': 'colonne {lettreColonne}',
  'import.nouveau_contexte.responsable': 'Responsable',
  'import.premiere_passe.compteur_introuvable_equipement': 'compteur « {compteur} » introuvable pour cet équipement',
  'import.premiere_passe.doublon_fichier_ligne': 'doublon dans le fichier, ligne {numero}',
  'import.premiere_passe.equipement_introuvable_prevo': 'équipement « {equipement} » introuvable dans Prévo',
  'import.premiere_passe.non': 'non',
  'import.premiere_passe.oui': 'oui',
  'import.premiere_passe.vide_defaut': '{champ} vide : « {defaut} » par défaut',
  'import.preparer.import_historique_interventions_pas': 'L\'import de l\'historique des interventions n\'est pas disponible (import-historique.js n\'est pas chargé).',
  'import.probleme_entete.aucune_ligne_donnees': 'Aucune ligne de données sous la ligne d\'en-tête (ligne {numero}).',
  'import.probleme_entete.aucune_ligne_entete': 'Aucune ligne d\'en-tête trouvée : la ligne {numero} ne contient que des nombres, des dates ou rien. Prévo reconnaît les colonnes par leur titre : ajoutez en haut du fichier une ligne de titres (par exemple « Repère », « Désignation »), ou indiquez ci-dessous la ligne qui les porte.',
  'import.provisoire.creee_import': 'créée par l\'import, n° {numero}',
  'import.provisoire.ligne_fichier': 'ligne {numero} du fichier',
  'import.raison.champ_message': '{champ} : {message}',
  'import.rapport_refus.raison': 'Raison',
  'import.reference.fournisseur': 'Fournisseur',
  'import.reference.localisation': 'Localisation',
  'import.references.creees_aussi': { one: 'Créée aussi, car citée par les lignes à importer :', other: 'Créées aussi, car citées par les lignes à importer :' },
  'import.references.reference': '{nature} « {libelle} » <small class="import-cible">{id}</small>',
  'import.rendre.etape_courante': 'Étape {numero} sur {total} : {titre}',
  'import.rendre_resultats.action': 'Action',
  'import.rendre_resultats.afficher_lignes': 'Afficher les lignes',
  'import.rendre_resultats.afficher_lignes_plus': { one: 'Afficher {n} lignes de plus (sur {reste})', other: 'Afficher {n} lignes de plus (sur {reste})' },
  'import.rendre_resultats.aucune_ligne_filtre': 'Aucune ligne pour ce filtre.',
  'import.rendre_resultats.detail': 'Détail',
  'import.rendre_resultats.fiche': 'Fiche',
  'import.rendre_resultats.ligne': 'Ligne',
  'import.rendre_resultats.lignes_fichier': 'Lignes du fichier',
  'import.rendre_resultats.prevo_fera_chaque_ligne': 'Ce que Prévo fera de chaque ligne du fichier',
  'import.rendre_resultats.telecharger_lignes_refusees': 'Télécharger les lignes refusées ({refusees})',
  'import.rendu_ia.entete_libelle': '« {entete} » → <b>{libelle}</b>',
  'import.rendu_ia.ia_rapproche_aucune_colonnes': 'L\'IA ne rapproche aucune de ces colonnes d\'un champ de Prévo.',
  'import.rendu_ia.propositions_ecartees': { one: '{n} proposition écartée (champ inconnu, titre non envoyé ou en double).', other: '{n} propositions écartées (champ inconnu, titre non envoyé ou en double).' },
  'import.rendu_ia.seuls_titres_colonnes_non': 'Seuls les titres des colonnes non reconnues ont été envoyés, jamais le contenu des cellules. Chaque proposition reste « à confirmer ».',
  'import.resoudre_chemin.plus_trois_niveaux_sous': 'plus de trois niveaux sous « {cheminDe} »',
  'import.resoudre_chemin.plusieurs_localisations': 'plusieurs localisations s\'appellent « {nom} » : donnez le chemin complet',
  'import.resultat.annuler_import': 'Annuler cet import',
  'import.resultat.demo_etat_avant_import': 'Démo : l\'état d\'avant l\'import est gardé en mémoire tant que cette page reste ouverte.',
  'import.resultat.fiches_creees': { one: '{n} fiche créée', other: '{n} fiches créées' },
  'import.resultat.fiches_mises_a_jour': { one: '{n} fiche mise à jour', other: '{n} fiches mises à jour' },
  'import.resultat.import_annule': { one: '<b>Import annulé :</b> {tables} est revenue à l\'état d\'avant l\'import.', other: '<b>Import annulé :</b> {tables} sont revenues à l\'état d\'avant l\'import.' },
  'import.resultat.import_arrete': '<b>L\'import s\'est arrêté en cours de route :</b> {message} Des fiches ont déjà été écrites ({tables}) : annulez cet import pour revenir à l\'état d\'avant, puis recommencez.',
  'import.resultat.import_termine': '<b>Import terminé :</b> {creees}, {misesAJour}.',
  'import.resultat.importer_autres_donnees': 'Importer d\'autres données',
  'import.resultat.sauvegarde_faite_juste_avant': 'Sauvegarde faite juste avant l\'import : <b id="import-sauvegarde">{sauvegarde}</b> (Paramètres, « Sauvegardes », type « Avant import »).',
  'import.resume.creer': { one: '{n} à créer', other: '{n} à créer' },
  'import.resume.doublon_suppose': { one: '{n} doublon supposé', other: '{n} doublons supposés' },
  'import.resume.doublon_sur': { one: '{n} doublon sûr (ignoré)', other: '{n} doublons sûrs (ignorés)' },
  'import.resume.identique': { one: '{n} identique', other: '{n} identiques' },
  'import.resume.lignes_lues': { one: '{n} ligne lue', other: '{n} lignes lues' },
  'import.resume.lues': '{lues}.',
  'import.resume.lues_detail': '{lues} : {detail}.',
  'import.resume.mettre_a_jour': { one: '{n} à mettre à jour', other: '{n} à mettre à jour' },
  'import.resume.refusee': { one: '{n} refusée', other: '{n} refusées' },
  'import.resume_lecture.colonnes': { one: '{n} colonne :', other: '{n} colonnes :' },
  'import.resume_lecture.debut_fichier': 'Début du fichier',
  'import.resume_lecture.debut_fichier_ligne_tete': 'Début du fichier : la ligne d\'en-tête est mise en évidence',
  'import.resume_lecture.ligne': 'Ligne',
  'import.resume_lecture.lignes_donnees': { one: '{n} ligne de données, à partir de la ligne {premiere} du fichier ; les lignes vides sont ignorées.', other: '{n} lignes de données, à partir de la ligne {premiere} du fichier ; les lignes vides sont ignorées.' },
  'import.resume_lecture.sans_titre': '(sans titre)',
  'import.resume_lecture.titre': '« {titre} »',
  'import.seconde_equipement.equipement_parent_introuvable_ni': 'équipement parent « {parent} » introuvable (ni dans Prévo, ni dans le fichier)',
  'import.seconde_equipement.equipement_peut_pas_etre': 'un équipement ne peut pas être son propre parent',
  'import.seconde_equipement.localisation_erreur': 'Localisation : {erreur}',
  'import.seconde_gamme.operation': 'Opération',
  'import.seconde_gamme.operation_ajoutee': 'opération ajoutée à la gamme de la ligne {numero}',
  'import.seconde_gamme.operation_deja_gamme_rien': 'opération déjà dans la gamme : rien à ajouter',
  'import.seconde_gamme.valeur_attendue': 'Valeur attendue ({operation})',
  'import.source.classeur': 'classeur',
  'import.source.collage': 'collage',
  'import.source.encodage': '{nature} {encodage}',
  'import.source.feuilles': { one: '{source}, {n} feuille', other: '{source}, {n} feuilles' },
  'import.source.fichier_texte': 'fichier texte',
  'import.statut_colonne.a_confirmer': 'À confirmer',
  'import.statut_colonne.non_utilisee': 'Non utilisée',
  'import.statut_colonne.sure': 'Sûre',
  'import.suivre_progression.ecriture_libelle_table_ecrites_size_nb_tables': 'Écriture : {libelleTable} ({ecritesSize} sur {nbTables})…',
  'import.suivre_progression.preparation': 'Préparation…',
  'import.suivre_progression.sauvegarde_avant_import': 'Sauvegarde avant l\'import…',
  'import.suivre_progression.tables_ecrites': 'Tables écrites',
  'import.tableau_resultat.creees': 'Créées',
  'import.tableau_resultat.fiches_ecrites_table': 'Fiches écrites par table',
  'import.tableau_resultat.mises_jour': 'Mises à jour',
  'import.tableau_resultat.table': 'Table',
  'import.texte_coupe': '{debut}…',
  'import.trouver_code.designe_plusieurs_codes': 'désigne plusieurs codes « {famille} »',
  'import.trouver_code.introuvable_parmi_codes': 'introuvable parmi les codes « {famille} »',
  'import.trouver_technicien.plusieurs_techniciens_appellent': 'plusieurs techniciens s\'appellent « {nom} »',
  'import.trouver_technicien.technicien_introuvable_prevo': 'technicien « {nom} » introuvable dans Prévo',
  'import.type.articles': 'Articles (pièces détachées)',
  'import.type.codes': 'Codes de défaillance',
  'import.type.compteurs': 'Compteurs',
  'import.type.controles': 'Contrôles réglementaires',
  'import.type.equipements': 'Équipements',
  'import.type.fournisseurs': 'Fournisseurs',
  'import.type.gammes': 'Gammes de préventif',
  'import.type.habilitations': 'Habilitations',
  'import.type.historique': 'Historique des interventions',
  'import.type.localisations': 'Localisations',
  'import.type.techniciens': 'Techniciens',
  'import.type_aide.articles': 'Le magasin : un article par ligne, reconnu par sa référence ; fournisseur par son nom (créé s\'il manque) ; le stock initial devient un inventaire.',
  'import.type_aide.codes': 'Symptômes, causes et remèdes : un code par ligne, reconnu par sa famille et son code.',
  'import.type_aide.compteurs': 'Un compteur par ligne : équipement (repère, déjà dans Prévo) et libellé.',
  'import.type_aide.controles': 'Un contrôle par ligne : équipement (repère, déjà dans Prévo) et nature du contrôle.',
  'import.type_aide.equipements': 'Le parc : un équipement par ligne, reconnu par son repère ; localisation par son chemin (« Site > Atelier > Ligne ») ou une colonne par niveau ; équipement parent par son repère.',
  'import.type_aide.fournisseurs': 'Un fournisseur par ligne, reconnu par son nom.',
  'import.type_aide.gammes': 'Une gamme par équipement et libellé ; opérations : une ligne par opération (gamme répétée) ou une colonne d\'opérations séparées par « ; ».',
  'import.type_aide.habilitations': 'Une habilitation par ligne : technicien (« Prénom Nom » ou « Nom Prénom », déjà dans Prévo) et intitulé.',
  'import.type_aide.historique': 'Les interventions passées d\'une autre GMAO : chacune devient un OT clôturé ; l\'ancien numéro est gardé dans le compte rendu.',
  'import.type_aide.localisations': 'Sites, ateliers et lignes : un chemin « Site > Atelier > Ligne » par ligne (séparateur >, / ou \\) ; le type se déduit du niveau.',
  'import.type_aide.techniciens': 'Un technicien par ligne, reconnu par son nom et son prénom.',
});
// ==== fin import ====

// ==== section magasin ====
I18n.ajouter('fr', {
});
// ==== fin magasin ====

// ==== section indicateurs ====
I18n.ajouter('fr', {
});
// ==== fin indicateurs ====

// ==== section rapport ====
I18n.ajouter('fr', {
});
// ==== fin rapport ====

// ==== section accueil ====
I18n.ajouter('fr', {
});
// ==== fin accueil ====

// ==== section equipe ====
I18n.ajouter('fr', {
});
// ==== fin equipe ====

// ==== section acces ====
I18n.ajouter('fr', {
});
// ==== fin acces ====

// ==== section connexion ====
I18n.ajouter('fr', {
});
// ==== fin connexion ====

// ==== section poste ====
I18n.ajouter('fr', {
});
// ==== fin poste ====

// ==== section apropos ====
I18n.ajouter('fr', {
});
// ==== fin apropos ====

// ==== section installation ====
I18n.ajouter('fr', {
});
// ==== fin installation ====

// ==== section porte ====
I18n.ajouter('fr', {
});
// ==== fin porte ====

// ==== section parametres ====
I18n.ajouter('fr', {
});
// ==== fin parametres ====

// ==== section sauvegardes ====
I18n.ajouter('fr', {
});
// ==== fin sauvegardes ====

// ==== section zip ====
I18n.ajouter('fr', {
});
// ==== fin zip ====

// ==== section serveur ====
I18n.ajouter('fr', {
});
// ==== fin serveur ====

// ==== section ia ====
I18n.ajouter('fr', {
});
// ==== fin ia ====
