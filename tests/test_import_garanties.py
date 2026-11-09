"""Import des garanties et des contrats de prestataires depuis un tableur (2.2, lot L6, tâche T487 ; CS173, CS174).

Fichiers d'essai réels (tests/fixtures/import/garanties.csv et contrats.csv, écrits par
outils/generer_fixtures_import.py, attentes dans leur LISEZMOI.md) lus par Import.lire dans la page, correspondance
automatique (Import.correspondance, sans mémoire du poste), aperçu (Import.preparer) sur la démo, puis Import.importer
et Import.annuler :
  - garanties : clé naturelle équipement + date de fin (une 2e garantie du même équipement, autre fin, est créée) ;
    fournisseur par son nom, créé s'il manque (D88 a), jamais pour une ligne refusée seule ; contrôle du formulaire
    (Garanties.verifierGarantie : fin avant le début) ; date impossible, équipement inconnu, doublon du fichier ;
  - contrats : clé prestataire + objet ; équipements concernés en repères séparés par des virgules ou par « ; »,
    écrits en identifiants séparés par « ; » (equipement_ids) ; UN REPÈRE INCONNU REFUSE SA LIGNE ET LES AUTRES
    S'IMPORTENT ; prestataire créé s'il manque, sans refus de Garanties.verifierContrat (« prestataire introuvable »),
    et reconnu en majuscules (doublon) ; montant facultatif, « 2 350,50 » lu 2350.5 ; préavis illisible ; montant
    négatif refusé par le formulaire sur une fiche existante, qui ne change pas ; CS173 sur le contrat importé (fin
    31/12, préavis 3 mois → date limite de résiliation 30/09, « à décider » à l'approche) ;
  - titres reconnus par leurs synonymes (« fin de garantie », « échéance », « préavis », « tacite reconduction »,
    « montant annuel HT », « coût de l'arrêt (€/h) »…) ; colonne cout_arret_h du type Équipements (CS174 : 0 permis,
    négatif refusé par Parc.verifierEquipement, illisible refusé) ;
  - ordre d'écriture (après fournisseurs et équipements) ; l'aperçu n'écrit rien ; annulation : tables à l'octet ;
  - écran #/import : les deux types proposés, aperçu (fiche de la ligne, date de fin en JJ/MM/AAAA, raison du refus,
    référence créée).
Page : index.html en file://, démo ; horloge du navigateur fixée à la date de référence de la démo (la démo n'est pas
décalée : les attentes du LISEZMOI, calculées sur donnees/demo, valent telles quelles).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_import_garanties.py" -v
"""
import base64
import unittest

from test_controles import date_reference
from test_import_ecrans import FIXTURES, CasImport

REFERENCE = date_reference()
HEURE_FIXE = REFERENCE.isoformat() + "T09:30:00"
MAINTENANT = REFERENCE.isoformat() + " 09:30"

# Fichier d'essai lu dans la page, correspondance automatique (sans mémoire), aperçu ; l'état des tables (journal à
# part) est gardé pour vérifier que l'aperçu n'écrit rien et que l'annulation rend tout à l'octet.
APERCU_JS = """async ([type, nom, b64, maintenant]) => {
  const etat = () => JSON.stringify(Object.fromEntries(Object.entries(Donnees.instantane())
    .filter(([n]) => n !== 'journal').map(([n, o]) => [n, Array.from(o).join(',')])));
  window.__avant = etat();
  window.__etat = etat;
  const lu = await Import.lire(new File([Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))], nom));
  const lignes = lu.feuilles[0].lignes;
  const rang = Import.ligneEntete(lignes, type);
  const entetes = Import.entetes(lignes, rang, false);
  const donnees = lignes.slice(rang + 1);
  const correspondance = Import.correspondance(type, entetes, donnees, null);
  const reglages = { mettreAJour: true, numeroPremiereLigne: rang + 2, maintenant };
  window.__calculer = () => Import.preparer(type, donnees, correspondance, reglages);
  const apercu = window.__calculer();
  window.__apercu = apercu;
  return { colonnes: correspondance.map((c) => [c.entete, c.champ, c.statut]), apercu: JSON.parse(JSON.stringify(apercu)),
           inchangee: etat() === window.__avant };
}"""
IMPORTER_JS = """async (nom) => {
  const resultat = await Import.importer(window.__apercu, { nomFichier: nom, recalculer: window.__calculer });
  window.__resultat = resultat;
  await Donnees.rafraichir();
  return { tables: resultat.tablesTouchees, bilan: resultat.tables,
           journal: Donnees.lignes('journal').map((l) => [l.table, l.id_ligne, l.action]) };
}"""
ANNULER_JS = """async () => { await Import.annuler(window.__resultat); return window.__etat() === window.__avant; }"""
FICHE_JS = "([table, id]) => Object.assign({}, Donnees.trouver(table, id))"


