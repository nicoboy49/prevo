'use strict';
// Textes turcs de Prévo : turc, locale tr-TR (chantier multilingue, Lot 5, T343 ; version 2.1.0).
// Traduction automatique assumée (l'interface le dit : « traduction automatique — corrections bienvenues »).
// Mêmes sections que js/i18n/fr.js, dans le même ordre : une section par domaine. On traduit par groupes de
// domaines, une tâche par groupe, chacune dans ses sections seulement : jamais deux tâches sur les mêmes lignes.
// Dans chaque bloc : les clés de la même section de fr.js, triées, une par ligne, chaînes entre apostrophes
// simples, échappements gardés (jamais d'espace insécable écrit en clair : \u00a0, \u202f), mêmes variables {…}
// que le français ; un pluriel { one, other } là où le français en a un, un texte simple ailleurs.
// Vocabulaire : docs/GLOSSAIRE.md (colonne de la langue). Clé absente : texte français affiché (avertissement
// dans la console). Pas d'aide longue traduite (D158) : l'aide longue s'affiche en anglais.
// Contrôle : py -X utf8 outils/controler_textes.py --langue tr [--domaine <domaine>].
// Déclaré dans js/i18n/langues.js seulement quand toutes ses sections sont traduites (Lot 5).

// ==== section commun ====
I18n.ajouter('tr', {
  'commun.bouton.actualiser': 'Yenile',
  'commun.bouton.ajouter': 'Ekle',
  'commun.bouton.annuler': 'İptal',
  'commun.bouton.continuer': 'Devam',
  'commun.bouton.desactiver': 'Devre dışı bırak',
  'commun.bouton.enregistrer': 'Kaydet',
  'commun.bouton.fermer': 'Kapat',
  'commun.bouton.imprimer': 'Yazdır',
  'commun.bouton.modifier': 'Düzenle',
  'commun.brouillon.abandonner': 'Taslaktan vazgeç',
  'commun.brouillon.effacer': 'Taslağı sil',
  'commun.brouillon.repris': 'Taslak geri yüklendi: bu cihazda {quand} tarihinde girildi, henüz kaydedilmedi.',
  'commun.champ.article': 'Malzeme',
  'commun.champ.commentaire': 'Yorum',
  'commun.champ.criticite': 'Kritiklik',
  'commun.champ.date': 'Tarih',
  'commun.champ.designation': 'Tanım',
  'commun.champ.equipement': 'Ekipman',
  'commun.champ.numero': 'No',
  'commun.champ.prenom': 'Ad',
  'commun.champ.priorite': 'Öncelik',
  'commun.champ.prix_unitaire': 'Birim fiyat',
  'commun.champ.quantite': 'Miktar',
  'commun.champ.reference': 'Kod',
  'commun.champ.repere': 'Ekipman kodu',
  'commun.champ.statut': 'Durum',
  'commun.champ.symptome': 'Belirti',
  'commun.champ.technicien': 'Teknisyen',
  'commun.liste.non_choisi': '(seçilmedi)',
  'commun.message.aucune_modification': 'Kaydedilecek bir değişiklik yok.',
  'commun.message.champ_obligatoire': 'zorunlu alan',
  'commun.message.erreur_inconnue': 'bilinmeyen hata',
  'commun.message.fichier_trop_volumineux': 'Bu dosya çok büyük (en fazla 9 MB).',
  'commun.message.ot_introuvable': '{otId} numaralı iş emri bulunamadı.',
  'commun.message.saisi_sur_autre_poste': 'Başka bir iş istasyonunda girilmiş olabilir: yenileyin.',
  'commun.message.serveur_a_repondu': 'Sunucu “{status}” yanıtını verdi.',
});
// ==== fin commun ====

