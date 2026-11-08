"""Tests de js/schema.js : conformité au brief §6 et à ARCHITECTURE.md §4, §14.1 (format v2) et §20.2 (format 3),
et au format 4 de la version 2.2 (note de conception du L1, §2 : noms, ordre, types, défauts et libellés).

Le schéma est chargé dans Chromium (page-vide.html en file://) puis lu avec JSON.stringify(Schema).
Chaque table commence exactement par les champs du brief §6, suivis exactement des champs du
tableau d'ARCHITECTURE.md §14.1 (version 2 du format, attribut depuisVersion: 2). Après les 22 tables du
brief viennent les tables du format 3, wiki_pages et wiki_journal (§20.2, attribut depuisVersion: 3 sur la
table), et ordres_travail gagne la colonne astuce (depuisVersion: 3, en fin de table). Le format 4 ajoute les
tables reserves_controle, garanties et contrats_prestataires (depuisVersion: 4, après wiki_journal : 27 tables) et,
en fin de table, des colonnes à equipements, ordres_travail, habilitations et controles_reglementaires
(depuisVersion: 4).
Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_schema.py" -v
"""
import json
import re
import unittest

from commun import NB_TABLES, RACINE, CasNavigateur, charger_scripts

# ---------------------------------------------------------------------------
# Lecture du tableau §6 du brief
# ---------------------------------------------------------------------------


def lire_tableau_brief():
    """Retourne {nom_de_table: {'champs': [noms…], 'parentheses': {champ: 'texte entre parenthèses'}}}.

    Chaque ligne du tableau est `| `table.csv` | champs… |`. Les parenthèses (valeurs d'une liste,
    exemples) sont retirées avant de découper sur les virgules ; ce qui suit « — » est un
    commentaire. Le tableau commence après le titre « 6. Modèle de données ».
    """
    texte = (RACINE / "docs" / "brief-gmao.md").read_text(encoding="utf-8")
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


def lire_tableau_version_2():
    """Retourne {nom_de_table: [(champ, type, libellé)…]} d'après le tableau d'ARCHITECTURE.md §14.1.

    Chaque ligne du tableau est `| `table` | `champ` | `type` (précisions) | Libellé |` ; l'ordre des
    lignes d'une même table est l'ordre attendu des champs en fin de table.
    """
    texte = (RACINE / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    debut = texte.index("### 14.1")
    fin = texte.index("### 14.2", debut)
    tables = {}
    for ligne in texte[debut:fin].splitlines():
        correspondance = re.match(
            r"^\s*\|\s*`([a-z_]+)`\s*\|\s*`([a-z_]+)`\s*\|\s*`([a-z_]+)`[^|]*\|\s*(.+?)\s*\|\s*$", ligne)
        if correspondance:
            nom_table, nom_champ, type_champ, libelle = correspondance.groups()
            tables.setdefault(nom_table, []).append((nom_champ, type_champ, libelle))
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
    "wiki_pages": ("WP-", 4, False), "wiki_journal": ("WJ-", 5, False),
    "reserves_controle": ("RES-", 5, False), "garanties": ("GAR-", 4, False),
    "contrats_prestataires": ("CTP-", 4, False),
}