def octets_b64(nom):
    return base64.b64encode((FIXTURES / nom).read_bytes()).decode("ascii")


def par_numero(apercu):
    return {ligne["numero"]: ligne for ligne in apercu["lignes"]}


class CasGaranties(CasImport):

    def setUp(self):
        super().setUp()
        self.contexte.clock.set_fixed_time(HEURE_FIXE)

    def ouvrir(self):
        self.ouvrir_demo()

    def apercu(self, type_, nom):
        rendu = self.page.evaluate(APERCU_JS, [type_, nom, octets_b64(nom), MAINTENANT])
        self.assertTrue(rendu["inchangee"], "l'aperçu n'écrit rien")
        return rendu

    def importer_puis_annuler(self, nom, verifier):
        """Import de l'aperçu calculé ; verifier(rendu) avec les tables écrites ; puis annulation à l'octet."""
        rendu = self.page.evaluate(IMPORTER_JS, nom)
        verifier(rendu)
        self.assertTrue(self.page.evaluate(ANNULER_JS), "annulation : tables rendues à l'octet")

    def fiche(self, table, identifiant):
        return self.page.evaluate(FICHE_JS, [table, identifiant])

    def verifier_actions(self, apercu, attendues):
        lignes = par_numero(apercu)
        self.assertEqual({n: (l["action"], l["cible"]) for n, l in lignes.items()}, attendues)

    def verifier_raisons(self, apercu, mots):
        lignes = par_numero(apercu)
        for numero, attendus in mots.items():
            with self.subTest(ligne=numero):
                texte = " ; ".join(lignes[numero]["raisons"])
                for mot in attendus:
                    self.assertIn(mot, texte)


# ---------------------------------------------------------------------------
# garanties.csv
# ---------------------------------------------------------------------------

