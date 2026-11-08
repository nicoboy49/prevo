'use strict';
// Textes portugais de Prévo : portugais du Portugal (jamais du Brésil), locale pt-PT (chantier multilingue, Lot 5, T343 ; version 2.1.0).
// Traduction automatique assumée (l'interface le dit : « traduction automatique — corrections bienvenues »).
// Mêmes sections que js/i18n/fr.js, dans le même ordre : une section par domaine. On traduit par groupes de
// domaines, une tâche par groupe, chacune dans ses sections seulement : jamais deux tâches sur les mêmes lignes.
// Dans chaque bloc : les clés de la même section de fr.js, triées, une par ligne, chaînes entre apostrophes
// simples, échappements gardés (jamais d'espace insécable écrit en clair : \u00a0, \u202f), mêmes variables {…}
// que le français ; un pluriel { one, other } là où le français en a un, un texte simple ailleurs.
// Vocabulaire : docs/GLOSSAIRE.md (colonne de la langue). Clé absente : texte français affiché (avertissement
// dans la console). Pas d'aide longue traduite (D158) : l'aide longue s'affiche en anglais.
// Contrôle : py -X utf8 outils/controler_textes.py --langue pt-PT [--domaine <domaine>].
// Déclaré dans js/i18n/langues.js seulement quand toutes ses sections sont traduites (Lot 5).

// ==== section commun ====
I18n.ajouter('pt-PT', {
  'commun.bouton.actualiser': 'Atualizar',
  'commun.bouton.ajouter': 'Adicionar',
  'commun.bouton.annuler': 'Cancelar',
  'commun.bouton.continuer': 'Continuar',
  'commun.bouton.desactiver': 'Desativar',
  'commun.bouton.enregistrer': 'Guardar',
  'commun.bouton.fermer': 'Fechar',
  'commun.bouton.imprimer': 'Imprimir',
  'commun.bouton.modifier': 'Editar',
  'commun.brouillon.abandonner': 'Abandonar o rascunho',
  'commun.brouillon.effacer': 'Apagar o rascunho',
  'commun.brouillon.repris': 'Rascunho retomado: introduzido neste dispositivo em {quand}, ainda não guardado.',
  'commun.champ.article': 'Artigo',
  'commun.champ.commentaire': 'Comentário',
  'commun.champ.criticite': 'Criticidade',
  'commun.champ.date': 'Data',
  'commun.champ.designation': 'Designação',
  'commun.champ.equipement': 'Equipamento',
  'commun.champ.numero': 'N.º',
  'commun.champ.prenom': 'Nome próprio',
  'commun.champ.priorite': 'Prioridade',
  'commun.champ.prix_unitaire': 'Preço unitário',
  'commun.champ.quantite': 'Quantidade',
  'commun.champ.reference': 'Referência',
  'commun.champ.repere': 'Código',
  'commun.champ.statut': 'Estado',
  'commun.champ.symptome': 'Sintoma',
  'commun.champ.technicien': 'Técnico',
  'commun.liste.non_choisi': '(não selecionado)',
  'commun.message.aucune_modification': 'Nenhuma alteração a guardar.',
  'commun.message.champ_obligatoire': 'campo obrigatório',
  'commun.message.erreur_inconnue': 'erro desconhecido',
  'commun.message.fichier_trop_volumineux': 'Este ficheiro é demasiado grande (9 MB no máximo).',
  'commun.message.ot_introuvable': 'A ordem de trabalho {otId} não foi encontrada.',
  'commun.message.saisi_sur_autre_poste': 'Pode ter sido introduzido noutra estação de trabalho: atualize.',
  'commun.message.serveur_a_repondu': 'O servidor respondeu «{status}».',
});
// ==== fin commun ====

