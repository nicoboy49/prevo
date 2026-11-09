"""CSV verrouillé par Excel au moment d'une écriture : parcours de bout en bout dans les deux modes (chantier
i18n-socle, tâche T231 ; messages de T232). T231 épinglait le comportement existant ; T232 (décision de Nicolas du
05/11) a changé le message, dans les deux modes : sans jargon, il nomme le fichier et dit quoi faire.

Excel garde ouvert le CSV qu'il affiche ; Windows refuse alors de le remplacer. Les pièces sont déjà testées une à une :
serveur.py remplacer_avec_essais (3 essais, puis 423 et message_fichier_verrouille(cible) ; tests/test_serveur.py,
test_fichier_ouvert_ailleurs_423), js/stockage-dossier.js ecrireFichier (NoModificationAllowedError ou
InvalidStateError → ErreurStockage qui nomme le fichier, nommerFichierOuvert ; repli dans traduireErreur ;
tests/test_stockage_dossier.py), js/stockage-serveur.js (un 423 rend le message du serveur). Ici, le parcours réel du
responsable dans l'écran, pour chaque mode :
    1. base d'essai ouverte (copie de f3-v1.2.0), fiche de EQ-0005 › « Modifier », désignation changée ;
    2. equipements.csv verrouillé, puis « Enregistrer » ;
    3. un message clair, dans le toast d'erreur (zone #toast, role="status", classes « erreur » et « visible » ; ni
       fenêtre ni bandeau), texte exact ci-dessous ; le formulaire reste ouvert, avec toute la saisie, et son bouton
       redevient utilisable ; aucun fichier changé à l'octet (serveur : tout le dossier de données, donc aucun fichier
       temporaire laissé ; dossier : tout l'OPFS, verrou.txt mis à part) ; journal.csv inchangé : l'essai refusé n'y
       laisse aucune ligne (Donnees.modifier n'écrit le journal qu'après une écriture réussie) ;
    4. déverrouillé, « Enregistrer » à nouveau : toast « Équipement enregistré. », retour à la fiche ; equipements.csv
       porte la nouvelle désignation, toutes ses autres lignes identiques à l'octet (et les autres cellules de
       EQ-0005) ; journal.csv : exactement UNE ligne ajoutée à la fin (equipements, EQ-0005, « modification :
       designation — modification de l'équipement »), aucun doublon ; aucun autre CSV de données changé.

    a. TestVerrouServeur : ServeurPrevo sur une copie ; verrou RÉEL : le test tient open(equipements.csv, 'r+b')
       pendant l'enregistrement (comme test_serveur : Windows refuse alors os.replace) ; le serveur essaie 3 fois puis
       répond 423. Message montré (T232) :
       « Le fichier « equipements.csv » est ouvert dans Excel ou un autre logiciel : fermez-le, puis réessayez. »
    b. TestVerrouDossier : dossier simulé (OPFS du navigateur de test, installer_dossier_simule). Le refus du
       navigateur est SIMULÉ sur le seul fichier <dossier>/equipements.csv (FileSystemFileHandle.createWritable remplacé
       avant le chargement de la page) : NoModificationAllowedError au createWritable, puis, dans un second test,
       InvalidStateError au write (les deux noms d'erreur que Prévo attribue à un fichier ouvert dans Excel ;
       le refus est vu une seule fois : aucun nouvel essai automatique). Le vrai verrou d'Excel n'est pas reproductible
       en automatique dans ce mode : il faudrait le sélecteur de dossier natif (showDirectoryPicker sur un vrai dossier
       du disque), qu'aucun test sans personne devant l'écran ne peut passer, et l'OPFS ne voit pas les verrous de
       Windows. Message montré (T232) : le même que celui du serveur, mot pour mot.

Constat de T231, corrigé par T232 : les anciens messages ne nommaient pas le fichier à fermer (equipements.csv) et, dans
le mode dossier, « (enregistrement de la table) » était un terme technique.

Règle numéro un : jamais de données réelles (copie du jeu tests/fixtures/formats/f3-v1.2.0 dans un dossier temporaire,
ou dans l'OPFS du navigateur de test).

Lancer depuis la racine du projet (à travers le verrou du navigateur) :
    py -X utf8 -m unittest discover -s tests -p "test_fichier_verrouille.py" -v
"""
import re
import unittest

from commun import ServeurPrevo
from test_recette_socle import (EQUIPEMENT, ERREUR_TABLE_DU_FORMAT_4_ABSENTE, NOM_DOSSIER, CasRecetteSocle,
                                csv_de_la_racine, fichiers_de, fichiers_du_jeu, lire_table)

