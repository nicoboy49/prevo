"""Imports après la relecture critique du 12/11/2026 (lot L7, tâche T507 ; rapport R3-zip-import.md).

Défauts fermés :
  - import tableur : « 1.200 » et « 1,200 » (un seul séparateur, puis exactement trois chiffres) étaient lus 1,2 sans
    rien dire (montant annuel d'un contrat, coût de l'arrêt…). La lecture ne change pas (un fichier de Prévo s'écrit
    avec un point) ; l'aperçu porte maintenant une note « lu comme 1,2, et non 1 200 », la ligne reste importable ;
  - import tableur des réserves : la note « Levée vide : « non » par défaut » restait sur une réserve que l'import crée
    levée (date de levée remplie) ;
  - import tableur : une garantie ou un contrat retiré (actif = 0) réimporté était dit « identique » sans un mot ;
  - import ZIP en mode serveur : une image dont le contenu n'est pas celui que son nom annonce (acceptée par le mode
    dossier, refusée par le serveur : 400) arrêtait l'import à mi-chemin, documents précédents déjà copiés ; elle est
    maintenant sautée, nommée dans le message de fin et au journal, et l'import va au bout ;
  - import ZIP : le refus « nom déjà pris » de l'adaptateur n'était reconnu qu'en français (essai du nom « -2 »).

Les trois premiers sans navigateur : les scripts du dépôt (ceux d'index.html, dans son ordre, jusqu'aux modules de
l'import) sont chargés tels quels dans un contexte `vm` de Node, données passées à StockageDemo.creer (jeu écrit à
la main ici, aucune donnée réelle). Les deux derniers dans la page, sur serveur.py (ServeurPrevo, dossiers
temporaires) : à lancer par le verrou des navigateurs.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_imports_relecture.py" -v
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from commun import ServeurPrevo, attendre_pret
from test_zip_import import (BOUTON_REMPLACER, CasImport, TestServeur, ecrire_zip, fichiers_demo, fichiers_du_jeu,
                             instantane, lire_csv, octets_pdf, octets_png)

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HARNAIS = r"""
const vm = require('vm'), fs = require('fs'), path = require('path');
const RACINE = process.argv[2];
const page = fs.readFileSync(path.join(RACINE, 'index.html'), 'utf8');
let SCRIPTS = [...page.matchAll(/<script src="([^"]+)"/g)].map((m) => m[1])
  .filter((s) => !/prechargement|qrcode|jsQR|i18n-chargeur|js\/app\.js/.test(s));
SCRIPTS = SCRIPTS.slice(0, SCRIPTS.indexOf('js/modules/import-ecrans.js'));
const csv = (entete, lignes) => [entete].concat(lignes).join('\r\n') + '\r\n';

async function contexte(tables) {
  const stock = new Map();
  const ctx = { console, setTimeout, clearTimeout, TextEncoder, TextDecoder, Blob, EventTarget, CustomEvent, Event, URL,
    URLSearchParams, Intl, structuredClone, queueMicrotask, crypto: require('crypto').webcrypto,
    localStorage: { getItem: (k) => (stock.has(k) ? stock.get(k) : null), setItem: (k, v) => stock.set(k, String(v)), removeItem: (k) => stock.delete(k) },
    navigator: { language: 'fr-FR', languages: ['fr-FR'], userAgent: 'node' },
    location: { protocol: 'file:', hash: '', search: '', href: 'file:///x' } };
  const el = () => new Proxy(function () {}, { get: (t, p) => (p === Symbol.toPrimitive ? () => '' : p === 'length' ? 0 : el()), apply: () => el(), set: () => true });
  ctx.document = { documentElement: { lang: 'fr', setAttribute() {}, getAttribute() { return 'fr'; }, dataset: {}, style: {} },
    addEventListener() {}, querySelector: () => null, querySelectorAll: () => [], createElement: () => el(), body: el(), head: el(), currentScript: null };
  ctx.window = ctx; ctx.self = ctx; ctx.globalThis = ctx; ctx.addEventListener = () => {};
  ctx.matchMedia = () => ({ matches: false, addEventListener() {} });
  vm.createContext(ctx);
  vm.runInContext("var App = { mode: 'demo', estResponsable: () => true, estTechnicien: () => false, comptesExiges: () => false, raisonErreur: (e) => e.message, definirTitre() {} };", ctx, { filename: 'app-factice' });
  for (const s of SCRIPTS) vm.runInContext(fs.readFileSync(path.join(RACINE, s), 'utf8'), ctx, { filename: s });
  ctx.tables = tables;
  const run = (code) => vm.runInContext(code, ctx);
  await run("Donnees.initialiser(StockageDemo.creer(tables), { poste: 'P', profil: 'R' }); Donnees.chargerTout()");
  // Aperçu d'une grille sans fichier, chaque colonne au champ de même nom → lignes { numero, action, raisons }.
  run(`var grille = (type, champs, lignes) => {
    const correspondance = champs.map((champ, colonne) => ({ colonne, entete: champ, champ, statut: 'sure', raison: '' }));
    const apercu = Import.preparer(type, lignes, correspondance, { mettreAJour: true, maintenant: '2026-11-12 10:00' });
    return apercu.lignes.map((l) => ({ numero: l.numero, action: l.action, raisons: Array.from(l.raisons) }));
  };`);
  return run;
}

