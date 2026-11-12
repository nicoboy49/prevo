"""Import ZIP coupé pendant les écritures (T508, relecture R3 ; ARCHITECTURE.md §22.11).

L'import remplace les tables l'une après l'autre, sans transaction (D172 : aucune route serveur). Un marqueur durable,
le paramètre « import_zip_en_cours » (valeur : nom de la sauvegarde « avant-import-zip »), est posé dans parametres.csv
avant la première table et retiré par la dernière écriture (parametres.csv, remplacée en dernier). S'il est encore là
à l'ouverture, un bandeau le dit : au responsable, le nom de la sauvegarde à restaurer et le lien vers Paramètres ;
aux autres rôles, « prévenez le responsable ».

    serveur   (comptes) import coupé au milieu (une écriture ne finit jamais, puis la page est rechargée) : marqueur
              dans parametres.csv, bandeau du responsable (sauvegarde nommée, lien), bandeau du technicien (sans lien),
              marqueur absent d'un export ; restauration complète de la sauvegarde : marqueur et bandeau retirés ;
              import mené au bout (ZIP qui porte lui-même la clé) : aucun marqueur, aucun bandeau ;
              écriture en panne ET retour arrière en panne : marqueur gardé, bandeau à la réouverture ;
              écriture en panne, retour arrière réussi : aucun marqueur ;
              comptes (relecture R3, D172 : prévenir seulement) : la confirmation liste le compte dont la fiche de
              technicien liée change de personne ou n'existe pas dans le ZIP ; rien si la fiche est la même ;
              acces/ jamais écrit ;
    dossier   (OPFS) import coupé puis page rechargée : bandeau après « Reprendre ».

    py -X utf8 -m unittest discover -s tests -p "test_import_zip_interrompu.py" -v
"""

import re
import unittest

from commun import RACINE, ServeurPrevo, ServeurStatique, attendre_pret, installer_dossier_simule, preregler_profil
from test_zip_import import (BOUTON_ANNULER, BOUTON_REMPLACER, ECRIRE_OPFS_JS, ERREUR_PING_ABSENT, ERREUR_TABLE_ABSENTE,
                             ERREUR_TABLE_NOUVELLE_ABSENTE, ERREUR_TABLE_REFUSEE, INSTANTANE_OPFS_JS,
                             MOTIF_AVANT_IMPORT_ZIP, NOM_DOSSIER, PANNE_ENREGISTRER_JS, CasImport, ecrire_zip,
                             en_base64, fichiers_demo, fichiers_du_jeu, instantane, lire_csv, sauvegardes_de)

import base64

CLE = "import_zip_en_cours"
TABLE_COUPEE = "ordres_travail"            # 4e table du schéma : equipements, localisations, demandes écrites avant
BANDEAU = "#bandeau-import-interrompu"

# Une écriture qui ne finit jamais : l'onglet « fermé » (page rechargée) pendant les écritures.
ECRITURE_SANS_FIN_JS = """(table) => {
  const vrai = App.adaptateur.enregistrer;
  window.__ecrites = [];
  App.adaptateur.enregistrer = function (nomTable, ...reste) {
    if (nomTable === table) { window.__coupe = true; return new Promise(() => {}); }
    window.__ecrites.push(nomTable);
    return vrai.call(this, nomTable, ...reste);
  };
}"""

PANNE_RESTAURER_JS = """() => {
  App.adaptateur.restaurer = () => Promise.reject(new Donnees.ErreurStockage('panne simulée de la restauration.'));
}"""

# Ordre des écritures de tables (journal compris), pour vérifier que parametres est la dernière.
ESPION_ECRITURES_JS = """() => {
  window.__ecrites = [];
  ['enregistrer', 'ajouter'].forEach((methode) => {
    const vrai = App.adaptateur[methode];
    if (typeof vrai !== 'function') return;
    App.adaptateur[methode] = function (nomTable, ...reste) {
      window.__ecrites.push(nomTable);
      return vrai.call(this, nomTable, ...reste);
    };
  });
}"""


def marqueur(octets_parametres):
    """Valeur du paramètre import_zip_en_cours dans un parametres.csv (None s'il n'y est pas)."""
    for ligne in lire_csv(octets_parametres)[1]:
        if ligne["cle"] == CLE:
            return ligne["valeur"]
    return None


def csv_f3():
    return {chemin: o for chemin, o in fichiers_du_jeu("f3-v1.2.0").items() if chemin.endswith(".csv")}


def texte_de(page, selecteur):
    return re.sub(r"\s+", " ", page.inner_text(selecteur)).strip()