# Tables ajoutées par le format 3 (ARCHITECTURE.md §20.2) : (champ, type, libellé), dans l'ordre.
TABLES_FORMAT_3 = {
    "wiki_pages": [
        ("id", "id", "Identifiant"), ("type", "choix", "Type"), ("titre", "texte", "Titre"),
        ("cle", "texte", "Clé (titre comparable)"), ("equipement_id", "ref", "Équipement"),
        ("article_id", "ref", "Article"), ("cause_code", "ref", "Code cause"),
        ("rattache_a", "ref", "Rattaché à la page"), ("texte", "texte_long", "Texte"),
        ("ot_cites", "texte", "OT cités"), ("liens", "texte", "Pages liées"), ("version", "entier", "Version"),
        ("origine", "choix", "Origine"), ("modele", "texte", "Modèle"),
        ("derniere_entree", "ref", "Dernière entrée appliquée"), ("valide_par", "texte", "Validé par"),
        ("valide_le", "date_heure", "Validé le"), ("cree_le", "date_heure", "Créée le"),
        ("modifie_le", "date_heure", "Modifiée le"), ("statut", "choix", "Statut"),
    ],
    "wiki_journal": [
        ("id", "id", "Identifiant"), ("nature", "choix", "Nature"), ("ot_id", "ref", "Ordre de travail"),
        ("date_intervention", "date_heure", "Date d'intervention"), ("statut", "choix", "Statut"),
        ("anterieure", "booleen", "Intervention antérieure"), ("ordre", "entier", "Rang de traitement"),
        ("pages", "texte", "Pages concernées"), ("changements", "texte_long", "Changements"),
        ("contradictions", "texte_long", "Contradictions"), ("raisons", "texte_long", "Raisons du refus"),
        ("modele", "texte", "Modèle"), ("essais", "entier", "Essais"), ("cree_le", "date_heure", "Créée le"),
        ("traite_le", "date_heure", "Traitée le"), ("decide_par", "texte", "Décidé par"),
        ("decide_le", "date_heure", "Décidé le"), ("motif", "texte_long", "Motif"),
    ],
}

# Colonnes ajoutées par le format 3 à des tables existantes (§20.2) : (champ, type, libellé), en fin de table.
CHAMPS_FORMAT_3 = {
    "ordres_travail": [("astuce", "texte_long", "Astuce pour la prochaine fois")],
}

# Tables ajoutées par le format 4 (version 2.2, note de conception du L1 §2.2) : (champ, type, libellé français), dans
# l'ordre ; libellés de montants avec « € » (devise par défaut, UI n'est pas chargé).
TABLES_FORMAT_4 = {
    "reserves_controle": [
        ("id", "id", "Identifiant"), ("controle_id", "ref", "Contrôle"), ("date_controle", "date", "Date du contrôle"),
        ("texte", "texte_long", "Réserve"), ("gravite", "choix", "Gravité"),
        ("echeance_levee", "date", "Échéance de levée"), ("levee", "booleen", "Levée"),
        ("date_levee", "date", "Date de levée"), ("commentaire_levee", "texte_long", "Commentaire de levée"),
        ("ot_id", "ref", "OT lié"),
    ],
    "garanties": [
        ("id", "id", "Identifiant"), ("equipement_id", "ref", "Équipement"), ("fournisseur_id", "ref", "Fournisseur"),
        ("date_debut", "date", "Début de garantie"), ("date_fin", "date", "Fin de garantie"),
        ("conditions", "texte_long", "Conditions"), ("document", "document", "Document"), ("actif", "booleen", "Actif"),
    ],
    "contrats_prestataires": [
        ("id", "id", "Identifiant"), ("fournisseur_id", "ref", "Prestataire"), ("objet", "texte", "Objet du contrat"),
        ("equipement_ids", "texte", "Équipements concernés"), ("perimetre", "texte_long", "Périmètre"),
        ("date_debut", "date", "Début"), ("date_fin", "date", "Fin"),
        ("preavis_mois", "entier", "Préavis de résiliation (mois)"),
        ("reconduction_tacite", "booleen", "Reconduction tacite"),
        ("reconduction_mois", "entier", "Durée d'une reconduction (mois)"),
        ("montant_annuel", "decimal", "Montant annuel (€ HT)"), ("document", "document", "Document"),
        ("actif", "booleen", "Actif"),
    ],
}

# Colonnes ajoutées par le format 4 à des tables existantes (note de conception du L1 §2.1), en fin de table.
CHAMPS_FORMAT_4 = {
    "equipements": [("cout_arret_h", "decimal", "Coût d'une heure d'arrêt (€/h)")],
    "ordres_travail": [("habilitation_requise", "texte", "Habilitation exigée par l'OT")],
    "habilitations": [("recyclage_mois", "entier", "Recyclage (mois)"), ("justificatif", "document", "Justificatif"),
                      ("catalogue_id", "texte", "Type du catalogue"), ("nature_source", "choix", "Nature de la source")],
    "controles_reglementaires": [
        ("source_periodicite", "choix", "Origine de la périodicité"), ("nature_source", "choix", "Nature de la source"),
        ("catalogue_id", "texte", "Ligne du catalogue"), ("catalogue_relu_le", "date", "Catalogue relu le")],
}

