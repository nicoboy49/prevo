"""Écritures des synthèses du wiki (tâche T99, ARCHITECTURE.md §20.5).

    démo     : enregistrer (« à valider »), valider (nom et date), revalider sans effet, texte identique sans
               effet, texte corrigé → « à valider », « corrigée par », validateur effacé ; remplacement
               (l'ancienne reste, « remplacée », plus validable ni corrigeable) ; refus sans rien écrire
               (consigne de sécurité, OT non permis ; correction à la main : OT clôturé de l'équipement
               permis, OT d'un autre équipement refusé) ; journal et trace de l'IA ; Donnees.problemes()
               propre ; visibilité par profil ;
    profils  : technicien et demandeur ne peuvent ni enregistrer, ni valider, ni corriger ;
    serveur  : le fichier wiki_syntheses.csv est écrit sur le disque ; un autre poste qui a validé entre-temps
               n'est pas écrasé (conflit de version, relecture) ;
    dossier  : même parcours avec StockageDossier (dossier simulé dans l'OPFS).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_wiki_ecritures.py" -v
"""
import csv
import io
import re
import unittest

from commun import (RACINE, CasNavigateur, ServeurPrevo, ServeurStatique, attendre_pret,
                    installer_dossier_simule, preregler_profil, url_fichier)

NOM = "Nicolas Test"

# Équipement qui a au moins deux OT clôturés, ses deux plus récents, un OT clôturé d'un autre équipement.
CAS_JS = """() => {
  const clos = Donnees.lignes('ordres_travail').filter((o) => /^Clôturé/.test(o.statut))
    .sort((a, b) => (b.date_fin || '').localeCompare(a.date_fin || ''));
  const compte = new Map();
  clos.forEach((o) => compte.set(o.equipement_id, (compte.get(o.equipement_id) || 0) + 1));
  const equipement = Array.from(compte.entries()).find(([, n]) => n >= 4)[0];
  const siens = clos.filter((o) => o.equipement_id === equipement).map((o) => o.id);
  const autre = clos.find((o) => o.equipement_id !== equipement).id;
  return { equipement, ot1: siens[0], ot2: siens[1], ot3: siens[2], autre };
}"""

APPELER_JS = """async ([nom, args]) => {
  try {
    return { ok: true, valeur: await Wiki[nom](...args) };
  } catch (erreur) {
    return { ok: false, nom: erreur.name, message: erreur.message };
  }
}"""

ETAT_JS = """(equipement) => ({
  lignes: Donnees.lignes('wiki_syntheses').filter((l) => l.equipement_id === equipement).map((l) => Object.assign({}, l)),
  total: Donnees.lignes('wiki_syntheses').length,
  journal: Donnees.lignes('journal').filter((j) => j.table === 'wiki_syntheses').map((j) => j.action),
  problemes: Donnees.problemes().filter((p) => p.table === 'wiki_syntheses').map((p) => p.message),
})"""


def texte_synthese(cas, consigne=False):
    lignes = ["Ce qui revient", "- Fuite au joint de tige, fréquente ici [%s]" % cas["ot1"],
              "À surveiller", "- Roulement côté moteur [%s]" % cas["ot2"]]
    if consigne:
        lignes[1] = "- Consigner la presse puis changer le joint [%s]" % cas["ot1"]
    return "\n".join(lignes)


