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
« saisie », C14 gardé), mention « à confirmer », familles, résumé de C18 affiché sans « conforme » (D194,
CS175), listes vides sans CatalogueFR, et une page où CatalogueFR est remplacé par une version
modifiée (tirée de docs/catalogue par outils/generer_catalogue.py) : l'écart est proposé, rien n'est changé.

Écritures du catalogue (T415, CONCEPTION-L2-L3 §4.2, js/modules/controles-ecritures.js), par l'API (Controles.*) en
mode serveur (serveur.py sur une COPIE du jeu de démo), CSV relus sur le disque : un contrôle créé depuis C14 enregistre
catalogue, C14, 2026-11-08 et obligation ; passé à 36 mois, il devient « saisie » (C14 gardé) ; changer l'organisme
ne change pas la source ; ligne et nature de la source inconnues ramenées à vide sans refus ; source et relecture
reçues ignorées ; catalogue relu (C14 à 60 mois) : une autre modification garde 48 mois, seule
appliquerMiseAJourCatalogue reprend les valeurs (journal « valeurs du catalogue C14 relu le 01/03/2027 reprises »),
rejouable ; ligne retirée du catalogue de la page : provenance gardée.

Le catalogue à l'écran (T416, CONCEPTION-L2-L3 §4.3, §4.4, controles-catalogue.js et controles-ecrans.js) :
  - en démo, formulaire « Nouveau contrôle » : « Saisie libre (hors catalogue) » en premier et choisi, un groupe par
    famille ; choisir C14 remplit 48 mois, sa référence et « obligation réglementaire », l'encart (lang="fr",
    data-catalogue) dit « relu le 08/11/2026 », « réglementation française », équipements visés, qui vérifie, liens
    en nouvel onglet (noopener noreferrer) ; changer la périodicité montre « saisie » ; C04 et C13 montrent « à
    confirmer avec votre organisme de contrôle » ; C13 laisse la périodicité vide avec son aide ; C18 ne dit jamais
    « conforme » ; fiche d'un contrôle de la démo : provenance, liens, phrase D182 ;
  - en mode serveur (CSV relus) : contrôle créé par le formulaire depuis C14 (catalogue, C14, 2026-11-08,
    obligation) ; page qui reçoit le catalogue relu (C14 à 60 mois) : encart « Le catalogue Prévo a été relu le
    01/03/2027 : il propose 60 mois (vous avez 48 mois). Rien n'est changé sans vous. », rien d'écrit sans le clic,
    pas de bouton pour le technicien (écran en anglais), « Reprendre ces valeurs » reprend 60 mois ; l'historique dit
    l'entrée du journal, traduite en anglais.

Bibliothèque standard + Playwright. Lancer depuis la racine du projet (au travers du verrou des navigateurs) :
    py -X utf8 -m unittest discover -s tests -p "test_catalogue_controles.py" -v
"""
import csv as module_csv
import io
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
# D194 : le résumé de C18 affiché sans « conforme ».
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


# ---------------------------------------------------------------------------------------------------------------
# Écritures du catalogue (T415) : par l'API, mode serveur sur une copie du jeu de démo, CSV relus sur le disque
# ---------------------------------------------------------------------------------------------------------------

# Appel d'une fonction de Controles : « accepté:<JSON> », « refus:<message> » (ErreurValidation) ou « erreur:… ».
APPEL_JS = """async ([fonction, arguments_]) => {
  try { return 'accepté:' + JSON.stringify(await Controles[fonction](...arguments_)); }
  catch (erreur) { return (erreur instanceof Donnees.ErreurValidation ? 'refus:' : 'erreur:') + erreur.message; }
}"""
PROPOSEE_JS = "(id) => Controles.miseAJourProposee(Donnees.trouver('controles_reglementaires', id))"
PROVENANCE = ("source_periodicite", "catalogue_id", "catalogue_relu_le", "nature_source")
SOURCE_C14 = {"source_periodicite": "catalogue", "catalogue_id": "C14", "catalogue_relu_le": "2026-11-08",
              "nature_source": "obligation"}
SANS_SOURCE = {"source_periodicite": "saisie", "catalogue_id": "", "catalogue_relu_le": "", "nature_source": ""}
MODIFICATION = " — modification du contrôle réglementaire"


def valeur_brute(valeur):
    """Valeur d'un champ CSV sans l'apostrophe de protection contre Excel (« '=… », « '+… »)."""
    valeur = valeur or ""
    return valeur[1:] if valeur.startswith("'") else valeur


def lire_table(dossier, nom):
    """Lignes d'un CSV du dossier de données relu sur le disque (BOM, « ; », apostrophe de protection retirée)."""
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return [{cle: valeur_brute(valeur) for cle, valeur in ligne.items()}
            for ligne in module_csv.DictReader(io.StringIO(texte), delimiter=";")]