JEU = "f3-v1.2.0"
FICHIER = "equipements.csv"
JOURNAL = "journal.csv"
VERROU_DU_DOSSIER = "verrou.txt"        # présence du poste, réécrit de temps en temps (mode dossier) : non comparé
NOUVELLE_DESIGNATION = "Pompe de refroidissement (essai Excel)"

# Textes attendus (T232, texte validé par Nicolas) : le même dans les deux modes, avec le vrai nom du fichier.
MESSAGE_SERVEUR = ("Le fichier « equipements.csv » est ouvert dans Excel ou un autre logiciel : fermez-le, puis "
                   "réessayez.")
MESSAGE_DOSSIER = MESSAGE_SERVEUR
SUCCES = "Équipement enregistré."
ACTION_DU_JOURNAL = "modification : designation — modification de l'équipement"

ROUTE_FICHE = "#/equipement/%s" % EQUIPEMENT
ROUTE_FORMULAIRE = ROUTE_FICHE + "/modifier"
BOUTON = "#parc-formulaire button[type=submit]"
# Chromium note en console.error la réponse 423 du serveur : c'est l'essai refusé, attendu.
ERREUR_423 = re.compile(r"status of 423")

# La saisie telle qu'on la voit : chaque champ du formulaire, le bouton, l'écran.
SAISIE_JS = """() => {
  const f = document.querySelector('#parc-formulaire');
  if (!f) return null;
  const champs = {};
  for (const c of f.elements) {
    if (!c.name || c.type === 'file') continue;
    champs[c.name] = (c.type === 'checkbox' || c.type === 'radio') ? c.checked : c.value;
  }
  const bouton = f.querySelector('button[type=submit]');
  return { champs: champs, boutonActif: !bouton.disabled, hash: location.hash, visible: f.offsetParent !== null };
}"""

# Où le message apparaît : zone des toasts (UI.toast), fenêtres ouvertes, bandeaux de l'application.
AFFICHAGE_JS = """() => {
  const zone = document.getElementById('toast');
  return { texte: zone ? zone.textContent.replace(/\\s+/g, ' ').trim() : null,
    classes: zone ? Array.from(zone.classList).sort() : [], role: zone ? zone.getAttribute('role') : null,
    fenetres: document.querySelectorAll('dialog[open]').length,
    bandeaux: Array.from(document.querySelectorAll('#alertes-app > *'))
      .map((e) => e.textContent.replace(/\\s+/g, ' ').trim()) };
}"""

BOUTON_ACTIF_JS = "(s) => { const b = document.querySelector(s); return Boolean(b) && !b.disabled; }"

# Mode dossier : refus du navigateur simulé sur UN fichier. window.__verrouExcel = { chemin: '<dossier>/<fichier>',
# erreur: nom de la DOMException, etape: 'createWritable' | 'write', refus: 0 } ; null : plus de verrou. Le fichier visé
# est reconnu par son chemin dans l'OPFS (resolve) : la copie de la sauvegarde du jour, du même nom, n'est pas visée.
REFUS_SIMULE_JS = """(() => {
  if (typeof FileSystemFileHandle === 'undefined') return;
  const createWritableReel = FileSystemFileHandle.prototype.createWritable;
  async function vise(poignee, verrou) {
    if (!verrou || poignee.name !== verrou.chemin.split('/').pop()) return false;
    const chemin = await (await navigator.storage.getDirectory()).resolve(poignee);
    return Boolean(chemin) && chemin.join('/') === verrou.chemin;
  }
  function refus(verrou) {
    verrou.refus += 1;
    return new DOMException('Fichier verrouillé par un autre programme (refus simulé, T231).', verrou.erreur);
  }
  FileSystemFileHandle.prototype.createWritable = async function (options) {
    const verrou = window.__verrouExcel;
    if (!(await vise(this, verrou))) return createWritableReel.call(this, options);
    if (verrou.etape === 'createWritable') throw refus(verrou);
    const flux = await createWritableReel.call(this, options);
    flux.write = async () => { throw refus(verrou); };
    return flux;
  };
})();"""


def lignes_physiques(octets):
    return octets.split(b"\r\n")


# ---------------------------------------------------------------------------
# Gestes et vérifications communs
# ---------------------------------------------------------------------------

