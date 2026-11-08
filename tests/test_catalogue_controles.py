"""Catalogue des contrôles et des habilitations chargé par l'application (2.2, T410 ; CONCEPTION-L2-L3 §1.2, §1.5).

js/catalogue/fr.js (T400, window.CatalogueFR) est chargé par index.html juste après js/formats.js, avec les cinq
modules nouveaux des lots L2 et L3 (vides en T410). Vérifié dans l'application elle-même, en démo (index.html en
file://, en français puis en anglais) et en mode serveur (serveur.py sur une COPIE du jeu de démo) :
  - window.CatalogueFR a 31 contrôles et 15 habilitations, les lignes de docs/catalogue/*.json telles quelles (plus
    la mention calculée), en français quelle que soit la langue de l'interface (CDC §3.2) ;
  - tout est gelé : aucun objet du catalogue ne peut être changé, ni une ligne ajoutée ;
  - le catalogue est chargé juste après js/formats.js, les cinq modules nouveaux sont chargés, l'application arrive
    à l'état « prêt » ; aucune erreur dans la console (CasNavigateur fait échouer le test sinon).

Règles pures du catalogue (T414, CONCEPTION-L2-L3 §4.1, js/modules/controles-catalogue.js), sur une page vide qui
ne charge que les scripts utiles : valeurs copiées d'une ligne (C14 : 48 mois, sa référence, obligation, catalogue,
C14, 2026-11-08 ; aucune périodicité pour C13 et C24), provenance, source après une saisie (une valeur changée rend
« saisie », C14 gardé), mention « à confirmer », familles, résumé de C18 affiché sans « conforme » (réponse
provisoire n° 1, CS175), listes vides sans CatalogueFR, et une page où CatalogueFR est remplacé par une version
modifiée (tirée de docs/catalogue par outils/generer_catalogue.py) : l'écart est proposé, rien n'est changé.

Bibliothèque standard + Playwright. Lancer depuis la racine du projet (au travers du verrou des navigateurs) :
    py -X utf8 -m unittest discover -s tests -p "test_catalogue_controles.py" -v
"""
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from commun import RACINE, CasNavigateur, ServeurPrevo, attendre_pret, charger_scripts, preregler_profil, url_fichier

sys.path.insert(0, str(RACINE / "outils"))
import generer_catalogue  # noqa: E402

EFFECTIFS = {"controles": 31, "habilitations": 15}
SCRIPT_CATALOGUE = "js/catalogue/fr.js"
MODULES_NOUVEAUX = ["controles-reserves.js", "controles-catalogue.js", "controles-reserves-ecrans.js",
                    "equipe-habilitations.js", "ordres-habilitations.js"]

# Relevé fait dans la page : le catalogue (copie JSON), son gel (chaque objet, à toute profondeur), des écritures
# essayées (refusées), les scripts de la page et les objets des modules complétés par les fichiers nouveaux.
RELEVE_JS = """() => {
  const catalogue = window.CatalogueFR;
  const tousGeles = (valeur) => {
    if (!valeur || typeof valeur !== 'object') return true;
    return Object.isFrozen(valeur) && Object.keys(valeur).every((cle) => tousGeles(valeur[cle]));
  };
  let ecrituresRefusees = false;
  let ajoutRefuse = false;
  if (catalogue && catalogue.controles.length && catalogue.habilitations.length) {
    const controle = catalogue.controles[0];
    const habilitation = catalogue.habilitations[0];
    ecrituresRefusees = !Reflect.set(catalogue, 'controles', [])
      && !Reflect.set(catalogue.controles, 'length', 0)
      && !Reflect.set(controle, 'nature', 'modifiée')
      && !Reflect.set(controle.liens[0], 'url', 'https://exemple.invalid/')
      && !Reflect.set(habilitation, 'duree_mois', 1)
      && !Reflect.deleteProperty(controle, 'reference')
      && controle.nature !== 'modifiée' && catalogue.controles.length > 0;
    try { catalogue.habilitations.push({ id: 'H99' }); } catch (erreur) { ajoutRefuse = erreur instanceof TypeError; }
  }
  return {
    present: !!catalogue && typeof catalogue === 'object',
    contenu: catalogue ? JSON.parse(JSON.stringify(catalogue)) : null,
    geles: !!catalogue && tousGeles(catalogue),
    ecrituresRefusees: ecrituresRefusees,
    ajoutRefuse: ajoutRefuse,
    langue: document.documentElement.lang,
    scripts: Array.from(document.scripts).map((script) => script.getAttribute('src')).filter(Boolean),
    objets: [typeof Controles, typeof Equipe, typeof Ordres],
  };
}"""


