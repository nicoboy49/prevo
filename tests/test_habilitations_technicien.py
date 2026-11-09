"""Habilitations du technicien sur son accueil, 2.2, lot L6 (T480 ; D199, décision de Nicolas du 09/11 ; D196 ; CS172).

Carte « Mes habilitations » de l'accueil du technicien (Equipe.carteMesHabilitations, equipe-habilitations.js, appelée
par accueil.js après « Mes ordres de travail ouverts ») : SES habilitations qui comptent (technicien du profil ; en mode
serveur avec comptes, du compte connecté), les plus urgentes d'abord : intitulé, statut (échue, à renouveler, pas encore
valable, valide) et son détail, dates, type du catalogue ; jamais un justificatif (ni nom ni lien), aucune habilitation
d'un autre technicien, aucun bouton ; phrase D182.

Toujours des données de test : la démo (index.html en file://, horloge du navigateur FIGÉE au 19/10/2026, fuseau
Europe/Paris) ou serveur.py sur une copie temporaire du jeu de démo (comptes de COMPTES_DE_TEST). Familles :
    demo      TEC-0002 : ses trois habilitations (= Equipe.habilitationsQuiComptent), CACES R489 à renouveler d'abord,
              type du catalogue en lang="fr", dates, aucune d'un autre technicien, carte après « Mes ordres » ;
    etats     lignes ajoutées : échue, pas encore valable, ancienne ligne renouvelée (absente), saisie libre (sans
              type) ; justificatifs posés sur ses lignes et sur celle d'un autre technicien : ni nom ni lien ;
    profils   responsable et demandeur : pas de carte ; technicien sans habilitation : « Aucune habilitation
              enregistrée à votre nom. » ; profil sans technicien lié : pas de carte ;
    telephone 390 px, en anglais : carte traduite, aucun défilement horizontal ;
    comptes   serveur avec comptes : le technicien connecté (julien.moreau, TEC-0001, profil venu de la session) voit
              les siennes ; le justificatif écrit par le responsable n'est jamais nommé.

Lancer depuis la racine du projet (au travers du verrou des navigateurs) :
    py -X utf8 -m unittest discover -s tests -p "test_habilitations_technicien.py" -v
"""
import csv
import io
import json
import unittest
from pathlib import Path

from commun import COMPTES_DE_TEST, CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, url_fichier

REFERENCE = "2026-10-19"
TECHNICIEN = "TEC-0002"
PDF = b"%PDF-1.4\n% justificatif de test (T480)\n%%EOF\n"
PHRASE = "Prévo est une aide au suivi ; la responsabilité reste celle de l'employeur."


def ligne(identifiant, technicien, intitule, obtention, echeance, catalogue="", justificatif="", recyclage=""):
    return {"id": identifiant, "technicien_id": technicien, "intitule": intitule, "date_obtention": obtention,
            "date_echeance": echeance, "recyclage_mois": recyclage, "justificatif": justificatif,
            "catalogue_id": catalogue, "nature_source": ""}


# Lignes ajoutées à la démo (famille etats) et justificatifs posés sur des lignes existantes.
AJOUTS = [
    ligne("HAB-9801", TECHNICIEN, "BR", "2023-09-01", "2026-09-30", "H02", "TEC-0002-BR-2023-09-01.pdf", "36"),
    ligne("HAB-9802", TECHNICIEN, "B1V", "2026-11-15", "2029-11-15", "H02"),
    ligne("HAB-9803", TECHNICIEN, "H0V", "2021-05-14", "2024-05-14", "H01", "TEC-0002-H0V-2021-05-14.pdf"),
    ligne("HAB-9804", TECHNICIEN, "Travail en hauteur", "2025-01-10", ""),
    ligne("HAB-9805", "TEC-0001", "Secret du voisin", "2024-01-01", "2026-01-01", "", "TEC-0001-voisin.pdf"),
]
JUSTIFICATIFS = {"HAB-0004": "TEC-0002-CACES-R489-2021-12-02.pdf"}
NOMS_JUSTIFICATIFS = [a["justificatif"] for a in AJOUTS if a["justificatif"]] + list(JUSTIFICATIFS.values())

AJOUTER_JS = """async ([ajouts, justificatifs]) => {
  await Donnees.modifier('habilitations', (lignes) => {
    lignes.forEach((l) => { if (justificatifs[l.id]) l.justificatif = justificatifs[l.id]; });
    ajouts.forEach((a) => lignes.push(Object.assign({}, a)));
  }, { action: 'habilitations de test (T480)' });
  await App.reafficher();
}"""

RETIRER_JS = """async (technicien) => {
  await Donnees.modifier('habilitations', (lignes) => {
    for (let i = lignes.length - 1; i >= 0; i -= 1) if (lignes[i].technicien_id === technicien) lignes.splice(i, 1);
  }, { action: 'habilitations retirées (T480)' });
  await App.reafficher();
}"""

