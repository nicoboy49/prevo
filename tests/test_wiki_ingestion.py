"""Ingestion du wiki : file, pages concernées, antériorité, données envoyées, ordonnanceur, traitement de la file
(lot 6 refondu, tâche T115 ; refonte 2, tâche T134 ; ARCHITECTURE.md §20.5, §20.12 ; D104, D111, D112 ; CS99, CS110).

    liste blanche : la requête d'un OT contient son astuce, son compte rendu, ses codes, le symptôme de sa DI, les
                    pièces consommées (sorties − retours), les pages concernées et le catalogue ; jamais le nom d'un
                    technicien ou d'un demandeur, un coût, un taux horaire, une valeur, le numéro de série, les
                    consignes, la consignation, la description ou la photo de la DI, un document ; les rubriques de la
                    consigne sont celles de Wiki.RUBRIQUES ;
    consigne      : (refonte 2) elle ne demande que « En bref » et « Astuces » de la machine, « À quoi il sert » des
                    articles consommés et des savoir-faire (seule page créée) ; aucune limite en dur ; schéma : un
                    savoir-faire seulement à la création ; (suites de la relecture de T134) une astuce à un seul endroit
                    (« Astuces » ou un savoir-faire), « À quoi il sert » sans rien d'inventé, relevés d'un préventif
                    écartés, liens inconnus sans crochets ; ce qu'un OT peut créer est dans le message utilisateur, tiré
                    de Wiki.SEUILS et de Wiki.LIMITES ; elle cite chaque entrée de Wiki.VOCABULAIRE_SECURITE, et la
                    tournure qu'elle propose pour arrêter la machine passe les contrôles (savoir-faire d'une machine ou
                    d'un article) ; (T140, avant la fabrication payante) règle des nombres = celle du contrôle (OT à
                    intégrer et texte actuel de la page écrite ; page créée : l'OT seul) et raison du refus qui le dit ;
                    « À quoi il sert » sans historique (une page non renvoyée reste inchangée, une page qui a des
                    phrases renvoyée vide est refusée) ; issues d'une rubrique pleine (chacune passe les contrôles),
                    relevés que l'OT dit anormaux, astuce ni dans « À quoi il sert », comptage même dans une étape,
                    fréquence, titre et création d'un savoir-faire ; définition astuce / savoir-faire dite une fois ;
                    (suites de la relecture de T140) « En bref » : ses pannes et ce qui les a réglées (plus « ce qui
                    revient ») ; nombres d'une sous-page créée ; titre d'un lien ; astuce sans adverbe de fréquence ;
                    savoir-faire créé pour deux gestes de l'astuce ou du compte rendu ; « petit nettoyage
                    complémentaire » ; une page renvoyée inchangée compte comme non renvoyée (« rien à ajouter » s'il
                    ne reste rien) ; (T141, D116) un seul savoir-faire par geste, commun aux machines, titre sans
                    repère, complété (« Particularités par machine », étapes) et jamais recréé, lien s'il n'est qu'au
                    catalogue, rattaché à l'article principal du geste sinon à la machine ; (T142, D117) « En bref »
                    réécrit en entier, règle de la rubrique pleine et « garde toutes ses phrases » hors « En bref » ;
                    message système sous 9 000 caractères ;
    pages         : clés et pages envoyées d'un OT dans l'ordre de priorité (sa machine, ses articles consommés, les
                    savoir-faire de la machine puis des articles — par ancrage ou par rattachement —, chacun suivi de
                    ses sous-pages), plus de cause, de mode ni de page liée depuis la machine ; page archivée exclue,
                    ancienne sous-page d'équipement non envoyée, plafond des pages envoyées ; (T141) puis les
                    savoir-faire dont le texte a un lien vers la machine, puis vers ses articles (un lien d'une sous-page
                    amène sa mère), puis ceux du même geste (Wiki.memeGeste, 2 au plus) : un OT de PO-01 reçoit
                    « Remplacer une garniture mécanique » créé pour PO-02 ; un savoir-faire créé pendant l'envoi et
                    concerné sur le nouvel état fait rejouer l'OT ;
    longueurs     : l'en-tête de chaque texte donne la mesure de chaque rubrique et sa limite (Wiki.LIMITES), celles
                    d'un savoir-faire entier, et « à réécrire en entier » pour « En bref » (D117) ; le faux modèle s'y
                    tient (« En bref » réécrit, les plus anciennes phrases retirées au-delà) ; une réponse qui réécrit
                    « En bref » en retirant ses phrases et ses OT d'avant est acceptée ; « Astuces » pleine : chaque
                    issue de la consigne passe ;
    catalogue     : machines, articles, savoir-faire et pannes (codes symptôme qui ont un cas : les pages Panne de
                    Wiki.listeEntites, seule définition — prouvée par un bouchon « Panne sentinelle », T140) ; ni
                    technicien, ni intervention, ni ancienne page de mode ou libre ; un lien [[<panne>]] est accepté ;
    file          : ordre par date d'intervention puis numéro d'OT, quel que soit l'ordre de mise en file ou de
                    clôture (OT importés compris) ; OT non clôturé administrativement, inconnu ou déjà intégré écarté ;
    antériorité   : mention et dates pour un OT plus ancien que les faits de SES pages ; aucune mention si les OT plus
                    récents sont ailleurs ; « Désormais » refusé pour lui seul ;
    ordonnanceur  : prochainsEnvois (plafond d'agents, clés prises par un envoi en cours ou par une entrée plus
                    ancienne restée en attente) ;
    traitement    : bout en bout avec le faux fournisseur (requêtes réellement envoyées, état proposé enchaîné,
                    antériorité notée, ordre par page, aucune page dans deux envois à la fois ; tous les textes de la
                    refonte 2 acceptés, chaque astuce à un seul endroit ; ancien texte réécrit dans ses rubriques
                    accepté, lien connu gardé, lien inconnu sans crochets) ; refus → « refusée »
                    avec ses raisons ; collision → « en file » avec le motif puis acceptée, et « refusée » après trois
                    collisions ; IA injoignable → arrêt, OT laissés en file ;
    relance       : (D106 révisée, CS112) une réponse refusée par les contrôles, ou illisible, est redemandée une fois
                    par une requête neuve — même message système et même schéma, message d'origine suivi de la réponse
                    refusée et de chaque raison, rien d'autre — dans le même envoi ; corrigée → « à valider », 2 essais,
                    raisons du premier refus gardées ; refusée deux fois → « refusée » avec les raisons du second refus ;
                    jamais plus d'une relance ; une collision est rejouée, jamais relancée ; « Arrêter » retient la
                    relance (OT laissé en file), `annuler` la coupe ;
    clôture       : la clôture administrative d'un OT le met en file ; un échec de la mise en file n'annule pas la
                    clôture (message, OT « hors du wiki ») ;
    trois modes   : la requête de chaque OT clôturé administrativement de la démo est la même en modes démo, dossier
                    et serveur (mêmes fichiers).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_wiki_ingestion.py" -v
"""
import csv
import io
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from commun import (CasNavigateur, RACINE, ServeurPrevo, ServeurStatique, attendre_pret, charger_scripts,
                    installer_dossier_simule, port_libre, preregler_profil, url_fichier)
from faux_fournisseur_ia import FauxFournisseur
from faux_wiki import lire_message, reponse_ingestion

SCRIPTS = [
    "js/lib/papaparse.min.js", "js/schema.js", "js/donnees.js", "js/stockage-demo.js",
    "js/modules/causes-frequentes.js", "js/modules/indicateurs-regles.js", "js/modules/ia.js", "js/modules/ia-prompts.js",
    "js/modules/wiki-regles.js", "js/modules/wiki-calculs.js", "js/modules/wiki-entites.js", "js/modules/wiki-texte.js",
    "js/modules/wiki-recherche.js",
    "js/modules/wiki-ingestion.js",
]
NL = chr(10)
MENTION = "Intervention antérieure à des faits déjà intégrés"


def table_csv(entete, lignes):
    """Texte CSV de Prévo (« ; », CRLF, guillemets RFC 4180 si besoin)."""
    sortie = io.StringIO()
    ecrivain = csv.writer(sortie, delimiter=";", lineterminator="\r\n")
    ecrivain.writerow(entete.split(";"))
    for ligne in lignes:
        ecrivain.writerow(ligne.split(";") if isinstance(ligne, str) else ligne)
    return sortie.getvalue()


def regler_ia(contexte, **reglages):
    """Réglages IA du poste (localStorage prevo.ia) avant tout chargement de page."""
    valeur = dict(actif=True, fournisseur="ollama", modele="faux", cle="", delaiS=30)
    valeur.update(reglages)
    contexte.add_init_script(
        "(() => { try { if (localStorage.getItem('prevo.ia') === null) "
        "localStorage.setItem('prevo.ia', %s); } catch (erreur) { /* about:blank */ } })();"
        % json.dumps(json.dumps(valeur)))


# ---------------------------------------------------------------------------------------------------
# Base d'essai : valeurs « sentinelles » dans tout ce qui ne doit jamais partir
# ---------------------------------------------------------------------------------------------------

INTERDITS = ["Zéphyrin", "Ledoux", "Hortense", "Valmy", "1234.56", "1234,56", "987.65", "77.77", "45678", "SN-SECRET-4711",
             "Cadenasser Q1", "Consigner et purger", "plan-secret.pdf", "photo-secrete.jpg", "Description privée Q9",
             "TEC-0001", "DI-2026-0001", "3.75"]
ASTUCE = "Aligner l'accouplement au repère avant la dépose."
# Titre du savoir-faire commun que le faux modèle tire de cette astuce (son premier geste, T141).
GESTE = "Aligner l'accouplement au repère avant la dépose"

EQUIPEMENTS = table_csv("id;repere;designation;marque;modele;num_serie;statut;consignation;document;actif;valeur_remplacement", [
    "EQ-0001;'PO-01;Pompe de process A;Hydro Nel;HC 50;SN-SECRET-4711;en service;Cadenasser Q1;plan-secret.pdf;1;45678.9",
    "EQ-0002;'CP-01;Compresseur;;;;en service;;;1;",
    "EQ-0003;'CV-01;Convoyeur;;;;en service;;;1;",
])
CODES = table_csv("id;famille;code;libelle", [
    "CD-0001;symptôme;S01;Fuite", "CD-0002;symptôme;S02;Bruit anormal",
    "CD-0008;symptôme;S03;Vibration",                               # aucun OT : pas de page Panne, hors du catalogue
    "CD-0003;cause;C01;Garniture usée", "CD-0004;cause;C02;Encrassement", "CD-0005;cause;C03;Desserrage",
    "CD-0006;remède;R01;Remplacement de la pièce", "CD-0007;remède;R02;Nettoyage",
])
TECHNICIENS = table_csv("id;nom;prenom;metier;taux_horaire;capacite_h_semaine;actif",
                        ["TEC-0001;Ledoux;Zéphyrin;mécanicien;77.77;35;1"])
DEMANDES = table_csv("id;date_heure;demandeur;equipement_id;symptome;impact;description;photo;statut;ot_id;symptome_code",
                     ["DI-2026-0001;2026-03-09 07:00;Hortense Valmy;EQ-0001;Goutte sous la pompe;;Description privée Q9;"
                      "photo-secrete.jpg;Acceptée;OT-2026-0001;S01"])
ENTETE_OT = ("id;equipement_id;type;priorite;statut;titre;travail_a_faire;consignes;date_creation;date_fin;technicien_id;"
             "di_id;duree_arret_h;symptome_code;cause_code;remede_code;compte_rendu;cout_soustraitance;date_cloture_tech;"
             "date_cloture_admin;astuce")
ORDRES = table_csv(ENTETE_OT, [
    ["OT-2026-0001", "EQ-0001", "correctif immédiat", "P1", "Clôturé administrativement", "PO-01 — Fuite à la garniture",
     "Changer la garniture", "Consigner et purger", "2026-03-09 08:00", "2026-03-10 10:00", "TEC-0001", "DI-2026-0001",
     "2.5", "S01", "C01", "R01", "Garniture usée remplacée, fuite stoppée.", "1234.56", "2026-03-10 11:00",
     "2026-03-20 09:00", ASTUCE],
    # Même date d'intervention que 0001 : départagé par le numéro.
    "OT-2026-0002;EQ-0002;correctif différé;P2;Clôturé administrativement;CP-01 — Filtre encrassé;;;2026-03-09 08:00;"
    "2026-03-10 10:00;;;;S02;C02;R02;Filtre nettoyé.;;2026-03-10 11:00;2026-03-12 09:00;",
    # Plus ancienne que 0001 mais clôturée administrativement après elle.
    "OT-2026-0003;EQ-0001;correctif différé;P2;Clôturé administrativement;PO-01 — Bruit au démarrage;;;2026-01-30 08:00;"
    "2026-02-01 08:00;;;;S02;C03;R02;Bornes resserrées.;;2026-02-01 09:00;2026-04-01 09:00;",
    # Importée : créée en octobre, intervention en janvier (la plus ancienne).
    "OT-2026-0004;EQ-0003;correctif différé;P3;Clôturé administrativement;CV-01 — Bande desserrée;;;2026-10-01 09:00;"
    "2026-01-15 08:00;;;;S02;C03;R02;Tension reprise.;;2026-10-01 09:00;2026-10-01 09:00;",
    "OT-2026-0005;EQ-0002;correctif différé;P2;Clôturé techniquement;CP-01 — Bruit;;;2026-02-28 08:00;"
    "2026-03-01 08:00;;;;S02;C02;R02;Nettoyé.;;2026-03-01 09:00;;",
    "OT-2026-0006;EQ-0003;correctif différé;P3;Clôturé administrativement;CV-01 — Rouleaux encrassés;;;2026-04-30 08:00;"
    "2026-05-01 08:00;;;;S02;C02;R02;Rouleaux nettoyés.;;2026-05-01 09:00;2026-05-02 09:00;",
    # Déjà intégrée (entrée validée) : citée par les pages de PO-01.
    "OT-2026-0007;EQ-0001;correctif immédiat;P1;Clôturé administrativement;PO-01 — Fuite;;;2026-04-14 08:00;"
    "2026-04-15 08:00;;;;S01;C01;R01;Garniture changée.;;2026-04-15 09:00;2026-04-16 09:00;",
    "OT-2026-0008;EQ-0001;correctif immédiat;P1;Clôturé administrativement;PO-01 — Fuite encore;;;2026-05-31 08:00;"
    "2026-06-01 08:00;;;;S01;C01;R01;Joint repris.;;2026-06-01 09:00;2026-06-02 09:00;",
])
ARTICLES_EN_PLUS = ["ART-%04d;R-%02d;Pièce de convoyeur %s;1.5;;4;1" % (numero, numero, lettre)
                    for numero, lettre in zip(range(4, 13), "ABCDEFGHI")]
ARTICLES = table_csv("id;reference;designation;prix_unitaire;fournisseur_id;stock;actif", [
    "ART-0001;KG-50;Kit garniture HC 50;987.65;FOU-0001;3;1",
    "ART-0002;RL-6205;Roulement 6205;11.11;;10;1",
    "ART-0003;FH-10;Filtre à huile;22.22;;5;1",
] + ARTICLES_EN_PLUS)
MOUVEMENTS = table_csv("id;date;article_id;type;quantite;ot_id;utilisateur;commentaire", [
    "MVT-000001;2026-03-10 09:00;ART-0001;sortie;1;OT-2026-0001;Zéphyrin Ledoux;",
    "MVT-000002;2026-03-10 09:05;ART-0002;sortie;2;OT-2026-0001;;",
    "MVT-000003;2026-03-10 09:30;ART-0002;retour;2;OT-2026-0001;;",          # rendu : pas consommé
    "MVT-000004;2026-03-10 09:00;ART-0003;sortie;1;OT-2026-0002;;",
] + ["MVT-%06d;2026-05-01 07:00;ART-%04d;sortie;1;OT-2026-0006;;" % (numero + 1, numero) for numero in range(4, 13)])
TEMPS = table_csv("id;ot_id;technicien_id;date;heures", ["TPS-000001;OT-2026-0001;TEC-0001;2026-03-10;3.75"])

ENTETE_WIKI = ("id;type;titre;cle;equipement_id;article_id;cause_code;rattache_a;texte;ot_cites;liens;version;origine;"
               "modele;derniere_entree;valide_par;valide_le;cree_le;modifie_le;statut")


def page_wiki(id_, type_, titre, texte="", equipement="", article="", cause="", rattache="", statut="active"):
    return [id_, type_, titre, "", equipement, article, cause, rattache, texte, "", "", "1", "IA" if texte else "", "", "",
            "", "", "2026-04-20 09:00", "2026-04-20 09:00", statut]


# Base de la refonte 2 (§20.12) : « En bref » de PO-01 (avec un lien vers le savoir-faire d'une autre machine, qui n'est
# plus envoyé pour autant), « À quoi il sert » du kit, des savoir-faire ancrés ou rattachés à la machine et aux articles,
# et des pages d'avant la refonte 2 qui ne sont ni envoyées ni au catalogue : deux modes ancrés sur les causes de OT
# (C01, C03) et un composant libre.
TEXTE_PO01 = ("## En bref" + NL + "- Fuite de garniture au démarrage, fréquent ici [OT-2026-0007]" + NL
              + "- Voir [[Nettoyer le filtre de CP-01]] [OT-2026-0007]")
