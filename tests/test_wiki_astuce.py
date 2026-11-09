"""Champ « Astuce pour la prochaine fois » de l'OT (lot 6, tâche T116 ; ARCHITECTURE.md §20.2 et §20.9, D110).

Mode serveur (serveur.py sur une copie du jeu de démo, fichiers lus sur le disque), sauf le dernier test (démo
file://) :
    champ    : dans l'onglet Compte rendu, sous le compte rendu, libellé du schéma, aide mot pour mot sous le champ,
               facultatif, mêmes règles d'édition que le compte rendu ; en lecture seule, montré seulement s'il existe ;
    cloture  : une clôture technique sans astuce passe (RG4 inchangée : Ordres.verifierCloture et parcours) ;
    ecriture : l'astuce est écrite par « Enregistrer le compte rendu » avec les autres champs (une seule écriture, une
               entrée au journal), octets du CSV sur le disque, puis montrée telle quelle sur l'OT clôturé et
               trouvée par la recherche ;
    limite   : Wiki.SEUILS.astuceMax (500) caractères acceptés (comptés en caractères, ni en octets ni en unités
               UTF-16), 501 refusés avec un message clair, rien n'est écrit (ordres_travail.csv et journal.csv
               inchangés à l'octet, même avant une transition) ;
    export   : l'export ZIP contient l'astuce ;
    piege    : un texte piégé (<img onerror>) reste du texte, sur la fiche et dans un résultat de recherche ;
    demo     : au moins 45 OT de la démo portent une astuce ; elle est montrée sur leur fiche ;
    resultat : affichage d'un résultat « page » de la recherche (wiki-ecrans.js) : titre de la page en lien vers
               #/wiki/<lien canonique>, aussi pour le demandeur, extrait surligné, titre piégé gardé en texte.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_wiki_astuce.py" -v
"""
import csv
import io
import unittest
import zipfile

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, scenarios_demo, url_fichier

LIBELLE = "Astuce pour la prochaine fois"
AIDE = ("Ce qui vous aurait fait gagner du temps. Les consignes de sécurité restent dans la consignation "
        "de l'équipement.")
SCENARIOS = scenarios_demo()
OT_P1 = SCENARIOS["ot_p1_ouvert"]                   # En cours, P1
OT_EN_COURS = SCENARIOS["ot_statut_en_cours"]       # correctif « En cours »
OT_PREPARE = SCENARIOS["ot_statut_prepare"]         # correctif « Préparé » : compte rendu en lecture seule
CLOS_TECH = "Clôturé techniquement"
FORMULAIRE = "#form-compte-rendu"
BLOC = FORMULAIRE + ' .champ[data-champ="astuce"]'
CHAMP = FORMULAIRE + " [name=astuce]"
COMPTE_RENDU = "Filtre à huile remplacé, radiateur nettoyé, essai concluant."

# Rend clôturable un OT en cours, sauf le compte rendu et l'astuce (saisis par l'interface) : date de fin, codes,
# remise en service, un temps passé.
PREPARER_CLOTURE_JS = """async (otId) => {
  await Donnees.modifier('ordres_travail', (l) => { Object.assign(l.find((x) => x.id === otId), {
    date_fin: Donnees.maintenant(), symptome_code: 'S01', cause_code: 'C01', remede_code: 'R01', remise_service: '1' }); });
  await Donnees.modifier('ot_temps', (l, o) => { l.push({ id: o.nouvelId(l), ot_id: otId,
    technicien_id: 'TEC-0001', date: Donnees.aujourdhui(), heures: '1.5' }); });
}"""

# Place des blocs de l'onglet : le champ suit le compte rendu et précède la remise en service ; l'aide suit le champ.
ORDRE_JS = """() => {
  const bloc = (nom) => document.querySelector('#form-compte-rendu .champ[data-champ="' + nom + '"]');
  const apres = (a, b) => Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
  const astuce = bloc('astuce');
  return { apresCompteRendu: apres(bloc('compte_rendu'), astuce), avantRemise: apres(astuce, bloc('remise_service')),
           aideSousLeChamp: apres(astuce.querySelector('textarea'), astuce.querySelector('.aide')),
           large: astuce.classList.contains('large') };
}"""


