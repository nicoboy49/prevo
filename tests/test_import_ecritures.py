"""Écriture et annulation de l'assistant d'import (tâche T83, ARCHITECTURE.md §18.7 ; CS83, CS84, CS85,
CS87, CS88).

Ce qui est vérifié, dans l'application complète :
  - démo : l'import écrit exactement l'aperçu (créations et mises à jour, table par table, dans l'ordre
    des références), journal ligne par ligne et bilan par table ; stock affiché = stock du fichier (mouvement
    « inventaire ») ; aucun problème nouveau dans Donnees.problemes() ; l'annulation rend les tables
    touchées à l'octet (instantané) ; un échec en cours d'écriture laisse un résultat partiel annulable ;
  - serveur : sauvegarde « …_avant-import » écrite AVANT les données, fichiers du disque égaux à l'aperçu ;
    annulation → fichiers des tables touchées identiques à l'octet à ceux d'avant ; sauvegarde impossible →
    rien n'est écrit ; deux postes : une fiche créée entre-temps sur l'autre poste → aperçu périmé, rien
    n'est écrit, jamais de doublon ;
  - dossier (simulé) : sauvegarde « avant-import » présente, annulation à l'octet.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_import_ecritures.py" -v
"""
import hashlib
import re
import unittest

from commun import (RACINE, CasNavigateur, ServeurPrevo, ServeurStatique, attendre_pret, installer_dossier_simule,
                    preregler_profil, url_fichier)
from test_app import ERREUR_PING_ABSENT
from test_import_regles import (C_ARTICLES, C_EQUIPEMENTS, E_ARTICLES, E_EQUIPEMENTS, G_EQUIPEMENTS, MAINTENANT,
                                correspondance, grille_articles)

MOTIF_AVANT_IMPORT = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}_avant-import$")
ORDRE = ["localisations", "fournisseurs", "techniciens", "equipements", "articles", "mouvements_stock", "compteurs",
         "controles_reglementaires", "habilitations", "gammes", "gamme_operations", "codes_defaillance",
         "ordres_travail", "ot_temps"]
IMPORTS = {
    "equipements": ("parc.xlsx", E_EQUIPEMENTS, G_EQUIPEMENTS, C_EQUIPEMENTS),
    "articles": ("magasin.csv", E_ARTICLES, grille_articles("14"), C_ARTICLES),
}

# Aperçu puis import dans la page ; rend l'aperçu, le résultat (ou l'erreur) et ce que contiennent les tables.
IMPORTER_JS = """async ([type, grille, correspondance, options, nomFichier, avecRecalcul]) => {
  const apercu = Import.preparer(type, grille, correspondance, options);
  const recalculer = avecRecalcul ? () => Import.preparer(type, grille, correspondance, options) : undefined;
  try {
    const resultat = await Import.importer(apercu, { nomFichier, recalculer });
    window.__resultat = resultat;
    return { ok: true, apercu: JSON.parse(JSON.stringify(apercu)),
      resultat: { sauvegarde: resultat.sauvegarde, tables: resultat.tables, tablesTouchees: resultat.tablesTouchees } };
  } catch (erreur) {
    window.__erreur = erreur;
    return { ok: false, apercu: JSON.parse(JSON.stringify(apercu)), nom: erreur.name, message: erreur.message,
      perime: Boolean(erreur.perime), partiel: erreur.resultatPartiel ? erreur.resultatPartiel.tablesTouchees : null };
  }
}"""

# Contenu des tables (octets sérialisés par Donnees, en texte) : comparaison à l'octet.
TABLES_JS = """(noms) => { const tout = Donnees.instantane(); const r = {};
  noms.forEach((n) => { r[n] = Array.from(tout[n]).join(','); }); return r; }"""
LIGNES_JS = "(noms) => Object.fromEntries(noms.map((n) => [n, Donnees.lignes(n).map((l) => Object.assign({}, l))]))"
JOURNAL_JS = "async () => { await Donnees.rafraichir(); return Donnees.lignes('journal').map((l) => [l.table, l.id_ligne, l.action]); }"
PROBLEMES_JS = "() => Donnees.problemes().map((p) => [p.niveau || p.gravite || '', p.message || p.texte || JSON.stringify(p)].join(' '))"


def options():
    return {"mettreAJour": True, "maintenant": MAINTENANT, "utilisateur": "Responsable"}


def empreintes(dossier):
    return {f.stem: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(dossier.glob("*.csv"))}