TEXTE_KIT = "## À quoi il sert" + NL + "- Étanchéité de l'arbre de la pompe [OT-2026-0007]"
WIKI_PAGES = table_csv(ENTETE_WIKI, [
    page_wiki("WP-0001", "équipement", "PO-01 — Pompe de process A", TEXTE_PO01, equipement="EQ-0001"),
    page_wiki("WP-0002", "savoir-faire", "Changer la garniture de PO-01", "## Étapes" + NL + "- Repérer l'accouplement [OT-2026-0007]",
              equipement="EQ-0001"),
    page_wiki("WP-0003", "composant", "Kit garniture HC 50", TEXTE_KIT, article="ART-0001"),
    # Rattaché à la page du composant (pas d'article_id) : trouvé par son rattachement.
    page_wiki("WP-0004", "savoir-faire", "Monter le kit garniture", "## Étapes" + NL + "- Lubrifier les joints [OT-2026-0007]",
              rattache="WP-0003"),
    page_wiki("WP-0005", "mode", "Usure de garniture", "## Causes" + NL + "- Garniture usée [OT-2026-0007]", cause="C01"),
    page_wiki("WP-0006", "composant", "Joint torique 20x2", "## Défaillances" + NL + "- Joint pincé [OT-2026-0007]"),
    page_wiki("WP-0007", "mode", "Desserrage", cause="C03"),
    page_wiki("WP-0008", "savoir-faire", "Nettoyer le filtre de CP-01", equipement="EQ-0002"),
    page_wiki("WP-0009", "savoir-faire", "Ancien geste", "## Étapes" + NL + "- Vieux [OT-2026-0007]", equipement="EQ-0001",
              statut="archivée"),
    # Rattaché à la page de l'équipement (pas d'equipement_id) : trouvé par son rattachement.
    page_wiki("WP-0010", "savoir-faire", "Graisser le palier", "## Étapes" + NL + "- Graisser [OT-2026-0007]", rattache="WP-0001"),
    # Ancré sur un article (article_id) : envoyé avec les OT qui le consomment.
    page_wiki("WP-0011", "savoir-faire", "Changer le filtre à huile", article="ART-0003"),
])
JOURNAL_WIKI = table_csv("id;nature;ot_id;date_intervention;statut;anterieure;ordre;pages;changements;contradictions;raisons;"
                         "modele;essais;cree_le;traite_le;decide_par;decide_le;motif",
                         ["WJ-00001;ingestion;OT-2026-0007;2026-04-15 08:00;validée;0;1;EQ:EQ-0001;[];[];;faux;1;"
                          "2026-04-16 09:00;2026-04-16 09:05;Responsable;2026-04-17 09:00;"])

BASE = {"equipements": EQUIPEMENTS, "codes_defaillance": CODES, "techniciens": TECHNICIENS, "demandes": DEMANDES,
        "ordres_travail": ORDRES, "articles": ARTICLES, "mouvements_stock": MOUVEMENTS, "ot_temps": TEMPS,
        "wiki_pages": WIKI_PAGES, "wiki_journal": JOURNAL_WIKI, "parametres": table_csv("cle;valeur", ["version_schema;3"])}
EN_FILE = ["OT-2026-0004", "OT-2026-0003", "OT-2026-0001", "OT-2026-0002", "OT-2026-0006", "OT-2026-0008"]

CHARGER_JS = """async (tables) => {
  Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Poste test', profil: 'Responsable test' });
  await Donnees.chargerTout();
}"""
DONNEES_JS = "(ot) => Wiki.donneesIngestion(ot)"
REQUETE_JS = "(ot) => Ia.requete('ingestionWiki', Wiki.donneesIngestion(ot))"
LIRE_JS = """([ot, contenu]) => { const d = Wiki.donneesIngestion(ot);
  try { return { ok: true, lu: Ia.lireReponse('ingestionWiki', contenu, d) }; }
  catch (e) { return { ok: false, nom: e.name, raisons: e.raisons || [e.message] }; } }"""
TRAITER_JS = """async ([ids, options]) => {
  await Wiki.mettreEnFile(ids);
  // Un traitement qui ne finit pas (relance sans fin) échoue au lieu de bloquer le test.
  const delai = new Promise((_, rejeter) => setTimeout(() => rejeter(new Error('traiterFile ne finit pas')), 60000));
  const b = await Promise.race([Wiki.traiterFile(options || {}), delai]);
  return { acceptees: b.acceptees, rien: b.rien, refusees: b.refusees, rejouees: b.rejouees, envois: b.envois,
    erreur: b.erreur ? { nom: b.erreur.name, message: b.erreur.message } : null };
}"""
JOURNAL_JS = "() => Donnees.lignes('wiki_journal').filter((e) => e.nature === 'ingestion' && e.ot_id !== 'OT-2026-0007')"
# Stockage dont chaque écriture prend 50 ms : deux résultats peuvent s'écrire en même temps (course de D112).
CHARGER_LENT_JS = """async (tables) => {
  const stockage = StockageDemo.creer(tables);
  const enregistrer = stockage.enregistrer;
  stockage.enregistrer = async function () { await new Promise((r) => setTimeout(r, 50)); return enregistrer.apply(this, arguments); };
  Donnees.initialiser(stockage, { poste: 'Poste test', profil: 'Responsable test' });
  await Donnees.chargerTout();
}"""
RIEN = "JSON.stringify({ rien_a_ajouter: true, pages: [], contradictions: [] })"
# Sous-pages (§20.4 ; savoir-faire seulement, §20.12) : deux validées (du savoir-faire de PO-01 et de celui du kit HC 50),
# une « à valider », créée avant la modification de sa mère dans les changements de son entrée (l'ordre ne compte pas),
# et une ancienne sous-page d'équipement (d'avant la refonte 2), qui n'est plus envoyée.
SOUS_PAGES_JS = """async () => {
  const NL = String.fromCharCode(10);
  const page = (id, type, titre, texte, rattache) => ({ id, type, titre, texte, rattache_a: rattache, version: '1',
    statut: 'active', origine: 'IA' });
  await Donnees.modifier('wiki_pages', (lignes) => {
    lignes.push(page('WP-0020', 'savoir-faire', 'Changer la garniture de PO-01 — dépose', '## Étapes' + NL
      + '- Déposer le kit usé [OT-2026-0007]', 'WP-0002'));
    lignes.push(page('WP-0021', 'savoir-faire', 'Monter le kit garniture — faces', '## Pièges' + NL + '- Faces rayées [OT-2026-0007]',
      'WP-0004'));
    lignes.push(page('WP-0022', 'équipement', 'PO-01 — garniture', '## Ce qui revient' + NL + '- Garniture sèche [OT-2026-0007]',
      'WP-0001'));
  });
  await Donnees.modifier('wiki_journal', (lignes) => { lignes.push({ id: 'WJ-00002', nature: 'ingestion', ot_id: 'OT-2026-0003',
    statut: 'à valider', ordre: '2', essais: '1', changements: JSON.stringify([
      { cle: 'TITRE:graisser le palier frequence', titre: 'Graisser le palier — fréquence', type: 'savoir-faire', creation: true,
        rattacheA: 'Graisser le palier', version_avant: 0, avant: '',
        apres: '## Quand le faire' + NL + '- Au bruit de grincement [OT-2026-0003]' },
      { cle: 'WP:WP-0010', page: 'WP-0010', titre: 'Graisser le palier', type: 'savoir-faire', creation: false, version_avant: 1,
        avant: '', apres: '## Étapes' + NL + '- Graisser [OT-2026-0007]' + NL
          + '- Fréquence : voir [[Graisser le palier — fréquence]] [OT-2026-0003]' }]) }); }, { journal: false });
}"""
# Savoir-faire communs (T141, D116) : PO-02 (EQ-0004, sans OT) et ses savoir-faire — « Remplacer une garniture mécanique »
# (le même geste qu'un OT de PO-01 qui parle de garniture mécanique) ; avec `liens` : un savoir-faire dont une phrase de
# « Particularités par machine » renvoie à PO-01, un dont « Pièces et outillage » renvoie au kit, et une sous-page qui
# renvoie à PO-01 (sa mère vient avec elle).
COMMUNS_JS = """async (liens) => {
  const NL = String.fromCharCode(10);
  await Donnees.modifier('equipements', (lignes) => { lignes.push({ id: 'EQ-0004', repere: 'PO-02', designation: 'Pompe de '
    + 'process B', statut: 'en service', actif: '1' }); });
  const page = (id, titre, texte, autres) => Object.assign({ id, type: 'savoir-faire', titre, texte, version: '1',
    statut: 'active', origine: 'IA', equipement_id: 'EQ-0004' }, autres || {});
  await Donnees.modifier('wiki_pages', (lignes) => {
    lignes.push(page('WP-0040', 'Remplacer une garniture mécanique', '## Étapes' + NL + '- Déposer le moteur [OT-2026-0007]'));
    if (!liens) return;
    lignes.push(page('WP-0041', "Contrôler l'alignement d'un accouplement", '## Particularités par machine' + NL
      + '- [[PO-01 — Pompe de process A]] : repère au feutre [OT-2026-0007]'));
    lignes.push(page('WP-0042', 'Stocker les kits à plat', '## Pièces et outillage' + NL + '- [[Kit garniture HC 50]] [OT-2026-0007]'));
    lignes.push(page('WP-0043', 'Régler un palier', '## Étapes' + NL + '- Caler [OT-2026-0007]'));
    lignes.push(page('WP-0044', 'Régler un palier — repères', '## Particularités par machine' + NL
      + '- [[PO-01 — Pompe de process A]] : palier côté moteur [OT-2026-0007]', { equipement_id: '', rattache_a: 'WP-0043' }));
  });
}"""
# Relance avec la raison (§20.5) : ce qui suit le message d'origine.
MARQUE_RELANCE = NL + NL + "Ta réponse précédente :" + NL
REFUS_RELANCE = NL + NL + "Elle a été refusée par les contrôles de Prévo :" + NL
DEMANDE_RELANCE = ("Corrige-la : rends une réponse complète (le même objet JSON, avec le texte complet de chaque page "
                   "modifiée ou créée) qui respecte les règles et ne reproduit aucune de ces erreurs.")


def message_de_relance(origine, reponse, raisons):
    """Message attendu d'une relance : le message d'origine, la réponse refusée, chaque raison sur sa ligne, la demande."""
    return (origine + MARQUE_RELANCE + reponse + REFUS_RELANCE + NL.join("- " + raison for raison in raisons)
            + NL + NL + DEMANDE_RELANCE)


# Astuce de plusieurs gestes (« … puis … ») : le faux modèle (faux-textes) en fait un savoir-faire, pas une ligne d'« Astuces ».
METHODE = "Déposer le moteur, puis nettoyer les faces de la garniture neuve."


def endroits_de(changements, astuce):
    """(titre, rubrique) de chaque phrase des textes proposés dont le texte, citations retirées, est l'astuce."""
    endroits = []
    for changement in changements:
        rubrique = ""
        for ligne in changement["apres"].split(NL):
            if ligne.startswith("## "):
                rubrique = ligne[3:].strip()
            elif ligne.startswith("- ") and re.sub(r"\s*\[OT-\d{4}-\d{4,}\]", "", ligne[2:]).strip() == astuce:
                endroits.append((changement["titre"], rubrique))
    return endroits


class CasIngestion(CasNavigateur):

    def charger(self, tables=None):
        self.requetes = []
        self.page.on("request", lambda requete: self.requetes.append(requete.url))
        charger_scripts(self.page, SCRIPTS)
        self.page.evaluate(CHARGER_JS, tables or BASE)

    def donnees(self, ot):
        return self.page.evaluate(DONNEES_JS, ot)

    def message(self, ot):
        return self.page.evaluate(REQUETE_JS, ot)["messages"][1]["content"]

    def journal(self):
        return {entree["ot_id"]: entree for entree in self.page.evaluate(JOURNAL_JS)}


# ---------------------------------------------------------------------------------------------------
# Données envoyées, pages concernées, file, antériorité, ordonnanceur (sans réseau)
# ---------------------------------------------------------------------------------------------------