class CasFichierVerrouille(CasRecetteSocle):

    def nombre_de_toasts(self):
        return self.page.evaluate("(window.__toasts || []).length")

    def ouvrir_le_formulaire(self):
        """Fiche de EQ-0005 › « Modifier » › désignation changée ; rend la saisie vue."""
        self.aller(ROUTE_FICHE, "a[href='%s']" % ROUTE_FORMULAIRE)
        self.page.click("a[href='%s']" % ROUTE_FORMULAIRE)
        self.page.wait_for_selector("#parc-formulaire [name=designation]")
        self.assertNotEqual(self.page.input_value("#parc-formulaire [name=designation]"), NOUVELLE_DESIGNATION)
        self.page.fill("#parc-formulaire [name=designation]", NOUVELLE_DESIGNATION)
        saisie = self.page.evaluate(SAISIE_JS)
        self.assertEqual(saisie["champs"]["designation"], NOUVELLE_DESIGNATION)
        self.assertEqual((saisie["hash"], saisie["boutonActif"], saisie["visible"]), (ROUTE_FORMULAIRE, True, True))
        return saisie

    def enregistrer_refuse(self, message, saisie):
        """« Enregistrer » pendant le verrou : un seul message, le texte attendu, dans le toast d'erreur (ni fenêtre ni
        bandeau) ; puis la même saisie, le bouton de nouveau utilisable, l'écran pas quitté."""
        debut = self.nombre_de_toasts()
        bandeaux = self.page.evaluate(AFFICHAGE_JS)["bandeaux"]
        self.page.click(BOUTON)
        self.page.wait_for_function("(d) => (window.__toasts || []).length > d", arg=debut)
        self.page.wait_for_function(BOUTON_ACTIF_JS, arg=BOUTON)
        self.assertEqual(self.page.evaluate("window.__toasts")[debut:], [message])
        affichage = self.page.evaluate(AFFICHAGE_JS)
        self.assertEqual(affichage["texte"], message)
        self.assertEqual(affichage["role"], "status")
        self.assertIn("erreur", affichage["classes"])
        self.assertIn("visible", affichage["classes"])
        self.assertEqual(affichage["fenetres"], 0, "une fenêtre s'est ouverte")
        self.assertEqual(affichage["bandeaux"], bandeaux, "un bandeau a changé")
        self.assertEqual(self.page.evaluate(SAISIE_JS), saisie, "saisie perdue ou changée après le refus")

    def enregistrer_avec_succes(self):
        """« Enregistrer » une fois déverrouillé : retour à la fiche et « Équipement enregistré. » (Donnees.modifier a
        rendu la main : la table ET le journal sont écrits)."""
        debut = self.nombre_de_toasts()
        self.page.click(BOUTON)
        self.page.wait_for_function("(h) => location.hash === h", arg=ROUTE_FICHE)
        self.page.wait_for_function("([d, m]) => (window.__toasts || []).slice(d).includes(m)", arg=[debut, SUCCES])
        self.page.wait_for_load_state("networkidle")

    def verifier_rien_ecrit(self, avant, apres, ignores=()):
        """Aucun fichier ajouté, supprimé ni changé à l'octet (hors `ignores`)."""
        noms_avant = sorted(nom for nom in avant if nom not in ignores)
        noms_apres = sorted(nom for nom in apres if nom not in ignores)
        self.assertEqual(noms_apres, noms_avant, "fichiers ajoutés ou supprimés par l'essai refusé")
        self.assertEqual([nom for nom in noms_avant if apres[nom] != avant[nom]], [],
                         "fichiers changés par l'essai refusé")

    def verifier_apres_nouvel_essai(self, avant, apres):
        """equipements.csv : seule la désignation de EQ-0005 a changé ; journal.csv : une ligne ajoutée à la fin, celle
        de cette modification ; aucun autre CSV de données changé."""
        changes = sorted(nom for nom, octets in csv_de_la_racine(avant).items() if apres.get(nom) != octets)
        self.assertEqual(changes, [FICHIER, JOURNAL])

        # equipements.csv : une seule ligne différente (celle de EQ-0005), toutes les autres identiques à l'octet.
        physiques_avant, physiques_apres = lignes_physiques(avant[FICHIER]), lignes_physiques(apres[FICHIER])
        self.assertEqual(len(physiques_apres), len(physiques_avant))
        differentes = [rang for rang, (a, b) in enumerate(zip(physiques_avant, physiques_apres)) if a != b]
        self.assertEqual(len(differentes), 1, differentes)
        self.assertTrue(physiques_avant[differentes[0]].startswith(EQUIPEMENT.encode("ascii") + b";"))
        entete, lignes_avant = lire_table(avant[FICHIER])
        entete_apres, lignes_apres = lire_table(apres[FICHIER])
        self.assertEqual(entete_apres, entete)
        self.assertEqual(len(lignes_apres), len(lignes_avant))
        rang = [ligne[0] for ligne in lignes_avant].index(EQUIPEMENT)
        ancienne, nouvelle = dict(zip(entete, lignes_avant[rang])), dict(zip(entete, lignes_apres[rang]))
        self.assertEqual(nouvelle["designation"], NOUVELLE_DESIGNATION)
        self.assertEqual({nom: valeur for nom, valeur in nouvelle.items() if nom != "designation"},
                         {nom: valeur for nom, valeur in ancienne.items() if nom != "designation"})

        # journal.csv : complété (pas réécrit), une seule ligne nouvelle, aucune pour l'essai refusé.
        self.assertTrue(apres[JOURNAL].startswith(avant[JOURNAL]), "journal.csv réécrit au lieu d'être complété")
        entete_journal, anciennes = lire_table(avant[JOURNAL])
        _, toutes = lire_table(apres[JOURNAL])
        ajoutees = [dict(zip(entete_journal, ligne)) for ligne in toutes[len(anciennes):]]
        self.assertEqual([(l["table"], l["id_ligne"], l["action"]) for l in ajoutees],
                         [("equipements", EQUIPEMENT, ACTION_DU_JOURNAL)])
        self.assertEqual(len({ligne[0] for ligne in toutes}), len(toutes), "identifiant du journal en double")


