"""Recette du lot 5 : assistant d'import, de bout en bout (tâche T86, ARCHITECTURE.md §18 ; CS79, CS81, CS84,
CS85, CS92, CS93, CS95). Les fichiers d'essai sont les vrais (tests/fixtures/import/, LISEZMOI.md), lus par
Import.lire dans la page ; correspondance des colonnes automatique (Import.correspondance), jamais corrigée : le
LISEZMOI n'en prévoit aucune correction (toutes « sûres », colonnes inconnues « non utilisées »).

Familles (le nom du test le dit) :
    reprise : serveur.py sur une base VIDE (« Créer une base vide »), un atelier complet repris dans l'ordre du
              LISEZMOI pour une base vide : codes.csv, techniciens.tsv, fournisseurs.tsv (collage),
              equipements.xlsx (par l'écran #/import de bout en bout : lien de l'accueil, dépôt du fichier,
              cinq étapes, « Importer »), articles.csv, habilitations.csv, compteurs.csv, controles.csv,
              gammes.xlsx, historique.csv. Ensuite :
              - totaux de chaque aperçu = ceux du LISEZMOI transposés à la base vide (« identique » et « mettre à
                jour » deviennent « créer », plus les différences qu'il annonce) ; fiches de chaque table = celles
                de l'aperçu ; comptes finaux recalculés ici (localisations des chemins du parc, fournisseurs du
                collage et des articles, mouvements « inventaire ») ; journal : une ligne de bilan par table ;
              - stock affiché (fiche article) = stock du fichier ; une sauvegarde « …_avant-import » par import sur
                le disque, celle d'avant l'historique égale aux CSV d'avant ; Donnees.problemes() sans erreur ;
              - historique compté (calcul indépendant ici, depuis historique.csv) : MTBF, MTTR et disponibilité de
                l'écran Indicateurs et de Indicateurs.parEquipement ; la panne sans durée d'arrêt (PR-01, ligne 7)
                compte dans le MTBF mais est exclue du MTTR et de la disponibilité (ajustement 3 de D92) ; causes
                fréquentes d'un symptôme ; suggestion de préventif S1 (écran Préventif → Suggestions) ;
              - réimport des dix fichiers : 0 créé, 0 mis à jour (historique : doublons sûrs par l'ancien numéro) ;
              - accueil après import à 1440 et 375 px sans défilement horizontal ;
              - annulation du dernier import (historique) : les 22 CSV identiques à l'octet à ceux d'avant
                (journal mis à part) ;
    demo    : index.html en file:// → démo : chaque fichier d'essai importé seul (le parc dans ses trois formats)
              → totaux égaux au tableau du LISEZMOI ; « Annuler » → tables rendues à l'octet (instantané) ;
    design  : démo, écran #/import à 1440 et 375 px à chaque étape (historique.csv), résultat de l'import, puis
              l'accueil : aucun défilement horizontal ; au téléphone, zones de l'assistant d'au moins 48 px.
Aucune erreur dans la console (CasNavigateur). Horloge du navigateur fixée à la date de référence de la démo
(js/demo-donnees.js) : la démo n'est pas décalée et les tests passent à toute heure.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_recette_lot5.py" -v
"""
import base64
import csv
import datetime
import hashlib
import io
import math
import re
import unittest

from commun import ServeurPrevo, attendre_pret, preregler_profil
from test_app import ERREUR_CSV_ABSENT
from test_controles import date_reference
from test_fixtures_import import lire_xlsx
from test_import_ecrans import (COLONNES_EQUIPEMENTS, FIXTURES, INSTANTANE_JS, JOURNAL_JS, LARGEUR_JS, MOTIF_AVANT_IMPORT,
                                CasImport)

REFERENCE = date_reference()
HEURE_FIXE = REFERENCE.isoformat() + "T09:30:00"
MAINTENANT = REFERENCE.isoformat() + " 09:30"
ACTIONS = ("creer", "mettre_a_jour", "identique", "refusee", "doublon_sur", "doublon_suppose")

# Ordre d'import sur une base vide (LISEZMOI, « Enchaînement sur une base vide ») et type de chaque fichier.
ORDRE_BASE_VIDE = ("codes.csv", "techniciens.tsv", "fournisseurs.tsv", "equipements.xlsx", "articles.csv",
                   "habilitations.csv", "compteurs.csv", "controles.csv", "gammes.xlsx", "historique.csv")