class TestGaranties(CasGaranties):

    def test_garanties_csv_sur_la_demo(self):
        self.ouvrir()
        rendu = self.apercu("garanties", "garanties.csv")
        self.assertEqual(rendu["colonnes"], [["Repère", "equipement", "sure"], ["Fournisseur", "fournisseur", "sure"],
                                             ["Date de début", "date_debut", "sure"], ["Échéance", "date_fin", "sure"],
                                             ["Ce qui est couvert", "conditions", "sure"]])
        apercu = rendu["apercu"]
        self.verifier_actions(apercu, {
            2: ("identique", "GAR-0001"), 3: ("mettre_a_jour", "GAR-0002"), 4: ("creer", "GAR-0004"),
            5: ("creer", "GAR-0005"), 6: ("creer", "GAR-0006"), 7: ("refusee", ""), 8: ("refusee", ""),
            9: ("refusee", ""), 10: ("refusee", ""), 11: ("refusee", "")})
        self.verifier_raisons(apercu, {
            7: ["XX-99", "introuvable"], 8: ["Fin de garantie obligatoire"],
            9: ["La date de fin ne peut pas précéder la date de début."], 10: ["31/02/2027"],
            11: ["doublon dans le fichier, ligne 4"]})
        lignes = par_numero(apercu)
        self.assertEqual([(c["champ"], c["apres"]) for c in lignes[3]["changements"]],
                         [("conditions", "Garniture mécanique, roulements et main-d'œuvre.")])
        self.assertEqual(apercu["totaux"], {"lignes": 10, "references": 1, "creer": 3, "mettre_a_jour": 1,
                                            "identique": 1, "refusee": 5})
        # Seul le fournisseur d'une ligne gardée est créé (ni « Hydraulique du Guiers » ni « Scies et Lames… »).
        self.assertEqual([(r["table"], r["libelle"], r["id"]) for r in apercu["referencesCreees"]],
                         [("fournisseurs", "Froid Industriel du Dauphiné", "FOU-0006")])
        ecritures = apercu["ecritures"]
        self.assertEqual([f["nom"] for f in ecritures["fournisseurs"]["creer"]], ["Froid Industriel du Dauphiné"])
        self.assertEqual(ecritures["garanties"]["creer"], [
            {"id": "GAR-0004", "equipement_id": "EQ-0007", "fournisseur_id": "FOU-0006", "date_debut": "2026-09-01",
             "date_fin": "2028-08-31", "conditions": "Compresseur frigorifique : pièces et main-d'œuvre, deux ans.",
             "document": "", "actif": "1"},
            {"id": "GAR-0005", "equipement_id": "EQ-0016", "fournisseur_id": "", "date_debut": "", "date_fin": "2027-06-30",
             "conditions": "Garantie constructeur : pièces seules.", "document": "", "actif": "1"},
            {"id": "GAR-0006", "equipement_id": "EQ-0004", "fournisseur_id": "FOU-0005", "date_debut": "2026-07-02",
             "date_fin": "2028-07-01", "conditions": "Pompe remplacée : nouvelle garantie de deux ans.", "document": "",
             "actif": "1"}])
        self.assertEqual(ecritures["garanties"]["modifier"],
                         [{"id": "GAR-0002", "changes": {"conditions": "Garniture mécanique, roulements et main-d'œuvre."}}])

        def verifier(importe):
            self.assertEqual(importe["tables"], ["fournisseurs", "garanties"], "fournisseurs écrits avant les garanties")
            self.assertEqual(importe["bilan"], {"fournisseurs": {"crees": 1, "misAJour": 0},
                                                "garanties": {"crees": 3, "misAJour": 1}})
            self.assertIn(["garanties", "", "import garanties.csv : 3 créé(s), 1 mis à jour"], importe["journal"])
            self.assertEqual(self.fiche("fournisseurs", "FOU-0006")["nom"], "Froid Industriel du Dauphiné")
            self.assertEqual(self.fiche("garanties", "GAR-0002")["conditions"], "Garniture mécanique, roulements et main-d'œuvre.")
            # La garantie importée sert aux règles du module (rappel, carte de la fiche équipement).
            sous = self.page.evaluate("() => { const s = Garanties.sousGarantie('EQ-0007', '2026-10-01');"
                                      " return s && [s.garantie.id, s.fournisseur && s.fournisseur.id]; }")
            self.assertEqual(sous, ["GAR-0004", "FOU-0006"])
        self.importer_puis_annuler("garanties.csv", verifier)


# ---------------------------------------------------------------------------
# contrats.csv
# ---------------------------------------------------------------------------