class CasInterrompu(CasImport):

    def setUp(self):
        super().setUp()
        for motif in (ERREUR_TABLE_REFUSEE, ERREUR_TABLE_ABSENTE, ERREUR_TABLE_NOUVELLE_ABSENTE):
            self.autoriser_erreur(motif)

    def couper_l_import(self, page, chemin_zip):
        """Import confirmé ; l'écriture de TABLE_COUPEE ne finit jamais. Rend les tables écrites avant."""
        page.evaluate(ECRITURE_SANS_FIN_JS, TABLE_COUPEE)
        self.choisir_zip(page, chemin_zip)
        self.confirmation(page)
        page.click(BOUTON_REMPLACER)
        page.wait_for_function("window.__coupe === true")
        return page.evaluate("window.__ecrites")


class TestServeur(CasInterrompu):

    def ouvrir(self, serveur, contexte, role, route="/#/parametres"):
        serveur.poser_session(contexte, role)
        page = self.page if contexte is self.contexte else contexte.new_page()
        if page is not self.page:
            self.surveiller(page)
        page.goto(serveur.url + route)
        attendre_pret(page)
        return page

    def test_serveur_import_coupe_marqueur_bandeau_par_role_puis_restauration(self):
        chemin_zip = ecrire_zip(self.temporaire / "f3.zip", csv_f3())
        with ServeurPrevo(comptes=True) as serveur:
            page = self.ouvrir(serveur, self.contexte, "responsable")
            self.assertEqual(page.locator(BANDEAU).count(), 0)
            avant = instantane(serveur.dossier)
            self.assertIsNone(marqueur(avant["parametres.csv"]))
            ecrites = self.couper_l_import(page, chemin_zip)
            # Le marqueur est posé avant la première table remplacée ; parametres n'est pas encore remplacée.
            self.assertEqual(ecrites[0], "parametres", ecrites)
            self.assertGreater(len(ecrites), 1, ecrites)
            self.assertEqual(ecrites.count("parametres"), 1, ecrites)
            coupe = instantane(serveur.dossier)
            noms = sauvegardes_de(coupe, MOTIF_AVANT_IMPORT_ZIP)
            self.assertEqual(len(noms), 1, noms)
            self.assertEqual(marqueur(coupe["parametres.csv"]), noms[0])
            # La sauvegarde d'avant l'import ne porte pas le marqueur.
            self.assertEqual(coupe["sauvegardes/%s/parametres.csv" % noms[0]], avant["parametres.csv"])
            # Base moitié ancienne, moitié nouvelle.
            self.assertNotEqual(coupe["equipements.csv"], avant["equipements.csv"])
            self.assertEqual(coupe["ordres_travail.csv"], avant["ordres_travail.csv"])

            # Réouverture par le responsable : bandeau qui nomme la sauvegarde, lien vers Paramètres.
            page.reload()
            attendre_pret(page)
            page.wait_for_selector(BANDEAU)
            texte = texte_de(page, BANDEAU)
            self.assertIn("Import ZIP interrompu", texte)
            self.assertIn("« %s »" % noms[0], texte)
            self.assertEqual(page.locator(BANDEAU + " a").get_attribute("href"), "#/parametres")
            # Rien d'écrit au démarrage : le marqueur reste, les fichiers n'ont pas changé.
            self.assertEqual(instantane(serveur.dossier)["parametres.csv"], coupe["parametres.csv"])
            # Le marqueur ne part pas dans un export.
            exporte = page.evaluate("new TextDecoder().decode(Donnees.instantane().parametres)")
            self.assertNotIn(CLE, exporte)
            self.assertIn("version_schema", exporte)

            # Un autre poste, technicien : « prévenez le responsable », sans lien.
            contexte_tech = self.navigateur.new_context(locale="fr-FR")
            self.addCleanup(contexte_tech.close)
            page_tech = self.ouvrir(serveur, contexte_tech, "technicien", "/#/accueil")
            page_tech.wait_for_selector(BANDEAU)
            texte_tech = texte_de(page_tech, BANDEAU)
            self.assertIn("Import ZIP interrompu", texte_tech)
            self.assertIn("prévenez le responsable", texte_tech)
            self.assertEqual(page_tech.locator(BANDEAU + " a").count(), 0)
            contexte_tech.close()

            # Restauration complète de la sauvegarde nommée : marqueur retiré, bandeau retiré, et pas de retour.
            page.locator(BANDEAU + " a").click()
            page.wait_for_selector('button[data-restaurer="%s"]' % noms[0])
            page.click('button[data-restaurer="%s"]' % noms[0])
            page.wait_for_selector("#fenetre-restauration")
            page.click("dialog .fenetre-actions .btn-danger")
            page.wait_for_selector("#nom-copie-securite")
            apres = instantane(serveur.dossier)
            self.assertIsNone(marqueur(apres["parametres.csv"]))
            self.assertEqual(apres["parametres.csv"], avant["parametres.csv"])
            self.assertEqual(apres["equipements.csv"], avant["equipements.csv"])
            self.assertEqual(page.locator(BANDEAU).count(), 0)
            page.reload()
            attendre_pret(page)
            page.wait_for_selector("#btn-import-zip")
            self.assertEqual(page.locator(BANDEAU).count(), 0)

    def test_serveur_import_mene_au_bout_aucun_marqueur_parametres_en_dernier(self):
        # Le ZIP porte lui-même la clé (export d'une base restée interrompue, ZIP fait à la main) : jamais importée.
        fichiers = csv_f3()
        fichiers["parametres.csv"] = fichiers["parametres.csv"].rstrip(b"\r\n") + (
            "\r\n%s;2020-01-01_000000_avant-import-zip\r\n" % CLE).encode("utf-8")
        chemin_zip = ecrire_zip(self.temporaire / "f3-marque.zip", fichiers)
        with ServeurPrevo() as serveur:
            preregler_profil(self.contexte, "responsable")
            page = self.page
            page.goto(serveur.url + "/#/parametres")
            attendre_pret(page)
            page.wait_for_selector("#btn-import-zip")
            page.evaluate(ESPION_ECRITURES_JS)
            self.choisir_zip(page, chemin_zip)
            self.confirmation(page)
            page.click(BOUTON_REMPLACER)
            self.texte_fenetre(page, "import-zip-termine")
            ecrites = page.evaluate("window.__ecrites")
            self.assertEqual(ecrites[0], "parametres", ecrites)
            self.assertEqual(ecrites[-1], "parametres", ecrites)
            self.assertEqual(ecrites[-2], "journal", ecrites)
            apres = instantane(serveur.dossier)
            self.assertIsNone(marqueur(apres["parametres.csv"]))
            self.assertNotIn(CLE.encode("utf-8"), apres["parametres.csv"])
            with page.expect_navigation():
                page.click("dialog button:has-text('Recharger Prévo')")
            attendre_pret(page)
            page.wait_for_selector("#btn-import-zip")
            self.assertEqual(page.locator(BANDEAU).count(), 0)

    def test_serveur_panne_puis_retour_arriere_en_panne_marqueur_garde_bandeau_a_la_reouverture(self):
        chemin_zip = ecrire_zip(self.temporaire / "f3.zip", csv_f3())
        with ServeurPrevo() as serveur:
            preregler_profil(self.contexte, "responsable")
            page = self.page
            page.goto(serveur.url + "/#/parametres")
            attendre_pret(page)
            page.wait_for_selector("#btn-import-zip")
            page.evaluate(PANNE_ENREGISTRER_JS, TABLE_COUPEE)
            page.evaluate(PANNE_RESTAURER_JS)
            self.choisir_zip(page, chemin_zip)
            self.confirmation(page)
            page.click(BOUTON_REMPLACER)
            self.texte_fenetre(page, "import-zip-echec")
            coupe = instantane(serveur.dossier)
            noms = sauvegardes_de(coupe, MOTIF_AVANT_IMPORT_ZIP)
            self.assertEqual(marqueur(coupe["parametres.csv"]), noms[0])
            page.reload()
            attendre_pret(page)
            page.wait_for_selector(BANDEAU)
            self.assertIn("« %s »" % noms[0], texte_de(page, BANDEAU))

    def test_serveur_panne_puis_retour_arriere_reussi_aucun_marqueur(self):
        chemin_zip = ecrire_zip(self.temporaire / "f3.zip", csv_f3())
        with ServeurPrevo() as serveur:
            preregler_profil(self.contexte, "responsable")
            page = self.page
            page.goto(serveur.url + "/#/parametres")
            attendre_pret(page)
            page.wait_for_selector("#btn-import-zip")
            avant = instantane(serveur.dossier)
            page.evaluate(PANNE_ENREGISTRER_JS, TABLE_COUPEE)
            self.choisir_zip(page, chemin_zip)
            self.confirmation(page)
            page.click(BOUTON_REMPLACER)
            self.texte_fenetre(page, "import-zip-echec")
            apres = instantane(serveur.dossier)
            self.assertEqual(apres["parametres.csv"], avant["parametres.csv"])
            self.fermer_fenetre(page, "import-zip-echec")
            page.reload()
            attendre_pret(page)
            page.wait_for_selector("#btn-import-zip")
            self.assertEqual(page.locator(BANDEAU).count(), 0)

    def confirmation_des_comptes(self, page, nom_zip, techniciens):
        """Confirmation d'un ZIP de la démo avec ce techniciens.csv, puis Annuler → texte de #comptes-import-zip
        (None s'il n'y est pas)."""
        chemin_zip = ecrire_zip(self.temporaire / nom_zip, dict(fichiers_demo(), **{"techniciens.csv": techniciens}))
        self.choisir_zip(page, chemin_zip)
        self.confirmation(page)
        texte = texte_de(page, "#comptes-import-zip") if page.locator("#comptes-import-zip").count() else None
        page.click(BOUTON_ANNULER)
        page.wait_for_selector("#confirmation-import-zip", state="detached")
        return texte

    def test_serveur_comptes_lies_a_une_fiche_que_l_import_change_dits_a_la_confirmation(self):
        demo = fichiers_demo()["techniciens.csv"]
        ligne = "TEC-0001;Moreau;Julien;".encode("utf-8")           # fiche liée au compte julien.moreau
        self.assertEqual(demo.count(ligne), 1)
        autre = demo.replace(ligne, "TEC-0001;Curie;Marie;".encode("utf-8"))
        debut = demo.index(ligne)
        sans = demo[:debut] + demo[demo.index(b"\r\n", debut) + 2:]
        with ServeurPrevo(comptes=True) as serveur:
            page = self.ouvrir(serveur, self.contexte, "responsable")
            page.wait_for_selector("#btn-import-zip")
            avant = instantane(serveur.dossier)
            # Même base : la fiche liée reste la même personne, rien n'est dit.
            self.assertIsNone(self.confirmation_des_comptes(page, "meme.zip", demo))
            # Même identifiant, autre personne.
            texte = self.confirmation_des_comptes(page, "autre.zip", autre)
            self.assertIn("1 compte est lié à une fiche de technicien qui ne sera plus la même personne", texte)
            self.assertIn("julien.moreau : la fiche TEC-0001 est Julien Moreau aujourd'hui, elle sera Marie Curie",
                          texte)
            self.assertIn("Équipe › Accès", texte)
            # Fiche absente du ZIP.
            texte = self.confirmation_des_comptes(page, "sans.zip", sans)
            self.assertIn("julien.moreau : la fiche TEC-0001 (Julien Moreau) n'existe pas dans le ZIP", texte)
            # Rien d'écrit (import annulé), acces/ compris.
            apres = instantane(serveur.dossier)
            self.assertEqual({c: o for c, o in apres.items() if c.startswith("acces/comptes")},
                             {c: o for c, o in avant.items() if c.startswith("acces/comptes")})
            self.assertEqual(apres["techniciens.csv"], avant["techniciens.csv"])