class TestDonneesEtFile(CasIngestion):

    def setUp(self):
        super().setUp()
        self.charger()

    def test_liste_blanche_de_la_requete(self):
        d = self.donnees("OT-2026-0001")
        self.assertEqual(sorted(d["ot"]), sorted(["id", "dateIntervention", "type", "equipement", "titre", "travail", "symptome",
                                                  "cause", "remede", "compteRendu", "astuce", "pieces", "dureeArret", "symptomeDI"]))
        self.assertEqual(sorted(d["ot"]["equipement"]), ["designation", "marque", "modele", "repere"])
        self.assertEqual(d["ot"]["pieces"], [{"designation": "Kit garniture HC 50", "reference": "KG-50", "quantite": "1"}])
        requete = self.page.evaluate(REQUETE_JS, "OT-2026-0001")
        self.assertEqual(requete["fonction"], "ingestionWiki")
        message = requete["messages"][1]["content"]
        for attendu in ("OT à intégrer : OT-2026-0001 · intervention du 2026-03-10 10:00 · correctif immédiat",
                        "Équipement : PO-01 — Pompe de process A", "Marque et modèle : Hydro Nel · HC 50",
                        "Titre : PO-01 — Fuite à la garniture", "Symptôme signalé : Goutte sous la pompe",
                        "Travail demandé : Changer la garniture", "Codes : Fuite / Garniture usée / Remplacement de la pièce",
                        "Compte rendu : Garniture usée remplacée, fuite stoppée.", "Astuce pour la prochaine fois : " + ASTUCE,
                        "Pièces consommées : Kit garniture HC 50 (réf. KG-50) × 1", "Durée d'arrêt : 2.5 h",
                        "=== Page « PO-01 — Pompe de process A » (équipement · En bref : 2 phrases sur 3, 13 mots sur 60, "
                        "à réécrire en entier en 45 mots environ · Astuces : 0 phrase sur 10) ===\n" + TEXTE_PO01,
                        "=== Page « Kit garniture HC 50 » (composant · À quoi il sert : 1 phrase sur 3, 6 mots sur 80) ===\n"
                        + TEXTE_KIT,
                        "Catalogue des pages :", "- Fuite (panne)", "- Roulement 6205 (composant)"):
            self.assertIn(attendu, message)
        tout = json.dumps(requete, ensure_ascii=False)
        for interdit in INTERDITS:
            self.assertNotIn(interdit, tout)
        self.assertEqual([u for u in self.requetes if not u.startswith(("file:", "data:"))], [])

    def test_rubriques_de_la_consigne_celles_du_wiki(self):
        systeme = self.page.evaluate(REQUETE_JS, "OT-2026-0002")["messages"][0]["content"]
        for type_, rubriques in self.page.evaluate("Wiki.RUBRIQUES").items():
            self.assertIn(type_ + " « " + " », « ".join(rubriques) + " »", systeme)

    def test_consigne_ne_demande_que_les_textes_de_la_refonte_2(self):
        """§20.12 : l'IA ne rédige que « En bref » et « Astuces » de la machine, « À quoi il sert » des articles consommés
        et des savoir-faire (seule page créée) ; ni mode, ni ancienne rubrique, ni limite en dur ; un texte d'avant la
        refonte se réécrit dans ses rubriques ; le schéma ne permet de créer qu'un savoir-faire."""
        requete = self.page.evaluate(REQUETE_JS, "OT-2026-0001")
        systeme = requete["messages"][0]["content"]
        for attendu in ("« En bref » de la machine (type « équipement ») : ce qu'il faut savoir d'abord de cette machine, "
                        "ses pannes et ce qui les a réglées ; une synthèse, pas un historique",
                        # Suites de la relecture de T134 : astuce ou savoir-faire, jamais les deux.
                        "« Astuces » de la machine : les astuces courtes des OT (« Astuce pour la prochaine fois ») ; chacune, "
                        "un conseil en une phrase propre à cette machine, même s'il porte sur un article",
                        "les savoir-faire : une méthode de plusieurs gestes, un seul par geste, commun aux machines, "
                        "tirée d'abord de l'astuce de l'OT, puis de son travail et de son compte rendu",
                        "au titre exact de l'article reçu principal du geste s'il y en a un, sinon de la machine",
                        # Liens d'un ancien texte ; préventif sans remarque (règles T140 : test_consigne_regles_de_t140).
                        "si l'OT n'apprend rien (préventif ou contrôle de routine sans remarque : gamme faite, relevés sans "
                        "anomalie signalée, usure normale, petit nettoyage complémentaire)",
                        "un lien d'un texte reçu vers un titre absent du catalogue et des pages reçues perd ses crochets (les "
                        "mots restent)",
                        "créer des savoir-faire (action « creer », type « savoir-faire »)",
                        "aucune autre page ne se crée", "le catalogue des titres (machines, articles, pannes, savoir-faire)",
                        "un texte reçu dans d'autres rubriques (ancien wiki) se réécrit dans les siennes en regroupant ses "
                        "phrases, chaque phrase regroupée citant tous les OT des phrases qu'elle reprend",
                        "l'en-tête de chaque page reçue donne la taille et la limite de chaque rubrique",
                        "un lien compte les mots de son titre",
                        "un savoir-faire qui dépasserait ses limites se découpe en sous-pages liées"):
            self.assertIn(attendu, systeme)
        self.assertNotRegex(systeme, r"\bmodes?\b")
        # « ce qui revient » : une fréquence, que la consigne interdit (relecture de T140, M10).
        for absent in ("Ce qui revient", "ce qui revient", "À surveiller", "Défaillances", "Symptômes",
                       "composant absent du catalogue", "sauf comme sous-page", "repère de l'équipement"):
            self.assertNotIn(absent, systeme)
        self.assertNotRegex(systeme, r"\b(5|10|30|60|80|120|600)\b")   # les limites sont dans l'en-tête de chaque texte
        formes = requete["schema"]["properties"]["pages"]["items"]["anyOf"]
        self.assertEqual([(f["properties"]["action"]["enum"], f["properties"]["type"]["enum"]) for f in formes],
                         [(["modifier"], ["équipement", "composant", "savoir-faire"]), (["creer"], ["savoir-faire"])])

    def test_consigne_regles_de_t140(self):
        """T140 (suites de la relecture de 884cedf, avant la fabrication payante par Claude Sonnet) : chaque règle nouvelle ou
        changée est dans la consigne, mot pour mot ; les anciennes formulations n'y sont plus ; la définition d'une astuce
        (un conseil) et d'un savoir-faire (une méthode de plusieurs gestes) n'est dite qu'une fois ; « deux fois » dans une
        étape est refusé par les contrôles comme la consigne le dit ; le message système reste sous 9 000 caractères (8 500
        jusqu'aux suites de la relecture de T140)."""
        systeme = self.page.evaluate(REQUETE_JS, "OT-2026-0001")["messages"][0]["content"]
        for attendu in (
                # C1 : la règle des nombres est celle du contrôle (Wiki.controlerProposition, texte de référence)
                "aucun nombre qui ne figure pas dans l'OT à intégrer ou dans le texte actuel de la page que tu écris (une page "
                "créée, titre compris : dans l'OT à intégrer seulement ; une sous-page créée : aussi dans le texte et le titre "
                "de sa mère) ; un nombre lu sur une autre page reçue ne se recopie pas ; le titre d'un lien [[…]] ne compte "
                "pas ; aucune date, aucun mois, aucune année ;",
                # C3 : « À quoi il sert » sans historique ; une page non changée n'est pas renvoyée
                "« À quoi il sert » de chaque article consommé (type « composant ») : l'OT ne donne que sa désignation et sa "
                "référence ; écris seulement ce que les OT observent de lui (à quoi il sert sur la machine si l'OT le dit, ses "
                "signes d'usure ou de casse, ce qui l'use, comment il se monte ou se change) ; jamais où ni quand il a été "
                "changé, ni la panne qu'il a réglée (Prévo les calcule), ni un rôle supposé ; si l'OT n'en dit rien de plus "
                "que sa consommation, ne renvoie pas sa page ;",
                "ajoute ce que l'OT apprend ; une page que tu ne changes pas ne se renvoie pas ;",
                # M3 (révisée par T142 : hors « En bref ») : issues d'une rubrique pleine (chacune passe les contrôles :
                # test_issues_d_une_rubrique_pleine), qui renvoient à la règle des phrases courtes
                "si l'OT confirme une phrase existante, ajoute seulement son numéro aux OT de cette phrase ; regroupe en une "
                "seule les phrases qui disent la même chose (elle cite tous leurs OT)",
                "ne dépasse jamais une limite ; une rubrique pleine autre que « En bref » : confirme ou regroupe ainsi, ou n'y "
                "écris rien (Prévo calcule déjà les pannes) ;",
                # M4 : relevés (les données ne donnent aucune plage normale)
                "relevés et mesures d'un contrôle de routine — pression, température, jeu… — sauf si l'OT les dit anormaux ou "
                "s'ils expliquent la panne) : c'est dans l'OT ;",
                # M5 et M12 : une astuce à un seul endroit, ni dans « À quoi il sert » ; définition dite une fois
                "Une astuce s'écrit à un seul endroit : dans « Astuces » ou dans un savoir-faire (créé ou complété), jamais aux "
                "deux ni dans « À quoi il sert » ; dans « Astuces », un lien [[titre du savoir-faire]] suffit ; dans une "
                "astuce, dis l'ordre des vérifications ou le geste, sans adverbe de fréquence (« toujours », « plus "
                "vite »).",
                # M8 et M9 : création et titre d'un savoir-faire (titre révisé par T141 : test_consigne_regles_de_t141_et_t142)
                # Relecture de T140 : le travail demandé en liste presque toujours deux, il ne suffit pas.
                "n'en crée un qu'avec au moins deux gestes que l'astuce ou le compte rendu décrivent (le travail demandé seul "
                "ne suffit pas) ;",
                # M6 et M10 : comptage même dans une étape ; aucune fréquence (Prévo la calcule)
                "aucun comptage, même dans une étape (jamais « deux fois », « 3 fois », « 4 OT ») ni aucune fréquence "
                "(« fréquent », « souvent », « régulièrement », « à chaque fois ») : Prévo les calcule ; jamais « cause "
                "certaine » ;",
                # M2 : la tournure d'arrêt vaut pour le savoir-faire d'une machine comme pour celui d'un article
                "une étape qui arrête la machine pour intervenir s'écrit seulement « Mettre la machine à l'arrêt selon la "
                "fiche en tête de sa page »"):
            self.assertIn(attendu, systeme)
        for absent in ("dans l'OT ou dans la page", "fréquent ici", "laisse sa page inchangée", "sortent de la normale",
                       "la défaillance qu'il a réglée", "où il a servi", "relevés normaux", "en tête de page »",
                       "un conseil court dans « Astuces », une méthode", "ce qui revient", "une sous-page : aussi",
                       "deux gestes réutilisables"):
            self.assertNotIn(absent, systeme)
        self.assertEqual((systeme.count("une méthode de plusieurs gestes"), systeme.count("un conseil")), (1, 1))
        self.assertLessEqual(len(systeme), 9000)                        # 8 730 avant T141 et T142, 8 948 après
        # « deux fois » dans une étape : refusé comme comptage (le contrôle que la consigne annonce).
        reponse = {"rien_a_ajouter": False, "contradictions": [], "pages": [{
            "action": "creer", "titre": "Changer la garniture sans fuite", "type": "savoir-faire",
            "rattache_a": "PO-01 — Pompe de process A", "rubriques": [{"rubrique": "Étapes", "phrases": [
                {"texte": "Changer la garniture", "ot": ["OT-2026-0001"]},
                {"texte": "Contrôler l'étanchéité deux fois", "ot": ["OT-2026-0001"]}]}]}]}
        refus = self.page.evaluate(LIRE_JS, ["OT-2026-0001", json.dumps(reponse, ensure_ascii=False)])
        self.assertEqual(refus["raisons"], ["Page « Changer la garniture sans fuite » : comptage interdit (les nombres de cas "
                                            "sont calculés par Prévo) — « Contrôler l'étanchéité deux fois »."])

    def test_consigne_regles_de_t141_et_t142(self):
        """T141 (D116) et T142 (D117), corrections de Nicolas après le temps 1 : chaque règle nouvelle ou changée est dans
        la consigne, mot pour mot ; les anciennes formulations n'y sont plus ; aucune limite en dur (elles sont dans
        l'en-tête, qui dit « à réécrire en entier » pour « En bref ») ; message système sous 9 000 caractères."""
        systeme = self.page.evaluate(REQUETE_JS, "OT-2026-0001")["messages"][0]["content"]
        for attendu in (
                # T142 : « En bref » réécrit en entier, jamais une phrase ajoutée ; chaque phrase avec ses OT
                "« En bref » de la machine (type « équipement ») : ce qu'il faut savoir d'abord de cette machine, ses pannes "
                "et ce qui les a réglées ; une synthèse, pas un historique, réécrite en entier à chaque OT (jamais une phrase "
                "ajoutée à la suite), chaque phrase avec les OT qui la fondent ;",
                # T142 : « garde toutes ses phrases » et la rubrique pleine hors « En bref »
                "rends son texte complet ; hors « En bref », garde toutes ses phrases, à l'identique ou reformulées, et tous "
                "les OT qu'elles citent",
                "une rubrique pleine autre que « En bref » : confirme ou regroupe ainsi, ou n'y écris rien",
                # T141 : un seul savoir-faire par geste, commun aux machines, titre sans repère
                "les savoir-faire : une méthode de plusieurs gestes, un seul par geste, commun aux machines,",
                "son titre dit le geste et l'organe, sans repère de machine (« Remplacer une garniture mécanique ») ;",
                # T141 : créé, il relie sa machine et ses articles
                "il relie ses machines dans « Particularités par machine » (une phrase par machine : [[sa machine]] et ce qui "
                "change pour elle : pièce, réglage, accès) et ses articles dans « Pièces et outillage ».",
                # T141 : complété, jamais recréé ; lien s'il n'est qu'au catalogue
                "Un geste qui a déjà son savoir-faire ne se recrée jamais : reçu, complète-le (sa phrase pour cette machine "
                "dans « Particularités par machine », ses étapes si l'OT en apprend) ; au catalogue seulement, un lien "
                "[[titre]] suffit.",
                # T141 : rattachement d'un savoir-faire commun
                "rattachés par « rattache_a » au titre exact de l'article reçu principal du geste s'il y en a un, sinon de la "
                "machine (une sous-page : à son savoir-faire)",
                "savoir-faire « Quand le faire », « Étapes », « Pièces et outillage », « Pièges », « Particularités par "
                "machine »"):
            self.assertIn(attendu, systeme)
        self.assertIn("en entier", systeme)
        for absent in ("réutilisable sur cette machine ou avec cet article", "Serrer la bride de <repère>", "le repère de la "
                       "machine, ou l'article", "si la rubrique est pleine", "une méthode va dans un savoir-faire",
                       "rends son texte complet ; garde toutes ses phrases"):
            self.assertNotIn(absent, systeme)
        self.assertNotRegex(systeme, r"\b(3|60) (phrases|mots)\b|au plus \d")
        self.assertLessEqual(len(systeme), 9000)
        # L'en-tête : « à réécrire en entier » pour « En bref » seulement ; le faux modèle le lit.
        message = self.message("OT-2026-0001")
        self.assertIn("(équipement · En bref : 2 phrases sur 3, 13 mots sur 60, à réécrire en entier en 45 mots environ · Astuces : 0 phrase sur "
                      "10) ===", message)
        self.assertEqual(message.count("à réécrire en entier"), 1)
        self.assertEqual([p["longueurs"]["En bref"]["reecrite"] for p in lire_message(message)["pages"][:1]], [True])

    def test_regle_des_nombres_et_raison_du_refus(self):
        """T140, C1 : un nombre se cherche là où le contrôle le cherche — l'OT à intégrer et le texte d'avant de la page écrite
        (une page créée : l'OT seul). Cas de la relecture : un savoir-faire CRÉÉ reprend « 15 minutes » d'une autre page
        reçue (qui cite un OT, OT-2026-0007) : refusé, et la raison dit ce qui a été vérifié (plus « absent des OT cités »,
        faux puisque l'OT est cité) ; le même nombre dans une phrase reformulée de la page qui le porte passe ; écrit sur une
        autre page reçue (le kit), il est refusé avec « texte d'avant de cette page »."""
        self.page.evaluate("""() => Donnees.modifier('wiki_pages', (lignes) => { const NL = String.fromCharCode(10);
          lignes.find((l) => l.id === 'WP-0001').texte += NL + '- Étanchéité vérifiée 15 minutes en marche [OT-2026-0007]'; })""")
        message = self.message("OT-2026-0001")
        self.assertIn("- Étanchéité vérifiée 15 minutes en marche [OT-2026-0007]", message)
        self.assertNotIn("15", message.split("Savoir-faire que tu peux créer", 1)[0])      # l'OT à intégrer n'a pas « 15 »
        po01, kit = "PO-01 — Pompe de process A", "Kit garniture HC 50"

        def lire(pages):
            reponse = {"rien_a_ajouter": False, "contradictions": [], "pages": pages}
            return self.page.evaluate(LIRE_JS, ["OT-2026-0001", json.dumps(reponse, ensure_ascii=False)])

        def page(action, titre, type_, rubrique, phrases, rattache=""):
            return {"action": action, "titre": titre, "type": type_, "rattache_a": rattache,
                    "rubriques": [{"rubrique": rubrique, "phrases": [{"texte": t, "ot": ot} for t, ot in phrases]}]}

        cree = lire([page("creer", "Vérifier l'étanchéité de PO-01", "savoir-faire", "Étapes", [
            ("Changer la garniture", ["OT-2026-0001"]), ("Vérifier l'étanchéité 15 minutes en marche", ["OT-2026-0007"])], po01)])
        self.assertEqual(cree, {"ok": False, "nom": "IaReponseInvalide", "raisons": [
            "Page « Vérifier l'étanchéité de PO-01 » : nombre « 15 » absent de l'OT intégré, seule source des nombres d'une "
            "page créée — « Vérifier l'étanchéité 15 minutes en marche »."]})
        garde = [("Fuite de garniture au démarrage, fréquent ici", ["OT-2026-0007"]),
                 ("Voir [[Nettoyer le filtre de CP-01]]", ["OT-2026-0007"])]
        reformule = lire([page("modifier", po01, "équipement", "En bref", garde + [
            ("Étanchéité de la garniture neuve vérifiée 15 minutes en marche", ["OT-2026-0007", "OT-2026-0001"])])])
        self.assertTrue(reformule["ok"], reformule)
        ailleurs = lire([page("modifier", kit, "composant", "À quoi il sert", [
            ("Étanchéité de l'arbre de la pompe", ["OT-2026-0007"]), ("Étanche après 15 minutes de marche", ["OT-2026-0001"])])])
        self.assertEqual(ailleurs["raisons"], [
            "Page « Kit garniture HC 50 » : nombre « 15 » absent de l'OT intégré et du texte d'avant de cette page — « Étanche "
            "après 15 minutes de marche »."])

    def test_page_non_renvoyee_reste_inchangee(self):
        """T140, C3 : « ne renvoie pas sa page » est accepté — une page concernée que la réponse ne renvoie pas reste
        inchangée, sans refus ; renvoyée vide alors qu'elle l'était (le filtre à huile), elle ne change rien et compte
        comme non renvoyée (relecture de T140) ; une page qui a des phrases, renvoyée sans phrase (le kit), est refusée
        (« aucune phrase »)."""
        message = self.message("OT-2026-0002")
        for titre in ("CP-01 — Compresseur", "Filtre à huile", "Nettoyer le filtre de CP-01"):
            self.assertIn("=== Page « %s »" % titre, message)
        machine = {"action": "modifier", "titre": "CP-01 — Compresseur", "type": "équipement", "rattache_a": "",
                   "rubriques": [{"rubrique": "En bref", "phrases": [{"texte": "Filtre encrassé, nettoyé", "ot": ["OT-2026-0002"]}]}]}
        filtre_vide = {"action": "modifier", "titre": "Filtre à huile", "type": "composant", "rattache_a": "", "rubriques": []}

        def lire(ot, pages):
            reponse = {"rien_a_ajouter": False, "contradictions": [], "pages": pages}
            return self.page.evaluate(LIRE_JS, [ot, json.dumps(reponse, ensure_ascii=False)])

        for nom, pages in (("machine seule", [machine]), ("filtre renvoyé vide", [machine, filtre_vide])):
            with self.subTest(nom):
                lu = lire("OT-2026-0002", pages)
                self.assertTrue(lu["ok"], lu)
                self.assertEqual([c["titre"] for c in lu["lu"]["changements"]], ["CP-01 — Compresseur"])
        kit_vide = {"action": "modifier", "titre": "Kit garniture HC 50", "type": "composant", "rattache_a": "", "rubriques": []}
        self.assertIn("Page « Kit garniture HC 50 » : aucune phrase.", lire("OT-2026-0001", [kit_vide])["raisons"])

    def test_issues_d_une_rubrique_pleine(self):
        """T140, M3 (révisée par T142 : hors « En bref », réécrit en entier) : « Astuces » pleine (10 phrases sur 10) —
        chaque issue que la consigne donne passe les contrôles : ajouter l'OT à la phrase qu'il confirme, regrouper deux
        phrases en gardant tous leurs OT (et écrire la nouvelle), n'y rien écrire ; une onzième phrase est refusée.
        « En bref » n'a pas de rubrique pleine : chaque réponse le réécrit (ici, une seule phrase de l'OT)."""
        anciennes = ["Repère %s sur le carter" % lettre for lettre in "abcdefghij"]
        self.page.evaluate("""(phrases) => Donnees.modifier('wiki_pages', (lignes) => { const NL = String.fromCharCode(10);
          lignes.find((l) => l.id === 'WP-0001').texte += NL + '## Astuces' + NL
            + phrases.map((p) => '- ' + p + ' [OT-2026-0007]').join(NL); })""", anciennes)
        self.assertIn("(équipement · En bref : 2 phrases sur 3, 13 mots sur 60, à réécrire en entier en 45 mots environ · Astuces : 10 phrases "
                      "sur 10)", self.message("OT-2026-0001"))
        avant = [(texte, ["OT-2026-0007"]) for texte in anciennes]
        en_bref = {"rubrique": "En bref", "phrases": [{"texte": "Fuite à la garniture : garniture usée remplacée",
                                                       "ot": ["OT-2026-0001"]}]}

        def lire(astuces):
            reponse = {"rien_a_ajouter": False, "contradictions": [], "pages": [{
                "action": "modifier", "titre": "PO-01 — Pompe de process A", "type": "équipement", "rattache_a": "",
                "rubriques": [en_bref, {"rubrique": "Astuces", "phrases": [{"texte": t, "ot": ot} for t, ot in astuces]}]}]}
            return self.page.evaluate(LIRE_JS, ["OT-2026-0001", json.dumps(reponse, ensure_ascii=False)])

        confirme = [(avant[0][0], ["OT-2026-0007", "OT-2026-0001"])] + avant[1:]
        regroupe = avant[:8] + [("Repères i et j sur le carter", ["OT-2026-0007"]), (ASTUCE, ["OT-2026-0001"])]
        for nom, resultat in (("confirme", lire(confirme)), ("regroupe", lire(regroupe)), ("rien dans Astuces", lire(avant))):
            with self.subTest(issue=nom):
                self.assertTrue(resultat["ok"], resultat)
        onzieme = lire(avant + [(ASTUCE, ["OT-2026-0001"])])
        self.assertEqual(onzieme["raisons"], ["Page « PO-01 — Pompe de process A » : « Astuces » : 11 phrases, 10 au plus."])

    def test_en_bref_reecrit_en_entier(self):
        """T142 (D117), de bout en bout (Wiki.lireIngestion) : une réponse qui réécrit « En bref » en retirant ses phrases et
        ses OT d'avant est acceptée (OT-2026-0007 disparaît de la page) ; une 4e phrase, ou plus de 60 mots, refusées avec
        leur raison ; une phrase sans OT refusée ; « Astuces » garde le non-retrait."""
        po01 = "PO-01 — Pompe de process A"

        def lire(en_bref, autres=()):
            reponse = {"rien_a_ajouter": False, "contradictions": [], "pages": [{
                "action": "modifier", "titre": po01, "type": "équipement", "rattache_a": "",
                "rubriques": [{"rubrique": "En bref", "phrases": [{"texte": t, "ot": ot} for t, ot in en_bref]}] + list(autres)}]}
            return self.page.evaluate(LIRE_JS, ["OT-2026-0001", json.dumps(reponse, ensure_ascii=False)])

        synthese = [("Fuite à la garniture : garniture usée remplacée", ["OT-2026-0001"])]
        lu = lire(synthese)
        self.assertTrue(lu["ok"], lu)
        self.assertEqual(lu["lu"]["changements"][0]["apres"],
                         "## En bref" + NL + "- Fuite à la garniture : garniture usée remplacée [OT-2026-0001]")
        self.assertNotIn("OT-2026-0007", lu["lu"]["changements"][0]["apres"])
        quatre = synthese + [("Bruit au démarrage", ["OT-2026-0007"]), ("Joint sec", ["OT-2026-0007"]),
                             ("Garniture neuve", ["OT-2026-0001"])]
        self.assertEqual(lire(quatre)["raisons"], ["Page « %s » : « En bref » : 4 phrases, 3 au plus." % po01])
        long = [("Fuite à la garniture " + " ".join(["usée"] * 57), ["OT-2026-0001"])]          # 61 mots
        self.assertEqual(lire(long)["raisons"], ["Page « %s » : « En bref » : 61 mots, 60 au plus (citations non comptées)."
                                                 % po01])
        self.assertEqual(lire([("Fuite à la garniture", [])])["raisons"],
                         ["Page « %s » : phrase sans OT cité — « Fuite à la garniture »." % po01])
        # « Astuces » garde le non-retrait : sa phrase d'avant est gardée, ou la réponse est refusée.
        self.page.evaluate("""() => Donnees.modifier('wiki_pages', (lignes) => { const NL = String.fromCharCode(10);
          lignes.find((l) => l.id === 'WP-0001').texte += NL + '## Astuces' + NL + '- Repérer le carter [OT-2026-0007]'; })""")
        garde = {"rubrique": "Astuces", "phrases": [{"texte": "Repérer le carter", "ot": ["OT-2026-0007"]}]}
        self.assertTrue(lire(synthese, [garde])["ok"])
        self.assertEqual(lire(synthese)["raisons"], ["Page « %s » : OT cité retiré de la page : OT-2026-0007." % po01,
                                                     "Page « %s » : phrase retirée — « Repérer le carter »." % po01])

    def test_ce_qu_un_ot_peut_creer_vient_de_seuils_et_de_limites(self):
        """Suites de la relecture de T134 : la ligne « Savoir-faire que tu peux créer » du message utilisateur, avant les
        pages, tire ses nombres de Wiki.SEUILS.pagesCreeesMax et de Wiki.LIMITES (savoir-faire entier : il n'a pas encore
        d'en-tête) ; le message système y renvoie et n'écrit aucun de ces nombres (ils ne peuvent plus diverger)."""
        pages, phrases, mots = self.page.evaluate("""() => [Wiki.SEUILS.pagesCreeesMax,
          Wiki.LIMITES['savoir-faire'].page.phrases, Wiki.LIMITES['savoir-faire'].page.mots]""")
        self.assertEqual(self.donnees("OT-2026-0001")["creation"], {"pages": pages, "phrases": phrases, "mots": mots})
        requete = self.page.evaluate(REQUETE_JS, "OT-2026-0001")
        systeme, message = requete["messages"][0]["content"], requete["messages"][1]["content"]
        ligne = ("Savoir-faire que tu peux créer pour cet OT : %d au plus, sous-pages comprises ; chacun : %d phrases et %d "
                 "mots au plus (rubriques comprises, citations non comptées)." % (pages, phrases, mots))
        self.assertIn(NL + NL + ligne + NL + NL + "Pages concernées (texte actuel) :" + NL, message)
        for attendu in ("pas plus que ne le dit la ligne « Savoir-faire que tu peux créer »",
                        "celles d'un savoir-faire créé sont dans la ligne « Savoir-faire que tu peux créer »"):
            self.assertIn(attendu, systeme)
        self.assertNotRegex(systeme, r"au plus \d|\d+ savoir-faire|\b(%d|%d)\b" % (phrases, mots))
        # Le faux modèle lit toujours l'OT et ses pages (la ligne est hors de ce qu'il analyse).
        lu = lire_message(message)
        self.assertEqual((lu["ot"], [p["titre"] for p in lu["pages"]][:2]),
                         ("OT-2026-0001", ["PO-01 — Pompe de process A", "Kit garniture HC 50"]))

    def test_consigne_cite_tout_le_vocabulaire_de_securite(self):
        """Suites de la relecture de T134 : chaque entrée de Wiki.VOCABULAIRE_SECURITE (refusée par les contrôles) est citée
        par la ligne des mots refusés de la consigne — une entrée « racine* » par un mot qui commence par la racine, une
        autre telle quelle (forme comparable) — : les deux listes ne divergent plus. La tournure qu'elle propose pour
        arrêter la machine dans des « Étapes » passe les contrôles, « selon sa fiche de consignation » non."""
        resultat = self.page.evaluate("""() => {
          const ligne = Ia.PROMPTS.ingestionWiki.systeme.split('\\n').find((l) => l.startsWith('- mots refusés dans toute phrase'))
            || '';
          const forme = ' ' + Wiki.comparable(ligne) + ' ';
          const mots = forme.trim().split(' ');
          return { ligne, entrees: Wiki.VOCABULAIRE_SECURITE.length, manquantes: Wiki.VOCABULAIRE_SECURITE.filter((entree) =>
            (entree.endsWith('*') ? !mots.some((mot) => mot.startsWith(entree.slice(0, -1))) : !forme.includes(' ' + entree + ' '))) };
        }""")
        self.assertTrue(resultat["ligne"].startswith("- mots refusés dans toute phrase, même pour rapporter un fait de l'OT : "))
        self.assertGreater(resultat["entrees"], 30)
        self.assertEqual(resultat["manquantes"], [])
        systeme = self.page.evaluate(REQUETE_JS, "OT-2026-0001")["messages"][0]["content"]
        # T140, M2 : « en tête de SA page » — la fiche de la machine est en tête de sa page ; un savoir-faire d'article ne
        # montre en tête que la liste des machines où l'article est monté (« la consignation de chacune est en tête de sa
        # page »), celui d'une machine montre la fiche de la machine : la tournure est juste pour les deux.
        tournure = "Mettre la machine à l'arrêt selon la fiche en tête de sa page"
        self.assertIn("une étape qui arrête la machine pour intervenir s'écrit seulement « " + tournure + " »", systeme)
        self.assertEqual(self.page.evaluate("(t) => t.map((x) => Wiki.termesDeSecurite(x))", [
            tournure, "Arrêter la machine selon sa fiche de consignation"]), [[], ["consignation"]])
        entetes = self.page.evaluate("() => ['WP-0002', 'WP-0004'].map((id) => Wiki.page(id).entete)")
        self.assertEqual([(e["consignation"] is not None, e["equipements"]) for e in entetes],
                         [(True, [{"equipementId": "EQ-0001", "repere": "PO-01"}]),      # savoir-faire de la machine : sa fiche
                          (False, [{"equipementId": "EQ-0001", "repere": "PO-01"}])])    # savoir-faire du kit : ses machines

        def savoir_faire(etape, rattache="PO-01 — Pompe de process A"):
            reponse = {"rien_a_ajouter": False, "contradictions": [], "pages": [{
                "action": "creer", "titre": "Changer la garniture sans fuite", "type": "savoir-faire",
                "rattache_a": rattache, "rubriques": [{"rubrique": "Étapes", "phrases": [
                    {"texte": etape, "ot": ["OT-2026-0001"]}, {"texte": "Changer la garniture", "ot": ["OT-2026-0001"]}]}]}]}
            return self.page.evaluate(LIRE_JS, ["OT-2026-0001", json.dumps(reponse, ensure_ascii=False)])

        self.assertTrue(savoir_faire(tournure)["ok"], savoir_faire(tournure))
        self.assertTrue(savoir_faire(tournure, "Kit garniture HC 50")["ok"], savoir_faire(tournure, "Kit garniture HC 50"))
        refus = savoir_faire("Arrêter la machine selon sa fiche de consignation")
        self.assertFalse(refus["ok"])
        self.assertTrue(any("consigne de sécurité" in raison and "consignation" in raison for raison in refus["raisons"]),
                        refus)

    def test_entete_de_chaque_texte_mesure_par_rubrique_et_limites(self):
        """§20.12 : chaque texte envoyé porte sa mesure par rubrique et la limite de Wiki.LIMITES (une machine est limitée
        à 3 phrases d'« En bref », D117, jamais « sur 30 ») ; un savoir-faire, sa mesure de page et ses limites ; les données
        le disent aussi (`longueurs`, et `reecrite` pour « En bref », réécrit en entier), plus de limite générique."""
        d = self.donnees("OT-2026-0001")
        self.assertNotIn("limites", d)
        self.assertEqual(sorted(d["pages"][0]), ["cle", "longueurs", "mere", "otDates", "texte", "titre", "type"])
        self.assertEqual({p["titre"]: p["longueurs"] for p in d["pages"][:3]}, {
            "PO-01 — Pompe de process A": [
                {"rubrique": "En bref", "phrases": 2, "mots": 13, "phrasesMax": 3, "motsMax": 60, "reecrite": True},
                {"rubrique": "Astuces", "phrases": 0, "mots": 0, "phrasesMax": 10, "motsMax": None, "reecrite": False}],
            "Kit garniture HC 50": [{"rubrique": "À quoi il sert", "phrases": 1, "mots": 6, "phrasesMax": 3, "motsMax": 80,
                                     "reecrite": False}],
            "Changer la garniture de PO-01": [{"rubrique": "", "phrases": 1, "mots": 3, "phrasesMax": 30, "motsMax": 600,
                                               "reecrite": False}]})
        message = self.message("OT-2026-0001")
        self.assertIn("=== Page « Changer la garniture de PO-01 » (savoir-faire · 1 phrase sur 30, 3 mots sur 600) ===",
                      message)
        self.assertNotIn("phrases sur 30, 13 mots", message)
        # Textes vides : machine, article (page calculée sans ligne) et savoir-faire.
        vide = self.message("OT-2026-0002")
        for attendu in ("=== Page « CP-01 — Compresseur » (équipement · En bref : 0 phrase sur 3, 0 mot sur 60, à réécrire en "
                        "entier en 45 mots environ · Astuces : 0 phrase sur 10) ===\n(page vide)",
                        "=== Page « Filtre à huile » (composant · À quoi il sert : 0 phrase sur 3, 0 mot sur 80) ===\n(page vide)",
                        "=== Page « Nettoyer le filtre de CP-01 » (savoir-faire · 0 phrase sur 30, 0 mot sur 600) ===\n"
                        "(page vide)"):
            self.assertIn(attendu, vide)
        # Le faux modèle lit ces longueurs (même en-tête qu'il analyse).
        self.assertEqual(lire_message(message)["pages"][0]["longueurs"], {
            "En bref": {"phrases": 2, "phrases_max": 3, "mots": 13, "mots_max": 60, "reecrite": True},
            "Astuces": {"phrases": 0, "phrases_max": 10, "mots": None, "mots_max": None, "reecrite": False}})

    def test_catalogue_machines_articles_savoir_faire_et_pannes(self):
        """§20.12 : le catalogue envoyé (liens [[…]]) : machines, articles, savoir-faire et pannes (code symptôme qui a au
        moins un cas) ; jamais un technicien, une intervention, une ancienne page de mode ou un composant libre ; le
        contrôle accepte un lien vers une panne et refuse un lien vers ce qui n'est pas au catalogue."""
        catalogue = self.donnees("OT-2026-0001")["catalogue"]
        self.assertEqual({p["type"] for p in catalogue}, {"équipement", "composant", "savoir-faire", "panne"})
        self.assertEqual([p["titre"] for p in catalogue if p["type"] == "panne"], ["Bruit anormal", "Fuite"])
        titres = [p["titre"] for p in catalogue]
        for attendu in ("PO-01 — Pompe de process A", "CV-01 — Convoyeur", "Kit garniture HC 50", "Pièce de convoyeur I",
                        "Changer la garniture de PO-01", "Graisser le palier", "Changer le filtre à huile"):
            self.assertIn(attendu, titres)
        for absent in ("Vibration", "Usure de garniture", "Desserrage", "Joint torique 20x2", "Ancien geste"):
            self.assertNotIn(absent, titres)
        texte = json.dumps(catalogue, ensure_ascii=False)
        for interdit in ("Ledoux", "Zéphyrin", "TEC-", "OT-20"):
            self.assertNotIn(interdit, texte)
        # Les pannes juste après les savoir-faire à valider (aucun ici), avant les titres de Wiki.catalogue.
        self.assertIn("Catalogue des pages :\n- Bruit anormal (panne)\n- Fuite (panne)\n- Changer la garniture de PO-01 "
                      "(savoir-faire)\n", self.message("OT-2026-0001"))

        def avec_lien(titre):
            reponse = {"rien_a_ajouter": False, "contradictions": [], "pages": [{
                "action": "modifier", "titre": "PO-01 — Pompe de process A", "type": "équipement", "rattache_a": "",
                "rubriques": [{"rubrique": "En bref", "phrases": [
                    {"texte": "Fuite de garniture au démarrage, fréquent ici", "ot": ["OT-2026-0007"]},
                    {"texte": "Voir [[Nettoyer le filtre de CP-01]]", "ot": ["OT-2026-0007"]},
                    {"texte": "Fuite à la garniture, voir [[" + titre + "]]", "ot": ["OT-2026-0001"]}]}]}]}
            return self.page.evaluate(LIRE_JS, ["OT-2026-0001", json.dumps(reponse, ensure_ascii=False)])

        self.assertTrue(avec_lien("Fuite")["ok"], avec_lien("Fuite"))
        for inconnu in ("Vibration", "Usure de garniture", "Zéphyrin Ledoux"):
            with self.subTest(lien=inconnu):
                refus = avec_lien(inconnu)
                self.assertFalse(refus["ok"])
                self.assertIn("Page « PO-01 — Pompe de process A » : lien vers une page inconnue « %s »." % inconnu,
                              refus["raisons"])

        # Une seule définition des pannes (suites de la relecture de T134) : celle des pages Panne, Wiki.listeEntites
        # (wiki-entites.js) — un préventif clôturé de code S03, un correctif S03 encore en cours n'en font pas une ; un
        # correctif S03 clôturé techniquement, si.
        def pannes():
            return self.page.evaluate("""() => [Wiki.donneesIngestion('OT-2026-0001').catalogue.filter((p) => p.type === 'panne')
              .map((p) => p.titre), Wiki.listeEntites('panne', { profil: 'responsable' }).map((p) => p.titre).sort()]""")

        ajouter_ot = """(ot) => Donnees.modifier('ordres_travail', (lignes) => { lignes.push(Object.assign({ equipement_id: 'EQ-0002',
          priorite: 'P2', date_creation: '2026-05-09 08:00', date_fin: '2026-05-10 08:00', symptome_code: 'S03' }, ot)); })"""
        self.page.evaluate(ajouter_ot, {"id": "OT-2026-0050", "type": "préventif systématique", "statut": "Clôturé administrativement",
                                        "titre": "CP-01 — Contrôle"})
        self.page.evaluate(ajouter_ot, {"id": "OT-2026-0051", "type": "correctif différé", "statut": "En cours",
                                        "titre": "CP-01 — Vibration", "date_fin": ""})
        self.assertEqual(pannes(), [["Bruit anormal", "Fuite"]] * 2)
        self.page.evaluate(ajouter_ot, {"id": "OT-2026-0052", "type": "correctif différé", "statut": "Clôturé techniquement",
                                        "titre": "CP-01 — Vibration"})
        self.assertEqual(pannes(), [["Bruit anormal", "Fuite", "Vibration"]] * 2)
        # Deux définitions qui donnent les mêmes pannes ne se distinguent pas ci-dessus (relecture de 884cedf : l'ancien
        # filtre recollé restait vert) : un bouchon de Wiki.listeEntites prouve que le catalogue la lit, elle seule (T140, C2).
        sentinelle = self.page.evaluate("""() => {
          const vraie = Wiki.listeEntites;
          const appels = [];
          Wiki.listeEntites = (type, options) => {
            appels.push([type, options && options.profil]);
            return type === 'panne' ? [{ id: 'PANNE-ZZ', code: 'ZZ', titre: 'Panne sentinelle', cas: 1, machines: 1, cause: null,
              derniere: '', lien: 'PANNE-ZZ' }] : vraie(type, options);
          };
          try {
            return { pannes: Wiki.donneesIngestion('OT-2026-0001').catalogue.filter((p) => p.type === 'panne').map((p) => p.titre),
              appels };
          } finally {
            Wiki.listeEntites = vraie;
          }
        }""")
        self.assertEqual(sentinelle["pannes"], ["Panne sentinelle"])
        self.assertIn(["panne", "responsable"], sentinelle["appels"])
        self.assertEqual(pannes(), [["Bruit anormal", "Fuite", "Vibration"]] * 2)          # fonction rendue

    def test_pages_concernees_dans_l_ordre_de_priorite(self):
        concernees = self.page.evaluate("(ot) => Wiki.pagesConcernees(ot)", "OT-2026-0001")
        # Ordre du §20.12 (D112 révisée) : sa machine, ses articles consommés, les savoir-faire de la machine (ancrés ou
        # rattachés) puis des articles ; ni cause (C01), ni mode ancré sur elle (WP-0005), ni savoir-faire d'une autre
        # machine lié depuis la page de PO-01 (WP-0008), ni page archivée (WP-0009).
        self.assertEqual(concernees["cles"], ["EQ:EQ-0001", "ART:ART-0001", "WP:WP-0002", "WP:WP-0010", "WP:WP-0004"])
        self.assertEqual([p["titre"] for p in concernees["envoyees"]],
                         ["PO-01 — Pompe de process A", "Kit garniture HC 50", "Changer la garniture de PO-01",
                          "Graisser le palier", "Monter le kit garniture"])
        # Pages calculées (sans ligne) : équipement et article ; savoir-faire ancré sur la machine, puis sur l'article.
        calculees = self.page.evaluate("(ot) => Wiki.pagesConcernees(ot)", "OT-2026-0002")
        self.assertEqual(calculees["cles"], ["EQ:EQ-0002", "ART:ART-0003", "WP:WP-0008", "WP:WP-0011"])
        self.assertEqual([(p["titre"], p["type"], p["texte"]) for p in calculees["envoyees"]],
                         [("CP-01 — Compresseur", "équipement", ""), ("Filtre à huile", "composant", ""),
                          ("Nettoyer le filtre de CP-01", "savoir-faire", ""), ("Changer le filtre à huile", "savoir-faire", "")])
        # Neuf articles consommés : toutes les clés, huit pages envoyées au plus.
        nombreuses = self.page.evaluate("(ot) => Wiki.pagesConcernees(ot)", "OT-2026-0006")
        self.assertEqual(nombreuses["cles"], ["EQ:EQ-0003"] + ["ART:ART-%04d" % n for n in range(4, 13)])
        self.assertEqual(len(nombreuses["envoyees"]), self.page.evaluate("Wiki.SEUILS.pagesEnvoyeesMax"))
        self.assertEqual(len(nombreuses["envoyees"]), 8)
        # Aucune clé de cause, pour aucun OT.
        self.assertEqual(self.page.evaluate("""() => Donnees.lignes('ordres_travail').flatMap((o) => Wiki.pagesConcernees(o.id).cles)
          .filter((cle) => !/^(EQ|ART|WP|TITRE):/.test(cle))"""), [])

    def test_sous_pages_juste_apres_leur_mere(self):
        """CS113 (§20.5 ; savoir-faire seulement, §20.12) : après chaque savoir-faire concerné, ses sous-pages (validées ou
        « à valider », par titre), clés comprises ; une ancienne sous-page d'équipement n'est pas envoyée ; un savoir-faire
        rattaché à une machine n'est pas une sous-page ; l'en-tête le dit."""
        self.page.evaluate(SOUS_PAGES_JS)
        concernees = self.page.evaluate("(ot) => Wiki.pagesConcernees(ot)", "OT-2026-0001")
        self.assertEqual(concernees["cles"], ["EQ:EQ-0001", "ART:ART-0001", "WP:WP-0002", "WP:WP-0020", "WP:WP-0010",
                                              "TITRE:graisser le palier frequence", "WP:WP-0004", "WP:WP-0021"])
        self.assertEqual([p["titre"] for p in concernees["envoyees"]],
                         ["PO-01 — Pompe de process A", "Kit garniture HC 50", "Changer la garniture de PO-01",
                          "Changer la garniture de PO-01 — dépose", "Graisser le palier", "Graisser le palier — fréquence",
                          "Monter le kit garniture", "Monter le kit garniture — faces"])
        # État proposé : une sous-page (validée ou à valider) a la clé de sa mère pour rattachement, aucun ancrage propre.
        etat = self.page.evaluate("""() => { const etat = Wiki.etatPropose();
          return ['WP:WP-0020', 'TITRE:graisser le palier frequence', 'WP:WP-0021', 'WP:WP-0010', 'WP:WP-0022'].map((cle) => {
            const p = etat.get(cle); return [p.type, p.rattacheA, p.equipementId, p.articleId]; }); }""")
        self.assertEqual(etat, [["savoir-faire", "WP:WP-0002", "", ""], ["savoir-faire", "WP:WP-0010", "", ""],
                                ["savoir-faire", "WP:WP-0004", "", ""], ["savoir-faire", "EQ:EQ-0001", "", ""],
                                ["équipement", "EQ:EQ-0001", "", ""]])
        # Données : chaque page porte `mere` (le titre de sa mère pour une sous-page) ; l'en-tête le dit.
        d = self.donnees("OT-2026-0001")
        self.assertEqual([p["mere"] for p in d["pages"]], ["", "", "", "Changer la garniture de PO-01", "", "Graisser le palier",
                                                           "", "Monter le kit garniture"])
        message = self.message("OT-2026-0001")
        self.assertIn("=== Page « Changer la garniture de PO-01 — dépose » (savoir-faire · sous-page de « Changer la "
                      "garniture de PO-01 » · 1 phrase sur 30, 5 mots sur 600) ===", message)
        self.assertIn("=== Page « Graisser le palier » (savoir-faire · 2 phrases sur 30, 8 mots sur 600) ===", message)
        self.assertIn("=== Page « Graisser le palier — fréquence » (savoir-faire · sous-page de « Graisser le palier » · "
                      "1 phrase sur 30, 7 mots sur 600) ===", message)
        self.assertNotIn("PO-01 — garniture", message.split("Catalogue des pages :")[0])
        self.assertEqual([(p["titre"], p["type"], p["mere"]) for p in lire_message(message)["pages"]][2:4],
                         [("Changer la garniture de PO-01", "savoir-faire", ""),
                          ("Changer la garniture de PO-01 — dépose", "savoir-faire", "Changer la garniture de PO-01")])
        # Réservations (D112) : un envoi en cours sur une sous-page retient l'OT.
        self.page.evaluate("(ids) => Wiki.mettreEnFile(ids)", ["OT-2026-0001"])
        self.assertEqual(self.page.evaluate("Wiki.prochainsEnvois(Wiki.file(), [{ cles: ['WP:WP-0021'] }]).length"), 0)

    def concernees(self, ot):
        resultat = self.page.evaluate("(ot) => Wiki.pagesConcernees(ot)", ot)
        return resultat["cles"], [p["titre"] for p in resultat["envoyees"]]

    def test_savoir_faire_du_meme_geste_d_une_autre_machine(self):
        """T141 (D116, point 3) : un OT de PO-01 reçoit le savoir-faire « Remplacer une garniture mécanique » créé pour PO-02
        (autre machine, autre article) parce que son texte dit le même geste (Wiki.memeGeste : 2 mots du titre sur 3) ;
        après les pages d'avant, une fois ; ni un OT de PO-01 qui ne parle pas de garniture mécanique, ni le même OT si son
        texte n'a qu'un mot du titre."""
        self.page.evaluate(COMMUNS_JS, False)
        avant = ["EQ:EQ-0001", "ART:ART-0001", "WP:WP-0002", "WP:WP-0010", "WP:WP-0004"]
        self.assertEqual(self.concernees("OT-2026-0001"), (avant, [
            "PO-01 — Pompe de process A", "Kit garniture HC 50", "Changer la garniture de PO-01", "Graisser le palier",
            "Monter le kit garniture"]))
        self.page.evaluate("""() => Donnees.modifier('ordres_travail', (lignes) => {
          lignes.find((o) => o.id === 'OT-2026-0001').titre = 'PO-01 — Fuite à la garniture mécanique'; })""")
        cles, titres = self.concernees("OT-2026-0001")
        self.assertEqual((cles, titres[-1]), (avant + ["WP:WP-0040"], "Remplacer une garniture mécanique"))
        self.assertEqual(self.concernees("OT-2026-0001"), (cles, titres))                  # déterministe
        self.assertIn("=== Page « Remplacer une garniture mécanique » (savoir-faire · 1 phrase sur 30, 4 mots sur 600) ===\n"
                      "## Étapes\n- Déposer le moteur [OT-2026-0007]", self.message("OT-2026-0001"))
        self.assertNotIn("WP:WP-0040", self.concernees("OT-2026-0003")[0])                 # PO-01, bruit au démarrage
        self.assertNotIn("WP:WP-0040", self.concernees("OT-2026-0002")[0])                 # CP-01, filtre

    def test_savoir_faire_lies_par_leur_texte(self):
        """T141 (D116, point 3) : les savoir-faire dont le texte a un lien vers la machine (une phrase de « Particularités
        par machine »), puis ceux du même geste, puis ceux qui ont un lien vers un article consommé ; un lien d'une
        sous-page amène sa mère, suivie de ses sous-pages ; toutes les clés réservées, 8 pages envoyées au plus."""
        self.page.evaluate(COMMUNS_JS, True)
        self.page.evaluate("""() => Donnees.modifier('ordres_travail', (lignes) => {
          lignes.find((o) => o.id === 'OT-2026-0001').titre = 'PO-01 — Fuite à la garniture mécanique'; })""")
        cles, titres = self.concernees("OT-2026-0001")
        self.assertEqual(cles, ["EQ:EQ-0001", "ART:ART-0001", "WP:WP-0002", "WP:WP-0010", "WP:WP-0004", "WP:WP-0041",
                                "WP:WP-0043", "WP:WP-0044", "WP:WP-0040", "WP:WP-0042"])
        self.assertEqual(titres[5:], ["Contrôler l'alignement d'un accouplement", "Régler un palier", "Régler un palier — repères"])
        self.assertEqual(len(titres), 8)
        # Le kit seul (OT-2026-0001 ne le consomme plus) : le savoir-faire lié au kit n'est plus concerné.
        self.page.evaluate("""() => Donnees.modifier('mouvements_stock', (lignes) => {
          lignes.find((m) => m.id === 'MVT-000001').quantite = '0'; })""")
        self.assertNotIn("WP:WP-0042", self.concernees("OT-2026-0001")[0])
        # Un OT d'une autre machine qui ne consomme pas le kit : aucun de ces liens ne le concerne.
        self.assertFalse({"WP:WP-0041", "WP:WP-0042", "WP:WP-0043", "WP:WP-0044"} & set(self.concernees("OT-2026-0004")[0]))

    def test_savoir_faire_cree_pendant_l_envoi_et_concerne_rejoue(self):
        """T141 : un savoir-faire du même geste créé par un autre OT pendant l'envoi (ici, une proposition à valider écrite
        pendant l'appel) : la réponse n'est pas écrite, l'OT est rejoué sur le nouvel état (sans relance) et reçoit alors ce
        savoir-faire."""
        self.page.evaluate("""() => Donnees.modifier('ordres_travail', (lignes) => {
          lignes.find((o) => o.id === 'OT-2026-0001').titre = 'PO-01 — Fuite à la garniture mécanique'; })""")
        resultat = self.page.evaluate("""async (rien) => {
          await Wiki.mettreEnFile(['OT-2026-0001']);
          const recus = [];
          const bilan = await Wiki.traiterFile({ agents: 1, appeler: async (requete, donnees) => {
            recus.push(donnees.pages.map((p) => p.titre));
            if (recus.length === 1) await Donnees.modifier('wiki_journal', (lignes, outils) => { lignes.push({
              id: outils.nouvelId(lignes), nature: 'ingestion', ot_id: 'OT-2026-0004', statut: 'à valider', ordre: '9',
              changements: JSON.stringify([{ cle: 'TITRE:remplacer une garniture mecanique', titre: 'Remplacer une garniture '
                + 'mécanique', type: 'savoir-faire', creation: true, rattacheA: 'CV-01 — Convoyeur', version_avant: 0, avant: '',
                apres: '## Étapes' + String.fromCharCode(10) + '- Déposer le moteur [OT-2026-0004]' }]) }); }, { journal: false });
            return { modele: 'essai', contenu: rien };
          } });
          const e = Donnees.lignes('wiki_journal').find((x) => x.ot_id === 'OT-2026-0001');
          return { recus, rejouees: bilan.rejouees, statut: e.statut, motif: e.motif, essais: e.essais };
        }""", json.dumps({"rien_a_ajouter": True, "pages": [], "contradictions": []}))
        self.assertEqual((resultat["rejouees"], resultat["statut"], resultat["motif"], resultat["essais"]),
                         (1, "rien à ajouter", "rejoué : pages changées pendant l'envoi", "2"))
        self.assertNotIn("Remplacer une garniture mécanique", resultat["recus"][0])
        self.assertIn("Remplacer une garniture mécanique", resultat["recus"][1])

    def test_ordre_de_la_file_par_date_d_intervention_puis_numero(self):
        self.assertEqual(self.page.evaluate("Wiki.horsDuWiki().map((o) => o.id)"), EN_FILE)
        self.assertEqual(self.page.evaluate("Wiki.horsDuWiki({ equipementId: 'EQ-0001' }).map((o) => o.id)"),
                         ["OT-2026-0003", "OT-2026-0001", "OT-2026-0008"])
        # Mis en file à l'envers, avec un OT non clôturé administrativement, un inconnu et un déjà intégré.
        ajoutes = self.page.evaluate("(ids) => Wiki.mettreEnFile(ids)",
                                     list(reversed(EN_FILE)) + ["OT-2026-0005", "OT-2026-9999", "OT-2026-0007"])
        self.assertEqual(ajoutes, 6)
        file = self.page.evaluate("Wiki.file().map((e) => [e.ot_id, e.date_intervention, e.statut, e.essais])")
        self.assertEqual([e[0] for e in file], EN_FILE)
        self.assertEqual(file[2], ["OT-2026-0001", "2026-03-10 10:00", "en file", "0"])
        self.assertEqual(self.page.evaluate("Wiki.horsDuWiki().length"), 0)
        self.assertEqual(self.page.evaluate("(ids) => Wiki.mettreEnFile(ids)", EN_FILE), 0)       # jamais deux fois
        self.assertEqual(self.page.evaluate("Donnees.lignes('journal').filter((l) => l.table === 'wiki_journal').length"), 0)

    def test_egalite_de_date_departagee_par_le_numero_d_ot(self):
        """Relecture de T118 : trois OT de même date d'intervention, mis en file dans le désordre, sortent par numéro."""
        self.page.evaluate("""() => Donnees.modifier('ordres_travail', (lignes) => {
          lignes.find((o) => o.id === 'OT-2026-0008').date_fin = '2026-03-10 10:00'; })""")
        self.page.evaluate("(ids) => Wiki.mettreEnFile(ids)", ["OT-2026-0008", "OT-2026-0002", "OT-2026-0001"])
        self.assertEqual(self.page.evaluate("Wiki.file().map((e) => e.ot_id)"), ["OT-2026-0001", "OT-2026-0002", "OT-2026-0008"])
        # 0001 et 0008 partagent PO-01 : 0008, plus grand numéro, attend.
        self.assertEqual(self.page.evaluate("Wiki.prochainsEnvois(Wiki.file(), [], { agents: 5 }).map((c) => c.entree.ot_id)"),
                         ["OT-2026-0001", "OT-2026-0002"])

    def test_anteriorite_par_les_pages_de_l_ot(self):
        anterieure = self.donnees("OT-2026-0003")              # PO-01, février ; ses pages citent OT-2026-0007 (avril)
        self.assertTrue(anterieure["anterieure"])
        message = self.message("OT-2026-0003")
        self.assertIn(MENTION, message)
        self.assertIn("Date d'intervention des OT déjà cités : OT-2026-0007 : 2026-04-15 08:00", message)
        self.assertTrue(self.donnees("OT-2026-0001")["anterieure"])       # mars < avril
        for ot in ("OT-2026-0008", "OT-2026-0004", "OT-2026-0002"):
            # 0008 : plus récent que tout ce que citent ses pages ; 0004 (le plus ancien) et 0002 : leurs pages ne
            # citent aucun OT, même si OT-2026-0007 est intégré ailleurs.
            with self.subTest(ot=ot):
                self.assertFalse(self.donnees(ot)["anterieure"])
                self.assertNotIn(MENTION, self.message(ot))
        # « Désormais » : refusé pour l'OT antérieur seulement.
        refus = self.page.evaluate(LIRE_JS, ["OT-2026-0003", json.dumps(
            reponse_ingestion(self.message("OT-2026-0003"), "faux-recent"), ensure_ascii=False)])
        self.assertFalse(refus["ok"])
        self.assertEqual(refus["nom"], "IaReponseInvalide")
        self.assertTrue(any("intervention antérieure à des faits déjà intégrés" in r for r in refus["raisons"]), refus)
        permis = self.page.evaluate(LIRE_JS, ["OT-2026-0008", json.dumps(
            reponse_ingestion(self.message("OT-2026-0008"), "faux-recent"), ensure_ascii=False)])
        self.assertTrue(permis["ok"], permis)

    def test_catalogue_au_plafond_garde_les_pages_en_attente(self):
        catalogue = self.page.evaluate("""async () => {
          await Donnees.modifier('equipements', (lignes) => { for (let n = 100; n < 520; n += 1) {
            lignes.push({ id: 'EQ-0' + n, repere: 'ZZ-' + n, designation: 'Machine ' + n, statut: 'en service', actif: '1' }); } });
          await Donnees.modifier('wiki_journal', (lignes) => { lignes.push({ id: 'WJ-00002', nature: 'ingestion',
            ot_id: 'OT-2026-0004', statut: 'à valider', ordre: '2', essais: '1', changements: JSON.stringify([{
            cle: 'TITRE:zzz usure tardive', titre: 'Zzz usure tardive', type: 'savoir-faire', creation: true,
            rattacheA: 'CV-01 — Convoyeur', version_avant: 0, avant: '', apres: '## Quand le faire\\n- Usure [OT-2026-0004]' }]) }); });
          return Wiki.donneesIngestion('OT-2026-0002').catalogue;
        }""")
        self.assertEqual(len(catalogue), self.page.evaluate("Wiki.SEUILS.catalogueMax"))
        self.assertEqual(catalogue[:3], [{"titre": "Zzz usure tardive", "type": "savoir-faire"},
                                         {"titre": "Bruit anormal", "type": "panne"}, {"titre": "Fuite", "type": "panne"}])

    def test_prochains_envois(self):
        self.page.evaluate("(ids) => Wiki.mettreEnFile(ids)", EN_FILE)
        choisir = """([agents, enCours]) => Wiki.prochainsEnvois(Wiki.file(), enCours, { agents })
          .map((c) => c.entree.ot_id)"""
        # Plus de clé de cause (refonte 2) : 0003 (PO-01) part avec 0004 (CV-01) malgré leur cause commune C03 ; 0001 et
        # 0008 attendent 0003 (PO-01) ; 0006 attend 0004 (CV-01).
        self.assertEqual(self.page.evaluate(choisir, [5, []]), ["OT-2026-0004", "OT-2026-0003", "OT-2026-0002"])
        self.assertEqual(self.page.evaluate(choisir, [1, []]), ["OT-2026-0004"])
        self.assertEqual(self.page.evaluate(choisir, [5, [{"cles": ["ART:ART-0003"]}]]), ["OT-2026-0004", "OT-2026-0003"])
        self.assertEqual(self.page.evaluate(choisir, [2, [{"cles": ["EQ:EQ-0009"]}]]), ["OT-2026-0004"])
        self.assertEqual(self.page.evaluate(choisir, [5, [{"cles": ["EQ:EQ-0003"]}]]), ["OT-2026-0003", "OT-2026-0002"])
        # Une clé de cause encore portée par un envoi (entrée d'avant la refonte 2) ne retient plus personne.
        self.assertEqual(self.page.evaluate(choisir, [5, [{"cles": ["CAUSE:C03"]}]]),
                         ["OT-2026-0004", "OT-2026-0003", "OT-2026-0002"])


