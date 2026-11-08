'use strict';
// Textes italiens de Prévo : italien, locale it-IT (chantier multilingue, Lot 5, T343 ; version 2.1.0).
// Traduction automatique assumée (l'interface le dit : « traduction automatique — corrections bienvenues »).
// Mêmes sections que js/i18n/fr.js, dans le même ordre : une section par domaine. On traduit par groupes de
// domaines, une tâche par groupe, chacune dans ses sections seulement : jamais deux tâches sur les mêmes lignes.
// Dans chaque bloc : les clés de la même section de fr.js, triées, une par ligne, chaînes entre apostrophes
// simples, échappements gardés (jamais d'espace insécable écrit en clair : \u00a0, \u202f), mêmes variables {…}
// que le français ; un pluriel { one, other } là où le français en a un, un texte simple ailleurs.
// Vocabulaire : docs/GLOSSAIRE.md (colonne de la langue). Clé absente : texte français affiché (avertissement
// dans la console). Pas d'aide longue traduite (D158) : l'aide longue s'affiche en anglais.
// Contrôle : py -X utf8 outils/controler_textes.py --langue it [--domaine <domaine>].
// Déclaré dans js/i18n/langues.js seulement quand toutes ses sections sont traduites (Lot 5).

// ==== section commun ====
I18n.ajouter('it', {
  'commun.bouton.actualiser': 'Aggiorna',
  'commun.bouton.ajouter': 'Aggiungi',
  'commun.bouton.annuler': 'Annulla',
  'commun.bouton.continuer': 'Continua',
  'commun.bouton.desactiver': 'Disattiva',
  'commun.bouton.enregistrer': 'Salva',
  'commun.bouton.fermer': 'Chiudi',
  'commun.bouton.imprimer': 'Stampa',
  'commun.bouton.modifier': 'Modifica',
  'commun.brouillon.abandonner': 'Abbandona la bozza',
  'commun.brouillon.effacer': 'Cancella la bozza',
  'commun.brouillon.repris': 'Bozza ripristinata: inserita su questo dispositivo il {quand}, non ancora salvata.',
  'commun.champ.article': 'Articolo',
  'commun.champ.commentaire': 'Commento',
  'commun.champ.criticite': 'Criticità',
  'commun.champ.date': 'Data',
  'commun.champ.designation': 'Designazione',
  'commun.champ.equipement': 'Attrezzatura',
  'commun.champ.numero': 'N.',
  'commun.champ.prenom': 'Nome',
  'commun.champ.priorite': 'Priorità',
  'commun.champ.prix_unitaire': 'Prezzo unitario',
  'commun.champ.quantite': 'Quantità',
  'commun.champ.reference': 'Codice',
  'commun.champ.repere': 'Codice',
  'commun.champ.statut': 'Stato',
  'commun.champ.symptome': 'Sintomo',
  'commun.champ.technicien': 'Tecnico',
  'commun.liste.non_choisi': '(non selezionato)',
  'commun.message.aucune_modification': 'Nessuna modifica da salvare.',
  'commun.message.champ_obligatoire': 'campo obbligatorio',
  'commun.message.erreur_inconnue': 'errore sconosciuto',
  'commun.message.fichier_trop_volumineux': 'Questo file è troppo grande (massimo 9 MB).',
  'commun.message.ot_introuvable': 'L\'ordine di lavoro {otId} non è stato trovato.',
  'commun.message.saisi_sur_autre_poste': 'Potrebbe essere stato inserito su un\'altra postazione: aggiorna.',
  'commun.message.serveur_a_repondu': 'Il server ha risposto «{status}».',
});
// ==== fin commun ====