TYPES = {"codes.csv": "codes", "techniciens.tsv": "techniciens", "fournisseurs.tsv": "fournisseurs",
         "equipements.xlsx": "equipements", "equipements.ods": "equipements", "equipements.xls": "equipements",
         "articles.csv": "articles", "habilitations.csv": "habilitations", "compteurs.csv": "compteurs",
         "controles.csv": "controles", "gammes.xlsx": "gammes", "historique.csv": "historique"}
COLLAGES = {"fournisseurs.tsv"}                   # « collage depuis Excel » : passé par la zone de collage
PAR_L_ECRAN = "equipements.xlsx"                  # importé par l'écran #/import, de bout en bout

# Totaux du LISEZMOI (base de démo, chaque fichier importé seul), recopiés du tableau « Vue d'ensemble ».
TOTAUX_DEMO = {
    "equipements.xlsx": {"creer": 5, "mettre_a_jour": 1, "identique": 14, "refusee": 3},
    "equipements.ods": {"creer": 5, "mettre_a_jour": 1, "identique": 14, "refusee": 3},
    "equipements.xls": {"creer": 5, "mettre_a_jour": 1, "identique": 14, "refusee": 3},
    "articles.csv": {"creer": 7, "mettre_a_jour": 1, "identique": 1, "refusee": 3},
    "fournisseurs.tsv": {"creer": 3, "mettre_a_jour": 1, "identique": 1, "refusee": 1},
    "techniciens.tsv": {"creer": 2, "mettre_a_jour": 1, "identique": 3, "refusee": 1},
    "habilitations.csv": {"creer": 2, "mettre_a_jour": 2, "identique": 1, "refusee": 3},
    "codes.csv": {"creer": 4, "identique": 36, "refusee": 3},
    "compteurs.csv": {"creer": 3, "mettre_a_jour": 1, "identique": 1, "refusee": 2},
    "controles.csv": {"creer": 2, "mettre_a_jour": 1, "identique": 1, "refusee": 2},
    "gammes.xlsx": {"creer": 6, "refusee": 3},
    "historique.csv": {"creer": 13, "refusee": 2, "doublon_sur": 1, "doublon_suppose": 2},
}
# Base vide : « identique » et « mettre à jour » deviennent « créer » ; « 007 » existe après le parc (son compteur,
# sa gamme sur deux lignes), Inès Chabert après techniciens.tsv (son habilitation), la ligne 18 de l'historique n'a
# plus d'OT en face (créée) ; les autres refus restent (LISEZMOI, « Enchaînement sur une base vide »).
TOTAUX_BASE_VIDE = {
    "codes.csv": {"creer": 40, "refusee": 3},
    "techniciens.tsv": {"creer": 6, "refusee": 1},
    "fournisseurs.tsv": {"creer": 5, "refusee": 1},
    "equipements.xlsx": {"creer": 20, "refusee": 3},
    "articles.csv": {"creer": 9, "refusee": 3},
    "habilitations.csv": {"creer": 6, "refusee": 2},
    "compteurs.csv": {"creer": 6, "refusee": 1},
    "controles.csv": {"creer": 4, "refusee": 2},
    "gammes.xlsx": {"creer": 8, "refusee": 1},
    "historique.csv": {"creer": 14, "refusee": 2, "doublon_sur": 1, "doublon_suppose": 1},
}
# Fiches attendues après la reprise (LISEZMOI) ; localisations, fournisseurs et mouvements recalculés plus bas.
FICHES_BASE_VIDE = {"codes_defaillance": 40, "techniciens": 6, "equipements": 20, "articles": 9, "habilitations": 6,
                    "compteurs": 6, "controles_reglementaires": 4, "gammes": 3, "gamme_operations": 8,
                    "ordres_travail": 14, "ot_temps": 13}
LIGNES_REFUSEES_PARC = {16, 17, 24}               # criticité « Z », parent « XX-99 », désignation vide
ARTICLES_REFUSES = {"OUT-020", "PNE-020"}         # désignation vide, délai illisible (le 2e ROU-101 : doublon)
HISTORIQUE_NON_CREE = {12, 13, 15, 19}            # base vide : doublon supposé, refusées, doublon sûr