def lignes_du_depot(nom):
    """Lignes de docs/catalogue/<nom>-fr.json (source du fichier généré js/catalogue/fr.js)."""
    with open(RACINE / "docs" / "catalogue" / (nom + "-fr.json"), encoding="utf-8") as fichier:
        return json.load(fichier)["lignes"]


class CasCatalogue(CasNavigateur):

    def verifier_catalogue(self, langue="fr"):
        releve = self.page.evaluate(RELEVE_JS)
        self.assertTrue(releve["present"], "window.CatalogueFR absent de l'application")
        self.assertEqual(releve["langue"], langue)
        for nom, effectif in EFFECTIFS.items():
            with self.subTest(liste=nom):
                lignes = releve["contenu"][nom]
                self.assertEqual(len(lignes), effectif)
                # Les lignes du dépôt telles quelles (françaises dans toutes les langues), plus la mention calculée.
                for chargee, attendue in zip(lignes, lignes_du_depot(nom)):
                    self.assertEqual(sorted(chargee), sorted(list(attendue) + ["mention"]), attendue["id"])
                    self.assertEqual({cle: chargee[cle] for cle in attendue}, attendue)
        self.assertEqual(sorted(releve["contenu"]), sorted(EFFECTIFS))
        self.assertTrue(releve["geles"], "un objet du catalogue n'est pas gelé")
        self.assertTrue(releve["ecrituresRefusees"], "une écriture dans le catalogue a été acceptée")
        self.assertTrue(releve["ajoutRefuse"], "une ligne a pu être ajoutée au catalogue")
        # Chargé une fois, juste après le registre des formats ; les cinq modules nouveaux chargés.
        scripts = releve["scripts"]
        self.assertEqual(scripts.count(SCRIPT_CATALOGUE), 1)
        self.assertEqual(scripts[scripts.index(SCRIPT_CATALOGUE) - 1], "js/formats.js")
        for module in MODULES_NOUVEAUX:
            with self.subTest(module=module):
                self.assertIn("js/modules/" + module, scripts)
        self.assertEqual(releve["objets"], ["object", "object", "object"])

    def ouvrir_demo(self):
        page = self.page
        page.goto(url_fichier("index.html"))
        page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        page.click("#btn-demo")
        page.wait_for_function("document.documentElement.dataset.etat === 'profil'")
        page.click("#profil-responsable")
        attendre_pret(page)


class TestCatalogueDemo(CasCatalogue):
    """Démo : index.html en file:// (aucun serveur), les données de démo en mémoire."""

    def test_catalogue_charge_et_gele_en_demo(self):
        self.ouvrir_demo()
        self.verifier_catalogue()

    def test_catalogue_en_francais_quand_l_interface_est_en_anglais(self):
        self.contexte.add_init_script(
            "try { if (localStorage.getItem('prevo.langue') === null) localStorage.setItem('prevo.langue', 'en'); }"
            " catch (erreur) { /* page sans stockage */ }")
        self.ouvrir_demo()
        self.verifier_catalogue(langue="en")