class TestContrats(CasGaranties):

    def test_contrats_un_repere_inconnu_refuse_sa_ligne_et_les_autres_s_importent(self):
        self.ouvrir()
        rendu = self.apercu("contrats", "contrats.csv")
        self.assertEqual(rendu["colonnes"], [
            ["Prestataire", "prestataire", "sure"], ["Objet", "objet", "sure"], ["Équipements", "equipements_concernes", "sure"],
            ["Début", "date_debut", "sure"], ["Fin", "date_fin", "sure"], ["Préavis", "preavis_mois", "sure"],
            ["Tacite reconduction", "reconduction_tacite", "sure"], ["Montant annuel HT", "montant_annuel", "sure"],
            ["Périmètre", "perimetre", "sure"]])
        apercu = rendu["apercu"]
        self.verifier_actions(apercu, {
            2: ("identique", "CTP-0001"), 3: ("mettre_a_jour", "CTP-0002"), 4: ("creer", "CTP-0005"),
            5: ("creer", "CTP-0006"), 6: ("refusee", ""), 7: ("refusee", ""), 8: ("refusee", ""), 9: ("refusee", ""),
            10: ("refusee", ""), 11: ("refusee", "")})
        self.verifier_raisons(apercu, {
            6: ["équipement « CV-09 » introuvable dans Prévo"], 7: ["Prestataire obligatoire"],
            8: ["« trois »", "n'est pas un nombre entier"], 9: ["Montant : un nombre positif, ou rien."],
            10: ["doublon dans le fichier, ligne 4"], 11: ["La date de fin ne peut pas précéder la date de début."]})
        lignes = par_numero(apercu)
        # Le prestataire créé par l'import n'est pas « introuvable » pour le formulaire.
        self.assertEqual(lignes[4]["raisons"], [])
        self.assertEqual(sorted((c["champ"], c["avant"], c["apres"]) for c in lignes[3]["changements"]),
                         [("date_fin", "2026-06-30", "2027-06-30"), ("montant_annuel", "1250", "1300")])
        self.assertEqual(apercu["totaux"], {"lignes": 10, "references": 1, "creer": 2, "mettre_a_jour": 1,
                                            "identique": 1, "refusee": 6})
        self.assertEqual([(r["table"], r["libelle"], r["id"]) for r in apercu["referencesCreees"]],
                         [("fournisseurs", "Froid Industriel du Dauphiné", "FOU-0006")])
        ecritures = apercu["ecritures"]
        self.assertEqual(ecritures["contrats_prestataires"]["creer"], [
            {"id": "CTP-0005", "fournisseur_id": "FOU-0006", "objet": "Maintenance du groupe froid", "equipement_ids": "EQ-0007",
             "perimetre": "Visite trimestrielle et dépannage sous 24 h.", "date_debut": "2026-01-01", "date_fin": "2026-12-31",
             "preavis_mois": "3", "reconduction_tacite": "1", "reconduction_mois": "", "montant_annuel": "2350.5",
             "document": "", "actif": "1"},
            {"id": "CTP-0006", "fournisseur_id": "FOU-0005", "objet": "Dépannage des pompes",
             "equipement_ids": "EQ-0004;EQ-0005;EQ-0006", "perimetre": "", "date_debut": "2026-03-01", "date_fin": "2027-02-28",
             "preavis_mois": "1", "reconduction_tacite": "0", "reconduction_mois": "", "montant_annuel": "",
             "document": "", "actif": "1"}])
        self.assertEqual(ecritures["contrats_prestataires"]["modifier"],
                         [{"id": "CTP-0002", "changes": {"date_fin": "2027-06-30", "montant_annuel": "1300"}}])
        avant_chaines = self.fiche("contrats_prestataires", "CTP-0004")

        def verifier(importe):
            self.assertEqual(importe["tables"], ["fournisseurs", "contrats_prestataires"])
            self.assertEqual(importe["bilan"], {"fournisseurs": {"crees": 1, "misAJour": 0},
                                                "contrats_prestataires": {"crees": 2, "misAJour": 1}})
            self.assertEqual(self.fiche("contrats_prestataires", "CTP-0004"), avant_chaines, "fiche du refus intacte")
            self.assertIsNone(self.page.evaluate("() => Donnees.lignes('fournisseurs').find((f) => f.nom === 'Hydraulique du Guiers') || null"))
            # CS173 sur le contrat importé : fin 31/12/2026, préavis 3 mois, reconduction tacite → date limite 30/09/2026.
            etat = self.page.evaluate("""() => { const c = Donnees.trouver('contrats_prestataires', 'CTP-0005');
              const e = Garanties.etatContrat(c, '2026-08-15', 60);
              return [Garanties.dateLimiteResiliation(c), e.statut, Garanties.equipementsDuContrat(Donnees.trouver('contrats_prestataires', 'CTP-0006')),
                      Garanties.contratsDeLEquipement('EQ-0005').map((x) => x.id).sort()]; }""")
            self.assertEqual(etat, ["2026-09-30", "a_decider", ["EQ-0004", "EQ-0005", "EQ-0006"], ["CTP-0003", "CTP-0006"]])
        self.importer_puis_annuler("contrats.csv", verifier)

    def test_prestataire_nouveau_et_repere_seul_dans_une_grille(self):
        # Sans fichier : virgules, « ; », espaces et doublons dans la liste des repères ; liste vide = rien d'effacé.
        self.ouvrir()
        apercu = self.page.evaluate("""() => {
          const entetes = ['prestataire', 'objet', 'equipements_concernes', 'date_fin'];
          const correspondance = entetes.map((champ, colonne) => ({ colonne, entete: champ, champ, statut: 'sure', raison: '' }));
          return JSON.parse(JSON.stringify(Import.preparer('contrats', [
            ['Nouveau Prestataire', 'Contrat A', ' GF-01 ;CP-01,, gf-01 ', '31/12/2026'],
            ['Fluidalpes Services', 'Maintenance préventive des compresseurs', ' , ', ''],
            ['Fluidalpes Services', 'Contrat B', 'CP-01, XX-01, YY-02', '31/12/2026']], correspondance, { maintenant: '2026-10-19 09:30' })));
        }""")
        lignes = par_numero(apercu)
        self.assertEqual([lignes[n]["action"] for n in (2, 3, 4)], ["creer", "identique", "refusee"])
        self.assertEqual(apercu["ecritures"]["contrats_prestataires"]["creer"][0]["equipement_ids"], "EQ-0007;EQ-0001")
        self.assertEqual(apercu["ecritures"]["contrats_prestataires"]["modifier"], [])
        raisons = " ; ".join(lignes[4]["raisons"])
        self.assertIn("« XX-01 »", raisons)
        self.assertIn("« YY-02 »", raisons)