# Indicateurs : heures de fonctionnement saisies après la reprise (le parc importé n'en a pas) sur deux machines
# du fichier ; période choisie de 90 jours qui contient la panne de CP-01 (ligne 4, 2,5 h) et celle de PR-01
# (ligne 7, arrêt sans durée).
HEURES_PAR_JOUR = 8
MACHINES_SUIVIES = ("CP-01", "PR-01")
DU, AU = "2025-01-01", "2025-03-31"

# Lecture d'un fichier d'essai, correspondance automatique, aperçu ; import si demandé (le résultat est gardé pour
# l'annulation). Rend ce que l'écran montrerait : colonnes, totaux, actions par ligne, écritures par table.
IMPORTER_JS = """async ([type, nom, contenu, collage, options, importer]) => {
  const source = collage ? { texte: contenu, nom }
    : new File([Uint8Array.from(atob(contenu), (c) => c.charCodeAt(0))], nom);
  const lu = await Import.lire(source);
  const lignes = lu.feuilles[0].lignes;
  const rang = Import.ligneEntete(lignes, type);
  const entetes = Import.entetes(lignes, rang, false);
  const donnees = lignes.slice(rang + 1);
  const correspondance = Import.correspondance(type, entetes, donnees, 'auto');
  const reglages = Object.assign({ mettreAJour: true, numeroPremiereLigne: rang + 2 }, options);
  const calculer = () => Import.preparer(type, donnees, correspondance, reglages);
  const apercu = calculer();
  const rendu = { format: lu.format, rang, totaux: apercu.totaux,
    colonnes: correspondance.map((c) => [c.entete, c.champ, c.statut]),
    lignes: apercu.lignes.map((l) => [l.numero, l.action, l.cible || '']),
    ecritures: Object.fromEntries(Object.entries(apercu.ecritures)
      .map(([table, e]) => [table, [e.creer.length, e.modifier.length]])) };
  if (importer) {
    const resultat = await Import.importer(apercu, { nomFichier: nom, recalculer: calculer });
    window.__imports = (window.__imports || []).concat([resultat]);
    rendu.resultat = { sauvegarde: resultat.sauvegarde, tables: resultat.tables, tablesTouchees: resultat.tablesTouchees };
  }
  return rendu;
}"""
ANNULER_JS = "async () => { const resultat = window.__imports.pop(); return Import.annuler(resultat); }"
COMPTES_JS = "() => Object.fromEntries(Schema.nomsTables().map((t) => [t, Donnees.lignes(t).length]))"
ERREURS_JS = "() => Donnees.problemes().filter((p) => p.gravite === 'erreur').map((p) => p.message)"


def totaux(totaux_apercu):
    return {action: totaux_apercu.get(action, 0) for action in ACTIONS}


def attendus(totaux_partiels):
    return {action: totaux_partiels.get(action, 0) for action in ACTIONS}


def contenu(nom):
    """(contenu, collage) : le texte pour un collage, sinon les octets du fichier en base64."""
    octets = (FIXTURES / nom).read_bytes()
    if nom in COLLAGES:
        return octets.decode("utf-8"), True
    return base64.b64encode(octets).decode("ascii"), False


def empreintes(dossier):
    return {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(dossier.glob("*.csv"))}


def lire_texte(nom, encodage, separateur):
    """En-tête et lignes d'un fichier d'essai texte, comme un tableur les lit (module csv)."""
    lignes = list(csv.reader(io.StringIO((FIXTURES / nom).read_bytes().decode(encodage), newline=""),
                             delimiter=separateur))
    return lignes[0], lignes[1:]


def localisations_du_parc():
    """Localisations créées par la liste du parc sur une base vide : chaque niveau de chaque chemin, une fois
    (séparateurs « > », « / », « \\ » ; libellés comparés tels quels, LISEZMOI choix 4), lignes refusées exclues."""
    grille = lire_xlsx(FIXTURES / "equipements.xlsx")[0]["Parc"]
    colonne = grille[1].index("Emplacement")
    chemins = set()
    for numero, cellules in enumerate(grille[2:], start=3):
        if numero in LIGNES_REFUSEES_PARC or len(cellules) <= colonne:
            continue
        niveaux = [n.strip() for n in re.split(r"[>/\\]", cellules[colonne]) if n.strip()]
        chemins.update(tuple(niveaux[:rang]) for rang in range(1, len(niveaux) + 1))
    return len(chemins)


