"""Trois écarts de la garde « fichier abîmé » sur la 2.0 (chantier i18n-socle, tâche T204), relevés par le correctif
1.2.1 (même garde, faite sur la 1.2) :
    1. TestParametresAbimeFormatAncienDossier (navigateur) : mode dossier, parametres.csv abîmé (une valeur au-delà de
       l'en-tête) dans une base au format 2 (jeu f2-v1.1.0, version_schema 2). Le passage au format courant est
       impossible (version_schema ne peut pas être écrite) : il est refusé AVANT la sauvegarde « avant-format », donc
       rien n'est écrit ; deux ouvertures de suite → aucune sauvegarde « avant-format », CSV identiques à l'octet,
       l'application s'ouvre avec UN seul bandeau « Fichier abîmé » qui nomme parametres.csv (pas de bandeau « Les
       fichiers n'ont pas pu passer au format » en plus).
    2. TestCelluleLongueServeur (sans navigateur) : un fichier sain dont une cellule a 200 000 caractères (plus que
       la limite par défaut du module csv, 131 072) n'est pas un fichier abîmé : raisons_fichier_abime vide, PUT 200.
    3. TestSauvegardeDuJourAvantGardeDossier (navigateur) : mode dossier. T204 disait « garde AVANT la sauvegarde du
       jour : un refus n'écrit rien, pas même la sauvegarde » ; inversé par T206 (règle de Nicolas : un fichier abîmé
       bloque l'écriture, jamais la sauvegarde quotidienne) : un refus de enregistrer et de ajouter fait la sauvegarde
       du jour si elle manque (jour sans sauvegarde au départ), les CSV abîmés y sont marqués « abime » dans le
       manifeste, et les CSV des données restent identiques à l'octet.

Règle numéro un : jamais de données réelles (copies des jeux de tests/fixtures/formats/ dans des dossiers temporaires,
ou dans l'OPFS du navigateur de test).

Lancer depuis la racine du projet (à travers le verrou du navigateur) :
    py -X utf8 -m unittest discover -s tests -p "test_garde_abime_ecarts.py" -v
"""
import json
import re
import unittest

from commun import RACINE as SERVEUR_RACINE, ServeurPrevo
from test_garde_abime_navigateur import AJOUTER_DIRECT_JS, ENREGISTRER_DIRECT_JS, avec_ligne_coupee
from test_garde_abime_serveur import SERVEUR, CasCopies, ecrire_tableau, lire_tableau, requete, version_de
from test_recette_socle import MOTIF_QUOTIDIENNE, CasRecetteSocle, csv_de_la_racine, fichiers_du_jeu, sauvegardes

MOTIF_AVANT_FORMAT = re.compile(r"_avant-format-v\d+$")
LIGNE_EN_TROP = b"cle_maison;valeur;en trop\r\n"          # une valeur au-delà de l'en-tête (cle;valeur) : abîmé
TEXTES_BANDEAUX_JS = """() => Array.from(document.querySelectorAll('#alertes-app > *'))
  .map((e) => e.textContent.replace(/\\s+/g, ' ').trim())"""
LONGUEUR = 200000                                         # > 131 072, limite par défaut de csv.field_size_limit


# ---------------------------------------------------------------------------
# 1. parametres.csv abîmé dans une base au format 2 (mode dossier)
# ---------------------------------------------------------------------------

class TestParametresAbimeFormatAncienDossier(CasRecetteSocle):

    def setUp(self):
        super().setUp()
        self.demarrer_statique()

    def verifier_ouverture(self, origine, numero):
        self.assertIn("parametres", self.page.evaluate("Donnees.tablesAbimees()"))
        apres = self.instantane()
        avant_format = sorted(nom for nom in sauvegardes(apres) if MOTIF_AVANT_FORMAT.search(nom))
        self.assertEqual(avant_format, [], "ouverture %d : sauvegarde « avant-format » faite alors que le passage est "
                                           "impossible (parametres.csv abîmé)" % numero)
        self.page.wait_for_function("() => (%s)().some((t) => t.includes('abîmé'))" % TEXTES_BANDEAUX_JS, timeout=5000)
        bandeaux = self.page.evaluate(TEXTES_BANDEAUX_JS)
        self.assertEqual([t for t in bandeaux if "pas pu passer au format" in t], [], bandeaux)
        abimes = [t for t in bandeaux if "abîmé" in t]
        self.assertEqual(len(abimes), 1, abimes)
        self.assertIn("Fichier abîmé : parametres.csv, repéré aujourd'hui.", abimes[0])
        self.assertEqual(csv_de_la_racine(apres), csv_de_la_racine(origine),
                         "ouverture %d : un CSV a été réécrit" % numero)

    def test_parametres_abime_format_2_deux_ouvertures_rien_d_ecrit(self):
        origine = fichiers_du_jeu("f2-v1.1.0")
        self.assertTrue(origine["parametres.csv"].endswith(b"version_schema;'2\r\n"))
        origine["parametres.csv"] += LIGNE_EN_TROP
        self.ouvrir_dossier(origine, "responsable")
        self.verifier_ouverture(origine, 1)
        self.rouvrir_dossier()
        self.verifier_ouverture(origine, 2)