# La carte lue à l'écran ; null si absente.
CARTE_JS = """() => {
  const carte = document.getElementById('accueil-mes-habilitations');
  if (!carte) return null;
  const espaces = (t) => t.replace(/\\s+/g, ' ').trim();
  const texteDe = (e) => (e ? espaces(e.textContent) : '');
  return {
    titre: texteDe(carte.querySelector('h2')), nombre: Number(texteDe(carte.querySelector('.entete-carte .badge'))),
    lignes: Array.from(carte.querySelectorAll('li[data-habilitation]')).map((li) => {
      const type = li.querySelector('.equipe-type [data-catalogue]');
      const h = Donnees.trouver('habilitations', li.dataset.habilitation);
      return { id: li.dataset.habilitation, statut: li.dataset.statut, technicien: h ? h.technicien_id : null,
        intitule: texteDe(li.querySelector('.equipe-intitule')), badge: texteDe(li.querySelector('.badge.statut')),
        detail: texteDe(li.querySelector('.equipe-detail')), dates: texteDe(li.querySelector('.equipe-dates')),
        type: texteDe(type), langType: type ? type.getAttribute('lang') : null };
    }),
    texte: espaces(carte.textContent), html: carte.innerHTML,
    liens: carte.querySelectorAll('a').length, boutons: carte.querySelectorAll('button, input, select').length,
    precedente: carte.previousElementSibling ? carte.previousElementSibling.className : '',
  };
}"""

# Appel d'une fonction d'Equipe (responsable) ; `fichier` (facultatif) : { nom, octets } devient un File PDF ajouté en dernier.
APPEL_JS = """async ([fonction, arguments_, fichier]) => {
  const args = arguments_.slice();
  if (fichier) args.push(new File([new Uint8Array(fichier.octets)], fichier.nom, { type: 'application/pdf' }));
  return JSON.stringify(await Equipe[fonction](...args));
}"""


def lire_csv(dossier, nom):
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte), delimiter=";"))


def brut(valeur):
    valeur = (valeur or "").strip()
    return valeur[1:] if valeur.startswith("'") else valeur


class CasHabilitationsTechnicien(CasNavigateur):

    def ouvrir(self, profil="technicien", technicien_id=TECHNICIEN, nom="", largeur=1280, hauteur=900,
               telephone=False, langue=None):
        """Démo en file://, horloge figée au jour de référence, profil réglé ; rend la page sur l'accueil."""
        options = dict(locale="fr-FR", timezone_id="Europe/Paris", reduced_motion="reduce",
                       viewport={"width": largeur, "height": hauteur})
        if telephone:
            options.update(is_mobile=True, has_touch=True, device_scale_factor=2)
        contexte = self.navigateur.new_context(**options)
        self.addCleanup(contexte.close)
        contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        contexte.clock.set_fixed_time(REFERENCE + "T09:00:00")
        if langue:
            contexte.add_init_script("try { localStorage.setItem('prevo.langue', %s); } catch (e) { /* sans stockage */ }"
                                     % json.dumps(langue))
        preregler_profil(contexte, profil, nom, technicien_id, poste="Poste atelier")
        page = contexte.new_page()
        self.surveiller(page)
        page.goto(url_fichier("index.html"))
        page.click("#btn-demo")
        attendre_pret(page)
        self.assertEqual(page.evaluate("Donnees.aujourdhui()"), REFERENCE)
        page.wait_for_selector("#contenu h1")
        return page

    def carte(self, page):
        carte = page.evaluate(CARTE_JS)
        self.assertIsNotNone(carte, "carte « Mes habilitations » absente")
        return carte

    def sans_justificatif(self, page, carte, noms):
        """Ni nom ni lien de justificatif, dans la carte ni ailleurs sur l'accueil ; aucune commande."""
        contenu = page.evaluate("document.getElementById('contenu').innerHTML")
        for nom in noms:
            self.assertNotIn(nom, contenu)
        self.assertNotIn("ustificatif", carte["texte"])
        self.assertNotIn("data-justificatif", carte["html"])
        self.assertNotIn("equipe-justificatif", carte["html"])
        self.assertEqual((carte["liens"], carte["boutons"]), (0, 0))
        self.assertEqual(page.locator("#contenu a[href*='documents'], #contenu a[href*='justificatif']").count(), 0)


# ---------------------------------------------------------------------------
# demo : ses habilitations sur son accueil
# ---------------------------------------------------------------------------