// ==== section schema ====
I18n.ajouter('it', {
  'schema.achats.article_id': 'Articolo',
  'schema.achats.date': 'Data',
  'schema.achats.date_reception': 'Data di ricevimento',
  'schema.achats.fournisseur_id': 'Fornitore',
  'schema.achats.id': 'ID',
  'schema.achats.prix_unitaire': 'Prezzo unitario',
  'schema.achats.quantite': 'Quantità',
  'schema.achats.statut': 'Stato',
  'schema.article_equipement.article_id': 'Articolo',
  'schema.article_equipement.equipement_id': 'Attrezzatura',
  'schema.article_equipement.id': 'ID',
  'schema.article_equipement.quantite': 'Quantità',
  'schema.articles.actif': 'Attivo',
  'schema.articles.critique': 'Articolo critico',
  'schema.articles.delai_jours': 'Tempo di approvvigionamento (giorni)',
  'schema.articles.designation': 'Designazione',
  'schema.articles.emplacement': 'Posizione di stoccaggio',
  'schema.articles.fabricant': 'Costruttore',
  'schema.articles.fournisseur_id': 'Fornitore',
  'schema.articles.id': 'ID',
  'schema.articles.point_commande': 'Punto di riordino',
  'schema.articles.prix_unitaire': 'Prezzo unitario',
  'schema.articles.qte_commande': 'Quantità da ordinare',
  'schema.articles.ref_fabricant': 'Codice del costruttore',
  'schema.articles.reference': 'Codice',
  'schema.articles.stock': 'Scorte',
  'schema.articles.stock_securite': 'Scorta di sicurezza',
  'schema.articles.unite': 'Unità',
  'schema.codes_defaillance.code': 'Codice',
  'schema.codes_defaillance.famille': 'Famiglia',
  'schema.codes_defaillance.id': 'ID',
  'schema.codes_defaillance.libelle': 'Etichetta',
  'schema.compteurs.equipement_id': 'Attrezzatura',
  'schema.compteurs.id': 'ID',
  'schema.compteurs.libelle': 'Etichetta',
  'schema.compteurs.unite': 'Unità',
  'schema.controles_reglementaires.derniere_date': 'Data dell\'ultima verifica',
  'schema.controles_reglementaires.equipement_id': 'Attrezzatura',
  'schema.controles_reglementaires.id': 'ID',
  'schema.controles_reglementaires.nature': 'Tipo di verifica',
  'schema.controles_reglementaires.observations': 'Osservazioni',
  'schema.controles_reglementaires.observations_levees': 'Osservazioni risolte',
  'schema.controles_reglementaires.organisme': 'Organismo di controllo',
  'schema.controles_reglementaires.periodicite_mois': 'Periodicità (mesi)',
  'schema.controles_reglementaires.prochaine_date': 'Data della prossima verifica',
  'schema.controles_reglementaires.rapport': 'Rapporto',
  'schema.controles_reglementaires.texte_reference': 'Testo di riferimento',
  'schema.demandes.date_decision': 'Data della decisione',
  'schema.demandes.date_heure': 'Data e ora della richiesta',
  'schema.demandes.demandeur': 'Richiedente',
  'schema.demandes.description': 'Descrizione',
  'schema.demandes.equipement_id': 'Attrezzatura',
  'schema.demandes.id': 'ID',
  'schema.demandes.impact': 'Impatto',
  'schema.demandes.motif_decision': 'Motivo della decisione',
  'schema.demandes.ot_id': 'Ordine di lavoro collegato',
  'schema.demandes.ot_origine_id': 'OdL di origine (preventiva)',
  'schema.demandes.photo': 'Foto',
  'schema.demandes.statut': 'Stato',
  'schema.demandes.symptome': 'Sintomo osservato',
  'schema.demandes.symptome_code': 'Codice sintomo',
  'schema.equipements.actif': 'Attiva',
  'schema.equipements.consignation': 'Messa in sicurezza',
  'schema.equipements.criticite': 'Criticità',
  'schema.equipements.date_mes': 'Data di messa in servizio',
  'schema.equipements.designation': 'Designazione',
  'schema.equipements.document': 'Documento',
  'schema.equipements.habilitation_requise': 'Abilitazione richiesta',
  'schema.equipements.heures_fonct_jour': 'Ore di funzionamento al giorno',
  'schema.equipements.id': 'ID',
  'schema.equipements.localisation_id': 'Ubicazione',
  'schema.equipements.marque': 'Marca',
  'schema.equipements.modele': 'Modello',
  'schema.equipements.num_serie': 'Numero di serie',
  'schema.equipements.parent_id': 'Attrezzatura madre',
  'schema.equipements.repere': 'Codice',
  'schema.equipements.statut': 'Stato',
  'schema.equipements.valeur_remplacement': 'Valore di sostituzione ({devise} IVA esclusa)',
  'schema.fournisseurs.contact': 'Contatto',
  'schema.fournisseurs.email': 'E-mail',
  'schema.fournisseurs.id': 'ID',
  'schema.fournisseurs.nom': 'Nome',
  'schema.fournisseurs.telephone': 'Telefono',
  'schema.gamme_operations.gamme_id': 'Piano di manutenzione',
  'schema.gamme_operations.id': 'ID',
  'schema.gamme_operations.operation': 'Attività',
  'schema.gamme_operations.ordre': 'Sequenza',
  'schema.gamme_operations.valeur_attendue': 'Valore atteso',
  'schema.gammes.actif': 'Attivo',
  'schema.gammes.avance_jours': 'Anticipo (giorni)',
  'schema.gammes.compteur_id': 'Contatore',
  'schema.gammes.consignes': 'Istruzioni di sicurezza',
  'schema.gammes.declencheur': 'Attivatore',
  'schema.gammes.derniere_realisation': 'Ultima esecuzione',
  'schema.gammes.equipement_id': 'Attrezzatura',
  'schema.gammes.id': 'ID',
  'schema.gammes.libelle': 'Etichetta',
  'schema.gammes.periodicite_jours': 'Periodicità (giorni)',
  'schema.gammes.periodicite_unites': 'Periodicità (unità del contatore)',
  'schema.gammes.prochaine_echeance': 'Prossima scadenza',
  'schema.gammes.releve_derniere_realisation': 'Lettura all\'ultima esecuzione',
  'schema.gammes.seuil': 'Soglia',
  'schema.gammes.temps_prevu_h': 'Tempo previsto (ore)',
  'schema.habilitations.date_echeance': 'Data di scadenza',
  'schema.habilitations.date_obtention': 'Data di conseguimento',
  'schema.habilitations.id': 'ID',
  'schema.habilitations.intitule': 'Nome',
  'schema.habilitations.technicien_id': 'Tecnico',
  'schema.journal.action': 'Azione',
  'schema.journal.date_heure': 'Data e ora',
  'schema.journal.id': 'ID',
  'schema.journal.id_ligne': 'ID della riga',
  'schema.journal.poste': 'Postazione',
  'schema.journal.profil': 'Profilo',
  'schema.journal.table': 'Tabella',
  'schema.localisations.id': 'ID',
  'schema.localisations.libelle': 'Etichetta',
  'schema.localisations.parent_id': 'Ubicazione madre',
  'schema.localisations.type': 'Tipo',
  'schema.mouvements_stock.article_id': 'Articolo',
  'schema.mouvements_stock.commentaire': 'Commento',
  'schema.mouvements_stock.date': 'Data e ora',
  'schema.mouvements_stock.id': 'ID',
  'schema.mouvements_stock.ot_id': 'Ordine di lavoro',
  'schema.mouvements_stock.quantite': 'Quantità',
  'schema.mouvements_stock.type': 'Tipo',
  'schema.mouvements_stock.utilisateur': 'Utente',
  'schema.ordres_travail.anomalie_constatee': 'Anomalia riscontrata',
  'schema.ordres_travail.arret_production': 'Fermo produzione',
  'schema.ordres_travail.astuce': 'Suggerimento per la prossima volta',
  'schema.ordres_travail.cause_code': 'Codice causa',
  'schema.ordres_travail.compte_rendu': 'Rapporto di intervento',
  'schema.ordres_travail.consignes': 'Istruzioni di sicurezza',
  'schema.ordres_travail.cout_soustraitance': 'Costo di subappalto',
  'schema.ordres_travail.date_cloture_admin': 'Data di chiusura amministrativa',
  'schema.ordres_travail.date_cloture_tech': 'Data di chiusura tecnica',
  'schema.ordres_travail.date_creation': 'Data di creazione',
  'schema.ordres_travail.date_debut': 'Data di inizio',
  'schema.ordres_travail.date_fin': 'Data di fine',
  'schema.ordres_travail.date_prevue': 'Data prevista',
  'schema.ordres_travail.di_id': 'Richiesta di intervento',
  'schema.ordres_travail.duree_arret_h': 'Tempo di fermo (ore)',
  'schema.ordres_travail.equipement_id': 'Attrezzatura',
  'schema.ordres_travail.gamme_id': 'Piano di manutenzione preventiva',
  'schema.ordres_travail.id': 'ID',
  'schema.ordres_travail.motif_annulation': 'Motivo dell\'annullamento',
  'schema.ordres_travail.motif_attente': 'Motivo dell\'attesa',
  'schema.ordres_travail.origine': 'Origine',
  'schema.ordres_travail.ot_lie_id': 'Ordine di lavoro collegato',
  'schema.ordres_travail.priorite': 'Priorità',
  'schema.ordres_travail.remede_code': 'Codice rimedio',
  'schema.ordres_travail.remise_service': 'Rimesso in servizio in sicurezza',
  'schema.ordres_travail.statut': 'Stato',
  'schema.ordres_travail.symptome_code': 'Codice sintomo',
  'schema.ordres_travail.technicien_id': 'Tecnico',
  'schema.ordres_travail.temps_prevu_h': 'Tempo previsto (ore)',
  'schema.ordres_travail.titre': 'Titolo',
  'schema.ordres_travail.travail_a_faire': 'Lavoro da eseguire',
  'schema.ordres_travail.type': 'Tipo',
  'schema.ot_operations.fait': 'Fatto',
  'schema.ot_operations.id': 'ID',
  'schema.ot_operations.operation': 'Attività',
  'schema.ot_operations.ordre': 'Sequenza',
  'schema.ot_operations.ot_id': 'Ordine di lavoro',
  'schema.ot_operations.valeur_attendue': 'Valore atteso',
  'schema.ot_operations.valeur_mesuree': 'Valore misurato',
  'schema.ot_pieces.article_id': 'Articolo',
  'schema.ot_pieces.id': 'ID',
  'schema.ot_pieces.ot_id': 'Ordine di lavoro',
  'schema.ot_pieces.quantite_prevue': 'Quantità prevista',
  'schema.ot_temps.date': 'Data',
  'schema.ot_temps.heures': 'Ore',
  'schema.ot_temps.id': 'ID',
  'schema.ot_temps.ot_id': 'Ordine di lavoro',
  'schema.ot_temps.technicien_id': 'Tecnico',
  'schema.parametres.cle': 'Chiave',
  'schema.parametres.valeur': 'Valore',
  'schema.releves.compteur_id': 'Contatore',
  'schema.releves.date': 'Data',
  'schema.releves.id': 'ID',
  'schema.releves.utilisateur': 'Utente',
  'schema.releves.valeur': 'Valore',
  'schema.tables.achats': 'Acquisti',
  'schema.tables.article_equipement': 'Articoli per attrezzatura',
  'schema.tables.articles': 'Articoli (ricambi)',
  'schema.tables.codes_defaillance': 'Codici di guasto',
  'schema.tables.compteurs': 'Contatori',
  'schema.tables.controles_reglementaires': 'Verifiche di legge',
  'schema.tables.demandes': 'Richieste di intervento',
  'schema.tables.equipements': 'Attrezzature',
  'schema.tables.fournisseurs': 'Fornitori',
  'schema.tables.gamme_operations': 'Attività dei piani di manutenzione',
  'schema.tables.gammes': 'Piani di manutenzione preventiva',
  'schema.tables.habilitations': 'Abilitazioni',
  'schema.tables.journal': 'Registro delle modifiche',
  'schema.tables.localisations': 'Ubicazioni',
  'schema.tables.mouvements_stock': 'Movimenti di magazzino',
  'schema.tables.ordres_travail': 'Ordini di lavoro',
  'schema.tables.ot_operations': 'Attività degli ordini di lavoro',
  'schema.tables.ot_pieces': 'Ricambi previsti negli ordini di lavoro',
  'schema.tables.ot_temps': 'Tempo impiegato sugli ordini di lavoro',
  'schema.tables.parametres': 'Impostazioni',
  'schema.tables.releves': 'Letture del contatore',
  'schema.tables.techniciens': 'Tecnici',
  'schema.tables.wiki_journal': 'Registro del wiki',
  'schema.tables.wiki_pages': 'Pagine del wiki',
  'schema.techniciens.actif': 'Attivo',
  'schema.techniciens.capacite_h_semaine': 'Capacità (ore settimanali)',
  'schema.techniciens.id': 'ID',
  'schema.techniciens.metier': 'Specializzazione',
  'schema.techniciens.nom': 'Cognome',
  'schema.techniciens.prenom': 'Nome',
  'schema.techniciens.taux_horaire': 'Tariffa oraria',
  'schema.wiki_journal.anterieure': 'Intervento precedente',
  'schema.wiki_journal.changements': 'Modifiche',
  'schema.wiki_journal.contradictions': 'Contraddizioni',
  'schema.wiki_journal.cree_le': 'Creata il',
  'schema.wiki_journal.date_intervention': 'Data dell\'intervento',
  'schema.wiki_journal.decide_le': 'Deciso il',
  'schema.wiki_journal.decide_par': 'Deciso da',
  'schema.wiki_journal.essais': 'Tentativi',
  'schema.wiki_journal.id': 'ID',
  'schema.wiki_journal.modele': 'Modello',
  'schema.wiki_journal.motif': 'Motivo',
  'schema.wiki_journal.nature': 'Natura',
  'schema.wiki_journal.ordre': 'Ordine di elaborazione',
  'schema.wiki_journal.ot_id': 'Ordine di lavoro',
  'schema.wiki_journal.pages': 'Pagine interessate',
  'schema.wiki_journal.raisons': 'Motivi del rifiuto',
  'schema.wiki_journal.statut': 'Stato',
  'schema.wiki_journal.traite_le': 'Elaborata il',
  'schema.wiki_pages.article_id': 'Articolo',
  'schema.wiki_pages.cause_code': 'Codice causa',
  'schema.wiki_pages.cle': 'Chiave (titolo confrontabile)',
  'schema.wiki_pages.cree_le': 'Creata il',
  'schema.wiki_pages.derniere_entree': 'Ultima voce applicata',
  'schema.wiki_pages.equipement_id': 'Attrezzatura',
  'schema.wiki_pages.id': 'ID',
  'schema.wiki_pages.liens': 'Pagine collegate',
  'schema.wiki_pages.modele': 'Modello',
  'schema.wiki_pages.modifie_le': 'Modificata il',
  'schema.wiki_pages.origine': 'Origine',
  'schema.wiki_pages.ot_cites': 'OdL citati',
  'schema.wiki_pages.rattache_a': 'Collegata alla pagina',
  'schema.wiki_pages.statut': 'Stato',
  'schema.wiki_pages.texte': 'Testo',
  'schema.wiki_pages.titre': 'Titolo',
  'schema.wiki_pages.type': 'Tipo',
  'schema.wiki_pages.valide_le': 'Convalidata il',
  'schema.wiki_pages.valide_par': 'Convalidata da',
  'schema.wiki_pages.version': 'Versione',
});
// ==== fin schema ====