class CasEcrituresCatalogue(CasNavigateur):

    def ouvrir(self, serveur):
        preregler_profil(self.contexte, "responsable", nom="Responsable")
        self.page.goto(serveur.url + "/#/controles")
        attendre_pret(self.page)
        # Les écritures du démarrage (OT préventifs échus) sont finies avant le premier relevé.
        self.page.wait_for_load_state("networkidle")
        self.dossier = serveur.dossier

    def appeler(self, fonction, *arguments):
        return self.page.evaluate(APPEL_JS, [fonction, list(arguments)])

    def accepte(self, fonction, *arguments):
        resultat = self.appeler(fonction, *arguments)
        self.assertTrue(resultat.startswith("accepté:"), resultat)
        return json.loads(resultat[len("accepté:"):])

    def controles(self):
        return lire_table(self.dossier, "controles_reglementaires.csv")

    def controle(self, identifiant):
        return next(ligne for ligne in self.controles() if ligne["id"] == identifiant)

    def provenance(self, identifiant):
        ligne = self.controle(identifiant)
        return {cle: ligne[cle] for cle in PROVENANCE}

    def octets(self):
        return (self.dossier / "controles_reglementaires.csv").read_bytes()

    def journal(self, identifiant):
        return [entree["action"] for entree in lire_table(self.dossier, "journal.csv")
                if entree["table"] == "controles_reglementaires" and entree["id_ligne"] == identifiant]

    def equipement(self):
        return next(ligne["id"] for ligne in lire_table(self.dossier, "equipements.csv")
                    if ligne["actif"] != "0" and ligne["statut"] != "rebut")

    def controle_du_catalogue(self, catalogue_id):
        """Un contrôle de la démo copié de cette ligne (« catalogue »), cherché dans le CSV (aucun identifiant en dur)."""
        return next(ligne["id"] for ligne in self.controles()
                    if ligne["catalogue_id"] == catalogue_id and ligne["source_periodicite"] == "catalogue")

    def valeurs_c14(self, **champs):
        """Valeurs du formulaire après le choix de C14 (Controles.valeursDepuisCatalogue), plus l'équipement."""
        valeurs = self.page.evaluate("() => Controles.valeursDepuisCatalogue('C14')")
        valeurs.update(equipement_id=self.equipement(), organisme="Organisme T415")
        valeurs.update(champs)
        return valeurs