class CasEcriture(CasNavigateur):

    def importer(self, page, type_, avec_recalcul=True, nom_fichier=None):
        nom, entetes, grille, choix = IMPORTS[type_]
        return page.evaluate(IMPORTER_JS, [type_, grille, correspondance(entetes, choix), options(),
                                           nom_fichier or nom, avec_recalcul])

    def verifier_ecritures(self, apercu, avant, apres):
        """Les tables après l'import = tables d'avant + créations + mises à jour de l'aperçu, rien d'autre."""
        for table in ORDRE:
            ecritures = apercu["ecritures"].get(table) or {"creer": [], "modifier": []}
            anciennes = {l["id"]: l for l in avant.get(table, [])}
            nouvelles = {l["id"]: l for l in apres.get(table, [])}
            with self.subTest(table=table):
                if table not in avant:
                    self.assertFalse(ecritures["creer"] or ecritures["modifier"])
                    continue
                self.assertEqual(len(nouvelles), len(anciennes) + len(ecritures["creer"]))
                for ligne in ecritures["creer"]:
                    self.assertNotIn(ligne["id"], anciennes)
                    ecrite = nouvelles[ligne["id"]]
                    for champ, valeur in ligne.items():
                        self.assertEqual(ecrite[champ], "" if valeur is None else str(valeur), (ligne["id"], champ))
                modifiees = {m["id"]: m["changes"] for m in ecritures["modifier"]}
                for identifiant, ancienne in anciennes.items():
                    attendue = dict(ancienne, **{k: str(v) for k, v in modifiees.get(identifiant, {}).items()})
                    self.assertEqual(nouvelles[identifiant], attendue, identifiant)


class TestDemo(CasEcriture):

    def setUp(self):
        super().setUp()
        preregler_profil(self.contexte, "responsable")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)

    def test_ecritures_egales_a_l_apercu_journal_stock_et_annulation_a_l_octet(self):
        page = self.page
        problemes_avant = set(page.evaluate(PROBLEMES_JS))
        journal_avant = len(page.evaluate(JOURNAL_JS))
        for type_ in ("equipements", "articles"):
            with self.subTest(type=type_):
                avant_lignes = page.evaluate(LIGNES_JS, ORDRE)
                avant_octets = page.evaluate(TABLES_JS, ORDRE)
                retour = self.importer(page, type_)
                self.assertTrue(retour["ok"], retour)
                apercu, resultat = retour["apercu"], retour["resultat"]
                self.assertIsNone(resultat["sauvegarde"], "démo : instantané en mémoire, pas de sauvegarde")
                touchees = [t for t in ORDRE if (apercu["ecritures"].get(t) or {}).get("creer") or (apercu["ecritures"].get(t) or {}).get("modifier")]
                self.assertEqual(resultat["tablesTouchees"], touchees, "ordre des références")
                for table in touchees:
                    self.assertEqual(resultat["tables"][table], {"crees": len(apercu["ecritures"][table]["creer"]),
                                                                 "misAJour": len(apercu["ecritures"][table]["modifier"])})
                self.verifier_ecritures(apercu, avant_lignes, page.evaluate(LIGNES_JS, ORDRE))
                # Journal : chaque ligne écrite, puis le bilan de chaque table
                journal = page.evaluate(JOURNAL_JS)[journal_avant:]
                nom = IMPORTS[type_][0]
                for table in touchees:
                    bilan = resultat["tables"][table]
                    self.assertIn([table, "", "import %s : %d créé(s), %d mis à jour" % (nom, bilan["crees"], bilan["misAJour"])], journal)
                    lignes_journal = [e for e in journal if e[0] == table and e[1] and e[2].endswith(" — import " + nom)]
                    self.assertEqual(len(lignes_journal), bilan["crees"] + bilan["misAJour"], table)
                if type_ == "articles":
                    # Stock affiché = stock du fichier (mouvement « inventaire »)
                    stocks = page.evaluate("""() => Object.fromEntries(['ROU-900', 'ROU-001'].map((r) => {
                      const a = Donnees.lignes('articles').find((l) => l.reference === r);
                      return [r, Donnees.stockArticle(a.id)]; }))""")
                    self.assertEqual(stocks, {"ROU-900": 12, "ROU-001": 14})
                self.assertEqual(set(page.evaluate(PROBLEMES_JS)) - problemes_avant, set(), "aucun problème nouveau")
                # Annulation : les tables touchées reviennent à l'octet
                annule = page.evaluate("() => Import.annuler(window.__resultat)")
                self.assertEqual(annule["restaurees"], touchees)
                self.assertEqual(page.evaluate(TABLES_JS, ORDRE), avant_octets)
                journal_avant = len(page.evaluate(JOURNAL_JS))
                self.assertIn("annulé", page.evaluate(JOURNAL_JS)[-1][2])

    def test_echec_en_cours_d_ecriture_laisse_un_resultat_partiel_annulable(self):
        page = self.page
        avant = page.evaluate(TABLES_JS, ORDRE)
        page.evaluate("""() => {
          const origine = App.adaptateur.enregistrer;
          App.adaptateur.enregistrer = (table, ...reste) => table === 'equipements'
            ? Promise.reject(new Error('disque plein')) : origine.call(App.adaptateur, table, ...reste);
          window.__origine = origine;
        }""")
        self.autoriser_erreur("disque plein")
        retour = self.importer(self.page, "equipements")
        self.assertFalse(retour["ok"], retour)
        self.assertIn("disque plein", retour["message"])
        self.assertEqual(retour["partiel"], ["localisations", "equipements"])
        self.assertNotEqual(page.evaluate(TABLES_JS, ["localisations"]), {"localisations": avant["localisations"]})
        page.evaluate("() => { App.adaptateur.enregistrer = window.__origine; }")
        page.evaluate("() => Import.annuler(window.__erreur.resultatPartiel)")
        self.assertEqual(page.evaluate(TABLES_JS, ORDRE), avant)

    def test_rien_a_importer_et_aucun_import_a_annuler(self):
        messages = self.page.evaluate("""async () => {
          const essais = [() => Import.importer({ ecritures: {} }, { nomFichier: 'x.csv' }), () => Import.annuler(null)];
          const r = [];
          for (const essai of essais) { try { await essai(); r.push('pas d\\'erreur'); } catch (e) { r.push(e.name + ' ' + e.message); } }
          return r;
        }""")
        self.assertIn("ErreurImport Rien à importer", messages[0])
        self.assertIn("ErreurImport Aucun import à annuler", messages[1])