// ==== section schema ====
I18n.ajouter('pt-PT', {
  'schema.achats.article_id': 'Artigo',
  'schema.achats.date': 'Data',
  'schema.achats.date_reception': 'Data de receção',
  'schema.achats.fournisseur_id': 'Fornecedor',
  'schema.achats.id': 'ID',
  'schema.achats.prix_unitaire': 'Preço unitário',
  'schema.achats.quantite': 'Quantidade',
  'schema.achats.statut': 'Estado',
  'schema.article_equipement.article_id': 'Artigo',
  'schema.article_equipement.equipement_id': 'Equipamento',
  'schema.article_equipement.id': 'ID',
  'schema.article_equipement.quantite': 'Quantidade',
  'schema.articles.actif': 'Ativo',
  'schema.articles.critique': 'Artigo crítico',
  'schema.articles.delai_jours': 'Prazo de aprovisionamento (dias)',
  'schema.articles.designation': 'Designação',
  'schema.articles.emplacement': 'Posição de armazenagem',
  'schema.articles.fabricant': 'Fabricante',
  'schema.articles.fournisseur_id': 'Fornecedor',
  'schema.articles.id': 'ID',
  'schema.articles.point_commande': 'Ponto de encomenda',
  'schema.articles.prix_unitaire': 'Preço unitário',
  'schema.articles.qte_commande': 'Quantidade a encomendar',
  'schema.articles.ref_fabricant': 'Referência do fabricante',
  'schema.articles.reference': 'Referência',
  'schema.articles.stock': 'Stock',
  'schema.articles.stock_securite': 'Stock de segurança',
  'schema.articles.unite': 'Unidade',
  'schema.codes_defaillance.code': 'Código',
  'schema.codes_defaillance.famille': 'Família',
  'schema.codes_defaillance.id': 'ID',
  'schema.codes_defaillance.libelle': 'Etiqueta',
  'schema.compteurs.equipement_id': 'Equipamento',
  'schema.compteurs.id': 'ID',
  'schema.compteurs.libelle': 'Etiqueta',
  'schema.compteurs.unite': 'Unidade',
  'schema.controles_reglementaires.derniere_date': 'Data da última inspeção',
  'schema.controles_reglementaires.equipement_id': 'Equipamento',
  'schema.controles_reglementaires.id': 'ID',
  'schema.controles_reglementaires.nature': 'Tipo de inspeção',
  'schema.controles_reglementaires.observations': 'Observações',
  'schema.controles_reglementaires.observations_levees': 'Observações resolvidas',
  'schema.controles_reglementaires.organisme': 'Organismo de inspeção',
  'schema.controles_reglementaires.periodicite_mois': 'Periodicidade (meses)',
  'schema.controles_reglementaires.prochaine_date': 'Data da próxima inspeção',
  'schema.controles_reglementaires.rapport': 'Relatório',
  'schema.controles_reglementaires.texte_reference': 'Texto de referência',
  'schema.demandes.date_decision': 'Data da decisão',
  'schema.demandes.date_heure': 'Data e hora do pedido',
  'schema.demandes.demandeur': 'Requerente',
  'schema.demandes.description': 'Descrição',
  'schema.demandes.equipement_id': 'Equipamento',
  'schema.demandes.id': 'ID',
  'schema.demandes.impact': 'Impacto',
  'schema.demandes.motif_decision': 'Motivo da decisão',
  'schema.demandes.ot_id': 'Ordem de trabalho associada',
  'schema.demandes.ot_origine_id': 'OT de origem (preventiva)',
  'schema.demandes.photo': 'Fotografia',
  'schema.demandes.statut': 'Estado',
  'schema.demandes.symptome': 'Sintoma observado',
  'schema.demandes.symptome_code': 'Código do sintoma',
  'schema.equipements.actif': 'Ativo',
  'schema.equipements.consignation': 'Consignação',
  'schema.equipements.criticite': 'Criticidade',
  'schema.equipements.date_mes': 'Data de entrada em serviço',
  'schema.equipements.designation': 'Designação',
  'schema.equipements.document': 'Documento',
  'schema.equipements.habilitation_requise': 'Habilitação necessária',
  'schema.equipements.heures_fonct_jour': 'Horas de funcionamento por dia',
  'schema.equipements.id': 'ID',
  'schema.equipements.localisation_id': 'Localização',
  'schema.equipements.marque': 'Marca',
  'schema.equipements.modele': 'Modelo',
  'schema.equipements.num_serie': 'Número de série',
  'schema.equipements.parent_id': 'Equipamento principal',
  'schema.equipements.repere': 'Código',
  'schema.equipements.statut': 'Estado',
  'schema.equipements.valeur_remplacement': 'Valor de substituição ({devise} sem IVA)',
  'schema.fournisseurs.contact': 'Contacto',
  'schema.fournisseurs.email': 'E-mail',
  'schema.fournisseurs.id': 'ID',
  'schema.fournisseurs.nom': 'Nome',
  'schema.fournisseurs.telephone': 'Telefone',
  'schema.gamme_operations.gamme_id': 'Gama',
  'schema.gamme_operations.id': 'ID',
  'schema.gamme_operations.operation': 'Operação',
  'schema.gamme_operations.ordre': 'Sequência',
  'schema.gamme_operations.valeur_attendue': 'Valor esperado',
  'schema.gammes.actif': 'Ativo',
  'schema.gammes.avance_jours': 'Antecedência (dias)',
  'schema.gammes.compteur_id': 'Contador',
  'schema.gammes.consignes': 'Instruções',
  'schema.gammes.declencheur': 'Acionador',
  'schema.gammes.derniere_realisation': 'Última realização',
  'schema.gammes.equipement_id': 'Equipamento',
  'schema.gammes.id': 'ID',
  'schema.gammes.libelle': 'Etiqueta',
  'schema.gammes.periodicite_jours': 'Periodicidade (dias)',
  'schema.gammes.periodicite_unites': 'Periodicidade (unidades do contador)',
  'schema.gammes.prochaine_echeance': 'Próximo vencimento',
  'schema.gammes.releve_derniere_realisation': 'Leitura na última realização',
  'schema.gammes.seuil': 'Limiar',
  'schema.gammes.temps_prevu_h': 'Tempo previsto (horas)',
  'schema.habilitations.date_echeance': 'Data de validade',
  'schema.habilitations.date_obtention': 'Data de obtenção',
  'schema.habilitations.id': 'ID',
  'schema.habilitations.intitule': 'Nome',
  'schema.habilitations.technicien_id': 'Técnico',
  'schema.journal.action': 'Ação',
  'schema.journal.date_heure': 'Data e hora',
  'schema.journal.id': 'ID',
  'schema.journal.id_ligne': 'ID da linha',
  'schema.journal.poste': 'Estação de trabalho',
  'schema.journal.profil': 'Perfil',
  'schema.journal.table': 'Tabela',
  'schema.localisations.id': 'ID',
  'schema.localisations.libelle': 'Etiqueta',
  'schema.localisations.parent_id': 'Localização principal',
  'schema.localisations.type': 'Tipo',
  'schema.mouvements_stock.article_id': 'Artigo',
  'schema.mouvements_stock.commentaire': 'Comentário',
  'schema.mouvements_stock.date': 'Data e hora',
  'schema.mouvements_stock.id': 'ID',
  'schema.mouvements_stock.ot_id': 'Ordem de trabalho',
  'schema.mouvements_stock.quantite': 'Quantidade',
  'schema.mouvements_stock.type': 'Tipo',
  'schema.mouvements_stock.utilisateur': 'Utilizador',
  'schema.ordres_travail.anomalie_constatee': 'Anomalia constatada',
  'schema.ordres_travail.arret_production': 'Paragem de produção',
  'schema.ordres_travail.astuce': 'Dica para a próxima vez',
  'schema.ordres_travail.cause_code': 'Código da causa',
  'schema.ordres_travail.compte_rendu': 'Relatório de intervenção',
  'schema.ordres_travail.consignes': 'Instruções',
  'schema.ordres_travail.cout_soustraitance': 'Custo de subcontratação',
  'schema.ordres_travail.date_cloture_admin': 'Data de encerramento administrativo',
  'schema.ordres_travail.date_cloture_tech': 'Data de encerramento técnico',
  'schema.ordres_travail.date_creation': 'Data de criação',
  'schema.ordres_travail.date_debut': 'Data de início',
  'schema.ordres_travail.date_fin': 'Data de fim',
  'schema.ordres_travail.date_prevue': 'Data prevista',
  'schema.ordres_travail.di_id': 'Pedido de intervenção',
  'schema.ordres_travail.duree_arret_h': 'Tempo de paragem (horas)',
  'schema.ordres_travail.equipement_id': 'Equipamento',
  'schema.ordres_travail.gamme_id': 'Gama de manutenção preventiva',
  'schema.ordres_travail.id': 'ID',
  'schema.ordres_travail.motif_annulation': 'Motivo do cancelamento',
  'schema.ordres_travail.motif_attente': 'Motivo da espera',
  'schema.ordres_travail.origine': 'Origem',
  'schema.ordres_travail.ot_lie_id': 'Ordem de trabalho associada',
  'schema.ordres_travail.priorite': 'Prioridade',
  'schema.ordres_travail.remede_code': 'Código da solução',
  'schema.ordres_travail.remise_service': 'Reposto em serviço em segurança',
  'schema.ordres_travail.statut': 'Estado',
  'schema.ordres_travail.symptome_code': 'Código do sintoma',
  'schema.ordres_travail.technicien_id': 'Técnico',
  'schema.ordres_travail.temps_prevu_h': 'Tempo previsto (horas)',
  'schema.ordres_travail.titre': 'Título',
  'schema.ordres_travail.travail_a_faire': 'Trabalho a realizar',
  'schema.ordres_travail.type': 'Tipo',
  'schema.ot_operations.fait': 'Feito',
  'schema.ot_operations.id': 'ID',
  'schema.ot_operations.operation': 'Operação',
  'schema.ot_operations.ordre': 'Sequência',
  'schema.ot_operations.ot_id': 'Ordem de trabalho',
  'schema.ot_operations.valeur_attendue': 'Valor esperado',
  'schema.ot_operations.valeur_mesuree': 'Valor medido',
  'schema.ot_pieces.article_id': 'Artigo',
  'schema.ot_pieces.id': 'ID',
  'schema.ot_pieces.ot_id': 'Ordem de trabalho',
  'schema.ot_pieces.quantite_prevue': 'Quantidade prevista',
  'schema.ot_temps.date': 'Data',
  'schema.ot_temps.heures': 'Horas',
  'schema.ot_temps.id': 'ID',
  'schema.ot_temps.ot_id': 'Ordem de trabalho',
  'schema.ot_temps.technicien_id': 'Técnico',
  'schema.parametres.cle': 'Chave',
  'schema.parametres.valeur': 'Valor',
  'schema.releves.compteur_id': 'Contador',
  'schema.releves.date': 'Data',
  'schema.releves.id': 'ID',
  'schema.releves.utilisateur': 'Utilizador',
  'schema.releves.valeur': 'Valor',
  'schema.tables.achats': 'Compras',
  'schema.tables.article_equipement': 'Artigos por equipamento',
  'schema.tables.articles': 'Artigos (peças sobresselentes)',
  'schema.tables.codes_defaillance': 'Códigos de avaria',
  'schema.tables.compteurs': 'Contadores',
  'schema.tables.controles_reglementaires': 'Inspeções regulamentares',
  'schema.tables.demandes': 'Pedidos de intervenção',
  'schema.tables.equipements': 'Equipamentos',
  'schema.tables.fournisseurs': 'Fornecedores',
  'schema.tables.gamme_operations': 'Operações de gama',
  'schema.tables.gammes': 'Gamas de manutenção preventiva',
  'schema.tables.habilitations': 'Habilitações',
  'schema.tables.journal': 'Registo de alterações',
  'schema.tables.localisations': 'Localizações',
  'schema.tables.mouvements_stock': 'Movimentos de stock',
  'schema.tables.ordres_travail': 'Ordens de trabalho',
  'schema.tables.ot_operations': 'Operações de ordem de trabalho',
  'schema.tables.ot_pieces': 'Peças previstas de ordem de trabalho',
  'schema.tables.ot_temps': 'Tempo dedicado a ordens de trabalho',
  'schema.tables.parametres': 'Definições',
  'schema.tables.releves': 'Leituras de contador',
  'schema.tables.techniciens': 'Técnicos',
  'schema.tables.wiki_journal': 'Registo do wiki',
  'schema.tables.wiki_pages': 'Páginas do wiki',
  'schema.techniciens.actif': 'Ativo',
  'schema.techniciens.capacite_h_semaine': 'Capacidade (horas por semana)',
  'schema.techniciens.id': 'ID',
  'schema.techniciens.metier': 'Especialidade',
  'schema.techniciens.nom': 'Apelido',
  'schema.techniciens.prenom': 'Nome próprio',
  'schema.techniciens.taux_horaire': 'Taxa horária',
  'schema.wiki_journal.anterieure': 'Intervenção anterior',
  'schema.wiki_journal.changements': 'Alterações',
  'schema.wiki_journal.contradictions': 'Contradições',
  'schema.wiki_journal.cree_le': 'Criada em',
  'schema.wiki_journal.date_intervention': 'Data da intervenção',
  'schema.wiki_journal.decide_le': 'Decidido em',
  'schema.wiki_journal.decide_par': 'Decidido por',
  'schema.wiki_journal.essais': 'Tentativas',
  'schema.wiki_journal.id': 'ID',
  'schema.wiki_journal.modele': 'Modelo',
  'schema.wiki_journal.motif': 'Motivo',
  'schema.wiki_journal.nature': 'Natureza',
  'schema.wiki_journal.ordre': 'Ordem de tratamento',
  'schema.wiki_journal.ot_id': 'Ordem de trabalho',
  'schema.wiki_journal.pages': 'Páginas em causa',
  'schema.wiki_journal.raisons': 'Razões da recusa',
  'schema.wiki_journal.statut': 'Estado',
  'schema.wiki_journal.traite_le': 'Tratada em',
  'schema.wiki_pages.article_id': 'Artigo',
  'schema.wiki_pages.cause_code': 'Código da causa',
  'schema.wiki_pages.cle': 'Chave (título comparável)',
  'schema.wiki_pages.cree_le': 'Criada em',
  'schema.wiki_pages.derniere_entree': 'Última entrada aplicada',
  'schema.wiki_pages.equipement_id': 'Equipamento',
  'schema.wiki_pages.id': 'ID',
  'schema.wiki_pages.liens': 'Páginas associadas',
  'schema.wiki_pages.modele': 'Modelo',
  'schema.wiki_pages.modifie_le': 'Modificada em',
  'schema.wiki_pages.origine': 'Origem',
  'schema.wiki_pages.ot_cites': 'OT citadas',
  'schema.wiki_pages.rattache_a': 'Associada à página',
  'schema.wiki_pages.statut': 'Estado',
  'schema.wiki_pages.texte': 'Texto',
  'schema.wiki_pages.titre': 'Título',
  'schema.wiki_pages.type': 'Tipo',
  'schema.wiki_pages.valide_le': 'Validada em',
  'schema.wiki_pages.valide_par': 'Validada por',
  'schema.wiki_pages.version': 'Versão',
});
// ==== fin schema ====