# Valeurs par défaut du format 4 (les autres champs nouveaux n'en ont pas).
DEFAUTS_FORMAT_4 = {
    ("controles_reglementaires", "source_periodicite"): "saisie", ("reserves_controle", "levee"): "0",
    ("garanties", "actif"): "1", ("contrats_prestataires", "reconduction_tacite"): "0",
    ("contrats_prestataires", "actif"): "1",
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
    ("wiki_pages", "type"), ("wiki_pages", "titre"),
    ("wiki_journal", "nature"), ("wiki_journal", "statut"),
    ("reserves_controle", "controle_id"), ("reserves_controle", "texte"),
    ("garanties", "equipement_id"), ("garanties", "date_fin"),
    ("contrats_prestataires", "fournisseur_id"), ("contrats_prestataires", "objet"),
    ("contrats_prestataires", "date_fin"),
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
    ("wiki_pages", "type"): ["équipement", "composant", "savoir-faire"],         # refonte 2 (§20.12) : « mode » retiré
    ("wiki_pages", "origine"): ["IA", "manuel", "IA et manuel"],
    ("wiki_pages", "statut"): ["active", "archivée"],
    ("wiki_journal", "nature"): ["ingestion", "manuel", "décision"],
    ("wiki_journal", "statut"): ["en file", "à valider", "validée", "rejetée", "à refaire", "refusée",
                                  "rien à ajouter", "appliquée"],
    ("habilitations", "nature_source"): ["obligation", "norme", "recommandation"],                 # format 4
    ("controles_reglementaires", "source_periodicite"): ["catalogue", "saisie"],                  # format 4
    ("controles_reglementaires", "nature_source"): ["obligation", "norme", "recommandation"],     # format 4
    ("reserves_controle", "gravite"): ["mineure", "majeure", "critique"],                         # format 4
}

# Tous les champs « choix » du schéma doivent figurer ci-dessus (et inversement)
TYPES_PAR_NOM = {
    "date": ["date_mes", "date_prevue", "derniere_realisation", "prochaine_echeance",
             "date_obtention", "date_echeance", "derniere_date", "prochaine_date",
             "date_reception", "catalogue_relu_le", "date_controle", "echeance_levee", "date_levee"],
    "date_heure": ["date_decision", "date_creation", "date_debut", "date_fin",
                   "date_cloture_tech", "date_cloture_admin", "valide_le", "cree_le", "modifie_le",
                   "date_intervention", "traite_le", "decide_le"],
    "booleen": ["actif", "arret_production", "remise_service", "fait", "critique",
                "observations_levees", "anomalie_constatee", "anterieure", "levee", "reconduction_tacite"],
    "entier": ["ordre", "delai_jours", "periodicite_jours", "avance_jours", "periodicite_mois", "version",
               "essais", "recyclage_mois", "preavis_mois", "reconduction_mois"],
    "decimal": ["heures_fonct_jour", "temps_prevu_h", "duree_arret_h", "cout_soustraitance",
                "quantite", "quantite_prevue", "heures", "stock", "stock_securite",
                "point_commande", "qte_commande", "prix_unitaire", "taux_horaire",
                "capacite_h_semaine", "periodicite_unites", "seuil",
                "releve_derniere_realisation", "valeur", "valeur_remplacement", "cout_arret_h", "montant_annuel"],
    "texte_long": ["description", "travail_a_faire", "consignes", "compte_rendu", "consignation",
                   "observations", "commentaire", "motif_decision", "motif_attente",
                   "motif_annulation", "astuce", "changements", "contradictions", "raisons", "motif",
                   "commentaire_levee", "conditions", "perimetre"],
    "texte": ["habilitation_requise", "catalogue_id", "objet", "equipement_ids"],
    "document": ["justificatif"],
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
    ("wiki_pages", "texte"): "texte_long",
    # Format 4 : dates sans heure (garanties, contrats), une réserve en texte long, documents joints
    ("garanties", "date_debut"): "date", ("garanties", "date_fin"): "date",
    ("contrats_prestataires", "date_debut"): "date", ("contrats_prestataires", "date_fin"): "date",
    ("reserves_controle", "texte"): "texte_long",
    ("garanties", "document"): "document", ("contrats_prestataires", "document"): "document",
}