// ==== section valeurs ====
I18n.ajouter('it', {
  'valeurs.achats.statut.commandée': 'ordinato',
  'valeurs.achats.statut.demandée': 'richiesto',
  'valeurs.achats.statut.reçue': 'ricevuto',
  'valeurs.codes_defaillance.famille.cause': 'causa',
  'valeurs.codes_defaillance.famille.remède': 'rimedio',
  'valeurs.codes_defaillance.famille.symptôme': 'sintomo',
  'valeurs.demandes.impact.arrêt': 'fermo',
  'valeurs.demandes.impact.dégradé': 'degradato',
  'valeurs.demandes.impact.gêne': 'intralcio',
  'valeurs.demandes.impact.sécurité': 'sicurezza',
  'valeurs.demandes.statut.Acceptée': 'Accettata',
  'valeurs.demandes.statut.Différée': 'Rinviata',
  'valeurs.demandes.statut.Nouvelle': 'Nuova',
  'valeurs.demandes.statut.Refusée': 'Rifiutata',
  'valeurs.demandes.statut.Regroupée': 'Accorpata',
  'valeurs.equipements.criticite.A': 'A',
  'valeurs.equipements.criticite.B': 'B',
  'valeurs.equipements.criticite.C': 'C',
  'valeurs.equipements.statut.arrêt': 'ferma',
  'valeurs.equipements.statut.en service': 'in servizio',
  'valeurs.equipements.statut.rebut': 'dismessa',
  'valeurs.gammes.declencheur.compteur': 'contatore',
  'valeurs.gammes.declencheur.date': 'data',
  'valeurs.gammes.declencheur.seuil': 'soglia',
  'valeurs.localisations.type.atelier': 'officina',
  'valeurs.localisations.type.ligne': 'linea',
  'valeurs.localisations.type.site': 'sito',
  'valeurs.mouvements_stock.type.entrée': 'carico',
  'valeurs.mouvements_stock.type.inventaire': 'inventario',
  'valeurs.mouvements_stock.type.retour': 'reso',
  'valeurs.mouvements_stock.type.sortie': 'scarico',
  'valeurs.ordres_travail.origine.DI': 'Richiesta',
  'valeurs.ordres_travail.origine.manuel': 'manuale',
  'valeurs.ordres_travail.origine.préventif': 'preventiva',
  'valeurs.ordres_travail.origine.urgence': 'emergenza',
  'valeurs.ordres_travail.priorite.P1': 'P1',
  'valeurs.ordres_travail.priorite.P2': 'P2',
  'valeurs.ordres_travail.priorite.P3': 'P3',
  'valeurs.ordres_travail.priorite.P4': 'P4',
  'valeurs.ordres_travail.statut.Annulé': 'Annullato',
  'valeurs.ordres_travail.statut.Clôturé administrativement': 'Chiuso amministrativamente',
  'valeurs.ordres_travail.statut.Clôturé techniquement': 'Chiuso tecnicamente',
  'valeurs.ordres_travail.statut.Créé': 'Creato',
  'valeurs.ordres_travail.statut.En attente': 'In attesa',
  'valeurs.ordres_travail.statut.En cours': 'In corso',
  'valeurs.ordres_travail.statut.Planifié': 'Pianificato',
  'valeurs.ordres_travail.statut.Préparé': 'Preparato',
  'valeurs.ordres_travail.type.amélioration': 'miglioramento',
  'valeurs.ordres_travail.type.correctif différé': 'correttiva differita',
  'valeurs.ordres_travail.type.correctif immédiat': 'correttiva immediata',
  'valeurs.ordres_travail.type.préventif conditionnel': 'preventiva su condizione',
  'valeurs.ordres_travail.type.préventif systématique': 'preventiva a calendario',
  'valeurs.ordres_travail.type.réglementaire': 'di legge',
  'valeurs.wiki_journal.nature.décision': 'decisione',
  'valeurs.wiki_journal.nature.ingestion': 'acquisizione',
  'valeurs.wiki_journal.nature.manuel': 'manuale',
  'valeurs.wiki_journal.statut.appliquée': 'applicata',
  'valeurs.wiki_journal.statut.en file': 'in coda',
  'valeurs.wiki_journal.statut.refusée': 'rifiutata',
  'valeurs.wiki_journal.statut.rejetée': 'scartata',
  'valeurs.wiki_journal.statut.rien à ajouter': 'niente da aggiungere',
  'valeurs.wiki_journal.statut.validée': 'convalidata',
  'valeurs.wiki_journal.statut.à refaire': 'da rifare',
  'valeurs.wiki_journal.statut.à valider': 'da convalidare',
  'valeurs.wiki_pages.origine.IA': 'IA',
  'valeurs.wiki_pages.origine.IA et manuel': 'IA e manuale',
  'valeurs.wiki_pages.origine.manuel': 'manuale',
  'valeurs.wiki_pages.statut.active': 'attiva',
  'valeurs.wiki_pages.statut.archivée': 'archiviata',
  'valeurs.wiki_pages.type.composant': 'componente',
  'valeurs.wiki_pages.type.mode': 'modo di guasto',
  'valeurs.wiki_pages.type.savoir-faire': 'know-how',
  'valeurs.wiki_pages.type.équipement': 'attrezzatura',
});
// ==== fin valeurs ====