// ==== section schema ====
I18n.ajouter('tr', {
  'schema.achats.article_id': 'Malzeme',
  'schema.achats.date': 'Tarih',
  'schema.achats.date_reception': 'Teslim alma tarihi',
  'schema.achats.fournisseur_id': 'Tedarikçi',
  'schema.achats.id': 'ID',
  'schema.achats.prix_unitaire': 'Birim fiyat',
  'schema.achats.quantite': 'Miktar',
  'schema.achats.statut': 'Durum',
  'schema.article_equipement.article_id': 'Malzeme',
  'schema.article_equipement.equipement_id': 'Ekipman',
  'schema.article_equipement.id': 'ID',
  'schema.article_equipement.quantite': 'Miktar',
  'schema.articles.actif': 'Aktif',
  'schema.articles.critique': 'Kritik malzeme',
  'schema.articles.delai_jours': 'Tedarik süresi (gün)',
  'schema.articles.designation': 'Tanım',
  'schema.articles.emplacement': 'Raf adresi',
  'schema.articles.fabricant': 'Üretici',
  'schema.articles.fournisseur_id': 'Tedarikçi',
  'schema.articles.id': 'ID',
  'schema.articles.point_commande': 'Sipariş noktası',
  'schema.articles.prix_unitaire': 'Birim fiyat',
  'schema.articles.qte_commande': 'Sipariş miktarı',
  'schema.articles.ref_fabricant': 'Üretici parça numarası',
  'schema.articles.reference': 'Kod',
  'schema.articles.stock': 'Stok',
  'schema.articles.stock_securite': 'Emniyet stoku',
  'schema.articles.unite': 'Birim',
  'schema.codes_defaillance.code': 'Kod',
  'schema.codes_defaillance.famille': 'Aile',
  'schema.codes_defaillance.id': 'ID',
  'schema.codes_defaillance.libelle': 'Etiket',
  'schema.compteurs.equipement_id': 'Ekipman',
  'schema.compteurs.id': 'ID',
  'schema.compteurs.libelle': 'Etiket',
  'schema.compteurs.unite': 'Birim',
  'schema.controles_reglementaires.derniere_date': 'Son kontrol tarihi',
  'schema.controles_reglementaires.equipement_id': 'Ekipman',
  'schema.controles_reglementaires.id': 'ID',
  'schema.controles_reglementaires.nature': 'Kontrol türü',
  'schema.controles_reglementaires.observations': 'Gözlemler',
  'schema.controles_reglementaires.observations_levees': 'Giderilen gözlemler',
  'schema.controles_reglementaires.organisme': 'Muayene kuruluşu',
  'schema.controles_reglementaires.periodicite_mois': 'Periyot (ay)',
  'schema.controles_reglementaires.prochaine_date': 'Sonraki kontrol tarihi',
  'schema.controles_reglementaires.rapport': 'Rapor',
  'schema.controles_reglementaires.texte_reference': 'Dayanak metin',
  'schema.demandes.date_decision': 'Karar tarihi',
  'schema.demandes.date_heure': 'Talep tarihi ve saati',
  'schema.demandes.demandeur': 'Talep eden',
  'schema.demandes.description': 'Açıklama',
  'schema.demandes.equipement_id': 'Ekipman',
  'schema.demandes.id': 'ID',
  'schema.demandes.impact': 'Etki',
  'schema.demandes.motif_decision': 'Karar gerekçesi',
  'schema.demandes.ot_id': 'Bağlantılı iş emri',
  'schema.demandes.ot_origine_id': 'Kaynak iş emri (önleyici)',
  'schema.demandes.photo': 'Fotoğraf',
  'schema.demandes.statut': 'Durum',
  'schema.demandes.symptome': 'Gözlenen belirti',
  'schema.demandes.symptome_code': 'Belirti kodu',
  'schema.equipements.actif': 'Aktif',
  'schema.equipements.consignation': 'Enerji izolasyonu (LOTO)',
  'schema.equipements.criticite': 'Kritiklik',
  'schema.equipements.date_mes': 'Hizmete alma tarihi',
  'schema.equipements.designation': 'Tanım',
  'schema.equipements.document': 'Belge',
  'schema.equipements.habilitation_requise': 'Yetkilendirme gerekli',
  'schema.equipements.heures_fonct_jour': 'Günlük çalışma saati',
  'schema.equipements.id': 'ID',
  'schema.equipements.localisation_id': 'Konum',
  'schema.equipements.marque': 'Marka',
  'schema.equipements.modele': 'Model',
  'schema.equipements.num_serie': 'Seri numarası',
  'schema.equipements.parent_id': 'Üst ekipman',
  'schema.equipements.repere': 'Ekipman kodu',
  'schema.equipements.statut': 'Durum',
  'schema.equipements.valeur_remplacement': 'Yerine koyma değeri ({devise} KDV hariç)',
  'schema.fournisseurs.contact': 'İlgili kişi',
  'schema.fournisseurs.email': 'E-posta',
  'schema.fournisseurs.id': 'ID',
  'schema.fournisseurs.nom': 'Ad',
  'schema.fournisseurs.telephone': 'Telefon',
  'schema.gamme_operations.gamme_id': 'Bakım planı',
  'schema.gamme_operations.id': 'ID',
  'schema.gamme_operations.operation': 'Görev',
  'schema.gamme_operations.ordre': 'Sıra',
  'schema.gamme_operations.valeur_attendue': 'Beklenen değer',
  'schema.gammes.actif': 'Aktif',
  'schema.gammes.avance_jours': 'Önceden oluşturma (gün)',
  'schema.gammes.compteur_id': 'Sayaç',
  'schema.gammes.consignes': 'Talimatlar',
  'schema.gammes.declencheur': 'Tetikleyici',
  'schema.gammes.derniere_realisation': 'Son gerçekleştirme',
  'schema.gammes.equipement_id': 'Ekipman',
  'schema.gammes.id': 'ID',
  'schema.gammes.libelle': 'Etiket',
  'schema.gammes.periodicite_jours': 'Periyot (gün)',
  'schema.gammes.periodicite_unites': 'Periyot (sayaç birimi)',
  'schema.gammes.prochaine_echeance': 'Sonraki vade tarihi',
  'schema.gammes.releve_derniere_realisation': 'Son gerçekleştirmedeki okuma',
  'schema.gammes.seuil': 'Eşik',
  'schema.gammes.temps_prevu_h': 'Planlanan süre (saat)',
  'schema.habilitations.date_echeance': 'Geçerlilik bitişi',
  'schema.habilitations.date_obtention': 'Alınma tarihi',
  'schema.habilitations.id': 'ID',
  'schema.habilitations.intitule': 'Ad',
  'schema.habilitations.technicien_id': 'Teknisyen',
  'schema.journal.action': 'İşlem',
  'schema.journal.date_heure': 'Tarih ve saat',
  'schema.journal.id': 'ID',
  'schema.journal.id_ligne': 'Satır kimliği',
  'schema.journal.poste': 'İş istasyonu',
  'schema.journal.profil': 'Profil',
  'schema.journal.table': 'Tablo',
  'schema.localisations.id': 'ID',
  'schema.localisations.libelle': 'Etiket',
  'schema.localisations.parent_id': 'Üst konum',
  'schema.localisations.type': 'Tür',
  'schema.mouvements_stock.article_id': 'Malzeme',
  'schema.mouvements_stock.commentaire': 'Yorum',
  'schema.mouvements_stock.date': 'Tarih ve saat',
  'schema.mouvements_stock.id': 'ID',
  'schema.mouvements_stock.ot_id': 'İş emri',
  'schema.mouvements_stock.quantite': 'Miktar',
  'schema.mouvements_stock.type': 'Tür',
  'schema.mouvements_stock.utilisateur': 'Kullanıcı',
  'schema.ordres_travail.anomalie_constatee': 'Tespit edilen arıza',
  'schema.ordres_travail.arret_production': 'Üretim durması',
  'schema.ordres_travail.astuce': 'Bir sonraki sefer için ipucu',
  'schema.ordres_travail.cause_code': 'Neden kodu',
  'schema.ordres_travail.compte_rendu': 'Müdahale raporu',
  'schema.ordres_travail.consignes': 'Talimatlar',
  'schema.ordres_travail.cout_soustraitance': 'Taşeron maliyeti',
  'schema.ordres_travail.date_cloture_admin': 'İdari kapatma tarihi',
  'schema.ordres_travail.date_cloture_tech': 'Teknik kapatma tarihi',
  'schema.ordres_travail.date_creation': 'Oluşturma tarihi',
  'schema.ordres_travail.date_debut': 'Başlangıç tarihi',
  'schema.ordres_travail.date_fin': 'Bitiş tarihi',
  'schema.ordres_travail.date_prevue': 'Planlanan tarih',
  'schema.ordres_travail.di_id': 'İş talebi',
  'schema.ordres_travail.duree_arret_h': 'Duruş süresi (saat)',
  'schema.ordres_travail.equipement_id': 'Ekipman',
  'schema.ordres_travail.gamme_id': 'Önleyici bakım planı',
  'schema.ordres_travail.id': 'ID',
  'schema.ordres_travail.motif_annulation': 'İptal gerekçesi',
  'schema.ordres_travail.motif_attente': 'Bekleme gerekçesi',
  'schema.ordres_travail.origine': 'Kaynak',
  'schema.ordres_travail.ot_lie_id': 'Bağlantılı iş emri',
  'schema.ordres_travail.priorite': 'Öncelik',
  'schema.ordres_travail.remede_code': 'Çözüm kodu',
  'schema.ordres_travail.remise_service': 'Güvenli şekilde hizmete alındı',
  'schema.ordres_travail.statut': 'Durum',
  'schema.ordres_travail.symptome_code': 'Belirti kodu',
  'schema.ordres_travail.technicien_id': 'Teknisyen',
  'schema.ordres_travail.temps_prevu_h': 'Planlanan süre (saat)',
  'schema.ordres_travail.titre': 'Başlık',
  'schema.ordres_travail.travail_a_faire': 'Yapılacak iş',
  'schema.ordres_travail.type': 'Tür',
  'schema.ot_operations.fait': 'Yapıldı',
  'schema.ot_operations.id': 'ID',
  'schema.ot_operations.operation': 'Görev',
  'schema.ot_operations.ordre': 'Sıra',
  'schema.ot_operations.ot_id': 'İş emri',
  'schema.ot_operations.valeur_attendue': 'Beklenen değer',
  'schema.ot_operations.valeur_mesuree': 'Ölçülen değer',
  'schema.ot_pieces.article_id': 'Malzeme',
  'schema.ot_pieces.id': 'ID',
  'schema.ot_pieces.ot_id': 'İş emri',
  'schema.ot_pieces.quantite_prevue': 'Planlanan miktar',
  'schema.ot_temps.date': 'Tarih',
  'schema.ot_temps.heures': 'Saat',
  'schema.ot_temps.id': 'ID',
  'schema.ot_temps.ot_id': 'İş emri',
  'schema.ot_temps.technicien_id': 'Teknisyen',
  'schema.parametres.cle': 'Anahtar',
  'schema.parametres.valeur': 'Değer',
  'schema.releves.compteur_id': 'Sayaç',
  'schema.releves.date': 'Tarih',
  'schema.releves.id': 'ID',
  'schema.releves.utilisateur': 'Kullanıcı',
  'schema.releves.valeur': 'Değer',
  'schema.tables.achats': 'Satın almalar',
  'schema.tables.article_equipement': 'Ekipmana göre malzemeler',
  'schema.tables.articles': 'Malzemeler (yedek parçalar)',
  'schema.tables.codes_defaillance': 'Arıza kodları',
  'schema.tables.compteurs': 'Sayaçlar',
  'schema.tables.controles_reglementaires': 'Yasal kontroller',
  'schema.tables.demandes': 'İş talepleri',
  'schema.tables.equipements': 'Ekipman',
  'schema.tables.fournisseurs': 'Tedarikçiler',
  'schema.tables.gamme_operations': 'Bakım planı görevleri',
  'schema.tables.gammes': 'Önleyici bakım planları',
  'schema.tables.habilitations': 'Yetkilendirmeler',
  'schema.tables.journal': 'Değişiklik günlüğü',
  'schema.tables.localisations': 'Konumlar',
  'schema.tables.mouvements_stock': 'Stok hareketleri',
  'schema.tables.ordres_travail': 'İş emirleri',
  'schema.tables.ot_operations': 'İş emri görevleri',
  'schema.tables.ot_pieces': 'İş emri için planlanan parçalar',
  'schema.tables.ot_temps': 'İş emrinde harcanan süreler',
  'schema.tables.parametres': 'Ayarlar',
  'schema.tables.releves': 'Sayaç okumaları',
  'schema.tables.techniciens': 'Teknisyenler',
  'schema.tables.wiki_journal': 'Wiki günlüğü',
  'schema.tables.wiki_pages': 'Wiki sayfaları',
  'schema.techniciens.actif': 'Aktif',
  'schema.techniciens.capacite_h_semaine': 'Kapasite (haftalık saat)',
  'schema.techniciens.id': 'ID',
  'schema.techniciens.metier': 'Uzmanlık',
  'schema.techniciens.nom': 'Soyadı',
  'schema.techniciens.prenom': 'Ad',
  'schema.techniciens.taux_horaire': 'Saat ücreti',
  'schema.wiki_journal.anterieure': 'Önceki müdahale',
  'schema.wiki_journal.changements': 'Değişiklikler',
  'schema.wiki_journal.contradictions': 'Çelişkiler',
  'schema.wiki_journal.cree_le': 'Oluşturulma',
  'schema.wiki_journal.date_intervention': 'Müdahale tarihi',
  'schema.wiki_journal.decide_le': 'Karar tarihi',
  'schema.wiki_journal.decide_par': 'Karar veren',
  'schema.wiki_journal.essais': 'Denemeler',
  'schema.wiki_journal.id': 'ID',
  'schema.wiki_journal.modele': 'Model',
  'schema.wiki_journal.motif': 'Gerekçe',
  'schema.wiki_journal.nature': 'Tür',
  'schema.wiki_journal.ordre': 'İşlem sırası',
  'schema.wiki_journal.ot_id': 'İş emri',
  'schema.wiki_journal.pages': 'İlgili sayfalar',
  'schema.wiki_journal.raisons': 'Red nedenleri',
  'schema.wiki_journal.statut': 'Durum',
  'schema.wiki_journal.traite_le': 'İşlenme',
  'schema.wiki_pages.article_id': 'Malzeme',
  'schema.wiki_pages.cause_code': 'Neden kodu',
  'schema.wiki_pages.cle': 'Anahtar (karşılaştırılabilir başlık)',
  'schema.wiki_pages.cree_le': 'Oluşturulma',
  'schema.wiki_pages.derniere_entree': 'Uygulanan son kayıt',
  'schema.wiki_pages.equipement_id': 'Ekipman',
  'schema.wiki_pages.id': 'ID',
  'schema.wiki_pages.liens': 'Bağlantılı sayfalar',
  'schema.wiki_pages.modele': 'Model',
  'schema.wiki_pages.modifie_le': 'Değiştirilme',
  'schema.wiki_pages.origine': 'Kaynak',
  'schema.wiki_pages.ot_cites': 'Anılan iş emirleri',
  'schema.wiki_pages.rattache_a': 'Bağlı olduğu sayfa',
  'schema.wiki_pages.statut': 'Durum',
  'schema.wiki_pages.texte': 'Metin',
  'schema.wiki_pages.titre': 'Başlık',
  'schema.wiki_pages.type': 'Tür',
  'schema.wiki_pages.valide_le': 'Onaylanma',
  'schema.wiki_pages.valide_par': 'Onaylayan',
  'schema.wiki_pages.version': 'Sürüm',
});
// ==== fin schema ====

