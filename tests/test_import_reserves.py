"""Import des réserves des contrôles depuis un tableur (2.2, lot L6, tâche T489 ; CS170, D183).

Fichier d'essai réel (tests/fixtures/import/reserves.csv, écrit par outils/generer_fixtures_import.py, attentes dans
son LISEZMOI.md) lu par Import.lire dans la page, correspondance automatique (sans mémoire du poste), aperçu
(Import.preparer) sur la démo, puis Import.importer et Import.annuler :
  - type « Réserves des contrôles » : contrôle désigné par l'équipement (repère) et la nature, un contrôle inconnu
    refuse la ligne ; clé naturelle contrôle + date du contrôle + texte (doublon écrit en majuscules) ; TROIS RÉSERVES
    DU TABLEUR DEVIENNENT TROIS LIGNES DE reserves_controle RATTACHÉES AU BON CONTRÔLE ; ligne contrôlée par les règles
    des réserves du L2 (date du contrôle vide ou future, échéance avant le contrôle, levée datée sans commentaire ou
    antérieure au contrôle, réserve levée qui changerait) ; levée sans date : date de levée vide, commentaire de la
    reprise s'il manque (D183) ; « non » avec une date, commentaire sans levée : refusée ;
  - type « Contrôles » (Q8 du tri L2-L6) : la colonne des observations crée des réserves par la règle D183 (une par
    ligne non vide, puces gardées, observations levées → levées sans date, commentaire D183), sur un fichier de trois
    lignes ; une réserve déjà là n'est pas recréée ; la colonne observations du contrôle n'est plus écrite ; réimport :
    rien de nouveau ;
  - ordre d'écriture (réserves après les contrôles), modèle à remplir, écran #/import (type proposé, aperçu).
Page : index.html en file://, démo ; horloge du navigateur fixée à la date de référence de la démo.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_import_reserves.py" -v
"""
import base64
import unittest

from test_import_garanties import ANNULER_JS, APERCU_JS, IMPORTER_JS, MAINTENANT, CasGaranties, octets_b64, par_numero

D183 = "levée avant la 2.2, date inconnue"
GF01 = "Contrôle d'étanchéité du circuit frigorifique (5 à < 50 t éq. CO2)"
RA01 = "Inspection périodique du réservoir d'air comprimé"
PURGEUR = "Purgeur automatique du réservoir défectueux : à remplacer avant la prochaine inspection."


def reserve(identifiant, controle, date, texte, gravite="", echeance="", levee="0", date_levee="", commentaire=""):
    return {"id": identifiant, "controle_id": controle, "date_controle": date, "texte": texte, "gravite": gravite,
            "echeance_levee": echeance, "levee": levee, "date_levee": date_levee, "commentaire_levee": commentaire, "ot_id": ""}


class CasReserves(CasGaranties):

    def apercu_octets(self, type_, nom, octets):
        rendu = self.page.evaluate(APERCU_JS, [type_, nom, base64.b64encode(octets).decode("ascii"), MAINTENANT])
        self.assertTrue(rendu["inchangee"], "l'aperçu n'écrit rien")
        return rendu

    def grille(self, type_, champs, lignes):
        """Aperçu d'une grille sans fichier, chaque colonne au champ de même nom."""
        return self.page.evaluate("""([type, champs, lignes, maintenant]) => {
          const correspondance = champs.map((champ, colonne) => ({ colonne, entete: champ, champ, statut: 'sure', raison: '' }));
          return JSON.parse(JSON.stringify(Import.preparer(type, lignes, correspondance, { maintenant })));
        }""", [type_, champs, lignes, MAINTENANT])

    def reserves_du_controle(self, controle):
        return self.page.evaluate("""(id) => Controles.reservesDuControle(id).map((g) => [g.date_controle,
          g.reserves.map((r) => [r.id, r.texte, r.levee, r.date_levee, r.commentaire_levee])])""", controle)


# ---------------------------------------------------------------------------
# reserves.csv : type « Réserves des contrôles »
# ---------------------------------------------------------------------------