# Références : (table, champ) -> (table visée, champCible, filtre)
REFERENCES_ATTENDUES = {
    ("localisations", "parent_id"): ("localisations", None, None),
    ("equipements", "parent_id"): ("equipements", None, None),
    ("equipements", "localisation_id"): ("localisations", None, None),
    ("demandes", "equipement_id"): ("equipements", None, None),
    ("demandes", "ot_id"): ("ordres_travail", None, None),
    ("demandes", "symptome_code"): ("codes_defaillance", "code", {"famille": "symptôme"}),   # v2
    ("demandes", "ot_origine_id"): ("ordres_travail", None, None),                            # v2
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
    ("wiki_pages", "equipement_id"): ("equipements", None, None),                            # v3
    ("wiki_pages", "article_id"): ("articles", None, None),                                # v3
    ("wiki_pages", "cause_code"): ("codes_defaillance", "code", {"famille": "cause"}),        # v3
    ("wiki_pages", "rattache_a"): ("wiki_pages", None, None),                              # v3
    ("wiki_pages", "derniere_entree"): ("wiki_journal", None, None),                       # v3
    ("wiki_journal", "ot_id"): ("ordres_travail", None, None),                             # v3
    ("reserves_controle", "controle_id"): ("controles_reglementaires", None, None),        # v4
    ("reserves_controle", "ot_id"): ("ordres_travail", None, None),                        # v4
    ("garanties", "equipement_id"): ("equipements", None, None),                           # v4
    ("garanties", "fournisseur_id"): ("fournisseurs", None, None),                         # v4
    ("contrats_prestataires", "fournisseur_id"): ("fournisseurs", None, None),             # v4
}