# ---------------------------------------------------------------------------------------------------
# Traitement de la file avec le faux fournisseur
# ---------------------------------------------------------------------------------------------------

class TestTraitement(CasIngestion):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.faux = FauxFournisseur(lenteur_s=1)
        cls.faux.demarrer()
        cls.addClassCleanup(cls.faux.arreter)

    def setUp(self):
        super().setUp()
        self.faux.requetes.clear()
        regler_ia(self.contexte, url=self.faux.url)
        self.charger()

    def traiter(self, ids, modele="faux", options=None):
        self.page.evaluate("(modele) => Ia.enregistrerReglages({ modele })", modele)
        return self.page.evaluate(TRAITER_JS, [ids, options])

    def test_bout_en_bout_requetes_etat_propose_et_ordre_par_page(self):
        bilan = self.traiter(EN_FILE, "faux-cree-commun")
        self.assertIsNone(bilan["erreur"])
        # 0004 (CV-01), 0003 (PO-01) et 0002 (CP-01) n'ont aucune page commune (plus de clé de cause) : ils partent
        # ensemble et créent tous trois le savoir-faire « Usure commune » ; le premier écrit l'emporte, les deux autres
        # sont rejoués et le trouvent alors au catalogue.
        self.assertEqual((bilan["acceptees"], bilan["rien"], bilan["refusees"], bilan["rejouees"]), (6, 0, 0, 2))
        journal = self.journal()
        self.assertEqual(sorted(journal), sorted(EN_FILE))
        self.assertEqual({ot: e["statut"] for ot, e in journal.items()}, {ot: "à valider" for ot in EN_FILE})
        self.assertEqual({ot: e["anterieure"] for ot, e in journal.items()},
                         {"OT-2026-0004": "0", "OT-2026-0003": "1", "OT-2026-0001": "1", "OT-2026-0002": "0",
                          "OT-2026-0006": "0", "OT-2026-0008": "0"})
        self.assertEqual(sorted(e["essais"] for e in journal.values()), ["1", "1", "1", "1", "2", "2"])
        # Le motif du rejeu reste sur l'entrée acceptée ensuite (D112 : le journal le note).
        self.assertEqual(sorted(e["motif"] for e in journal.values()), [""] * 4 + ["rejoué : page créée entre-temps"] * 2)
        self.assertEqual({ot for ot, e in journal.items() if e["motif"]} | {ot for ot, e in journal.items()
                         if any(c["titre"] == "Usure commune" for c in json.loads(e["changements"]))},
                         {"OT-2026-0004", "OT-2026-0003", "OT-2026-0002"})
        self.assertTrue(all(e["modele"] == "faux-cree-commun" for e in journal.values()), journal)
        creations = [(c["titre"], c["type"]) for e in journal.values() for c in json.loads(e["changements"]) if c["creation"]]
        self.assertEqual(sorted(creations), [(GESTE, "savoir-faire"), ("Usure commune", "savoir-faire")])
        # Pour chaque page : les OT dans l'ordre des dates d'intervention (rang de traitement), jamais deux à la fois.
        envois = bilan["envois"]
        self.assertEqual(len(envois), 8)
        self.assertEqual(sorted(e["ot"] for e in envois if e["debut"] < min(x["fin"] for x in envois)),
                         ["OT-2026-0002", "OT-2026-0003", "OT-2026-0004"])
        for cle in {cle for envoi in envois for cle in envoi["cles"]}:
            avec = sorted((e for e in envois if cle in e["cles"]), key=lambda e: e["debut"])
            for avant, apres in zip(avec, avec[1:]):
                self.assertLess(avant["fin"], apres["debut"], (cle, avant, apres))
        rang = {ot: int(e["ordre"]) for ot, e in journal.items()}
        self.assertLess(rang["OT-2026-0003"], rang["OT-2026-0001"])
        self.assertLess(rang["OT-2026-0001"], rang["OT-2026-0008"])
        self.assertLess(rang["OT-2026-0004"], rang["OT-2026-0006"])
        # État proposé enchaîné : la page de PO-01 de la dernière proposition, « En bref » réécrit en entier à chaque OT
        # (T142 : une phrase par panne, 3 au plus) — les phrases de l'OT-2026-0007 sont parties, une par une.
        page_po01 = [c for c in json.loads(journal["OT-2026-0008"]["changements"]) if c["cle"] == "EQ:EQ-0001"][0]
        self.assertEqual(page_po01["apres"], NL.join(["## En bref", "- Bruit au démarrage [OT-2026-0003]",
                                                      "- Fuite à la garniture [OT-2026-0001]", "- Fuite encore [OT-2026-0008]"]))
        # Versions enchaînées (D105) : WP-0001 est en version 1 ; chaque proposition plus ancienne en attente l'avance.
        versions = {ot: [(c["page"], c["version_avant"]) for c in json.loads(journal[ot]["changements"]) if c["cle"] == "EQ:EQ-0001"]
                    for ot in ("OT-2026-0003", "OT-2026-0001", "OT-2026-0008")}
        self.assertEqual(versions, {"OT-2026-0003": [("WP-0001", 1)], "OT-2026-0001": [("WP-0001", 2)],
                                    "OT-2026-0008": [("WP-0001", 3)]})
        self.assertEqual(self.page.evaluate("Wiki.etatPropose().get('EQ:EQ-0001').version"), 4)
        self.assertEqual(journal["OT-2026-0001"]["pages"].split(";")[:4], ["EQ:EQ-0001", "ART:ART-0001", "WP:WP-0002", "WP:WP-0010"])
        self.assertNotIn("CAUSE:", "".join(e["pages"] for e in journal.values()))
        # Requêtes réellement envoyées : une par envoi, rien d'interdit, l'astuce de 0001 et la mention de 0003.
        corps = [r["corps"] for r in self.faux.requetes_vers("/api/chat")]
        self.assertEqual(len(corps), 8)
        # La collision est rejouée par une requête d'origine (sur le nouvel état), jamais relancée avec une raison.
        self.assertFalse(any(MARQUE_RELANCE in c["messages"][1]["content"] for c in corps))
        textes = [json.dumps(c, ensure_ascii=False) for c in corps]
        for interdit in INTERDITS:
            self.assertFalse(any(interdit in t for t in textes), interdit)
        messages = {re.search(r"OT à intégrer : (OT-\d{4}-\d{4})", c["messages"][1]["content"]).group(1): c["messages"][1]["content"]
                    for c in corps}
        self.assertIn("Astuce pour la prochaine fois : " + ASTUCE, messages["OT-2026-0001"])
        self.assertIn(MENTION, messages["OT-2026-0003"])
        self.assertNotIn(MENTION, messages["OT-2026-0008"])
        self.assertEqual(self.page.evaluate("Wiki.file().length"), 0)

    def test_collision_vue_meme_avec_un_stockage_lent(self):
        charger_scripts(self.page, SCRIPTS)
        self.page.evaluate(CHARGER_LENT_JS, BASE)
        bilan = self.traiter(EN_FILE, "faux-cree-commun")
        self.assertIsNone(bilan["erreur"])
        self.assertEqual((bilan["acceptees"], bilan["refusees"], bilan["rejouees"]), (6, 0, 2))
        creations = [c["titre"] for e in self.journal().values() for c in json.loads(e["changements"]) if c["creation"]]
        self.assertEqual(sorted(creations), [GESTE, "Usure commune"])

    def test_collision_sur_un_titre_trop_proche(self):
        resultat = self.page.evaluate("""async () => {
          await Wiki.mettreEnFile(['OT-2026-0004', 'OT-2026-0002']);
          const titres = { 'OT-2026-0004': ['Usure commune', 50], 'OT-2026-0002': ['Usures communes', 150] };
          const bilan = await Wiki.traiterFile({ appeler: async (requete, donnees) => {
            const [titre, delai] = titres[donnees.ot.id];
            await new Promise((r) => setTimeout(r, delai));
            return { modele: 'essai', contenu: JSON.stringify({ rien_a_ajouter: false, contradictions: [], pages: [{
              action: 'creer', titre, type: 'savoir-faire', rattache_a: donnees.pages[0].titre, rubriques: [{
              rubrique: 'Quand le faire', phrases: [{ texte: 'Usure des pièces', ot: [donnees.ot.id] }] }] }] }) };
          } });
          return { bilan: [bilan.acceptees, bilan.refusees, bilan.rejouees],
            journal: Donnees.lignes('wiki_journal').filter((e) => e.ot_id !== 'OT-2026-0007')
              .map((e) => [e.ot_id, e.statut, e.motif, e.essais]) };
        }""")
        # 0002 voit « Usure commune » créée pendant son envoi : rejouée (sans relance), puis refusée par les contrôles
        # (titre trop proche), relancée avec la raison et refusée encore : trois essais.
        self.assertEqual(resultat["bilan"], [1, 1, 1])
        self.assertEqual(sorted(resultat["journal"]), [
            ["OT-2026-0002", "refusée", "rejoué : page créée entre-temps", "3"], ["OT-2026-0004", "à valider", "", "1"]])
        raisons = self.journal()["OT-2026-0002"]["raisons"]
        self.assertIn("titre trop proche de « Usure commune »", raisons)

    def test_page_changee_pendant_l_envoi_rejouee(self):
        resultat = self.page.evaluate("""async () => {
          await Wiki.mettreEnFile(['OT-2026-0008']);
          let appels = 0;
          const bilan = await Wiki.traiterFile({ appeler: async (requete) => {
            appels += 1;
            if (requete.messages[1].content.includes('Ta réponse précédente')) throw new Error('collision relancée');
            // Écriture à la main de la page de PO-01 pendant le premier envoi.
            if (appels === 1) await Donnees.modifier('wiki_pages', (lignes) => {
              const ligne = lignes.find((l) => l.id === 'WP-0001');
              ligne.texte = ligne.texte + '\\n## Astuces\\n- Repérer au feutre [OT-2026-0007]';
              ligne.version = '2';
            });
            return { modele: 'essai', contenu: %s };
          } });
          const e = Donnees.lignes('wiki_journal').find((x) => x.ot_id === 'OT-2026-0008');
          return { appels, rejouees: bilan.rejouees, rien: bilan.rien, statut: e.statut, motif: e.motif, essais: e.essais };
        }""" % RIEN)
        self.assertEqual(resultat, {"appels": 2, "rejouees": 1, "rien": 1, "statut": "rien à ajouter",
                                    "motif": "rejoué : pages changées pendant l'envoi", "essais": "2"})
        self.assertEqual(self.page.evaluate("Wiki.MOTIF_PAGES_CHANGEES"), "rejoué : pages changées pendant l'envoi")

    def test_arreter_laisse_finir_les_envois_partis(self):
        resultat = self.page.evaluate("""async () => {
          await Wiki.mettreEnFile(['OT-2026-0004', 'OT-2026-0003', 'OT-2026-0002', 'OT-2026-0006']);
          const arret = new AbortController();
          let appels = 0;
          const bilan = await Wiki.traiterFile({ signal: arret.signal, appeler: async (requete, donnees, annuler) => {
            appels += 1;
            arret.abort();                                    // « Arrêter » pendant les envois
            await new Promise((r) => setTimeout(r, 200));
            if (annuler && annuler.aborted) throw new Error('envoi coupé');
            return { modele: 'essai', contenu: %s };
          } });
          return { appels, rien: bilan.rien, erreur: bilan.erreur && bilan.erreur.message, envois: bilan.envois.length,
            file: Wiki.file().map((e) => e.ot_id) };
        }""" % RIEN)
        # 0004, 0003 et 0002 sont partis ensemble (0006 attend 0004, CV-01) : ils finissent ; rien d'autre ne part.
        self.assertEqual(resultat, {"appels": 3, "rien": 3, "erreur": None, "envois": 3, "file": ["OT-2026-0006"]})

    def test_refus_des_controles(self):
        # Le faux modèle invente à chaque fois : refusée, relancée avec la raison, refusée encore.
        bilan = self.traiter(["OT-2026-0002"], "faux-invente")
        self.assertEqual((bilan["acceptees"], bilan["refusees"], bilan["erreur"]), (0, 1, None))
        entree = self.journal()["OT-2026-0002"]
        self.assertEqual((entree["statut"], entree["modele"], entree["essais"], entree["ordre"]), ("refusée", "faux-invente", "2", ""))
        self.assertIn("OT cité hors des OT permis : OT-1999-9999", entree["raisons"])
        self.assertEqual(len(self.faux.requetes_vers("/api/chat")), 2)
        rien = self.traiter(["OT-2026-0004"], "faux-rien")
        self.assertEqual(rien["rien"], 1)
        self.assertEqual(self.journal()["OT-2026-0004"]["statut"], "rien à ajouter")
        self.assertEqual(self.journal()["OT-2026-0004"]["raisons"], "")

    def test_page_renvoyee_inchangee_comptee_non_renvoyee(self):
        """Relecture de T140 (sonde 84-f) : une page renvoyée avec le texte qu'elle avait à l'envoi — tel quel, ou une fois
        mis en forme (citation écrite dans la phrase) — ne change rien : elle compte comme non renvoyée, ni proposée ni
        contrôlée ; avec une autre page changée, seule celle-ci est proposée ; sans autre page ni contradiction (même avec
        « rien à ajouter » vrai), la réponse vaut « rien à ajouter », jusque dans le journal (aucun changement vide)."""
        po01, kit = "PO-01 — Pompe de process A", "Kit garniture HC 50"
        kit_identique = {"action": "modifier", "titre": kit, "type": "composant", "rattache_a": "", "rubriques": [
            {"rubrique": "À quoi il sert", "phrases": [{"texte": "Étanchéité de l'arbre de la pompe", "ot": ["OT-2026-0007"]}]}]}
        en_bref = [{"texte": "Fuite de garniture au démarrage, fréquent ici [OT-2026-0007]", "ot": []},
                   {"texte": "Voir [[Nettoyer le filtre de CP-01]]", "ot": ["OT-2026-0007"]}]

        def machine(phrases):
            return {"action": "modifier", "titre": po01, "type": "équipement", "rattache_a": "",
                    "rubriques": [{"rubrique": "En bref", "phrases": phrases}]}

        def lire(pages, rien=False):
            reponse = {"rien_a_ajouter": rien, "contradictions": [], "pages": pages}
            return self.page.evaluate(LIRE_JS, ["OT-2026-0001", json.dumps(reponse, ensure_ascii=False)])

        avec = lire([machine(en_bref + [{"texte": "Fuite à la garniture", "ot": ["OT-2026-0001"]}]), kit_identique])
        self.assertTrue(avec["ok"], avec)
        self.assertEqual((avec["lu"]["rien"], [c["titre"] for c in avec["lu"]["changements"]]), (False, [po01]))
        for nom, pages, rien in (("kit seul", [kit_identique], False), ("machine mise en forme", [machine(en_bref)], False),
                                 ("les deux, rien à ajouter vrai", [machine(en_bref), kit_identique], True)):
            with self.subTest(nom):
                lu = lire(pages, rien)
                self.assertTrue(lu["ok"], lu)
                self.assertEqual((lu["lu"]["rien"], lu["lu"]["changements"], lu["lu"]["contradictions"]), (True, [], []))
        # De bout en bout : l'entrée est « rien à ajouter », sans changement enregistré.
        resultat = self.page.evaluate("""async (contenu) => {
          await Wiki.mettreEnFile(['OT-2026-0001']);
          const bilan = await Wiki.traiterFile({ appeler: async () => ({ modele: 'essai', contenu }) });
          const e = Donnees.lignes('wiki_journal').find((x) => x.ot_id === 'OT-2026-0001');
          return [bilan.acceptees, bilan.rien, bilan.refusees, e.statut, e.changements, e.essais];
        }""", json.dumps({"rien_a_ajouter": False, "contradictions": [], "pages": [kit_identique]}, ensure_ascii=False))
        self.assertEqual(resultat, [0, 1, 0, "rien à ajouter", "[]", "1"])

    def test_reponse_qui_decoupe_acceptee(self):
        """CS113 (savoir-faire seulement, §20.12) : une réponse qui découpe un savoir-faire de la machine (faux-decoupe :
        sous-page savoir-faire rattachée à lui, renvoi dans la mère) passe les contrôles ; la sous-page entre dans l'état
        proposé sans ancrage propre ; l'OT suivant de la machine l'envoie juste après sa mère et peut la modifier."""
        mere = "Changer la garniture de PO-01"
        titre = mere + " — étapes détaillées"
        bilan = self.traiter(["OT-2026-0001"], "faux-decoupe")
        self.assertEqual((bilan["acceptees"], bilan["refusees"], bilan["erreur"]), (1, 0, None))
        entree = self.journal()["OT-2026-0001"]
        self.assertEqual((entree["statut"], entree["essais"], entree["raisons"]), ("à valider", "1", ""))
        changements = {c["titre"]: c for c in json.loads(entree["changements"])}
        self.assertEqual(sorted(changements), [GESTE, mere, titre, "PO-01 — Pompe de process A"])
        sous_page = changements[titre]
        self.assertEqual((sous_page["cle"], sous_page["type"], sous_page["creation"], sous_page["rattacheA"]),
                         ("TITRE:changer la garniture de po 01 etapes detaillees", "savoir-faire", True, mere))
        self.assertEqual(sous_page["apres"], "## Étapes" + NL + "- Repérer l'accouplement [OT-2026-0007]")
        self.assertEqual(changements[mere]["apres"], "## Étapes" + NL + "- Détail des étapes : voir [[" + titre + "]] "
                         "[OT-2026-0007]")
        etat = self.page.evaluate("""() => { const p = Wiki.etatPropose().get('TITRE:changer la garniture de po 01 etapes detaillees');
          return [p.type, p.rattacheA, p.equipementId, p.articleId]; }""")
        self.assertEqual(etat, ["savoir-faire", "WP:WP-0002", "", ""])
        # L'OT suivant de PO-01 : la sous-page part juste après sa mère ; la nouvelle phrase y va.
        cles = self.page.evaluate("(ot) => Wiki.pagesConcernees(ot).cles", "OT-2026-0008")
        self.assertEqual(cles.index("TITRE:changer la garniture de po 01 etapes detaillees"), cles.index("WP:WP-0002") + 1)
        self.assertIn("=== Page « " + titre + " » (savoir-faire · sous-page de « " + mere + " » · 1 phrase sur 30, 3 mots "
                      "sur 600) ===", self.message("OT-2026-0008"))
        bilan = self.traiter(["OT-2026-0008"], "faux-decoupe")
        self.assertEqual((bilan["acceptees"], bilan["refusees"], bilan["erreur"]), (1, 0, None))
        suite = json.loads(self.journal()["OT-2026-0008"]["changements"])
        self.assertEqual([(c["titre"], c["creation"], c["version_avant"]) for c in suite], [(titre, False, 1)])
        self.assertTrue(suite[0]["apres"].endswith("- Fuite encore [OT-2026-0008]"), suite[0]["apres"])

    def test_tous_les_textes_de_la_refonte_2_acceptes_de_bout_en_bout(self):
        """§20.12 : la réponse du faux modèle qui écrit tous les textes (faux-textes) — « En bref » qui lie la panne de
        l'OT, « Astuces », « À quoi il sert » de l'article consommé (ce que l'OT observe de lui, T140), un
        savoir-faire pour une méthode — passe les contrôles de bout en bout. Suites de la relecture de T134 : une astuce
        est à un seul endroit — courte, dans « Astuces » sans savoir-faire ; une méthode (« … puis … ») dans un savoir-faire,
        créé puis complété par l'OT suivant qui la porte, et « Astuces » n'en a que le lien."""
        bilan = self.traiter(["OT-2026-0001"], "faux-textes")
        self.assertEqual((bilan["acceptees"], bilan["refusees"], bilan["rejouees"], bilan["erreur"]), (1, 0, 0, None))
        entree = self.journal()["OT-2026-0001"]
        self.assertEqual((entree["statut"], entree["essais"], entree["raisons"]), ("à valider", "1", ""))
        changements = {c["titre"]: (c["type"], c["creation"], c["apres"]) for c in json.loads(entree["changements"])}
        self.assertEqual(changements, {
            "PO-01 — Pompe de process A": ("équipement", False, TEXTE_PO01 + NL
                                           + "- Fuite à la garniture ([[Fuite]]) [OT-2026-0001]" + NL
                                           + "## Astuces" + NL + "- " + ASTUCE + " [OT-2026-0001]"),
            "Kit garniture HC 50": ("composant", False, TEXTE_KIT + NL + "- Défaut constaté : Garniture usée [OT-2026-0001]")})
        self.assertEqual(endroits_de(json.loads(entree["changements"]), ASTUCE), [("PO-01 — Pompe de process A", "Astuces")])
        # Une méthode : 0003 (le plus ancien) crée le savoir-faire, 0008 le complète ; « Astuces » n'en a que le lien.
        self.page.evaluate("""(astuce) => Donnees.modifier('ordres_travail', (lignes) => lignes
          .filter((o) => ['OT-2026-0003', 'OT-2026-0008'].includes(o.id)).forEach((o) => { o.astuce = astuce; }))""", METHODE)
        bilan = self.traiter(["OT-2026-0008", "OT-2026-0003"], "faux-textes")
        self.assertEqual((bilan["acceptees"], bilan["refusees"], bilan["rejouees"], bilan["erreur"]), (2, 0, 0, None))
        journal = self.journal()
        savoir = "Déposer le moteur"                    # savoir-faire commun (T141) : le premier geste, sans repère
        lien = "- Méthode : voir [[" + savoir + "]] "
        attendus = {"OT-2026-0003": ([("PO-01 — Pompe de process A", False), (savoir, True)], "[OT-2026-0003]"),
                    "OT-2026-0008": ([("PO-01 — Pompe de process A", False), (savoir, False)], "[OT-2026-0003] [OT-2026-0008]")}
        for ot, (pages, citations) in attendus.items():
            with self.subTest(ot=ot):
                changements = json.loads(journal[ot]["changements"])
                self.assertEqual(journal[ot]["statut"], "à valider")
                self.assertEqual([(c["titre"], c["creation"]) for c in changements], pages)
                self.assertEqual(endroits_de(changements, METHODE), [(savoir, "Étapes")])
                # Complété par l'OT suivant de la machine : sa phrase de « Particularités par machine » reçoit l'OT.
                self.assertEqual(changements[1]["apres"], NL.join([
                    "## Étapes", "- " + METHODE + " " + citations, "## Particularités par machine",
                    "- [[PO-01 — Pompe de process A]] : Bruit au démarrage " + citations]))
                self.assertIn(NL + "## Astuces" + NL + "- " + ASTUCE + " [OT-2026-0001]" + NL + lien + citations,
                              changements[0]["apres"])

    def test_savoir_faire_commun_cree_puis_complete_par_une_autre_machine(self):
        """T141 (D116, point 7) : le faux modèle crée le savoir-faire commun d'une méthode — titre : son premier geste, sans
        repère — avec la phrase de sa machine dans « Particularités par machine » ; un OT d'une autre machine qui porte le
        même geste le reçoit (Wiki.memeGeste) et le complète (l'OT s'ajoute à l'étape, sa machine a sa phrase) au lieu d'en
        créer un autre : un seul savoir-faire de ce titre ; chaque réponse passe les contrôles."""
        self.page.evaluate("""(methode) => Promise.all([
          Donnees.modifier('equipements', (lignes) => { lignes.push({ id: 'EQ-0004', repere: 'PO-02', designation: 'Pompe de '
            + 'process B', statut: 'en service', actif: '1' }); }),
          Donnees.modifier('ordres_travail', (lignes) => {
            lignes.find((o) => o.id === 'OT-2026-0008').astuce = methode;
            lignes.push({ id: 'OT-2026-0010', equipement_id: 'EQ-0004', type: 'correctif différé', priorite: 'P2',
              statut: 'Clôturé administrativement', titre: 'PO-02 — Fuite au joint', date_creation: '2026-02-14 08:00',
              date_fin: '2026-02-15 08:00', symptome_code: 'S01', cause_code: 'C01', remede_code: 'R01',
              compte_rendu: 'Joint changé.', astuce: methode });
          })])""", METHODE)
        savoir = "Déposer le moteur"
        bilan = self.traiter(["OT-2026-0010"], "faux-textes")
        self.assertEqual((bilan["acceptees"], bilan["refusees"], bilan["erreur"]), (1, 0, None))
        cree = {c["titre"]: c for c in json.loads(self.journal()["OT-2026-0010"]["changements"])}[savoir]
        self.assertEqual((cree["creation"], cree["rattacheA"]), (True, "PO-02 — Pompe de process B"))
        self.assertEqual(cree["apres"], NL.join(["## Étapes", "- " + METHODE + " [OT-2026-0010]", "## Particularités par machine",
                                                 "- [[PO-02 — Pompe de process B]] : Fuite au joint [OT-2026-0010]"]))
        self.assertIn("=== Page « " + savoir + " » (savoir-faire", self.message("OT-2026-0008"))
        bilan = self.traiter(["OT-2026-0008"], "faux-textes")
        self.assertEqual((bilan["acceptees"], bilan["refusees"], bilan["erreur"]), (1, 0, None))
        changements = json.loads(self.journal()["OT-2026-0008"]["changements"])
        self.assertEqual([(c["titre"], c["creation"]) for c in changements], [("PO-01 — Pompe de process A", False), (savoir, False)])
        self.assertEqual(changements[1]["apres"], NL.join([
            "## Étapes", "- " + METHODE + " [OT-2026-0010] [OT-2026-0008]", "## Particularités par machine",
            "- [[PO-02 — Pompe de process B]] : Fuite au joint [OT-2026-0010]",
            "- [[PO-01 — Pompe de process A]] : Fuite encore [OT-2026-0008]"]))
        creations = [c["titre"] for e in self.journal().values() for c in json.loads(e["changements"] or "[]") if c["creation"]]
        self.assertEqual(creations, [savoir])

    def test_a_quoi_il_sert_seulement_ce_que_dit_l_ot(self):
        """T140, C3 : faux-textes n'écrit dans « À quoi il sert » que ce que l'OT observe de l'article (le défaut constaté :
        la cause de l'OT), jamais où ni quand il a été changé, ni la panne qu'il a réglée, ni le titre de l'OT ; un OT qui
        n'en dit rien de plus (sans panne au catalogue — préventif… — ou sans cause) ne renvoie pas la page de l'article,
        et la réponse passe les contrôles."""
        self.page.evaluate("""() => Donnees.modifier('ordres_travail', (lignes) => {
          lignes.find((o) => o.id === 'OT-2026-0002').symptome_code = ''; })""")
        message = self.message("OT-2026-0002")
        self.assertIn("Codes : Encrassement / Nettoyage" + NL, message)
        self.assertIn("=== Page « Filtre à huile » (composant", message)
        reponse = reponse_ingestion(message, "faux-textes")
        self.assertEqual([(p["action"], p["titre"]) for p in reponse["pages"]], [("modifier", "CP-01 — Compresseur")])
        lu = self.page.evaluate(LIRE_JS, ["OT-2026-0002", json.dumps(reponse, ensure_ascii=False)])
        self.assertTrue(lu["ok"], lu)
        # Avec sa panne et sa cause : la phrase de l'article dit le défaut constaté — ni la panne, ni la machine, ni le titre de
        # l'OT (« Rouleaux encrassés »).
        message = self.message("OT-2026-0006")
        avec_panne = reponse_ingestion(message, "faux-textes")
        articles = [p for p in avec_panne["pages"] if p["type"] == "composant"]
        self.assertEqual(len(articles), len([p for p in lire_message(message)["pages"] if p["type"] == "composant"]))
        self.assertGreater(len(articles), 5)
        self.assertEqual({phrase["texte"] for p in articles for r in p["rubriques"] for phrase in r["phrases"]},
                         {"Défaut constaté : Encrassement"})
        textes = json.dumps(articles, ensure_ascii=False)
        for absent in ("Bruit anormal", "CV-01", "Rouleaux", "[["):
            self.assertNotIn(absent, textes)
        self.assertTrue(self.page.evaluate(LIRE_JS, ["OT-2026-0006", json.dumps(avec_panne, ensure_ascii=False)])["ok"])

    def test_en_bref_au_dela_de_sa_limite_le_faux_modele_le_reecrit(self):
        """T142 (D117) : « En bref » au-delà de sa limite (5 phrases d'avant, 3 au plus, lue dans l'en-tête, « à réécrire en
        entier ») : le faux modèle le réécrit en entier — les phrases les plus anciennes partent, la nouvelle en dernier —
        et la réponse passe les contrôles."""
        self.page.evaluate("""() => Donnees.modifier('wiki_pages', (lignes) => { const NL = String.fromCharCode(10);
          lignes.find((l) => l.id === 'WP-0001').texte += ['', '- Bruit de palier [OT-2026-0007]', '- Joint sec [OT-2026-0007]',
            '- Garniture neuve [OT-2026-0007]'].join(NL); })""")
        self.assertIn("(équipement · En bref : 5 phrases sur 3, 20 mots sur 60, à réécrire en entier en 45 mots environ · Astuces : 0 phrase sur 10)",
                      self.message("OT-2026-0008"))
        bilan = self.traiter(["OT-2026-0008"], "faux")
        self.assertEqual((bilan["acceptees"], bilan["refusees"]), (1, 0))
        apres = json.loads(self.journal()["OT-2026-0008"]["changements"])[0]["apres"]
        self.assertEqual(apres, NL.join(["## En bref", "- Joint sec [OT-2026-0007]", "- Garniture neuve [OT-2026-0007]",
                                         "- Fuite encore [OT-2026-0008]"]))

    def test_ancien_texte_reecrit_dans_ses_rubriques(self):
        """Base de développement (avant la refonte 2) : un texte de machine aux anciennes rubriques, réécrit dans les
        siennes en regroupant ses phrases (chaque phrase regroupée cite tous leurs OT), est accepté ; son lien vers un
        titre du catalogue reste un lien, celui vers une ancienne page de mode (absente du catalogue) perd ses crochets,
        comme le dit la consigne — gardé, il est refusé ; le même texte gardé tel quel est refusé (rubriques inconnues)."""
        self.page.evaluate("""() => Donnees.modifier('wiki_pages', (lignes) => { const NL = String.fromCharCode(10);
          lignes.push({ id: 'WP-0030', type: 'équipement', titre: 'CV-01 — Convoyeur', equipement_id: 'EQ-0003', version: '1',
            statut: 'active', origine: 'IA', texte: ['## Ce qui revient', '- Bande qui patine [OT-2026-0004]',
              '- Rouleau bruyant [OT-2026-0004]', '## À surveiller', '- Voir [[Desserrage]] [OT-2026-0004]',
              '- Méthode : [[Nettoyer le filtre de CP-01]] [OT-2026-0004]'].join(NL) }); })""")
        message = self.message("OT-2026-0006")
        self.assertIn("(équipement · En bref : 0 phrase sur 3, 0 mot sur 60, à réécrire en entier en 45 mots environ · Astuces : 0 phrase sur 10) "
                      "===\n## Ce qui revient", message)
        self.assertIn("\n- Nettoyer le filtre de CP-01 (savoir-faire)\n", message)
        self.assertNotIn("- Desserrage (", message)
        reponse = reponse_ingestion(message, "faux")
        lu = self.page.evaluate(LIRE_JS, ["OT-2026-0006", json.dumps(reponse, ensure_ascii=False)])
        self.assertTrue(lu["ok"], lu)
        self.assertEqual(lu["lu"]["changements"][0]["apres"], NL.join([
            "## En bref", "- Ce qui revient : Bande qui patine ; Rouleau bruyant [OT-2026-0004]",
            "- À surveiller : Voir Desserrage ; Méthode : [[Nettoyer le filtre de CP-01]] [OT-2026-0004]",
            "- Rouleaux encrassés [OT-2026-0006]"]))
        # Le lien vers l'ancienne page gardé : refusé (c'est ce que la consigne évite).
        phrase = reponse["pages"][0]["rubriques"][0]["phrases"][1]
        phrase["texte"] = phrase["texte"].replace("Voir Desserrage", "Voir [[Desserrage]]")
        refus = self.page.evaluate(LIRE_JS, ["OT-2026-0006", json.dumps(reponse, ensure_ascii=False)])
        self.assertFalse(refus["ok"])
        self.assertEqual(refus["raisons"], ["Page « CV-01 — Convoyeur » : lien vers une page inconnue « Desserrage »."])
        garde = {"rien_a_ajouter": False, "contradictions": [], "pages": [{"action": "modifier", "titre": "CV-01 — Convoyeur",
                 "type": "équipement", "rattache_a": "", "rubriques": [
                     {"rubrique": "Ce qui revient", "phrases": [{"texte": "Bande qui patine", "ot": ["OT-2026-0004"]},
                                                                {"texte": "Rouleau bruyant", "ot": ["OT-2026-0004"]}]},
                     {"rubrique": "À surveiller", "phrases": [{"texte": "Voir Desserrage", "ot": ["OT-2026-0004"]}]},
                     {"rubrique": "En bref", "phrases": [{"texte": "Rouleaux encrassés", "ot": ["OT-2026-0006"]}]}]}]}
        refus = self.page.evaluate(LIRE_JS, ["OT-2026-0006", json.dumps(garde, ensure_ascii=False)])
        self.assertFalse(refus["ok"])
        self.assertIn("Page « CV-01 — Convoyeur » : rubrique « Ce qui revient » inconnue pour une page équipement.",
                      refus["raisons"])

    def requetes_ia(self):
        """Corps des requêtes reçues par le faux fournisseur : (système, utilisateur, schéma, modèle) de chacune."""
        return [(c["messages"][0]["content"], c["messages"][1]["content"], c["format"], c["model"])
                for c in (r["corps"] for r in self.faux.requetes_vers("/api/chat"))]

    def test_relance_avec_la_raison_puis_acceptee(self):
        """CS112 : la réponse refusée (phrase sans OT) est redemandée une fois par une requête neuve — même système,
        même schéma, message d'origine suivi de la réponse refusée et de chaque raison, rien d'autre — puis acceptée."""
        attendu = self.message("OT-2026-0002")                         # message d'origine, avant l'envoi
        bilan = self.traiter(["OT-2026-0002"], "faux-corrige")
        self.assertEqual((bilan["acceptees"], bilan["refusees"], bilan["rejouees"], bilan["erreur"]), (1, 0, 0, None))
        self.assertEqual(len(bilan["envois"]), 1)                       # la relance fait partie du même envoi
        entree = self.journal()["OT-2026-0002"]
        self.assertEqual((entree["statut"], entree["essais"], entree["modele"], entree["motif"], entree["ordre"]),
                         ("à valider", "2", "faux-corrige", "", "2"))
        raisons = entree["raisons"].split(NL)
        self.assertEqual(raisons, ["Page « CP-01 — Compresseur » : phrase sans OT cité — « Filtre encrassé »."])
        changements = json.loads(entree["changements"])
        self.assertEqual([(c["titre"], c["apres"]) for c in changements],
                         [("CP-01 — Compresseur", "## En bref" + NL + "- Filtre encrassé [OT-2026-0002]")])
        requetes = self.requetes_ia()
        self.assertEqual(len(requetes), 2)
        (systeme, origine, schema, modele), relance = requetes
        self.assertEqual(origine, attendu)
        self.assertNotIn("Ta réponse précédente", origine)
        refusee = json.dumps(reponse_ingestion(origine, "faux-corrige"), ensure_ascii=False)
        self.assertEqual(relance, (systeme, message_de_relance(origine, refusee, raisons), schema, modele))
        for interdit in INTERDITS:
            self.assertNotIn(interdit, relance[1])

    def test_refusee_deux_fois_raisons_du_second_refus(self):
        """CS112 : refusée à l'envoi (phrase sans OT) puis à la relance (OT inventé) → « refusée » avec les raisons du
        second refus ; jamais plus d'une relance."""
        bilan = self.traiter(["OT-2026-0002"], "faux-refuse-deux")
        self.assertEqual((bilan["acceptees"], bilan["refusees"], bilan["erreur"]), (0, 1, None))
        entree = self.journal()["OT-2026-0002"]
        self.assertEqual((entree["statut"], entree["essais"], entree["ordre"]), ("refusée", "2", ""))
        self.assertEqual(entree["raisons"], "Page « CP-01 — Compresseur » : OT cité hors des OT permis : OT-1999-9999.")
        requetes = self.requetes_ia()
        self.assertEqual(len(requetes), 2)
        refusee = json.dumps(reponse_ingestion(requetes[0][1], "faux-refuse-deux"), ensure_ascii=False)
        self.assertEqual(requetes[1][1], message_de_relance(requetes[0][1], refusee, [
            "Page « CP-01 — Compresseur » : phrase sans OT cité — « Filtre encrassé »."]))
        self.assertEqual(self.page.evaluate("Wiki.file().length"), 0)

    def test_relance_d_une_reponse_illisible_et_donnees_de_la_relance(self):
        """Une réponse illisible est relancée de même, avec son message pour raison ; les données de la relance portent
        { reponse, raisons } ; la relance passe par le même `appeler`, une seule fois."""
        resultat = self.page.evaluate("""async () => {
          await Wiki.mettreEnFile(['OT-2026-0004']);
          const recus = [];
          const bilan = await Wiki.traiterFile({ appeler: async (requete, donnees) => {
            recus.push({ relance: donnees.relance || null, message: requete.messages[1].content, ot: donnees.ot.id });
            return { modele: 'essai', contenu: recus.length === 1 ? 'Bien sûr ! Voici ma réponse.' : %s };
          } });
          const e = Donnees.lignes('wiki_journal').find((x) => x.ot_id === 'OT-2026-0004');
          return { recus, rien: bilan.rien, statut: e.statut, essais: e.essais, raisons: e.raisons };
        }""" % RIEN)
        raison = "Réponse de l'IA illisible : aucune proposition."
        self.assertEqual((resultat["rien"], resultat["statut"], resultat["essais"], resultat["raisons"]),
                         (1, "rien à ajouter", "2", raison))
        premier, second = resultat["recus"]
        self.assertEqual((premier["relance"], second["ot"]), (None, "OT-2026-0004"))
        self.assertEqual(second["relance"], {"reponse": "Bien sûr ! Voici ma réponse.", "raisons": [raison]})
        self.assertEqual(second["message"], message_de_relance(premier["message"], "Bien sûr ! Voici ma réponse.", [raison]))

    def test_arreter_retient_la_relance_et_annuler_la_coupe(self):
        refus = "JSON.stringify({ rien_a_ajouter: true, pages: [{ action: 'creer' }], contradictions: [] })"
        resultat = self.page.evaluate("""async () => {
          await Wiki.mettreEnFile(['OT-2026-0004']);
          // « Arrêter » pendant l'envoi dont la réponse est refusée : la relance ne part pas, l'OT reste en file.
          const arret = new AbortController();
          let appels = 0;
          const arrete = await Wiki.traiterFile({ signal: arret.signal, appeler: async () => {
            appels += 1;
            arret.abort();
            return { modele: 'essai', contenu: %s };
          } });
          const apresArret = { appels, refusees: arrete.refusees, envois: arrete.envois.length, erreur: arrete.erreur,
            file: Wiki.file().map((e) => [e.ot_id, e.statut, e.essais]) };
          // `annuler` coupe la relance en cours : elle le reçoit comme l'envoi d'origine.
          const annuler = new AbortController();
          const signaux = [];
          const coupe = await Wiki.traiterFile({ annuler: annuler.signal, appeler: async (requete, donnees, signal) => {
            signaux.push(signal === annuler.signal);
            if (!donnees.relance) return { modele: 'essai', contenu: %s };
            annuler.abort();
            await new Promise((r) => setTimeout(r, 50));
            if (signal.aborted) throw new Error('relance coupée');
            return { modele: 'essai', contenu: %s };
          } });
          return { apresArret, signaux, erreur: coupe.erreur && coupe.erreur.message, refusees: coupe.refusees,
            file: Wiki.file().map((e) => [e.ot_id, e.statut, e.essais]) };
        }""" % (refus, refus, RIEN))
        self.assertEqual(resultat["apresArret"], {"appels": 1, "refusees": 0, "envois": 1, "erreur": None,
                                                  "file": [["OT-2026-0004", "en file", "0"]]})
        self.assertEqual((resultat["signaux"], resultat["erreur"], resultat["refusees"]), ([True, True], "relance coupée", 0))
        self.assertEqual(resultat["file"], [["OT-2026-0004", "en file", "0"]])

    def test_trois_collisions_puis_refus(self):
        resultat = self.page.evaluate("""async () => {
          await Wiki.mettreEnFile(['OT-2026-0002']);
          const titres = ['Grippage', 'Corrosion', 'Fissuration', 'Vibration'];
          let appels = 0;
          const bilan = await Wiki.traiterFile({ agents: 1, appeler: async (requete, donnees) => {
            const titre = titres[appels];
            appels += 1;
            if (donnees.relance || requete.messages[1].content.includes('Ta réponse précédente')) throw new Error('collision relancée');
            // Un autre OT crée la même page pendant l'envoi.
            await Donnees.modifier('wiki_journal', (lignes, outils) => { lignes.push({ id: outils.nouvelId(lignes),
              nature: 'ingestion', statut: 'à valider', ordre: '99', changements: JSON.stringify([{ cle: 'TITRE:'
              + Wiki.comparable(titre), titre, type: 'savoir-faire', creation: true, avant: '', apres: '' }]) }); },
              { journal: false });
            return { modele: 'essai', contenu: JSON.stringify({ rien_a_ajouter: false, contradictions: [], pages: [{
              action: 'creer', titre, type: 'savoir-faire', rattache_a: donnees.pages[0].titre, rubriques: [{
              rubrique: 'Quand le faire', phrases: [{ texte: 'Constaté sur le compresseur', ot: [donnees.ot.id] }] }] }] }) };
          } });
          const entree = Donnees.lignes('wiki_journal').find((e) => e.ot_id === 'OT-2026-0002');
          return { appels, rejouees: bilan.rejouees, refusees: bilan.refusees, statut: entree.statut, essais: entree.essais,
            raisons: entree.raisons, motif: entree.motif };
        }""")
        self.assertEqual(resultat, {"appels": 4, "rejouees": 3, "refusees": 1, "statut": "refusée", "essais": "4",
                                    "raisons": "Page créée en même temps par un autre OT, 4 essais.",
                                    "motif": "rejoué : page créée entre-temps"})
        self.assertEqual(self.page.evaluate("Wiki.MOTIF_COLLISION"), "rejoué : page créée entre-temps")

    def test_ia_injoignable_arret_et_ot_en_file(self):
        self.autoriser_erreur("ERR_CONNECTION_REFUSED")
        self.page.evaluate("(url) => Ia.enregistrerReglages({ url })", "http://127.0.0.1:%d" % port_libre())
        bilan = self.page.evaluate(TRAITER_JS, [["OT-2026-0004", "OT-2026-0002"], {"agents": 1}])
        self.assertIsNotNone(bilan["erreur"])
        self.assertEqual((bilan["acceptees"], bilan["refusees"], len(bilan["envois"])), (0, 0, 1))
        self.assertEqual([(e["ot_id"], e["statut"], e["essais"]) for e in self.page.evaluate("Wiki.file()")],
                         [("OT-2026-0004", "en file", "0"), ("OT-2026-0002", "en file", "0")])
        # Arrêt demandé : rien ne part.
        controleur = self.page.evaluate("""async () => { const c = new AbortController(); c.abort();
          const b = await Wiki.traiterFile({ signal: c.signal }); return b.envois.length; }""")
        self.assertEqual(controleur, 0)