// ==== section valeurs ====
I18n.ajouter('tr', {
  'valeurs.achats.statut.commandée': 'sipariş verildi',
  'valeurs.achats.statut.demandée': 'talep edildi',
  'valeurs.achats.statut.reçue': 'teslim alındı',
  'valeurs.codes_defaillance.famille.cause': 'neden',
  'valeurs.codes_defaillance.famille.remède': 'çözüm',
  'valeurs.codes_defaillance.famille.symptôme': 'belirti',
  'valeurs.demandes.impact.arrêt': 'durma',
  'valeurs.demandes.impact.dégradé': 'düşük performans',
  'valeurs.demandes.impact.gêne': 'aksama',
  'valeurs.demandes.impact.sécurité': 'güvenlik',
  'valeurs.demandes.statut.Acceptée': 'Kabul edildi',
  'valeurs.demandes.statut.Différée': 'Ertelendi',
  'valeurs.demandes.statut.Nouvelle': 'Yeni',
  'valeurs.demandes.statut.Refusée': 'Reddedildi',
  'valeurs.demandes.statut.Regroupée': 'Birleştirildi',
  'valeurs.equipements.criticite.A': 'A',
  'valeurs.equipements.criticite.B': 'B',
  'valeurs.equipements.criticite.C': 'C',
  'valeurs.equipements.statut.arrêt': 'durdu',
  'valeurs.equipements.statut.en service': 'serviste',
  'valeurs.equipements.statut.rebut': 'hurdaya çıkarıldı',
  'valeurs.gammes.declencheur.compteur': 'sayaç',
  'valeurs.gammes.declencheur.date': 'tarih',
  'valeurs.gammes.declencheur.seuil': 'eşik',
  'valeurs.localisations.type.atelier': 'atölye',
  'valeurs.localisations.type.ligne': 'hat',
  'valeurs.localisations.type.site': 'tesis',
  'valeurs.mouvements_stock.type.entrée': 'giriş',
  'valeurs.mouvements_stock.type.inventaire': 'sayım',
  'valeurs.mouvements_stock.type.retour': 'iade',
  'valeurs.mouvements_stock.type.sortie': 'çıkış',
  'valeurs.ordres_travail.origine.DI': 'Talep',
  'valeurs.ordres_travail.origine.manuel': 'manuel',
  'valeurs.ordres_travail.origine.préventif': 'önleyici',
  'valeurs.ordres_travail.origine.urgence': 'acil',
  'valeurs.ordres_travail.priorite.P1': 'P1',
  'valeurs.ordres_travail.priorite.P2': 'P2',
  'valeurs.ordres_travail.priorite.P3': 'P3',
  'valeurs.ordres_travail.priorite.P4': 'P4',
  'valeurs.ordres_travail.statut.Annulé': 'İptal edildi',
  'valeurs.ordres_travail.statut.Clôturé administrativement': 'İdari olarak kapatıldı',
  'valeurs.ordres_travail.statut.Clôturé techniquement': 'Teknik olarak kapatıldı',
  'valeurs.ordres_travail.statut.Créé': 'Oluşturuldu',
  'valeurs.ordres_travail.statut.En attente': 'Beklemede',
  'valeurs.ordres_travail.statut.En cours': 'Devam ediyor',
  'valeurs.ordres_travail.statut.Planifié': 'Planlandı',
  'valeurs.ordres_travail.statut.Préparé': 'Hazırlandı',
  'valeurs.ordres_travail.type.amélioration': 'iyileştirme',
  'valeurs.ordres_travail.type.correctif différé': 'ertelenmiş düzeltici',
  'valeurs.ordres_travail.type.correctif immédiat': 'anında düzeltici',
  'valeurs.ordres_travail.type.préventif conditionnel': 'duruma bağlı önleyici',
  'valeurs.ordres_travail.type.préventif systématique': 'takvime bağlı önleyici',
  'valeurs.ordres_travail.type.réglementaire': 'yasal',
  'valeurs.wiki_journal.nature.décision': 'karar',
  'valeurs.wiki_journal.nature.ingestion': 'işleme alma',
  'valeurs.wiki_journal.nature.manuel': 'manuel',
  'valeurs.wiki_journal.statut.appliquée': 'uygulandı',
  'valeurs.wiki_journal.statut.en file': 'sırada',
  'valeurs.wiki_journal.statut.refusée': 'reddedildi',
  'valeurs.wiki_journal.statut.rejetée': 'elendi',
  'valeurs.wiki_journal.statut.rien à ajouter': 'eklenecek bir şey yok',
  'valeurs.wiki_journal.statut.validée': 'onaylandı',
  'valeurs.wiki_journal.statut.à refaire': 'yeniden yapılacak',
  'valeurs.wiki_journal.statut.à valider': 'onaylanacak',
  'valeurs.wiki_pages.origine.IA': 'YZ',
  'valeurs.wiki_pages.origine.IA et manuel': 'YZ ve manuel',
  'valeurs.wiki_pages.origine.manuel': 'manuel',
  'valeurs.wiki_pages.statut.active': 'aktif',
  'valeurs.wiki_pages.statut.archivée': 'arşivlendi',
  'valeurs.wiki_pages.type.composant': 'bileşen',
  'valeurs.wiki_pages.type.mode': 'arıza modu',
  'valeurs.wiki_pages.type.savoir-faire': 'know-how',
  'valeurs.wiki_pages.type.équipement': 'ekipman',
});
// ==== fin valeurs ====