class TestEcrituresCatalogue(CasEcrituresCatalogue):

    def test_cree_depuis_c14_puis_36_mois_devient_saisie_c14_garde(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur)
            identifiant = self.accepte("creerControle", self.valeurs_c14())
            ligne = self.controle(identifiant)
            self.assertEqual((ligne["nature"], ligne["texte_reference"], ligne["periodicite_mois"]),
                             (C14["nature"], C14["reference"], "48"))
            self.assertEqual(self.provenance(identifiant), SOURCE_C14)
            # Renommer la nature ou changer l'organisme n'est pas changer la source : « catalogue » gardé.
            self.assertEqual(self.accepte("modifierControle", identifiant, {
                "nature": "Inspection du réservoir de l'atelier 2", "organisme": "Autre organisme"}),
                ["nature", "organisme"])
            self.assertEqual(self.provenance(identifiant), SOURCE_C14)
            # 36 mois saisis : « saisie », la ligne C14 et sa relecture gardées (nature choisie au catalogue).
            self.assertEqual(self.accepte("modifierControle", identifiant, {"periodicite_mois": "36"}),
                             ["periodicite_mois", "source_periodicite"])
            self.assertEqual(self.controle(identifiant)["periodicite_mois"], "36")
            self.assertEqual(self.provenance(identifiant), dict(SOURCE_C14, source_periodicite="saisie"))
            # Rien à reprendre (contrôle saisi, catalogue de cette version) : rien n'est écrit.
            avant = self.octets()
            self.assertEqual(self.accepte("appliquerMiseAJourCatalogue", identifiant), [])
            self.assertEqual(self.octets(), avant)
            # Revenu aux valeurs de la ligne (« 048 » = 48) : de nouveau « catalogue ».
            self.assertEqual(self.accepte("modifierControle", identifiant, {"periodicite_mois": "048"}),
                             ["periodicite_mois", "source_periodicite"])
            self.assertEqual(self.provenance(identifiant), SOURCE_C14)
            self.assertEqual(self.journal(identifiant), [
                "création — création du contrôle réglementaire",
                "modification : nature, organisme" + MODIFICATION,
                "modification : periodicite_mois, source_periodicite" + MODIFICATION,
                "modification : periodicite_mois, source_periodicite" + MODIFICATION])

    def test_valeurs_inconnues_ramenees_a_vide_et_provenance_jamais_prise_de_l_appelant(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur)
            # Ligne et nature de la source inconnues : ramenées à vide, sans refus ni message ; « saisie ».
            inconnues = self.accepte("creerControle", {
                "equipement_id": self.equipement(), "nature": "Contrôle maison (T415)", "periodicite_mois": "12",
                "catalogue_id": "C99", "nature_source": "loi", "source_periodicite": "catalogue",
                "catalogue_relu_le": "2020-01-01"})
            self.assertEqual(self.provenance(inconnues), SANS_SOURCE)
            # Ligne en minuscules, nature de la source en capitales : reconnues ; source et relecture reçues
            # ignorées (calculées par l'écriture).
            reconnue = self.accepte("creerControle", self.valeurs_c14(
                catalogue_id=" c14 ", nature_source="Obligation", source_periodicite="saisie",
                catalogue_relu_le="2020-01-01"))
            self.assertEqual(self.provenance(reconnue), SOURCE_C14)
            # Nature choisie au catalogue, périodicité saisie dès la création : « saisie », C14 gardé.
            saisie = self.accepte("creerControle", self.valeurs_c14(periodicite_mois="36"))
            self.assertEqual(self.provenance(saisie), dict(SOURCE_C14, source_periodicite="saisie"))
            # Saisie libre (aucune ligne) : comme avant la 2.2, la nature de la source saisie gardée.
            libre = self.accepte("creerControle", {"equipement_id": self.equipement(), "nature": "Essai (T415)",
                                                   "periodicite_mois": "12", "nature_source": "norme"})
            self.assertEqual(self.provenance(libre), dict(SANS_SOURCE, nature_source="norme"))
            # Modification : ligne, relecture et source reçues ignorées ; rien d'écrit.
            avant = self.octets()
            self.assertEqual(self.accepte("modifierControle", reconnue, {
                "catalogue_id": "C01", "catalogue_relu_le": "2030-01-01", "source_periodicite": "saisie"}), [])
            self.assertEqual(self.octets(), avant)
            # Nature de la source inconnue à la modification : vide, donc « saisie » (C14 gardé).
            self.assertEqual(self.accepte("modifierControle", reconnue, {"nature_source": "inconnue"}),
                             ["nature_source", "source_periodicite"])
            self.assertEqual(self.provenance(reconnue),
                             dict(SOURCE_C14, source_periodicite="saisie", nature_source=""))

    def test_catalogue_relu_seule_appliquer_mise_a_jour_reprend_ses_valeurs(self):
        """CS171 : la page reçoit le catalogue d'une version plus récente (C14 relu le 2027-03-01 à 60 mois)."""
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur)
            c14, c01 = self.controle_du_catalogue("C14"), self.controle_du_catalogue("C01")
            initiaux = {ligne["id"]: ligne for ligne in self.controles()}
            dossier = tempfile.mkdtemp(prefix="prevo-t415-")
            self.addCleanup(shutil.rmtree, dossier, True)
            self.page.add_script_tag(content=catalogue_modifie(dossier))
            self.assertEqual(self.page.evaluate("() => Controles.ligneCatalogue('C14').periodicite_mois"), 60)
            self.assertEqual(self.controles(), list(initiaux.values()), "le catalogue relu a changé un contrôle")
            # Une autre modification (l'organisme) garde 48 mois, « catalogue » et la relecture du 08/11/2026 ;
            # la mise à jour reste proposée.
            self.assertEqual(self.accepte("modifierControle", c14, {"organisme": "Autre organisme (T415)"}),
                             ["organisme"])
            self.assertEqual(dict(self.controle(c14), organisme=initiaux[c14]["organisme"]), initiaux[c14])
            self.assertEqual(self.controle(c14)["periodicite_mois"], "48")
            self.assertEqual(self.page.evaluate(PROPOSEE_JS, c14)["ecarts"],
                             [{"champ": "periodicite_mois", "actuel": "48", "propose": "60"}])
            # Ligne relue sans changement (C01) : rien à reprendre, rien d'écrit.
            octets = self.octets()
            self.assertEqual(self.accepte("appliquerMiseAJourCatalogue", c01), [])
            self.assertEqual(self.octets(), octets)
            # Le clic : 60 mois et la relecture du 01/03/2027 ; la prochaine date et le reste tels quels.
            self.assertEqual(self.accepte("appliquerMiseAJourCatalogue", c14),
                             ["periodicite_mois", "catalogue_relu_le"])
            ligne = self.controle(c14)
            self.assertEqual({cle: ligne[cle] for cle in PROVENANCE + ("periodicite_mois",)},
                             dict(SOURCE_C14, catalogue_relu_le="2027-03-01", periodicite_mois="60"))
            self.assertEqual(dict(ligne, organisme=initiaux[c14]["organisme"], periodicite_mois="48",
                                  catalogue_relu_le="2026-11-08"), initiaux[c14])
            self.assertEqual(self.journal(c14)[-1], "modification : periodicite_mois, catalogue_relu_le"
                             " — valeurs du catalogue C14 relu le 01/03/2027 reprises")
            self.assertIsNone(self.page.evaluate(PROPOSEE_JS, c14))
            # Rejouable (double clic, autre poste) : rien de plus.
            octets = self.octets()
            self.assertEqual(self.accepte("appliquerMiseAJourCatalogue", c14), [])
            self.assertEqual(self.octets(), octets)
            # Les autres contrôles n'ont pas bougé.
            for autre in self.controles():
                if autre["id"] != c14:
                    with self.subTest(controle=autre["id"]):
                        self.assertEqual(autre, initiaux[autre["id"]])
            resultat = self.appeler("appliquerMiseAJourCatalogue", "CTR-9999")
            self.assertTrue(resultat.startswith("refus:") and "CTR-9999" in resultat, resultat)
            self.assertEqual(self.octets(), octets)

    def test_ligne_retiree_du_catalogue_de_la_page_provenance_gardee(self):
        """Une version qui n'aurait plus la ligne C14 (ou une page sans elle) n'efface pas la provenance."""
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur)
            c14 = self.controle_du_catalogue("C14")
            self.page.evaluate("""() => {
              const catalogue = window.CatalogueFR;
              window.CatalogueFR = Object.freeze({ habilitations: catalogue.habilitations,
                controles: Object.freeze(catalogue.controles.filter((ligne) => ligne.id !== 'C14')) });
            }""")
            self.assertIsNone(self.page.evaluate("() => Controles.ligneCatalogue('C14')"))
            self.assertEqual(self.accepte("modifierControle", c14, {"organisme": "Autre organisme (T415)"}),
                             ["organisme"])
            self.assertEqual(self.provenance(c14), SOURCE_C14)
            self.assertEqual(self.accepte("modifierControle", c14, {"periodicite_mois": "36"}),
                             ["periodicite_mois", "source_periodicite"])
            self.assertEqual(self.provenance(c14), dict(SOURCE_C14, source_periodicite="saisie"))
            octets = self.octets()
            self.assertEqual(self.accepte("appliquerMiseAJourCatalogue", c14), [])
            self.assertEqual(self.octets(), octets)