// ==== section valeurs ====
I18n.ajouter('pt-PT', {
  'valeurs.achats.statut.commandée': 'encomendada',
  'valeurs.achats.statut.demandée': 'pedida',
  'valeurs.achats.statut.reçue': 'recebida',
  'valeurs.codes_defaillance.famille.cause': 'causa',
  'valeurs.codes_defaillance.famille.remède': 'solução',
  'valeurs.codes_defaillance.famille.symptôme': 'sintoma',
  'valeurs.demandes.impact.arrêt': 'paragem',
  'valeurs.demandes.impact.dégradé': 'degradado',
  'valeurs.demandes.impact.gêne': 'perturbação',
  'valeurs.demandes.impact.sécurité': 'segurança',
  'valeurs.demandes.statut.Acceptée': 'Aceite',
  'valeurs.demandes.statut.Différée': 'Adiado',
  'valeurs.demandes.statut.Nouvelle': 'Novo',
  'valeurs.demandes.statut.Refusée': 'Recusado',
  'valeurs.demandes.statut.Regroupée': 'Agrupado',
  'valeurs.equipements.criticite.A': 'A',
  'valeurs.equipements.criticite.B': 'B',
  'valeurs.equipements.criticite.C': 'C',
  'valeurs.equipements.statut.arrêt': 'parado',
  'valeurs.equipements.statut.en service': 'em serviço',
  'valeurs.equipements.statut.rebut': 'abatido',
  'valeurs.gammes.declencheur.compteur': 'contador',
  'valeurs.gammes.declencheur.date': 'data',
  'valeurs.gammes.declencheur.seuil': 'limiar',
  'valeurs.localisations.type.atelier': 'oficina',
  'valeurs.localisations.type.ligne': 'linha',
  'valeurs.localisations.type.site': 'instalação',
  'valeurs.mouvements_stock.type.entrée': 'entrada',
  'valeurs.mouvements_stock.type.inventaire': 'inventário',
  'valeurs.mouvements_stock.type.retour': 'devolução',
  'valeurs.mouvements_stock.type.sortie': 'saída',
  'valeurs.ordres_travail.origine.DI': 'Pedido',
  'valeurs.ordres_travail.origine.manuel': 'manual',
  'valeurs.ordres_travail.origine.préventif': 'preventivo',
  'valeurs.ordres_travail.origine.urgence': 'urgência',
  'valeurs.ordres_travail.priorite.P1': 'P1',
  'valeurs.ordres_travail.priorite.P2': 'P2',
  'valeurs.ordres_travail.priorite.P3': 'P3',
  'valeurs.ordres_travail.priorite.P4': 'P4',
  'valeurs.ordres_travail.statut.Annulé': 'Cancelada',
  'valeurs.ordres_travail.statut.Clôturé administrativement': 'Encerrada administrativamente',
  'valeurs.ordres_travail.statut.Clôturé techniquement': 'Encerrada tecnicamente',
  'valeurs.ordres_travail.statut.Créé': 'Criada',
  'valeurs.ordres_travail.statut.En attente': 'Em espera',
  'valeurs.ordres_travail.statut.En cours': 'Em curso',
  'valeurs.ordres_travail.statut.Planifié': 'Agendada',
  'valeurs.ordres_travail.statut.Préparé': 'Preparada',
  'valeurs.ordres_travail.type.amélioration': 'melhoria',
  'valeurs.ordres_travail.type.correctif différé': 'corretivo diferido',
  'valeurs.ordres_travail.type.correctif immédiat': 'corretivo imediato',
  'valeurs.ordres_travail.type.préventif conditionnel': 'preventivo condicionado',
  'valeurs.ordres_travail.type.préventif systématique': 'preventivo sistemático',
  'valeurs.ordres_travail.type.réglementaire': 'regulamentar',
  'valeurs.wiki_journal.nature.décision': 'decisão',
  'valeurs.wiki_journal.nature.ingestion': 'ingestão',
  'valeurs.wiki_journal.nature.manuel': 'manual',
  'valeurs.wiki_journal.statut.appliquée': 'aplicada',
  'valeurs.wiki_journal.statut.en file': 'em fila',
  'valeurs.wiki_journal.statut.refusée': 'recusada',
  'valeurs.wiki_journal.statut.rejetée': 'rejeitada',
  'valeurs.wiki_journal.statut.rien à ajouter': 'nada a acrescentar',
  'valeurs.wiki_journal.statut.validée': 'validada',
  'valeurs.wiki_journal.statut.à refaire': 'a refazer',
  'valeurs.wiki_journal.statut.à valider': 'por validar',
  'valeurs.wiki_pages.origine.IA': 'IA',
  'valeurs.wiki_pages.origine.IA et manuel': 'IA e manual',
  'valeurs.wiki_pages.origine.manuel': 'manual',
  'valeurs.wiki_pages.statut.active': 'ativa',
  'valeurs.wiki_pages.statut.archivée': 'arquivada',
  'valeurs.wiki_pages.type.composant': 'componente',
  'valeurs.wiki_pages.type.mode': 'modo de avaria',
  'valeurs.wiki_pages.type.savoir-faire': 'saber-fazer',
  'valeurs.wiki_pages.type.équipement': 'equipamento',
});
// ==== fin valeurs ====

