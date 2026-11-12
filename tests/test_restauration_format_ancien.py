"""Restauration d'une sauvegarde d'un format plus ancien, et « Annuler cet import » sur une table qui n'existait pas
(chantier 2.2, T502 ; relecture R1 et R2 du 12/11 ; docs/FORMAT.md §8, docs/ARCHITECTURE.md §3 et §18.7).

Règle : à la restauration COMPLÈTE, une table de la base absente de la sauvegarde (elle n'existait pas alors :
reserves_controle, garanties, contrats_prestataires pour une sauvegarde d'avant la 2.2) est vidée (en-tête du format
courant, aucune ligne), après la copie de sécurité « avant-restauration », qui la contient. Une table demandée par son
nom, absente de la sauvegarde mais présente dans la base (annulation d'un import qui l'a créée), est vidée de même.

    serveur (sans navigateur, serveur réel de tests/commun.py, jeux de tests/jeux_formats.py)
        avant-format-v4    base 2.1 passée en 2.2, réserve, garanties et contrats ajoutés, restauration complète de
                           « avant-format-v4 » : plus aucune ligne dans les trois tables, la copie de sécurité les
                           contient à l'octet ; au redémarrage, le passage 3 → 4 redonne exactement les réserves du
                           premier passage (ni doublon, ni reste) ;
        annuler un import  tables touchées dont une n'existait pas avant (garanties) : 200, la table d'avant revient,
                           l'autre est vidée ; une table absente de la sauvegarde ET de la base : 400, aucune copie ;
        témoins            sauvegarde du format courant : restauration complète à l'octet, rien de vidé ; une seule
                           table : elle seule change.
    dossier (navigateur, OPFS ; à lancer à travers le verrou) : les mêmes règles par js/stockage-dossier.js.

Lancer depuis la racine du projet (à travers le verrou du navigateur) :
    py -X utf8 -m unittest discover -s tests -p "test_restauration_format_ancien.py" -v
"""
import http.client
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import test_stockage_dossier as aides_dossier
from commun import RACINE, CasNavigateur, ServeurPrevo, ServeurStatique, installer_dossier_simule
from jeux_formats import copier_jeu

BOM = b"\xef\xbb\xbf"
NOUVELLES = ["reserves_controle", "garanties", "contrats_prestataires"]       # tables nées au format 4
JEU_COURANT = RACINE / "tests" / "fixtures" / "formats" / "f4-v2.2.0"


def lignes_de_donnees(octets):
    """Lignes d'un CSV après l'en-tête (fichier absent : aucune)."""
    if octets is None:
        return []
    return [ligne for ligne in octets[len(BOM):].split(b"\r\n")[1:] if ligne]


def entete(octets):
    return octets[len(BOM):].split(b"\r\n")[0]


def fichiers_csv(dossier):
    return {chemin.name: chemin.read_bytes() for chemin in sorted(Path(dossier).glob("*.csv"))}


class CasServeur(unittest.TestCase):

    def setUp(self):
        self.temporaire = Path(tempfile.mkdtemp(prefix="prevo-t502-"))
        self.addCleanup(shutil.rmtree, str(self.temporaire), True)

    def lancer(self, source):
        serveur = ServeurPrevo(source=source)
        serveur.demarrer()
        self.addCleanup(serveur.arreter)
        return serveur

    def lancer_jeu(self, jeu):
        return self.lancer(copier_jeu(jeu, self.temporaire / jeu))

    def poster(self, serveur, chemin, corps=None):
        octets = json.dumps(corps).encode("utf-8") if corps is not None else b""
        connexion = http.client.HTTPConnection("127.0.0.1", serveur.port, timeout=30)
        try:
            connexion.request("POST", chemin, body=octets, headers={
                "X-Prevo": "1", "Content-Type": "application/json; charset=utf-8", "Content-Length": str(len(octets))})
            reponse = connexion.getresponse()
            return reponse.status, json.loads(reponse.read().decode("utf-8") or "null")
        finally:
            connexion.close()

    def sauvegardes(self, serveur, fin):
        return sorted(d.name for d in (serveur.dossier / "sauvegardes").iterdir() if d.name.endswith(fin))

    def lire(self, serveur, table):
        chemin = serveur.dossier / (table + ".csv")
        return chemin.read_bytes() if chemin.is_file() else None

    def ajouter_ligne(self, serveur, table):
        """Recopie la dernière ligne de la table à la fin du fichier (une modification « faite depuis »)."""
        octets = self.lire(serveur, table)
        (serveur.dossier / (table + ".csv")).write_bytes(octets + lignes_de_donnees(octets)[-1] + b"\r\n")

    def assert_videe(self, octets, table):
        self.assertIsNotNone(octets, table + ".csv doit rester présent")
        self.assertEqual(lignes_de_donnees(octets), [], table + ".csv doit être vide")
        self.assertEqual(entete(octets), entete((JEU_COURANT / (table + ".csv")).read_bytes()),
                         table + ".csv : en-tête du format courant")