# ---------------------------------------------------------------------------
# Titres reconnus, coût d'une heure d'arrêt (type Équipements), ordre d'écriture, écran
# ---------------------------------------------------------------------------

CORRESPONDANCE_JS = """([type, entetes, exemple]) => Import.correspondance(type, entetes, [exemple], null)
  .map((c) => [c.entete, c.champ, c.statut])"""


class TestTitresEtEquipements(CasGaranties):

    def test_synonymes_des_titres(self):
        self.ouvrir()
        cas = [
            ("garanties", ["Code machine", "Fin de garantie", "Début de garantie", "Garant", "Conditions de garantie"],
             ["CP-01", "31/12/2027", "01/01/2026", "Fluidalpes Services", "Pièces"],
             ["equipement", "date_fin", "date_debut", "fournisseur", "conditions"]),
            ("garanties", ["Machine", "Garantie jusqu'au", "Fournisseur"], ["CP-01", "31/12/2027", "Fluidalpes Services"],
             ["equipement", "date_fin", "fournisseur"]),
            ("contrats", ["Fournisseur", "Intitulé du contrat", "Repères", "Date de début", "Échéance", "Préavis (mois)",
                          "Tacite reconduction", "Durée de reconduction", "Montant annuel HT", "Périmètre"],
             ["Fluidalpes Services", "Contrat", "CP-01", "01/01/2026", "31/12/2026", "3", "oui", "12", "1 200,00", "Atelier"],
             ["prestataire", "objet", "equipements_concernes", "date_debut", "date_fin", "preavis_mois",
              "reconduction_tacite", "reconduction_mois", "montant_annuel", "perimetre"]),
            ("contrats", ["Prestataire", "Objet du contrat", "Équipements concernés", "Préavis de résiliation (mois)",
                          "Reconduction tacite", "Montant annuel (€ HT)"],
             ["Fluidalpes Services", "Contrat", "CP-01", "3", "non", "4800"],
             ["prestataire", "objet", "equipements_concernes", "preavis_mois", "reconduction_tacite", "montant_annuel"]),
        ]
        for titre in ("Coût de l'arrêt (€/h)", "Coût horaire d'arrêt", "Coût d'arrêt", "Perte de production horaire",
                      "Coût d'une heure d'arrêt (€/h)"):
            cas.append(("equipements", ["Repère", titre], ["CP-01", "850"], ["repere", "cout_arret_h"]))
        for type_, entetes, exemple, champs in cas:
            with self.subTest(type=type_, entetes=entetes):
                obtenu = self.page.evaluate(CORRESPONDANCE_JS, [type_, entetes, exemple])
                self.assertEqual(obtenu, [[e, c, "sure"] for e, c in zip(entetes, champs)])

    def test_cout_d_une_heure_d_arret_dans_le_type_equipements(self):
        self.ouvrir()
        champ = self.page.evaluate("() => { const c = Import.TYPES.equipements.champs.find((x) => x.cle === 'cout_arret_h');"
                                   " return c && [c.table, c.champ, c.type, c.libelle, c.obligatoire, c.exemple]; }")
        self.assertEqual(champ, ["equipements", "cout_arret_h", "decimal", "Coût d'une heure d'arrêt (€/h)", False, "850"])
        avant = {r: self.page.evaluate("(r) => Donnees.lignes('equipements').find((e) => e.repere === r).cout_arret_h", r)
                 for r in ("CP-01", "AE-02", "CU-01.CH")}
        self.assertEqual(avant, {"CP-01": "850", "AE-02": "", "CU-01.CH": ""})
        apercu = self.page.evaluate("""() => {
          const correspondance = [{ colonne: 0, entete: 'Repère', champ: 'repere', statut: 'sure' },
                                  { colonne: 1, entete: 'Coût', champ: 'cout_arret_h', statut: 'sure' }];
          const apercu = Import.preparer('equipements', [['CP-01', '900'], ['AE-02', '120,50'], ['CN-01', '-10'], ['CU-01', 'abc'],
            ['CU-01.CH', '0']], correspondance, { maintenant: '2026-10-19 09:30' });
          window.__apercu = apercu;
          window.__calculer = () => apercu;
          const etat = () => JSON.stringify(Object.fromEntries(Object.entries(Donnees.instantane())
            .filter(([n]) => n !== 'journal').map(([n, o]) => [n, Array.from(o).join(',')])));
          window.__avant = etat();
          window.__etat = etat;
          return JSON.parse(JSON.stringify(apercu));
        }""")
        lignes = par_numero(apercu)
        self.assertEqual([lignes[n]["action"] for n in range(2, 7)],
                         ["mettre_a_jour", "mettre_a_jour", "refusee", "refusee", "mettre_a_jour"])
        self.assertIn("Saisissez un montant positif ou nul, au centime", " ".join(lignes[4]["raisons"]))
        self.assertIn("« abc »", " ".join(lignes[5]["raisons"]))
        self.assertEqual(sorted((m["id"], m["changes"]["cout_arret_h"]) for m in apercu["ecritures"]["equipements"]["modifier"]),
                         [("EQ-0001", "900"), ("EQ-0011", "120.5"), ("EQ-0017", "0")])

        def verifier(importe):
            self.assertEqual(importe["bilan"], {"equipements": {"crees": 0, "misAJour": 3}})
            self.assertEqual(self.fiche("equipements", "EQ-0011")["cout_arret_h"], "120.5")
        self.importer_puis_annuler("tableur", verifier)

    def test_ordre_d_ecriture_types_et_modeles(self):
        self.ouvrir()
        ordre = self.page.evaluate("() => Import.ORDRE_ECRITURE")
        for table in ("garanties", "contrats_prestataires"):
            self.assertGreater(ordre.index(table), ordre.index("fournisseurs"))
            self.assertGreater(ordre.index(table), ordre.index("equipements"))
        types = self.page.evaluate("""() => ['garanties', 'contrats'].map((t) => [Import.TYPES[t].libelle, Import.TYPES[t].tables,
          Import.TYPES[t].champs.filter((c) => c.cleNaturelle).map((c) => c.cle), Import.REGLES[t].table, Import.nomModele(t, 'csv')])""")
        self.assertEqual(types, [
            ["Garanties", ["fournisseurs", "garanties"], ["equipement", "date_fin"], "garanties", "prevo-modele-garanties.csv"],
            ["Contrats de prestataires", ["fournisseurs", "contrats_prestataires"], ["prestataire", "objet"], "contrats_prestataires",
             "prevo-modele-contrats.csv"]])
        # Modèle .csv des contrats : titres en libellés et ligne d'exemple valable sur la démo (montant dans la devise).
        modele = self.page.evaluate("async () => (await (await Import.modele('contrats', 'csv')).text())")
        self.assertIn("Prestataire;Objet du contrat;Équipements concernés;", modele)
        self.assertIn("Montant annuel (€ HT)", modele)
        self.assertIn("Fluidalpes Services;Maintenance du groupe froid;GF-01, CP-01;", modele)