class TestReservesCsv(CasReserves):

    def test_trois_reserves_du_tableur_rattachees_au_bon_controle(self):
        self.ouvrir()
        rendu = self.apercu("reserves", "reserves.csv")
        self.assertEqual(rendu["colonnes"], [
            ["Repère", "equipement", "sure"], ["Nature du contrôle", "nature", "sure"], ["Date du contrôle", "date_controle", "sure"],
            ["Réserve", "texte", "sure"], ["Gravité", "gravite", "sure"], ["Échéance", "echeance_levee", "sure"],
            ["Levée", "levee", "sure"], ["Levée le", "date_levee", "sure"], ["Commentaire", "commentaire_levee", "sure"]])
        apercu = rendu["apercu"]
        attendues = {2: ("identique", "RES-00003"), 3: ("mettre_a_jour", "RES-00001"), 4: ("creer", "RES-00004"),
                     5: ("creer", "RES-00005"), 6: ("creer", "RES-00006")}
        attendues.update({n: ("refusee", "") for n in range(7, 17)})
        self.verifier_actions(apercu, attendues)
        self.verifier_raisons(apercu, {
            7: ["contrôle « Vérification des freins » introuvable", "CH-01"], 8: ["« XX-99 » introuvable"],
            9: ["Commentaire de levée : Décrivez ce qui a été fait"], 10: ["La date du contrôle ne peut pas être dans le futur."],
            11: ["ne peut pas précéder le contrôle du 05/11/2021"], 12: ["Cette réserve est levée : elle ne se modifie plus"],
            13: ["date ou commentaire de levée pour une réserve non levée"], 14: ["doublon dans le fichier, ligne 4"],
            15: ["« grave »", "mineure, majeure, critique"], 16: ["Indiquez la date du contrôle."]})
        lignes = par_numero(apercu)
        self.assertEqual(sorted((c["champ"], c["avant"], c["apres"]) for c in lignes[3]["changements"]),
                         [("commentaire_levee", "", D183), ("gravite", "", "majeure"), ("levee", "0", "1")])
        self.assertEqual(apercu["totaux"], {"lignes": 15, "references": 0, "creer": 3, "mettre_a_jour": 1, "identique": 1,
                                            "refusee": 10})
        ecritures = apercu["ecritures"]
        self.assertEqual(list(ecritures), ["reserves_controle"])
        trois = [
            reserve("RES-00004", "CTR-0005", "2026-03-24", "Raccord du détendeur à resserrer.", "mineure", "2026-04-24"),
            reserve("RES-00005", "CTR-0005", "2026-03-24", "Étiquetage du circuit (fluide, charge) à compléter.", levee="1",
                    date_levee="2026-04-10", commentaire="Étiquette posée par le frigoriste."),
            reserve("RES-00006", "CTR-0001", "2026-02-10", "Fin de course de montée à régler.", "critique", levee="1",
                    commentaire=D183)]
        self.assertEqual(ecritures["reserves_controle"]["creer"], trois)
        self.assertEqual(ecritures["reserves_controle"]["modifier"],
                         [{"id": "RES-00001", "changes": {"gravite": "majeure", "levee": "1", "commentaire_levee": D183}}])
        differentiel = self.fiche("reserves_controle", "RES-00002")

        def verifier(importe):
            self.assertEqual(importe["tables"], ["reserves_controle"])
            self.assertEqual(importe["bilan"], {"reserves_controle": {"crees": 3, "misAJour": 1}})
            self.assertIn(["reserves_controle", "", "import reserves.csv : 3 créé(s), 1 mis à jour"], importe["journal"])
            for attendue in trois:
                self.assertEqual(self.fiche("reserves_controle", attendue["id"]), attendue)
            # Rattachées au bon contrôle : celles de GF-01 groupées sous leur contrôle (ouverte avant levée), celle de PT-01.
            self.assertEqual(self.reserves_du_controle("CTR-0005"), [["2026-03-24", [
                ["RES-00004", "Raccord du détendeur à resserrer.", "0", "", ""],
                ["RES-00005", "Étiquetage du circuit (fluide, charge) à compléter.", "1", "2026-04-10", "Étiquette posée par le frigoriste."]]]])
            self.assertEqual(self.reserves_du_controle("CTR-0001"), [["2026-02-10", [
                ["RES-00006", "Fin de course de montée à régler.", "1", "", D183]]]])
            purgeur = self.fiche("reserves_controle", "RES-00001")
            self.assertEqual([purgeur[c] for c in ("gravite", "levee", "date_levee", "commentaire_levee")], ["majeure", "1", "", D183])
            self.assertEqual(self.fiche("reserves_controle", "RES-00002"), differentiel, "réserve levée intacte")
            etats = self.page.evaluate("""() => ['RES-00004', 'RES-00006'].map((id) =>
              Controles.etatReserve(Donnees.trouver('reserves_controle', id), '2026-10-19').statut)""")
            self.assertEqual(etats, ["en retard", "levée"])
        self.importer_puis_annuler("reserves.csv", verifier)

    def test_levee_et_regles_des_reserves_sur_une_grille(self):
        self.ouvrir()
        champs = ["equipement", "nature", "date_controle", "texte", "levee", "date_levee", "commentaire_levee"]
        apercu = self.grille("reserves", champs, [
            ["GF-01", GF01, "24/03/2026", "Fuite au raccord.", "", "20/03/2026", "Resserré."],
            ["GF-01", GF01, "24/03/2026", "Manomètre hors service.", "", "", "Remplacé."],
            ["AE-01", "Vérification périodique des installations électriques", "12/11/2025",
             "Différentiel 30 mA du tableau de l'atelier à remplacer.", "non", "", ""],
            ["RA-01", RA01, "03/04/2025", PURGEUR, "oui", "01/05/2025", "Purgeur remplacé."],
            ["GF-01", GF01, "24/03/2026", "Isolant de la ligne d'aspiration abîmé.", "oui", "", "Isolant refait."],
            ["ra-01", RA01.upper(), "2025-04-03", PURGEUR.lower(), "", "", ""]])
        lignes = par_numero(apercu)
        self.assertEqual([lignes[n]["action"] for n in range(2, 8)],
                         ["refusee", "refusee", "refusee", "mettre_a_jour", "creer", "refusee"])
        self.assertIn("une levée antérieure est refusée", " ".join(lignes[2]["raisons"]))
        self.assertIn("pour une réserve non levée", " ".join(lignes[3]["raisons"]))
        self.assertIn("Cette réserve est levée", " ".join(lignes[4]["raisons"]))
        self.assertIn("doublon dans le fichier, ligne 5", " ".join(lignes[7]["raisons"]), "clé : casse et accents ignorés")
        ecritures = apercu["ecritures"]["reserves_controle"]
        # Levée datée : sa date et son commentaire, pas celui de la reprise ; levée sans date : commentaire donné gardé.
        self.assertEqual(ecritures["modifier"], [{"id": "RES-00001", "changes": {"levee": "1", "date_levee": "2025-05-01",
                                                                                  "commentaire_levee": "Purgeur remplacé."}}])
        self.assertEqual(ecritures["creer"], [reserve("RES-00004", "CTR-0005", "2026-03-24", "Isolant de la ligne d'aspiration abîmé.",
                                                      levee="1", commentaire="Isolant refait.")])