class TestServeur(CasEcriture):

    def ouvrir(self, serveur, contexte=None):
        contexte = contexte or self.contexte
        preregler_profil(contexte, "responsable")
        page = self.page if contexte is self.contexte else contexte.new_page()
        page.goto(serveur.url + "/#/import")
        attendre_pret(page)
        page.wait_for_load_state("networkidle")
        return page

    def test_sauvegarde_avant_les_donnees_disque_egal_a_l_apercu_et_annulation_a_l_octet(self):
        with ServeurPrevo() as serveur:
            page = self.ouvrir(serveur)
            disque_avant = empreintes(serveur.dossier)
            avant_lignes = page.evaluate(LIGNES_JS, ORDRE)
            retour = self.importer(page, "equipements")
            self.assertTrue(retour["ok"], retour)
            nom = retour["resultat"]["sauvegarde"]
            self.assertRegex(nom, MOTIF_AVANT_IMPORT)
            sauvegarde = serveur.dossier / "sauvegardes" / nom
            # La sauvegarde contient la base d'AVANT l'import
            self.assertEqual({t: h for t, h in empreintes(sauvegarde).items() if t != "journal"},
                             {t: h for t, h in disque_avant.items() if t != "journal"})
            # Le disque contient exactement l'aperçu (relu par une page neuve)
            relue = self.ouvrir(serveur, self.navigateur.new_context(locale="fr-FR"))
            self.verifier_ecritures(retour["apercu"], avant_lignes, relue.evaluate(LIGNES_JS, ORDRE))
            touchees = retour["resultat"]["tablesTouchees"]
            disque_apres = empreintes(serveur.dossier)
            self.assertEqual(sorted(t for t in disque_apres if disque_apres[t] != disque_avant[t] and t != "journal"), sorted(touchees))
            # Annulation : fichiers des tables touchées identiques à l'octet à ceux d'avant
            page.evaluate("() => Import.annuler(window.__resultat)")
            disque_annule = empreintes(serveur.dossier)
            self.assertEqual({t: disque_annule[t] for t in touchees}, {t: disque_avant[t] for t in touchees})
            self.assertEqual(page.evaluate(LIGNES_JS, touchees), {t: avant_lignes[t] for t in touchees})

    def test_sauvegarde_impossible_rien_n_est_ecrit(self):
        with ServeurPrevo() as serveur:
            page = self.ouvrir(serveur)
            disque_avant = empreintes(serveur.dossier)
            page.evaluate("() => { App.adaptateur.sauvegarder = () => Promise.reject(new Error('dossier en lecture seule')); }")
            retour = self.importer(page, "articles")
            self.assertFalse(retour["ok"])
            self.assertEqual(retour["nom"], "ErreurImport")
            self.assertIn("dossier en lecture seule", retour["message"])
            self.assertIn("rien n'a été importé", retour["message"])
            page.wait_for_timeout(200)
            self.assertEqual(empreintes(serveur.dossier), disque_avant)

    def test_fiche_creee_entre_temps_sur_un_autre_poste_jamais_de_doublon(self):
        with ServeurPrevo() as serveur:
            page = self.ouvrir(serveur)
            autre = self.ouvrir(serveur, self.navigateur.new_context(locale="fr-FR"))
            nom, entetes, grille, choix = IMPORTS["articles"]
            apercu = page.evaluate("([t, g, c, o]) => { window.__apercu = Import.preparer(t, g, c, o); return window.__apercu.referencesCreees; }",
                                   ["articles", grille, correspondance(entetes, choix), options()])
            fournisseur = next(r for r in apercu if r["table"] == "fournisseurs")
            # L'autre poste crée le même fournisseur (même nom) avant l'import
            autre.evaluate("""async (nom) => { await Donnees.modifier('fournisseurs', (lignes, outils) => {
              lignes.push({ id: outils.nouvelId(), nom }); }); }""", fournisseur["libelle"])
            disque_avant = empreintes(serveur.dossier)
            retour = page.evaluate("""async ([t, g, c, o]) => {
              try { await Import.importer(window.__apercu, { nomFichier: 'magasin.csv', recalculer: () => Import.preparer(t, g, c, o) }); return { ok: true }; }
              catch (e) { return { ok: false, perime: Boolean(e.perime), message: e.message,
                nouveau: e.apercu ? e.apercu.referencesCreees.map((r) => r.libelle) : null }; }
            }""", ["articles", grille, correspondance(entetes, choix), options()])
            self.assertFalse(retour["ok"], retour)
            self.assertTrue(retour["perime"], retour)
            self.assertNotIn(fournisseur["libelle"], retour["nouveau"], "le nouvel aperçu reconnaît la fiche de l'autre poste")
            self.assertEqual({t: h for t, h in empreintes(serveur.dossier).items() if t != "journal"},
                             {t: h for t, h in disque_avant.items() if t != "journal"}, "rien n'est écrit")
            # Sans recalcul : l'identifiant pris sur l'autre poste arrête tout, sans doublon
            retour = page.evaluate("""async () => {
              try { await Import.importer(window.__apercu, { nomFichier: 'magasin.csv' }); return { ok: true }; }
              catch (e) { return { ok: false, message: e.message }; } }""")
            self.assertFalse(retour["ok"], retour)
            self.assertIn("vient d'être pris sur un autre poste", retour["message"])
            noms = page.evaluate("() => Donnees.lignes('fournisseurs').map((l) => Import.comparable(l.nom))")
            self.assertEqual(noms.count(page.evaluate("(n) => Import.comparable(n)", fournisseur["libelle"])), 1)