# ---------------------------------------------------------------------------
# 2. Cellule de plus de 131 072 caractères (serveur)
# ---------------------------------------------------------------------------

class TestCelluleLongueServeur(CasCopies):

    def avec_cellule_longue(self, octets, lettre):
        entete, lignes = lire_tableau(octets)
        lignes[0][entete.index("travail_a_faire")] = lettre * LONGUEUR
        return ecrire_tableau(entete, lignes)

    def test_cellule_de_200000_caracteres_fichier_sain_put_accepte(self):
        source = self.jeu("f3-v1.2.0")
        chemin_source = source / "ordres_travail.csv"
        long_a = self.avec_cellule_longue(chemin_source.read_bytes(), "a")
        long_b = self.avec_cellule_longue(chemin_source.read_bytes(), "b")
        self.assertEqual(SERVEUR.raisons_fichier_abime(long_a), [])
        chemin_source.write_bytes(long_a)
        with ServeurPrevo(source=source) as serveur:
            chemin = serveur.dossier / "ordres_travail.csv"
            self.assertEqual(chemin.read_bytes(), long_a)
            statut, reponse = requete(serveur, "PUT", "/api/csv/ordres_travail", long_b,
                                      {"X-Version-Attendue": version_de(long_a)})
            self.assertEqual(statut, 200, reponse)
            self.assertEqual(chemin.read_bytes(), long_b)

    def test_limite_des_cellules_egale_a_celle_d_un_csv_de_l_import_zip(self):
        """T207 (Nicolas) : la limite relevée est de 10 Mo, celle d'un CSV dans l'import ZIP (LIMITES.racine de
        js/modules/zip-lecture.js), et non sans limite ; elle est bien celle du module csv."""
        texte = (SERVEUR_RACINE / "js" / "modules" / "zip-lecture.js").read_text(encoding="utf-8")
        mo = re.search(r"^\s*racine: (\d+) \* MO,", texte, re.M)
        self.assertIsNotNone(mo, "LIMITES.racine introuvable dans zip-lecture.js")
        self.assertEqual(SERVEUR.TAILLE_MAX_CELLULE_CSV, int(mo.group(1)) * 1024 * 1024)
        self.assertEqual(SERVEUR.csv.field_size_limit(), SERVEUR.TAILLE_MAX_CELLULE_CSV)


# ---------------------------------------------------------------------------
# 3. Sauvegarde du jour avant la garde (mode dossier ; T204 inversé par T206)
# ---------------------------------------------------------------------------

class TestSauvegardeDuJourAvantGardeDossier(CasRecetteSocle):

    def setUp(self):
        super().setUp()
        self.demarrer_statique()

    def sauvegardes_du_jour(self):
        return sorted(nom for nom in sauvegardes(self.instantane()) if MOTIF_QUOTIDIENNE.match(nom))

    def test_refus_sur_fichier_abime_fait_la_sauvegarde_du_jour(self):
        origine = fichiers_du_jeu("entete-tronque")                  # ordres_travail.csv abîmé
        origine["journal.csv"] = avec_ligne_coupee(origine["journal.csv"])
        self.ouvrir_dossier(origine, "demandeur")
        self.assertEqual(self.sauvegardes_du_jour(), [], "jour déjà sauvegardé au départ")
        refus = {"enregistrer": self.page.evaluate(ENREGISTRER_DIRECT_JS, ["ordres_travail", None]),
                 "ajouter": self.page.evaluate(AJOUTER_DIRECT_JS)}
        for appel, resultat in refus.items():
            with self.subTest(appel=appel):
                self.assertFalse(resultat["ok"], resultat)
                self.assertTrue(resultat["abime"], resultat)
        jours = self.sauvegardes_du_jour()
        self.assertEqual(len(jours), 1, "une sauvegarde du jour attendue malgré le refus (T206) : %r" % jours)
        apres = self.instantane()
        manifeste = json.loads(sauvegardes(apres)[jours[0]]["manifeste.json"].decode("utf-8"))
        marques = sorted(f["nom"] for f in manifeste["fichiers"] if f.get("abime") is True)
        self.assertEqual(marques, ["journal.csv", "ordres_travail.csv"])
        self.assertEqual(csv_de_la_racine(apres), csv_de_la_racine(origine))


if __name__ == "__main__":
    unittest.main()
