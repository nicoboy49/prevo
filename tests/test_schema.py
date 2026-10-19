"""Tests de js/schema.js : conformité au brief §6 et à ARCHITECTURE.md §4.

Le schéma est chargé dans Chromium (page-vide.html en file://) puis lu avec JSON.stringify(Schema).
Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_schema.py" -v
"""
import json
import re
import unittest

from commun import RACINE, CasNavigateur, charger_scripts

# ---------------------------------------------------------------------------
# Lecture du tableau §6 du brief
# ---------------------------------------------------------------------------


def lire_tableau_brief():
    """Retourne {nom_de_table: {'champs': [noms…], 'parentheses': {champ: 'texte entre parenthèses'}}}.

    Chaque ligne du tableau est `| `table.csv` | champs… |`. Les parenthèses (valeurs d'une liste,
    exemples) sont retirées avant de découper sur les virgules ; ce qui suit « — » est un
    commentaire. Le tableau commence après le titre « 6. Modèle de données ».
    """
    texte = (RACINE / "brief-gmao.md").read_text(encoding="utf-8")
    debut = texte.index("## 6. Modèle de données")
    fin = texte.index("## 7.", debut)
    tables = {}
    for ligne in texte[debut:fin].splitlines():
        correspondance = re.match(r"^\|\s*`([a-z_]+)\.csv`\s*\|(.*)\|\s*$", ligne)
        if not correspondance:
            continue
        nom_table, cellule = correspondance.group(1), correspondance.group(2)
        cellule = cellule.split(" — ")[0]
        parentheses = {}
        champs = []
        # on découpe en « segments » séparés par des virgules situées hors parenthèses
        profondeur, courant, segments = 0, "", []
        for caractere in cellule:
            if caractere == "(":
                profondeur += 1
            elif caractere == ")":
                profondeur -= 1
            if caractere == "," and profondeur == 0:
                segments.append(courant)
                courant = ""
            else:
                courant += caractere
        segments.append(courant)
        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue
            nom_champ = re.split(r"\s", segment, maxsplit=1)[0]
            champs.append(nom_champ)
            interieur = re.search(r"\((.*)\)", segment)
            if interieur:
                parentheses[nom_champ] = interieur.group(1)
        tables[nom_table] = {"champs": champs, "parentheses": parentheses}
    return tables


# ---------------------------------------------------------------------------
# Attendus (ARCHITECTURE.md §4 et consignes de la tâche T03)
# ---------------------------------------------------------------------------

TYPES_CONNUS = {"id", "texte", "texte_long", "entier", "decimal", "date", "date_heure",
                "booleen", "choix", "ref", "document"}

IDENTIFIANTS_ATTENDUS = {
    "localisations": ("LOC-", 4, False), "equipements": ("EQ-", 4, False),
    "demandes": ("DI-", 4, True), "ordres_travail": ("OT-", 4, True),
    "ot_operations": ("OTO-", 6, False), "ot_pieces": ("OTP-", 6, False),
    "ot_temps": ("OTT-", 6, False), "gammes": ("GAM-", 4, False),
    "gamme_operations": ("GOP-", 6, False), "fournisseurs": ("FOU-", 4, False),
    "articles": ("ART-", 4, False), "article_equipement": ("AEQ-", 5, False),
    "mouvements_stock": ("MVT-", 6, False), "techniciens": ("TEC-", 4, False),
    "habilitations": ("HAB-", 4, False), "compteurs": ("CPT-", 4, False),
    "releves": ("REL-", 6, False), "controles_reglementaires": ("CTR-", 4, False),
    "codes_defaillance": ("CD-", 4, False), "achats": ("ACH-", 4, False),
}

CHAMPS_PROTEGES = {
    ("equipements", "num_serie"), ("equipements", "repere"),
    ("articles", "reference"), ("articles", "ref_fabricant"), ("fournisseurs", "telephone"),
}

OBLIGATOIRES = {
    ("equipements", "repere"), ("equipements", "designation"),
    ("demandes", "equipement_id"), ("demandes", "symptome"), ("demandes", "impact"),
    ("ordres_travail", "equipement_id"), ("ordres_travail", "titre"), ("ordres_travail", "type"),
    ("ordres_travail", "priorite"), ("ordres_travail", "statut"),
    ("articles", "reference"), ("articles", "designation"),
    ("techniciens", "nom"),
    ("codes_defaillance", "famille"), ("codes_defaillance", "code"), ("codes_defaillance", "libelle"),
    ("localisations", "libelle"), ("localisations", "type"),
}