// ==== section socle ====
I18n.ajouter('tr', {
  'socle.analyser.ligne_contient_plus_valeurs': '{reperage}: bu satırda başlıktaki sütun sayısından fazla değer var; “{valeurIgnoree}” değeri ({colonneIgnoree} sütunu) yok sayıldı.',
  'socle.analyser.ligne_structure_fichier_abimee': '{descriptionLibelle}, {fichier} dosyasının {numero}. satırı: dosya yapısı hasarlı ({erreurMessage}), örneğin kapatılmamış bir tırnak işareti. Bu satırdaki ve sonraki satırlardaki değerler kaymış olabilir.',
  'socle.analyser.pas_utf_8_sans': '{descriptionLibelle}: {fichier} UTF-8 biçiminde değil (büyük olasılıkla Excel tarafından “CSV (noktalı virgül ayraçlı)” biçiminde kaydedilmiş); Windows-1252 olarak okundu. Tablo bir sonraki değiştirildiğinde UTF-8 olarak yeniden yazılacak.',
  'socle.analyser.reperage_champ_libelle_contient_lu_valeur': '{reperage}: “{champLibelle}” alanında “{luValeur}” var, {explication}.',
  'socle.app.gmao': 'BYBS',
  'socle.app.menu': 'Menü',
  'socle.app.propos': 'Hakkında',
  'socle.appliquer_repli.deplier_menu': 'Menüyü genişlet',
  'socle.appliquer_repli.replier_menu': 'Menüyü daralt',
  'socle.associer_colonnes.colonne_apparait_deux_fois': '{descriptionLibelle}: “{nomColonne}” sütunu {fichier} dosyasında iki kez geçiyor; ikincisi “{nomConserve}” adıyla ayrı olarak saklanır ve Prévo tarafından kullanılmaz.',
  'socle.associer_colonnes.colonne_fait_pas_partie': '{descriptionLibelle}: {fichier} dosyasındaki “{nomConserve}” sütunu Prévo\'ya ait değil; olduğu gibi saklanır (dosyanın sonuna yeniden yazılır).',
  'socle.associer_colonnes.colonne_numero': '{numero}. sütun',
  'socle.badge_priorite.priorite_code': 'Öncelik {code}',
  'socle.badge_priorite.priorite_inconnue': 'Öncelik bilinmiyor',
  'socle.bandeau_changement.donnees_ont_change_autre': 'Veriler başka bir iş istasyonunda değişti',
  'socle.bandeau_demo.demo_rien_enregistre': 'Demo — hiçbir şey kaydedilmez',
  'socle.bandeau_fichiers_abimes.fichier_abime': 'Hasarlı dosya',
  'socle.bandeau_fichiers_abimes.fichiers_abimes': 'Hasarlı dosyalar',
  'socle.bandeau_fichiers_abimes.prevenez_responsable': '<b>{titre}: sorumluyu bilgilendirin.</b> {suite}',
  'socle.bandeau_fichiers_abimes.tant_ils_sont_pas': 'Onarılana kadar Prévo, bu dosyaları etkileyen kayıtları hiçbir şey kaybetmeden reddeder.',
  'socle.bandeau_fichiers_abimes.tant_pas_repare_prevo': 'Onarılana kadar Prévo, bu dosyayı etkileyen kayıtları hiçbir şey kaybetmeden reddeder.',
  'socle.bandeau_fichiers_abimes.tete_coupe_guillemet_non': '<b>{titre}: {fichiers}.</b> Başlık kesilmiş, tırnak işareti kapatılmamış ya da başlığın ötesinde değerler var: Prévo hiçbir şey kaybetmemek için artık bu dosyayı kaydetmiyor. Dosyayı düzeltin, bir yedeği geri yükleyin veya bir ZIP içe aktarın; ayrıntılar Ayarlar › Veri tabanı kontrolü bölümünde.',
  'socle.bandeau_fichiers_laisses.fichier_abime_laisse_tel': 'Hasarlı dosya olduğu gibi bırakıldı',
  'socle.bandeau_fichiers_laisses.fichiers_abimes_laisses_tels': 'Hasarlı dosyalar olduğu gibi bırakıldı',
  'socle.bandeau_fichiers_laisses.tete_illisible_lignes_reecriture': '<b>{titre}: {fichiers}.</b> Başlık okunamıyor ya da yeniden yazma satır kaybettirir: Prévo, dosyayı {version} biçimine geçirmek için yeniden yazmıyor. Dosyayı düzeltin veya bir yedeği geri yükleyin; ayrıntılar Ayarlar › Veri tabanı kontrolü bölümünde.',
  'socle.bandeau_format_en_attente.fichiers_donnees_sont_pas': '<b>Veri dosyaları henüz {courant} biçiminde değil</b> ({depart} biçimi bulundu). Dosyaları, bir yedekten sonra, başlangıçta Prévo sunucusu günceller; bu tarayıcı onlara dokunmaz. Bu ileti ekranda kalırsa Excel\'i (ve bir veri dosyasını açmış tüm programları) kapatın, sonra Prévo\'yu yeniden başlatın. O zamana kadar vadesi gelen önleyici iş emirleri otomatik oluşturulmaz.',
  'socle.btn_base_demo.atelier_fictif_complet_pourrez': 'Düzenleyebileceğiniz veya yerine başkasını koyabileceğiniz tam bir örnek atölye',
  'socle.btn_base_demo.partir_donnees_demo': 'Demo verileriyle başla',
  'socle.btn_base_vide.23_fichiers_csv_seuls': 'Yalnızca sütun başlıklarını içeren 23 CSV dosyası',
  'socle.btn_base_vide.creer_base_vide': 'Boş veri tabanı oluştur',
  'socle.btn_demo.atelier_fictif_rien_enregistre': 'Örnek atölye, hiçbir şey kaydedilmez',
  'socle.btn_demo.essayer_donnees_demo': 'Demo verileriyle dene',
  'socle.btn_dossier.choisir_dossier_donnees': 'Veri klasörünü seç',
  'socle.btn_dossier.fichiers_csv_restent_pc': 'CSV dosyaları bu PC\'de kalır (Chrome veya Edge)',
  'socle.btn_explications.explications': 'Açıklamalar',
  'socle.btn_explications.revoir_explication_ecran': 'Bu ekranın açıklamasını yeniden gör',
  'socle.btn_explications_mobile.explications_ecran': 'Bu ekranın açıklamaları',
  'socle.btn_export_demo.exporter_zip': 'ZIP olarak dışa aktar',
  'socle.btn_replier.replier_menu': 'Menüyü daralt',
  'socle.btn_reprendre.reprendre_dossier_precedent': 'Önceki klasörle devam et',
  'socle.btn_telecharger.gratuit_libre_installez_travailler': 'Ücretsiz ve özgür: kendi verilerinizle çalışmak için kurun.',
  'socle.btn_telecharger.telecharger_prevo': 'Prévo\'yu indir',
  'socle.changer_profil.profil_libelle_affiche': 'Profil: {libelleAffiche}.',
  'socle.chargement.chargement': 'Yükleniyor…',
  'socle.charger_echarts.bibliotheque_graphiques_js_lib': 'Grafik kitaplığı (js/lib/echarts.min.js) yüklenemedi.',
  'socle.charger_image.image_peut_pas_etre': 'Bu görsel okunamıyor (biçim desteklenmiyor olabilir mi?).',
  'socle.charger_script_demo.jeu_demo_js_demo': 'Demo veri seti (js/demo-donnees.js) yüklenemedi.',
  'socle.charger_sheet_js.bibliotheque_lecture_fichiers_excel': 'Excel dosyalarını okuma kitaplığı (js/lib/xlsx.full.min.js) yüklenemedi.',
  'socle.choisir.choix_dossier': 'klasör seçimi',
  'socle.confirmer.confirmation': 'Onay',
  'socle.confirmer.confirmer': 'Onayla',
  'socle.connexion_avec_compte.ai_compte': 'Hesabım var',
  'socle.connexion_changer.enregistrer_continuer': 'Kaydet ve devam et',
  'socle.connexion_enrolement.entrez_nom': 'Adınızı girin',
  'socle.connexion_enrolement.nom_inscrit_demandes_appareil': 'Adınız taleplerinize yazılır; bu cihaz şifresiz tanınmaya devam eder.',
  'socle.connexion_formulaire.forme_prenom_nom_donne': 'ad.soyad biçiminde, sorumlu tarafından verilir.',
  'socle.connexion_formulaire.identifiant': 'Kullanıcı adı',
  'socle.connexion_formulaire.mot_passe': 'Şifre',
  'socle.connexion_formulaire.rester_connecte_appareil': 'Bu cihazda oturumu açık tut',
  'socle.connexion_mdp_deconnexion.deconnecter': 'Oturumu kapat',
  'socle.connexion_mot_de_passe_panneau.12_caracteres_moins_256': 'En az 12, en çok 256 karakter, bileşim kuralı yok: birkaç sözcükten oluşan bir parola cümlesi önerilir.',
  'socle.connexion_mot_de_passe_panneau.confirmation': 'Onay',
  'socle.connexion_mot_de_passe_panneau.mot_passe_actuel_provisoire': 'Mevcut şifre (geçici)',
  'socle.connexion_mot_de_passe_panneau.nouveau_mot_passe': 'Yeni şifre',
  'socle.connexion_sous_titre.chaque_personne_compte_serveur': 'Her kişinin kendi hesabı vardır; sunucu yetkileri denetler.',
  'socle.connexion_titre.connexion': 'Oturum açma',
  'socle.connexion_valider.connecter': 'Oturum aç',
  'socle.constructor.action_refusee': 'İşlem reddedildi.',
  'socle.constructor.donnees_viennent_version_plus': 'Bu veriler Prévo\'nun daha yeni bir sürümünden geliyor (dosya biçimi {format}; bu sürüm {version} biçimine kadar okur): salt okunur açıldı ve hiçbir şey kaydedilmez. Bunları Prévo\'nun son sürümüyle açın.',
  'socle.constructor.fichier_abime_tete_coupe': '{fichier} dosyası hasarlı (başlık kesilmiş, tırnak işareti kapatılmamış ya da başlığın ötesinde değerler var): Prévo hiçbir şey kaybetmemek için artık bu dosyayı kaydetmiyor. Dosyayı düzeltin, bir yedeği geri yükleyin veya bir ZIP içe aktarın (Ayarlar); ayrıntılar Ayarlar › Veri tabanı kontrolü bölümünde.',
  'socle.constructor.fichier_ete_modifie_meme': 'Dosya, başka bir iş istasyonunda aynı anda değiştirildi.',
  'socle.constructor.lecture_ecriture_fichier_impossible': 'Dosya okunamadı veya yazılamadı.',
  'socle.construire_menus.plus': 'Daha fazla',
  'socle.controler_coherence.demande_acceptee_mais_aucun': '{id} talebi: “Kabul edildi” durumunda ama ona bağlı hiçbir iş emri yok. Yeniden açın veya iş emrine bağlayın.',
  'socle.controler_coherence.demande_acceptee_mais_ordre': '{id} talebi: “Kabul edildi” durumunda ama “{ot_id}” iş emri yok.',
  'socle.controler_coherence.ordre_travail_vient_demande': '{id} iş emri: “{statut}” durumundaki “{di_id}” talebinden geliyor (ne kabul edildi ne birleştirildi). Talebi kabul edin veya birleştirin, ya da iş emrini iptal edin.',
  'socle.controler_coherence.sans_identifiant': '(ID yok)',
  'socle.controler_identifiants.identifiant_apparait_plusieurs_fois': '{descriptionLibelle}: “{cle}” ID\'si {fichier} dosyasında birden çok kez geçiyor (veri satırı no. {numero}). Prévo yalnızca ilk satırı bulur: diğerlerine benzersiz bir ID verin.',
  'socle.controler_identifiants.pas_identifiant_colonne_vide': '{descriptionLibelle}: {fichier} dosyasındaki {reperageLigne} için ID yok (“{cle}” sütunu boş). Doldurun veya satırı dosyadan silin.',
  'socle.controler_references.existe_mais_lieu': '{descriptionCibleLibelle} içinde var ama {filtre} yerine {familleTrouvee} ile',
  'socle.controler_references.existe_pas': '{descriptionCibleLibelle} içinde yok ({filtre})',
  'socle.controler_references.existe_pas_sans_filtre': '{descriptionCibleLibelle} içinde yok',
  'socle.controler_references.reperage_champ_libelle_vaut_valeur': '{reperage}: “{champLibelle}” alanı “{valeur}” değerinde, bu değer {explication}.',
  'socle.controler_wiki.changements_illisibles': '(okunamayan değişiklikler)',
  'socle.controler_wiki.cite_aucun_ot': 'hiçbir iş emrini anmıyor.',
  'socle.controler_wiki.cite_ot_existe_pas': 'mevcut olmayan “{ot}” iş emrini anıyor.',
  'socle.controler_wiki.entree_journal_wiki_contradiction': { one: 'Wiki günlüğünün {entreeId} kaydı: “{page}” sayfasında {n} günden uzun süredir açık bir çelişki var.', other: 'Wiki günlüğünün {entreeId} kaydı: “{page}” sayfasında {n} günden uzun süredir açık bir çelişki var.' },
  'socle.controler_wiki.entree_journal_wiki_validee': 'Wiki günlüğünün {entreeId} kaydı: “onaylandı” durumunda ama değişiklikleri sayfalarda yok ({pages}).',
  'socle.controler_wiki.lien_vers_page_inexistante': 'mevcut olmayan veya arşivlenmiş bir sayfaya bağlantı (“{lien}”).',
  'socle.controler_wiki.meme_titre_page_deux': '{page} sayfasıyla aynı başlık (aynı anahtarlı iki aktif sayfa).',
  'socle.controler_wiki.page_wiki': 'Wiki sayfası {id} (“{pageTitre}”): {message}',
  'socle.controler_wiki.rattachee_page_archivee': 'arşivlenmiş “{mereTitre}” sayfasına ({mereId}) bağlı.',
  'socle.controler_wiki.sous_page_page_archivee': 'arşivlenmiş “{mereTitre}” sayfasının ({mereId}) alt sayfası.',
  'socle.controler_wiki.type_page_retire_panne': 'kaldırılmış sayfa türü (“{pageType}”: arıza, Prévo tarafından hesaplanan bir sayfadır); arşivleyin.',
  'socle.creer.ajout_fichier': 'dosyaya ekleme',
  'socle.creer.aucune_table_restauree': 'hiçbiri',
  'socle.creer.contenu_ajouter_doit_commencer': 'Eklenecek içerik başlık satırıyla başlamalıdır.',
  'socle.creer.contenu_ajouter_doit_etre': 'Eklenecek içerik UTF-8 olarak kodlanmış olmalıdır.',
  'socle.creer.demo_rien_enregistre': 'Demo — hiçbir şey kaydedilmez',
  'socle.creer.document_existe_deja': '{nom} belgesi zaten var.',
  'socle.creer.document_porte_deja_nom': 'Bu adı taşıyan bir belge zaten var.',
  'socle.creer.dossier_name': '“{name}” klasörü',
  'socle.creer.enregistrement_document': 'belgeyi kaydetme',
  'socle.creer.enregistrement_table': 'tabloyu kaydetme',
  'socle.creer.fichier_csv_ete_modifie': '{nomTable}.csv dosyası başka bir iş istasyonu tarafından değiştirildi.',
  'socle.creer.fichier_csv_existe_deja': '{nomTable}.csv dosyası zaten var.',
  'socle.creer.fichier_csv_existe_plus': '{nomTable}.csv dosyası artık yok.',
  'socle.creer.fichier_csv_pas_utf': '{nomTable}.csv dosyası UTF-8 biçiminde değil (Excel yeniden mi kaydetti?).',
  'socle.creer.fichier_vient_etre_modifie': '{nomFichier} dosyası az önce başka bir iş istasyonu tarafından değiştirildi.',
  'socle.creer.indisponible_mode_demo_rien': 'Demo modunda kullanılamaz: hiçbir şey kaydedilmez.',
  'socle.creer.lecture_document': 'belgeyi okuma',
  'socle.creer.lecture_nom_fichiers_abimes': '{fichier} okuma',
  'socle.creer.lecture_table': 'tabloyu okuma',
  'socle.creer.lecture_versions': 'sürümleri okuma',
  'socle.creer.liste_sauvegardes': 'yedeklerin listesi',
  'socle.creer.mise_jour': '{fichier} güncelleme',
  'socle.creer.nom_document_invalide': 'Geçersiz belge adı: “{nom}”.',
  'socle.creer.poste_inconnu': 'Bilinmeyen iş istasyonu',
  'socle.creer.restauration': 'geri yükleme',
  'socle.creer.restauration_interrompue_table_tables': '{interrompueMessage} Geri yükleme {table} tablosunda kesildi; zaten geri yüklenen tablolar: {dejaRestaurees}. Geri yüklemeden önceki durum {copieSecurite} yedeğinde.',
  'socle.creer.sauvegarde': 'yedek',
  'socle.creer.sauvegarde_avant_mise_jour': 'Prévo güncellemesi öncesi yedek',
  'socle.creer.sauvegarde_incomplete_copie_interrompue': '{nom} yedeği eksik (kopyalama kesildi veya sürüyor): başka birini seçin.',
  'socle.creer.sauvegarde_introuvable': 'Yedek bulunamadı: {nom}.',
  'socle.creer.serveur_host': 'Sunucu {host}',
  'socle.creer.table_absente_sauvegarde': '{table} tablosu bu yedekte yok.',
  'socle.creer.tables_doit_etre_liste': '“tables” bir tablo adları listesi olmalıdır.',
  'socle.creer.tete_csv_different': '{nomTable}.csv dosyasının başlığı farklı.',
  'socle.creer.version_application_inconnue_rien': 'Uygulama sürümü bilinmiyor: hiçbir şey yedeklenmez.',
  'socle.decaler_dates.stockage_demo_decaler_dates_dates_attendues': 'StockageDemo.decalerDates: tarihler YYYY-AA-GG biçiminde beklenir.',
  'socle.deconnecter.appareil_enrole_sans_mot': 'Bu cihaz şifresiz eşleştirilmiş: yalnızca sorumlu yetkisini kaldırabilir (Ekip › Erişim).',
  'socle.definir_titre.prevo': 'Prévo',
  'socle.definir_titre.prevo_gmao': 'Prévo — BYBS',
  'socle.definir_titre.texte_prevo': '{texte} — Prévo',
  'socle.demander_base_vide.aucun_fichier_trouve': { one: 'Prévo dosyası bulunamadı ({stockage}). Neyle başlamak istersiniz?', other: 'Prévo\'nun {n} dosyasının hiçbiri bulunamadı ({stockage}). Neyle başlamak istersiniz?' },
  'socle.demander_motif.motif': 'Gerekçe',
  'socle.demander_motif.motif_obligatoire': 'Gerekçe zorunludur.',
  'socle.demander_motif.valider': 'Doğrula',
  'socle.demarrage.navigateur_sait_pas_ouvrir': '<b>Bu tarayıcı klasör açamıyor.</b> Dosyalarınızla çalışmak için bir bilgisayarda Chrome veya Edge kullanın. Bu arada demo burada çalışır.',
  'socle.depuis_fichiers.impossible_lire_fichier': '{name} dosyası okunamıyor.',
  'socle.description_table.donnees_csv_table_inconnue': 'Donnees.csv: bilinmeyen tablo “{nomTable}”.',
  'socle.ecran.app_ecran_ecran_deja': 'App.ecran: “{definitionId}” ekranı zaten kayıtlı.',
  'socle.ecran.app_ecran_id_route': 'App.ecran: id, route (RegExp) ve afficher(conteneur, parametres) zorunludur.',
  'socle.ecran_base_vide.aucune_donnee_instant': 'Henüz veri yok',
  'socle.ecran_base_vide.langue_prevo': 'Prévo dili',
  'socle.ecran_base_vide.langue_prevo_aide': 'Bu tarayıcıya göre önerildi. Prévo, kendi dilini seçmemiş iş istasyonlarında bu dille açılır; verilere yazdığı metinlerin dili de budur. Sonradan Ayarlar\'dan değiştirilebilir.',
  'socle.ecran_chargement.chargement_prevo': 'Prévo yükleniyor…',
  'socle.ecran_demarrage.developpe_claude_anthropic_demande': 'Nicolas Briand\'ın isteğiyle Claude (Anthropic) tarafından geliştirildi — SELECTIS',
  'socle.ecran_demarrage.gmao_libre_atelier_demandes': 'Atölye için özgür BYBS: talepler, iş emirleri, ekipman envanteri.',
  'socle.ecran_demarrage.prevo': 'Prévo',
  'socle.ecran_installation.installer_prevo': 'Prévo\'yu kur',
  'socle.ecran_profil.inscrit_journal_chaque_modification': 'Her değişiklikle birlikte günlüğe yazılır.',
  'socle.ecran_profil.nom_poste': 'Bu iş istasyonunun adı',
  'socle.ecran_profil.profil_adapte_ecrans_pas': 'Profil ekranları uyarlar; bir güvenlik önlemi değildir.',
  'socle.ecran_profil.utilise_poste': 'Bu iş istasyonunu kim kullanıyor?',
  'socle.en_octets.contenu_fichier_illisible_texte': 'Dosya içeriği okunamıyor (metin veya bayt bekleniyordu).',
  'socle.en_octets.donnees_csv_octets_attendus': 'Donnees.csv: bayt bekleniyordu (Uint8Array veya ArrayBuffer).',
  'socle.en_octets.formats_manifeste_octets_attendus': 'Formats.manifeste: bayt bekleniyordu (Uint8Array veya ArrayBuffer).',
  'socle.en_octets.stockage_dossier_octets_attendus_uint': 'StockageDossier: bayt bekleniyordu (Uint8Array veya ArrayBuffer).',
  'socle.erreur_depuis_reponse.serveur_refuse_demande_code': 'Sunucu isteği reddetti (kod {status}).',
  'socle.erreur_depuis_reponse.table': 'bu tablonun',
  'socle.etat_poste.changer': 'değiştir',
  'socle.etat_poste.changer_profil': 'Profili değiştir',
  'socle.exiger_formats.donnees_registre_formats_js': 'Donnees: biçim kaydı (js/formats.js), js/donnees.js dosyasından önce yüklenmelidir.',
  'socle.explication_valeur_illisible.fait_pas_partie_valeurs': 'olası değerler arasında değil ({valeurs})',
  'socle.explication_valeur_illisible.illisible': 'okunamıyor',
  'socle.explication_valeur_illisible.pas_date_heure_valide': 'geçerli bir tarih ve saat değil (kabul edilen biçimler: 2024-03-15 08:30 veya 15/03/2024 08:30)',
  'socle.explication_valeur_illisible.pas_date_valide_formats': 'geçerli bir tarih değil (kabul edilen biçimler: 2024-03-15 veya 15/03/2024)',
  'socle.explication_valeur_illisible.pas_nombre_entier': 'tam sayı değil',
  'socle.explication_valeur_illisible.pas_nombre_exemples_acceptes': 'sayı değil (kabul edilen örnekler: 7,5 veya 7.5)',
  'socle.explication_valeur_illisible.pas_reconnu_comme_oui': 'evet veya hayır olarak tanınmadı (kabul edilen değerler: 1, 0, oui, non, vrai, faux, x)',
  'socle.fichier_abime_depuis.depuis_le': { one: '{fichier}, {date} tarihinden beri ({n} gün)', other: '{fichier}, {date} tarihinden beri ({n} gün)' },
  'socle.fichier_abime_depuis.repere_aujourd_hui': '{fichier}, bugün fark edildi',
  'socle.html.ui_html_utilise_comme': 'UI.html bir şablon olarak kullanılır: UI.html`…`',
  'socle.installation_contenu.lecture_etat_installation': 'Kurulum durumu okunuyor…',
  'socle.installation_premiere_ligne.tant_installation_pas_terminee': 'Kurulum bitene kadar Prévo yalnızca bu PC\'den erişilebilir.',
  'socle.installation_quitter.ouvrir_prevo_sans_terminer': 'Kurulumu bitirmeden Prévo\'yu aç (yalnızca bu PC\'den erişilebilir kalır)',
  'socle.lecture_seule.lecture_seule_donnees_viennent': '<b>Salt okunur: bu veriler Prévo\'nun daha yeni bir sürümünden geliyor</b> (dosya biçimi {format}; bu sürüm {version} biçimine kadar okur). Bunlara bakabilirsiniz ama hiçbir şey kaydedilmez. Bunları Prévo\'nun son sürümüyle açın.',
  'socle.libelle_journal.demandeur_p_nom': 'Talep eden {nom}',
  'socle.libelle_journal.technicien_technicien_id': 'Teknisyen {technicienId}',
  'socle.libelle_type.demandeur': 'Talep eden',
  'socle.libelle_type.responsable': 'Sorumlu',
  'socle.libelle_type.technicien': 'Teknisyen',
  'socle.lire_cellule.valeur_conservee_telle_quelle': '{explicationValeurIllisible}. Değer olduğu gibi saklandı: düzeltilmeli',
  'socle.lire_cellule.valeur_probablement_abimee_excel': 'değer büyük olasılıkla Excel tarafından bozulmuş (uzun bir sayı bilimsel gösterime çevrilmiş). Özgün değeri bulun ve başına bir kesme işareti koyarak girin, örneğin \'123456789012345',
  'socle.lire_cellule.valeur_probablement_abimee_excel_formule': 'değer büyük olasılıkla Excel tarafından bozulmuş (“=”, “+” veya “-” ile başlayan metin formül sanılmış). Özgün metni bulun ve başına bir kesme işareti koyarak girin',
  'socle.liste_deroulante.choisir': '— Seçin —',
  'socle.liste_deroulante.valeur_inconnue': '{valeurTexte} (bilinmeyen değer)',
  'socle.menu.navigation_principale': 'Ana gezinme',
  'socle.message_conflit_persistant.fichier_modifie_meme_temps': '{nomTable} dosyası başka bir iş istasyonunda aynı anda değiştiriliyor. Birazdan yeniden deneyin.',
  'socle.message_delai_depasse.serveur_prevo_met_trop': 'Prévo sunucusu çok geç yanıt veriyor. Ağı kontrol edip yeniden deneyin; kaydediyorsanız değişikliğin yapılıp yapılmadığını görmek için sayfayı yeniden yükleyin.',
  'socle.message_erreur.fichier_abime_prevenez_responsable': 'Hasarlı dosya: sorumluyu bilgilendirin. Hiçbir şey kaydedilmedi; girdiğiniz bilgiler formda duruyor.',
  'socle.message_erreur.fichier_abime_rien_ete': 'Hasarlı dosya: hiçbir şey kaybetmemek için hiçbir şey kaydedilmedi; girdiğiniz bilgiler formda duruyor. Günün yedeğini geri yükleyin (Ayarlar › Yedekler) veya bir ZIP içe aktarın; ayrıntılar Ayarlar › Veri tabanı kontrolü bölümünde.',
  'socle.message_erreur.fichier_abime_rien_ete_avec_fichier': 'Hasarlı dosya ({fichier}): hiçbir şey kaybetmemek için hiçbir şey kaydedilmedi; girdiğiniz bilgiler formda duruyor. Günün yedeğini geri yükleyin (Ayarlar › Yedekler) veya bir ZIP içe aktarın; ayrıntılar Ayarlar › Veri tabanı kontrolü bölümünde.',
  'socle.message_fichier_ouvert.fichier_dossier_donnees_ouvert': 'Veri klasöründeki bir dosya Excel\'de veya başka bir yazılımda açık: kapatın, sonra yeniden deneyin.',
  'socle.message_fichier_ouvert.fichier_ouvert_excel_autre': '“{nomFichier}” dosyası Excel\'de veya başka bir yazılımda açık: kapatın, sonra yeniden deneyin.',
  'socle.message_reponse_inattendue.reponse_inattendue_serveur_operation': 'Sunucudan beklenmeyen yanıt; işlem yapılmış olabilir, sayfayı yeniden yükleyin.',
  'socle.message_serveur_injoignable.serveur_prevo_repond_pas': 'Prévo sunucusu yanıt vermiyor. Sunucu penceresinin PC\'de açık olduğunu kontrol edin.',
  'socle.mettre_ajour_boutons_profil.appareil_enrole': 'Eşleştirilmiş cihaz: {libelleAffiche}',
  'socle.mettre_ajour_boutons_profil.changer_profil': 'Profili değiştir',
  'socle.mettre_ajour_boutons_profil.connecte_cliquer_deconnecter': 'Oturum açık: {libelleCompte}. Oturumu kapatmak için tıklayın.',
  'socle.mettre_ajour_boutons_profil.deconnecter': 'oturumu kapat',
  'socle.mettre_ajour_boutons_profil.deconnecter_bouton': 'Oturumu kapat',
  'socle.mettre_ajour_boutons_profil.profil_poste_cliquer_changer': 'Profil: {libelleAffiche} — “{poste}” iş istasyonu. Değiştirmek için tıklayın.',
  'socle.migrer.formats_migrer_format_cible': 'Formats.migrer: hedef biçim bilinmiyor ({vers}); bilinen biçimler: {premier} ila {version}.',
  'socle.migrer.formats_migrer_format_depart': 'Formats.migrer: başlangıç biçimi okunamıyor ({de}).',
  'socle.migrer_au_format_courant.sans_sauvegarde_demo': 'yedeksiz (demo)',
  'socle.migrer_au_format_courant.sauvegarde_avant_passage_format': '{courant} biçimine geçmeden önce yedek alınamadı: {messageSansPointFinal}; güncelleme bir sonraki açılışta yeniden denenecek.',
  'socle.migrer_au_format_courant.sauvegarde_faite_juste_avant': '{sauvegarde} yedeği hemen öncesinde alındı',
  'socle.note_donnees_demo.atelier_francais_interface_traduite': 'Demo verileri Fransız bir atölyeyi anlatır: yalnızca arayüz çevrilmiştir.',
  'socle.note_donnees_demo.nulle_part_elles_vivent': 'Hiçbir yerde: bu sayfada durur ve sayfayı kapattığınızda kaybolur. Kurulumunuzda bunlar PC\'nizdeki, Excel\'de okunabilen CSV dosyalarıdır.',
  'socle.nouvel_id.donnees_nouvel_id_table_pas': 'Donnees.nouvelId: “{nomTable}” tablosunun hesaplanan bir ID\'si yok.',
  'socle.ouvrir_fichiers_deposes.aucun_fichier_reconnu_fichiers': 'Tanınan dosya yok: dosyaların adı equipements.csv, demandes.csv, ordres_travail.csv… olmalıdır.',
  'socle.ouvrir_fichiers_deposes.fichiers_ignores_nom_inconnu': 'Yok sayılan dosyalar (bilinmeyen veya yinelenen ad): {fichiers}',
  'socle.ouvrir_plus.changer_profil': 'Profili değiştir ({libelleAffiche})',
  'socle.ouvrir_plus.deconnecter_libelle_compte': 'Oturumu kapat ({libelleCompte})',
  'socle.ouvrir_plus.exporter_zip': 'ZIP olarak dışa aktar',
  'socle.passer_au_format_courant.fichiers_ont_pas_pu': '<b>Dosyalar {version} biçimine geçemedi.</b> {message} O zamana kadar vadesi gelen önleyici iş emirleri otomatik oluşturulmaz.',
  'socle.poste_aleatoire.poste_suffixe': 'İstasyon-{suffixe}',
  'socle.probleme_colonne_absente.colonne_absente_sera_ajoutee': '{descriptionLibelle}: “{champNom}” ({champLibelle}) sütunu {fichier} dosyasında yok; {suite}. Tablo bir sonraki değiştirildiğinde eklenecek.',
  'socle.probleme_colonne_absente.colonne_ajoutee_version_format': '{descriptionLibelle}: “{champNom}” sütunu biçimin {depuisVersion} sürümüyle eklendi, bir sonraki kayıtta yazılacak.',
  'socle.probleme_colonne_absente.valeur_defaut_utilisee': '“{valeurParDefaut}” varsayılan değeri kullanılır',
  'socle.probleme_colonne_absente.valeur_laissee_vide': 'değer boş bırakılır',
  'socle.probleme_table_laissee.abime_structure_fichier_valeurs': '{fichier} hasarlı (dosya yapısı veya başlığın ötesinde değerler: diğer sorunlarına bakın) ve yeniden yazmak bir kısmını kaybettirir',
  'socle.probleme_table_laissee.ligne_tete_incomplete_illisible': '{fichier} dosyasının başlık satırı eksik veya okunamıyor (1. biçimin bazı sütunları yok)',
  'socle.probleme_table_laissee.prevo_reecrit_pas_fichier': '{descriptionLibelle}: {raison}; Prévo bu dosyayı {version} biçimine geçirmek için yeniden yazmaz, olduğu gibi bırakır. Dosyayı düzeltin veya bir yedeği geri yükleyin.',
  'socle.profil_demandeur.demandeur': 'Talep eden',
  'socle.profil_demandeur.signaler_probleme_suivre_mes': 'Sorun bildirin, taleplerimi izleyin',
  'socle.profil_panneau_demandeur.nom': 'Adınız',
  'socle.profil_panneau_demandeur.retour': 'Geri',
  'socle.profil_panneau_technicien.choisissez_nom': 'Adınızı seçin',
  'socle.profil_responsable.responsable': 'Sorumlu',
  'socle.profil_responsable.tout_suivi_demandes_ot': 'Tüm takip: talepler, iş emirleri, ekipman envanteri, ayarlar',
  'socle.profil_technicien.mes_ordres_travail_comptes': 'İş emirlerim, müdahale raporları',
  'socle.profil_technicien.technicien': 'Teknisyen',
  'socle.qr_svg.bibliotheque_qrcode_absente_js': 'qrcode kitaplığı yok (js/lib/qrcode.js).',
  'socle.qr_svg.qr_code': 'QR kod: {texte}',
  'socle.raison_erreur.fichier_abime_prevenez_responsable': 'hasarlı dosya: sorumluyu bilgilendirin',
  'socle.raison_erreur.fichier_abime_rien_ete': 'hasarlı dosya, içine hiçbir şey kaydedilmedi: günün yedeğini geri yükleyin veya bir ZIP içe aktarın; ayrıntılar Ayarlar › Veri tabanı kontrolü bölümünde',
  'socle.raison_erreur.fichier_abime_rien_ete_avec_fichier': 'hasarlı dosya ({fichier}), içine hiçbir şey kaydedilmedi: günün yedeğini geri yükleyin veya bir ZIP içe aktarın; ayrıntılar Ayarlar › Veri tabanı kontrolü bölümünde',
  'socle.redimensionner_photo.photo_pas_pu_etre': 'Fotoğraf dönüştürülemedi.',
  'socle.remplir_liste_techniciens.aucun_technicien_actif_techniciens': 'techniciens.csv dosyasında aktif teknisyen yok: başka bir profil seçin.',
  'socle.remplir_phrases_balisees.developpe_claude_anthropic_demande': '<b>Nicolas Briand — SELECTIS</b> isteğiyle <b>Claude (Anthropic)</b> tarafından geliştirildi',
  'socle.remplir_phrases_balisees.installer_prevo_assistant_comptes': '<a href="#/installation">Prévo\'yu kur (sihirbaz)</a>: hesaplar, https, telefonlar, PC ile başlatma.',
  'socle.remplir_phrases_balisees.plusieurs_postes_telephones_lancez': 'Birden çok iş istasyonu ve telefon mu var? <b>Lancer_GMAO.bat</b> (Windows) veya <b>lancer.sh</b> (Mac, Linux) dosyasını çalıştırın: sunucu modu kendiliğinden tanınır.',
  'socle.rendre.ecran_pas_pu_afficher': '<b>Bu ekran görüntülenemedi.</b> {message}',
  'socle.reperage_ligne.ligne_donnees_sans_identifiant': 'veri satırı no. {numero} (ID yok)',
  'socle.reprendre_dossier.acces_dossier_precedent_pas': 'Önceki klasöre erişim izni verilmedi. Klasörü yeniden seçin.',
  'socle.route.aucun_ecran_correspond_adresse': 'Bu adrese uyan bir ekran yok.',
  'socle.route.ecran_introuvable': 'Ekran bulunamadı',
  'socle.route.ecran_pas_disponible_profil': '“{ecranTitre}” ekranı {profil} profili için kullanılamaz.',
  'socle.sauvegarder_avant_format.mode_stockage_sait_pas': 'bu depolama modu yedek alamaz',
  'socle.sauvegarder_avant_format.stockage_pas_confirme_sauvegarde': 'depolama yedeği doğrulamadı (ad döndürmedi)',
  'socle.sauvegarder_avant_mise_ajour.sauvegarde_avant_mise_jour': '<b>“Prévo güncellemesi öncesi” yedeği alınamadı.</b> {message} Bir sonraki açılışta yeniden denenecek.',
  'socle.scanner_qr.impossible_ouvrir_camera_autorisation': 'Kamera açılamıyor (izin reddedildi veya kamera meşgul).',
  'socle.scanner_qr.placez_qr_code_equipement': 'Ekipmanın QR kodunu çerçevenin içine yerleştirin.',
  'socle.scanner_qr.scan_camera_pas_disponible': 'Kamerayla tarama bu sayfada kullanılamıyor. Telefonun kamerasını kullanın.',
  'socle.scanner_qr.scanner_qr_code': 'QR kod tara',
  'socle.selecteur_equipement.aucun_equipement_correspond': '“{recherche}” ile eşleşen ekipman yok.',
  'socle.selecteur_equipement.changer': 'Değiştir',
  'socle.selecteur_equipement.equipements_trouves': 'Bulunan ekipman',
  'socle.selecteur_equipement.equipements_trouves_affiner': { one: '{n} ekipman: daraltmak için birkaç harf yazın.', other: '{n} ekipman: daraltmak için birkaç harf yazın.' },
  'socle.selecteur_equipement.qr_code_correspond_aucun': 'Bu QR kod bilinen hiçbir ekipmanla eşleşmiyor.',
  'socle.selecteur_equipement.rechercher_equipement': 'Ekipman ara',
  'socle.selecteur_equipement.repere_nom': 'Ekipman kodu veya ad',
  'socle.selecteur_equipement.scanner': 'Tara',
  'socle.selecteur_langue.changer': 'Değiştir',
  'socle.selecteur_langue.changer_langue': 'Dili değiştir',
  'socle.selecteur_langue.choix_non_retenu': 'Dil kaydedilmedi: bu tarayıcı ayarlarını kaydetmeyi reddediyor.',
  'socle.selecteur_langue.langue_ecran': 'Ekran dili',
  'socle.selecteur_langue.recharge_demo': 'Dili değiştirmek demoyu yeniden yükler: demoda yaptığınız değişiklikler kaybolur.',
  'socle.session_perdue.reconnecte_saisie_gardee': 'Yeniden oturum açıldı: girdiğiniz bilgiler ekranda duruyor; kaydedin.',
  'socle.session_perdue.reconnectez_vous_meme_compte': 'Oturumunuz sona erdi. Aynı hesapla yeniden oturum açın: ekranı bıraktığınız gibi, girdiğiniz bilgilerle birlikte bulursunuz. Kaydedilmemiş olanlar henüz kaydedilmedi: sonra kaydedin.',
  'socle.suffixe_du_motif.motif_sauvegarde_refuse_motifs': 'Yedek gerekçesi reddedildi. Kabul edilen gerekçeler: {motifs}.',
  'socle.tableau.aucune_ligne_afficher': 'Gösterilecek satır yok.',
  'socle.texte_base_vide.aucun_23_fichiers_prevo': 'Prévo\'nun 23 dosyasının hiçbiri bulunamadı.',
  'socle.titre_donnees.ou_sont_donnees': 'Verileriniz nerede?',
  'socle.titre_donnees_demo.ou_sont_donnees_demo': 'Bu demonun verileri nerede?',
  'socle.traduire_erreur.acces_refuse_dossier_donnees': 'Veri klasörüne erişim reddedildi ({action}). İzni yeniden vermek için klasörü yeniden seçin.',
  'socle.traduire_erreur.dossier_donnees_introuvable_ete': 'Veri klasörü bulunamadı ({action}): taşınmış, yeniden adlandırılmış veya bağlantısı kesilmiş olabilir mi?',
  'socle.traduire_erreur.lecture_ecriture_impossible_dossier': 'Veri klasöründe okuma veya yazma yapılamıyor ({action}).',
  'socle.valider_demandeur.indiquez_nom_permet_retrouver': 'Adınızı girin: taleplerinizi bulmayı sağlar.',
  'socle.verifier_dossier_accessible.dossier_donnees_introuvable_inaccessible': 'Veri klasörü bulunamıyor veya erişilemiyor (silinmiş, taşınmış, USB bellek veya ağ paylaşımının bağlantısı kesilmiş olabilir mi?). Yeniden bağlayın veya klasörü yeniden seçin.',
  'socle.verifier_formulaire.case_doit_etre_cochee': 'Bu kutu işaretlenmelidir.',
  'socle.verifier_formulaire.champ_obligatoire': 'Bu alan zorunludur.',
  'socle.verifier_formulaire.saisissez_nombre_entier_ex': 'Bir tam sayı girin (örn. 12).',
  'socle.verifier_formulaire.saisissez_nombre_ex_12': 'Bir sayı girin (örn. 12,5).',
  'socle.verifier_initialise.donnees_appelez_donnees_initialiser': 'Donnees: okumadan veya yazmadan önce Donnees.initialiser(adaptateur, …) çağırın.',
  'socle.verifier_nom_document.nom_document_refuse_lettres': 'Belge adı reddedildi: harfler, rakamlar, “.”, “_” veya “-”.',
  'socle.verifier_nom_document.nom_document_reserve_windows': 'Belge adı Windows tarafından ayrılmış.',
  'socle.verifier_nom_document.type_document_refuse_types': 'Belge türü reddedildi. Kabul edilen türler: {types}.',
  'socle.verifier_nom_sauvegarde.nom_sauvegarde_invalide': 'Geçersiz yedek adı.',
  'socle.verifier_nom_table.table_inconnue': 'Bilinmeyen tablo: “{nomTable}”.',
  'socle.verifier_nom_table.table_inconnue_dossier': 'Bilinmeyen tablo: {table}.',
  'socle.verifier_verrou_dossier.dossier_semble_deja_ouvert': '<b>Bu klasör “{poste}” iş istasyonunda zaten açık görünüyor</b> (son canlılık belirtisi: {heure}). Aynı klasöre yazan iki iş istasyonu birbirini engelleyebilir: mümkünse diğer oturumu kapatın.',
  'socle.zone_depot.cliquer_choisir_demo_propres': 'veya seçmek için tıklayın: kendi dosyalarınızla demo, hiçbir şey kaydedilmez',
  'socle.zone_depot.deposer_fichiers_csv_ici': 'CSV dosyalarını buraya bırakın',
});
// ==== fin socle ====