class TestDemo(CasHabilitationsTechnicien):

    def test_demo_ses_trois_habilitations_type_echeance_statut_seulement_les_siennes(self):
        page = self.ouvrir()
        page.wait_for_selector("#accueil-mes-habilitations")
        carte = self.carte(page)
        attendues = page.evaluate("(id) => Equipe.habilitationsQuiComptent(id).map((h) => h.id).sort()", TECHNICIEN)
        self.assertEqual(sorted(l["id"] for l in carte["lignes"]), attendues)
        self.assertEqual(attendues, ["HAB-0004", "HAB-0005", "HAB-0006"])
        self.assertEqual({l["technicien"] for l in carte["lignes"]}, {TECHNICIEN})
        self.assertEqual((carte["titre"], carte["nombre"]), ("Mes habilitations", 3))
        # La plus urgente d'abord : CACES R489 à renouveler (échéance le 02/12/2026, dans 44 jours), puis les valides
        self.assertEqual([l["id"] for l in carte["lignes"]], ["HAB-0004", "HAB-0005", "HAB-0006"])
        caces = carte["lignes"][0]
        self.assertEqual((caces["intitule"], caces["statut"], caces["badge"]), ("CACES R489", "à renouveler", "à renouveler"))
        self.assertEqual(caces["detail"], "échéance le 02/12/2026 (dans 44 jours)")
        self.assertEqual(caces["dates"], "Obtenue le 02/12/2021 · échéance le 02/12/2026")
        types = page.evaluate("(ids) => ids.map((id) => Equipe.typeHabilitation(id).type)", ["H12", "H14", "H01"])
        self.assertEqual([l["type"] for l in carte["lignes"]], types)
        self.assertEqual({l["langType"] for l in carte["lignes"]}, {"fr"})
        autorisation = carte["lignes"][1]
        self.assertEqual((autorisation["badge"], autorisation["detail"]), ("valide", "sans échéance"))
        self.assertEqual(carte["lignes"][2]["dates"], "Obtenue le 14/05/2024 · échéance le 14/05/2027")
        # Aucune habilitation d'un autre technicien (BR, B2V : TEC-0001, TEC-0003, TEC-0004)
        self.assertNotIn("BR", carte["texte"].split())
        self.assertNotIn("B2V", carte["texte"])
        self.assertIn(PHRASE, carte["texte"])
        self.assertIn("Tenues à jour par le responsable", carte["texte"])
        self.assertIn("accueil-mes-ordres", carte["precedente"])
        self.sans_justificatif(page, carte, [])


# ---------------------------------------------------------------------------
# etats : échue, à renouveler, pas encore valable, valide ; justificatifs jamais montrés
# ---------------------------------------------------------------------------

class TestEtats(CasHabilitationsTechnicien):

    def test_etats_ordre_ancienne_ligne_absente_et_aucun_justificatif(self):
        page = self.ouvrir()
        page.wait_for_selector("#accueil-mes-habilitations")
        page.evaluate(AJOUTER_JS, [AJOUTS, JUSTIFICATIFS])
        page.wait_for_selector("#accueil-mes-habilitations li[data-habilitation='HAB-9801']")
        carte = self.carte(page)
        # échue, à renouveler, pas encore valable, puis les valides par intitulé ; l'ancienne H0V (HAB-9803) ne compte plus
        self.assertEqual([(l["id"], l["badge"]) for l in carte["lignes"]], [
            ("HAB-9801", "échue"), ("HAB-0004", "à renouveler"), ("HAB-9802", "pas encore valable"),
            ("HAB-0005", "valide"), ("HAB-0006", "valide"), ("HAB-9804", "valide")])
        self.assertEqual(carte["nombre"], 6)
        par_id = {l["id"]: l for l in carte["lignes"]}
        self.assertEqual(par_id["HAB-9801"]["detail"], "échue le 30/09/2026 (depuis 19 jours)")
        self.assertEqual(par_id["HAB-9802"]["detail"], "valable à partir du 15/11/2026")
        self.assertEqual(par_id["HAB-9804"]["dates"], "Obtenue le 10/01/2025 · sans échéance")
        self.assertEqual(par_id["HAB-9804"]["type"], "")          # saisie libre : pas de type du catalogue
        self.assertEqual(par_id["HAB-9801"]["type"], page.evaluate("Equipe.typeHabilitation('H02').type"))
        self.assertEqual({l["technicien"] for l in carte["lignes"]}, {TECHNICIEN})
        self.assertNotIn("Secret du voisin", page.inner_text("#contenu"))
        self.sans_justificatif(page, carte, NOMS_JUSTIFICATIFS)


# ---------------------------------------------------------------------------
# profils : la carte n'est que celle du technicien
# ---------------------------------------------------------------------------