# Valeurs canoniques des listes : (table, champ) -> valeurs, accents compris
VALEURS_CANONIQUES = {
    ("demandes", "statut"): ["Nouvelle", "Acceptée", "Regroupée", "Différée", "Refusée"],
    ("demandes", "impact"): ["sécurité", "arrêt", "dégradé", "gêne"],
    ("ordres_travail", "statut"): ["Créé", "Préparé", "Planifié", "En cours", "En attente",
                                   "Clôturé techniquement", "Clôturé administrativement", "Annulé"],
    ("ordres_travail", "origine"): ["DI", "préventif", "urgence", "manuel"],
    ("ordres_travail", "type"): ["correctif immédiat", "correctif différé", "préventif systématique",
                                 "préventif conditionnel", "amélioration", "réglementaire"],
    ("ordres_travail", "priorite"): ["P1", "P2", "P3", "P4"],
    ("equipements", "statut"): ["en service", "arrêt", "rebut"],
    ("equipements", "criticite"): ["A", "B", "C"],
    ("localisations", "type"): ["site", "atelier", "ligne"],
    ("codes_defaillance", "famille"): ["symptôme", "cause", "remède"],
    ("mouvements_stock", "type"): ["entrée", "sortie", "inventaire", "retour"],
    ("achats", "statut"): ["demandée", "commandée", "reçue"],
    ("gammes", "declencheur"): ["date", "compteur", "seuil"],
}

# Tous les champs « choix » du schéma doivent figurer ci-dessus (et inversement)
TYPES_PAR_NOM = {
    "date": ["date_mes", "date_prevue", "derniere_realisation", "prochaine_echeance",
             "date_obtention", "date_echeance", "derniere_date", "prochaine_date",
             "date_reception"],
    "date_heure": ["date_decision", "date_creation", "date_debut", "date_fin",
                   "date_cloture_tech", "date_cloture_admin"],
    "booleen": ["actif", "arret_production", "remise_service", "fait", "critique",
                "observations_levees"],
    "entier": ["ordre", "delai_jours", "periodicite_jours", "avance_jours", "periodicite_mois"],
    "decimal": ["heures_fonct_jour", "temps_prevu_h", "duree_arret_h", "cout_soustraitance",
                "quantite", "quantite_prevue", "heures", "stock", "stock_securite",
                "point_commande", "qte_commande", "prix_unitaire", "taux_horaire",
                "capacite_h_semaine", "periodicite_unites", "seuil",
                "releve_derniere_realisation", "valeur"],
    "texte_long": ["description", "travail_a_faire", "consignes", "compte_rendu", "consignation",
                   "observations", "commentaire", "motif_decision", "motif_attente",
                   "motif_annulation"],
    "document": [],
}

# Types qui dépendent de la table (même nom de champ, types différents)
TYPES_PAR_TABLE_ET_NOM = {
    ("ot_temps", "date"): "date", ("releves", "date"): "date", ("achats", "date"): "date",
    ("demandes", "date_heure"): "date_heure", ("mouvements_stock", "date"): "date_heure",
    ("journal", "date_heure"): "date_heure",
    ("demandes", "symptome"): "texte_long",
    # releves.valeur est un nombre ; parametres.valeur est un texte (ex. « prochain arrêt »)
    ("releves", "valeur"): "decimal", ("parametres", "valeur"): "texte",
    ("equipements", "document"): "document", ("demandes", "photo"): "document",
    ("controles_reglementaires", "rapport"): "document",
    ("journal", "id_ligne"): "texte", ("journal", "table"): "texte",
}