class TestCatalogueServeur(CasCatalogue):
    """Mode serveur : serveur.py sur une copie du jeu de démo (jamais donnees/ réel)."""

    def test_catalogue_charge_et_gele_en_mode_serveur(self):
        with ServeurPrevo() as serveur:
            preregler_profil(self.contexte, "responsable", nom="Responsable")
            self.page.goto(serveur.url + "/")
            attendre_pret(self.page)
            # Les écritures du démarrage (OT préventifs échus) sont finies avant le relevé.
            self.page.wait_for_load_state("networkidle")
            self.verifier_catalogue()


# ---------------------------------------------------------------------------------------------------------------
# Règles pures du catalogue (T414) : page vide, scripts utiles seulement, jeu construit à la main
# ---------------------------------------------------------------------------------------------------------------

SCRIPTS_REGLES = ["js/lib/papaparse.min.js", "js/schema.js", "js/formats.js", SCRIPT_CATALOGUE, "js/donnees.js",
                  "js/stockage-demo.js", "js/interface.js", "js/modules/controles-regles.js",
                  "js/modules/controles-reserves.js", "js/modules/controles-catalogue.js"]
MENTION = "à confirmer avec votre organisme de contrôle"
# Réponse provisoire n° 1 de QUESTIONS-L2-L6 (à confirmer) : le résumé de C18 affiché sans « conforme ».
C18_AFFICHE = ("3 mois ; 6 mois si un système de détection des fuites est installé (obligatoire pour les équipements"
               " fixes, donc 6 mois pour un équipement fixe répondant aux exigences du règlement)")
MOT_CONFORME = re.compile(r"\bconformes?\b", re.IGNORECASE)


def csv(entete, lignes):
    """Texte CSV du format (séparateur ;, fins de ligne CRLF)."""
    return "\r\n".join([entete] + list(lignes)) + "\r\n"


def champ_csv(valeur):
    """Valeur d'un champ CSV, entre guillemets si elle contient le séparateur ou un guillemet."""
    return '"%s"' % valeur.replace('"', '""') if ";" in valeur or '"' in valeur else valeur


def lignes_par_id(nom="controles"):
    return {ligne["id"]: ligne for ligne in lignes_du_depot(nom)}


C14 = lignes_par_id()["C14"]
EQUIPEMENTS = csv("id;repere;designation;statut;actif", ["EQ-0001;RA-01;Réservoir d'air;en service;1",
                                                         "EQ-0002;PT-01;Pont roulant;en service;1"])
CONTROLES = csv(
    "id;equipement_id;nature;texte_reference;periodicite_mois;organisme;derniere_date;prochaine_date;rapport;"
    "observations;observations_levees;source_periodicite;nature_source;catalogue_id;catalogue_relu_le", [
        # copié de C14 au catalogue relu le 2026-11-08
        "CTR-0001;EQ-0001;%s;%s;48;Organisme;2025-04-03;2029-04-03;;;1;catalogue;obligation;C14;2026-11-08"
        % (champ_csv(C14["nature"]), champ_csv(C14["reference"])),
        # nature choisie au catalogue (C14), périodicité saisie
        "CTR-0002;EQ-0001;%s;%s;36;Organisme;2025-04-03;2028-04-03;;;1;saisie;obligation;C14;2026-11-08"
        % (champ_csv(C14["nature"]), champ_csv(C14["reference"])),
        # copié de C01 (la version modifiée le relit sans rien y changer)
        "CTR-0003;EQ-0002;VGP pont roulant;%s;12;Organisme;2026-02-10;2027-02-10;;;1;catalogue;obligation;C01;"
        "2026-11-08" % champ_csv(lignes_par_id()["C01"]["reference"]),
        # contrôle d'avant la 2.2 : colonnes du format 4 à leur défaut
        "CTR-0004;EQ-0002;VGP;Arrêté du 1er mars 2004;12;Organisme;2026-02-10;2027-02-10;;;1;saisie;;;",
    ])

# Relevé des contrôles et du journal en mémoire, et de ce que le stockage de démo a écrit.
RELEVE_DONNEES_JS = """() => JSON.stringify({
  controles: Donnees.lignes('controles_reglementaires'),
  journal: Donnees.lignes('journal'),
})"""