def lignes_csv(octets):
    """Lignes (dictionnaires) d'un CSV de Prévo lu en octets : BOM, « ; », sauts de ligne des champs gardés."""
    return list(csv.DictReader(io.StringIO(octets.decode("utf-8-sig"), newline=""), delimiter=";"))


def cellule_csv(valeur):
    """Cellule écrite par Prévo (§3.1) : entre guillemets si « ; », « " », CR, LF ou espace au bord."""
    if any(signe in valeur for signe in ';"\r\n') or valeur[:1] in " \t" or valeur[-1:] in " \t":
        return '"' + valeur.replace('"', '""') + '"'
    return valeur


class CasAstuce(CasNavigateur):

    def ouvrir(self, serveur, route, profil="responsable", technicien_id=""):
        preregler_profil(self.contexte, profil, technicien_id=technicien_id)
        self.page.goto(serveur.url + "/" + route)
        attendre_pret(self.page)

    def aller(self, route):
        self.page.evaluate("(route) => { location.hash = route; }", route)

    def fiche(self, ot_id, onglet="compte-rendu"):
        """Ouvre la fiche d'un OT sur l'onglet voulu (Compte rendu par défaut)."""
        self.aller("#/ot/" + ot_id)
        self.page.wait_for_function(
            "document.querySelector('.ot-fiche .ot-numero') && document.querySelector('.ot-fiche .ot-numero').textContent === %r" % ot_id)
        self.page.click(".onglet[data-onglet='%s']" % onglet)
        self.page.wait_for_selector(FORMULAIRE)

    def attendre_toast(self, texte):
        self.page.wait_for_function("(t) => document.getElementById('toast').textContent.includes(t)", arg=texte)

    def enregistrer(self):
        """« Enregistrer le compte rendu », puis attend la fin (fiche réaffichée, toast de succès)."""
        self.page.evaluate("document.getElementById('toast').textContent = ''")
        self.page.click(FORMULAIRE + " button[type=submit]")
        self.attendre_toast("Compte rendu enregistré.")

    def cloturer(self):
        self.page.click(FORMULAIRE + " button[data-action='transition'][data-cible='%s']" % CLOS_TECH)
        self.page.wait_for_function(
            "document.querySelector('.ot-badges .badge.statut') && document.querySelector('.ot-badges .badge.statut').textContent === %r"
            % CLOS_TECH)
        self.page.wait_for_selector(FORMULAIRE)

    @staticmethod
    def octets(serveur, nom):
        return (serveur.dossier / nom).read_bytes()

    def ot_sur_disque(self, serveur, ot_id):
        return next(o for o in lignes_csv(self.octets(serveur, "ordres_travail.csv")) if o["id"] == ot_id)

    def journal_de(self, serveur, ot_id):
        return [j for j in lignes_csv(self.octets(serveur, "journal.csv"))
                if j["table"] == "ordres_travail" and j["id_ligne"] == ot_id]


# ---------------------------------------------------------------------------
# Champ, règles d'édition, clôture sans astuce
# ---------------------------------------------------------------------------

