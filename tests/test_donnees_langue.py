"""Chantier multilingue, Lot 3 — textes écrits dans les données dans la langue de l'installation (T292 ; D156, D146).

Ce que l'appli écrit elle-même dans les données (journal, motifs et titres pré-remplis, nom du profil inscrit, rapport
figé) passe par I18n.donnees ou I18n.enLangueDesDonnees : la langue de l'installation (le français jusqu'au Lot 4),
jamais celle de l'écran. Ce qui est affiché (messages, titres, boutons) suit la langue de l'écran.

Dans Chromium, application de démonstration en file:// (profil responsable, poste « Poste test ») :
    - même suite d'écritures en français puis en anglais (English choisi : localStorage « prevo.langue », page
      rechargée) — temps passé, opération et pièce prévue ajoutés à un OT « En cours » par ses onglets, inventaire
      sans commentaire, motif « Pièce : … » pré-rempli d'une mise en attente : le fichier du journal (actions,
      profil), le mouvement d'inventaire (commentaire, utilisateur) et le motif proposé sont identiques, au texte
      français du dictionnaire ; les messages affichés, eux, sont en anglais ;
    - rapport mensuel figé en anglais : le document enregistré est en français (lang="fr", titres, mois, nombres) ;
      la tuile de l'accueil et le message de confirmation sont en anglais.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_donnees_langue.py" -v
"""
import re
import unittest

from commun import CasNavigateur, attendre_pret, preregler_profil, scenarios_demo, url_fichier

SCENARIOS = scenarios_demo()
OT_EN_COURS = SCENARIOS["ot_statut_en_cours"]                      # onglets Préparation et Exécution modifiables
OT_PIECE_MANQUANTE = SCENARIOS["ot_a_planifier_piece_manquante"]   # « Planifié » refusé : stock insuffisant
OPERATION = "Contrôle T292"
NOMS_MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
             "novembre", "décembre"]

# Lignes d'une table telles qu'enregistrées par le stockage (le « fichier » du mode démo), relues par Donnees.csv.
LIRE_FICHIER_JS = """async (table) => {
  const lu = await App.adaptateur.charger(table);
  return Donnees.csv.analyser(table, lu.octets).lignes;
}"""
# Un texte dans les deux langues : celle de l'installation (données) et celle de l'écran.
DEUX_TEXTES_JS = """([cle, valeurs]) => ({ donnees: I18n.donnees(cle, valeurs), reference: I18n.reference(cle, valeurs),
  ecran: I18n.t(cle, valeurs) })"""
NB_JOURNAL_JS = "(table) => Donnees.lignes('journal').filter((l) => l.table === table).length"
TOAST_JS = "(texte) => { const zone = document.getElementById('toast'); return Boolean(zone) && zone.textContent.includes(texte); }"