// ==== section socle ====
I18n.ajouter('it', {
  'socle.analyser.ligne_contient_plus_valeurs': '{reperage}: questa riga contiene più valori di quante colonne ha l\'intestazione; il valore «{valeurIgnoree}» (colonna {colonneIgnoree}) viene ignorato.',
  'socle.analyser.ligne_structure_fichier_abimee': '{descriptionLibelle}, riga {numero} di {fichier}: struttura del file danneggiata ({erreurMessage}), ad esempio delle virgolette non chiuse. I valori di questa riga e delle successive potrebbero risultare sfalsati.',
  'socle.analyser.pas_utf_8_sans': '{descriptionLibelle}: {fichier} non è in UTF-8 (probabilmente salvato da Excel in formato «CSV (separatore: punto e virgola)»); è stato letto come Windows-1252. Sarà riscritto in UTF-8 alla prossima modifica della tabella.',
  'socle.analyser.reperage_champ_libelle_contient_lu_valeur': '{reperage}: «{champLibelle}» contiene «{luValeur}», {explication}.',
  'socle.app.gmao': 'CMMS',
  'socle.app.menu': 'Menu',
  'socle.app.propos': 'Informazioni',
  'socle.appliquer_repli.deplier_menu': 'Espandi il menu',
  'socle.appliquer_repli.replier_menu': 'Comprimi il menu',
  'socle.associer_colonnes.colonne_apparait_deux_fois': '{descriptionLibelle}: la colonna «{nomColonne}» compare due volte in {fichier}; la seconda è conservata a parte con il nome «{nomConserve}» e non è usata da Prévo.',
  'socle.associer_colonnes.colonne_fait_pas_partie': '{descriptionLibelle}: la colonna «{nomConserve}» di {fichier} non fa parte di Prévo; viene conservata così com\'è (riscritta in fondo al file).',
  'socle.associer_colonnes.colonne_numero': 'colonna {numero}',
  'socle.badge_priorite.priorite_code': 'Priorità {code}',
  'socle.badge_priorite.priorite_inconnue': 'Priorità sconosciuta',
  'socle.bandeau_changement.donnees_ont_change_autre': 'Alcuni dati sono cambiati su un\'altra postazione',
  'socle.bandeau_demo.demo_rien_enregistre': 'Demo — nulla viene salvato',
  'socle.bandeau_fichiers_abimes.fichier_abime': 'File danneggiato',
  'socle.bandeau_fichiers_abimes.fichiers_abimes': 'File danneggiati',
  'socle.bandeau_fichiers_abimes.prevenez_responsable': '<b>{titre}: avvisa il responsabile.</b> {suite}',
  'socle.bandeau_fichiers_abimes.tant_ils_sont_pas': 'Finché non vengono riparati, Prévo rifiuta i salvataggi che li riguardano, senza perdere nulla.',
  'socle.bandeau_fichiers_abimes.tant_pas_repare_prevo': 'Finché non viene riparato, Prévo rifiuta i salvataggi che lo riguardano, senza perdere nulla.',
  'socle.bandeau_fichiers_abimes.tete_coupe_guillemet_non': '<b>{titre}: {fichiers}.</b> Intestazione tagliata, virgolette non chiuse o valori oltre l\'intestazione: Prévo non lo salva più, per non perdere nulla. Correggi il file, ripristina un backup o importa uno ZIP; i dettagli sono in Impostazioni › Controllo della base dati.',
  'socle.bandeau_fichiers_laisses.fichier_abime_laisse_tel': 'File danneggiato lasciato com\'è',
  'socle.bandeau_fichiers_laisses.fichiers_abimes_laisses_tels': 'File danneggiati lasciati così come sono',
  'socle.bandeau_fichiers_laisses.tete_illisible_lignes_reecriture': '<b>{titre}: {fichiers}.</b> Intestazione illeggibile, o righe che una riscrittura farebbe perdere: Prévo non lo riscrive per portarlo al formato {version}. Correggi il file, oppure ripristina un backup; i dettagli sono in Impostazioni › Controllo della base dati.',
  'socle.bandeau_format_en_attente.fichiers_donnees_sont_pas': '<b>I file di dati non sono ancora nel formato {courant}</b> (trovato il formato {depart}). È il server Prévo ad aggiornarli, all\'avvio, dopo un backup; questo browser non li tocca. Se questo messaggio resta visibile, chiudi Excel (e ogni programma che ha aperto un file di dati), poi riavvia Prévo. Nel frattempo gli OdL preventivi scaduti non vengono generati automaticamente.',
  'socle.btn_base_demo.atelier_fictif_complet_pourrez': 'Un\'officina fittizia completa, che potrai modificare o sostituire',
  'socle.btn_base_demo.partir_donnees_demo': 'Parti dai dati demo',
  'socle.btn_base_vide.23_fichiers_csv_seuls': '23 file CSV con le sole intestazioni di colonna',
  'socle.btn_base_vide.creer_base_vide': 'Crea una base vuota',
  'socle.btn_demo.atelier_fictif_rien_enregistre': 'Officina fittizia, nulla viene salvato',
  'socle.btn_demo.essayer_donnees_demo': 'Prova con i dati demo',
  'socle.btn_dossier.choisir_dossier_donnees': 'Scegli la cartella dei dati',
  'socle.btn_dossier.fichiers_csv_restent_pc': 'I file CSV restano su questo PC (Chrome o Edge)',
  'socle.btn_explications.explications': 'Spiegazioni',
  'socle.btn_explications.revoir_explication_ecran': 'Rivedi la spiegazione di questa schermata',
  'socle.btn_explications_mobile.explications_ecran': 'Spiegazioni di questa schermata',
  'socle.btn_export_demo.exporter_zip': 'Esporta in ZIP',
  'socle.btn_replier.replier_menu': 'Comprimi il menu',
  'socle.btn_reprendre.reprendre_dossier_precedent': 'Riprendi la cartella precedente',
  'socle.btn_telecharger.gratuit_libre_installez_travailler': 'Gratuito e libero: installalo per lavorare sui tuoi dati.',
  'socle.btn_telecharger.telecharger_prevo': 'Scarica Prévo',
  'socle.changer_profil.profil_libelle_affiche': 'Profilo: {libelleAffiche}.',
  'socle.chargement.chargement': 'Caricamento…',
  'socle.charger_echarts.bibliotheque_graphiques_js_lib': 'Non è stato possibile caricare la libreria dei grafici (js/lib/echarts.min.js).',
  'socle.charger_image.image_peut_pas_etre': 'Questa immagine non può essere letta (formato non supportato?).',
  'socle.charger_script_demo.jeu_demo_js_demo': 'Non è stato possibile caricare i dati demo (js/demo-donnees.js).',
  'socle.charger_sheet_js.bibliotheque_lecture_fichiers_excel': 'Non è stato possibile caricare la libreria di lettura dei file Excel (js/lib/xlsx.full.min.js).',
  'socle.choisir.choix_dossier': 'scelta della cartella',
  'socle.confirmer.confirmation': 'Conferma',
  'socle.confirmer.confirmer': 'Conferma',
  'socle.connexion_avec_compte.ai_compte': 'Ho un account',
  'socle.connexion_changer.enregistrer_continuer': 'Salva e continua',
  'socle.connexion_enrolement.entrez_nom': 'Inserisci il tuo nome',
  'socle.connexion_enrolement.nom_inscrit_demandes_appareil': 'Il tuo nome è indicato sulle tue richieste; questo dispositivo resterà riconosciuto senza password.',
  'socle.connexion_formulaire.forme_prenom_nom_donne': 'Nel formato nome.cognome, fornito dal responsabile.',
  'socle.connexion_formulaire.identifiant': 'Nome utente',
  'socle.connexion_formulaire.mot_passe': 'Password',
  'socle.connexion_formulaire.rester_connecte_appareil': 'Resta connesso su questo dispositivo',
  'socle.connexion_mdp_deconnexion.deconnecter': 'Esci',
  'socle.connexion_mot_de_passe_panneau.12_caracteres_moins_256': 'Almeno 12 caratteri, al massimo 256, nessuna regola di composizione: si consiglia una frase di più parole.',
  'socle.connexion_mot_de_passe_panneau.confirmation': 'Conferma',
  'socle.connexion_mot_de_passe_panneau.mot_passe_actuel_provisoire': 'Password attuale (provvisoria)',
  'socle.connexion_mot_de_passe_panneau.nouveau_mot_passe': 'Nuova password',
  'socle.connexion_sous_titre.chaque_personne_compte_serveur': 'Ogni persona ha il proprio account; il server verifica i permessi.',
  'socle.connexion_titre.connexion': 'Accesso',
  'socle.connexion_valider.connecter': 'Accedi',
  'socle.constructor.action_refusee': 'Azione rifiutata.',
  'socle.constructor.donnees_viennent_version_plus': 'Questi dati provengono da una versione più recente di Prévo (formato {format} dei file; questa versione legge fino al formato {version}): vengono aperti in sola lettura e nulla viene salvato. Aprili con l\'ultima versione di Prévo.',
  'socle.constructor.fichier_abime_tete_coupe': 'Il file {fichier} è danneggiato (intestazione tagliata, virgolette non chiuse o valori oltre l\'intestazione): Prévo non lo salva più, per non perdere nulla. Correggilo, ripristina un backup o importa uno ZIP (Impostazioni); i dettagli sono in Impostazioni › Controllo della base dati.',
  'socle.constructor.fichier_ete_modifie_meme': 'Il file è stato modificato contemporaneamente su un\'altra postazione.',
  'socle.constructor.lecture_ecriture_fichier_impossible': 'Lettura o scrittura del file impossibile.',
  'socle.construire_menus.plus': 'Altro',
  'socle.controler_coherence.demande_acceptee_mais_aucun': 'Richiesta {id}: è «Accettata» ma non ha alcun ordine di lavoro collegato. Riaprila o collegala al suo ordine di lavoro.',
  'socle.controler_coherence.demande_acceptee_mais_ordre': 'Richiesta {id}: è «Accettata» ma il suo ordine di lavoro «{ot_id}» non esiste.',
  'socle.controler_coherence.ordre_travail_vient_demande': 'Ordine di lavoro {id}: proviene dalla richiesta «{di_id}», che è «{statut}» (né accettata né accorpata). Accetta o accorpa la richiesta, oppure annulla l\'ordine di lavoro.',
  'socle.controler_coherence.sans_identifiant': '(senza ID)',
  'socle.controler_identifiants.identifiant_apparait_plusieurs_fois': '{descriptionLibelle}: l\'ID «{cle}» compare più volte in {fichier} (riga di dati n. {numero}). Prévo trova solo la prima riga: assegna un ID univoco alle altre.',
  'socle.controler_identifiants.pas_identifiant_colonne_vide': '{descriptionLibelle}: la {reperageLigne} di {fichier} non ha un ID (colonna «{cle}» vuota). Completalo o elimina la riga nel file.',
  'socle.controler_references.existe_mais_lieu': 'esiste in {descriptionCibleLibelle} ma con {familleTrouvee} invece di {filtre}',
  'socle.controler_references.existe_pas': 'non esiste in {descriptionCibleLibelle} ({filtre})',
  'socle.controler_references.existe_pas_sans_filtre': 'non esiste in {descriptionCibleLibelle}',
  'socle.controler_references.reperage_champ_libelle_vaut_valeur': '{reperage}: «{champLibelle}» vale «{valeur}», che {explication}.',
  'socle.controler_wiki.changements_illisibles': '(modifiche illeggibili)',
  'socle.controler_wiki.cite_aucun_ot': 'non cita alcun OdL.',
  'socle.controler_wiki.cite_ot_existe_pas': 'cita l\'OdL «{ot}», che non esiste.',
  'socle.controler_wiki.entree_journal_wiki_contradiction': { one: 'Voce {entreeId} del registro del wiki: contraddizione aperta da più di {n} giorno nella pagina «{page}».', other: 'Voce {entreeId} del registro del wiki: contraddizione aperta da più di {n} giorni nella pagina «{page}».' },
  'socle.controler_wiki.entree_journal_wiki_validee': 'Voce {entreeId} del registro del wiki: è «convalidata» ma le sue modifiche non sono nelle pagine ({pages}).',
  'socle.controler_wiki.lien_vers_page_inexistante': 'collegamento a una pagina inesistente o archiviata («{lien}»).',
  'socle.controler_wiki.meme_titre_page_deux': 'stesso titolo della pagina {page} (due pagine attive con la stessa chiave).',
  'socle.controler_wiki.page_wiki': 'Pagina del wiki {id} («{pageTitre}»): {message}',
  'socle.controler_wiki.rattachee_page_archivee': 'collegata alla pagina archiviata «{mereTitre}» ({mereId}).',
  'socle.controler_wiki.sous_page_page_archivee': 'sottopagina della pagina archiviata «{mereTitre}» ({mereId}).',
  'socle.controler_wiki.type_page_retire_panne': 'tipo di pagina rimosso («{pageType}»: un guasto è una pagina calcolata da Prévo); archiviala.',
  'socle.creer.ajout_fichier': 'aggiunta al file',
  'socle.creer.aucune_table_restauree': 'nessuna',
  'socle.creer.contenu_ajouter_doit_commencer': 'Il contenuto da aggiungere deve iniziare con la riga di intestazione.',
  'socle.creer.contenu_ajouter_doit_etre': 'Il contenuto da aggiungere deve essere codificato in UTF-8.',
  'socle.creer.demo_rien_enregistre': 'Demo — nulla viene salvato',
  'socle.creer.document_existe_deja': 'Il documento {nom} esiste già.',
  'socle.creer.document_porte_deja_nom': 'Esiste già un documento con questo nome.',
  'socle.creer.dossier_name': 'Cartella «{name}»',
  'socle.creer.enregistrement_document': 'salvataggio del documento',
  'socle.creer.enregistrement_table': 'salvataggio della tabella',
  'socle.creer.fichier_csv_ete_modifie': 'Il file {nomTable}.csv è stato modificato da un\'altra postazione.',
  'socle.creer.fichier_csv_existe_deja': 'Il file {nomTable}.csv esiste già.',
  'socle.creer.fichier_csv_existe_plus': 'Il file {nomTable}.csv non esiste più.',
  'socle.creer.fichier_csv_pas_utf': 'Il file {nomTable}.csv non è in UTF-8 (salvato di nuovo da Excel?).',
  'socle.creer.fichier_vient_etre_modifie': 'Il file {nomFichier} è stato appena modificato da un\'altra postazione.',
  'socle.creer.indisponible_mode_demo_rien': 'Non disponibile in modalità demo: nulla viene salvato.',
  'socle.creer.lecture_document': 'lettura del documento',
  'socle.creer.lecture_nom_fichiers_abimes': 'lettura di {fichier}',
  'socle.creer.lecture_table': 'lettura della tabella',
  'socle.creer.lecture_versions': 'lettura delle versioni',
  'socle.creer.liste_sauvegardes': 'elenco dei backup',
  'socle.creer.mise_jour': 'aggiornamento di {fichier}',
  'socle.creer.nom_document_invalide': 'Nome del documento non valido: «{nom}».',
  'socle.creer.poste_inconnu': 'Postazione sconosciuta',
  'socle.creer.restauration': 'ripristino',
  'socle.creer.restauration_interrompue_table_tables': '{interrompueMessage} Ripristino interrotto alla tabella {table}; tabelle già ripristinate: {dejaRestaurees}. Lo stato precedente al ripristino è nel backup {copieSecurite}.',
  'socle.creer.sauvegarde': 'backup',
  'socle.creer.sauvegarde_avant_mise_jour': 'backup prima dell\'aggiornamento di Prévo',
  'socle.creer.sauvegarde_incomplete_copie_interrompue': 'Il backup {nom} è incompleto (copia interrotta o in corso): sceglierne un altro.',
  'socle.creer.sauvegarde_introuvable': 'Backup non trovato: {nom}.',
  'socle.creer.serveur_host': 'Server {host}',
  'socle.creer.table_absente_sauvegarde': 'La tabella {table} è assente da questo backup.',
  'socle.creer.tables_doit_etre_liste': '«tables» deve essere un elenco di nomi di tabelle.',
  'socle.creer.tete_csv_different': 'L\'intestazione di {nomTable}.csv è diversa.',
  'socle.creer.version_application_inconnue_rien': 'Versione dell\'applicazione sconosciuta: nulla viene salvato.',
  'socle.decaler_dates.stockage_demo_decaler_dates_dates_attendues': 'StockageDemo.decalerDates: date attese nel formato AAAA-MM-GG.',
  'socle.deconnecter.appareil_enrole_sans_mot': 'Questo dispositivo è abbinato senza password: solo il responsabile può revocarlo (Squadra › Accesso).',
  'socle.definir_titre.prevo': 'Prévo',
  'socle.definir_titre.prevo_gmao': 'Prévo — CMMS',
  'socle.definir_titre.texte_prevo': '{texte} — Prévo',
  'socle.demander_base_vide.aucun_fichier_trouve': { one: 'Il file di Prévo non è stato trovato ({stockage}). Da dove vuoi iniziare?', other: 'Nessuno dei {n} file di Prévo è stato trovato ({stockage}). Da dove vuoi iniziare?' },
  'socle.demander_motif.motif': 'Motivo',
  'socle.demander_motif.motif_obligatoire': 'Il motivo è obbligatorio.',
  'socle.demander_motif.valider': 'Convalida',
  'socle.demarrage.navigateur_sait_pas_ouvrir': '<b>Questo browser non sa aprire una cartella.</b> Per lavorare sui tuoi file, usa Chrome o Edge su un computer. Nel frattempo, qui la demo funziona.',
  'socle.depuis_fichiers.impossible_lire_fichier': 'Impossibile leggere il file {name}.',
  'socle.description_table.donnees_csv_table_inconnue': 'Donnees.csv: tabella sconosciuta «{nomTable}».',
  'socle.ecran.app_ecran_ecran_deja': 'App.ecran: la schermata «{definitionId}» è già registrata.',
  'socle.ecran.app_ecran_id_route': 'App.ecran: id, route (RegExp) e afficher(conteneur, parametres) sono obbligatori.',
  'socle.ecran_base_vide.aucune_donnee_instant': 'Ancora nessun dato',
  'socle.ecran_base_vide.langue_prevo': 'Lingua di Prévo',
  'socle.ecran_base_vide.langue_prevo_aide': 'Proposta in base a questo browser. Prévo si aprirà in questa lingua sulle postazioni che non hanno scelto la propria; è anche la lingua dei testi che scrive nei dati. Si può cambiare in seguito in Impostazioni.',
  'socle.ecran_chargement.chargement_prevo': 'Caricamento di Prévo…',
  'socle.ecran_demarrage.developpe_claude_anthropic_demande': 'Sviluppato da Claude (Anthropic) su richiesta di Nicolas Briand — SELECTIS',
  'socle.ecran_demarrage.gmao_libre_atelier_demandes': 'Software di manutenzione libero per l\'officina: richieste, ordini di lavoro, attrezzature.',
  'socle.ecran_demarrage.prevo': 'Prévo',
  'socle.ecran_installation.installer_prevo': 'Installa Prévo',
  'socle.ecran_profil.inscrit_journal_chaque_modification': 'Registrato nel registro a ogni modifica.',
  'socle.ecran_profil.nom_poste': 'Nome di questa postazione',
  'socle.ecran_profil.profil_adapte_ecrans_pas': 'Il profilo adatta le schermate; non è una protezione.',
  'socle.ecran_profil.utilise_poste': 'Chi usa questa postazione?',
  'socle.en_octets.contenu_fichier_illisible_texte': 'Contenuto del file illeggibile (attesi testo o byte).',
  'socle.en_octets.donnees_csv_octets_attendus': 'Donnees.csv: attesi byte (Uint8Array o ArrayBuffer).',
  'socle.en_octets.formats_manifeste_octets_attendus': 'Formats.manifeste: attesi byte (Uint8Array o ArrayBuffer).',
  'socle.en_octets.stockage_dossier_octets_attendus_uint': 'StockageDossier: attesi byte (Uint8Array o ArrayBuffer).',
  'socle.erreur_depuis_reponse.serveur_refuse_demande_code': 'Il server ha rifiutato la richiesta (codice {status}).',
  'socle.erreur_depuis_reponse.table': 'di questa tabella',
  'socle.etat_poste.changer': 'cambia',
  'socle.etat_poste.changer_profil': 'Cambia profilo',
  'socle.exiger_formats.donnees_registre_formats_js': 'Donnees: il registro dei formati (js/formats.js) deve essere caricato prima di js/donnees.js.',
  'socle.explication_valeur_illisible.fait_pas_partie_valeurs': 'non fa parte dei valori possibili ({valeurs})',
  'socle.explication_valeur_illisible.illisible': 'è illeggibile',
  'socle.explication_valeur_illisible.pas_date_heure_valide': 'non è una data e ora valida (formati accettati: 2024-03-15 08:30 o 15/03/2024 08:30)',
  'socle.explication_valeur_illisible.pas_date_valide_formats': 'non è una data valida (formati accettati: 2024-03-15 o 15/03/2024)',
  'socle.explication_valeur_illisible.pas_nombre_entier': 'non è un numero intero',
  'socle.explication_valeur_illisible.pas_nombre_exemples_acceptes': 'non è un numero (esempi accettati: 7,5 o 7.5)',
  'socle.explication_valeur_illisible.pas_reconnu_comme_oui': 'non è riconosciuto come sì o no (valori accettati: 1, 0, yes, no, true, false, x)',
  'socle.fichier_abime_depuis.depuis_le': { one: '{fichier}, dal {date} ({n} giorno)', other: '{fichier}, dal {date} ({n} giorni)' },
  'socle.fichier_abime_depuis.repere_aujourd_hui': '{fichier}, rilevato oggi',
  'socle.html.ui_html_utilise_comme': 'UI.html si usa come modello: UI.html`…`',
  'socle.installation_contenu.lecture_etat_installation': 'Lettura dello stato dell\'installazione…',
  'socle.installation_premiere_ligne.tant_installation_pas_terminee': 'Finché l\'installazione non è terminata, Prévo è raggiungibile solo da questo PC.',
  'socle.installation_quitter.ouvrir_prevo_sans_terminer': 'Apri Prévo senza terminare l\'installazione (resta raggiungibile solo da questo PC)',
  'socle.lecture_seule.lecture_seule_donnees_viennent': '<b>Sola lettura: questi dati provengono da una versione più recente di Prévo</b> (formato {format} dei file; questa versione legge fino al formato {version}). Puoi consultarli, ma nulla viene salvato. Aprili con l\'ultima versione di Prévo.',
  'socle.libelle_journal.demandeur_p_nom': 'Richiedente {nom}',
  'socle.libelle_journal.technicien_technicien_id': 'Tecnico {technicienId}',
  'socle.libelle_type.demandeur': 'Richiedente',
  'socle.libelle_type.responsable': 'Responsabile',
  'socle.libelle_type.technicien': 'Tecnico',
  'socle.lire_cellule.valeur_conservee_telle_quelle': '{explicationValeurIllisible}. Valore conservato così com\'è: da correggere',
  'socle.lire_cellule.valeur_probablement_abimee_excel': 'valore probabilmente danneggiato da Excel (numero lungo trasformato in notazione scientifica). Ritrova il valore originale e inseriscilo preceduto da un apostrofo, ad esempio \'123456789012345',
  'socle.lire_cellule.valeur_probablement_abimee_excel_formule': 'valore probabilmente danneggiato da Excel (testo che inizia con «=», «+» o «-» scambiato per una formula). Ritrova il testo originale e inseriscilo preceduto da un apostrofo',
  'socle.liste_deroulante.choisir': '— Scegli —',
  'socle.liste_deroulante.valeur_inconnue': '{valeurTexte} (valore sconosciuto)',
  'socle.menu.navigation_principale': 'Navigazione principale',
  'socle.message_conflit_persistant.fichier_modifie_meme_temps': 'Il file {nomTable} è modificato contemporaneamente su un\'altra postazione. Riprova tra un istante.',
  'socle.message_delai_depasse.serveur_prevo_met_trop': 'Il server Prévo impiega troppo tempo a rispondere. Controlla la rete e riprova; se stavi salvando, ricarica la pagina per verificare se la modifica è stata applicata.',
  'socle.message_erreur.fichier_abime_prevenez_responsable': 'File danneggiato: avvisa il responsabile. Nulla è stato salvato; quanto inserito è rimasto nel modulo.',
  'socle.message_erreur.fichier_abime_rien_ete': 'File danneggiato: nulla è stato salvato, per non perdere nulla; quanto inserito è rimasto nel modulo. Ripristina il backup del giorno (Impostazioni › Backup) o importa uno ZIP; i dettagli sono in Impostazioni › Controllo della base dati.',
  'socle.message_erreur.fichier_abime_rien_ete_avec_fichier': 'File danneggiato ({fichier}): nulla è stato salvato, per non perdere nulla; quanto inserito è rimasto nel modulo. Ripristina il backup del giorno (Impostazioni › Backup) o importa uno ZIP; i dettagli sono in Impostazioni › Controllo della base dati.',
  'socle.message_fichier_ouvert.fichier_dossier_donnees_ouvert': 'Un file della cartella dei dati è aperto in Excel o in un altro programma: chiudilo, poi riprova.',
  'socle.message_fichier_ouvert.fichier_ouvert_excel_autre': 'Il file «{nomFichier}» è aperto in Excel o in un altro programma: chiudilo, poi riprova.',
  'socle.message_reponse_inattendue.reponse_inattendue_serveur_operation': 'Risposta inattesa dal server; l\'operazione potrebbe essere stata eseguita, ricarica la pagina.',
  'socle.message_serveur_injoignable.serveur_prevo_repond_pas': 'Il server Prévo non risponde. Verifica che la finestra del server sia aperta sul PC.',
  'socle.mettre_ajour_boutons_profil.appareil_enrole': 'Dispositivo abbinato: {libelleAffiche}',
  'socle.mettre_ajour_boutons_profil.changer_profil': 'Cambia profilo',
  'socle.mettre_ajour_boutons_profil.connecte_cliquer_deconnecter': 'Connesso: {libelleCompte}. Clicca per uscire.',
  'socle.mettre_ajour_boutons_profil.deconnecter': 'esci',
  'socle.mettre_ajour_boutons_profil.deconnecter_bouton': 'Esci',
  'socle.mettre_ajour_boutons_profil.profil_poste_cliquer_changer': 'Profilo: {libelleAffiche} — postazione «{poste}». Clicca per cambiare.',
  'socle.migrer.formats_migrer_format_cible': 'Formats.migrer: formato di destinazione sconosciuto ({vers}); formati noti: da {premier} a {version}.',
  'socle.migrer.formats_migrer_format_depart': 'Formats.migrer: formato di partenza illeggibile ({de}).',
  'socle.migrer_au_format_courant.sans_sauvegarde_demo': 'senza backup (demo)',
  'socle.migrer_au_format_courant.sauvegarde_avant_passage_format': 'Backup prima del passaggio al formato {courant} impossibile: {messageSansPointFinal}; l\'aggiornamento sarà ritentato alla prossima apertura.',
  'socle.migrer_au_format_courant.sauvegarde_faite_juste_avant': 'backup {sauvegarde} eseguito poco prima',
  'socle.note_donnees_demo.atelier_francais_interface_traduite': 'I dati della demo descrivono un\'officina francese: è tradotta solo l\'interfaccia.',
  'socle.note_donnees_demo.nulle_part_elles_vivent': 'Da nessuna parte: vivono in questa pagina e scompaiono quando la chiudi. Nella tua installazione sono file CSV sul tuo PC, leggibili in Excel.',
  'socle.nouvel_id.donnees_nouvel_id_table_pas': 'Donnees.nouvelId: la tabella «{nomTable}» non ha un ID calcolato.',
  'socle.ouvrir_fichiers_deposes.aucun_fichier_reconnu_fichiers': 'Nessun file riconosciuto: i file devono chiamarsi equipements.csv, demandes.csv, ordres_travail.csv…',
  'socle.ouvrir_fichiers_deposes.fichiers_ignores_nom_inconnu': 'File ignorati (nome sconosciuto o duplicato): {fichiers}',
  'socle.ouvrir_plus.changer_profil': 'Cambia profilo ({libelleAffiche})',
  'socle.ouvrir_plus.deconnecter_libelle_compte': 'Esci ({libelleCompte})',
  'socle.ouvrir_plus.exporter_zip': 'Esporta in ZIP',
  'socle.passer_au_format_courant.fichiers_ont_pas_pu': '<b>I file non hanno potuto passare al formato {version}.</b> {message} Nel frattempo gli OdL preventivi scaduti non vengono generati automaticamente.',
  'socle.poste_aleatoire.poste_suffixe': 'Postazione-{suffixe}',
  'socle.probleme_colonne_absente.colonne_absente_sera_ajoutee': '{descriptionLibelle}: la colonna «{champNom}» ({champLibelle}) è assente da {fichier}; {suite}. Verrà aggiunta alla prossima modifica della tabella.',
  'socle.probleme_colonne_absente.colonne_ajoutee_version_format': '{descriptionLibelle}: colonna «{champNom}» aggiunta dalla versione {depuisVersion} del formato, scritta al prossimo salvataggio.',
  'socle.probleme_colonne_absente.valeur_defaut_utilisee': 'viene usato il valore predefinito «{valeurParDefaut}»',
  'socle.probleme_colonne_absente.valeur_laissee_vide': 'il valore viene lasciato vuoto',
  'socle.probleme_table_laissee.abime_structure_fichier_valeurs': '{fichier} è danneggiato (struttura del file, o valori oltre l\'intestazione: vedi gli altri problemi) e riscriverlo ne farebbe perdere una parte',
  'socle.probleme_table_laissee.ligne_tete_incomplete_illisible': 'la riga di intestazione di {fichier} è incompleta o illeggibile (mancano colonne del formato 1)',
  'socle.probleme_table_laissee.prevo_reecrit_pas_fichier': '{descriptionLibelle}: {raison}; Prévo non riscrive questo file per portarlo al formato {version} e lo lascia com\'è. Correggilo, oppure ripristina un backup.',
  'socle.profil_demandeur.demandeur': 'Richiedente',
  'socle.profil_demandeur.signaler_probleme_suivre_mes': 'Segnala un problema, segui le mie richieste',
  'socle.profil_panneau_demandeur.nom': 'Il tuo nome',
  'socle.profil_panneau_demandeur.retour': 'Indietro',
  'socle.profil_panneau_technicien.choisissez_nom': 'Scegli il tuo nome',
  'socle.profil_responsable.responsable': 'Responsabile',
  'socle.profil_responsable.tout_suivi_demandes_ot': 'Tutto il monitoraggio: richieste, OdL, attrezzature, impostazioni',
  'socle.profil_technicien.mes_ordres_travail_comptes': 'I miei ordini di lavoro, rapporti di intervento',
  'socle.profil_technicien.technicien': 'Tecnico',
  'socle.qr_svg.bibliotheque_qrcode_absente_js': 'Libreria qrcode assente (js/lib/qrcode.js).',
  'socle.qr_svg.qr_code': 'Codice QR: {texte}',
  'socle.raison_erreur.fichier_abime_prevenez_responsable': 'file danneggiato: avvisa il responsabile',
  'socle.raison_erreur.fichier_abime_rien_ete': 'file danneggiato, nulla vi è stato salvato: ripristina il backup del giorno o importa uno ZIP; i dettagli sono in Impostazioni › Controllo della base dati',
  'socle.raison_erreur.fichier_abime_rien_ete_avec_fichier': 'file danneggiato ({fichier}), nulla vi è stato salvato: ripristina il backup del giorno o importa uno ZIP; i dettagli sono in Impostazioni › Controllo della base dati',
  'socle.redimensionner_photo.photo_pas_pu_etre': 'Non è stato possibile convertire la foto.',
  'socle.remplir_liste_techniciens.aucun_technicien_actif_techniciens': 'Nessun tecnico attivo in techniciens.csv: scegli un altro profilo.',
  'socle.remplir_phrases_balisees.developpe_claude_anthropic_demande': 'Sviluppato da <b>Claude (Anthropic)</b> su richiesta di <b>Nicolas Briand — SELECTIS</b>',
  'socle.remplir_phrases_balisees.installer_prevo_assistant_comptes': '<a href="#/installation">Installa Prévo (procedura guidata)</a>: account, https, telefoni, avvio con il PC.',
  'socle.remplir_phrases_balisees.plusieurs_postes_telephones_lancez': 'Più postazioni e telefoni? Avvia <b>Lancer_GMAO.bat</b> (Windows) o <b>lancer.sh</b> (Mac, Linux): la modalità server viene riconosciuta da sola.',
  'socle.rendre.ecran_pas_pu_afficher': '<b>Questa schermata non ha potuto essere visualizzata.</b> {message}',
  'socle.reperage_ligne.ligne_donnees_sans_identifiant': 'riga di dati n. {numero} (senza ID)',
  'socle.reprendre_dossier.acces_dossier_precedent_pas': 'L\'accesso alla cartella precedente non è stato concesso. Scegli di nuovo la cartella.',
  'socle.route.aucun_ecran_correspond_adresse': 'Nessuna schermata corrisponde a questo indirizzo.',
  'socle.route.ecran_introuvable': 'Schermata non trovata',
  'socle.route.ecran_pas_disponible_profil': 'La schermata «{ecranTitre}» non è disponibile per il profilo {profil}.',
  'socle.sauvegarder_avant_format.mode_stockage_sait_pas': 'questa modalità di archiviazione non sa fare backup',
  'socle.sauvegarder_avant_format.stockage_pas_confirme_sauvegarde': 'l\'archiviazione non ha confermato il backup (nessun nome restituito)',
  'socle.sauvegarder_avant_mise_ajour.sauvegarde_avant_mise_jour': '<b>Non è stato possibile eseguire il backup «prima dell\'aggiornamento di Prévo».</b> {message} Verrà ritentato alla prossima apertura.',
  'socle.scanner_qr.impossible_ouvrir_camera_autorisation': 'Impossibile aprire la fotocamera (autorizzazione negata o fotocamera occupata).',
  'socle.scanner_qr.placez_qr_code_equipement': 'Inquadra il codice QR dell\'attrezzatura.',
  'socle.scanner_qr.scan_camera_pas_disponible': 'La scansione con la fotocamera non è disponibile in questa pagina. Usa la fotocamera del telefono.',
  'socle.scanner_qr.scanner_qr_code': 'Scansiona un codice QR',
  'socle.selecteur_equipement.aucun_equipement_correspond': 'Nessuna attrezzatura corrisponde a «{recherche}».',
  'socle.selecteur_equipement.changer': 'Cambia',
  'socle.selecteur_equipement.equipements_trouves': 'Attrezzature trovate',
  'socle.selecteur_equipement.equipements_trouves_affiner': { one: '{n} attrezzatura: digita qualche lettera per restringere.', other: '{n} attrezzature: digita qualche lettera per restringere.' },
  'socle.selecteur_equipement.qr_code_correspond_aucun': 'Questo codice QR non corrisponde ad alcuna attrezzatura nota.',
  'socle.selecteur_equipement.rechercher_equipement': 'Cerca un\'attrezzatura',
  'socle.selecteur_equipement.repere_nom': 'Codice o nome',
  'socle.selecteur_equipement.scanner': 'Scansiona',
  'socle.selecteur_langue.changer': 'Cambia',
  'socle.selecteur_langue.changer_langue': 'Cambia lingua',
  'socle.selecteur_langue.choix_non_retenu': 'Lingua non salvata: questo browser rifiuta di salvare le sue impostazioni.',
  'socle.selecteur_langue.langue_ecran': 'Lingua dello schermo',
  'socle.selecteur_langue.recharge_demo': 'Cambiare lingua ricarica la demo: le modifiche che vi hai fatto andranno perse.',
  'socle.session_perdue.reconnecte_saisie_gardee': 'Riconnessione effettuata: quanto inserito è rimasto a schermo; salvalo.',
  'socle.session_perdue.reconnectez_vous_meme_compte': 'La tua sessione è terminata. Accedi di nuovo con lo stesso account: ritroverai la schermata com\'era, compreso quanto inserito. Ciò che non era stato salvato non lo è ancora: salvalo dopo.',
  'socle.suffixe_du_motif.motif_sauvegarde_refuse_motifs': 'Motivo del backup rifiutato. Motivi accettati: {motifs}.',
  'socle.tableau.aucune_ligne_afficher': 'Nessuna riga da visualizzare.',
  'socle.texte_base_vide.aucun_23_fichiers_prevo': 'Nessuno dei 23 file di Prévo è stato trovato.',
  'socle.titre_donnees.ou_sont_donnees': 'Dove sono i tuoi dati?',
  'socle.titre_donnees_demo.ou_sont_donnees_demo': 'Dove sono i dati di questa demo?',
  'socle.traduire_erreur.acces_refuse_dossier_donnees': 'Accesso negato alla cartella dei dati ({action}). Scegli di nuovo la cartella per concedere l\'autorizzazione.',
  'socle.traduire_erreur.dossier_donnees_introuvable_ete': 'Cartella dei dati non trovata ({action}): è stata spostata, rinominata o scollegata?',
  'socle.traduire_erreur.lecture_ecriture_impossible_dossier': 'Lettura o scrittura impossibile nella cartella dei dati ({action}).',
  'socle.valider_demandeur.indiquez_nom_permet_retrouver': 'Indica il tuo nome: permette di ritrovare le tue richieste.',
  'socle.verifier_dossier_accessible.dossier_donnees_introuvable_inaccessible': 'La cartella dei dati non è stata trovata o non è accessibile (eliminata, spostata, chiavetta USB o condivisione di rete scollegata?). Ricollegala o scegli di nuovo la cartella.',
  'socle.verifier_formulaire.case_doit_etre_cochee': 'Questa casella deve essere selezionata.',
  'socle.verifier_formulaire.champ_obligatoire': 'Questo campo è obbligatorio.',
  'socle.verifier_formulaire.saisissez_nombre_entier_ex': 'Inserisci un numero intero (es. 12).',
  'socle.verifier_formulaire.saisissez_nombre_ex_12': 'Inserisci un numero (es. 12,5).',
  'socle.verifier_initialise.donnees_appelez_donnees_initialiser': 'Donnees: chiama Donnees.initialiser(adaptateur, …) prima di leggere o scrivere.',
  'socle.verifier_nom_document.nom_document_refuse_lettres': 'Nome del documento rifiutato: lettere, cifre, «.», «_» o «-».',
  'socle.verifier_nom_document.nom_document_reserve_windows': 'Nome del documento riservato da Windows.',
  'socle.verifier_nom_document.type_document_refuse_types': 'Tipo di documento rifiutato. Tipi accettati: {types}.',
  'socle.verifier_nom_sauvegarde.nom_sauvegarde_invalide': 'Nome del backup non valido.',
  'socle.verifier_nom_table.table_inconnue': 'Tabella sconosciuta: «{nomTable}».',
  'socle.verifier_nom_table.table_inconnue_dossier': 'Tabella sconosciuta: {table}.',
  'socle.verifier_verrou_dossier.dossier_semble_deja_ouvert': '<b>Questa cartella sembra già aperta su «{poste}»</b> (ultimo segnale di vita: {heure}). Due postazioni che scrivono nella stessa cartella possono interferire: se possibile, chiudi l\'altra sessione.',
  'socle.zone_depot.cliquer_choisir_demo_propres': 'oppure clicca per sceglierli: demo con i tuoi file, nulla viene salvato',
  'socle.zone_depot.deposer_fichiers_csv_ici': 'Trascina qui i file CSV',
});
// ==== fin socle ====