class TestEcran(CasGaranties):

    def test_types_proposes_et_apercu_a_l_ecran(self):
        self.ouvrir()
        libelles = self.page.evaluate("""() => Object.fromEntries([...document.querySelectorAll('input[name="import-type"]')]
          .map((e) => [e.value, e.closest('label').querySelector('b').textContent.trim()]))""")
        self.assertEqual(libelles["garanties"], "Garanties")
        self.assertEqual(libelles["contrats"], "Contrats de prestataires")
        self.jusqu_a_l_apercu("contrats", fichier="contrats.csv")
        self.attendre_total("refusee", 6)
        lignes = self.lignes()
        self.assertEqual(lignes[6]["action"], "refusee")
        self.assertIn("CV-09", lignes[6]["texte"])
        self.assertIn("Froid Industriel du Dauphiné", lignes[4]["texte"])
        self.assertIn("Maintenance du groupe froid", lignes[4]["texte"])
        self.assertIn("Froid Industriel du Dauphiné", self.page.inner_text("#contenu"))
        self.retour(3)
        self.retour(2)
        self.retour(1)
        self.choisir_type("garanties")
        self.deposer("garanties.csv")
        self.continuer(3)
        self.continuer(4)
        self.attendre_total("creer", 3)
        lignes = self.lignes()
        self.assertIn("31/08/2028", lignes[4]["texte"], "date de fin en JJ/MM/AAAA")
        self.assertIn("GF-01", lignes[4]["texte"])


if __name__ == "__main__":
    unittest.main()
