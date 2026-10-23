"""Ingestion du wiki : file, pages concernées, antériorité, données envoyées, ordonnanceur, traitement de la file
(lot 6 refondu, tâche T115 ; ARCHITECTURE.md §20.5 ; D104, D111, D112 ; CS99, CS110).

    liste blanche : la requête d'un OT contient son astuce, son compte rendu, ses codes, le symptôme de sa DI, les
                    pièces consommées (sorties − retours), les pages concernées et le catalogue ; jamais le nom d'un
                    technicien ou d'un demandeur, un coût, un taux horaire, une valeur, le numéro de série, les
                    consignes, la consignation, la description ou la photo de la DI, un document ; les rubriques de la
                    consigne sont celles de Wiki.RUBRIQUES ;
    pages         : clés et pages envoyées d'un OT dans l'ordre de priorité (équipement, savoir-faire de l'équipement
                    — par ancrage ou par rattachement —, articles consommés, savoir-faire des articles, cause, modes
                    de la cause, pages liées), page archivée exclue, plafond des pages envoyées ;
    file          : ordre par date d'intervention puis numéro d'OT, quel que soit l'ordre de mise en file ou de
                    clôture (OT importés compris) ; OT non clôturé administrativement, inconnu ou déjà intégré écarté ;
    antériorité   : mention et dates pour un OT plus ancien que les faits de SES pages ; aucune mention si les OT plus
                    récents sont ailleurs ; « Désormais » refusé pour lui seul ;
    ordonnanceur  : prochainsEnvois (plafond d'agents, clés prises par un envoi en cours ou par une entrée plus
                    ancienne restée en attente) ;
    traitement    : bout en bout avec le faux fournisseur (requêtes réellement envoyées, état proposé enchaîné,
                    antériorité notée, ordre par page, aucune page dans deux envois à la fois) ; refus → « refusée »
                    avec ses raisons ; collision → « en file » avec le motif puis acceptée, et « refusée » après trois
                    collisions ; IA injoignable → arrêt, OT laissés en file ;
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
from faux_wiki import reponse_ingestion

SCRIPTS = [
    "js/lib/papaparse.min.js", "js/schema.js", "js/donnees.js", "js/stockage-demo.js",
    "js/modules/causes-frequentes.js", "js/modules/indicateurs-regles.js", "js/modules/ia.js", "js/modules/ia-prompts.js",
    "js/modules/wiki-regles.js", "js/modules/wiki-calculs.js", "js/modules/wiki-texte.js", "js/modules/wiki-recherche.js",
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
ASTUCE = "Marquer la position de l'accouplement avant la dépose."

EQUIPEMENTS = table_csv("id;repere;designation;marque;modele;num_serie;statut;consignation;document;actif;valeur_remplacement", [
    "EQ-0001;'PO-01;Pompe de process A;Hydro Nel;HC 50;SN-SECRET-4711;en service;Cadenasser Q1;plan-secret.pdf;1;45678.9",
    "EQ-0002;'CP-01;Compresseur;;;;en service;;;1;",
    "EQ-0003;'CV-01;Convoyeur;;;;en service;;;1;",
])
CODES = table_csv("id;famille;code;libelle", [
    "CD-0001;symptôme;S01;Fuite", "CD-0002;symptôme;S02;Bruit anormal",
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


TEXTE_PO01 = ("## Ce qui revient" + NL + "- Fuite de garniture au démarrage, fréquent ici [OT-2026-0007]" + NL
              + "## À surveiller" + NL + "- Voir [[Cavitation]] [OT-2026-0007]")
WIKI_PAGES = table_csv(ENTETE_WIKI, [
    page_wiki("WP-0001", "équipement", "PO-01 — Pompe de process A", TEXTE_PO01, equipement="EQ-0001"),
    page_wiki("WP-0002", "savoir-faire", "Changer la garniture de PO-01", "## Étapes" + NL + "- Repérer l'accouplement [OT-2026-0007]",
              equipement="EQ-0001"),
    page_wiki("WP-0003", "composant", "Kit garniture HC 50", "## Défaillances" + NL + "- Usure de la face [OT-2026-0007]",
              article="ART-0001"),
    # Rattaché à la page du composant (pas d'article_id) : trouvé par son rattachement.
    page_wiki("WP-0004", "savoir-faire", "Monter le kit garniture", "## Étapes" + NL + "- Lubrifier les joints [OT-2026-0007]",
              rattache="WP-0003"),
    page_wiki("WP-0005", "mode", "Usure de garniture", "## Causes" + NL + "- Garniture usée [OT-2026-0007]", cause="C01"),
    page_wiki("WP-0006", "mode", "Cavitation", "## Symptômes" + NL + "- Bruit de gravier [OT-2026-0007]"),
    page_wiki("WP-0007", "mode", "Desserrage", cause="C03"),
    page_wiki("WP-0008", "savoir-faire", "Nettoyer le filtre de CP-01", equipement="EQ-0002"),
    page_wiki("WP-0009", "savoir-faire", "Ancien geste", "## Étapes" + NL + "- Vieux [OT-2026-0007]", equipement="EQ-0001",
              statut="archivée"),
    # Rattaché à la page de l'équipement (pas d'equipement_id) : trouvé par son rattachement.
    page_wiki("WP-0010", "savoir-faire", "Graisser le palier", "## Étapes" + NL + "- Graisser [OT-2026-0007]", rattache="WP-0001"),
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
                        "=== Page « PO-01 — Pompe de process A » (équipement · 2 phrases sur 12, 14 mots sur 250) ===",
                        TEXTE_PO01,
                        "Catalogue des pages :", "- Cavitation (mode)", "- Roulement 6205 (composant)"):
            self.assertIn(attendu, message)
        tout = json.dumps(requete, ensure_ascii=False)
        for interdit in INTERDITS:
            self.assertNotIn(interdit, tout)
        self.assertEqual([u for u in self.requetes if not u.startswith(("file:", "data:"))], [])

    def test_rubriques_de_la_consigne_celles_du_wiki(self):
        systeme = self.page.evaluate(REQUETE_JS, "OT-2026-0002")["messages"][0]["content"]
        for type_, rubriques in self.page.evaluate("Wiki.RUBRIQUES").items():
            self.assertIn(type_ + " « " + " », « ".join(rubriques) + " »", systeme)

    def test_pages_concernees_dans_l_ordre_de_priorite(self):
        concernees = self.page.evaluate("(ot) => Wiki.pagesConcernees(ot)", "OT-2026-0001")
        # Ordre du §20.5 : équipement, articles, cause (clé seule), savoir-faire (équipement puis articles), modes de
        # la cause, pages liées depuis la page de l'équipement.
        self.assertEqual(concernees["cles"], ["EQ:EQ-0001", "ART:ART-0001", "CAUSE:C01", "WP:WP-0002", "WP:WP-0010",
                                              "WP:WP-0004", "WP:WP-0005", "WP:WP-0006"])
        self.assertEqual([p["titre"] for p in concernees["envoyees"]],
                         ["PO-01 — Pompe de process A", "Kit garniture HC 50", "Changer la garniture de PO-01",
                          "Graisser le palier", "Monter le kit garniture", "Usure de garniture", "Cavitation"])
        # Pages calculées (sans ligne) : équipement et article ; la cause réserve sa clé sans page.
        calculees = self.page.evaluate("(ot) => Wiki.pagesConcernees(ot)", "OT-2026-0002")
        self.assertEqual(calculees["cles"], ["EQ:EQ-0002", "ART:ART-0003", "CAUSE:C02", "WP:WP-0008"])
        self.assertEqual([(p["titre"], p["type"], p["texte"]) for p in calculees["envoyees"]],
                         [("CP-01 — Compresseur", "équipement", ""), ("Filtre à huile", "composant", ""),
                          ("Nettoyer le filtre de CP-01", "savoir-faire", "")])
        # Neuf articles consommés : toutes les clés, huit pages envoyées au plus.
        nombreuses = self.page.evaluate("(ot) => Wiki.pagesConcernees(ot)", "OT-2026-0006")
        self.assertEqual(nombreuses["cles"], ["EQ:EQ-0003"] + ["ART:ART-%04d" % n for n in range(4, 13)]
                         + ["CAUSE:C02"])
        self.assertEqual(len(nombreuses["envoyees"]), self.page.evaluate("Wiki.SEUILS.pagesEnvoyeesMax"))
        self.assertEqual(len(nombreuses["envoyees"]), 8)

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
            cle: 'TITRE:zzz usure tardive', titre: 'Zzz usure tardive', type: 'mode', creation: true, version_avant: 0,
            avant: '', apres: '## Causes\\n- Usure [OT-2026-0004]' }]) }); });
          return Wiki.donneesIngestion('OT-2026-0002').catalogue;
        }""")
        self.assertEqual(len(catalogue), self.page.evaluate("Wiki.SEUILS.catalogueMax"))
        self.assertIn({"titre": "Zzz usure tardive", "type": "mode"}, catalogue)

    def test_prochains_envois(self):
        self.page.evaluate("(ids) => Wiki.mettreEnFile(ids)", EN_FILE)
        choisir = """([agents, enCours]) => Wiki.prochainsEnvois(Wiki.file(), enCours, { agents })
          .map((c) => c.entree.ot_id)"""
        # 0003, 0001 et 0008 attendent 0004 (cause C03) puis 0003 (PO-01) ; 0006 attend 0004 (CV-01).
        self.assertEqual(self.page.evaluate(choisir, [5, []]), ["OT-2026-0004", "OT-2026-0002"])
        self.assertEqual(self.page.evaluate(choisir, [1, []]), ["OT-2026-0004"])
        self.assertEqual(self.page.evaluate(choisir, [5, [{"cles": ["ART:ART-0003"]}]]), ["OT-2026-0004"])
        self.assertEqual(self.page.evaluate(choisir, [2, [{"cles": ["EQ:EQ-0009"]}]]), ["OT-2026-0004"])
        self.assertEqual(self.page.evaluate(choisir, [5, [{"cles": ["CAUSE:C03"]}]]), ["OT-2026-0002"])


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
        bilan = self.traiter(EN_FILE, "faux-cree-mode")
        self.assertIsNone(bilan["erreur"])
        # 0004 et 0002 partent ensemble et créent tous deux « Usure commune » : le second est rejoué.
        self.assertEqual((bilan["acceptees"], bilan["rien"], bilan["refusees"], bilan["rejouees"]), (6, 0, 0, 1))
        journal = self.journal()
        self.assertEqual(sorted(journal), sorted(EN_FILE))
        self.assertEqual({ot: e["statut"] for ot, e in journal.items()}, {ot: "à valider" for ot in EN_FILE})
        self.assertEqual({ot: e["anterieure"] for ot, e in journal.items()},
                         {"OT-2026-0004": "0", "OT-2026-0003": "1", "OT-2026-0001": "1", "OT-2026-0002": "0",
                          "OT-2026-0006": "0", "OT-2026-0008": "0"})
        self.assertEqual(sorted(e["essais"] for e in journal.values()), ["1", "1", "1", "1", "1", "2"])
        # Le motif du rejeu reste sur l'entrée acceptée ensuite (D112 : le journal le note).
        self.assertEqual(sorted(e["motif"] for e in journal.values()), [""] * 5 + ["rejoué : page créée entre-temps"])
        self.assertTrue(all(e["modele"] == "faux-cree-mode" for e in journal.values()), journal)
        creations = [c["titre"] for e in journal.values() for c in json.loads(e["changements"]) if c["creation"]]
        self.assertEqual(sorted(creations), ["Astuce de l'OT-2026-0001", "Usure commune"])
        # Pour chaque page : les OT dans l'ordre des dates d'intervention (rang de traitement), jamais deux à la fois.
        envois = bilan["envois"]
        self.assertEqual(len(envois), 7)
        for cle in {cle for envoi in envois for cle in envoi["cles"]}:
            avec = sorted((e for e in envois if cle in e["cles"]), key=lambda e: e["debut"])
            for avant, apres in zip(avec, avec[1:]):
                self.assertLess(avant["fin"], apres["debut"], (cle, avant, apres))
        rang = {ot: int(e["ordre"]) for ot, e in journal.items()}
        self.assertLess(rang["OT-2026-0003"], rang["OT-2026-0001"])
        self.assertLess(rang["OT-2026-0001"], rang["OT-2026-0008"])
        self.assertLess(rang["OT-2026-0004"], rang["OT-2026-0006"])
        # État proposé enchaîné : la page de PO-01 de la dernière proposition garde tout et cite les trois OT.
        page_po01 = [c for c in json.loads(journal["OT-2026-0008"]["changements"]) if c["cle"] == "EQ:EQ-0001"][0]
        for ot in ("OT-2026-0003", "OT-2026-0001", "OT-2026-0007", "OT-2026-0008"):
            self.assertIn("[" + ot + "]", page_po01["apres"])
        self.assertIn("[[Cavitation]]", page_po01["apres"])
        # Versions enchaînées (D105) : WP-0001 est en version 1 ; chaque proposition plus ancienne en attente l'avance.
        versions = {ot: [(c["page"], c["version_avant"]) for c in json.loads(journal[ot]["changements"]) if c["cle"] == "EQ:EQ-0001"]
                    for ot in ("OT-2026-0003", "OT-2026-0001", "OT-2026-0008")}
        self.assertEqual(versions, {"OT-2026-0003": [("WP-0001", 1)], "OT-2026-0001": [("WP-0001", 2)],
                                    "OT-2026-0008": [("WP-0001", 3)]})
        self.assertEqual(self.page.evaluate("Wiki.etatPropose().get('EQ:EQ-0001').version"), 4)
        self.assertEqual(journal["OT-2026-0001"]["pages"].split(";")[:4], ["EQ:EQ-0001", "ART:ART-0001", "CAUSE:C01", "WP:WP-0002"])
        # Requêtes réellement envoyées : une par envoi, rien d'interdit, l'astuce de 0001 et la mention de 0003.
        corps = [r["corps"] for r in self.faux.requetes_vers("/api/chat")]
        self.assertEqual(len(corps), 7)
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
        bilan = self.traiter(EN_FILE, "faux-cree-mode")
        self.assertIsNone(bilan["erreur"])
        self.assertEqual((bilan["acceptees"], bilan["refusees"], bilan["rejouees"]), (6, 0, 1))
        creations = [c["titre"] for e in self.journal().values() for c in json.loads(e["changements"]) if c["creation"]]
        self.assertEqual(sorted(creations), ["Astuce de l'OT-2026-0001", "Usure commune"])

    def test_collision_sur_un_titre_trop_proche(self):
        resultat = self.page.evaluate("""async () => {
          await Wiki.mettreEnFile(['OT-2026-0004', 'OT-2026-0002']);
          const titres = { 'OT-2026-0004': ['Usure commune', 50], 'OT-2026-0002': ['Usures communes', 150] };
          const bilan = await Wiki.traiterFile({ appeler: async (requete, donnees) => {
            const [titre, delai] = titres[donnees.ot.id];
            await new Promise((r) => setTimeout(r, delai));
            return { modele: 'essai', contenu: JSON.stringify({ rien_a_ajouter: false, contradictions: [], pages: [{
              action: 'creer', titre, type: 'mode', rattache_a: '', rubriques: [{ rubrique: 'Causes', phrases: [{
              texte: 'Usure des pièces', ot: [donnees.ot.id] }] }] }] }) };
          } });
          return { bilan: [bilan.acceptees, bilan.refusees, bilan.rejouees],
            journal: Donnees.lignes('wiki_journal').filter((e) => e.ot_id !== 'OT-2026-0007')
              .map((e) => [e.ot_id, e.statut, e.motif, e.essais]) };
        }""")
        # 0002 voit « Usure commune » créée pendant son envoi : rejouée, puis refusée par les contrôles (titre trop proche).
        self.assertEqual(resultat["bilan"], [1, 1, 1])
        self.assertEqual(sorted(resultat["journal"]), [
            ["OT-2026-0002", "refusée", "rejoué : page créée entre-temps", "2"], ["OT-2026-0004", "à valider", "", "1"]])
        raisons = self.journal()["OT-2026-0002"]["raisons"]
        self.assertIn("titre trop proche de « Usure commune »", raisons)

    def test_page_changee_pendant_l_envoi_rejouee(self):
        resultat = self.page.evaluate("""async () => {
          await Wiki.mettreEnFile(['OT-2026-0008']);
          let appels = 0;
          const bilan = await Wiki.traiterFile({ appeler: async () => {
            appels += 1;
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
          await Wiki.mettreEnFile(['OT-2026-0004', 'OT-2026-0003', 'OT-2026-0002']);
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
        # 0004 et 0002 sont partis ensemble (0003 attend 0004, cause C03) : ils finissent ; rien d'autre ne part.
        self.assertEqual(resultat, {"appels": 2, "rien": 2, "erreur": None, "envois": 2, "file": ["OT-2026-0003"]})

    def test_refus_des_controles(self):
        bilan = self.traiter(["OT-2026-0002"], "faux-invente")
        self.assertEqual((bilan["acceptees"], bilan["refusees"], bilan["erreur"]), (0, 1, None))
        entree = self.journal()["OT-2026-0002"]
        self.assertEqual((entree["statut"], entree["modele"], entree["essais"], entree["ordre"]), ("refusée", "faux-invente", "1", ""))
        self.assertIn("OT cité hors des OT permis : OT-1999-9999", entree["raisons"])
        rien = self.traiter(["OT-2026-0004"], "faux-rien")
        self.assertEqual(rien["rien"], 1)
        self.assertEqual(self.journal()["OT-2026-0004"]["statut"], "rien à ajouter")

    def test_trois_collisions_puis_refus(self):
        resultat = self.page.evaluate("""async () => {
          await Wiki.mettreEnFile(['OT-2026-0002']);
          const titres = ['Grippage', 'Corrosion', 'Fissuration', 'Vibration'];
          let appels = 0;
          const bilan = await Wiki.traiterFile({ agents: 1, appeler: async (requete, donnees) => {
            const titre = titres[appels];
            appels += 1;
            // Un autre OT crée la même page pendant l'envoi.
            await Donnees.modifier('wiki_journal', (lignes, outils) => { lignes.push({ id: outils.nouvelId(lignes),
              nature: 'ingestion', statut: 'à valider', ordre: '99', changements: JSON.stringify([{ cle: 'TITRE:'
              + Wiki.comparable(titre), titre, type: 'mode', creation: true, avant: '', apres: '' }]) }); }, { journal: false });
            return { modele: 'essai', contenu: JSON.stringify({ rien_a_ajouter: false, contradictions: [], pages: [{
              action: 'creer', titre, type: 'mode', rattache_a: '', rubriques: [{ rubrique: 'Causes', phrases: [{
              texte: 'Constaté sur le compresseur', ot: [donnees.ot.id] }] }] }] }) };
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
    if (ligne) ligne.texte = (ligne.texte || '## Ce qui revient') + phrase;
    else lignes.push({ id: 'WP-9001', type: 'équipement', titre: equipement.repere + ' — ' + equipement.designation,
      equipement_id: equipement.id, version: '1', statut: 'active', texte: '## Ce qui revient' + phrase });
  });
  await Donnees.modifier('wiki_journal', (lignes) => { lignes.push({ id: 'WJ-99001', nature: 'ingestion', ot_id: ot,
    statut: 'à valider', ordre: '9999', essais: '1', changements: JSON.stringify([{ cle: 'TITRE:usure commune essai',
    titre: 'Usure commune essai', type: 'mode', creation: true, version_avant: 0, avant: '', apres: '## Causes\\n- Usure [' + ot + ']' }]) }); });
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
        self.assertTrue(all("- Usure commune essai (mode)" in m for m in messages))
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