// ==== section socle ====
I18n.ajouter('pt-PT', {
  'socle.analyser.ligne_contient_plus_valeurs': '{reperage}: esta linha contém mais valores do que o cabeçalho tem colunas; o valor «{valeurIgnoree}» (coluna {colonneIgnoree}) é ignorado.',
  'socle.analyser.ligne_structure_fichier_abimee': '{descriptionLibelle}, linha {numero} de {fichier}: estrutura do ficheiro danificada ({erreurMessage}), por exemplo umas aspas não fechadas. Os valores desta linha e das seguintes podem estar desfasados.',
  'socle.analyser.pas_utf_8_sans': '{descriptionLibelle}: {fichier} não está em UTF-8 (provavelmente guardado pelo Excel no formato «CSV (separador: ponto e vírgula)»); foi lido em Windows-1252. Será reescrito em UTF-8 na próxima alteração da tabela.',
  'socle.analyser.reperage_champ_libelle_contient_lu_valeur': '{reperage}: «{champLibelle}» contém «{luValeur}», {explication}.',
  'socle.app.gmao': 'GMAO',
  'socle.app.menu': 'Menu',
  'socle.app.propos': 'Acerca de',
  'socle.appliquer_repli.deplier_menu': 'Expandir o menu',
  'socle.appliquer_repli.replier_menu': 'Recolher o menu',
  'socle.associer_colonnes.colonne_apparait_deux_fois': '{descriptionLibelle}: a coluna «{nomColonne}» aparece duas vezes em {fichier}; a segunda é conservada à parte com o nome «{nomConserve}» e não é utilizada pelo Prévo.',
  'socle.associer_colonnes.colonne_fait_pas_partie': '{descriptionLibelle}: a coluna «{nomConserve}» de {fichier} não faz parte do Prévo; é conservada tal como está (reescrita no fim do ficheiro).',
  'socle.associer_colonnes.colonne_numero': 'coluna {numero}',
  'socle.badge_priorite.priorite_code': 'Prioridade {code}',
  'socle.badge_priorite.priorite_inconnue': 'Prioridade desconhecida',
  'socle.bandeau_changement.donnees_ont_change_autre': 'Os dados foram alterados noutra estação de trabalho',
  'socle.bandeau_demo.demo_rien_enregistre': 'Demonstração — nada é guardado',
  'socle.bandeau_fichiers_abimes.fichier_abime': 'Ficheiro danificado',
  'socle.bandeau_fichiers_abimes.fichiers_abimes': 'Ficheiros danificados',
  'socle.bandeau_fichiers_abimes.prevenez_responsable': '<b>{titre}: avise o responsável.</b> {suite}',
  'socle.bandeau_fichiers_abimes.tant_ils_sont_pas': 'Enquanto não forem reparados, o Prévo recusa as gravações que os afetam, sem perder nada.',
  'socle.bandeau_fichiers_abimes.tant_pas_repare_prevo': 'Enquanto não for reparado, o Prévo recusa as gravações que o afetam, sem perder nada.',
  'socle.bandeau_fichiers_abimes.tete_coupe_guillemet_non': '<b>{titre}: {fichiers}.</b> Cabeçalho cortado, aspas não fechadas ou valores além do cabeçalho: o Prévo deixa de o guardar, para não perder nada. Corrija o ficheiro, restaure uma cópia de segurança ou importe um ZIP; o detalhe está em Definições › Controlo da base.',
  'socle.bandeau_fichiers_laisses.fichier_abime_laisse_tel': 'Ficheiro danificado deixado como está',
  'socle.bandeau_fichiers_laisses.fichiers_abimes_laisses_tels': 'Ficheiros danificados deixados como estão',
  'socle.bandeau_fichiers_laisses.tete_illisible_lignes_reecriture': '<b>{titre}: {fichiers}.</b> Cabeçalho ilegível, ou linhas que uma reescrita faria perder: o Prévo não o reescreve para o passar ao formato {version}. Corrija o ficheiro ou restaure uma cópia de segurança; o detalhe está em Definições › Controlo da base.',
  'socle.bandeau_format_en_attente.fichiers_donnees_sont_pas': '<b>Os ficheiros de dados ainda não estão no formato {courant}</b> (formato {depart} encontrado). É o servidor Prévo que os atualiza, no arranque, depois de uma cópia de segurança; este navegador não lhes toca. Se esta mensagem continuar visível, feche o Excel (e qualquer programa que tenha aberto um ficheiro de dados) e reinicie o Prévo. Até lá, as OT preventivas vencidas não são geradas automaticamente.',
  'socle.btn_base_demo.atelier_fictif_complet_pourrez': 'Uma oficina fictícia completa, que pode editar ou substituir',
  'socle.btn_base_demo.partir_donnees_demo': 'Começar com os dados de demonstração',
  'socle.btn_base_vide.23_fichiers_csv_seuls': '23 ficheiros CSV só com os cabeçalhos das colunas',
  'socle.btn_base_vide.creer_base_vide': 'Criar uma base vazia',
  'socle.btn_demo.atelier_fictif_rien_enregistre': 'Oficina fictícia, nada é guardado',
  'socle.btn_demo.essayer_donnees_demo': 'Experimentar com os dados de demonstração',
  'socle.btn_dossier.choisir_dossier_donnees': 'Escolher a pasta de dados',
  'socle.btn_dossier.fichiers_csv_restent_pc': 'Os ficheiros CSV ficam neste PC (Chrome ou Edge)',
  'socle.btn_explications.explications': 'Explicações',
  'socle.btn_explications.revoir_explication_ecran': 'Rever a explicação deste ecrã',
  'socle.btn_explications_mobile.explications_ecran': 'Explicações deste ecrã',
  'socle.btn_export_demo.exporter_zip': 'Exportar para ZIP',
  'socle.btn_replier.replier_menu': 'Recolher o menu',
  'socle.btn_reprendre.reprendre_dossier_precedent': 'Retomar a pasta anterior',
  'socle.btn_telecharger.gratuit_libre_installez_travailler': 'Gratuito e livre: instale-o para trabalhar com os seus próprios dados.',
  'socle.btn_telecharger.telecharger_prevo': 'Transferir o Prévo',
  'socle.changer_profil.profil_libelle_affiche': 'Perfil: {libelleAffiche}.',
  'socle.chargement.chargement': 'A carregar…',
  'socle.charger_echarts.bibliotheque_graphiques_js_lib': 'Não foi possível carregar a biblioteca de gráficos (js/lib/echarts.min.js).',
  'socle.charger_image.image_peut_pas_etre': 'Não é possível ler esta imagem (formato não suportado?).',
  'socle.charger_script_demo.jeu_demo_js_demo': 'Não foi possível carregar o conjunto de demonstração (js/demo-donnees.js).',
  'socle.charger_sheet_js.bibliotheque_lecture_fichiers_excel': 'Não foi possível carregar a biblioteca de leitura de ficheiros Excel (js/lib/xlsx.full.min.js).',
  'socle.choisir.choix_dossier': 'escolha da pasta',
  'socle.confirmer.confirmation': 'Confirmação',
  'socle.confirmer.confirmer': 'Confirmar',
  'socle.connexion_avec_compte.ai_compte': 'Tenho uma conta',
  'socle.connexion_changer.enregistrer_continuer': 'Guardar e continuar',
  'socle.connexion_enrolement.entrez_nom': 'Introduza o seu nome',
  'socle.connexion_enrolement.nom_inscrit_demandes_appareil': 'O seu nome fica registado nos seus pedidos; este dispositivo continuará a ser reconhecido sem palavra-passe.',
  'socle.connexion_formulaire.forme_prenom_nom_donne': 'Na forma nome.apelido, indicado pelo responsável.',
  'socle.connexion_formulaire.identifiant': 'Nome de utilizador',
  'socle.connexion_formulaire.mot_passe': 'Palavra-passe',
  'socle.connexion_formulaire.rester_connecte_appareil': 'Manter a sessão iniciada neste dispositivo',
  'socle.connexion_mdp_deconnexion.deconnecter': 'Terminar sessão',
  'socle.connexion_mot_de_passe_panneau.12_caracteres_moins_256': 'No mínimo 12 caracteres e no máximo 256, sem regras de composição: recomenda-se uma frase-passe com várias palavras.',
  'socle.connexion_mot_de_passe_panneau.confirmation': 'Confirmação',
  'socle.connexion_mot_de_passe_panneau.mot_passe_actuel_provisoire': 'Palavra-passe atual (provisória)',
  'socle.connexion_mot_de_passe_panneau.nouveau_mot_passe': 'Nova palavra-passe',
  'socle.connexion_sous_titre.chaque_personne_compte_serveur': 'Cada pessoa tem a sua conta; o servidor verifica os direitos.',
  'socle.connexion_titre.connexion': 'Início de sessão',
  'socle.connexion_valider.connecter': 'Iniciar sessão',
  'socle.constructor.action_refusee': 'Ação recusada.',
  'socle.constructor.donnees_viennent_version_plus': 'Estes dados vêm de uma versão mais recente do Prévo (formato {format} dos ficheiros; esta versão lê até ao formato {version}): são abertos só para leitura e nada é guardado. Abra-os com a última versão do Prévo.',
  'socle.constructor.fichier_abime_tete_coupe': 'O ficheiro {fichier} está danificado (cabeçalho cortado, aspas não fechadas ou valores além do cabeçalho): o Prévo deixa de o guardar, para não perder nada. Corrija-o, restaure uma cópia de segurança ou importe um ZIP (Definições); o detalhe está em Definições › Controlo da base.',
  'socle.constructor.fichier_ete_modifie_meme': 'O ficheiro foi modificado ao mesmo tempo noutra estação de trabalho.',
  'socle.constructor.lecture_ecriture_fichier_impossible': 'Não foi possível ler ou escrever o ficheiro.',
  'socle.construire_menus.plus': 'Mais',
  'socle.controler_coherence.demande_acceptee_mais_aucun': 'Pedido {id}: está «Aceite», mas nenhuma ordem de trabalho lhe está associada. Reabra-o ou associe-o à sua ordem de trabalho.',
  'socle.controler_coherence.demande_acceptee_mais_ordre': 'Pedido {id}: está «Aceite», mas a sua ordem de trabalho «{ot_id}» não existe.',
  'socle.controler_coherence.ordre_travail_vient_demande': 'Ordem de trabalho {id}: vem do pedido «{di_id}», que está «{statut}» (nem aceite nem agrupado). Aceite ou agrupe o pedido, ou cancele a ordem de trabalho.',
  'socle.controler_coherence.sans_identifiant': '(sem ID)',
  'socle.controler_identifiants.identifiant_apparait_plusieurs_fois': '{descriptionLibelle}: o ID «{cle}» aparece várias vezes em {fichier} (linha de dados n.º {numero}). O Prévo só encontra a primeira linha: atribua um ID único às outras.',
  'socle.controler_identifiants.pas_identifiant_colonne_vide': '{descriptionLibelle}: a {reperageLigne} de {fichier} não tem ID (coluna «{cle}» vazia). Preencha-o ou elimine a linha no ficheiro.',
  'socle.controler_references.existe_mais_lieu': 'existe em {descriptionCibleLibelle}, mas com {familleTrouvee} em vez de {filtre}',
  'socle.controler_references.existe_pas': 'não existe em {descriptionCibleLibelle} ({filtre})',
  'socle.controler_references.existe_pas_sans_filtre': 'não existe em {descriptionCibleLibelle}',
  'socle.controler_references.reperage_champ_libelle_vaut_valeur': '{reperage}: «{champLibelle}» vale «{valeur}», que {explication}.',
  'socle.controler_wiki.changements_illisibles': '(alterações ilegíveis)',
  'socle.controler_wiki.cite_aucun_ot': 'não cita nenhuma OT.',
  'socle.controler_wiki.cite_ot_existe_pas': 'cita a OT «{ot}», que não existe.',
  'socle.controler_wiki.entree_journal_wiki_contradiction': { one: 'Entrada {entreeId} do registo do wiki: contradição aberta há mais de {n} dia na página «{page}».', other: 'Entrada {entreeId} do registo do wiki: contradição aberta há mais de {n} dias na página «{page}».' },
  'socle.controler_wiki.entree_journal_wiki_validee': 'Entrada {entreeId} do registo do wiki: está «validada», mas as suas alterações não estão nas páginas ({pages}).',
  'socle.controler_wiki.lien_vers_page_inexistante': 'ligação para uma página inexistente ou arquivada («{lien}»).',
  'socle.controler_wiki.meme_titre_page_deux': 'mesmo título que a página {page} (duas páginas ativas com a mesma chave).',
  'socle.controler_wiki.page_wiki': 'Página do wiki {id} («{pageTitre}»): {message}',
  'socle.controler_wiki.rattachee_page_archivee': 'associada à página arquivada «{mereTitre}» ({mereId}).',
  'socle.controler_wiki.sous_page_page_archivee': 'subpágina da página arquivada «{mereTitre}» ({mereId}).',
  'socle.controler_wiki.type_page_retire_panne': 'tipo de página retirado («{pageType}»: uma avaria é uma página calculada pelo Prévo); arquive-a.',
  'socle.creer.ajout_fichier': 'adição ao ficheiro',
  'socle.creer.aucune_table_restauree': 'nenhuma',
  'socle.creer.contenu_ajouter_doit_commencer': 'O conteúdo a adicionar deve começar pela linha de cabeçalho.',
  'socle.creer.contenu_ajouter_doit_etre': 'O conteúdo a adicionar deve estar codificado em UTF-8.',
  'socle.creer.demo_rien_enregistre': 'Demonstração — nada é guardado',
  'socle.creer.document_existe_deja': 'O documento {nom} já existe.',
  'socle.creer.document_porte_deja_nom': 'Já existe um documento com este nome.',
  'socle.creer.dossier_name': 'Pasta «{name}»',
  'socle.creer.enregistrement_document': 'gravação do documento',
  'socle.creer.enregistrement_table': 'gravação da tabela',
  'socle.creer.fichier_csv_ete_modifie': 'O ficheiro {nomTable}.csv foi modificado por outra estação de trabalho.',
  'socle.creer.fichier_csv_existe_deja': 'O ficheiro {nomTable}.csv já existe.',
  'socle.creer.fichier_csv_existe_plus': 'O ficheiro {nomTable}.csv já não existe.',
  'socle.creer.fichier_csv_pas_utf': 'O ficheiro {nomTable}.csv não está em UTF-8 (guardado de novo pelo Excel?).',
  'socle.creer.fichier_vient_etre_modifie': 'O ficheiro {nomFichier} acabou de ser modificado por outra estação de trabalho.',
  'socle.creer.indisponible_mode_demo_rien': 'Indisponível no modo de demonstração: nada é guardado.',
  'socle.creer.lecture_document': 'leitura do documento',
  'socle.creer.lecture_nom_fichiers_abimes': 'leitura de {fichier}',
  'socle.creer.lecture_table': 'leitura da tabela',
  'socle.creer.lecture_versions': 'leitura das versões',
  'socle.creer.liste_sauvegardes': 'lista das cópias de segurança',
  'socle.creer.mise_jour': 'atualização de {fichier}',
  'socle.creer.nom_document_invalide': 'Nome de documento inválido: «{nom}».',
  'socle.creer.poste_inconnu': 'Estação de trabalho desconhecida',
  'socle.creer.restauration': 'restauro',
  'socle.creer.restauration_interrompue_table_tables': '{interrompueMessage} Restauro interrompido na tabela {table}; tabelas já restauradas: {dejaRestaurees}. O estado anterior ao restauro está na cópia de segurança {copieSecurite}.',
  'socle.creer.sauvegarde': 'cópia de segurança',
  'socle.creer.sauvegarde_avant_mise_jour': 'cópia de segurança antes da atualização do Prévo',
  'socle.creer.sauvegarde_incomplete_copie_interrompue': 'A cópia de segurança {nom} está incompleta (cópia interrompida ou em curso): escolha outra.',
  'socle.creer.sauvegarde_introuvable': 'Cópia de segurança não encontrada: {nom}.',
  'socle.creer.serveur_host': 'Servidor {host}',
  'socle.creer.table_absente_sauvegarde': 'A tabela {table} não existe nesta cópia de segurança.',
  'socle.creer.tables_doit_etre_liste': '«tables» deve ser uma lista de nomes de tabelas.',
  'socle.creer.tete_csv_different': 'O cabeçalho de {nomTable}.csv é diferente.',
  'socle.creer.version_application_inconnue_rien': 'Versão da aplicação desconhecida: nada é guardado.',
  'socle.decaler_dates.stockage_demo_decaler_dates_dates_attendues': 'StockageDemo.decalerDates: datas esperadas no formato AAAA-MM-DD.',
  'socle.deconnecter.appareil_enrole_sans_mot': 'Este dispositivo está associado sem palavra-passe: só o responsável o pode revogar (Equipa › Acesso).',
  'socle.definir_titre.prevo': 'Prévo',
  'socle.definir_titre.prevo_gmao': 'Prévo — GMAO',
  'socle.definir_titre.texte_prevo': '{texte} — Prévo',
  'socle.demander_base_vide.aucun_fichier_trouve': { one: 'O ficheiro do Prévo não foi encontrado ({stockage}). Por onde pretende começar?', other: 'Nenhum dos {n} ficheiros do Prévo foi encontrado ({stockage}). Por onde pretende começar?' },
  'socle.demander_motif.motif': 'Motivo',
  'socle.demander_motif.motif_obligatoire': 'O motivo é obrigatório.',
  'socle.demander_motif.valider': 'Confirmar',
  'socle.demarrage.navigateur_sait_pas_ouvrir': '<b>Este navegador não sabe abrir uma pasta.</b> Para trabalhar com os seus ficheiros, utilize o Chrome ou o Edge num computador. Entretanto, a demonstração funciona aqui.',
  'socle.depuis_fichiers.impossible_lire_fichier': 'Não foi possível ler o ficheiro {name}.',
  'socle.description_table.donnees_csv_table_inconnue': 'Donnees.csv: tabela desconhecida «{nomTable}».',
  'socle.ecran.app_ecran_ecran_deja': 'App.ecran: o ecrã «{definitionId}» já está registado.',
  'socle.ecran.app_ecran_id_route': 'App.ecran: id, route (RegExp) e afficher(conteneur, parametres) são obrigatórios.',
  'socle.ecran_base_vide.aucune_donnee_instant': 'Ainda sem dados',
  'socle.ecran_base_vide.langue_prevo': 'Idioma do Prévo',
  'socle.ecran_base_vide.langue_prevo_aide': 'Sugerido a partir deste navegador. O Prévo abrirá neste idioma nas estações de trabalho que não escolheram o seu; é também o idioma dos textos que escreve nos dados. Pode alterá-lo mais tarde em Definições.',
  'socle.ecran_chargement.chargement_prevo': 'A carregar o Prévo…',
  'socle.ecran_demarrage.developpe_claude_anthropic_demande': 'Desenvolvido por Claude (Anthropic) a pedido de Nicolas Briand — SELECTIS',
  'socle.ecran_demarrage.gmao_libre_atelier_demandes': 'GMAO livre para a oficina: pedidos, ordens de trabalho, parque de equipamentos.',
  'socle.ecran_demarrage.prevo': 'Prévo',
  'socle.ecran_installation.installer_prevo': 'Instalar o Prévo',
  'socle.ecran_profil.inscrit_journal_chaque_modification': 'Fica registado no registo de alterações com cada modificação.',
  'socle.ecran_profil.nom_poste': 'Nome desta estação de trabalho',
  'socle.ecran_profil.profil_adapte_ecrans_pas': 'O perfil adapta os ecrãs; não é uma medida de segurança.',
  'socle.ecran_profil.utilise_poste': 'Quem utiliza esta estação de trabalho?',
  'socle.en_octets.contenu_fichier_illisible_texte': 'Conteúdo de ficheiro ilegível (esperava-se texto ou bytes).',
  'socle.en_octets.donnees_csv_octets_attendus': 'Donnees.csv: esperavam-se bytes (Uint8Array ou ArrayBuffer).',
  'socle.en_octets.formats_manifeste_octets_attendus': 'Formats.manifeste: esperavam-se bytes (Uint8Array ou ArrayBuffer).',
  'socle.en_octets.stockage_dossier_octets_attendus_uint': 'StockageDossier: esperavam-se bytes (Uint8Array ou ArrayBuffer).',
  'socle.erreur_depuis_reponse.serveur_refuse_demande_code': 'O servidor recusou o pedido (código {status}).',
  'socle.erreur_depuis_reponse.table': 'desta tabela',
  'socle.etat_poste.changer': 'alterar',
  'socle.etat_poste.changer_profil': 'Alterar o perfil',
  'socle.exiger_formats.donnees_registre_formats_js': 'Donnees: o registo dos formatos (js/formats.js) deve ser carregado antes de js/donnees.js.',
  'socle.explication_valeur_illisible.fait_pas_partie_valeurs': 'não faz parte dos valores possíveis ({valeurs})',
  'socle.explication_valeur_illisible.illisible': 'é ilegível',
  'socle.explication_valeur_illisible.pas_date_heure_valide': 'não é uma data e hora válida (formatos aceites: 2024-03-15 08:30 ou 15/03/2024 08:30)',
  'socle.explication_valeur_illisible.pas_date_valide_formats': 'não é uma data válida (formatos aceites: 2024-03-15 ou 15/03/2024)',
  'socle.explication_valeur_illisible.pas_nombre_entier': 'não é um número inteiro',
  'socle.explication_valeur_illisible.pas_nombre_exemples_acceptes': 'não é um número (exemplos aceites: 7,5 ou 7.5)',
  'socle.explication_valeur_illisible.pas_reconnu_comme_oui': 'não é reconhecido como sim ou não (valores aceites: 1, 0, oui, non, vrai, faux, x)',
  'socle.fichier_abime_depuis.depuis_le': { one: '{fichier}, desde {date} ({n} dia)', other: '{fichier}, desde {date} ({n} dias)' },
  'socle.fichier_abime_depuis.repere_aujourd_hui': '{fichier}, detetado hoje',
  'socle.html.ui_html_utilise_comme': 'UI.html utiliza-se como modelo: UI.html`…`',
  'socle.installation_contenu.lecture_etat_installation': 'A ler o estado da instalação…',
  'socle.installation_premiere_ligne.tant_installation_pas_terminee': 'Enquanto a instalação não estiver concluída, o Prévo só pode ser acedido neste PC.',
  'socle.installation_quitter.ouvrir_prevo_sans_terminer': 'Abrir o Prévo sem concluir a instalação (continua acessível só neste PC)',
  'socle.lecture_seule.lecture_seule_donnees_viennent': '<b>Só de leitura: estes dados vêm de uma versão mais recente do Prévo</b> (formato {format} dos ficheiros; esta versão lê até ao formato {version}). Pode consultá-los, mas nada é guardado. Abra-os com a última versão do Prévo.',
  'socle.libelle_journal.demandeur_p_nom': 'Requerente {nom}',
  'socle.libelle_journal.technicien_technicien_id': 'Técnico {technicienId}',
  'socle.libelle_type.demandeur': 'Requerente',
  'socle.libelle_type.responsable': 'Responsável',
  'socle.libelle_type.technicien': 'Técnico',
  'socle.lire_cellule.valeur_conservee_telle_quelle': '{explicationValeurIllisible}. Valor conservado tal como está: a corrigir',
  'socle.lire_cellule.valeur_probablement_abimee_excel': 'valor provavelmente danificado pelo Excel (número longo transformado em notação científica). Encontre o valor original e introduza-o precedido de uma apóstrofe, por exemplo \'123456789012345',
  'socle.lire_cellule.valeur_probablement_abimee_excel_formule': 'valor provavelmente danificado pelo Excel (texto que começa por «=», «+» ou «-» tomado por uma fórmula). Encontre o texto original e introduza-o precedido de uma apóstrofe',
  'socle.liste_deroulante.choisir': '— Escolher —',
  'socle.liste_deroulante.valeur_inconnue': '{valeurTexte} (valor desconhecido)',
  'socle.menu.navigation_principale': 'Navegação principal',
  'socle.message_conflit_persistant.fichier_modifie_meme_temps': 'O ficheiro {nomTable} está a ser modificado ao mesmo tempo noutra estação de trabalho. Tente novamente dentro de instantes.',
  'socle.message_delai_depasse.serveur_prevo_met_trop': 'O servidor Prévo demora demasiado a responder. Verifique a rede e tente novamente; se estava a guardar, recarregue a página para ver se a alteração foi feita.',
  'socle.message_erreur.fichier_abime_prevenez_responsable': 'Ficheiro danificado: avise o responsável. Nada foi guardado; o que introduziu continua no formulário.',
  'socle.message_erreur.fichier_abime_rien_ete': 'Ficheiro danificado: nada foi guardado, para não perder nada; o que introduziu continua no formulário. Restaure a cópia de segurança do dia (Definições › Cópias de segurança) ou importe um ZIP; o detalhe está em Definições › Controlo da base.',
  'socle.message_erreur.fichier_abime_rien_ete_avec_fichier': 'Ficheiro danificado ({fichier}): nada foi guardado, para não perder nada; o que introduziu continua no formulário. Restaure a cópia de segurança do dia (Definições › Cópias de segurança) ou importe um ZIP; o detalhe está em Definições › Controlo da base.',
  'socle.message_fichier_ouvert.fichier_dossier_donnees_ouvert': 'Um ficheiro da pasta de dados está aberto no Excel ou noutro programa: feche-o e tente novamente.',
  'socle.message_fichier_ouvert.fichier_ouvert_excel_autre': 'O ficheiro «{nomFichier}» está aberto no Excel ou noutro programa: feche-o e tente novamente.',
  'socle.message_reponse_inattendue.reponse_inattendue_serveur_operation': 'Resposta inesperada do servidor; a operação pode ter sido feita, recarregue a página.',
  'socle.message_serveur_injoignable.serveur_prevo_repond_pas': 'O servidor Prévo não responde. Verifique se a janela do servidor está aberta no PC.',
  'socle.mettre_ajour_boutons_profil.appareil_enrole': 'Dispositivo associado: {libelleAffiche}',
  'socle.mettre_ajour_boutons_profil.changer_profil': 'Alterar o perfil',
  'socle.mettre_ajour_boutons_profil.connecte_cliquer_deconnecter': 'Sessão iniciada: {libelleCompte}. Clique para terminar a sessão.',
  'socle.mettre_ajour_boutons_profil.deconnecter': 'terminar sessão',
  'socle.mettre_ajour_boutons_profil.deconnecter_bouton': 'Terminar sessão',
  'socle.mettre_ajour_boutons_profil.profil_poste_cliquer_changer': 'Perfil: {libelleAffiche} — estação de trabalho «{poste}». Clique para alterar.',
  'socle.migrer.formats_migrer_format_cible': 'Formats.migrer: formato de destino desconhecido ({vers}); formatos conhecidos: {premier} a {version}.',
  'socle.migrer.formats_migrer_format_depart': 'Formats.migrer: formato de origem ilegível ({de}).',
  'socle.migrer_au_format_courant.sans_sauvegarde_demo': 'sem cópia de segurança (demonstração)',
  'socle.migrer_au_format_courant.sauvegarde_avant_passage_format': 'Cópia de segurança antes da passagem ao formato {courant} impossível: {messageSansPointFinal}; a atualização será repetida na próxima abertura.',
  'socle.migrer_au_format_courant.sauvegarde_faite_juste_avant': 'cópia de segurança {sauvegarde} feita mesmo antes',
  'socle.note_donnees_demo.atelier_francais_interface_traduite': 'Os dados da demonstração descrevem uma oficina francesa: só a interface está traduzida.',
  'socle.note_donnees_demo.nulle_part_elles_vivent': 'Em lado nenhum: vivem nesta página e desaparecem quando a fecha. Na sua instalação, são ficheiros CSV no seu PC, legíveis no Excel.',
  'socle.nouvel_id.donnees_nouvel_id_table_pas': 'Donnees.nouvelId: a tabela «{nomTable}» não tem ID calculado.',
  'socle.ouvrir_fichiers_deposes.aucun_fichier_reconnu_fichiers': 'Nenhum ficheiro reconhecido: os ficheiros devem chamar-se equipements.csv, demandes.csv, ordres_travail.csv…',
  'socle.ouvrir_fichiers_deposes.fichiers_ignores_nom_inconnu': 'Ficheiros ignorados (nome desconhecido ou repetido): {fichiers}',
  'socle.ouvrir_plus.changer_profil': 'Alterar o perfil ({libelleAffiche})',
  'socle.ouvrir_plus.deconnecter_libelle_compte': 'Terminar sessão ({libelleCompte})',
  'socle.ouvrir_plus.exporter_zip': 'Exportar para ZIP',
  'socle.passer_au_format_courant.fichiers_ont_pas_pu': '<b>Os ficheiros não puderam passar ao formato {version}.</b> {message} Até lá, as OT preventivas vencidas não são geradas automaticamente.',
  'socle.poste_aleatoire.poste_suffixe': 'Estação-{suffixe}',
  'socle.probleme_colonne_absente.colonne_absente_sera_ajoutee': '{descriptionLibelle}: a coluna «{champNom}» ({champLibelle}) não existe em {fichier}; {suite}. Será adicionada na próxima alteração da tabela.',
  'socle.probleme_colonne_absente.colonne_ajoutee_version_format': '{descriptionLibelle}: coluna «{champNom}» adicionada pela versão {depuisVersion} do formato, escrita na próxima gravação.',
  'socle.probleme_colonne_absente.valeur_defaut_utilisee': 'é utilizado o valor predefinido «{valeurParDefaut}»',
  'socle.probleme_colonne_absente.valeur_laissee_vide': 'o valor fica vazio',
  'socle.probleme_table_laissee.abime_structure_fichier_valeurs': '{fichier} está danificado (estrutura do ficheiro, ou valores além do cabeçalho: ver os seus outros problemas) e reescrevê-lo perderia uma parte',
  'socle.probleme_table_laissee.ligne_tete_incomplete_illisible': 'a linha de cabeçalho de {fichier} está incompleta ou ilegível (faltam-lhe colunas do formato 1)',
  'socle.probleme_table_laissee.prevo_reecrit_pas_fichier': '{descriptionLibelle}: {raison}; o Prévo não reescreve este ficheiro para o passar ao formato {version} e deixa-o como está. Corrija-o ou restaure uma cópia de segurança.',
  'socle.profil_demandeur.demandeur': 'Requerente',
  'socle.profil_demandeur.signaler_probleme_suivre_mes': 'Comunicar um problema, acompanhar os meus pedidos',
  'socle.profil_panneau_demandeur.nom': 'O seu nome',
  'socle.profil_panneau_demandeur.retour': 'Voltar',
  'socle.profil_panneau_technicien.choisissez_nom': 'Escolha o seu nome',
  'socle.profil_responsable.responsable': 'Responsável',
  'socle.profil_responsable.tout_suivi_demandes_ot': 'Todo o acompanhamento: pedidos, OT, parque de equipamentos, definições',
  'socle.profil_technicien.mes_ordres_travail_comptes': 'As minhas ordens de trabalho, relatórios de intervenção',
  'socle.profil_technicien.technicien': 'Técnico',
  'socle.qr_svg.bibliotheque_qrcode_absente_js': 'Biblioteca qrcode em falta (js/lib/qrcode.js).',
  'socle.qr_svg.qr_code': 'QR code: {texte}',
  'socle.raison_erreur.fichier_abime_prevenez_responsable': 'ficheiro danificado: avise o responsável',
  'socle.raison_erreur.fichier_abime_rien_ete': 'ficheiro danificado, nada nele foi guardado: restaure a cópia de segurança do dia ou importe um ZIP; o detalhe está em Definições › Controlo da base',
  'socle.raison_erreur.fichier_abime_rien_ete_avec_fichier': 'ficheiro danificado ({fichier}), nada nele foi guardado: restaure a cópia de segurança do dia ou importe um ZIP; o detalhe está em Definições › Controlo da base',
  'socle.redimensionner_photo.photo_pas_pu_etre': 'Não foi possível converter a fotografia.',
  'socle.remplir_liste_techniciens.aucun_technicien_actif_techniciens': 'Nenhum técnico ativo em techniciens.csv: escolha outro perfil.',
  'socle.remplir_phrases_balisees.developpe_claude_anthropic_demande': 'Desenvolvido por <b>Claude (Anthropic)</b> a pedido de <b>Nicolas Briand — SELECTIS</b>',
  'socle.remplir_phrases_balisees.installer_prevo_assistant_comptes': '<a href="#/installation">Instalar o Prévo (assistente)</a>: contas, https, telemóveis, arranque com o PC.',
  'socle.remplir_phrases_balisees.plusieurs_postes_telephones_lancez': 'Várias estações de trabalho e telemóveis? Execute <b>Lancer_GMAO.bat</b> (Windows) ou <b>lancer.sh</b> (Mac, Linux): o modo servidor é reconhecido automaticamente.',
  'socle.rendre.ecran_pas_pu_afficher': '<b>Não foi possível apresentar este ecrã.</b> {message}',
  'socle.reperage_ligne.ligne_donnees_sans_identifiant': 'linha de dados n.º {numero} (sem ID)',
  'socle.reprendre_dossier.acces_dossier_precedent_pas': 'O acesso à pasta anterior não foi concedido. Escolha novamente a pasta.',
  'socle.route.aucun_ecran_correspond_adresse': 'Nenhum ecrã corresponde a este endereço.',
  'socle.route.ecran_introuvable': 'Ecrã não encontrado',
  'socle.route.ecran_pas_disponible_profil': 'O ecrã «{ecranTitre}» não está disponível para o perfil {profil}.',
  'socle.sauvegarder_avant_format.mode_stockage_sait_pas': 'este modo de armazenamento não sabe fazer cópias de segurança',
  'socle.sauvegarder_avant_format.stockage_pas_confirme_sauvegarde': 'o armazenamento não confirmou a cópia de segurança (nenhum nome devolvido)',
  'socle.sauvegarder_avant_mise_ajour.sauvegarde_avant_mise_jour': '<b>Não foi possível fazer a cópia de segurança «antes da atualização do Prévo».</b> {message} Será repetida na próxima abertura.',
  'socle.scanner_qr.impossible_ouvrir_camera_autorisation': 'Não foi possível abrir a câmara (autorização recusada ou câmara ocupada).',
  'socle.scanner_qr.placez_qr_code_equipement': 'Coloque o QR code do equipamento no quadro.',
  'socle.scanner_qr.scan_camera_pas_disponible': 'A leitura por câmara não está disponível nesta página. Utilize a câmara do telemóvel.',
  'socle.scanner_qr.scanner_qr_code': 'Ler um QR code',
  'socle.selecteur_equipement.aucun_equipement_correspond': 'Nenhum equipamento corresponde a «{recherche}».',
  'socle.selecteur_equipement.changer': 'Alterar',
  'socle.selecteur_equipement.equipements_trouves': 'Equipamentos encontrados',
  'socle.selecteur_equipement.equipements_trouves_affiner': { one: '{n} equipamento: escreva algumas letras para refinar.', other: '{n} equipamentos: escreva algumas letras para refinar.' },
  'socle.selecteur_equipement.qr_code_correspond_aucun': 'Este QR code não corresponde a nenhum equipamento conhecido.',
  'socle.selecteur_equipement.rechercher_equipement': 'Pesquisar um equipamento',
  'socle.selecteur_equipement.repere_nom': 'Código ou nome',
  'socle.selecteur_equipement.scanner': 'Ler',
  'socle.selecteur_langue.changer': 'Alterar',
  'socle.selecteur_langue.changer_langue': 'Alterar o idioma',
  'socle.selecteur_langue.choix_non_retenu': 'Idioma não retido: este navegador recusa guardar as suas definições.',
  'socle.selecteur_langue.langue_ecran': 'Idioma do ecrã',
  'socle.selecteur_langue.recharge_demo': 'Alterar o idioma recarrega a demonstração: as modificações que fez nela serão perdidas.',
  'socle.session_perdue.reconnecte_saisie_gardee': 'Sessão reiniciada: o que introduziu continua no ecrã; guarde-o.',
  'socle.session_perdue.reconnectez_vous_meme_compte': 'A sua sessão terminou. Inicie sessão novamente com a mesma conta: encontrará o ecrã como o deixou, incluindo o que introduziu. O que não estava guardado ainda não o está: guarde-o a seguir.',
  'socle.suffixe_du_motif.motif_sauvegarde_refuse_motifs': 'Motivo de cópia de segurança recusado. Motivos aceites: {motifs}.',
  'socle.tableau.aucune_ligne_afficher': 'Nenhuma linha para apresentar.',
  'socle.texte_base_vide.aucun_23_fichiers_prevo': 'Nenhum dos 23 ficheiros do Prévo foi encontrado.',
  'socle.titre_donnees.ou_sont_donnees': 'Onde estão os seus dados?',
  'socle.titre_donnees_demo.ou_sont_donnees_demo': 'Onde estão os dados desta demonstração?',
  'socle.traduire_erreur.acces_refuse_dossier_donnees': 'Acesso recusado à pasta de dados ({action}). Escolha novamente a pasta para conceder de novo a autorização.',
  'socle.traduire_erreur.dossier_donnees_introuvable_ete': 'Pasta de dados não encontrada ({action}): foi movida, mudou de nome ou foi desligada?',
  'socle.traduire_erreur.lecture_ecriture_impossible_dossier': 'Leitura ou escrita impossível na pasta de dados ({action}).',
  'socle.valider_demandeur.indiquez_nom_permet_retrouver': 'Indique o seu nome: permite encontrar os seus pedidos.',
  'socle.verifier_dossier_accessible.dossier_donnees_introuvable_inaccessible': 'A pasta de dados não foi encontrada ou está inacessível (eliminada, movida, pen USB ou partilha de rede desligada?). Volte a ligá-la ou escolha novamente a pasta.',
  'socle.verifier_formulaire.case_doit_etre_cochee': 'Esta caixa tem de estar assinalada.',
  'socle.verifier_formulaire.champ_obligatoire': 'Este campo é obrigatório.',
  'socle.verifier_formulaire.saisissez_nombre_entier_ex': 'Introduza um número inteiro (ex.: 12).',
  'socle.verifier_formulaire.saisissez_nombre_ex_12': 'Introduza um número (ex.: 12,5).',
  'socle.verifier_initialise.donnees_appelez_donnees_initialiser': 'Donnees: chame Donnees.initialiser(adaptateur, …) antes de ler ou escrever.',
  'socle.verifier_nom_document.nom_document_refuse_lettres': 'Nome de documento recusado: letras, algarismos, «.», «_» ou «-».',
  'socle.verifier_nom_document.nom_document_reserve_windows': 'Nome de documento reservado pelo Windows.',
  'socle.verifier_nom_document.type_document_refuse_types': 'Tipo de documento recusado. Tipos aceites: {types}.',
  'socle.verifier_nom_sauvegarde.nom_sauvegarde_invalide': 'Nome de cópia de segurança inválido.',
  'socle.verifier_nom_table.table_inconnue': 'Tabela desconhecida: «{nomTable}».',
  'socle.verifier_nom_table.table_inconnue_dossier': 'Tabela desconhecida: {table}.',
  'socle.verifier_verrou_dossier.dossier_semble_deja_ouvert': '<b>Esta pasta parece já estar aberta em «{poste}»</b> (último sinal de vida: {heure}). Duas estações de trabalho que escrevem na mesma pasta podem interferir uma com a outra: feche a outra sessão, se possível.',
  'socle.zone_depot.cliquer_choisir_demo_propres': 'ou clique para os escolher: demonstração com os seus próprios ficheiros, nada é guardado',
  'socle.zone_depot.deposer_fichiers_csv_ici': 'Largar ficheiros CSV aqui',
});
// ==== fin socle ====