# ---------------------------------------------------------------------------
# a. Mode serveur : verrou réel tenu par le test
# ---------------------------------------------------------------------------

class TestVerrouServeur(CasFichierVerrouille):

    def test_csv_ouvert_ailleurs_message_saisie_gardee_rien_ecrit_puis_nouvel_essai(self):
        self.autoriser_erreur(ERREUR_423)
        # Jeu au format 3 : le passage au format 4 ne crée ni garanties ni contrats_prestataires (CONCEPTION-L1 §3.3).
        self.autoriser_erreur(ERREUR_TABLE_DU_FORMAT_4_ABSENTE)
        with ServeurPrevo(source=self.jeu(JEU)) as serveur:
            self.ouvrir_serveur(serveur.url, "responsable")
            saisie = self.ouvrir_le_formulaire()
            avant = fichiers_de(serveur.dossier)
            with open(serveur.dossier / FICHIER, "r+b"):        # Excel tient le fichier : os.replace est refusé
                self.enregistrer_refuse(MESSAGE_SERVEUR, saisie)
                self.page.wait_for_load_state("networkidle")
                pendant = fichiers_de(serveur.dossier)
            self.verifier_rien_ecrit(avant, pendant)
            self.verifier_rien_ecrit(avant, fichiers_de(serveur.dossier))
            self.assertEqual([nom for nom in pendant if nom.endswith(".tmp")], [], "fichier temporaire laissé")

            self.enregistrer_avec_succes()
            apres = fichiers_de(serveur.dossier)
            self.page.goto("about:blank")                  # la page quitte le serveur avant son arrêt
        self.verifier_apres_nouvel_essai(avant, apres)


# ---------------------------------------------------------------------------
# b. Mode dossier : refus du navigateur simulé (OPFS)
# ---------------------------------------------------------------------------

class TestVerrouDossier(CasFichierVerrouille):

    def setUp(self):
        super().setUp()
        self.demarrer_statique()
        self.contexte.add_init_script(REFUS_SIMULE_JS)

    def parcours(self, erreur, etape):
        self.ouvrir_dossier(fichiers_du_jeu(JEU), "responsable")
        saisie = self.ouvrir_le_formulaire()
        avant = self.instantane()
        self.page.evaluate("(v) => { window.__verrouExcel = v; }",
                           {"chemin": NOM_DOSSIER + "/" + FICHIER, "erreur": erreur, "etape": etape, "refus": 0})
        self.enregistrer_refuse(MESSAGE_DOSSIER, saisie)
        self.assertEqual(self.page.evaluate("window.__verrouExcel.refus"), 1, "le refus simulé n'a pas servi une fois")
        self.verifier_rien_ecrit(avant, self.instantane(), ignores=(VERROU_DU_DOSSIER,))

        self.page.evaluate("() => { window.__verrouExcel = null; }")
        self.enregistrer_avec_succes()
        self.verifier_apres_nouvel_essai(avant, self.instantane())

    def test_no_modification_allowed_au_createwritable_message_saisie_gardee_puis_nouvel_essai(self):
        self.parcours("NoModificationAllowedError", "createWritable")

    def test_invalid_state_au_write_message_saisie_gardee_puis_nouvel_essai(self):
        self.parcours("InvalidStateError", "write")


if __name__ == "__main__":
    unittest.main()