def catalogue_modifie(dossier):
    """js/catalogue/fr.js tel que le générerait une version de Prévo dont le catalogue a été relu le 2027-03-01 :
    C14 passe à 60 mois, C01 est relu sans changement ; le reste tel quel. Rend le texte du script."""
    for nom in generer_catalogue.FICHIERS.values():
        shutil.copy(RACINE / "docs" / "catalogue" / nom, Path(dossier) / nom)
    chemin = Path(dossier) / generer_catalogue.FICHIERS["controles"]
    donnees = json.loads(chemin.read_text(encoding="utf-8"))
    for ligne in donnees["lignes"]:
        if ligne["id"] == "C14":
            ligne["periodicite_mois"] = 60
            ligne["relu_le"] = "2027-03-01"
        elif ligne["id"] == "C01":
            ligne["relu_le"] = "2027-03-01"
    chemin.write_text(json.dumps(donnees, ensure_ascii=False, indent=2), encoding="utf-8")
    return generer_catalogue.contenu(dossier)


class CasReglesCatalogue(CasNavigateur):

    def charger(self, avec_catalogue=True):
        scripts = [script for script in SCRIPTS_REGLES if avec_catalogue or script != SCRIPT_CATALOGUE]
        charger_scripts(self.page, scripts)
        self.page.evaluate("""async (tables) => {
          Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Poste test', profil: 'Responsable test' });
          await Donnees.chargerTout();
        }""", {"equipements": EQUIPEMENTS, "controles_reglementaires": CONTROLES})

    def js(self, script, argument=None):
        return self.page.evaluate(script, argument)

    def controle(self, identifiant):
        return self.js("(id) => Donnees.trouver('controles_reglementaires', id)", identifiant)