# ---------------------------------------------------------------------------------------------------------------
# Le catalogue à l'écran (T416) : formulaire « Nouveau contrôle », fiche, mise à jour proposée
# ---------------------------------------------------------------------------------------------------------------

PHRASE_D182 = "Prévo est une aide au suivi ; la responsabilité reste celle de l'employeur."
PROVENANCE_C14 = "Catalogue Prévo (C14), relu le 08/11/2026 — réglementation française"
AIDE_SANS_PERIODICITE = "Aucune périodicité par défaut : à saisir (par exemple selon votre contrat d'assurance)."
MISE_A_JOUR_C14 = ("Le catalogue Prévo a été relu le 01/03/2027 : il propose 60 mois (vous avez 48 mois). Rien n'est"
                   " changé sans vous.")

# Relevé du formulaire « Nouveau contrôle » : champs, encart de la ligne choisie, texte de la page.
FORMULAIRE_JS = """() => {
  const formulaire = document.querySelector('#form-controle');
  const champ = (nom) => formulaire.querySelector('[name="' + nom + '"]');
  const encart = formulaire.querySelector('.controles-catalogue-encart');
  const dans = (selecteur) => (encart && !encart.hidden ? Array.from(encart.querySelectorAll(selecteur)) : []);
  const liste = champ('catalogue_id');
  return {
    choisie: liste.value,
    libelle: formulaire.querySelector('label[for="' + liste.id + '"]').textContent.trim(),
    premiere: [liste.options[0].value, liste.options[0].text],
    groupes: Array.from(liste.querySelectorAll('optgroup')).map((groupe) => [groupe.label,
      Array.from(groupe.querySelectorAll('option')).map((option) => option.value)]),
    options: Object.fromEntries(Array.from(liste.querySelectorAll('optgroup option')).map((o) => [o.value, o.text])),
    nature: champ('nature').value, periodicite: champ('periodicite_mois').value,
    reference: champ('texte_reference').value, natureSource: champ('nature_source').value,
    natureSourceAffichee: champ('nature_source').selectedOptions[0].text,
    natureSourceVide: champ('nature_source').options[0].text,
    aidePeriodicite: formulaire.querySelector('.champ[data-champ="periodicite_mois"] .aide').textContent,
    encart: !!encart && !encart.hidden,
    texteEncart: encart && !encart.hidden ? encart.innerText : '',
    provenance: dans('.controles-provenance').map((e) => e.textContent.trim()).join(''),
    badge: dans('.controles-badge-saisie').map((e) => e.textContent.trim()).join(''),
    valeurModifiee: dans('.controles-valeur-modifiee').some((e) => !e.hidden),
    mentions: dans('.controles-catalogue-mention').map((e) => e.innerText.trim()),
    liens: dans('.controles-catalogue-liens a').map((a) => [a.getAttribute('href'), a.target, a.rel]),
    blocs: dans('[data-catalogue]').map((e) => e.getAttribute('lang')),
    principe: Array.from(formulaire.querySelectorAll('.controles-principe')).map((e) => e.textContent.trim()),
    page: document.querySelector('#contenu').innerText,
  };
}"""