# ---------------------------------------------------------------------------------------------------
# Dans l'application : crochet de clôture administrative, même requête dans les trois modes
# ---------------------------------------------------------------------------------------------------

LISTE_REQUETES_JS = """() => { const etat = Wiki.etatPropose();
  return Donnees.lignes('ordres_travail').filter((o) => o.statut === 'Clôturé administrativement').map((o) => o.id).sort()
    .map((id) => Ia.requete('ingestionWiki', Wiki.donneesIngestion(id, etat))); }"""
FICHIERS_JS = """() => Object.fromEntries(Object.entries(Donnees.instantane())
  .map(([nom, octets]) => [nom, new TextDecoder().decode(octets)]))"""
# Écrit de la même façon dans chaque mode, par-dessus le wiki de la démo (qui peut déjà avoir la page) : une phrase
# de plus sur la page de l'équipement du premier OT (créée si besoin) et une proposition à valider qui crée une page.
AJOUT_WIKI_JS = """async () => {
  const ot = Donnees.lignes('ordres_travail').filter((o) => o.statut === 'Clôturé administrativement').map((o) => o.id).sort()[0];
  const equipement = Donnees.trouver('equipements', Donnees.trouver('ordres_travail', ot).equipement_id);
  const phrase = '\\n- Panne connue ici [' + ot + ']';
  await Donnees.modifier('wiki_pages', (lignes) => {
    const ligne = lignes.find((l) => l.type === 'équipement' && l.equipement_id === equipement.id && l.statut !== 'archivée');
    if (ligne) ligne.texte = (ligne.texte || '## En bref') + phrase;
    else lignes.push({ id: 'WP-9001', type: 'équipement', titre: equipement.repere + ' — ' + equipement.designation,
      equipement_id: equipement.id, version: '1', statut: 'active', texte: '## En bref' + phrase });
  });
  await Donnees.modifier('wiki_journal', (lignes) => { lignes.push({ id: 'WJ-99001', nature: 'ingestion', ot_id: ot,
    statut: 'à valider', ordre: '9999', essais: '1', changements: JSON.stringify([{ cle: 'TITRE:usure commune essai',
    titre: 'Usure commune essai', type: 'savoir-faire', creation: true, rattacheA: equipement.repere + ' — ' + equipement.designation,
    version_avant: 0, avant: '', apres: '## Quand le faire\\n- Usure [' + ot + ']' }]) }); });
}"""
ERREURS_SERVEUR_STATIQUE = [re.compile(r"status of 404.*/api/ping"), re.compile(r"status of 404.*/api/csv/")]