class TestProfils(CasHabilitationsTechnicien):

    def test_profils_responsable_et_demandeur_sans_carte(self):
        for profil, nom, technicien in (("responsable", "", ""), ("demandeur", "Lucas Perrot", "")):
            with self.subTest(profil=profil):
                page = self.ouvrir(profil=profil, technicien_id=technicien, nom=nom)
                page.wait_for_selector("#bento" if profil == "responsable" else "#contenu .accueil-signaler")
                self.assertEqual(page.locator("#accueil-mes-habilitations").count(), 0)

    def test_technicien_sans_habilitation_et_profil_sans_technicien(self):
        page = self.ouvrir()
        page.wait_for_selector("#accueil-mes-habilitations")
        page.evaluate(RETIRER_JS, TECHNICIEN)
        page.wait_for_selector("#accueil-mes-habilitations .muted:not(.accueil-habilitations-aide)")
        carte = self.carte(page)
        self.assertEqual((carte["lignes"], carte["nombre"]), ([], 0))
        self.assertIn("Aucune habilitation enregistrée à votre nom.", carte["texte"])
        self.assertIn(PHRASE, carte["texte"])
        # Sans technicien lié au profil : aucune carte (jamais les lignes au technicien_id vide d'une base abîmée)
        self.assertEqual(page.evaluate("(jour) => String(Equipe.carteMesHabilitations('', jour))", REFERENCE), "")
        self.assertEqual(page.evaluate("(jour) => String(Equipe.carteMesHabilitations('  ', jour))", REFERENCE), "")


# ---------------------------------------------------------------------------
# telephone : 390 px, en anglais
# ---------------------------------------------------------------------------

class TestTelephone(CasHabilitationsTechnicien):

    def test_telephone_en_anglais_sans_defilement_horizontal(self):
        page = self.ouvrir(largeur=390, hauteur=844, telephone=True, langue="en")
        page.wait_for_selector("#accueil-mes-habilitations")
        carte = self.carte(page)
        self.assertEqual(carte["titre"], "My authorisations")
        self.assertEqual([l["badge"] for l in carte["lignes"]], ["to renew", "valid", "valid"])
        self.assertIn("Kept up to date by the manager", carte["texte"])
        self.assertEqual({l["langType"] for l in carte["lignes"]}, {"fr"})   # contenu du catalogue : en français
        largeurs = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        self.assertLessEqual(largeurs[0], largeurs[1])
        boite = page.eval_on_selector("#accueil-mes-habilitations", "e => e.getBoundingClientRect().right")
        self.assertLessEqual(boite, largeurs[1])


# ---------------------------------------------------------------------------
# comptes : le technicien du compte connecté (mode serveur)
# ---------------------------------------------------------------------------

class TestComptes(CasHabilitationsTechnicien):

    def test_comptes_technicien_connecte_voit_les_siennes_sans_justificatif(self):
        technicien = COMPTES_DE_TEST["technicien"][4]
        with ServeurPrevo(comptes=True) as serveur:
            # Le responsable joint un vrai justificatif à la ligne BR du technicien du compte.
            serveur.poser_session(self.contexte, "responsable")
            self.page.goto(serveur.url + "/#/equipe/" + technicien)
            attendre_pret(self.page)
            self.page.wait_for_selector(".equipe-carte-habilitations")
            br = next(h for h in lire_csv(serveur.dossier, "habilitations.csv")
                      if h["technicien_id"] == technicien and brut(h["intitule"]) == "BR")
            nom = json.loads(self.page.evaluate(APPEL_JS, ["ecrireJustificatif", [technicien, "BR", brut(br["date_obtention"])],
                                                           {"nom": "titre.pdf", "octets": list(PDF)}]))
            self.page.evaluate(APPEL_JS, ["modifierHabilitation", [br["id"], {"justificatif": nom}], None])
            self.assertEqual(brut(next(h for h in lire_csv(serveur.dossier, "habilitations.csv")
                                       if h["id"] == br["id"])["justificatif"]), nom)

            contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 900})
            self.addCleanup(contexte.close)
            contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
            serveur.poser_session(contexte, "technicien", profil=False)     # profil tiré de la session seulement
            page = contexte.new_page()
            self.surveiller(page)
            page.goto(serveur.url + "/#/accueil")
            attendre_pret(page)
            page.wait_for_selector("#accueil-mes-habilitations")
            self.assertEqual(page.evaluate("[App.profil.type, App.profil.technicienId, App.comptesExiges()]"),
                             ["technicien", technicien, True])
            carte = self.carte(page)
            siennes = sorted({h["id"] for h in lire_csv(serveur.dossier, "habilitations.csv") if h["technicien_id"] == technicien})
            self.assertEqual(sorted(l["id"] for l in carte["lignes"]), siennes)
            self.assertIn(br["id"], siennes)
            self.assertEqual({l["technicien"] for l in carte["lignes"]}, {technicien})
            self.assertNotIn("CACES R489", carte["texte"])                  # habilitation de TEC-0002 et TEC-0004
            self.sans_justificatif(page, carte, [nom])


if __name__ == "__main__":
    unittest.main()