class TestRestaurationAvantFormat4(CasServeur):

    def test_restauration_complete_puis_redemarrage(self):
        serveur = self.lancer_jeu("reserves-a-reprendre")
        avant_format = self.sauvegardes(serveur, "_avant-format-v4")
        self.assertEqual(len(avant_format), 1)
        reserves_du_passage = self.lire(serveur, "reserves_controle")
        self.assertTrue(lignes_de_donnees(reserves_du_passage), "le passage doit avoir repris des réserves")
        self.assertIsNone(self.lire(serveur, "garanties"))
        # Travail fait en 2.2 : une réserve de plus, des garanties et des contrats.
        self.ajouter_ligne(serveur, "reserves_controle")
        for table in ("garanties", "contrats_prestataires"):
            shutil.copyfile(str(JEU_COURANT / (table + ".csv")), str(serveur.dossier / (table + ".csv")))
        en_2_2 = {table: self.lire(serveur, table) for table in NOUVELLES}
        for table in NOUVELLES:
            self.assertTrue(lignes_de_donnees(en_2_2[table]), table)

        statut, resultat = self.poster(serveur, "/api/restauration", {"sauvegarde": avant_format[0]})
        self.assertEqual(statut, 200, resultat)
        self.assertEqual(len(resultat["restaurees"]), 24)
        self.assertEqual(resultat["videes"], NOUVELLES)
        for table in NOUVELLES:
            self.assertNotIn(table, resultat["restaurees"])
            self.assert_videe(self.lire(serveur, table), table)
            copie = serveur.dossier / "sauvegardes" / resultat["copie_securite"] / (table + ".csv")
            self.assertEqual(copie.read_bytes(), en_2_2[table], "copie de sécurité : " + table)
        sauvegarde = serveur.dossier / "sauvegardes" / avant_format[0]
        for nom, octets in fichiers_csv(sauvegarde).items():
            self.assertEqual((serveur.dossier / nom).read_bytes(), octets, nom)

        # Redémarrage : le passage 3 → 4 est rejoué sur les tables vidées.
        copie_des_donnees = self.temporaire / "apres-restauration"
        shutil.copytree(str(serveur.dossier), str(copie_des_donnees))
        serveur.arreter()
        second = self.lancer(copie_des_donnees)
        self.assertEqual(self.lire(second, "reserves_controle"), reserves_du_passage)
        for table in ("garanties", "contrats_prestataires"):
            self.assertEqual(lignes_de_donnees(self.lire(second, table)), [], table)
        self.assertIn(b"version_schema;'4", self.lire(second, "parametres"))


class TestAnnulerUnImport(CasServeur):

    def test_table_touchee_qui_n_existait_pas(self):
        serveur = self.lancer_jeu("f3-v2.1.0")
        self.assertIsNone(self.lire(serveur, "garanties"))
        self.assertIsNone(self.lire(serveur, "contrats_prestataires"))
        statut, reponse = self.poster(serveur, "/api/sauvegarde", {"motif": "avant-import"})
        self.assertEqual(statut, 200, reponse)
        equipements_avant = self.lire(serveur, "equipements")
        # L'import : des équipements en plus, et garanties.csv créé.
        self.ajouter_ligne(serveur, "equipements")
        shutil.copyfile(str(JEU_COURANT / "garanties.csv"), str(serveur.dossier / "garanties.csv"))
        garanties_importees = self.lire(serveur, "garanties")

        # Table absente de la sauvegarde ET de la base : refus, avant toute copie.
        statut, refus = self.poster(serveur, "/api/restauration",
                                    {"sauvegarde": reponse["sauvegarde"], "tables": ["contrats_prestataires"]})
        self.assertEqual(statut, 400, refus)
        self.assertEqual(self.sauvegardes(serveur, "_avant-restauration"), [])

        statut, resultat = self.poster(serveur, "/api/restauration",
                                       {"sauvegarde": reponse["sauvegarde"], "tables": ["equipements", "garanties"]})
        self.assertEqual(statut, 200, resultat)
        self.assertEqual(resultat["restaurees"], ["equipements"])
        self.assertEqual(resultat["videes"], ["garanties"])
        self.assertEqual(self.lire(serveur, "equipements"), equipements_avant)
        self.assert_videe(self.lire(serveur, "garanties"), "garanties")
        copie = serveur.dossier / "sauvegardes" / resultat["copie_securite"]
        self.assertEqual((copie / "garanties.csv").read_bytes(), garanties_importees)