const BASE = () => ({
  fournisseurs: csv('id;nom', ['FOU-0001;Presta']),
  equipements: csv('id;repere;designation;statut;actif', ['EQ-0001;CP-01;Compresseur;en service;1']),
  controles_reglementaires: csv('id;equipement_id;nature;periodicite_mois;derniere_date;prochaine_date',
    ['CTR-0001;EQ-0001;Inspection du réservoir;12;2025-04-03;2026-04-03']),
  reserves_controle: csv('id;controle_id;date_controle;texte;gravite;echeance_levee;levee;date_levee;commentaire_levee;ot_id', []),
  garanties: csv('id;equipement_id;fournisseur_id;date_debut;date_fin;conditions;document;actif', [
    'GAR-0001;EQ-0001;;2024-12-01;2028-12-31;;;0', 'GAR-0002;EQ-0001;;2024-12-01;2029-06-30;;;1']),
  contrats_prestataires: csv('id;fournisseur_id;objet;equipement_ids;perimetre;date_debut;date_fin;preavis_mois;reconduction_tacite;reconduction_mois;montant_annuel;document;actif', [
    'CTP-0001;FOU-0001;Contrat retiré;;;2025-01-01;2027-12-31;;0;;;;0', 'CTP-0002;FOU-0001;Contrat suivi;;;2025-01-01;2027-12-31;;0;;;;1']),
  journal: csv('id;date_heure;poste;utilisateur;table;id_ligne;action', []),
});