def stocks_des_articles():
    """{référence: stock} des articles créés : quantité du fichier, 0 si la cellule est vide (aucun mouvement) ;
    la première ligne d'une référence en double compte."""
    entete, lignes = lire_texte("articles.csv", "cp1252", ";")
    reference, quantite = entete.index("Code article"), entete.index("Qté stock")
    stocks = {}
    for cellules in lignes:
        if cellules[reference] in stocks or cellules[reference] in ARTICLES_REFUSES:
            continue
        valeur = cellules[quantite].strip()
        stocks[cellules[reference]] = float(valeur.replace(",", ".")) if valeur else None
    return stocks


def fournisseurs_attendus():
    """Fournisseurs du collage (raison sociale non vide) et ceux que citent les articles créés (D88 a)."""
    entete, lignes = lire_texte("fournisseurs.tsv", "utf-8", "\t")
    noms = {c[entete.index("Raison sociale")].strip() for c in lignes if c and c[entete.index("Raison sociale")].strip()}
    entete, lignes = lire_texte("articles.csv", "cp1252", ";")
    vus = set()
    for cellules in lignes:
        reference = cellules[entete.index("Code article")]
        if reference in vus or reference in ARTICLES_REFUSES:
            continue
        vus.add(reference)
        noms.add(cellules[entete.index("Fournisseur")].strip())
    return len(noms)


def jour_du_fichier(texte):
    """« JJ/MM/AAAA HH:MM » → date (None si vide)."""
    texte = texte.strip()
    return datetime.datetime.strptime(texte, "%d/%m/%Y %H:%M").date() if texte else None


def pannes_du_fichier():
    """Pannes de historique.csv créées sur une base vide (calcul indépendant, §15.3 et §18.6) : OT correctif
    (« Dépannage », « Curatif » → correctif immédiat ; « Correctif différé » ou type absent → correctif différé)
    avec arrêt de production (« oui », ou colonne vide et durée > 0) ; date de panne = date de demande, sinon de
    début ; durée vide → None (jamais 0). [{ ligne, repere, jour, duree }]."""
    entete, lignes = lire_texte("historique.csv", "utf-8", ",")
    correctifs = {"dépannage", "curatif", "correctif différé", ""}
    pannes = []
    for numero, cellules in enumerate(lignes, start=2):
        valeurs = dict(zip(entete, cellules))
        if numero in HISTORIQUE_NON_CREE or valeurs["Type"].strip().lower() not in correctifs:
            continue
        brute = valeurs["Durée arrêt (h)"].strip()
        duree = float(brute.replace(",", ".")) if brute else None
        arret = valeurs["Arrêt"].strip().lower()
        if arret == "oui" or (arret == "" and duree is not None and duree > 0):
            pannes.append({"ligne": numero, "repere": valeurs["Machine"].strip(), "duree": duree,
                           "jour": jour_du_fichier(valeurs["Date demande"]) or jour_du_fichier(valeurs["Début"])})
    return pannes


def fiabilite(pannes, requis):
    """MTBF, MTTR, disponibilité (§15.3, ajustement 3 de D92 : disponibilité sur les seules pannes avec durée)."""
    durees = [p["duree"] for p in pannes if p["duree"] is not None]
    arret = sum(durees)
    mtbf = (requis - arret) / len(pannes) if pannes else None
    mttr = arret / len(durees) if durees else None
    mtbf_avec_duree = (requis - arret) / len(durees) if durees else None
    disponibilite = mtbf_avec_duree / (mtbf_avec_duree + mttr) if durees else None
    return {"pannes": len(pannes), "mtbf": mtbf, "mttr": mttr, "disponibilite": disponibilite}


class CasRecette(CasImport):

    def setUp(self):
        super().setUp()
        self.contexte.clock.set_fixed_time(HEURE_FIXE)

    def importer_fichier(self, nom, importer=True, options=None):
        texte, collage = contenu(nom)
        reglages = dict({"maintenant": MAINTENANT}, **(options or {}))
        return self.page.evaluate(IMPORTER_JS, [TYPES[nom], nom, texte, collage, reglages, importer])

    def verifier_colonnes(self, nom, colonnes):
        """Correspondance automatique : chaque colonne « sûre », sauf les colonnes inconnues « non utilisées »."""
        for entete, champ, statut in colonnes:
            with self.subTest(fichier=nom, colonne=entete):
                if champ:
                    self.assertEqual(statut, "sure", (entete, champ))
                else:
                    self.assertEqual(statut, "non_utilisee", entete)