class TestDansLApplication(CasNavigateur):

    def ouvrir_demo(self, page=None):
        page = page or self.page
        page.goto(url_fichier("index.html"))
        page.click("#btn-demo")
        attendre_pret(page)
        return page

    def test_cloture_administrative_met_en_file_et_un_echec_ne_l_annule_pas(self):
        preregler_profil(self.contexte, "responsable")
        page = self.ouvrir_demo()
        ids = page.evaluate("""() => Donnees.lignes('ordres_travail').filter((o) => o.statut === 'Clôturé techniquement')
          .map((o) => o.id).slice(0, 2)""")
        self.assertEqual(len(ids), 2)
        statut = page.evaluate("(ot) => Ordres.changerStatut(ot, 'Clôturé techniquement', 'Clôturé administrativement')", ids[0])
        self.assertEqual(statut, "Clôturé administrativement")
        entree = page.evaluate("(ot) => Donnees.lignes('wiki_journal').find((e) => e.ot_id === ot)", ids[0])
        date_fin = page.evaluate("(ot) => Donnees.trouver('ordres_travail', ot).date_fin", ids[0])
        self.assertEqual((entree["nature"], entree["statut"], entree["date_intervention"], entree["essais"]),
                         ("ingestion", "en file", date_fin, "0"))
        page.wait_for_function("(document.getElementById('toast') || {}).textContent === 'OT ajouté à la file du wiki.'")
        # La mise en file échoue : la clôture reste faite, l'OT reste « hors du wiki », le message le dit.
        page.evaluate("""() => { const modifier = Donnees.modifier;
          Donnees.modifier = function (table) { if (table === 'wiki_journal') return Promise.reject(new Error('disque plein'));
            return modifier.apply(this, arguments); }; }""")
        statut = page.evaluate("(ot) => Ordres.changerStatut(ot, 'Clôturé techniquement', 'Clôturé administrativement')", ids[1])
        self.assertEqual(statut, "Clôturé administrativement")
        self.assertEqual(page.evaluate("(ot) => Donnees.trouver('ordres_travail', ot).statut", ids[1]), "Clôturé administrativement")
        page.wait_for_function("(document.getElementById('toast') || {}).textContent.includes('hors du wiki')")
        self.assertIn("disque plein", page.inner_text("#toast"))
        self.assertIn(ids[1], page.evaluate("Wiki.horsDuWiki().map((o) => o.id)"))
        self.assertNotIn(ids[0], page.evaluate("Wiki.horsDuWiki().map((o) => o.id)"))

    def test_meme_requete_en_modes_demo_dossier_et_serveur(self):
        for motif in ERREURS_SERVEUR_STATIQUE:
            self.autoriser_erreur(motif)
        preregler_profil(self.contexte, "responsable")
        page = self.ouvrir_demo()
        self.assertEqual(page.evaluate("App.mode"), "demo")
        fichiers = page.evaluate(FICHIERS_JS)
        page.evaluate(AJOUT_WIKI_JS)
        demo = page.evaluate(LISTE_REQUETES_JS)
        messages = [r["messages"][1]["content"] for r in demo]
        self.assertTrue(any("- Panne connue ici [OT-" in m for m in messages))
        self.assertTrue(all("- Usure commune essai (savoir-faire)" in m for m in messages))
        noms = page.evaluate("""() => Donnees.lignes('techniciens').map((t) => (t.prenom + ' ' + t.nom).trim())
          .concat(Donnees.lignes('demandes').map((d) => d.demandeur)).filter(Boolean)""")
        astuces = page.evaluate("""() => Donnees.lignes('ordres_travail').filter((o) => o.statut === 'Clôturé administrativement'
          && o.astuce).map((o) => o.id)""")
        self.assertGreater(len(demo), 100)
        self.assertGreater(len(astuces), 40)
        par_ot = {r["messages"][1]["content"].split(" · ")[0].replace("OT à intégrer : ", ""): r for r in demo}
        for ot in astuces:
            self.assertIn("Astuce pour la prochaine fois : ", par_ot[ot]["messages"][1]["content"])
        tout = json.dumps(demo, ensure_ascii=False)
        for nom in set(noms):
            self.assertNotIn(nom, tout)

        # Mode dossier : base de démo écrite dans un dossier vide (mêmes fichiers).
        contexte_dossier = self.navigateur.new_context(locale="fr-FR")
        self.addCleanup(contexte_dossier.close)
        preregler_profil(contexte_dossier, "responsable")
        installer_dossier_simule(contexte_dossier, "donnees-ingestion")
        with ServeurStatique(RACINE) as statique:
            page_dossier = contexte_dossier.new_page()
            self.surveiller(page_dossier)
            page_dossier.goto(statique.url + "/index.html")
            page_dossier.click("#btn-dossier")
            page_dossier.wait_for_selector("#btn-base-demo", state="visible")
            page_dossier.click("#btn-base-demo")
            attendre_pret(page_dossier, 30000)
            self.assertEqual(page_dossier.evaluate("App.mode"), "dossier")
            page_dossier.evaluate(AJOUT_WIKI_JS)
            dossier = page_dossier.evaluate(LISTE_REQUETES_JS)
        self.assertEqual(dossier, demo)

        # Mode serveur : les fichiers de la démo en mémoire, écrits dans un dossier de données.
        source = Path(tempfile.mkdtemp(prefix="prevo-ingestion-"))
        self.addCleanup(shutil.rmtree, source, True)
        for nom, contenu in fichiers.items():
            (source / (nom + ".csv")).write_text(contenu, encoding="utf-8-sig", newline="")
        contexte_serveur = self.navigateur.new_context(locale="fr-FR")
        self.addCleanup(contexte_serveur.close)
        preregler_profil(contexte_serveur, "responsable")
        with ServeurPrevo(source) as serveur:
            page_serveur = contexte_serveur.new_page()
            self.surveiller(page_serveur)
            page_serveur.goto(serveur.url + "/")
            attendre_pret(page_serveur, 30000)
            self.assertEqual(page_serveur.evaluate("App.mode"), "serveur")
            page_serveur.evaluate(AJOUT_WIKI_JS)
            self.assertEqual(page_serveur.evaluate(LISTE_REQUETES_JS), demo)


if __name__ == "__main__":
    unittest.main()