class TestDossier(CasEcriture):

    def test_sauvegarde_avant_import_et_annulation_a_l_octet(self):
        self.autoriser_erreur(ERREUR_PING_ABSENT)
        installer_dossier_simule(self.contexte, "donnees-import-ecritures")
        preregler_profil(self.contexte, "responsable")
        page = self.page
        with ServeurStatique(RACINE) as statique:
            page.goto(statique.url + "/index.html")
            page.wait_for_selector("#btn-dossier")
            page.click("#btn-dossier")
            page.wait_for_selector("#ecran-base-vide", state="visible")
            page.click("#btn-base-demo")
            attendre_pret(page)
            self.assertEqual(page.evaluate("App.mode"), "dossier")
            avant = page.evaluate(TABLES_JS, ORDRE)
            retour = self.importer(page, "articles")
            self.assertTrue(retour["ok"], retour)
            nom = retour["resultat"]["sauvegarde"]
            self.assertRegex(nom, MOTIF_AVANT_IMPORT)
            self.assertIn(nom, page.evaluate("App.adaptateur.listerSauvegardes().then((l) => l.map((s) => s.nom || s))"))
            self.assertNotEqual(page.evaluate(TABLES_JS, ORDRE), avant)
            page.evaluate("() => Import.annuler(window.__resultat)")
            self.assertEqual(page.evaluate(TABLES_JS, ORDRE), avant)


if __name__ == "__main__":
    unittest.main()