class TestReglesCatalogue(CasReglesCatalogue):

    def setUp(self):
        super().setUp()
        self.charger()

    def test_c14_rend_48_mois_sa_reference_obligation_catalogue_c14_et_2026_11_08(self):
        attendu = {"nature": C14["nature"], "periodicite_mois": "48", "texte_reference": C14["reference"],
                   "nature_source": "obligation", "source_periodicite": "catalogue", "catalogue_id": "C14",
                   "catalogue_relu_le": "2026-11-08"}
        self.assertEqual(self.js("() => Controles.valeursDepuisCatalogue('C14')"), attendu)
        self.assertEqual(self.js("() => Controles.valeursDepuisCatalogue(Controles.ligneCatalogue(' c14 '))"), attendu)
        self.assertIsNone(self.js("() => Controles.ligneCatalogue('C99')"))
        self.assertIsNone(self.js("() => Controles.ligneCatalogue('')"))
        self.assertIsNone(self.js("() => Controles.valeursDepuisCatalogue('C99')"))

    def test_periodicite_vide_pour_c13_et_c24_seulement(self):
        periodicites = self.js("() => Object.fromEntries(Controles.catalogue().map((ligne) =>"
                               " [ligne.id, Controles.valeursDepuisCatalogue(ligne).periodicite_mois]))")
        for identifiant, ligne in lignes_par_id().items():
            with self.subTest(ligne=identifiant):
                attendue = "" if identifiant in ("C13", "C24") else str(ligne["periodicite_mois"])
                self.assertEqual(periodicites[identifiant], attendue)

    def test_catalogue_et_familles_dans_l_ordre_du_fichier(self):
        releve = self.js("""() => ({
          ids: Controles.catalogue().map((ligne) => ligne.id),
          geles: Object.isFrozen(Controles.catalogue()) && Controles.catalogue().every((ligne) => Object.isFrozen(ligne)),
          memes: Controles.catalogue() === Controles.catalogue()
            && Controles.ligneCatalogue('C14') === window.CatalogueFR.controles[13],
          familles: Controles.famillesCatalogue().map((groupe) => [groupe.famille, groupe.lignes.map((l) => l.id)]),
        })""")
        lignes = lignes_du_depot("controles")
        self.assertEqual(releve["ids"], [ligne["id"] for ligne in lignes])
        self.assertTrue(releve["geles"])
        self.assertTrue(releve["memes"], "les lignes sans remplacement sont celles de CatalogueFR")
        attendues = []
        for ligne in lignes:
            if not attendues or attendues[-1][0] != ligne["famille"]:
                attendues.append([ligne["famille"], []])
            attendues[-1][1].append(ligne["id"])
        self.assertEqual(releve["familles"], attendues)
        self.assertEqual(len({famille for famille, _ in attendues}), len(attendues), "familles d'un seul tenant")

    def test_c18_affiche_sans_conforme_catalogue_valide_inchange(self):
        releve = self.js("""() => ({
          affiche: Controles.ligneCatalogue('C18').periodicite_texte,
          gelee: Object.isFrozen(Controles.ligneCatalogue('C18')),
          source: window.CatalogueFR.controles.find((ligne) => ligne.id === 'C18').periodicite_texte,
          tout: JSON.stringify([Controles.catalogue(), Controles.famillesCatalogue()]),
        })""")
        self.assertEqual(releve["affiche"], C18_AFFICHE)
        self.assertTrue(releve["gelee"])
        # Remplacement à l'affichage seulement : le catalogue validé garde son texte.
        self.assertEqual(releve["source"], lignes_par_id()["C18"]["periodicite_texte"])
        self.assertRegex(releve["source"], MOT_CONFORME)
        self.assertIsNone(MOT_CONFORME.search(releve["tout"]), "« conforme » dans une ligne affichée du catalogue")

    def test_lire_source(self):
        cas = {
            "CTR-0001": {"origine": "catalogue", "catalogueId": "C14", "reluLe": "2026-11-08"},
            "CTR-0002": {"origine": "saisie", "catalogueId": "C14", "reluLe": "2026-11-08"},
            "CTR-0004": {"origine": "saisie", "catalogueId": "", "reluLe": ""},
        }
        for identifiant, attendu in cas.items():
            with self.subTest(controle=identifiant):
                self.assertEqual(self.js("(id) => Controles.lireSource(Donnees.trouver('controles_reglementaires', id))",
                                         identifiant), attendu)
        # Contrôle sans les colonnes du format 4 ; « catalogue » sans catalogue_id (fichier retouché) : saisie.
        self.assertEqual(self.js("() => Controles.lireSource({ id: 'CTR-0009', periodicite_mois: '12' })"),
                         {"origine": "saisie", "catalogueId": "", "reluLe": ""})
        self.assertEqual(self.js("() => Controles.lireSource({ source_periodicite: 'catalogue', catalogue_id: '' })"),
                         {"origine": "saisie", "catalogueId": "", "reluLe": ""})

    def test_source_apres_saisie(self):
        source = self.js("""() => {
          const copie = Controles.valeursDepuisCatalogue('C14');
          const avec = (champs) => Controles.sourceApresSaisie(Object.assign({}, copie, champs), 'C14');
          return {
            copie: avec({}),
            periodicite: avec({ periodicite_mois: '36' }),
            reference: avec({ texte_reference: 'Arrêté du 20 novembre 2017' }),
            natureSource: avec({ nature_source: 'recommandation' }),
            natureRenommee: avec({ nature: 'Inspection du réservoir de l\\'atelier 2', organisme: 'Autre' }),
            zeroDevant: avec({ periodicite_mois: '048' }),
            ligneObjet: Controles.sourceApresSaisie(copie, Controles.ligneCatalogue('C14')),
            sansLigne: Controles.sourceApresSaisie(copie, null),
            inconnue: Controles.sourceApresSaisie(copie, 'C99'),
          };
        }""")
        catalogue = {"source_periodicite": "catalogue", "catalogue_id": "C14", "catalogue_relu_le": "2026-11-08"}
        saisie = dict(catalogue, source_periodicite="saisie")
        vide = {"source_periodicite": "saisie", "catalogue_id": "", "catalogue_relu_le": ""}
        attendus = {"copie": catalogue, "periodicite": saisie, "reference": saisie, "natureSource": saisie,
                    "natureRenommee": catalogue, "zeroDevant": catalogue, "ligneObjet": catalogue,
                    "sansLigne": vide, "inconnue": vide}
        for cas, attendu in attendus.items():
            with self.subTest(cas=cas):
                self.assertEqual(source[cas], attendu)

    def test_mention_du_controle(self):
        mentions = self.js("""() => ({
          C04: Controles.mentionDuControle({ catalogue_id: 'C04', source_periodicite: 'catalogue' }),
          C13: Controles.mentionDuControle({ catalogue_id: 'C13', source_periodicite: 'saisie' }),
          C14: Controles.mentionDuControle(Donnees.trouver('controles_reglementaires', 'CTR-0001')),
          sans: Controles.mentionDuControle(Donnees.trouver('controles_reglementaires', 'CTR-0004')),
          inconnu: Controles.mentionDuControle({ catalogue_id: 'C99' }),
          rien: Controles.mentionDuControle(null),
        })""")
        self.assertEqual(mentions, {"C04": MENTION, "C13": MENTION, "C14": "", "sans": "", "inconnu": "", "rien": ""})
        avec_mention = sorted(identifiant for identifiant, ligne in lignes_par_id().items() if ligne["a_confirmer"])
        self.assertEqual(avec_mention, ["C04", "C13"])

    def test_aucune_mise_a_jour_proposee_avec_le_catalogue_du_controle(self):
        for identifiant in ("CTR-0001", "CTR-0002", "CTR-0003", "CTR-0004"):
            with self.subTest(controle=identifiant):
                self.assertIsNone(self.js(
                    "(id) => Controles.miseAJourProposee(Donnees.trouver('controles_reglementaires', id))", identifiant))