# Relevé de la source d'un contrôle sur sa fiche.
FICHE_JS = """() => {
  const source = document.querySelector('#contenu .controles-source');
  const mise = source && source.querySelector('.controles-mise-a-jour');
  return {
    provenance: source ? source.querySelector('.controles-provenance').textContent.trim() : null,
    liens: source ? Array.from(source.querySelectorAll('.controles-catalogue-liens a')).map((a) =>
      [a.getAttribute('href'), a.target, a.rel, a.querySelector('[data-catalogue]').getAttribute('lang')]) : [],
    miseAJour: mise ? mise.querySelector('p').textContent.trim() : null,
    bouton: !!document.querySelector('#controle-reprendre-catalogue'),
    principe: Array.from(document.querySelectorAll('#contenu .controles-principe')).map((e) => e.textContent.trim()),
    natureSource: (document.querySelector('#form-controle [name=nature_source]') || {}).value,
    historique: Array.from(document.querySelectorAll('#contenu .controles-journal .controles-action'))
      .map((e) => e.textContent.trim()),
    page: document.querySelector('#contenu').innerText,
  };
}"""


def liens_de(identifiant):
    """[adresse, cible, rel] des liens d'une ligne du catalogue, tels que l'écran doit les rendre."""
    return [[lien["url"], "_blank", "noopener noreferrer"] for lien in lignes_par_id()[identifiant]["liens"]]


class CasCatalogueEcran(CasCatalogue):

    def formulaire(self):
        return self.page.evaluate(FORMULAIRE_JS)

    def choisir(self, identifiant):
        self.page.select_option("#form-controle [name=catalogue_id]", identifiant)
        return self.formulaire()

    def aller(self, route, selecteur):
        self.page.evaluate("(route) => { location.hash = route; }", route)
        self.page.wait_for_selector(selecteur)