class TestChamp(CasAstuce):

    def test_champ_sous_le_compte_rendu_avec_l_aide_exacte(self):
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot", profil="technicien", technicien_id="TEC-0002")
            self.fiche(OT_P1)
            self.assertEqual(page.locator(BLOC).count(), 1)
            self.assertEqual(page.inner_text(BLOC + " label.libelle").strip(), LIBELLE)   # sans « * » : facultatif
            self.assertEqual(page.inner_text(BLOC + " .aide").strip(), AIDE)
            self.assertEqual(page.locator(BLOC + " .requis").count(), 0)
            self.assertEqual(page.evaluate("document.querySelector(%r).required" % CHAMP), False)
            self.assertIsNone(page.get_attribute(CHAMP, "aria-required"))
            self.assertIsNone(page.get_attribute(CHAMP, "maxlength"))     # la limite est contrôlée à l'enregistrement
            self.assertEqual(page.evaluate("document.querySelector(%r).tagName" % CHAMP), "TEXTAREA")
            self.assertEqual(page.evaluate(ORDRE_JS), {"apresCompteRendu": True, "avantRemise": True,
                                                       "aideSousLeChamp": True, "large": True})
            # Mêmes règles d'édition que le compte rendu : modifiable ici, vide au départ.
            self.assertFalse(page.is_disabled(FORMULAIRE + " [name=compte_rendu]"))
            self.assertFalse(page.is_disabled(CHAMP))
            self.assertEqual(page.input_value(CHAMP), "")

    def test_lecture_seule_montree_seulement_si_elle_existe(self):
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot")
            # OT « Préparé » : compte rendu en lecture seule ; sans astuce, pas de champ.
            self.fiche(OT_PREPARE)
            self.assertTrue(page.is_disabled(FORMULAIRE + " [name=compte_rendu]"))
            self.assertEqual(page.locator(BLOC).count(), 0)
            # Une astuce existe (écrite sur un autre poste) : montrée, en lecture seule, telle quelle.
            astuce = "Prévoir deux joints d'avance.\nLe second sert presque toujours."
            page.evaluate("""async ([otId, astuce]) => {
              await Donnees.modifier('ordres_travail', (l) => { l.find((x) => x.id === otId).astuce = astuce; });
              await App.reafficher(); }""", [OT_PREPARE, astuce])
            page.wait_for_selector(CHAMP)
            self.assertTrue(page.is_disabled(CHAMP))
            self.assertEqual(page.input_value(CHAMP), astuce)
            self.assertEqual(page.inner_text(BLOC + " .aide").strip(), AIDE)

    def test_cloture_technique_sans_astuce_acceptee(self):
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot")
            # RG4 inchangée : la règle n'exige jamais d'astuce.
            complet = {"id": "X", "statut": "En cours", "type": "correctif différé", "date_debut": "2026-10-19 08:00",
                       "date_fin": "2026-10-19 10:00", "cause_code": "C01", "remede_code": "R01",
                       "compte_rendu": COMPTE_RENDU, "remise_service": "1"}
            verifier = "([ot, temps]) => Ordres.verifierCloture(ot, { temps })"
            for ot in (complet, dict(complet, astuce=""), dict(complet, astuce="   ")):
                self.assertEqual(page.evaluate(verifier, [ot, [{"heures": "1.5"}]]), [])
            # Par l'interface : compte rendu saisi (formulaire modifié), astuce laissée vide, clôture technique.
            page.evaluate(PREPARER_CLOTURE_JS, OT_P1)
            self.fiche(OT_P1)
            page.fill(FORMULAIRE + " [name=compte_rendu]", COMPTE_RENDU)
            self.assertEqual(page.input_value(CHAMP), "")
            self.cloturer()
            ligne = self.ot_sur_disque(serveur, OT_P1)
            self.assertEqual((ligne["statut"], ligne["compte_rendu"], ligne["astuce"]), (CLOS_TECH, COMPTE_RENDU, ""))
            # OT clôturé sans astuce : rien à montrer.
            self.assertTrue(page.is_disabled(FORMULAIRE + " [name=compte_rendu]"))
            self.assertEqual(page.locator(BLOC).count(), 0)


# ---------------------------------------------------------------------------
# Écriture, limite, export
# ---------------------------------------------------------------------------

