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