// ==== section planning ====
I18n.ajouter('tr', {
});
// ==== fin planning ====

// ==== section causes ====
I18n.ajouter('tr', {
});
// ==== fin causes ====

// ==== section dictee ====
I18n.ajouter('tr', {
});
// ==== fin dictee ====

// ==== section mise ====
I18n.ajouter('tr', {
});
// ==== fin mise ====

// ==== section aide ====
I18n.ajouter('tr', {
});
// ==== fin aide ====

// ==== section ordres ====
I18n.ajouter('tr', {
});
// ==== fin ordres ====

// ==== section demandes ====
I18n.ajouter('tr', {
});
// ==== fin demandes ====

// ==== section parc ====
I18n.ajouter('tr', {
});
// ==== fin parc ====

// ==== section preventif ====
I18n.ajouter('tr', {
});
// ==== fin preventif ====

// ==== section controles ====
I18n.ajouter('tr', {
});
// ==== fin controles ====

// ==== section wiki ====
I18n.ajouter('tr', {
});
// ==== fin wiki ====

// ==== section suggestions ====
I18n.ajouter('tr', {
});
// ==== fin suggestions ====

// ==== section import ====
I18n.ajouter('tr', {
});
// ==== fin import ====

// ==== section magasin ====
I18n.ajouter('tr', {
});
// ==== fin magasin ====