(async () => {
  const run = await contexte(BASE());
  const sortie = {};
  sortie.nombres = run(`grille('contrats', ['prestataire', 'objet', 'date_fin', 'montant_annuel'], [
    ['Presta', 'A', '31/12/2027', '1.200'], ['Presta', 'B', '31/12/2027', '1,200'], ['Presta', 'C', '31/12/2027', '1200'],
    ['Presta', 'D', '31/12/2027', '1 200,50'], ['Presta', 'E', '31/12/2027', '12,5'], ['Presta', 'F', '31/12/2027', '0,125'],
    ['Presta', 'G', '31/12/2027', '12.345'], ['Presta', 'H', '31/12/2027', '1234.567']])`);
  sortie.arret = run(`grille('equipements', ['repere', 'designation', 'cout_arret_h', 'valeur_remplacement'], [['PR-09', 'Presse', '2.500', '85,000']])`);
  sortie.libelles = run("({ montant: Import.TYPES.contrats.champs.find((c) => c.cle === 'montant_annuel').libelle,"
    + " arret: Import.TYPES.equipements.champs.find((c) => c.cle === 'cout_arret_h').libelle,"
    + " valeur: Import.TYPES.equipements.champs.find((c) => c.cle === 'valeur_remplacement').libelle,"
    + " levee: Import.TYPES.reserves.champs.find((c) => c.cle === 'levee').libelle })");
  sortie.reserves = run(`grille('reserves', ['equipement', 'nature', 'date_controle', 'texte', 'levee', 'date_levee', 'commentaire_levee'], [
    ['CP-01', 'Inspection du réservoir', '03/04/2025', 'Soupape à retarer', '', '20/04/2025', 'retarée'],
    ['CP-01', 'Inspection du réservoir', '03/04/2025', 'Purgeur à remplacer', '', '', '']])`);
  sortie.garanties = run(`grille('garanties', ['equipement', 'date_fin'], [['CP-01', '31/12/2028'], ['CP-01', '30/06/2029']])`);
  sortie.contrats = run(`grille('contrats', ['prestataire', 'objet', 'date_fin', 'perimetre'], [
    ['Presta', 'Contrat retiré', '31/12/2027', ''], ['Presta', 'Contrat retiré', '', ''], ['Presta', 'Contrat suivi', '31/12/2027', '']])`);
  sortie.contratsChange = run(`grille('contrats', ['prestataire', 'objet', 'date_fin', 'perimetre'], [['Presta', 'Contrat retiré', '31/12/2027', 'Deux visites']])`);
  sortie.retiree = run("I18n.t('import.decider.fiche_retiree')");
  const octets = (debut) => "new Uint8Array([" + debut.concat([1, 2, 3, 4, 5, 6, 7, 8, 9]).join(',') + "])";
  const PNG = [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A], JPG = [0xFF, 0xD8, 0xFF, 0xE0], GIF = [0x47, 0x49, 0x46, 0x38, 0x39, 0x61];
  const WEBP = [0x52, 0x49, 0x46, 0x46, 0, 0, 0, 0, 0x57, 0x45, 0x42, 0x50], RIFF = [0x52, 0x49, 0x46, 0x46, 0, 0, 0, 0, 0x57, 0x41, 0x56, 0x45];
  sortie.images = {};
  for (const [nom, debut] of [['photo.jpg', JPG], ['photo.JPEG', JPG], ['photo-pompe.jpg', PNG], ['plan.png', PNG], ['plan.png', JPG],
    ['anim.gif', GIF], ['anim.gif', PNG], ['vue.webp', WEBP], ['faux.webp', RIFF], ['notice.pdf', PNG], ['sans-extension', JPG], ['vide.png', []]]) {
    sortie.images[nom + ' <- ' + debut.slice(0, 4).join(',')] = run("typeof ZipDonnees.imageRefusee !== 'function' ? null : ZipDonnees.imageRefusee(" + JSON.stringify(nom) + ", " + (debut.length ? octets(debut) : 'new Uint8Array(0)') + ")");
  }
  process.stdout.write(JSON.stringify(sortie));
})().catch((erreur) => { console.error(erreur && erreur.stack || erreur); process.exit(1); });
"""

_SORTIE = {}


def harnais():
    """Lance le harnais Node une fois pour toute la classe → dictionnaire des sorties."""
    if not _SORTIE:
        dossier = tempfile.mkdtemp(prefix="prevo-imports-relecture-")
        try:
            chemin = os.path.join(dossier, "harnais.js")
            with open(chemin, "w", encoding="utf-8") as fichier:
                fichier.write(HARNAIS)
            rendu = subprocess.run(["node", chemin, RACINE], capture_output=True, text=True, encoding="utf-8", timeout=120)
            if rendu.returncode != 0:
                raise AssertionError("harnais Node : " + rendu.stderr[-2000:])
            _SORTIE.update(json.loads(rendu.stdout))
        finally:
            shutil.rmtree(dossier, ignore_errors=True)
    return _SORTIE


def par_numero(lignes):
    return {ligne["numero"]: ligne for ligne in lignes}


@unittest.skipUnless(shutil.which("node"), "Node absent")
class TestImportTableurSansNavigateur(unittest.TestCase):

    def test_nombre_a_trois_chiffres_apres_son_seul_separateur_note_lu_comme_ligne_importable(self):
        sortie = harnais()
        lignes = par_numero(sortie["nombres"])
        montant = sortie["libelles"]["montant"]
        for numero, ecrit in ((2, "1.200"), (3, "1,200")):
            self.assertEqual(lignes[numero]["action"], "creer", lignes[numero])        # une note, pas un refus
            self.assertEqual(len(lignes[numero]["raisons"]), 1, lignes[numero])
            self.assertRegex(lignes[numero]["raisons"][0], r"^%s : « %s » lu comme 1,2, et non 1\s200 : vérifiez le "
                             r"séparateur$" % (re.escape(montant), re.escape(ecrit)))
        self.assertRegex(lignes[8]["raisons"][0], r"« 12\.345 » lu comme 12,345, et non 12\s345 ")
        # Sans ambiguïté : aucune note (entier, milliers à espace et virgule, une décimale, « 0,125 », quatre chiffres avant).
        for numero in (4, 5, 6, 7, 9):
            self.assertEqual((lignes[numero]["action"], lignes[numero]["raisons"]), ("creer", []), lignes[numero])

    def test_cout_de_l_arret_et_valeur_de_remplacement_portent_la_meme_note(self):
        sortie = harnais()
        ligne = sortie["arret"][0]
        self.assertEqual(ligne["action"], "creer", ligne)
        notes = [raison for raison in ligne["raisons"] if "lu comme" in raison]
        self.assertEqual(len(notes), 2, ligne)
        self.assertRegex(notes[0], r"^%s : « 85,000 » lu comme 85, et non 85\s000 " % re.escape(sortie["libelles"]["valeur"]))
        self.assertRegex(notes[1], r"^%s : « 2\.500 » lu comme 2,5, et non 2\s500 " % re.escape(sortie["libelles"]["arret"]))

    def test_note_dans_les_cinq_langues(self):
        for langue in ("fr", "en", "tr", "it", "pt-PT"):
            with open(os.path.join(RACINE, "js", "i18n", langue + ".js"), encoding="utf-8") as fichier:
                texte = fichier.read()
            for cle in ("import.convertir.nombre_lu_comme", "import.decider.fiche_retiree", "zip.importer.documents_non_repris"):
                self.assertEqual(texte.count("'%s':" % cle), 1, (langue, cle))

    def test_reserve_creee_levee_par_sa_date_sans_la_note_non_par_defaut(self):
        sortie = harnais()
        lignes = par_numero(sortie["reserves"])
        note = "%s vide : « non » par défaut" % sortie["libelles"]["levee"]
        self.assertEqual((lignes[2]["action"], lignes[2]["raisons"]), ("creer", []))          # levée déduite de la date
        self.assertEqual((lignes[3]["action"], lignes[3]["raisons"]), ("creer", [note]))      # non levée : la note reste

    def test_garantie_ou_contrat_retire_reimporte_dit_retire(self):
        sortie = harnais()
        retiree = sortie["retiree"]
        self.assertEqual(retiree, "déjà dans Prévo, mais retirée : l'import ne la rétablit pas")
        garanties = par_numero(sortie["garanties"])
        self.assertEqual((garanties[2]["action"], garanties[2]["raisons"]), ("identique", [retiree]))
        self.assertEqual((garanties[3]["action"], garanties[3]["raisons"]), ("identique", []))       # fiche active : rien
        contrats = par_numero(sortie["contrats"])
        self.assertEqual((contrats[2]["action"], contrats[2]["raisons"]), ("identique", [retiree]))
        self.assertEqual(contrats[3]["action"], "refusee")                                         # doublon du fichier
        self.assertEqual((contrats[4]["action"], contrats[4]["raisons"]), ("identique", []))
        change = sortie["contratsChange"][0]                    # mise à jour d'une fiche retirée : dite aussi, elle le reste
        self.assertEqual((change["action"], change["raisons"]), ("mettre_a_jour", [retiree]))

    def test_image_refusee_memes_signatures_que_le_serveur(self):
        images = harnais()["images"]
        self.assertEqual(images, {
            "photo.jpg <- 255,216,255,224": False, "photo.JPEG <- 255,216,255,224": False,
            "photo-pompe.jpg <- 137,80,78,71": True, "plan.png <- 137,80,78,71": False, "plan.png <- 255,216,255,224": True,
            "anim.gif <- 71,73,70,56": False, "anim.gif <- 137,80,78,71": True,
            "vue.webp <- 82,73,70,70": False, "faux.webp <- 82,73,70,70": True,       # RIFF sans « WEBP » aux octets 8 à 11
            "notice.pdf <- 137,80,78,71": False, "sans-extension <- 255,216,255,224": False, "vide.png <- ": True})


# ---------------------------------------------------------------------------
# Import ZIP en mode serveur (navigateur : par le verrou)
# ---------------------------------------------------------------------------

# Premier envoi refusé « nom déjà pris » par l'adaptateur, dans la langue de l'écran ; noms demandés gardés.
NOM_PRIS_UNE_FOIS_JS = """() => {
  window.nomsDemandes = [];
  const ecrireDocument = App.adaptateur.ecrireDocument;
  App.adaptateur.ecrireDocument = async function (nom, blob) {
    window.nomsDemandes.push(nom);
    if (window.nomsDemandes.length === 1) throw new Donnees.ErreurStockage(I18n.t('socle.creer.document_porte_deja_nom'));
    return ecrireDocument.call(this, nom, blob);
  };
}"""


class TestImportZipServeur(CasImport):
    ouvrir_parametres = TestServeur.ouvrir_parametres
    dossier_source = TestServeur.dossier_source

    def test_serveur_image_au_contenu_refuse_sautee_et_dite_l_import_va_au_bout(self):
        f3 = {chemin: o for chemin, o in fichiers_du_jeu("f3-v1.2.0").items() if chemin.endswith(".csv")}
        documents = {"a-notice.pdf": octets_pdf("notice"), "b-photo-pompe.jpg": octets_png("un PNG renommé en jpg"),
                     "c-plan.png": octets_png("plan")}
        chemin_zip = ecrire_zip(self.temporaire / "image.zip",
                                dict(f3, **{"documents/" + nom: o for nom, o in documents.items()}))
        with ServeurPrevo() as serveur:
            page = self.ouvrir_parametres(serveur)
            self.choisir_zip(page, chemin_zip)
            self.assertEqual(self.confirmation(page)["documents"], 3)
            page.click(BOUTON_REMPLACER)
            message = self.texte_fenetre(page, "import-zip-termine")
            self.assertIn("2 documents (aucun document existant supprimé)", message)
            self.assertIn("1 document du ZIP n'a pas été repris, car son contenu n'est pas l'image que son nom annonce : "
                          "b-photo-pompe.jpg.", message)
            apres = instantane(serveur.dossier)
            presents = [o for chemin, o in apres.items() if chemin.startswith("documents/")]
            self.assertIn(documents["a-notice.pdf"], presents)
            self.assertIn(documents["c-plan.png"], presents)                 # le document suivant est bien écrit
            self.assertNotIn(documents["b-photo-pompe.jpg"], presents)
            derniere = lire_csv(apres["journal.csv"])[1][-1]
            self.assertRegex(derniere["action"], r"^import ZIP : image\.zip, \d+ tables, 2 documents ; non repris "
                             r"\(contenu qui n'est pas l'image annoncée\) : b-photo-pompe\.jpg ; sauvegarde ")
            # Les tables sont celles du ZIP (l'import est allé au bout).
            self.assertEqual(lire_csv(apres["equipements.csv"])[1][0]["id"], lire_csv(f3["equipements.csv"])[1][0]["id"])
            self.assertEqual(len(lire_csv(apres["equipements.csv"])[1]), len(lire_csv(f3["equipements.csv"])[1]))

    def test_serveur_nom_deja_pris_reconnu_en_anglais_le_nom_suivant_est_essaye(self):
        fichiers = fichiers_demo()
        fichiers["parametres.csv"] = fichiers["parametres.csv"].rstrip(b"\r\n") + b"\r\nlangue_defaut;en\r\n"
        source = self.dossier_source("anglaise", fichiers)
        f3 = {chemin: o for chemin, o in fichiers_du_jeu("f3-v1.2.0").items() if chemin.endswith(".csv")}
        notice = octets_pdf("notice")
        chemin_zip = ecrire_zip(self.temporaire / "nom.zip", dict(f3, **{"documents/a-notice.pdf": notice}))
        contexte = self.navigateur.new_context(locale="en-GB", viewport={"width": 1280, "height": 800})
        self.addCleanup(contexte.close)
        contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        with ServeurPrevo(source=source, comptes=True) as serveur:
            serveur.poser_session(contexte, "responsable")
            page = contexte.new_page()
            self.surveiller(page)
            page.goto(serveur.url + "/#/parametres")
            attendre_pret(page)
            self.assertEqual(page.evaluate("I18n.langue"), "en")
            page.evaluate(NOM_PRIS_UNE_FOIS_JS)
            self.choisir_zip(page, chemin_zip)
            self.confirmation(page)
            page.click("dialog button:has-text('Replace all the data')")
            self.texte_fenetre(page, "import-zip-termine")
            self.assertEqual(page.evaluate("window.nomsDemandes"), ["a-notice.pdf", "a-notice-2.pdf"])
            presents = [o for chemin, o in instantane(serveur.dossier).items() if chemin.startswith("documents/")]
            self.assertIn(notice, presents)


del CasImport, TestServeur            # classes de base : leurs tests ne sont pas rejoués ici


if __name__ == "__main__":
    unittest.main()