# Références : (table, champ) -> (table visée, champCible, filtre)
REFERENCES_ATTENDUES = {
    ("localisations", "parent_id"): ("localisations", None, None),
    ("equipements", "parent_id"): ("equipements", None, None),
    ("equipements", "localisation_id"): ("localisations", None, None),
    ("demandes", "equipement_id"): ("equipements", None, None),
    ("demandes", "ot_id"): ("ordres_travail", None, None),
    ("ordres_travail", "di_id"): ("demandes", None, None),
    ("ordres_travail", "gamme_id"): ("gammes", None, None),
    ("ordres_travail", "equipement_id"): ("equipements", None, None),
    ("ordres_travail", "technicien_id"): ("techniciens", None, None),
    ("ordres_travail", "ot_lie_id"): ("ordres_travail", None, None),
    ("ordres_travail", "symptome_code"): ("codes_defaillance", "code", {"famille": "symptôme"}),
    ("ordres_travail", "cause_code"): ("codes_defaillance", "code", {"famille": "cause"}),
    ("ordres_travail", "remede_code"): ("codes_defaillance", "code", {"famille": "remède"}),
    ("ot_operations", "ot_id"): ("ordres_travail", None, None),
    ("ot_pieces", "ot_id"): ("ordres_travail", None, None),
    ("ot_pieces", "article_id"): ("articles", None, None),
    ("ot_temps", "ot_id"): ("ordres_travail", None, None),
    ("ot_temps", "technicien_id"): ("techniciens", None, None),
    ("gammes", "equipement_id"): ("equipements", None, None),
    ("gammes", "compteur_id"): ("compteurs", None, None),
    ("gamme_operations", "gamme_id"): ("gammes", None, None),
    ("articles", "fournisseur_id"): ("fournisseurs", None, None),
    ("article_equipement", "article_id"): ("articles", None, None),
    ("article_equipement", "equipement_id"): ("equipements", None, None),
    ("mouvements_stock", "article_id"): ("articles", None, None),
    ("mouvements_stock", "ot_id"): ("ordres_travail", None, None),
    ("habilitations", "technicien_id"): ("techniciens", None, None),
    ("compteurs", "equipement_id"): ("equipements", None, None),
    ("releves", "compteur_id"): ("compteurs", None, None),
    ("controles_reglementaires", "equipement_id"): ("equipements", None, None),
    ("achats", "article_id"): ("articles", None, None),
    ("achats", "fournisseur_id"): ("fournisseurs", None, None),
}