class TestEcriture(CasAstuce):

    def test_astuce_enregistree_octets_du_csv_puis_montree_sur_l_ot_cloture(self):
        page = self.page
        astuce = ("Desserrer d'abord le contre-écrou ; prendre la clé « 24 » \"longue\".\n"
                  "Puis enduire le filetage de pâte au cuivre.")
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot")
            page.evaluate(PREPARER_CLOTURE_JS, OT_EN_COURS)
            self.fiche(OT_EN_COURS)
            journal_avant = len(self.journal_de(serveur, OT_EN_COURS))
            page.fill(FORMULAIRE + " [name=compte_rendu]", COMPTE_RENDU)
            page.fill(CHAMP, "  " + astuce + "  ")                     # espaces de bord retirés, comme partout
            self.enregistrer()
            # Sur le disque : la colonne astuce, octet pour octet (cellule entre guillemets : « ; », « " », saut de ligne).
            octets = self.octets(serveur, "ordres_travail.csv")
            self.assertIn(b"astuce", octets.split(b"\r\n", 1)[0].split(b";"))   # format 4 : n'est plus la dernière
            self.assertIn(cellule_csv(astuce).encode("utf-8"), octets)
            ligne = self.ot_sur_disque(serveur, OT_EN_COURS)
            self.assertEqual((ligne["astuce"], ligne["compte_rendu"], ligne["statut"]), (astuce, COMPTE_RENDU, "En cours"))
            # Une seule écriture : une entrée au journal, avec les deux champs.
            entrees = self.journal_de(serveur, OT_EN_COURS)[journal_avant:]
            self.assertEqual([e["action"] for e in entrees], ["modification : compte_rendu, astuce — compte rendu"])
            self.assertEqual(page.input_value(CHAMP), astuce)          # fiche réaffichée
            # Clôture technique : l'astuce reste montrée, telle quelle, en lecture seule.
            self.cloturer()
            self.assertTrue(page.is_disabled(CHAMP))
            self.assertEqual(page.input_value(CHAMP), astuce)
            self.assertEqual(self.ot_sur_disque(serveur, OT_EN_COURS)["astuce"], astuce)
            # La recherche la trouve (index refait après l'écriture).
            trouves = page.evaluate("""() => Wiki.rechercher('pâte au cuivre').portees[0].resultats
              .map((r) => [r.type, r.otId, r.extrait])""")
            self.assertEqual(trouves[0][:2], ["ot", OT_EN_COURS])
            self.assertIn("pâte au cuivre", trouves[0][2])

    def test_500_caracteres_acceptes_501_refuses_fichiers_inchanges(self):
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot")
            self.fiche(OT_EN_COURS)
            # La limite du formulaire est le seuil du wiki (§20.1, D100) : 500.
            maximum = page.evaluate("Wiki.SEUILS.astuceMax")
            self.assertEqual(maximum, 500)
            # 500 caractères : acceptés. Comptés en caractères : ni en octets (« é » : 2 octets), ni en unités
            # UTF-16 (la clé U+1F527, saisie au clavier d'un téléphone, en compte 2).
            acceptee = "é" * (maximum - 1) + "\U0001F527"
            page.fill(CHAMP, acceptee)
            self.enregistrer()
            self.assertEqual(self.ot_sur_disque(serveur, OT_EN_COURS)["astuce"], acceptee)
            # 501 caractères : refusés avec un message clair, rien n'est écrit.
            ordres_avant = self.octets(serveur, "ordres_travail.csv")
            journal_avant = self.octets(serveur, "journal.csv")
            page.fill(CHAMP, "a" * (maximum + 1))
            page.click(FORMULAIRE + " button[type=submit]")
            page.wait_for_selector(BLOC + " .erreur-champ:not([hidden])")
            message = page.inner_text(BLOC + " .erreur-champ")
            for attendu in ("Astuce trop longue", "501 caractères", "500 au plus", "rien n'a été enregistré"):
                self.assertIn(attendu, message)
            self.attendre_toast("Astuce trop longue")
            self.assertEqual(page.get_attribute(CHAMP, "aria-invalid"), "true")
            self.assertEqual(page.input_value(CHAMP), "a" * 501)        # la saisie reste à l'écran
            # Une transition enregistre d'abord la saisie : refusée de même, le statut ne change pas.
            page.evaluate("document.getElementById('toast').textContent = ''")
            page.click(FORMULAIRE + " button[data-action='transition'][data-cible='%s']" % CLOS_TECH)
            self.attendre_toast("Astuce trop longue")
            self.assertEqual(self.octets(serveur, "ordres_travail.csv"), ordres_avant)
            self.assertEqual(self.octets(serveur, "journal.csv"), journal_avant)
            self.assertEqual(page.evaluate("Donnees.trouver('ordres_travail', %r).astuce" % OT_EN_COURS), acceptee)
            self.assertEqual(page.inner_text(".ot-badges .badge.statut"), "En cours")

    def test_export_zip_contient_l_astuce(self):
        page = self.page
        astuce = "Noter le couple de serrage sur le carter ; il varie d'un modèle à l'autre."
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot")
            self.fiche(OT_EN_COURS)
            page.fill(CHAMP, astuce)
            self.enregistrer()
            self.aller("#/accueil")
            page.wait_for_selector("#btn-export-accueil")
            with page.expect_download() as attente:
                page.click("#btn-export-accueil")
            with zipfile.ZipFile(attente.value.path()) as archive:
                octets = archive.read("ordres_travail.csv")
            self.assertIn(b"astuce", octets.split(b"\r\n", 1)[0].split(b";"))   # format 4 : n'est plus la dernière
            ligne = next(o for o in lignes_csv(octets) if o["id"] == OT_EN_COURS)
            self.assertEqual(ligne["astuce"], astuce)
            self.assertEqual(octets, self.octets(serveur, "ordres_travail.csv"))   # le fichier tel qu'il est sur le disque