class TestDossier(CasInterrompu):

    def setUp(self):
        super().setUp()
        self.autoriser_erreur(ERREUR_PING_ABSENT)

    def opfs(self, page):
        return {chemin: base64.b64decode(valeur)
                for chemin, valeur in page.evaluate(INSTANTANE_OPFS_JS, NOM_DOSSIER).items()}

    def test_dossier_import_coupe_puis_page_rechargee_bandeau_apres_reprendre(self):
        chemin_zip = ecrire_zip(self.temporaire / "f3.zip", csv_f3())
        base = {chemin.name: chemin.read_bytes() for chemin in (RACINE / "donnees" / "demo").glob("*.csv")}
        installer_dossier_simule(self.contexte, NOM_DOSSIER)
        preregler_profil(self.contexte, "responsable")
        page = self.page
        with ServeurStatique(RACINE) as statique:
            page.goto(statique.url + "/index.html")
            page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
            page.evaluate(ECRIRE_OPFS_JS, [NOM_DOSSIER, {chemin: en_base64(o) for chemin, o in base.items()}])
            page.click("#btn-dossier")
            attendre_pret(page)
            self.assertEqual(page.evaluate("App.mode"), "dossier")
            page.evaluate("location.hash = '#/parametres'")
            page.wait_for_selector("#btn-import-zip")
            self.assertEqual(page.locator(BANDEAU).count(), 0)
            ecrites = self.couper_l_import(page, chemin_zip)
            self.assertEqual(ecrites[0], "parametres", ecrites)
            coupe = self.opfs(page)
            noms = sauvegardes_de(coupe, MOTIF_AVANT_IMPORT_ZIP)
            self.assertEqual(len(noms), 1, noms)
            self.assertEqual(marqueur(coupe["parametres.csv"]), noms[0])
            page.reload()
            page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
            page.click("#btn-reprendre")
            attendre_pret(page)
            page.wait_for_selector(BANDEAU)
            texte = texte_de(page, BANDEAU)
            self.assertIn("« %s »" % noms[0], texte)
            self.assertEqual(page.locator(BANDEAU + " a").get_attribute("href"), "#/parametres")
            self.assertEqual(marqueur(self.opfs(page)["parametres.csv"]), noms[0])


if __name__ == "__main__":
    unittest.main()