// ==== section planning ====
I18n.ajouter('it', {
});
// ==== fin planning ====

// ==== section causes ====
I18n.ajouter('it', {
});
// ==== fin causes ====

// ==== section dictee ====
I18n.ajouter('it', {
});
// ==== fin dictee ====

// ==== section mise ====
I18n.ajouter('it', {
});
// ==== fin mise ====

// ==== section aide ====
I18n.ajouter('it', {
});
// ==== fin aide ====

// ==== section ordres ====
I18n.ajouter('it', {
});
// ==== fin ordres ====

// ==== section demandes ====
I18n.ajouter('it', {
});
// ==== fin demandes ====

// ==== section parc ====
I18n.ajouter('it', {
});
// ==== fin parc ====

// ==== section preventif ====
I18n.ajouter('it', {
});
// ==== fin preventif ====

// ==== section controles ====
I18n.ajouter('it', {
});
// ==== fin controles ====

// ==== section wiki ====
I18n.ajouter('it', {
});
// ==== fin wiki ====

// ==== section suggestions ====
I18n.ajouter('it', {
});
// ==== fin suggestions ====

// ==== section import ====
I18n.ajouter('it', {
});
// ==== fin import ====

// ==== section magasin ====
I18n.ajouter('it', {
});
// ==== fin magasin ====