# ---------------------------------------------------------------------------
# Reprise d'un atelier complet sur une base vide (serveur.py)
# ---------------------------------------------------------------------------

class TestReprise(CasRecette):

    def importer_par_l_ecran(self, nom):
        """Le parc par l'écran : lien de l'accueil (parc vide), type, dépôt du fichier, colonnes, aperçu, import."""
        page = self.page
        page.wait_for_selector("#lien-import-accueil", state="visible")
        page.click("#lien-import-accueil")
        self.attendre_etape(1)
        self.choisir_type(TYPES[nom])
        self.deposer(nom)
        self.assertEqual(page.input_value("#import-ligne-entete"), "2")
        self.continuer(3)
        self.assertEqual([(c["entete"], c["champ"], c["statut"]) for c in self.colonnes()], COLONNES_EQUIPEMENTS)
        self.continuer(4)
        self.assertTrue(page.is_checked("#import-mettre-a-jour"))
        affiches = self.totaux()
        self.continuer(5)
        self.importer()
        sauvegarde = page.inner_text("#import-sauvegarde").strip()
        return affiches, sauvegarde, self.resultat_par_table()

    def test_atelier_complet_repris_sur_base_vide_indicateurs_reimport_puis_annulation(self):
        self.autoriser_erreur(ERREUR_CSV_ABSENT)          # base vide : les 22 CSV manquent avant « Créer »
        with ServeurPrevo(source=None) as serveur:
            preregler_profil(self.contexte, "responsable")
            page = self.page
            page.goto(serveur.url + "/")
            page.wait_for_selector("#btn-base-vide", state="visible")
            page.click("#btn-base-vide")
            attendre_pret(page)
            self.assertEqual(set(page.evaluate(COMPTES_JS).values()) - {0}, {1}, "base vide : seuls les paramètres")

            # 1. Les dix fichiers, dans l'ordre du LISEZMOI
            apercus, sauvegardes, bilans = {}, [], []
            for nom in ORDRE_BASE_VIDE:
                with self.subTest(fichier=nom):
                    avant = page.evaluate(COMPTES_JS)
                    if nom == PAR_L_ECRAN:
                        apercu = self.importer_fichier(nom, importer=False)       # ce que l'écran doit montrer
                        affiches, sauvegarde, par_table = self.importer_par_l_ecran(nom)
                        self.assertEqual({a: affiches.get(a, 0) for a in ("creer", "mettre_a_jour", "identique", "refusee")},
                                         {a: totaux(apercu["totaux"])[a] for a in ("creer", "mettre_a_jour", "identique", "refusee")})
                        tables = {t: {"crees": c[0], "misAJour": c[1]} for t, c in par_table.items()}
                        self.aller("#/accueil")
                    else:
                        apercu = self.importer_fichier(nom)
                        sauvegarde, tables = apercu["resultat"]["sauvegarde"], apercu["resultat"]["tables"]
                    apercus[nom] = apercu
                    self.verifier_colonnes(nom, apercu["colonnes"])
                    self.assertEqual(totaux(apercu["totaux"]), attendus(TOTAUX_BASE_VIDE[nom]))
                    # Fiches écrites = créations de l'aperçu (base vide : rien à mettre à jour)
                    apres = page.evaluate(COMPTES_JS)
                    ecrites = {t: n for t, (n, m) in apercu["ecritures"].items() if n or m}
                    self.assertEqual({t: apres[t] - avant[t] for t in apres if apres[t] != avant[t] and t != "journal"}, ecrites)
                    self.assertEqual({t: [b["crees"], b["misAJour"]] for t, b in tables.items()},
                                     {t: [n, 0] for t, n in ecrites.items()})
                    self.assertRegex(sauvegarde, MOTIF_AVANT_IMPORT)
                    sauvegardes.append(sauvegarde)
                    bilans += [[t, "", "import %s : %d créé(s), 0 mis à jour" % (nom, n)] for t, n in ecrites.items()]
                if nom == "gammes.xlsx":
                    # Avant l'historique : heures de fonctionnement de deux machines (le parc importé n'en a pas) et
                    # réglages des suggestions (2 pannes de même cause, sur 24 mois), comme dans la fiche et Paramètres.
                    page.evaluate("""async ([reperes, heures]) => {
                      await Donnees.modifier('equipements', (lignes) => { lignes.filter((e) => reperes.includes(e.repere))
                        .forEach((e) => { e.heures_fonct_jour = String(heures); }); }, { action: 'heures saisies (recette)' });
                      await Donnees.modifier('parametres', (lignes) => {
                        [['suggestion_seuil_pannes', '2'], ['suggestion_fenetre_mois', '24']].forEach(([cle, valeur]) => {
                          const ligne = lignes.find((l) => l.cle === cle);
                          if (ligne) ligne.valeur = valeur; else lignes.push({ cle, valeur }); }); }, { action: 'réglages (recette)' });
                    }""", [list(MACHINES_SUIVIES), HEURES_PAR_JOUR])
                    avant_historique = empreintes(serveur.dossier)

            # 2. Les fiches sont là, le stock est celui du fichier, le journal a son bilan, la base est saine
            comptes = page.evaluate(COMPTES_JS)
            stocks = stocks_des_articles()
            attendu = dict(FICHES_BASE_VIDE, localisations=localisations_du_parc(), fournisseurs=fournisseurs_attendus(),
                           mouvements_stock=sum(1 for s in stocks.values() if s is not None))
            print("\n  [recette] base vide reprise : %s" % ", ".join("%s %d" % (t, comptes[t]) for t in sorted(attendu)))
            self.assertEqual({t: comptes[t] for t in attendu}, attendu)
            self.assertEqual(page.evaluate(ERREURS_JS), [], "Donnees.problemes() : aucune erreur")
            journal = page.evaluate(JOURNAL_JS)
            for bilan in bilans:
                self.assertIn(bilan, journal)
            articles = page.evaluate("() => Object.fromEntries(Donnees.lignes('articles').map((a) => [a.reference, [a.id, Donnees.stockArticle(a.id)]]))")
            self.assertEqual(set(articles), set(stocks))
            for reference, stock in stocks.items():
                with self.subTest(article=reference):
                    self.assertEqual(articles[reference][1], stock or 0)
            for reference in ("ELE-150", "LUB-010", "ROU-001"):                 # 120,5 ; « 0 » ; cellule vide
                self.aller("#/magasin/article/" + articles[reference][0])
                page.wait_for_selector("#magasin-stock")
                affiche = page.inner_text("#magasin-stock").split(" ")[0]
                self.assertEqual(affiche, ("%g" % (stocks[reference] or 0)).replace(".", ","), reference)

            # Une sauvegarde « avant-import » par import, sur le disque ; celle d'avant l'historique = CSV d'avant
            self.assertEqual(len(set(sauvegardes)), len(ORDRE_BASE_VIDE))
            for nom in sauvegardes:
                self.assertTrue((serveur.dossier / "sauvegardes" / nom / "ordres_travail.csv").is_file(), nom)
            self.assertEqual(empreintes(serveur.dossier / "sauvegardes" / sauvegardes[-1]), avant_historique)

            # 3. L'historique importé compte : indicateurs (calcul indépendant), causes fréquentes, suggestion
            historique = {numero: cible for numero, action, cible in apercus["historique.csv"]["lignes"] if action == "creer"}
            self.assertEqual(sorted(historique), sorted(set(range(2, 20)) - HISTORIQUE_NON_CREE))
            equipements = page.evaluate("() => Object.fromEntries(Donnees.lignes('equipements').map((e) => [e.repere, e.id]))")
            debut, fin = datetime.date.fromisoformat(DU), datetime.date.fromisoformat(AU)
            requis = HEURES_PAR_JOUR * ((fin - debut).days + 1)          # mises en service bien avant 2025
            pannes = [p for p in pannes_du_fichier() if debut <= p["jour"] <= fin]
            sans_duree = {"id": historique[7], "raison": "sans durée d'arrêt"}
            for repere in MACHINES_SUIVIES:
                calcul = fiabilite([p for p in pannes if p["repere"] == repere], requis)
                obtenu = page.evaluate("([id, du, au]) => Indicateurs.parEquipement(id, Indicateurs.periode('du-au', null, du, au))",
                                       [equipements[repere], DU, AU])
                for cle, valeur in calcul.items():
                    with self.subTest(equipement=repere, indicateur=cle):
                        if valeur is None:
                            self.assertIsNone(obtenu[cle]["valeur"], obtenu[cle])
                        else:
                            self.assertIsNotNone(obtenu[cle]["valeur"], obtenu[cle])
                            self.assertTrue(math.isclose(obtenu[cle]["valeur"], valeur, rel_tol=1e-9), (obtenu[cle], valeur))
            pr01 = page.evaluate("([id, du, au]) => Indicateurs.parEquipement(id, Indicateurs.periode('du-au', null, du, au))",
                                 [equipements["PR-01"], DU, AU])
            self.assertEqual(pr01["pannes"]["valeur"], 1)
            self.assertIn(historique[7], pr01["mtbf"]["ots"], "la panne sans durée compte dans le MTBF")
            self.assertIn(sans_duree, pr01["mttr"]["exclus"])
            self.assertIn(sans_duree, pr01["disponibilite"]["exclus"])
            # Écran Indicateurs : bandeau sur les deux machines suivies (les autres n'ont pas d'heures)
            global_ = fiabilite([p for p in pannes if p["repere"] in MACHINES_SUIVIES], requis * len(MACHINES_SUIVIES))
            page.evaluate("hash => { location.hash = hash; }", "#/indicateurs?periode=du-au&du=%s&au=%s" % (DU, AU))
            page.wait_for_function("(du) => { const r = document.querySelector('#contenu .indicateurs-resume');"
                                   " return r && r.textContent.includes(du) && document.querySelector('#contenu [data-indicateur=\"mtbf\"]'); }",
                                   arg="01/01/2025")
            affiches = page.evaluate("""() => Object.fromEntries([...document.querySelectorAll('#contenu [data-indicateur]')]
              .map((e) => [e.dataset.indicateur, [e.dataset.valeur, e.textContent.replace(/\\s+/g, ' ')]]))""")
            print("  [recette] indicateurs du %s au %s (%s) : MTBF %s h, MTTR %s h, disponibilité %s %%"
                  % (DU, AU, " + ".join(MACHINES_SUIVIES), affiches["mtbf"][0], affiches["mttr"][0], affiches["disponibilite"][0]))
            self.assertLessEqual(abs(float(affiches["mtbf"][0]) - global_["mtbf"]), 0.05 + 1e-9)
            self.assertLessEqual(abs(float(affiches["mttr"][0]) - global_["mttr"]), 0.05 + 1e-9)
            self.assertLessEqual(abs(float(affiches["disponibilite"][0]) - 100 * global_["disponibilite"]), 0.05 + 1e-9)
            self.assertIn("2 pannes", affiches["mtbf"][1])
            self.assertIn("%s : sans durée d'arrêt" % historique[7], affiches["mttr"][1])
            # Causes fréquentes du symptôme S05 sur CV-02 : ses deux pannes importées (lignes 6 et 18, cause C04)
            causes = page.evaluate("(id) => CausesFrequentes.calculer(id, 'S05', { minimum: 2 })", equipements["CV-02"])
            self.assertEqual((causes["suffisant"], causes["portee"], causes["total"]), (True, "equipement", 2))
            self.assertEqual([(c["code"], c["nombre"], sorted(c["ots"])) for c in causes["causes"]],
                             [("C04", 2, sorted([historique[6], historique[18]]))])
            # Suggestion S1 « Créer une gamme » sur CV-02 (sans gamme), écran Préventif → Suggestions compris
            cle = "S1-%s-C04" % equipements["CV-02"]
            suggestion = page.evaluate("(cle) => Suggestions.trouver(cle)", cle)
            self.assertIsNotNone(suggestion, "suggestion %s absente" % cle)
            self.assertEqual(sorted(suggestion["ots"]), sorted([historique[6], historique[18]]))
            self.aller("#/preventif?onglet=suggestions")
            page.wait_for_selector('#contenu .sg-carte[data-cle="%s"]' % cle)

            # 4. Accueil après import : aucun défilement horizontal, ordinateur et téléphone
            for largeur, hauteur in ((1440, 900), (375, 800)):
                page.set_viewport_size({"width": largeur, "height": hauteur})
                self.aller("#/accueil")
                page.wait_for_selector("#bento-synthese")
                self.verifier_largeur("accueil après import à %d px" % largeur)
            page.set_viewport_size({"width": 1280, "height": 800})

            # 5. Réimport complet : rien n'est créé ni mis à jour (historique : doublons sûrs par l'ancien numéro)
            for nom in ORDRE_BASE_VIDE:
                with self.subTest(reimport=nom):
                    second = totaux(self.importer_fichier(nom, importer=False)["totaux"])
                    self.assertEqual((second["creer"], second["mettre_a_jour"]), (0, 0), second)
                    if nom == "historique.csv":
                        self.assertEqual(second, {"creer": 0, "mettre_a_jour": 0, "identique": 0, "refusee": 2,
                                                  "doublon_sur": 15, "doublon_suppose": 1})

            # 6. Annulation du dernier import (historique) : CSV rendus à l'octet, journal mis à part
            restaurees = page.evaluate(ANNULER_JS)
            self.assertEqual(restaurees["restaurees"], ["ordres_travail", "ot_temps"])
            final = empreintes(serveur.dossier)
            self.assertEqual([n for n in avant_historique if final[n] != avant_historique[n]], ["journal.csv"])
            self.assertEqual(page.evaluate("() => [Donnees.lignes('ordres_travail').length, Donnees.lignes('ot_temps').length]"),
                             [0, 0])