class TestCatalogueEcranDemo(CasCatalogueEcran):
    """Démo (index.html en file://), profil Responsable."""

    def test_formulaire_nouveau_controle(self):
        self.ouvrir_demo()
        self.aller("#/controles/nouveau", "#form-controle [name=catalogue_id]")
        lignes = lignes_du_depot("controles")
        releve = self.formulaire()
        # Saisie libre en premier et choisie ; un groupe par famille, dans l'ordre du fichier ; libellés des options.
        self.assertEqual(releve["libelle"], "Choisir dans le catalogue Prévo — réglementation française")
        self.assertEqual(releve["premiere"], ["", "Saisie libre (hors catalogue)"])
        self.assertEqual(releve["choisie"], "")
        familles = []
        for ligne in lignes:
            if not familles or familles[-1][0] != ligne["famille"]:
                familles.append([ligne["famille"], []])
            familles[-1][1].append(ligne["id"])
        self.assertEqual(releve["groupes"], familles)
        self.assertEqual(releve["options"]["C01"], "C01 · VGP pont roulant, palan, potence (installés à demeure) — 12 mois")
        self.assertEqual(releve["options"]["C13"], "C13 · " + lignes_par_id()["C13"]["nature"]
                         + " — sans périodicité par défaut")
        self.assertFalse(releve["encart"])
        self.assertEqual(releve["principe"], [PHRASE_D182])
        self.assertEqual(releve["natureSourceVide"], "— non renseignée —")
        aide_initiale = releve["aidePeriodicite"]

        # C14 : 48 mois, sa référence, « obligation réglementaire », relu le 08/11/2026, réglementation française.
        releve = self.choisir("C14")
        self.assertEqual((releve["nature"], releve["periodicite"], releve["reference"], releve["natureSource"]),
                         (C14["nature"], "48", C14["reference"], "obligation"))
        self.assertEqual(releve["natureSourceAffichee"], "obligation réglementaire")
        self.assertTrue(releve["encart"])
        self.assertIn("obligation réglementaire · relu le 08/11/2026 · réglementation française", releve["texteEncart"])
        for morceau in (C14["reference"], C14["equipements"], C14["qui_verifie"], C14["periodicite_texte"],
                        "Tout reste modifiable."):
            with self.subTest(morceau=morceau):
                self.assertIn(morceau, releve["texteEncart"])
        self.assertEqual(releve["provenance"], PROVENANCE_C14)
        self.assertEqual((releve["badge"], releve["valeurModifiee"], releve["mentions"]), ("", False, []))
        self.assertEqual(releve["liens"], liens_de("C14"))
        self.assertTrue(releve["blocs"] and all(lang == "fr" for lang in releve["blocs"]), releve["blocs"])
        self.assertEqual(releve["principe"], [PHRASE_D182])
        # Renommer la nature n'est pas changer la source ; changer la périodicité montre « saisie ».
        self.page.fill("#form-controle [name=nature]", "Inspection du réservoir de l'atelier 2")
        self.assertEqual((self.formulaire()["provenance"], self.formulaire()["badge"]), (PROVENANCE_C14, ""))
        self.page.fill("#form-controle [name=periodicite_mois]", "36")
        releve = self.formulaire()
        self.assertEqual((releve["badge"], releve["valeurModifiee"]), ("saisie", True))
        self.assertEqual(releve["provenance"], "Saisie (nature choisie au catalogue : C14)")
        self.assertIn("Valeur modifiée : elle sera notée « saisie ».", releve["texteEncart"])
        self.page.fill("#form-controle [name=periodicite_mois]", "48")
        self.assertEqual((self.formulaire()["badge"], self.formulaire()["provenance"]), ("", PROVENANCE_C14))
        self.page.select_option("#form-controle [name=nature_source]", "norme")
        self.assertEqual(self.formulaire()["badge"], "saisie")

        # C04 et C13 : « à confirmer avec votre organisme de contrôle » ; C13 sans périodicité, avec son aide.
        releve = self.choisir("C04")
        self.assertEqual((releve["periodicite"], releve["mentions"], releve["badge"]), ("6", [MENTION], ""))
        releve = self.choisir("C13")
        self.assertEqual((releve["periodicite"], releve["natureSource"], releve["mentions"]),
                         ("", "recommandation", [MENTION]))
        self.assertEqual(releve["aidePeriodicite"], AIDE_SANS_PERIODICITE)
        # C18 : jamais « conforme » à l'écran (D194).
        releve = self.choisir("C18")
        self.assertIn(C18_AFFICHE, releve["texteEncart"])
        self.assertIsNone(MOT_CONFORME.search(releve["page"]), "« conforme » à l'écran")
        self.assertEqual(releve["aidePeriodicite"], aide_initiale)
        # Retour à la saisie libre : encart fermé, valeurs gardées (tout reste modifiable).
        releve = self.choisir("")
        self.assertFalse(releve["encart"])
        self.assertEqual((releve["nature"], releve["periodicite"]), (lignes_par_id()["C18"]["nature"], "3"))
        self.assertEqual(releve["principe"], [PHRASE_D182])

    def test_fiche_d_un_controle_de_la_demo(self):
        self.ouvrir_demo()
        identifiant, relu_le = self.page.evaluate("() => { const c = Donnees.lignes('controles_reglementaires')"
                                                  ".find((c) => c.catalogue_id === 'C14'); return [c.id, c.catalogue_relu_le]; }")
        self.aller("#/controles/" + identifiant, "#contenu .controles-source")
        releve = self.page.evaluate(FICHE_JS)
        # La démo décale toutes ses colonnes date (StockageDemo.decalerDates), catalogue_relu_le comprise : la date
        # affichée est celle du contrôle en mémoire (écart signalé au rendu de T416).
        annee, mois_, jour = relu_le.split("-")
        self.assertEqual(releve["provenance"], "Catalogue Prévo (C14), relu le %s/%s/%s — réglementation française"
                         % (jour, mois_, annee))
        self.assertEqual(releve["liens"], [lien + ["fr"] for lien in liens_de("C14")])
        self.assertEqual((releve["miseAJour"], releve["bouton"]), (None, False))
        self.assertEqual(releve["principe"], [PHRASE_D182])
        self.assertEqual(releve["natureSource"], "obligation")
        self.assertIsNone(MOT_CONFORME.search(releve["page"]))