// ==== section planning ====
I18n.ajouter('pt-PT', {
});
// ==== fin planning ====

// ==== section causes ====
I18n.ajouter('pt-PT', {
});
// ==== fin causes ====

// ==== section dictee ====
I18n.ajouter('pt-PT', {
});
// ==== fin dictee ====

// ==== section mise ====
I18n.ajouter('pt-PT', {
});
// ==== fin mise ====

// ==== section aide ====
I18n.ajouter('pt-PT', {
});
// ==== fin aide ====

// ==== section ordres ====
I18n.ajouter('pt-PT', {
});
// ==== fin ordres ====

// ==== section demandes ====
I18n.ajouter('pt-PT', {
});
// ==== fin demandes ====

// ==== section parc ====
I18n.ajouter('pt-PT', {
});
// ==== fin parc ====

// ==== section preventif ====
I18n.ajouter('pt-PT', {
});
// ==== fin preventif ====

// ==== section controles ====
I18n.ajouter('pt-PT', {
});
// ==== fin controles ====

// ==== section wiki ====
I18n.ajouter('pt-PT', {
});
// ==== fin wiki ====

// ==== section suggestions ====
I18n.ajouter('pt-PT', {
});
// ==== fin suggestions ====

// ==== section import ====
I18n.ajouter('pt-PT', {
});
// ==== fin import ====