class TestReglesSansCatalogue(CasReglesCatalogue):
    """Page de test sans js/catalogue/fr.js : listes vides, aucune erreur, la saisie libre reste possible."""

    def test_listes_vides_sans_catalogue_fr(self):
        self.charger(avec_catalogue=False)
        releve = self.js("""() => ({
          absent: typeof window.CatalogueFR,
          catalogue: Controles.catalogue(),
          familles: Controles.famillesCatalogue(),
          ligne: Controles.ligneCatalogue('C14'),
          valeurs: Controles.valeursDepuisCatalogue('C14'),
          mention: Controles.mentionDuControle({ catalogue_id: 'C04' }),
          proposee: Controles.miseAJourProposee(Donnees.trouver('controles_reglementaires', 'CTR-0001')),
          source: Controles.sourceApresSaisie({ periodicite_mois: '48' }, 'C14'),
          lue: Controles.lireSource(Donnees.trouver('controles_reglementaires', 'CTR-0001')),
        })""")
        self.assertEqual(releve, {
            "absent": "undefined", "catalogue": [], "familles": [], "ligne": None, "valeurs": None, "mention": "",
            "proposee": None, "source": {"source_periodicite": "saisie", "catalogue_id": "", "catalogue_relu_le": ""},
            "lue": {"origine": "catalogue", "catalogueId": "C14", "reluLe": "2026-11-08"}})