class TestCatalogueEcranServeur(CasCatalogueEcran):
    """Mode serveur (copie du jeu de démo, CSV relus) : création depuis C14, mise à jour proposée puis reprise."""

    def ouvrir_technicien(self, serveur, route):
        """Seconde page, profil Technicien, écran en anglais (le contenu du catalogue reste en français)."""
        contexte = self.navigateur.new_context(locale="en-GB", viewport={"width": 1280, "height": 800})
        self.addCleanup(contexte.close)
        contexte.add_init_script("try { localStorage.setItem('prevo.langue', 'en'); } catch (erreur) {}")
        technicien = next(ligne["id"] for ligne in lire_table(serveur.dossier, "techniciens.csv"))
        preregler_profil(contexte, "technicien", nom="Technicien", technicien_id=technicien)
        page = contexte.new_page()
        self.surveiller(page)
        page.goto(serveur.url + "/" + route)
        attendre_pret(page)
        page.wait_for_selector("#contenu .controles-source")
        return page

    def test_cree_depuis_c14_puis_mise_a_jour_proposee_et_reprise_sur_un_clic(self):
        with ServeurPrevo() as serveur:
            self.dossier = serveur.dossier
            equipement = next(ligne["id"] for ligne in lire_table(serveur.dossier, "equipements.csv")
                              if ligne["actif"] != "0" and ligne["statut"] != "rebut")
            preregler_profil(self.contexte, "responsable", nom="Responsable")
            self.page.goto(serveur.url + "/#/controles/nouveau?equipement=" + equipement)
            attendre_pret(self.page)
            self.page.wait_for_load_state("networkidle")
            self.page.wait_for_selector("#form-controle [name=catalogue_id]")
            self.choisir("C14")
            self.page.fill("#form-controle [name=organisme]", "Organisme T416")
            self.page.click("#form-controle button[type=submit]")
            self.page.wait_for_function("location.hash.startsWith('#/controles/CTR-')")
            identifiant = self.page.evaluate("decodeURIComponent(location.hash.split('/').pop())")
            ligne = self.controle(identifiant)
            self.assertEqual({cle: ligne[cle] for cle in PROVENANCE + ("periodicite_mois", "texte_reference")},
                             dict(SOURCE_C14, periodicite_mois="48", texte_reference=C14["reference"]))
            self.page.wait_for_selector("#contenu .controles-source")
            releve = self.page.evaluate(FICHE_JS)
            self.assertEqual((releve["provenance"], releve["miseAJour"], releve["principe"]),
                             (PROVENANCE_C14, None, [PHRASE_D182]))

            # La page reçoit le catalogue relu (C14 à 60 mois) : proposé, rien d'écrit.
            dossier = tempfile.mkdtemp(prefix="prevo-t416-")
            self.addCleanup(shutil.rmtree, dossier, True)
            script = catalogue_modifie(dossier)
            octets = self.octets()
            self.page.add_script_tag(content=script)
            self.page.evaluate("App.reafficher()")
            self.page.wait_for_selector("#controle-reprendre-catalogue")
            releve = self.page.evaluate(FICHE_JS)
            self.assertEqual(releve["miseAJour"], MISE_A_JOUR_C14)
            self.assertEqual(self.page.inner_text("#controle-reprendre-catalogue").strip(), "Reprendre ces valeurs")
            self.assertEqual(self.octets(), octets)

            # Technicien (écran en anglais) : la proposition, sans bouton.
            technicien = self.ouvrir_technicien(serveur, "#/controles/" + identifiant)
            technicien.add_script_tag(content=script)
            technicien.evaluate("App.reafficher()")
            technicien.wait_for_selector("#contenu .controles-mise-a-jour")
            anglais = technicien.evaluate(FICHE_JS)
            self.assertEqual(anglais["miseAJour"], "The Prévo catalogue was reviewed on 01/03/2027: it proposes"
                             " 60 months (you have 48 months). Nothing is changed without you.")
            self.assertFalse(anglais["bouton"])
            self.assertEqual(anglais["provenance"], "Prévo catalogue (C14), reviewed on 08/11/2026 — French regulations")
            self.assertEqual(anglais["principe"],
                             ["Prévo is an aid to keeping track; responsibility remains with the employer."])
            self.assertEqual(anglais["liens"], [lien + ["fr"] for lien in liens_de("C14")])
            self.assertEqual(self.octets(), octets)

            # Le clic du responsable : 60 mois, relecture du 01/03/2027 ; l'historique le dit.
            self.page.click("#controle-reprendre-catalogue")
            self.page.wait_for_function(
                "() => document.getElementById('toast').textContent.includes('Valeurs du catalogue reprises')")
            self.page.wait_for_function("() => !document.querySelector('#controle-reprendre-catalogue')")
            ligne = self.controle(identifiant)
            self.assertEqual({cle: ligne[cle] for cle in PROVENANCE + ("periodicite_mois",)},
                             dict(SOURCE_C14, catalogue_relu_le="2027-03-01", periodicite_mois="60"))
            releve = self.page.evaluate(FICHE_JS)
            self.assertEqual((releve["miseAJour"], releve["provenance"]),
                             (None, "Catalogue Prévo (C14), relu le 01/03/2027 — réglementation française"))
            self.assertEqual(releve["historique"][0], "modification : periodicite_mois, catalogue_relu_le"
                             " — valeurs du catalogue C14 relu le 01/03/2027 reprises")
            # Le technicien recharge : plus rien de proposé ; l'entrée du journal traduite.
            technicien.reload()
            attendre_pret(technicien)
            technicien.wait_for_selector("#contenu .controles-source")
            technicien.add_script_tag(content=script)
            technicien.evaluate("App.reafficher()")
            technicien.wait_for_selector("#contenu .controles-journal")
            anglais = technicien.evaluate(FICHE_JS)
            self.assertIsNone(anglais["miseAJour"])
            self.assertIn("values of catalogue entry C14 reviewed on 01/03/2027 applied", anglais["historique"][0])

    def controle(self, identifiant):
        return next(ligne for ligne in lire_table(self.dossier, "controles_reglementaires.csv")
                    if ligne["id"] == identifiant)

    def octets(self):
        return (self.dossier / "controles_reglementaires.csv").read_bytes()


if __name__ == "__main__":
    unittest.main()