class CasEcritures(CasNavigateur):

    def appeler(self, nom, *args):
        return self.page.evaluate(APPELER_JS, [nom, list(args)])

    def etat(self, equipement):
        return self.page.evaluate(ETAT_JS, equipement)

    def parcours_complet(self, cas, trace=True):
        """Enregistrer → valider → revalider → texte identique → texte corrigé ; renvoie l'identifiant.
        « trace » : la trace de l'IA (D65) est attendue au journal (pas sur la page du mode dossier, sans Ia)."""
        texte = texte_synthese(cas)
        enregistre = self.appeler("enregistrer", cas["equipement"],
                                  {"texte": texte, "otSources": [cas["ot1"], cas["ot2"]], "modele": "faux"})
        self.assertTrue(enregistre["ok"], enregistre)
        identifiant = enregistre["valeur"]
        self.assertRegex(identifiant, r"^WIKI-\d{4}$")
        ligne = self.etat(cas["equipement"])["lignes"][-1]
        self.assertEqual((ligne["statut"], ligne["valide_par"], ligne["corrigee_par"], ligne["modele"]),
                         ("à valider", "", "", "faux"))
        self.assertEqual(ligne["texte"], texte)
        self.assertEqual(ligne["ot_cites"], "%s;%s" % (cas["ot1"], cas["ot2"]))
        self.assertEqual(ligne["ot_sources"], "%s;%s" % (cas["ot1"], cas["ot2"]))
        self.assertRegex(ligne["date_proposition"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")

        self.assertEqual(self.appeler("valider", identifiant), {"ok": True, "valeur": True})
        ligne = self.etat(cas["equipement"])["lignes"][-1]
        self.assertEqual((ligne["statut"], ligne["valide_par"]), ("validée", NOM))
        self.assertRegex(ligne["date_validation"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
        self.assertEqual(self.appeler("valider", identifiant), {"ok": True, "valeur": False})
        # Même texte, autres espaces et fins de ligne : rien ne change, la synthèse reste validée.
        self.assertEqual(self.appeler("modifier", identifiant, "  " + texte.replace("\n", "\r\n\r\n") + "  "),
                         {"ok": True, "valeur": False})
        self.assertEqual(self.etat(cas["equipement"])["lignes"][-1]["statut"], "validée")

        # Texte corrigé (un OT clôturé de l'équipement, non envoyé à l'IA, est permis) → « à valider ».
        corrige = texte + "\n- Courroie à surveiller [%s]" % cas["ot3"]
        self.assertEqual(self.appeler("modifier", identifiant, corrige), {"ok": True, "valeur": True})
        ligne = self.etat(cas["equipement"])["lignes"][-1]
        self.assertEqual((ligne["statut"], ligne["corrigee_par"], ligne["valide_par"], ligne["date_validation"]),
                         ("à valider", NOM, "", ""))
        self.assertEqual(ligne["ot_cites"], "%s;%s;%s" % (cas["ot1"], cas["ot2"], cas["ot3"]))
        self.assertRegex(ligne["date_modification"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
        etat = self.etat(cas["equipement"])
        self.assertEqual(etat["problemes"], [])
        actions = " | ".join(etat["journal"])
        attendus = ["création — synthèse proposée (faux)", "synthèse validée", "synthèse corrigée — à valider"]
        for attendu in attendus + (["proposition IA utilisée (faux) : synthèse"] if trace else []):
            self.assertIn(attendu, actions)
        return identifiant


class TestDemo(CasEcritures):

    def ouvrir(self, profil="responsable", nom=NOM, technicien=""):
        preregler_profil(self.contexte, profil, nom, technicien)
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        return self.page.evaluate(CAS_JS)

    def test_parcours_valider_puis_corriger(self):
        self.parcours_complet(self.ouvrir())

    def test_remplacement_l_ancienne_reste_et_n_est_plus_modifiable(self):
        cas = self.ouvrir()
        premiere = self.appeler("enregistrer", cas["equipement"],
                                {"texte": texte_synthese(cas), "otSources": [cas["ot1"], cas["ot2"]], "modele": "faux"}, {"valider": True})
        self.assertTrue(premiere["ok"], premiere)
        self.assertEqual(self.etat(cas["equipement"])["lignes"][-1]["statut"], "validée")
        seconde = self.appeler("enregistrer", cas["equipement"],
                               {"texte": texte_synthese(cas), "otSources": [cas["ot1"], cas["ot2"]], "modele": "autre"})
        self.assertTrue(seconde["ok"], seconde)
        lignes = {l["id"]: l for l in self.etat(cas["equipement"])["lignes"]}
        self.assertEqual(lignes[premiere["valeur"]]["statut"], "remplacée")
        self.assertEqual(lignes[seconde["valeur"]]["statut"], "à valider")
        self.assertEqual([l["id"] for l in self.page.evaluate("(e) => Wiki.remplacees(e)", cas["equipement"])],
                         [premiere["valeur"]])
        for nom, args in (("valider", [premiere["valeur"]]), ("modifier", [premiere["valeur"], texte_synthese(cas) + " !"])):
            with self.subTest(appel=nom):
                refus = self.appeler(nom, *args)
                self.assertEqual((refus["ok"], refus["nom"]), (False, "ErreurValidation"))
                self.assertIn("remplacée", refus["message"])
        self.assertEqual(self.etat(cas["equipement"])["problemes"], [])

    def test_refus_sans_rien_ecrire(self):
        cas = self.ouvrir()
        avant = self.etat(cas["equipement"])
        refus = {
            "consigne": (cas["equipement"], {"texte": texte_synthese(cas, consigne=True),
                                             "otSources": [cas["ot1"], cas["ot2"]], "modele": "faux"}, {}),
            "OT non envoyé": (cas["equipement"], {"texte": texte_synthese(cas), "otSources": [cas["ot1"]], "modele": "faux"}, {}),
            "OT d'un autre équipement, même corrigé": (
                cas["equipement"], {"texte": texte_synthese(cas) + "\n- Autre [%s]" % cas["autre"],
                                    "otSources": [cas["ot1"], cas["ot2"]], "modele": "faux"}, {"corrige": True}),
            "équipement inconnu": ("EQ-9999", {"texte": texte_synthese(cas), "otSources": [cas["ot1"]], "modele": "faux"}, {}),
        }
        for nom, args in refus.items():
            with self.subTest(cas=nom):
                resultat = self.appeler("enregistrer", *args)
                self.assertEqual((resultat["ok"], resultat["nom"]), (False, "ErreurValidation"), resultat)
        self.assertEqual(self.etat(cas["equipement"])["total"], avant["total"])
        self.assertEqual(self.etat(cas["equipement"])["journal"], avant["journal"])
        # Correction à la main : un OT clôturé de l'équipement, même non envoyé à l'IA, est permis.
        permis = self.appeler("enregistrer", cas["equipement"],
                              {"texte": texte_synthese(cas), "otSources": [cas["ot1"]], "modele": "faux"}, {"corrige": True})
        self.assertTrue(permis["ok"], permis)
        self.assertEqual(self.etat(cas["equipement"])["lignes"][-1]["corrigee_par"], NOM)

    def test_visibilite_par_profil(self):
        self.ouvrir()
        matrice = self.page.evaluate("""() => ['à valider', 'validée', 'remplacée'].map((statut) =>
          [statut, ['demandeur', 'technicien', 'responsable'].map((type) => Wiki.syntheseVisible({ statut }, { type }))])""")
        self.assertEqual(matrice, [["à valider", [False, False, True]], ["validée", [True, True, True]],
                                   ["remplacée", [False, False, True]]])
        self.assertFalse(self.page.evaluate("Wiki.syntheseVisible(null, { type: 'responsable' })"))


class TestProfils(CasEcritures):

    def verifier_refus(self, profil, nom, technicien):
        preregler_profil(self.contexte, profil, nom, technicien)
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        cas = self.page.evaluate(CAS_JS)
        for appel, args in (("enregistrer", [cas["equipement"], {"texte": texte_synthese(cas),
                                                                   "otSources": [cas["ot1"], cas["ot2"]], "modele": "faux"}]),
                            ("valider", ["WIKI-0001"]), ("modifier", ["WIKI-0001", texte_synthese(cas)])):
            with self.subTest(appel=appel):
                resultat = self.appeler(appel, *args)
                self.assertEqual((resultat["ok"], resultat["nom"]), (False, "ErreurValidation"))
                self.assertEqual(resultat["message"], self.page.evaluate("Wiki.MESSAGE_RESERVE"))
        self.assertEqual(self.page.evaluate("Donnees.lignes('wiki_syntheses').length"), 0)

    def test_technicien(self):
        self.verifier_refus("technicien", "", "TEC-0001")

    def test_demandeur(self):
        self.verifier_refus("demandeur", "Lucie Martin", "")


def lignes_csv(octets):
    texte = octets.decode("utf-8-sig")
    lecteur = csv.reader(io.StringIO(texte), delimiter=";")
    entete = next(lecteur)
    return [dict(zip(entete, cellules)) for cellules in lecteur if any(cellules)]


class TestServeur(CasEcritures):

    def test_fichier_sur_le_disque_et_autre_poste_non_ecrase(self):
        with ServeurPrevo() as serveur:
            preregler_profil(self.contexte, "responsable", NOM)
            self.page.goto(serveur.url + "/#/accueil")
            attendre_pret(self.page)
            self.page.evaluate("Donnees.arreterSurveillance()")        # le cache doit pouvoir rester périmé
            cas = self.page.evaluate(CAS_JS)
            identifiant = self.parcours_complet(cas)
            fichier = serveur.dossier / "wiki_syntheses.csv"
            sur_disque = [l for l in lignes_csv(fichier.read_bytes()) if l["id"] == identifiant]
            self.assertEqual(len(sur_disque), 1)
            self.assertEqual(sur_disque[0]["statut"], "à valider")
            self.assertIn("synthèse corrigée — à valider", (serveur.dossier / "journal.csv").read_text(encoding="utf-8-sig"))

            # Un autre poste valide pendant que notre page garde l'ancien état : notre « Valider » relit le
            # fichier (conflit de version) et ne réécrit pas son validateur.
            # (Lecture et écriture par le module csv : ot_cites contient des « ; », il est entre guillemets.)
            rangees = list(csv.reader(io.StringIO(fichier.read_bytes().decode("utf-8-sig")), delimiter=";"))
            entete = rangees[0]
            for rangee in rangees[1:]:
                if rangee and rangee[0] == identifiant:
                    rangee[entete.index("statut")] = "validée"
                    rangee[entete.index("valide_par")] = "Autre poste"
                    rangee[entete.index("date_validation")] = "2026-10-22 08:00"
            sortie = io.StringIO()
            csv.writer(sortie, delimiter=";", lineterminator="\r\n").writerows(rangees)
            fichier.write_bytes(b"\xef\xbb\xbf" + sortie.getvalue().encode("utf-8"))
            self.autoriser_erreur(re.compile(r"status of 409.*/api/csv/wiki_syntheses"))
            self.assertEqual(self.appeler("valider", identifiant), {"ok": True, "valeur": False})
            ligne = [l for l in lignes_csv(fichier.read_bytes()) if l["id"] == identifiant][0]
            self.assertEqual((ligne["statut"], ligne["valide_par"]), ("validée", "Autre poste"))


AIDE_DOSSIER_JS = """
window.aideWiki = (() => {
  async function racine() {
    return (await navigator.storage.getDirectory()).getDirectoryHandle('donnees-wiki', { create: true });
  }
  async function installer(tables) {
    const dossier = await racine();
    for (const table of tables) {
      const octets = new Uint8Array(await (await fetch('/donnees/demo/' + table + '.csv', { cache: 'no-store' })).arrayBuffer());
      const flux = await (await dossier.getFileHandle(table + '.csv', { create: true })).createWritable();
      await flux.write(octets);
      await flux.close();
    }
  }
  async function lire(nom) {
    const dossier = await racine();
    const fichier = await (await dossier.getFileHandle(nom)).getFile();
    return await fichier.text();
  }
  async function ouvrir() {
    window.App = { profil: { type: 'responsable', nom: %s, technicienId: '' } };
    const stockage = await StockageDossier.creer(await window.showDirectoryPicker(), { poste: 'Poste test' });
    Donnees.initialiser(stockage, { poste: 'Poste test', profil: 'Responsable' });
    await Donnees.chargerTout();
  }
  return { installer, lire, ouvrir };
})();
"""


class TestDossier(CasEcritures):

    def test_parcours_en_mode_dossier(self):
        with ServeurStatique(RACINE) as statique:
            installer_dossier_simule(self.contexte, "donnees-wiki")
            self.page.goto(statique.url + "/tests/fixtures/page-stockage-dossier.html")
            for script in ("js/interface.js", "js/modules/causes-frequentes.js", "js/modules/indicateurs-regles.js",
                           "js/modules/wiki-regles.js", "js/modules/wiki-ecritures.js"):
                self.page.add_script_tag(url=statique.url + "/" + script)
            self.page.add_script_tag(content=AIDE_DOSSIER_JS % ('"%s"' % NOM))
            tables = self.page.evaluate("Schema.nomsTables()")
            self.page.evaluate("(t) => aideWiki.installer(t)", [t for t in tables if t != "wiki_syntheses"])
            self.page.evaluate("aideWiki.ouvrir()")
            cas = self.page.evaluate(CAS_JS)
            identifiant = self.parcours_complet(cas, trace=False)
            contenu = self.page.evaluate("aideWiki.lire('wiki_syntheses.csv')")
            ligne = [l for l in lignes_csv(contenu.encode("utf-8")) if l["id"] == identifiant][0]
            self.assertEqual((ligne["statut"], ligne["corrigee_par"]), ("à valider", NOM))


if __name__ == "__main__":
    unittest.main()