class TestSchema(CasNavigateur):
    """Vérifie le contenu de Schema, tel que le voit le navigateur."""

    def setUp(self):
        super().setUp()
        charger_scripts(self.page, ["js/schema.js"])
        self.schema = json.loads(self.page.evaluate("JSON.stringify(Schema)"))
        self.tables = self.schema["tables"]
        self.brief = lire_tableau_brief()
        self.version_2 = lire_tableau_version_2()

    def champs_de(self, nom_table):
        return {c["nom"]: c for c in self.tables[nom_table]["champs"]}

    def tous_les_champs(self):
        """Itère sur (nom de table, champ) pour toutes les tables."""
        for nom_table, table in self.tables.items():
            for champ in table["champs"]:
                yield nom_table, champ

    # -- structure générale ---------------------------------------------------

    def test_le_brief_decrit_22_tables(self):
        self.assertEqual(len(self.brief), 22)

    def test_22_tables_dans_l_ordre_du_brief_puis_celles_des_formats_3_et_4(self):
        attendu = list(self.brief.keys()) + list(TABLES_FORMAT_3.keys()) + list(TABLES_FORMAT_4.keys())
        self.assertEqual(list(self.tables.keys()), attendu)
        self.assertEqual(len(self.tables), 27)
        self.assertEqual(self.page.evaluate("Schema.nomsTables()"), attendu)
        # tests/commun.py lit le schéma comme du texte : il compte les mêmes tables
        self.assertEqual(NB_TABLES, len(self.tables))

    def test_table_du_format_3(self):
        """wiki_pages et wiki_journal (§20.2) : champs, types et libellés exacts ; depuisVersion 3 sur la table ;
        statut « active » par défaut ; le contrat cite chaque champ."""
        contrat = (RACINE / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
        section = contrat[contrat.index("### 20.2"):contrat.index("### 20.3")]
        for nom_table, champs in TABLES_FORMAT_3.items():
            table = self.tables[nom_table]
            self.assertEqual([(c["nom"], c["type"], c["libelle"]) for c in table["champs"]], champs)
            self.assertIs(table.get("depuisVersion"), 3)
            for nom, _, _ in champs:
                self.assertIn("`" + nom + "`", section, nom)
        self.assertEqual(self.champs_de("wiki_pages")["statut"]["defaut"], "active")
        self.assertEqual(self.champs_de("wiki_pages")["version"]["defaut"], "0")
        self.assertEqual(self.champs_de("wiki_journal")["essais"]["defaut"], "0")
        for nom_table in TABLES_FORMAT_3:
            self.assertIs(self.tables[nom_table]["ajoutSeul"], False)
        for nom_table, champs in CHAMPS_FORMAT_3.items():
            for nom, type_attendu, libelle in champs:
                champ = self.champs_de(nom_table)[nom]
                self.assertEqual((champ["type"], champ["libelle"]), (type_attendu, libelle))
                self.assertIs(champ.get("depuisVersion"), 3)
                self.assertFalse(champ.get("obligatoire", False))   # un fichier v2 n'a pas la colonne
                self.assertIn("`" + nom_table + "." + nom + "`", section)

    def test_tables_du_format_4(self):
        """reserves_controle, garanties, contrats_prestataires : champs, types et libellés français exacts, dans
        l'ordre ; depuisVersion 4 sur la table (pas sur ses champs) ; jamais en ajout seul."""
        for nom_table, champs in TABLES_FORMAT_4.items():
            with self.subTest(table=nom_table):
                table = self.tables[nom_table]
                self.assertEqual([(c["nom"], c["type"], c["libelle"]) for c in table["champs"]], champs)
                self.assertIs(table.get("depuisVersion"), 4)
                self.assertIs(table["ajoutSeul"], False)
                self.assertFalse([c["nom"] for c in table["champs"] if "depuisVersion" in c])
        self.assertEqual(self.tables["reserves_controle"]["libelle"], "Réserves des contrôles")
        self.assertEqual(self.tables["garanties"]["libelle"], "Garanties")
        self.assertEqual(self.tables["contrats_prestataires"]["libelle"], "Contrats de prestataires")

    def test_colonnes_du_format_4_en_fin_de_table(self):
        """Colonnes ajoutées aux tables existantes : type, libellé français, depuisVersion 4, jamais obligatoires
        (un fichier au format 3 n'a pas la colonne), placées après toutes les autres."""
        for nom_table, champs in CHAMPS_FORMAT_4.items():
            noms = [c["nom"] for c in self.tables[nom_table]["champs"]]
            self.assertEqual(noms[-len(champs):], [nom for nom, _, _ in champs], nom_table)
            for nom, type_attendu, libelle in champs:
                with self.subTest(table=nom_table, champ=nom):
                    champ = self.champs_de(nom_table)[nom]
                    self.assertEqual((champ["type"], champ["libelle"]), (type_attendu, libelle))
                    self.assertIs(champ.get("depuisVersion"), 4)
                    self.assertFalse(champ.get("obligatoire", False))

    def test_defauts_et_libelles_des_valeurs_du_format_4(self):
        nouveaux = {(t, nom) for t, champs in TABLES_FORMAT_4.items() for nom, _, _ in champs}
        nouveaux |= {(t, nom) for t, champs in CHAMPS_FORMAT_4.items() for nom, _, _ in champs}
        trouves = {(t, c["nom"]): c["defaut"] for t, c in self.tous_les_champs()
                   if (t, c["nom"]) in nouveaux and "defaut" in c}
        self.assertEqual(trouves, DEFAUTS_FORMAT_4)
        # Valeurs stockées en français (D155), affichées par valeurs.<table>.<champ>.<valeur>
        affichees = self.page.evaluate("""() => [
          Schema.libelleValeur('controles_reglementaires', 'source_periodicite', 'catalogue'),
          Schema.libelleValeur('controles_reglementaires', 'nature_source', 'obligation'),
          Schema.libelleValeur('habilitations', 'nature_source', 'recommandation'),
          Schema.libelleValeur('reserves_controle', 'gravite', 'majeure')]""")
        self.assertEqual(affichees, ["catalogue Prévo", "obligation réglementaire", "recommandation", "majeure"])

    def test_le_tableau_du_format_v2_decrit_4_champs_dans_3_tables(self):
        """Garde-fou de la lecture d'ARCHITECTURE.md §14.1 (sinon les tests ci-dessous ne prouvent rien)."""
        self.assertEqual(self.version_2, {
            "equipements": [("valeur_remplacement", "decimal", "Valeur de remplacement (€ HT)")],
            "demandes": [("symptome_code", "ref", "Code symptôme"),
                         ("ot_origine_id", "ref", "OT d'origine (préventif)")],
            "ordres_travail": [("anomalie_constatee", "booleen", "Anomalie constatée")],
        })

    def test_version_du_format(self):
        self.assertEqual(self.schema["version"], 4)

    def test_champs_du_brief_en_tete_puis_exactement_les_champs_v2(self):
        """Chaque table : les champs du brief §6, dans le même ordre, sont le début exact de la liste ;
        viennent ensuite exactement les champs du tableau §14.1, puis ceux des formats 3 et 4 (aucun ailleurs)."""
        for nom_table, attendu in self.brief.items():
            with self.subTest(table=nom_table):
                noms = [c["nom"] for c in self.tables[nom_table]["champs"]]
                champs_brief = attendu["champs"]
                self.assertEqual(noms[:len(champs_brief)], champs_brief)
                champs_v2 = [nom for nom, _, _ in self.version_2.get(nom_table, [])]
                champs_v3 = [nom for nom, _, _ in CHAMPS_FORMAT_3.get(nom_table, [])]
                champs_v4 = [nom for nom, _, _ in CHAMPS_FORMAT_4.get(nom_table, [])]
                self.assertEqual(noms[len(champs_brief):], champs_v2 + champs_v3 + champs_v4)

    def test_champs_v2_types_libelles_et_depuis_version(self):
        for nom_table, champs_v2 in self.version_2.items():
            for nom_champ, type_attendu, libelle in champs_v2:
                with self.subTest(table=nom_table, champ=nom_champ):
                    champ = self.champs_de(nom_table)[nom_champ]
                    self.assertEqual(champ["type"], type_attendu)
                    self.assertEqual(champ["libelle"], libelle)
                    self.assertIs(champ.get("depuisVersion"), 2)
                    self.assertFalse(champ.get("obligatoire", False))   # un fichier v1 n'a pas la colonne
        self.assertEqual(self.champs_de("ordres_travail")["anomalie_constatee"]["defaut"], "0")
        self.assertNotIn("defaut", self.champs_de("equipements")["valeur_remplacement"])

    def test_seuls_les_champs_v2_portent_depuis_version(self):
        attendus = {(t, nom) for t, champs in self.version_2.items() for nom, _, _ in champs}
        attendus |= {(t, nom) for t, champs in CHAMPS_FORMAT_3.items() for nom, _, _ in champs}
        attendus |= {(t, nom) for t, champs in CHAMPS_FORMAT_4.items() for nom, _, _ in champs}
        trouves = {(t, c["nom"]) for t, c in self.tous_les_champs() if "depuisVersion" in c}
        self.assertEqual(trouves, attendus)
        tables_datees = {t: table["depuisVersion"] for t, table in self.tables.items() if "depuisVersion" in table}
        self.assertEqual(tables_datees, {**{t: 3 for t in TABLES_FORMAT_3}, **{t: 4 for t in TABLES_FORMAT_4}})

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
                         ["articles", "contrats_prestataires", "equipements", "gammes", "garanties", "techniciens"])
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

    def test_valeurs_retirees(self):
        """Une valeur retirée (`retirees`) n'est plus proposée, mais une ancienne ligne qui la porte reste lue : seul le
        type « mode » des pages du wiki (refonte 2, §20.12)."""
        trouves = {(t, c["nom"]): c["retirees"] for t, c in self.tous_les_champs() if "retirees" in c}
        self.assertEqual(trouves, {("wiki_pages", "type"): ["mode"]})
        for (nom_table, nom_champ), retirees in trouves.items():
            self.assertFalse(set(retirees) & set(self.champs_de(nom_table)[nom_champ]["valeurs"]))

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
        self.assertEqual(len(self.page.evaluate("Schema.nomsTables()")), 27)


if __name__ == "__main__":
    unittest.main()