// ==== section indicateurs ====
I18n.ajouter('it', {
});
// ==== fin indicateurs ====

// ==== section rapport ====
I18n.ajouter('it', {
});
// ==== fin rapport ====

// ==== section accueil ====
I18n.ajouter('it', {
});
// ==== fin accueil ====

// ==== section equipe ====
I18n.ajouter('it', {
});
// ==== fin equipe ====

// ==== section acces ====
I18n.ajouter('it', {
});
// ==== fin acces ====

// ==== section connexion ====
I18n.ajouter('it', {
});
// ==== fin connexion ====

// ==== section poste ====
I18n.ajouter('it', {
});
// ==== fin poste ====

// ==== section apropos ====
I18n.ajouter('it', {
});
// ==== fin apropos ====

// ==== section installation ====
I18n.ajouter('it', {
});
// ==== fin installation ====

// ==== section porte ====
I18n.ajouter('it', {
});
// ==== fin porte ====

// ==== section parametres ====
I18n.ajouter('it', {
});
// ==== fin parametres ====

// ==== section sauvegardes ====
I18n.ajouter('it', {
});
// ==== fin sauvegardes ====

// ==== section zip ====
I18n.ajouter('it', {
});
// ==== fin zip ====

// ==== section serveur ====
I18n.ajouter('it', {
});
// ==== fin serveur ====

// ==== section ia ====
I18n.ajouter('it', {
});
// ==== fin ia ====
