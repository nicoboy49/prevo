# Glossaire métier : français → anglais, turc, italien, portugais (Portugal)

Ce glossaire fixe la traduction des termes métier de Prévo en anglais (`en`), turc (`tr`), italien (`it`) et portugais du Portugal (`pt-PT`). Il sert aux traducteurs de `js/i18n/en.js`, `tr.js`, `it.js` et `pt-PT.js` (un par groupe d'écrans) et à la relecture. Le français reste la langue pivot.

**Règle d'or (anglais) : un terme français = une traduction anglaise, partout.** Même terme dans un menu, un bouton, un message d'erreur, un champ du schéma ou le wiki. Si un terme n'est pas dans la liste, prendre le plus proche et l'ajouter ici (une ligne) avant de continuer.

**Règle d'or (turc) : un terme français = un terme turc, partout** (menu, bouton, erreur, schéma, wiki), celui que la maintenance industrielle turque emploie vraiment.

**Règle d'or (italien) : un terme français = un terme italien, partout**, celui que la manutenzione industriale italiana emploie vraiment.

**Règle d'or (portugais du Portugal) : un terme français = un terme portugais, partout**, celui du Portugal et jamais celui du Brésil.

Pour les trois nouvelles langues aussi, un terme absent de la liste se rapproche du plus proche et s'ajoute ici avant de continuer.

Autres règles :

- **Anglais britannique** (décision D151 : `en` = en-GB) : colour, organisation, catalogue, labour, programme, stocktake, cancelled. Mais on garde le terme que l'industrie britannique emploie vraiment (ex. « work order », « MTBF »).
- Termes anglais en minuscules, sauf noms propres (Prévo) et abréviations. La première lettre d'un libellé affiché suit l'usage de l'écran (majuscule en début de libellé, comme en français).
- Le genre et l'accord français disparaissent : « Acceptée » (demande) et « Accepté » (OT) donnent le même mot.
- Le pluriel anglais suit la forme `one` / `other` déjà utilisée par le dictionnaire.
- Les colonnes `tr`, `it` et `pt-PT` ont été ajoutées au Lot 5 (décision D166), avant les traductions des dictionnaires, qui les appliquent terme par terme. Ce sont des traductions automatiques : les corrections sont bienvenues (issues GitHub).

Règles propres au turc (`tr`) :

- Majuscule et minuscule du i : `İ`/`i` (avec point) et `I`/`ı` (sans point) ; on ne remplace jamais l'un par l'autre (« İş emri », « ıslak »).
- Pas de pluriel après un nombre : « 3 iş emri », pas « 3 iş emirleri ».
- Boutons et menus au radical du verbe (« Kaydet », « Sil ») ; phrases d'aide à la forme de politesse « siz » (« Kaydedin »).
- Mot de passe : « şifre » (usage courant). Guillemets “…”.

Règles propres à l'italien (`it`) :

- Boutons et menus à l'impératif (« Salva », « Elimina ») ; phrases en tournure impersonnelle ou « tu », constantes dans tout le logiciel.
- Genre et accord indiqués « masculin/féminin » pour les statuts et adjectifs (« aperto/aperta »). Pour un statut d'OT (« ordine di lavoro », masculin) on accorde au masculin ; pour une demande (« richiesta », féminin) au féminin.
- Abréviation usuelle : « OdL » (ordine di lavoro) ; « DI » reste en toutes lettres.
- Guillemets « … » ; pas d'espace avant « : ; ! ? ».

Règles propres au portugais du Portugal (`pt-PT`) :

- Jamais le portugais du Brésil : ecrã (pas tela), ficheiro (pas arquivo), utilizador (pas usuário), registo (pas registro), telemóvel (pas celular), guardar (pas salvar), palavra-passe (pas senha), definições (pas configurações), cópia de segurança (pas backup).
- Orthographe de l'accord de 1990 en vigueur au Portugal (receção, ativo, facto) ; pas de gérondif brésilien (« a guardar » et non « guardando »).
- Boutons et menus à l'infinitif (« Guardar », « Eliminar »).
- Genre et accord indiqués « masculin/féminin » (« aberto/aberta ») ; « ordem de trabalho » est féminin (OT), « pedido » masculin.
- Abréviations usuelles : « OT » (ordem de trabalho), « GMAO » ; « DI » reste en toutes lettres.

## 1. Abréviations françaises : que fait-on en anglais ?

| fr | en | tr | it | pt-PT | remarque |
|---|---|---|---|---|---|
| OT | WO | iş emri | OdL | OT | abréviation anglaise usuelle de « work order ». Écrire « work order » en toutes lettres à la première occurrence d'un écran ou dans une phrase d'aide. tr : en toutes lettres (« İE » n'est pas usuel) ; it « OdL » ; pt-PT « OT ». Écrire la forme complète à la première occurrence d'un écran. |
| DI | (pas d'abréviation) « work request » | iş talebi | richiesta di intervento | pedido de intervenção | « WR » n'est pas assez courant. Toujours en toutes lettres. pas d'abréviation en tr, it ni pt-PT. |
| GMAO | CMMS | BYBS | CMMS | GMAO | computerised maintenance management system ; en toutes lettres dans « À propos ». tr : « bakım yönetim yazılımı » en toutes lettres dans « À propos » ; it : « software di manutenzione » en toutes lettres ; pt-PT : « GMAO » est l'usage portugais, « software de gestão da manutenção » en toutes lettres. |
| MTBF, MTTR | MTBF, MTTR | MTBF, MTTR | MTBF, MTTR | MTBF, MTTR | identiques. Développer : mean time between failures / mean time to repair. |
| HT | excl. VAT | KDV hariç | IVA esclusa | sem IVA | « (€ HT) » devient « (€ excl. VAT) ». Pas de « HT » en anglais britannique. tr « KDV » = TVA. |
| TTC | incl. VAT | KDV dahil | IVA inclusa | com IVA |  |
| IA | AI | YZ | IA | IA | tr « YZ » (yapay zekâ). |
| RG (règle de gestion, « RG6 ») | « business rule 6 » | iş kuralı 6 | regola di gestione 6 | regra de gestão 6 | références internes dans les textes d'aide. Ne pas écrire « BR6 » : personne ne l'emploie. |
| P1 à P4 | P1 à P4 | P1 à P4 | P1 à P4 | P1 à P4 | inchangés (valeurs de liste). |
| A, B, C (criticité) | A, B, C | A, B, C | A, B, C | A, B, C | inchangés. |
| D24, D151… | D24, D151… | D24, D151… | D24, D151… | D24, D151… | numéros de décision : inchangés. |
| CSV, ZIP, QR code, PC | idem | aynı | idem | idem | inchangés. |

## 2. Ordres de travail et demandes

| fr | en | tr | it | pt-PT | remarque |
|---|---|---|---|---|---|
| ordre de travail (OT) | work order (WO) | iş emri | ordine di lavoro (OdL) | ordem de trabalho (OT) | la fiche de travail. Pluriel : work orders. tr : pas de pluriel après un nombre (« 3 iş emri »). it : masculin ; pt-PT : féminin. |
| demande d'intervention (DI) | work request | iş talebi | richiesta di intervento | pedido de intervenção | émise par un demandeur ; peut donner un OT. it : féminin ; pt-PT : masculin. |
| demande | request | talep | richiesta | pedido | forme courte de « demande d'intervention ». |
| demandeur | requester | talep eden | richiedente | requerente | personne qui signale un problème (profil « Demandeur »). |
| intervention | job | müdahale | intervento | intervenção | le travail réalisé sur site. « Intervention antérieure » (wiki) : previous job. |
| travail à faire | work to be done | yapılacak iş | lavoro da eseguire | trabalho a realizar | champ de l'OT. |
| compte rendu | job report | müdahale raporu | rapporto di intervento | relatório de intervenção | rédigé à la fin de l'OT. |
| anomalie constatée | fault found | tespit edilen arıza | anomalia riscontrata | anomalia constatada | champ de l'OT : ce que le technicien a vu. |
| astuce pour la prochaine fois | tip for next time | bir sonraki sefer için ipucu | suggerimento per la prossima volta | dica para a próxima vez | champ libre de l'OT. |
| curatif | corrective | düzeltici | correttiva | corretiva | on ne dit pas « curative » en maintenance. it, pt-PT : l'adjectif s'accorde (« manutenzione correttiva », « manutenção corretiva »). |
| correctif | corrective | düzeltici | correttivo/correttiva | corretivo/corretiva | « correctif immédiat » : immediate corrective ; « correctif différé » : deferred corrective. « correctif immédiat » : anında düzeltici / correttivo immediato / corretivo imediato ; « différé » : ertelenmiş düzeltici / correttivo differito / corretivo diferido. |
| amélioration | improvement | iyileştirme | miglioramento | melhoria | type d'OT. |
| panne | breakdown | arıza | guasto | avaria | OT correctif qui a arrêté la production. « Failure » est réservé à « code de défaillance ». « Failure » (code de défaillance) : tr « arıza kodu » aussi ; la panne et le code partagent « arıza » en tr, « guasto » en it, « avaria » en pt-PT. |
| symptôme | symptom | belirti | sintomo | sintoma | ce qu'on observe. |
| cause | cause | neden | causa | causa |  |
| remède | remedy | çözüm | rimedio | solução | ce qui a été fait pour réparer. |
| code de défaillance | failure code | arıza kodu | codice di guasto | código de avaria | liste Symptôme / Cause / Remède. |
| famille (de code) | family | aile | famiglia | família | famille de code de défaillance. |
| origine (d'un OT) | origin | kaynak | origine | origem | valeurs : DI, manuel, préventif, urgence. |
| urgence | emergency | acil | emergenza | urgência | valeur d'origine. |
| manuel | manual | manuel | manuale | manual |  |
| impact (d'une demande) | impact | etki | impatto | impacto | valeurs : arrêt, dégradé, gêne, sécurité. |
| arrêt de production | production stoppage | üretim durması | fermo produzione | paragem de produção | champ de l'OT. |
| durée d'arrêt | downtime | duruş süresi | tempo di fermo | tempo de paragem | en heures. |
| mettre en attente | put on hold | beklemeye al | metti in attesa | pôr em espera | motif : « reason for hold ». motif : bekleme gerekçesi / motivo dell'attesa / motivo da espera. |
| motif | reason | gerekçe | motivo | motivo | motif d'annulation, de refus, de report, de mise en attente. tr « gerekçe » (et non « neden », réservé à la cause). |
| remis en service en sécurité | returned to service safely | güvenli şekilde hizmete alındı | rimesso in servizio in sicurezza | reposto em serviço em segurança | case à cocher de l'OT. |
| sous-traitance | subcontracting | taşeron | subappalto | subcontratação | coût de sous-traitance : subcontracting cost. coût : taşeron maliyeti / costo del subappalto / custo de subcontratação. |
| OT lié | linked work order | bağlantılı iş emri | ordine di lavoro collegato | ordem de trabalho associada |  |
| ordre (d'une opération) | sequence | sıra | sequenza | sequência | colonne « Ordre » des opérations ; pas « order » ni « position ». |
| repères (fiche d'un OT) | key details | temel bilgiler | dati principali | dados principais | bloc de la fiche OT ; sans rapport avec « repère » (tag) d'un équipement. |
| origine « DI » (liste des OT) | Request | Talep | Richiesta | Pedido | valeur d'origine d'un OT né d'une demande. |
| RAS | NTR | bildirilecek bir şey yok | niente da segnalare | nada a assinalar | « RAS » refusé sur un correctif : « NTR » ; le contrôle accepte aussi « nothing to report ». |
| prise en charge (d'un OT) | taken on | üstlenme | presa in carico | assunção |  |
| poste (ligne du tableau de coûts d'un OT) | cost line | maliyet kalemi | voce di costo | linha de custo | pas « item » : réservé à l'article du magasin. |
| bon de travail | work order sheet | iş föyü | foglio di lavoro | folha de trabalho | fiche imprimée de l'OT ; pas « job sheet ». |
| geste (wiki) | task | uygulama yöntemi | procedura operativa | procedimento | un geste ou une méthode (page savoir-faire). |
| regrouper | merge | birleştir | unisci | agrupar | une demande « Regroupée » est fusionnée dans une autre. |
| différer | defer | ertele | rinvia | adiar | demande « Différée ». |

## 3. Équipements et parc

| fr | en | tr | it | pt-PT | remarque |
|---|---|---|---|---|---|
| équipement | equipment | ekipman | attrezzatura | equipamento | machine ou installation. Jamais « asset » dans les libellés. it : « attrezzatura » (et non « equipaggiamento », faux ami). |
| parc | equipment register | ekipman envanteri | parco attrezzature | parque de equipamentos | l'ensemble des équipements suivis. Le menu court dit « Equipment ». menu court : Ekipman / Attrezzature / Equipamentos. |
| repère | tag | ekipman kodu | codice | código | identifiant lisible d'un équipement (ex. CP-01). « Equipment tag » si l'ambiguïté est possible. it, tr : « tag » est aussi employé en atelier mais reste en anglais ; on garde « codice » / « ekipman kodu ». |
| localisation | location | konum | ubicazione | localização | arbre site > atelier > ligne. |
| site | site | tesis | sito | instalação | type de localisation. |
| atelier | workshop | atölye | officina | oficina | type de localisation ; pas « plant ». « PC atelier » : workshop PC. |
| ligne | line | hat | linea | linha | ligne de production (type de localisation). Ne pas confondre avec la ligne d'un tableau (« row »). |
| criticité | criticality | kritiklik | criticità | criticidade | valeurs A, B, C. |
| statut (d'un équipement) | status | durum | stato | estado | valeurs : en service, arrêt, rebut. |
| en service | in service | serviste | in servizio | em serviço |  |
| arrêt (statut équipement) | stopped | durdu | fermo/ferma | parado/parada |  |
| rebut / mis au rebut | scrapped | hurdaya çıkarıldı | dismesso/dismessa | abatido/abatida |  |
| désignation | designation | tanım | designazione | designação | nom descriptif d'un équipement ou d'un article. À ne pas confondre avec « description » (demandes). |
| marque | make | marka | marca | marca | pas « brand ». |
| modèle | model | model | modello | modelo |  |
| numéro de série | serial number | seri numarası | numero di serie | número de série |  |
| date de mise en service | date in service | hizmete alma tarihi | data di messa in servizio | data de entrada em serviço | pas « commissioning date » (réservé à la mise en route). |
| heures de fonctionnement par jour | operating hours per day | günlük çalışma saati | ore di funzionamento al giorno | horas de funcionamento por dia | sert au calcul du temps requis. |
| valeur de remplacement | replacement value | yerine koyma değeri | valore di sostituzione | valor de substituição |  |
| habilitation requise | authorisation required | yetkilendirme gerekli | abilitazione richiesta | habilitação necessária |  |
| compteur | meter | sayaç | contatore | contador | heures de marche, cycles, etc. |
| relevé (de compteur) | meter reading | sayaç okuması | lettura del contatore | leitura do contador |  |
| fiche (d'un équipement, d'un OT) | record | kayıt | scheda | ficha | « la fiche de l'équipement » : the equipment record. Pas « sheet ». « la fiche de l'équipement » : ekipman kaydı / scheda dell'attrezzatura / ficha do equipamento. |
| fiche technique | data sheet | teknik föy | scheda tecnica | ficha técnica | document d'un équipement. |
| menus courts « Parc », « Contrôles » | Equipment, Inspections | Ekipman, Kontroller | Attrezzature, Controlli | Equipamentos, Inspeções | la forme longue (parc) reste « equipment register ». |
| document (d'un équipement) | document | belge | documento | documento |  |
| articles par équipement | parts by equipment | ekipmana göre malzemeler | articoli per attrezzatura | artigos por equipamento | table de liaison article / équipement. |
| actif (case) | active | aktif | attivo/attiva | ativo/ativa | un enregistrement inactif est « inactive », jamais « deleted ». inactif : pasif / inattivo/inattiva / inativo/inativa. |

## 4. Préventif et contrôles

| fr | en | tr | it | pt-PT | remarque |
|---|---|---|---|---|---|
| préventif | preventive | önleyici | preventiva | preventiva | adjectif et nom (« le préventif » : preventive maintenance). Pas d'abréviation PM/PPM. it, pt-PT : adjectif féminin accordé à « manutenzione » / « manutenção » ; « o preventivo » (pt-PT) s'emploie comme nom. |
| gamme (de préventif) | task list | bakım planı | piano di manutenzione | gama de manutenção | modèle récurrent de travail. Pluriel : task lists. Choix tranché (voir la dernière section). pt-PT « gama » est l'usage portugais ; pluriel tr : « bakım planları » (sans nombre). |
| opération (d'une gamme / d'un OT) | task | görev | attività | operação | une ligne de la gamme. |
| préventif systématique | fixed-interval preventive | takvime bağlı önleyici | preventiva a calendario | preventiva sistemática | déclenché par le calendrier. |
| préventif conditionnel | condition-based preventive | duruma bağlı önleyici | preventiva su condizione | preventiva condicionada | déclenché par un compteur ou un seuil. |
| déclencheur | trigger | tetikleyici | attivatore | acionador | valeurs : date, compteur, seuil. valeurs : tarih, sayaç, eşik. |
| seuil | threshold | eşik | soglia | limiar |  |
| périodicité | interval | periyot | periodicità | periodicidade | en jours, en mois ou en unités de compteur. |
| fréquence | frequency | sıklık | frequenza | frequência | « fois par an » ; pour une durée entre deux passages, utiliser « interval ». |
| échéance | due date | vade tarihi | scadenza | vencimento | « prochaine échéance » : next due date. « Échue » : overdue. « Échue » : vadesi geçmiş / scaduta / vencida. |
| avance (jours) | lead time (days) | önceden oluşturma (gün) | anticipo (giorni) | antecedência (dias) | combien de jours avant l'échéance l'OT est créé. |
| dernière réalisation | last completed | son gerçekleştirme | ultima esecuzione | última realização |  |
| planifier | schedule | planla | pianifica | agendar | donner une date à un OT. Pas « plan ». pt-PT : « agendar » (donner une date), « planear » est réservé à la planification globale. |
| date prévue | planned date | planlanan tarih | data prevista | data prevista |  |
| temps prévu | planned time | planlanan süre | tempo previsto | tempo previsto | en heures. |
| respect du préventif | preventive compliance | önleyici bakım uyumu | rispetto della manutenzione preventiva | cumprimento da manutenção preventiva | part des OT préventifs faits à l'échéance. |
| part du préventif | preventive share | önleyici bakım payı | quota di manutenzione preventiva | peso da manutenção preventiva | part des heures passées sur le préventif. |
| contrôle réglementaire | statutory inspection | yasal kontrol | verifica di legge | inspeção regulamentar | vérification périodique imposée par un texte. |
| organisme de contrôle | inspection body | muayene kuruluşu | organismo di controllo | organismo de inspeção |  |
| texte de référence | reference text | dayanak metin | testo di riferimento | texto de referência | le texte réglementaire (ex. arrêté, norme). |
| observations levées | observations cleared | giderilen gözlemler | osservazioni risolte | observações resolvidas |  |
| rapport (d'un contrôle) | report | rapor | rapporto | relatório |  |
| rapport mensuel | monthly report | aylık rapor | rapporto mensile | relatório mensal | « Report » seul reste réservé au rapport (contrôle ou mensuel) : le menu « Signaler » est « Report a problem ». |
| nature du contrôle | type of inspection | kontrol türü | tipo di verifica | tipo de inspeção | pas « nature of the inspection ». |
| check-list (d'une gamme) | checklist | kontrol listesi | checklist | lista de verificação | un seul mot. |
| levée d'observations | clearing | gözlemlerin giderilmesi | risoluzione delle osservazioni | resolução das observações | action de lever les observations d'un contrôle. |
| figer (un rapport), rapport figé | finalise, finalised report | kesinleştir, kesinleşmiş rapor | finalizza, rapporto finalizzato | finalizar, relatório finalizado |  |
| fait marquant | highlight | önemli olay | fatto rilevante | facto relevante | rapport mensuel. |
| suggestion | suggestion | öneri | suggerimento | sugestão | propositions S1 à S4 de l'écran préventif. |

## 5. Sécurité et habilitations

| fr | en | tr | it | pt-PT | remarque |
|---|---|---|---|---|---|
| consignation | isolation | enerji izolasyonu (LOTO) | messa in sicurezza (LOTO) | consignação | mise en sécurité d'une machine avant intervention (énergies coupées, cadenassées). Choix tranché (voir la dernière section). pt-PT « consignação » est le terme normatif portugais ; it : « lockout/tagout » est aussi compris mais on garde « messa in sicurezza ». |
| déconsignation | de-isolation | izolasyonun kaldırılması | ripristino delle energie | desconsignação | remise sous énergie. |
| procédure de consignation | isolation procedure | enerji izolasyon prosedürü | procedura di messa in sicurezza | procedimento de consignação | champ « Consignation » de l'équipement : isolation. |
| cadenas | padlock | asma kilit | lucchetto | cadeado |  |
| consigne (de sécurité) | safety instruction | güvenlik talimatı | istruzione di sicurezza | instrução de segurança | « consignes » d'une gamme ou d'un OT : instructions. |
| habilitation | authorisation | yetkilendirme | abilitazione | habilitação | autorisation nominative (ex. habilitation électrique). Choix tranché (voir la dernière section). |
| date d'obtention | date obtained | alınma tarihi | data di conseguimento | data de obtenção |  |
| date d'échéance (habilitation) | expiry date | geçerlilik bitişi | data di scadenza | data de validade | pour une habilitation ; « due date » reste pour le préventif. |
| intitulé | name | ad | nome | nome | nom de l'habilitation. |
| sécurité | safety | güvenlik | sicurezza | segurança | valeur d'impact : « safety ». |
| permis de feu | hot work permit | sıcak çalışma izni | permesso di lavoro a caldo | licença de trabalho a quente |  |

## 6. Magasin et achats

| fr | en | tr | it | pt-PT | remarque |
|---|---|---|---|---|---|
| magasin | stores | depo | magazzino | armazém | le lieu et l'écran. Pas « warehouse ». |
| stock | stock | stok | scorte | stock | pas « inventory ». pt-PT : « stock » est l'usage portugais. |
| article | item | malzeme | articolo | artigo | un article du magasin. |
| pièce (détachée) | spare part | yedek parça | ricambio | peça sobresselente | « pièces prévues d'un OT » : planned parts. « pièces prévues d'un OT » : planlanan parçalar / ricambi previsti / peças previstas. |
| référence | reference | kod | codice | referência | référence interne de l'article. |
| référence fabricant | manufacturer part number | üretici parça numarası | codice del costruttore | referência do fabricante |  |
| fabricant | manufacturer | üretici | costruttore | fabricante |  |
| fournisseur | supplier | tedarikçi | fornitore | fornecedor | pas « vendor ». |
| unité | unit | birim | unità | unidade | unité de stock. |
| point de commande | reorder point | sipariş noktası | punto di riordino | ponto de encomenda | seuil sous lequel on réapprovisionne. |
| stock de sécurité | safety stock | emniyet stoku | scorta di sicurezza | stock de segurança |  |
| quantité à commander | order quantity | sipariş miktarı | quantità da ordinare | quantidade a encomendar |  |
| délai d'approvisionnement | supply lead time | tedarik süresi | tempo di approvvigionamento | prazo de aprovisionamento |  |
| article critique | critical item | kritik malzeme | articolo critico | artigo crítico |  |
| mouvement (de stock) | stock movement | stok hareketi | movimento di magazzino | movimento de stock |  |
| entrée | receipt | giriş | carico | entrada | mouvement de stock entrant. Pas « entry ». |
| sortie | issue | çıkış | scarico | saída | mouvement sortant (« issue to a work order »). |
| retour | return | iade | reso | devolução |  |
| inventaire | stocktake | sayım | inventario | inventário | comptage du stock (usage britannique). « inventario » et « inventário » désignent bien le comptage (pas le stock). |
| achat | purchase | satın alma | acquisto | compra |  |
| commande | order | sipariş | ordine | encomenda | verbe « commander » : to order. |
| réception | goods receipt | mal kabul | ricevimento merce | receção de mercadoria | arrivée d'un achat ; le mouvement de stock qui en résulte est un « receipt ». |
| réceptionner | receive | mal kabul et | ricevi | rececionar |  |
| prix unitaire | unit price | birim fiyat | prezzo unitario | preço unitário |  |
| valeur du stock | stock value | stok değeri | valore delle scorte | valor do stock |  |
| quantité | quantity | miktar | quantità | quantidade |  |
| emplacement (d'un article) | bin location | raf adresi | posizione di stoccaggio | posição de armazenagem | partout : colonne, fiche, étiquette, wiki (pas « bin », « position » ni « storage location »). « Rayon et casier » : aisle and bin. « Rayon et casier » : koridor ve göz / corsia e vano / corredor e prateleira. |
| rupture (de stock) | out of stock / stock-out | stokta yok | esaurito | rutura de stock | « out of stock » comme état ou libellé ; « stock-out » comme nom compté (« 2 stock-outs »). nom compté : stok tükenmesi / esaurimento scorte / rutura de stock. |
| écart (d'inventaire) | variance | fark | differenza | diferença |  |
| nomenclature | bill of materials | malzeme listesi | distinta base | lista de materiais | articles montés sur une machine. |

## 7. Équipe et accès

| fr | en | tr | it | pt-PT | remarque |
|---|---|---|---|---|---|
| technicien | technician | teknisyen | tecnico | técnico | pas « engineer ». |
| responsable | manager | sorumlu | responsabile | responsável | profil qui voit tout et règle les paramètres. |
| profil | profile | profil | profilo | perfil | Demandeur / Technicien / Responsable. |
| métier | trade | uzmanlık | specializzazione | especialidade | électricien, mécanicien… |
| capacité (heures par semaine) | capacity (hours per week) | kapasite (haftalık saat) | capacità (ore settimanali) | capacidade (horas por semana) |  |
| taux horaire | hourly rate | saat ücreti | tariffa oraria | taxa horária |  |
| utilisateur | user | kullanıcı | utente | utilizador |  |
| identifiant (de connexion) | username | kullanıcı adı | nome utente | nome de utilizador | de la forme prenom.nom. |
| identifiant (clé d'une ligne) | ID | ID | ID | ID | colonne « Identifiant » du schéma : ID. |
| mot de passe | password | şifre | password | palavra-passe | tr « şifre » (usage courant) ; it « password » (usage courant) ; pt-PT « palavra-passe ». |
| se connecter / se déconnecter | sign in / sign out | oturum aç / oturumu kapat | accedi / esci | iniciar sessão / terminar sessão | pas « log in ». |
| compte | account | hesap | account | conta |  |
| poste (cet ordinateur ou un autre) | workstation | iş istasyonu | postazione | estação de trabalho | « Ce poste » : This workstation ; « Nom du poste » : Workstation name ; « changé sur un autre poste » : on another workstation. Jamais « computer » ni « this PC » pour le poste. « PC » reste « PC » quand le français dit PC (le PC atelier, le PC serveur). Ne désigne jamais un emploi. « Ce poste » : bu iş istasyonu / questa postazione / esta estação de trabalho. Ne désigne jamais un emploi (pas « posto de trabalho » en pt-PT). « PC » reste « PC ». |
| accès | access | erişim | accesso | acesso |  |
| paramètres | settings | ayarlar | impostazioni | definições |  |
| sauvegarde | backup | yedek | backup | cópia de segurança |  |
| journal des modifications | change log | değişiklik günlüğü | registro delle modifiche | registo de alterações | table `journal`. |
| appareil | device | cihaz | dispositivo | dispositivo | téléphone ou navigateur enrôlé ; ne pas confondre avec « poste » (workstation). |
| enrôler, enrôlement, appareil enrôlé | enrol, enrolment, enrolled device | eşleştir, eşleştirme, eşleştirilmiş cihaz | abbinare, abbinamento, dispositivo abbinato | associar, associação, dispositivo associado | orthographe britannique (un seul « l » à enrol, deux à enrolled). |
| révoquer | revoke | yetkisini kaldır | revocare | revogar |  |
| fiche d'accès | access record | erişim kaydı | scheda di accesso | ficha de acesso | pas « access sheet ». |
| journal des connexions | sign-in log | oturum açma günlüğü | registro degli accessi | registo de inícios de sessão |  |
| mandataire (inverse) | proxy (reverse proxy) | ters proxy | reverse proxy | proxy inverso |  |
| tâche planifiée | scheduled task | zamanlanmış görev | attività pianificata | tarefa agendada | tâche Windows de démarrage. |
| portée (de l'accès : « ce PC », atelier, dehors) | scope | kapsam | ambito | âmbito |  |
| empreinte (d'un fichier, manifeste) | fingerprint | özet değeri (hash) | impronta | impressão digital |  |
| copie de sécurité | safety copy | güvenlik kopyası | copia precauzionale | cópia prévia | copie faite avant une restauration ; « Copie des sauvegardes » (dossier externe) : backup copy. distincte de « sauvegarde » : copie faite avant une restauration. |
| bombe de décompression | decompression bomb | dekompresyon bombası | bomba di decompressione | bomba de descompressão |  |
| porte d'entrée | front door | giriş kapısı | porta d'ingresso | porta de entrada | accès réseau de Prévo ; « page de porte » : gateway page. « page de porte » : giriş sayfası / pagina d'ingresso / página de entrada. |
| élévation (de droits) | elevation | yetki yükseltme | innalzamento dei privilegi | elevação de privilégios |  |
| Mode Solo | Solo mode | Solo modu | Modalità Solo | Modo Solo |  |
| Appliquer et relancer | Apply and restart | Uygula ve yeniden başlat | Applica e riavvia | Aplicar e reiniciar |  |
| Démarrer avec la machine / avec le PC | Starting with the PC | PC ile başlatma | Avvio con il PC | Iniciar com o PC | libellé réel du réglage : « Starting with the PC, and sleep » ; question de l'assistant : « Start with the PC? ». |

## 8. Indicateurs

| fr | en | tr | it | pt-PT | remarque |
|---|---|---|---|---|---|
| indicateur | indicator | gösterge | indicatore | indicador |  |
| MTBF | MTBF | MTBF | MTBF | MTBF | mean time between failures : temps moyen entre pannes. tr : arızalar arası ortalama süre ; it : tempo medio tra i guasti ; pt-PT : tempo médio entre avarias. |
| MTTR | MTTR | MTTR | MTTR | MTTR | mean time to repair : temps moyen de rétablissement. tr : ortalama onarım süresi ; it : tempo medio di riparazione ; pt-PT : tempo médio de reparação. |
| disponibilité | availability | kullanılabilirlik | disponibilità | disponibilidade | MTBF ÷ (MTBF + MTTR). |
| temps requis | required time | gereken süre | tempo richiesto | tempo requerido | heures de fonctionnement × jours de la période. |
| temps passé | time spent | harcanan süre | tempo impiegato | tempo dedicado | heures saisies sur un OT. « Temps passés sur OT » : time spent on work orders. « Temps passés sur OT » : iş emirlerinde harcanan süre / tempo impiegato sugli OdL / tempo dedicado às OT. |
| délai de prise en charge | response time | yanıt süresi | tempo di risposta | tempo de resposta | de la demande au début de l'intervention. |
| OT en retard | overdue work orders | geciken iş emirleri | OdL in ritardo | OT em atraso |  |
| charge / capacité | workload / capacity | iş yükü / kapasite | carico di lavoro / capacità | carga de trabalho / capacidade |  |
| coût | cost | maliyet | costo | custo | main-d'œuvre : labour ; pièces : parts. main-d'œuvre : işçilik / manodopera / mão de obra ; pièces : parçalar / ricambi / peças. |
| période | period | dönem | periodo | período |  |
| non calculable | cannot be calculated | hesaplanamıyor | non calcolabile | não calculável |  |
| pointage (temps) | time entry | zaman kaydı | rilevazione ore | registo de tempo | ligne de temps passé sur un OT. |

## 9. Wiki

| fr | en | tr | it | pt-PT | remarque |
|---|---|---|---|---|---|
| wiki | wiki | wiki | wiki | wiki | base de savoir de l'atelier, rédigée avec l'aide de l'IA. |
| page | page | sayfa | pagina | página |  |
| savoir-faire | know-how | know-how | know-how | saber-fazer | type de page. |
| mode (type de page) | failure mode | arıza modu | modo di guasto | modo de avaria |  |
| composant | component | bileşen | componente | componente |  |
| ingestion | ingestion | işleme alma | acquisizione | ingestão | lecture d'un OT clôturé par l'IA. |
| journal du wiki | wiki log | wiki günlüğü | registro del wiki | registo do wiki |  |
| en file | queued | sırada | in coda | em fila |  |
| à valider | to be validated | onaylanacak | da convalidare | por validar |  |
| appliquée / validée | applied / validated | uygulandı / onaylandı | applicata / convalidata | aplicada / validada |  |
| refusée | declined | reddedildi | rifiutata | recusada | décision humaine ; pas « rejected ». décision humaine ; tr « reddedildi », rejet automatique : « elendi ». |
| rejetée | rejected | elendi | scartata | rejeitada | rejet automatique (contrôles). |
| à refaire | to be redone | yeniden yapılacak | da rifare | a refazer |  |
| rien à ajouter | nothing to add | eklenecek bir şey yok | niente da aggiungere | nada a acrescentar |  |
| archivée | archived | arşivlendi | archiviata | arquivada |  |
| rubrique | heading | alt başlık | intestazione | cabeçalho | titre `## …` d'une page ; pas « section » (réservé à l'écran). |
| ancrage | anchor | çapa | ancoraggio | âncora |  |
| requête (envoyée à l'IA) | AI request | YZ isteği | richiesta all'IA | pedido à IA | pour ne pas confondre avec la demande (work request). |
| savoir-faire (pages) | know-how pages | know-how sayfaları | pagine know-how | páginas de saber-fazer |  |
| tranchée / à trancher | settled / to be settled | karara bağlandı / karara bağlanacak | risolta / da risolvere | decidida / por decidir | contradictions du wiki. |
| rang de traitement | processing order | işlem sırası | ordine di elaborazione | ordem de tratamento | colonne du journal du wiki. |
| Créée le / Traitée le / Décidé par | Created on / Processed on / Decided by | Oluşturulma / İşlenme / Karar veren | Creata il / Elaborata il / Deciso da | Criada em / Tratada em / Decidido por | journal du wiki ; pour une suggestion, « Traitée le » : Dealt with on. suggestion : « Traitée le » = Ele alındı / Gestita il / Tratada em. |
| essai(s) | attempt(s) | deneme | tentativo/i | tentativa(s) | pas « try » ni « trial ». tr : pas de pluriel après un nombre. |
| faits (suggestions) | events | olaylar | eventi | eventos | pannes, anomalies, visites. |
| suggestion traitée | dealt with | ele alındı | gestita | tratada |  |
| refus (de l'IA) | rejected | eleme | scarto | rejeição | refus automatique ; comparer « refusée » : declined. |

## 10. Interface et actions courantes

| fr | en | tr | it | pt-PT | remarque |
|---|---|---|---|---|---|
| accueil | home | Ana sayfa | Home | Início |  |
| écran | screen | ekran | schermata | ecrã |  |
| menu | menu | menü | menu | menu |  |
| enregistrer | save | Kaydet | Salva | Guardar |  |
| annuler | cancel | İptal | Annulla | Cancelar | bouton ; pour un OT : « cancel the work order ». OT : tr « iptal et » ; it « annullare » ; pt-PT « cancelar ». |
| modifier | edit | Düzenle | Modifica | Editar |  |
| ajouter | add | Ekle | Aggiungi | Adicionar |  |
| supprimer | delete | Sil | Elimina | Eliminar |  |
| désactiver | deactivate | Devre dışı bırak | Disattiva | Desativar |  |
| fermer | close | Kapat | Chiudi | Fechar |  |
| continuer | continue | Devam | Continua | Continuar |  |
| confirmer | confirm | Onayla | Conferma | Confirmar |  |
| actualiser | refresh | Yenile | Aggiorna | Atualizar |  |
| imprimer | print | Yazdır | Stampa | Imprimir |  |
| importer / exporter | import / export | İçe aktar / Dışa aktar | Importa / Esporta | Importar / Exportar |  |
| valider | validate | Doğrula | Convalida | Validar | validation humaine (wiki, formulaire). Si « Valider » ferme une saisie : « confirm ». tr « Doğrula », pour ne pas confondre avec « Onayla » (confirmer). |
| clôturer | close | Kapat | Chiudi | Encerrar | « clôturer techniquement » : close technically ; « administrativement » : close administratively. « clôturer techniquement » : teknik olarak kapat / chiudere tecnicamente / encerrar tecnicamente. |
| rouvrir | reopen | Yeniden aç | Riapri | Reabrir |  |
| démarrer | start | Başlat | Avvia | Iniciar |  |
| accepter / refuser | accept / decline | Kabul et / Reddet | Accetta / Rifiuta | Aceitar / Recusar | demandes. |
| libellé | label | etiket | etichetta | etiqueta | nom court. |
| titre | title | Başlık | Titolo | Título |  |
| description | description | Açıklama | Descrizione | Descrição |  |
| commentaire | comment | Yorum | Commento | Comentário |  |
| observations | observations | gözlemler | osservazioni | observações |  |
| données de démo | demo data | demo verileri | dati demo | dados de demonstração |  |
| dossier de données | data folder | veri klasörü | cartella dei dati | pasta de dados |  |
| dictée | dictation | sesli dikte | dettatura | ditado | saisie vocale. |
| signaler un problème | report a problem | Sorun bildir | Segnala un problema | Comunicar um problema |  |
| menu « Signaler » | Report a problem | Sorun bildir | Segnala un problema | Comunicar um problema | le menu court a le même libellé que l'écran, pour ne pas entrer en collision avec « Report » (rapport). |
| lots 1 à 4 (À propos) | phases 1 to 4 | aşamalar 1 ila 4 | fasi da 1 a 4 | fases 1 a 4 | pas « batch ». |
| ligne (d'un fichier ou d'un tableau) | row | satır | riga | linha | « line » reste pour la ligne de production, une ligne de journal ou de commande. |
| ligne refusée (import) | rejected | elendi | scartata | rejeitada |  |
| doublon sûr / supposé | certain / probable duplicate | kesin / olası kopya | duplicato certo / probabile | duplicado certo / provável |  |
| feuilles du modèle | Data, Help | Veri, Yardım | Dati, Guida | Dados, Ajuda |  |
| aucun… pour le moment | no … yet | henüz … yok | ancora nessun/a … | ainda sem … | « Aucune demande pour le moment » : No requests yet. « Aucune demande pour le moment » : Henüz talep yok / Ancora nessuna richiesta / Ainda sem pedidos. |
| (non choisi) | (none selected) | (seçilmedi) | (non selezionato) | (não selecionado) |  |
| champ obligatoire | required field | zorunlu alan | campo obbligatorio | campo obrigatório |  |
| abîmé (fichier) | damaged | hasarlı | danneggiato/danneggiata | danificado/danificada | « Fichier abîmé » : damaged file. « Fichier abîmé » : hasarlı dosya / file danneggiato / ficheiro danificado. |

## 11. Statuts et valeurs de listes

| fr | en | tr | it | pt-PT | remarque |
|---|---|---|---|---|---|
| Créé | Created | Oluşturuldu | Creato/Creata | Criado/Criada | OT. OT : it masculin, pt-PT féminin (même règle pour toute la série). |
| Préparé | Prepared | Hazırlandı | Preparato/Preparata | Preparado/Preparada | OT : tout est prêt. |
| Planifié | Scheduled | Planlandı | Pianificato/Pianificata | Agendado/Agendada | OT. |
| En cours | In progress | Devam ediyor | In corso | Em curso | OT. |
| En attente | On hold | Beklemede | In attesa | Em espera | OT. |
| Annulé | Cancelled | İptal edildi | Annullato/Annullata | Cancelado/Cancelada | OT, orthographe britannique (deux « l »). |
| Clôturé techniquement | Technically closed | Teknik olarak kapatıldı | Chiuso/Chiusa tecnicamente | Encerrado/Encerrada tecnicamente | OT. |
| Clôturé administrativement | Administratively closed | İdari olarak kapatıldı | Chiuso/Chiusa amministrativamente | Encerrado/Encerrada administrativamente | OT. |
| Nouvelle | New | Yeni | Nuova | Novo | demande. demande : it féminin (richiesta), pt-PT masculin (pedido). |
| Acceptée | Accepted | Kabul edildi | Accettata | Aceite | demande. |
| Refusée | Declined | Reddedildi | Rifiutata | Recusado | demande. |
| Différée | Deferred | Ertelendi | Rinviata | Adiado | demande. |
| Regroupée | Merged | Birleştirildi | Accorpata | Agrupado | demande. |
| P1 / P2 / P3 / P4 | P1 / P2 / P3 / P4 | P1 / P2 / P3 / P4 | P1 / P2 / P3 / P4 | P1 / P2 / P3 / P4 | priorités ; « Priorité P1 » : Priority P1. |
| arrêt / dégradé / gêne / sécurité | stoppage / degraded / disruption / safety | durma / düşük performans / aksama / güvenlik | fermo / degradato / intralcio / sicurezza | paragem / degradado / perturbação / segurança | impact d'une demande. |
| entrée / sortie / inventaire / retour | receipt / issue / stocktake / return | giriş / çıkış / sayım / iade | carico / scarico / inventario / reso | entrada / saída / inventário / devolução | types de mouvement de stock. |
| commandée / demandée / reçue | ordered / requested / received | sipariş verildi / talep edildi / teslim alındı | ordinato / richiesto / ricevuto | encomendada / pedida / recebida | statuts d'un achat. |
| date / compteur / seuil | date / meter / threshold | tarih / sayaç / eşik | data / contatore / soglia | data / contador / limiar | déclencheurs de gamme. |
| décision / ingestion / manuel | decision / ingestion / manual | karar / işleme alma / manuel | decisione / acquisizione / manuale | decisão / ingestão / manual | nature d'une entrée du journal du wiki. |
| IA / IA et manuel / manuel | AI / AI and manual / manual | YZ / YZ ve manuel / manuel | IA / IA e manuale / manuale | IA / IA e manual / manual | origine d'une page du wiki. |

## 12. Nouveautés de la 2.2 : réserves, catalogue, habilitations, garanties, coût de l'arrêt

Termes relevés tels qu'ils sont déjà écrits dans `js/i18n/*.js` (T488) ; le glossaire suit les dictionnaires, il ne les corrige pas. Les écarts entre écrans sont signalés dans la colonne « remarque ».

| fr | en | tr | it | pt-PT | remarque |
|---|---|---|---|---|---|
| réserve (d'un contrôle) | finding | bulgu | rilievo | reserva | une observation à lever relevée lors d'un contrôle. Table « Réserves des contrôles » : inspection findings / kontrol bulguları / rilievi delle verifiche / reservas das inspeções. pt-PT garde « reserva » (usage portugais). |
| lever une réserve, levée | clear, clearing | gidermek, giderme | risolvere, risoluzione | resolver, resolução | « Lever la réserve » : Clear the finding / Bulguyu gider / Risolvi il rilievo / Resolver a reserva. « à lever » : to be cleared / giderilecek / da risolvere / por resolver. Même verbe que « levée d'observations » (section 4). |
| catalogue (Prévo) | catalogue | katalog | catalogo | catálogo | catalogue de contrôles et de types d'habilitation, réglementation française. Anglais britannique : catalogue. Rien n'est changé sans l'utilisateur. |
| nature de la source | source type | kaynağın niteliği | natura della fonte | natureza da fonte | libellé du champ (contrôles et habilitations). Valeurs : voir les trois lignes suivantes. |
| obligation réglementaire | legal requirement | yasal zorunluluk | obbligo di legge | obrigação legal | valeur de « nature de la source ». |
| norme | standard | standart | norma | norma | valeur de « nature de la source ». |
| recommandation | recommendation | tavsiye | raccomandazione | recomendação | valeur de « nature de la source ». |
| à confirmer | to be confirmed | onaylanacak | da confermare | a confirmar | seul emploi relevé : proposition de l'IA à l'import (« proposée par l'IA : à confirmer »). La formule « à confirmer avec votre organisme de contrôle » n'existe pas encore dans les dictionnaires : à traduire avec ce terme quand elle sera écrite. |
| relu le (catalogue) | reviewed on | gözden geçirildi | riletto il | relido em | « relu le {date} » : reviewed on {date} / {date} tarihinde gözden geçirildi / riletto il {date} / relido em {date}. Champ « Catalogue relu le » : Catalogue reviewed on. |
| habilitation exigée | authorisation required | gerekli yetkilendirme | abilitazione richiesta | habilitação exigida | habilitation demandée par l'OT. Cohérent avec « habilitation » (section 5). |
| passer outre, dérogation | override | kuralı aşmak, istisna | deroga | exceção | bouton « Passer outre et enregistrer » : Override and save / Kuralı aş ve kaydet / Deroga e salva / Abrir exceção e guardar. « Motif de la dérogation » : Reason for the override / İstisna gerekçesi / Motivo della deroga / Motivo da exceção. |
| recyclage (habilitation) | refresher interval | yenileme | aggiornamento | reciclagem | durée en mois entre deux remises à niveau : « Recyclage (mois) » : Refresher interval (months). |
| justificatif | supporting document | dayanak belge | giustificativo | comprovativo | pièce jointe à une habilitation (titre, attestation, CACES). |
| autorisation de conduite | operating authorisation | kullanma yetkisi | autorizzazione alla conduzione | autorização de condução | délivrée par l'employeur ; le CACES en est un justificatif. |
| garantie | warranty | garanti | garanzia | garantia | « Fin de garantie » : Warranty end / Garanti bitişi / Fine garanzia / Fim da garantia. |
| contrat de prestataire | service contract | hizmet sözleşmesi | contratto di servizio | contrato de prestador | pt-PT : « prestador » (de serviços). |
| préavis (de résiliation) | termination notice | fesih ihbarı | preavviso di recesso | pré-aviso de rescisão | délai en mois. Anglais : « Termination notice » (champ) mais « Notice period » (fiche du contrat) : à unifier. |
| date limite de résiliation | termination deadline | fesih için son tarih | termine ultimo di recesso | data limite de rescisão | fin − préavis. « préavis dépassé » : notice deadline passed / ihbar süresi geçti / termine di recesso superato / pré-aviso ultrapassado. |
| reconduction tacite | automatic renewal | otomatik yenileme | rinnovo tacito | renovação tácita | le contrat se renouvelle seul s'il n'est pas résilié. |
| coût de l'arrêt | downtime cost | duruş maliyeti | costo del fermo | custo da paragem | indicateurs et rapport mensuel. |
| coût d'une heure d'arrêt | downtime cost per hour | bir saatlik duruş maliyeti | costo di un'ora di fermo | custo de uma hora de paragem | champ de l'équipement. |
| non chiffré | not costed | maliyetlendirilmemiş | non quantificato | não quantificado | équipement sans coût d'une heure d'arrêt. |
| aide au suivi | aid to keeping track | takip yardımcısı | aiuto al monitoraggio | ajuda ao acompanhamento | « Prévo est une aide au suivi ; la responsabilité reste celle de l'employeur. » |

Incohérences relevées entre écrans (aucune corrigée ici) :

- **Préavis, anglais** : « Termination notice (months) » (champ du schéma) contre « Notice period » (fiche du contrat, avertissement) ; le turc, l'italien et le portugais sont constants.
- **Autorisation, anglais** : « habilitation » et « autorisation de conduite » donnent tous deux « authorisation » (« operating authorisation » pour la seconde) ; sans ambiguïté en italien, portugais et turc (yetkilendirme / yetki).
- **Dérogation, turc** : « Kuralı aş » (bouton) contre « istisna » (motif, bandeau) ; l'italien et le portugais emploient « deroga » / « exceção » partout (le bouton pt-PT dit « Abrir exceção »).
- **Réserve, turc** : « bulgu » traduit aussi « observation » ; pas de distinction réserve / observation.
- **Justificatif, turc** : « dayanak belge » rappelle « dayanak metin » (texte de référence, section 4).

## Choix tranchés par Nicolas (06/11/2026)

Nicolas a retenu les choix par défaut ci-dessous ; le glossaire ci-dessus les applique. L'autre option reste notée pour mémoire.

1. **consignation** [tr « enerji izolasyonu (LOTO) », it « messa in sicurezza (LOTO) », pt-PT « consignação »] : défaut « isolation » ; autre « lockout/tagout (LOTO) ». « Isolation » est le terme britannique (isolation, lock-off) ; LOTO est surtout américain.
2. **habilitation** [tr « yetkilendirme », it « abilitazione », pt-PT « habilitação »] : défaut « authorisation » ; autre « qualification » ou « certification ». « Authorised person » est l'usage britannique pour l'électricité ; « qualification » ferait penser à un diplôme.
3. **demande d'intervention (DI)** [tr « iş talebi », it « richiesta di intervento », pt-PT « pedido de intervenção »] : défaut « work request » ; autre « maintenance request ». Plus court, et cohérent avec « work order ».
4. **gamme** [tr « bakım planı », it « piano di manutenzione », pt-PT « gama de manutenção »] : défaut « task list » ; autres « job plan » (IBM Maximo), « procedure ». « Task list » est neutre et couvre aussi les listes de contrôle.
5. **ordre de travail (OT)** [tr « iş emri », it « ordine di lavoro (OdL) », pt-PT « ordem de trabalho (OT) »] : défaut « work order » (« WO ») ; autre « job » (« job card »). « Work order » est le terme standard des GMAO.
6. **repère** [tr « ekipman kodu », it « codice », pt-PT « código »] : défaut « tag » ; autres « asset number », « equipment ID ». « Tag » est court et courant dans les ateliers.
7. **parc** [tr « ekipman envanteri », it « parco attrezzature », pt-PT « parque de equipamentos »] : défaut « equipment register » ; autres « asset register », « plant ». Le menu court dirait « Equipment » : à confirmer.
8. **magasin** [tr « depo », it « magazzino », pt-PT « armazém »] : défaut « stores » ; autres « storeroom », « warehouse ». « Stores » est l'usage britannique en maintenance.
9. **contrôle réglementaire** [tr « yasal kontrol », it « verifica di legge », pt-PT « inspeção regulamentar »] : défaut « statutory inspection » ; autre « regulatory check ». « Statutory » est l'usage britannique pour les contrôles imposés par la loi.
10. **technicien** [tr « teknisyen », it « tecnico », pt-PT « técnico »] : défaut « technician » ; autre « engineer ». « Engineer » est très courant au Royaume-Uni (« maintenance engineer »), mais peut sembler trop élevé pour un technicien.
11. **responsable** [tr « sorumlu », it « responsabile », pt-PT « responsável »] : défaut « manager » ; autres « supervisor », « maintenance manager ». Le profil règle les paramètres : « manager » suffit.
12. **inventaire** (comptage de stock) [tr « sayım », it « inventario », pt-PT « inventário »] : défaut « stocktake » ; autre « stock count ». « Stocktake » est britannique ; « inventory » serait un faux ami (= le stock).
13. **panne** [tr « arıza », it « guasto », pt-PT « avaria »] : défaut « breakdown » ; autre « failure ». « Breakdown » est la panne vécue sur le terrain ; « failure » est gardé pour les codes de défaillance.
14. **poste** (autre ordinateur du réseau) [tr « iş istasyonu », it « postazione », pt-PT « estação de trabalho »] : défaut « workstation » ; autres « device », « computer ». « Workstation » est un peu formel, mais sans ambiguïté.