class TestSchema(CasNavigateur):
    """Vérifie le contenu de Schema, tel que le voit le navigateur."""

    def setUp(self):
        super().setUp()
        charger_scripts(self.page, ["js/schema.js"])
        self.schema = json.loads(self.page.evaluate("JSON.stringify(Schema)"))
        self.tables = self.schema["tables"]
        self.brief = lire_tableau_brief()

    def champs_de(self, nom_table):
        return {c["nom"]: c for c in self.tables[nom_table]["champs"]}

    def tous_les_champs(self):
        """Itère sur (nom de table, champ) pour les 22 tables."""
        for nom_table, table in self.tables.items():
            for champ in table["champs"]:
                yield nom_table, champ

    # -- structure générale ---------------------------------------------------

    def test_le_brief_decrit_22_tables(self):
        self.assertEqual(len(self.brief), 22)

    def test_22_tables_dans_l_ordre_du_brief(self):
        self.assertEqual(list(self.tables.keys()), list(self.brief.keys()))
        self.assertEqual(len(self.tables), 22)
        self.assertEqual(self.page.evaluate("Schema.nomsTables()"), list(self.brief.keys()))

    def test_champs_identiques_au_brief_et_dans_le_meme_ordre(self):
        for nom_table, attendu in self.brief.items():
            with self.subTest(table=nom_table):
                noms = [c["nom"] for c in self.tables[nom_table]["champs"]]
                self.assertEqual(noms, attendu["champs"])

    def test_chaque_table_a_fichier_libelle_et_cle(self):
        for nom_table, table in self.tables.items():
            with self.subTest(table=nom_table):
                self.assertEqual(table["fichier"], nom_table + ".csv")
                self.assertTrue(table["libelle"].strip())
                self.assertIn(table["cle"], [c["nom"] for c in table["champs"]])

    def test_chaque_champ_a_un_type_connu_et_un_libelle(self):
        for nom_table, champ in self.tous_les_champs():
            with self.subTest(table=nom_table, champ=champ["nom"]):
                self.assertIn(champ["type"], TYPES_CONNUS)
                self.assertTrue(champ.get("libelle", "").strip(), "libellé vide")

    def test_pas_de_champ_en_double(self):
        for nom_table, table in self.tables.items():
            noms = [c["nom"] for c in table["champs"]]
            self.assertEqual(len(noms), len(set(noms)), nom_table)

    # -- typage ---------------------------------------------------------------

    def test_types_par_nom_de_champ(self):
        for type_attendu, noms in TYPES_PAR_NOM.items():
            for nom_table, champ in self.tous_les_champs():
                if champ["nom"] in noms and (nom_table, champ["nom"]) not in TYPES_PAR_TABLE_ET_NOM:
                    with self.subTest(table=nom_table, champ=champ["nom"]):
                        self.assertEqual(champ["type"], type_attendu)

    def test_types_qui_dependent_de_la_table(self):
        for (nom_table, nom_champ), type_attendu in TYPES_PAR_TABLE_ET_NOM.items():
            with self.subTest(table=nom_table, champ=nom_champ):
                self.assertEqual(self.champs_de(nom_table)[nom_champ]["type"], type_attendu)

    def test_actif_est_booleen_par_defaut_a_1_partout(self):
        presents = [(t, c) for t, c in self.tous_les_champs() if c["nom"] == "actif"]
        self.assertEqual(sorted(t for t, _ in presents),
                         ["articles", "equipements", "gammes", "techniciens"])
        for nom_table, champ in presents:
            self.assertEqual((champ["type"], champ.get("defaut")), ("booleen", "1"), nom_table)

    def test_les_booleens_valent_0_par_defaut_sauf_actif(self):
        for nom_table, champ in self.tous_les_champs():
            if champ["type"] == "booleen" and champ["nom"] != "actif":
                with self.subTest(table=nom_table, champ=champ["nom"]):
                    self.assertEqual(champ.get("defaut"), "0")

    def test_valeurs_par_defaut_utiles(self):
        self.assertEqual(self.champs_de("demandes")["statut"]["defaut"], "Nouvelle")
        self.assertEqual(self.champs_de("ordres_travail")["statut"]["defaut"], "Créé")
        self.assertEqual(self.champs_de("equipements")["statut"]["defaut"], "en service")
        self.assertEqual(self.champs_de("equipements")["criticite"]["defaut"], "B")
        # un défaut de choix doit être une valeur de la liste
        for nom_table, champ in self.tous_les_champs():
            if champ["type"] == "choix" and "defaut" in champ:
                self.assertIn(champ["defaut"], champ["valeurs"], (nom_table, champ["nom"]))

    def test_champs_obligatoires_exacts(self):
        trouves = {(t, c["nom"]) for t, c in self.tous_les_champs() if c.get("obligatoire")}
        self.assertEqual(trouves, OBLIGATOIRES)

    def test_champs_proteges_exacts(self):
        trouves = {(t, c["nom"]) for t, c in self.tous_les_champs() if c.get("protege")}
        self.assertEqual(trouves, CHAMPS_PROTEGES)
        for nom_table, nom_champ in CHAMPS_PROTEGES:
            self.assertEqual(self.champs_de(nom_table)[nom_champ]["type"], "texte")

    def test_les_synonymes_sont_des_listes_de_textes(self):
        avec_synonymes = 0
        for nom_table, champ in self.tous_les_champs():
            if "synonymes" in champ:
                avec_synonymes += 1
                with self.subTest(table=nom_table, champ=champ["nom"]):
                    self.assertIsInstance(champ["synonymes"], list)
                    self.assertTrue(champ["synonymes"])
                    for synonyme in champ["synonymes"]:
                        self.assertTrue(isinstance(synonyme, str) and synonyme.strip())
        self.assertGreater(avec_synonymes, 20)

    # -- listes ---------------------------------------------------------------

    def test_valeurs_canoniques_des_listes(self):
        for (nom_table, nom_champ), valeurs in VALEURS_CANONIQUES.items():
            with self.subTest(table=nom_table, champ=nom_champ):
                champ = self.champs_de(nom_table)[nom_champ]
                self.assertEqual(champ["type"], "choix")
                self.assertEqual(champ["valeurs"], valeurs)

    def test_aucun_choix_non_prevu(self):
        trouves = {(t, c["nom"]) for t, c in self.tous_les_champs() if c["type"] == "choix"}
        self.assertEqual(trouves, set(VALEURS_CANONIQUES.keys()))

    def test_listes_conformes_aux_parentheses_du_brief(self):
        """Les valeurs écrites « a / b / c » entre parenthèses dans le brief sont celles du schéma."""
        for nom_table, attendu in self.brief.items():
            for nom_champ, parenthese in attendu["parentheses"].items():
                if " / " not in parenthese:
                    continue
                with self.subTest(table=nom_table, champ=nom_champ):
                    valeurs_brief = [v.strip() for v in parenthese.split(" / ")]
                    champ = self.champs_de(nom_table)[nom_champ]
                    if champ["type"] == "choix":
                        self.assertEqual(champ["valeurs"], valeurs_brief)

    # -- références -----------------------------------------------------------

    def test_references_attendues(self):
        for (nom_table, nom_champ), (cible, champ_cible, filtre) in REFERENCES_ATTENDUES.items():
            with self.subTest(table=nom_table, champ=nom_champ):
                champ = self.champs_de(nom_table)[nom_champ]
                self.assertEqual(champ["type"], "ref")
                self.assertEqual(champ["table"], cible)
                self.assertEqual(champ.get("champCible"), champ_cible)
                self.assertEqual(champ.get("filtre"), filtre)

    def test_aucune_reference_non_prevue(self):
        trouvees = {(t, c["nom"]) for t, c in self.tous_les_champs() if c["type"] == "ref"}
        self.assertEqual(trouvees, set(REFERENCES_ATTENDUES.keys()))

    def test_toute_reference_vise_une_table_et_un_champ_existants(self):
        for nom_table, champ in self.tous_les_champs():
            if champ["type"] != "ref":
                continue
            with self.subTest(table=nom_table, champ=champ["nom"]):
                self.assertIn(champ["table"], self.tables)
                champs_cible = self.champs_de(champ["table"])
                cible = champ.get("champCible", self.tables[champ["table"]]["cle"])
                self.assertIn(cible, champs_cible)
                for nom_filtre, valeur in (champ.get("filtre") or {}).items():
                    self.assertIn(nom_filtre, champs_cible)
                    if champs_cible[nom_filtre]["type"] == "choix":
                        self.assertIn(valeur, champs_cible[nom_filtre]["valeurs"])

    # -- identifiants ---------------------------------------------------------

    def test_formats_des_identifiants(self):
        for nom_table, (prefixe, chiffres, annuel) in IDENTIFIANTS_ATTENDUS.items():
            with self.subTest(table=nom_table):
                identifiant = self.tables[nom_table]["identifiant"]
                self.assertEqual(identifiant["prefixe"], prefixe)
                self.assertEqual(identifiant["chiffres"], chiffres)
                self.assertEqual(bool(identifiant.get("annuel")), annuel)
                self.assertFalse(identifiant.get("horodate", False))
                self.assertEqual(self.tables[nom_table]["cle"], "id")
                self.assertEqual(self.champs_de(nom_table)["id"]["type"], "id")

    def test_identifiant_du_journal(self):
        journal = self.tables["journal"]
        self.assertEqual(journal["identifiant"]["prefixe"], "J-")
        self.assertIs(journal["identifiant"]["horodate"], True)
        self.assertEqual(journal["cle"], "id")

    def test_journal_en_ajout_seul_et_les_autres_non(self):
        self.assertIs(self.tables["journal"]["ajoutSeul"], True)
        for nom_table, table in self.tables.items():
            if nom_table != "journal":
                self.assertFalse(table.get("ajoutSeul", False), nom_table)

    def test_parametres_a_pour_cle_cle(self):
        parametres = self.tables["parametres"]
        self.assertEqual(parametres["cle"], "cle")
        self.assertNotIn("identifiant", parametres)
        self.assertEqual([c["nom"] for c in parametres["champs"]], ["cle", "valeur"])

    def test_les_champs_cle_sont_de_type_id_et_seuls_de_leur_type(self):
        for nom_table, table in self.tables.items():
            champs_id = [c["nom"] for c in table["champs"] if c["type"] == "id"]
            self.assertEqual(champs_id, [table["cle"]], nom_table)

    # -- fonctions d'accès ----------------------------------------------------

    def test_fonctions_d_acces(self):
        self.assertEqual(self.page.evaluate("Schema.table('articles').fichier"), "articles.csv")
        self.assertIsNone(self.page.evaluate("Schema.table('inexistante') === undefined ? null : 1"))
        self.assertEqual(self.page.evaluate("Schema.champ('equipements', 'num_serie').protege"), True)
        self.assertTrue(self.page.evaluate("Schema.champ('equipements', 'zzz') === undefined"))
        self.assertTrue(self.page.evaluate("Schema.champ('zzz', 'id') === undefined"))
        # un nom hérité d'Object (toString, constructor) n'est pas une table
        self.assertTrue(self.page.evaluate("Schema.table('constructor') === undefined"))
        self.assertEqual(len(self.page.evaluate("Schema.nomsTables()")), 22)


if __name__ == "__main__":
    unittest.main()