class TestCatalogueModifie(CasReglesCatalogue):
    """CS171 : la page reçoit une version modifiée de CatalogueFR (C14 relu le 2027-03-01 à 60 mois) ; la mise à jour
    est proposée, jamais appliquée : le contrôle, le journal et le stockage restent tels quels."""

    def setUp(self):
        super().setUp()
        self.charger()
        dossier = tempfile.mkdtemp(prefix="prevo-t414-")
        self.addCleanup(shutil.rmtree, dossier, True)
        self.script_modifie = catalogue_modifie(dossier)

    def remplacer_catalogue(self):
        self.page.add_script_tag(content=self.script_modifie)
        self.assertEqual(self.js("() => [Controles.ligneCatalogue('C14').periodicite_mois,"
                                 " Controles.ligneCatalogue('C14').relu_le, Object.isFrozen(window.CatalogueFR)]"),
                         [60, "2027-03-01", True])

    def test_ecart_propose_sans_rien_changer(self):
        avant = self.js(RELEVE_DONNEES_JS)
        controle_avant = self.controle("CTR-0001")
        self.assertIsNone(self.js(
            "() => Controles.miseAJourProposee(Donnees.trouver('controles_reglementaires', 'CTR-0001'))"))
        self.remplacer_catalogue()
        proposee = self.js("""() => {
          const controle = Donnees.trouver('controles_reglementaires', 'CTR-0001');
          const copie = JSON.stringify(controle);
          const resultat = Controles.miseAJourProposee(controle);
          return { idLigne: resultat.ligne.id, ecarts: resultat.ecarts, intact: JSON.stringify(controle) === copie };
        }""")
        self.assertEqual(proposee["idLigne"], "C14")
        self.assertEqual(proposee["ecarts"], [{"champ": "periodicite_mois", "actuel": "48", "propose": "60"}])
        self.assertTrue(proposee["intact"], "miseAJourProposee a changé le contrôle passé")
        # Saisie (CTR-0002), ligne relue sans changement (CTR-0003), contrôle d'avant la 2.2 : rien de proposé.
        for identifiant in ("CTR-0002", "CTR-0003", "CTR-0004"):
            with self.subTest(controle=identifiant):
                self.assertIsNone(self.js(
                    "(id) => Controles.miseAJourProposee(Donnees.trouver('controles_reglementaires', id))", identifiant))
        # Un contrôle déjà relu à cette date n'a rien de proposé.
        self.assertIsNone(self.js("""() => Controles.miseAJourProposee(Object.assign({},
          Donnees.trouver('controles_reglementaires', 'CTR-0001'), { catalogue_relu_le: '2027-03-01' }))"""))
        # Rien n'est changé : contrôles, journal, ni le contrôle relu.
        self.assertEqual(self.js(RELEVE_DONNEES_JS), avant)
        self.assertEqual(self.controle("CTR-0001"), controle_avant)
        self.assertEqual(controle_avant["periodicite_mois"], "48")

    def test_une_autre_modification_garde_la_source_catalogue_et_la_proposition(self):
        self.remplacer_catalogue()
        releve = self.js("""() => {
          const avant = Donnees.trouver('controles_reglementaires', 'CTR-0001');
          const apres = (champs) => Object.assign({}, avant, champs);
          const source = (champs) => Controles.sourceApresSaisie(apres(champs), avant.catalogue_id, avant);
          const organisme = Object.assign(apres({ organisme: 'Autre organisme' }), source({ organisme: 'Autre organisme' }));
          return {
            organisme: source({ organisme: 'Autre organisme' }),
            toujoursProposee: Controles.miseAJourProposee(organisme) !== null,
            periodicite: source({ periodicite_mois: '36' }),
            nouvelleValeurTapee: source({ periodicite_mois: '60' }),
            sansAvant: Controles.sourceApresSaisie(apres({ organisme: 'Autre organisme' }), 'C14'),
          };
        }""")
        catalogue = {"source_periodicite": "catalogue", "catalogue_id": "C14", "catalogue_relu_le": "2026-11-08"}
        self.assertEqual(releve["organisme"], catalogue)
        self.assertTrue(releve["toujoursProposee"])
        self.assertEqual(releve["periodicite"], dict(catalogue, source_periodicite="saisie"))
        self.assertEqual(releve["nouvelleValeurTapee"], catalogue)
        self.assertEqual(releve["sansAvant"], dict(catalogue, source_periodicite="saisie"))


if __name__ == "__main__":
    unittest.main()