// ==== section indicateurs ====
I18n.ajouter('tr', {
});
// ==== fin indicateurs ====

// ==== section rapport ====
I18n.ajouter('tr', {
});
// ==== fin rapport ====

// ==== section accueil ====
I18n.ajouter('tr', {
});
// ==== fin accueil ====

// ==== section equipe ====
I18n.ajouter('tr', {
});
// ==== fin equipe ====

// ==== section acces ====
I18n.ajouter('tr', {
});
// ==== fin acces ====

// ==== section connexion ====
I18n.ajouter('tr', {
});
// ==== fin connexion ====

// ==== section poste ====
I18n.ajouter('tr', {
});
// ==== fin poste ====

// ==== section apropos ====
I18n.ajouter('tr', {
});
// ==== fin apropos ====

// ==== section installation ====
I18n.ajouter('tr', {
});
// ==== fin installation ====

// ==== section porte ====
I18n.ajouter('tr', {
});
// ==== fin porte ====

// ==== section parametres ====
I18n.ajouter('tr', {
});
// ==== fin parametres ====

// ==== section sauvegardes ====
I18n.ajouter('tr', {
});
// ==== fin sauvegardes ====

// ==== section zip ====
I18n.ajouter('tr', {
});
// ==== fin zip ====

// ==== section serveur ====
I18n.ajouter('tr', {
});
// ==== fin serveur ====

// ==== section ia ====
I18n.ajouter('tr', {
});
// ==== fin ia ====