# ---------------------------------------------------------------------------
# Démo : chaque fichier seul, totaux du LISEZMOI, annulation par l'instantané
# ---------------------------------------------------------------------------

class TestDemo(CasRecette):

    def test_chaque_fichier_seul_totaux_du_lisezmoi_puis_annulation_a_l_octet(self):
        page = self.ouvrir_demo()
        for nom, attendu in TOTAUX_DEMO.items():
            with self.subTest(fichier=nom):
                avant = {t: o for t, o in page.evaluate(INSTANTANE_JS).items() if t != "journal"}
                apercu = self.importer_fichier(nom)
                self.verifier_colonnes(nom, apercu["colonnes"])
                self.assertEqual(totaux(apercu["totaux"]), attendus(attendu))
                self.assertIsNone(apercu["resultat"]["sauvegarde"], "démo : instantané en mémoire")
                self.assertNotEqual({t: o for t, o in page.evaluate(INSTANTANE_JS).items() if t != "journal"}, avant)
                page.evaluate(ANNULER_JS)
                apres = {t: o for t, o in page.evaluate(INSTANTANE_JS).items() if t != "journal"}
                self.assertEqual([t for t in avant if apres[t] != avant[t]], [], "tables rendues à l'octet")


# ---------------------------------------------------------------------------
# Design : l'assistant et l'accueil après import, ordinateur et téléphone
# ---------------------------------------------------------------------------