// ==== section magasin ====
I18n.ajouter('pt-PT', {
});
// ==== fin magasin ====

// ==== section indicateurs ====
I18n.ajouter('pt-PT', {
});
// ==== fin indicateurs ====

// ==== section rapport ====
I18n.ajouter('pt-PT', {
});
// ==== fin rapport ====

// ==== section accueil ====
I18n.ajouter('pt-PT', {
});
// ==== fin accueil ====

// ==== section equipe ====
I18n.ajouter('pt-PT', {
});
// ==== fin equipe ====

// ==== section acces ====
I18n.ajouter('pt-PT', {
});
// ==== fin acces ====

// ==== section connexion ====
I18n.ajouter('pt-PT', {
});
// ==== fin connexion ====

// ==== section poste ====
I18n.ajouter('pt-PT', {
});
// ==== fin poste ====

// ==== section apropos ====
I18n.ajouter('pt-PT', {
});
// ==== fin apropos ====

// ==== section installation ====
I18n.ajouter('pt-PT', {
});
// ==== fin installation ====

// ==== section porte ====
I18n.ajouter('pt-PT', {
});
// ==== fin porte ====

// ==== section parametres ====
I18n.ajouter('pt-PT', {
});
// ==== fin parametres ====

// ==== section sauvegardes ====
I18n.ajouter('pt-PT', {
});
// ==== fin sauvegardes ====

// ==== section zip ====
I18n.ajouter('pt-PT', {
});
// ==== fin zip ====

// ==== section serveur ====
I18n.ajouter('pt-PT', {
});
// ==== fin serveur ====

// ==== section ia ====
I18n.ajouter('pt-PT', {
});
// ==== fin ia ====