# ---------------------------------------------------------------------------
# Type « Contrôles » : les observations deviennent des réserves (D183), fichier de trois lignes
# ---------------------------------------------------------------------------

CONTROLES_CSV = ("Équipement;Nature du contrôle;Périodicité (mois);Date du dernier contrôle;Date du prochain contrôle;"
                 "Observations;Observations levées\r\n"
                 "RA-01;" + RA01 + ";;03/04/2025;;\"" + PURGEUR + "\n- Soupape de sûreté à plomber.\";non\r\n"
                 "CU-01;Contrôle des protecteurs;12;14/01/2026;14/01/2027;\"Protecteur de broche fissuré.\n\n  Carter arrière mal fixé.  \";oui\r\n"
                 "PT-01;VGP pont roulant, palan, potence (installés à demeure);;;;;\r\n")


class TestControlesObservations(CasReserves):

    def test_observations_d_un_fichier_de_trois_lignes_deviennent_des_reserves(self):
        self.ouvrir()
        octets = b"\xef\xbb\xbf" + CONTROLES_CSV.encode("utf-8")
        purgeur_avant = self.fiche("controles_reglementaires", "CTR-0004")
        rendu = self.apercu_octets("controles", "controles-observations.csv", octets)
        self.assertEqual([c[1:] for c in rendu["colonnes"]], [["equipement", "sure"], ["nature", "sure"], ["periodicite_mois", "sure"],
                                                              ["derniere_date", "sure"], ["prochaine_date", "sure"],
                                                              ["observations", "sure"], ["observations_levees", "sure"]])
        apercu = rendu["apercu"]
        self.verifier_actions(apercu, {2: ("mettre_a_jour", "CTR-0004"), 3: ("creer", "CTR-0008"), 4: ("identique", "CTR-0001")})
        lignes = par_numero(apercu)
        # Première ligne des observations déjà en réserve (RES-00001) : seule la seconde est ajoutée, puce gardée (D183).
        self.assertEqual([(c["champ"], c["avant"], c["apres"]) for c in lignes[2]["changements"]],
                         [("reserve", "", "- Soupape de sûreté à plomber.")])
        ecritures = apercu["ecritures"]
        self.assertEqual(ecritures["controles_reglementaires"]["modifier"], [], "colonne observations jamais écrite")
        cree = ecritures["controles_reglementaires"]["creer"]
        self.assertEqual([(c["id"], c["equipement_id"], c["observations"], c["observations_levees"]) for c in cree],
                         [("CTR-0008", "EQ-0016", "", "0")])
        attendues = [
            reserve("RES-00004", "CTR-0004", "2025-04-03", "- Soupape de sûreté à plomber."),
            reserve("RES-00005", "CTR-0008", "2026-01-14", "Protecteur de broche fissuré.", levee="1", commentaire=D183),
            reserve("RES-00006", "CTR-0008", "2026-01-14", "Carter arrière mal fixé.", levee="1", commentaire=D183)]
        self.assertEqual(ecritures["reserves_controle"], {"creer": attendues, "modifier": []})

        def verifier(importe):
            self.assertEqual(importe["tables"], ["controles_reglementaires", "reserves_controle"], "réserves après les contrôles")
            self.assertEqual(importe["bilan"], {"controles_reglementaires": {"crees": 1, "misAJour": 0},
                                                "reserves_controle": {"crees": 3, "misAJour": 0}})
            self.assertEqual(self.fiche("controles_reglementaires", "CTR-0004"), purgeur_avant, "observations gardées à l'octet")
            self.assertEqual([r[0] for g in self.reserves_du_controle("CTR-0004") for r in g[1]], ["RES-00001", "RES-00004"])
            self.assertEqual(self.reserves_du_controle("CTR-0008"), [["2026-01-14", [
                ["RES-00005", "Protecteur de broche fissuré.", "1", "", D183], ["RES-00006", "Carter arrière mal fixé.", "1", "", D183]]]])
            # Réimport du même fichier : rien de nouveau (contrôles identiques, réserves déjà là).
            second = self.page.evaluate("() => JSON.parse(JSON.stringify(window.__calculer().totaux))")
            self.assertEqual((second["creer"], second["mettre_a_jour"], second["identique"]), (0, 0, 3))
        self.importer_puis_annuler("controles-observations.csv", verifier)

    def test_sans_mise_a_jour_aucune_reserve_sur_un_controle_existant(self):
        self.ouvrir()
        apercu = self.page.evaluate("""([nature, maintenant]) => {
          const champs = ['equipement', 'nature', 'observations'];
          const correspondance = champs.map((champ, colonne) => ({ colonne, entete: champ, champ, statut: 'sure', raison: '' }));
          return JSON.parse(JSON.stringify(Import.preparer('controles', [['RA-01', nature, 'Nouvelle réserve.']], correspondance,
            { maintenant, mettreAJour: false })));
        }""", [RA01, MAINTENANT])
        self.assertEqual(apercu["lignes"][0]["action"], "identique")
        self.assertEqual(apercu["ecritures"]["reserves_controle"], {"creer": [], "modifier": []})