class TestDesign(CasRecette):

    def parcourir(self, largeur, hauteur, telephone):
        self.page.set_viewport_size({"width": largeur, "height": hauteur})
        self.ouvrir_demo()

        def verifier(ou):
            self.verifier_largeur("%s à %d px" % (ou, largeur))
            if telephone:
                self.verifier_zones("%s à %d px" % (ou, largeur))

        verifier("étape 1")
        self.choisir_type("historique")
        self.deposer("historique.csv")
        verifier("étape 2")
        self.continuer(3)
        verifier("étape 3")
        self.continuer(4)
        verifier("étape 4 (aperçu)")
        self.continuer(5)
        verifier("étape 5")
        self.importer()
        self.verifier_largeur("résultat de l'import à %d px" % largeur)
        self.assertEqual(self.resultat_par_table(), {"ordres_travail": [13, 0], "ot_temps": [12, 0]})
        self.aller("#/accueil")
        self.page.wait_for_selector("#bento-synthese")
        self.verifier_largeur("accueil après import à %d px" % largeur)
        largeur_page, ecran = self.page.evaluate(LARGEUR_JS)
        print("\n  [recette] %d px : accueil après import %d px de large pour %d px d'écran" % (largeur, largeur_page, ecran))

    def test_assistant_et_accueil_apres_import_1440_px(self):
        self.parcourir(1440, 900, telephone=False)

    def test_assistant_et_accueil_apres_import_375_px(self):
        self.parcourir(375, 800, telephone=True)


if __name__ == "__main__":
    unittest.main()