class TestTemoins(CasServeur):

    def test_format_courant_et_une_seule_table(self):
        serveur = self.lancer_jeu("f4-v2.2.0")
        depart = fichiers_csv(serveur.dossier)
        self.assertEqual(len(depart), 27)
        statut, reponse = self.poster(serveur, "/api/sauvegarde")
        self.assertEqual(statut, 200, reponse)
        for table in ("equipements", "garanties", "reserves_controle"):
            self.ajouter_ligne(serveur, table)
        modifie = fichiers_csv(serveur.dossier)

        # Une seule table : elle seule revient.
        statut, resultat = self.poster(serveur, "/api/restauration",
                                       {"sauvegarde": reponse["sauvegarde"], "tables": ["equipements"]})
        self.assertEqual(statut, 200, resultat)
        self.assertEqual((resultat["restaurees"], resultat.get("videes", [])), (["equipements"], []))
        attendu = dict(modifie, **{"equipements.csv": depart["equipements.csv"]})
        self.assertEqual(fichiers_csv(serveur.dossier), attendu)

        # Restauration complète d'une sauvegarde du format courant : tout revient à l'octet, rien n'est vidé.
        statut, resultat = self.poster(serveur, "/api/restauration", {"sauvegarde": reponse["sauvegarde"]})
        self.assertEqual(statut, 200, resultat)
        self.assertEqual(len(resultat["restaurees"]), 27)
        self.assertEqual(resultat.get("videes", []), [])
        self.assertEqual(fichiers_csv(serveur.dossier), depart)


class TestModeDossier(CasNavigateur):
    """Les mêmes règles par js/stockage-dossier.js (dossier simulé dans l'OPFS)."""

    def setUp(self):
        super().setUp()
        self.statique = ServeurStatique(RACINE)
        self.statique.demarrer()
        self.addCleanup(self.statique.arreter)
        installer_dossier_simule(self.contexte, aides_dossier.NOM_DOSSIER_SIMULE)
        self.page.goto(self.statique.url + aides_dossier.PAGE)
        self.page.add_script_tag(content=aides_dossier.AIDE_JS)

    def appeler(self, methode, *arguments):
        return aides_dossier.revenir_en_python(self.page.evaluate(
            "([methode, args]) => aide.appeler(methode, args)", [methode, list(arguments)]))

    def reussir(self, methode, *arguments):
        resultat = self.appeler(methode, *arguments)
        self.assertTrue(resultat["ok"], "%s a échoué : %s" % (methode, resultat))
        return resultat["valeur"]

    def lire_opfs(self, chemin):
        valeur = self.page.evaluate("(c) => aide.lireOpfs(c)", chemin)
        return None if valeur is None else bytes(valeur)

    def ecrire_opfs(self, chemin, octets):
        self.page.evaluate("([c, o]) => aide.ecrireOpfs(c, o)", [chemin, list(octets)])

    def test_tables_absentes_de_la_sauvegarde(self):
        self.page.evaluate("""async () => {
            window.dos = await StockageDossier.creer(await StockageDossier.choisir(), { poste: 'Poste A' });
        }""")
        ancien = RACINE / "tests" / "fixtures" / "formats" / "f3-v2.1.0"
        equipements = (ancien / "equipements.csv").read_bytes()
        parametres = (ancien / "parametres.csv").read_bytes()
        garanties = (JEU_COURANT / "garanties.csv").read_bytes()
        self.ecrire_opfs("equipements.csv", equipements)
        self.ecrire_opfs("parametres.csv", parametres)
        nom = self.reussir("sauvegarder")                      # sauvegarde « d'avant » : sans garanties
        self.ecrire_opfs("garanties.csv", garanties)
        self.ecrire_opfs("equipements.csv", equipements + lignes_de_donnees(equipements)[-1] + b"\r\n")

        # Annulation d'un import : une table demandée n'existait pas avant.
        resultat = self.reussir("restaurer", nom, ["equipements", "garanties"])
        self.assertEqual((resultat["restaurees"], resultat["videes"]), (["equipements"], ["garanties"]))
        self.assertEqual(self.lire_opfs("equipements.csv"), equipements)
        vide = self.lire_opfs("garanties.csv")
        self.assertEqual((entete(vide), lignes_de_donnees(vide)), (entete(garanties), []))
        self.assertEqual(self.lire_opfs("sauvegardes/%s/garanties.csv" % resultat["copieSecurite"]), garanties)
        # Absente de la sauvegarde et de la base : refus (inchangé).
        self.assertFalse(self.appeler("restaurer", nom, ["contrats_prestataires"])["ok"])

        # Restauration complète : la table absente de la sauvegarde est vidée, la copie de sécurité la contient.
        self.ecrire_opfs("garanties.csv", garanties)
        resultat = self.reussir("restaurer", nom)
        self.assertEqual((resultat["restaurees"], resultat["videes"]), (["equipements", "parametres"], ["garanties"]))
        self.assertEqual(lignes_de_donnees(self.lire_opfs("garanties.csv")), [])
        self.assertEqual(self.lire_opfs("sauvegardes/%s/garanties.csv" % resultat["copieSecurite"]), garanties)
        self.assertEqual(self.lire_opfs("parametres.csv"), parametres)

        # Témoin : une seule table présente dans la sauvegarde, rien d'autre ne bouge.
        self.ecrire_opfs("garanties.csv", garanties)
        resultat = self.reussir("restaurer", nom, ["equipements"])
        self.assertEqual((resultat["restaurees"], resultat["videes"]), (["equipements"], []))
        self.assertEqual(self.lire_opfs("garanties.csv"), garanties)


if __name__ == "__main__":
    unittest.main()