# ---------------------------------------------------------------------------
# Type, ordre d'écriture, modèle, écran
# ---------------------------------------------------------------------------

class TestTypeEtEcran(CasReserves):

    def test_type_ordre_et_modele(self):
        self.ouvrir()
        rendu = self.page.evaluate("""async () => [Import.TYPES.reserves.libelle, Import.TYPES.reserves.tables,
          Import.TYPES.reserves.champs.filter((c) => c.cleNaturelle).map((c) => c.cle), Import.REGLES.reserves.table,
          Import.TYPES.controles.tables, Import.ORDRE_ECRITURE.indexOf('reserves_controle') > Import.ORDRE_ECRITURE.indexOf('controles_reglementaires'),
          await (await Import.modele('reserves', 'csv')).text()]""")
        self.assertEqual(rendu[:6], ["Réserves des contrôles", ["reserves_controle"], ["equipement", "nature", "date_controle", "texte"],
                                     "reserves_controle", ["controles_reglementaires", "reserves_controle"], True])
        self.assertIn("Équipement;Nature du contrôle;Date du contrôle;Réserve;Gravité;Échéance de levée;Levée;Date de levée;"
                      "Commentaire de levée", rendu[6])
        self.assertIn("GF-01;" + GF01 + ";", rendu[6])

    def test_type_propose_et_apercu_a_l_ecran(self):
        self.ouvrir()
        libelles = self.page.evaluate("""() => Object.fromEntries([...document.querySelectorAll('input[name="import-type"]')]
          .map((e) => [e.value, e.closest('label').querySelector('b').textContent.trim()]))""")
        self.assertEqual(libelles["reserves"], "Réserves des contrôles")
        self.jusqu_a_l_apercu("reserves", fichier="reserves.csv")
        self.attendre_total("creer", 3)
        self.attendre_total("refusee", 10)
        lignes = self.lignes()
        self.assertIn("GF-01", lignes[4]["texte"])
        self.assertIn("24/03/2026", lignes[4]["texte"], "date du contrôle en JJ/MM/AAAA")
        self.assertEqual(lignes[7]["action"], "refusee")
        self.assertIn("Vérification des freins", lignes[7]["texte"])


if __name__ == "__main__":
    unittest.main()