# ---------------------------------------------------------------------------
# Texte piégé ; démo
# ---------------------------------------------------------------------------

class TestPiegeEtDemo(CasAstuce):

    def test_texte_piege_reste_du_texte(self):
        page = self.page
        piege = '<img src=x onerror="window.piege=1">Desserrer <b>avant</b> de chauffer & "taper"'
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot")
            page.evaluate(PREPARER_CLOTURE_JS, OT_EN_COURS)
            self.fiche(OT_EN_COURS)
            page.fill(FORMULAIRE + " [name=compte_rendu]", COMPTE_RENDU)
            page.fill(CHAMP, piege)
            self.enregistrer()
            self.assertEqual(self.ot_sur_disque(serveur, OT_EN_COURS)["astuce"], piege)
            self.cloturer()
            self.assertEqual(page.input_value(CHAMP), piege)
            self.assertEqual(page.locator(BLOC + " img, " + BLOC + " b").count(), 0)
            # Dans un résultat de recherche (écran du wiki) : extrait en texte, aucun élément venu de l'astuce.
            self.aller("#/wiki")
            page.wait_for_selector("#contenu .wiki-recherche-champ")
            page.fill("#contenu .wiki-recherche-champ", "onerror")
            ligne = '#contenu .wiki-trouve[data-id="%s"]' % OT_EN_COURS
            page.wait_for_selector(ligne)
            self.assertIn('<img src=x onerror="window.piege=1">', page.inner_text(ligne + " .wiki-extrait"))
            self.assertEqual(page.locator("#contenu .wiki-resultats img, #contenu .wiki-extrait b").count(), 0)
            self.assertEqual(page.eval_on_selector_all(ligne + " .wiki-extrait *", "e => e.map((x) => x.tagName)"), ["MARK"])
            self.assertIsNone(page.evaluate("window.piege === undefined ? null : window.piege"))

    def test_demo_astuce_montree_sur_la_fiche(self):
        page = self.page
        preregler_profil(self.contexte, "technicien", technicien_id="TEC-0001")
        page.goto(url_fichier("index.html"))
        page.click("#btn-demo")
        attendre_pret(page)
        avec = page.evaluate("""() => Donnees.lignes('ordres_travail').filter((ot) => ot.astuce)
          .map((ot) => ({ id: ot.id, statut: ot.statut, astuce: ot.astuce }))""")
        self.assertGreaterEqual(len(avec), 45)
        self.assertTrue(all(ot["statut"].startswith("Clôturé") for ot in avec))
        sans = page.evaluate("""() => Donnees.lignes('ordres_travail')
          .find((ot) => !ot.astuce && ot.statut === 'Clôturé administrativement').id""")
        for ot in (avec[0], avec[len(avec) // 2], avec[-1]):
            with self.subTest(ot=ot["id"]):
                self.aller("#/ot/" + ot["id"])          # OT clôturé : la fiche s'ouvre sur le compte rendu
                page.wait_for_function(
                    "document.querySelector('.ot-fiche .ot-numero') && document.querySelector('.ot-fiche .ot-numero').textContent === %r"
                    % ot["id"])
                page.wait_for_selector(CHAMP)
                self.assertEqual(page.input_value(CHAMP), ot["astuce"])
                self.assertTrue(page.is_disabled(CHAMP))
                self.assertEqual(page.evaluate(ORDRE_JS)["apresCompteRendu"], True)
        self.fiche(sans)
        self.assertEqual(page.locator(BLOC).count(), 0)


# ---------------------------------------------------------------------------
# Affichage d'un résultat « page » (wiki-ecrans.js), démo file://
# ---------------------------------------------------------------------------

# Deux pages validées écrites en mémoire (démo) : une page d'équipement (lien canonique EQ-0005) et un
# savoir-faire sans équipement au titre piégé (lien WP-0002) ; le mot « stroboscope » n'est que dans elles. Elles
# remplacent le wiki figé de la démo (T122).
PAGES_JS = """async () => {
  await Donnees.modifier('wiki_journal', (lignes) => { lignes.splice(0, lignes.length); });
  await Donnees.modifier('wiki_pages', (lignes) => {
    lignes.splice(0, lignes.length);
    lignes.push({ id: 'WP-0001', type: 'équipement', titre: 'PO-02', equipement_id: 'EQ-0005', statut: 'active',
      texte: '## À surveiller\\n- Contrôler la vitesse au stroboscope après un remontage [OT-2025-0010]',
      valide_le: '2026-10-01 10:00', version: '1', origine: 'IA' });
    lignes.push({ id: 'WP-0002', type: 'savoir-faire', titre: '<img src=x onerror="window.piege=1">Régler au stroboscope',
      statut: 'active', texte: '## Étapes\\n- Le stroboscope se règle sur la vitesse nominale [OT-2025-0010]',
      modifie_le: '2026-10-02 10:00', version: '1', origine: 'manuel' });
  });
}"""

RESULTATS_PAGES_JS = """() => Array.from(document.querySelectorAll('#contenu .wiki-trouve[data-type="page"]')).map((li) => {
  const lien = li.querySelector('.wiki-ligne-tete > a.wiki-lien-page');
  return { id: li.dataset.id, href: lien && lien.getAttribute('href'), titre: lien && lien.textContent,
           premier: li.querySelector('.wiki-ligne-tete > :first-child') === lien,
           badge: li.querySelector('.wiki-ligne-tete .badge.info') && li.querySelector('.wiki-ligne-tete .badge.info').textContent,
           carteTitre: li.querySelectorAll('.carte-titre').length,
           marques: Array.from(li.querySelectorAll('.wiki-extrait mark')).map((m) => m.textContent),
           extrait: li.querySelector('.wiki-extrait').textContent,
           elements: Array.from(li.querySelectorAll('*')).map((e) => e.tagName) };
})"""


class TestResultatPage(CasAstuce):

    def verifier_profil(self, profil, nom="", technicien_id=""):
        page = self.page
        preregler_profil(self.contexte, profil, nom=nom, technicien_id=technicien_id)
        page.goto(url_fichier("index.html"))
        page.click("#btn-demo")
        attendre_pret(page)
        page.evaluate(PAGES_JS)
        self.aller("#/wiki")
        page.wait_for_selector("#contenu .wiki-recherche-champ")
        page.fill("#contenu .wiki-recherche-champ", "stroboscope")
        page.wait_for_function("document.querySelectorAll('#contenu .wiki-trouve[data-type=\"page\"]').length === 2")
        lus = {r["id"]: r for r in page.evaluate(RESULTATS_PAGES_JS)}
        self.assertEqual(sorted(lus), ["WP-0001", "WP-0002"])
        # Lien vers la page (identifiant canonique), avec le titre de Wiki.page, en tête de la ligne.
        for page_id, href in (("WP-0001", "#/wiki/EQ-0005"), ("WP-0002", "#/wiki/WP-0002")):
            with self.subTest(profil=profil, page=page_id):
                lu = lus[page_id]
                self.assertEqual(lu["href"], href)
                self.assertEqual(lu["titre"], page.evaluate("(id) => Wiki.page(id).titre", page_id))
                self.assertTrue(lu["premier"])
                self.assertEqual(lu["badge"], "Page du wiki")
                self.assertEqual(lu["carteTitre"], 0)                    # le titre n'est pas répété
                self.assertEqual(lu["marques"], ["stroboscope"])
                self.assertNotIn("[OT-", lu["extrait"])
        self.assertEqual(lus["WP-0001"]["titre"], "PO-02 — Pompe centrifuge eau de refroidissement")
        # Titre piégé : du texte, aucun élément ni script.
        self.assertEqual(lus["WP-0002"]["titre"], '<img src=x onerror="window.piege=1">Régler au stroboscope')
        self.assertNotIn("IMG", lus["WP-0002"]["elements"])
        self.assertIsNone(page.evaluate("window.piege === undefined ? null : window.piege"))
        # Le lien de la page d'équipement mène à sa page.
        page.click('#contenu .wiki-trouve[data-id="WP-0001"] a.wiki-lien-page')
        page.wait_for_selector('.wiki-page[data-equipement="EQ-0005"]')

    def test_resultat_page_pour_le_demandeur(self):
        self.verifier_profil("demandeur", nom="Lucie Martin")

    def test_resultat_page_pour_le_technicien(self):
        self.verifier_profil("technicien", technicien_id="TEC-0001")


if __name__ == "__main__":
    unittest.main()