class TestDonneesLangue(CasNavigateur):

    def setUp(self):
        super().setUp()
        preregler_profil(self.contexte, "responsable")
        self.cles_absentes = []          # console.warn du moteur : « Prévo (traduction) : clé … »
        self.page.on("console", lambda message: self.cles_absentes.append(message.text)
                     if message.type == "warning" and "(traduction)" in message.text else None)

    # -- outils ---------------------------------------------------------------------------------

    def ouvrir_demo(self, langue):
        page = self.page
        if langue == "fr":
            page.goto(url_fichier("index.html"))
        else:
            page.evaluate("(code) => localStorage.setItem('prevo.langue', code)", langue)
            page.reload()
        page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        page.click("#btn-demo")
        attendre_pret(page)
        self.assertEqual(page.evaluate("[I18n.langue, document.documentElement.lang]"), [langue, langue])

    def aller(self, route, selecteur):
        self.page.evaluate("location.hash = %r" % route)
        self.page.wait_for_selector(selecteur)

    def onglet(self, identifiant):
        self.page.click(".onglet[data-onglet='%s']" % identifiant)

    def fichier(self, table):
        return self.page.evaluate(LIRE_FICHIER_JS, table)

    def textes(self, cle, valeurs=None):
        return self.page.evaluate(DEUX_TEXTES_JS, [cle, valeurs or {}])

    def ecrire_par_l_ecran(self, action, table):
        """action() puis attente de la nouvelle ligne de journal de `table`."""
        avant = self.page.evaluate(NB_JOURNAL_JS, table)
        action()
        self.page.wait_for_function("([table, n]) => Donnees.lignes('journal').filter((l) => l.table === table).length > n",
                                    arg=[table, avant])

    def ecrire_et_relever(self):
        """La même suite d'écritures dans la langue ouverte ; renvoie ce qui a été écrit et ce qui a été affiché."""
        page = self.page
        debut_journal = len(self.fichier("journal"))
        self.aller("#/ot/" + OT_EN_COURS, ".ot-fiche .ot-badges .badge.statut")

        # Temps passé (onglet Exécution).
        self.onglet("execution")
        page.fill("#ot-temps-heures", "1.5")
        self.ecrire_par_l_ecran(lambda: page.click("#form-temps button[type=submit]"), "ot_temps")
        temps_ajoute = page.evaluate("I18n.t('ordres.temps.temps_ajoute')")
        page.wait_for_function(TOAST_JS, arg=temps_ajoute)

        # Opération puis pièce prévue (onglet Préparation).
        self.onglet("preparation")
        page.wait_for_selector("#form-operations [name=nouvelle_operation]")
        page.fill("#form-operations [name=nouvelle_operation]", OPERATION)
        self.ecrire_par_l_ecran(lambda: page.click("#form-operations button[type=submit]"), "ot_operations")
        page.wait_for_selector("#ot-nouvel-article")
        article = page.eval_on_selector("#ot-nouvel-article", "(liste) => Array.from(liste.options).find((o) => o.value).value")
        page.select_option("#ot-nouvel-article", article)
        page.fill("#ot-nouvelle-quantite", "1")
        self.ecrire_par_l_ecran(lambda: page.click("#form-pieces button[type=submit]"), "ot_pieces")

        # Inventaire sans commentaire (commentaire et utilisateur écrits par Prévo).
        page.evaluate("(id) => Magasin.inventorier([{ articleId: id, quantite: 7 }], '')", article)
        inventaire = [m for m in self.fichier("mouvements_stock") if m["type"] == "inventaire" and m["article_id"] == article]

        # Motif « Pièce : … » pré-rempli (refus de « Planifié » faute de stock), puis Annuler : rien n'est écrit.
        self.aller("#/ot/" + OT_PIECE_MANQUANTE, ".ot-fiche .ot-badges .badge.statut")
        self.onglet("preparation")
        page.click(".ot-actions-preparation button[data-action='transition'][data-cible='Planifié']")
        page.click("#ot-message button[data-action='attente-piece']")
        page.wait_for_selector("dialog textarea")
        motif = page.input_value("dialog textarea")
        question = page.inner_text("dialog")
        page.click("dialog .fenetre-actions .btn-fantome")

        journal = self.fichier("journal")[debut_journal:]
        return {
            "journal": [(l["poste"], l["profil"], l["table"], l["id_ligne"], l["action"]) for l in journal],
            "inventaire": (inventaire[-1]["commentaire"], inventaire[-1]["utilisateur"]),
            "motif": motif,
            "affiche": {"toast": temps_ajoute, "question": question},
        }

    # -- tests ----------------------------------------------------------------------------------

    def test_ecritures_en_anglais_identiques_au_francais(self):
        self.ouvrir_demo("fr")
        francais = self.ecrire_et_relever()
        self.ouvrir_demo("en")
        anglais = self.ecrire_et_relever()

        # Les données : identiques, octet pour octet (hors identifiant et heure des lignes du journal).
        self.assertEqual(anglais["journal"], francais["journal"])
        self.assertEqual(anglais["inventaire"], francais["inventaire"])
        self.assertEqual(anglais["motif"], francais["motif"])

        # … et au texte français du dictionnaire, dont l'anglais diffère (sinon le test ne prouverait rien).
        actions = {table: action for (_, _, table, _, action) in anglais["journal"]}
        for cle, table in (("ordres.ajouter_temps.temps_passe", "ot_temps"),
                           ("ordres.enregistrer_operations.operations_ot_id", "ot_operations"),
                           ("ordres.enregistrer_pieces.pieces_prevues", "ot_pieces")):
            with self.subTest(cle=cle):
                textes = self.textes(cle, {"otId": OT_EN_COURS})
                self.assertEqual(textes["donnees"], textes["reference"])
                self.assertNotEqual(textes["ecran"], textes["reference"])
                self.assertEqual(actions[table], "création — " + textes["reference"])
        profil = self.textes("socle.libelle_type.responsable")
        self.assertNotEqual(profil["ecran"], profil["reference"])
        self.assertEqual({p for (_, p, _, _, _) in anglais["journal"]}, {profil["reference"]})
        self.assertEqual({p for (p, _, _, _, _) in anglais["journal"]}, {"Poste test"})
        inventaire, responsable = (self.textes("magasin.inventorier.inventaire"),
                                   self.textes("magasin.utilisateur_courant.responsable"))
        self.assertEqual(anglais["inventaire"], (inventaire["reference"], responsable["reference"]))
        self.assertNotEqual((inventaire["ecran"], responsable["ecran"]), anglais["inventaire"])
        self.assertTrue(anglais["motif"].startswith("Pièce : "), anglais["motif"])
        manque = self.textes("ordres.mettre_en_attente_piece.stock_insuffisant")
        self.assertNotIn(manque["ecran"], anglais["motif"])

        # L'écran, lui, est dans sa langue : message et fenêtre de la mise en attente en anglais.
        self.assertNotEqual(anglais["affiche"]["toast"], francais["affiche"]["toast"])
        self.assertNotEqual(anglais["affiche"]["question"], francais["affiche"]["question"])
        self.assertEqual(self.cles_absentes, [])

    def test_rapport_fige_en_anglais_document_en_francais(self):
        page = self.page
        self.ouvrir_demo("fr")
        self.ouvrir_demo("en")
        mois = page.evaluate("Rapport.moisAProposer(Donnees.aujourdhui())")
        self.assertTrue(mois)
        page.wait_for_selector("#bandeau-rapport")
        plus_tard = self.textes("rapport.tuile_accueil.plus_tard")
        self.assertNotEqual(plus_tard["ecran"], plus_tard["reference"])
        self.assertEqual(page.inner_text('#bandeau-rapport [data-action="rapport-plus-tard"]').strip(), plus_tard["ecran"])

        page.click('#bandeau-rapport [data-action="figer-rapport"]')
        nom = "rapport-mensuel-%s.html" % mois
        page.wait_for_function("(nom) => App.adaptateur.documentsEnMemoire().some((d) => d.nom === nom)", arg=nom)
        fige = self.textes("rapport.executer.rapport_fige", {"resultatNom": nom})
        self.assertNotEqual(fige["ecran"], fige["reference"])
        page.wait_for_function(TOAST_JS, arg=fige["ecran"])            # le message : dans la langue de l'écran

        document = page.evaluate("async (nom) => (await App.adaptateur.lireDocument(nom)).text()", nom)
        libelle_mois = NOMS_MOIS[int(mois[5:7]) - 1] + " " + mois[:4]
        self.assertIn('<html lang="fr">', document)
        titre = self.textes("rapport.texte_courriel.rapport_mensuel_maintenance_2", {"libelleMois": libelle_mois})
        self.assertIn("<h1>%s</h1>" % titre["reference"], document)
        for cle in ("rapport.html.faits_marquants", "rapport.html.comprendre", "rapport.tuiles_definies.disponibilite"):
            with self.subTest(cle=cle):
                textes = self.textes(cle)
                self.assertNotEqual(textes["ecran"], textes["reference"])
                self.assertIn(textes["reference"], document)
                self.assertNotIn(textes["ecran"], document)
        # Nombres à la française : virgule décimale, jamais « 92.4 » ni « 1,234 ».
        valeurs = re.findall(r'<div class="val">([^<]*)</div>', document)
        self.assertEqual(len(valeurs), 4)    # disponibilité, coût, part du préventif, coût de l'arrêt (L5, T470)
        for valeur in valeurs:
            with self.subTest(valeur=valeur):
                self.assertIsNone(re.search(r"\d\.\d|\d,\d{3}(?!\d)", valeur))
        # La langue de l'écran est revenue après l'écriture du document.
        self.assertEqual(page.evaluate("[I18n.langue, I18n.locale]"), ["en", "en-GB"])
        self.assertEqual(self.cles_absentes, [])


if __name__ == "__main__":
    unittest.main()
