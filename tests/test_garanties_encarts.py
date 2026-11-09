"""Tests des encarts du module Garanties dans les autres écrans (garanties-encarts.js, T457 ; CDC §3.4, D126, CS173).

Page vide (charger_scripts), jeu écrit à la main dans ce fichier (aucune donnée réelle), date du jour passée en
argument (jamais la date réelle) ; profil passé en argument (responsable ou non). Familles (le nom du test le dit) :
    badge  : Garanties.badgeEquipement — « Sous garantie jusqu'au … » selon le jour (bornes incluses, garantie
             suivante, ligne retirée ignorée, ambre sous le délai d'alerte), '' sans garantie en cours ;
    rappel : Garanties.rappelOt — bandeau « attention » pour un correctif (immédiat, différé) sur un équipement sous
             garantie (fournisseur et téléphone en tel:, sans téléphone, sans fournisseur, conditions), null pour un
             préventif, une amélioration, un équipement sans garantie en cours ; rien au journal ; texte anglais ;
    carte  : Garanties.carteEquipement — garantie en cours (fournisseur en tel:, conditions repliées au-delà de 3
             lignes, document), à venir, fin inconnue, 3 dernières terminées, contrats qui citent l'équipement ;
             technicien : ni lien vers les écrans du responsable ni statut des contrats ; responsable : « Ajouter une
             garantie », liens, statut et raison ; jamais de montant (D126) ; vide expliqué.

Lancer depuis la racine du projet (navigateur : au travers du verrou) :
    py -X utf8 -m unittest discover -s tests -p "test_garanties_encarts.py" -v
"""
import unittest

from commun import RACINE, CasNavigateur, charger_scripts

SCRIPTS = [
    "js/lib/papaparse.min.js",
    "js/schema.js",
    "js/donnees.js",
    "js/stockage-demo.js",
    "js/interface.js",
    "js/i18n/en.js",
    "js/modules/controles-regles.js",
    "js/modules/garanties-regles.js",
    "js/modules/garanties-ecritures.js",
    "js/modules/garanties-formulaires.js",
    "js/modules/garanties-ecrans.js",
    "js/modules/garanties-encarts.js",
]


def csv(entete, lignes):
    return "\r\n".join([entete] + list(lignes)) + "\r\n"


EQUIPEMENTS = csv("id;repere;designation;statut;actif", [
    "EQ-0001;CP-01;Compresseur à vis;en service;1",
    "EQ-0002;PR-02;Presse hydraulique;en service;1",
    "EQ-0003;TO-03;Tour sans garantie;en service;1",
    "EQ-0004;CH-04;Chariot sous contrat;en service;1",
    "EQ-0005;PE-05;Perceuse;en service;1",
])

FOURNISSEURS = csv("id;nom;contact;telephone;email", [
    "FOU-0001;Hydraulique Services;M. Roux;04 65 71 00 99;contact@hydraulique.test",
    "FOU-0002;Air Maintenance;;;",
])

CONDITIONS_LONGUES = ("\"Pièces et main-d'œuvre.\nPièces d'usure exclues.\nIntervention par le fabricant seulement.\n"
                      "Huile d'origine obligatoire.\nAnnulée en cas de démontage.\"")

GARANTIES = csv("id;equipement_id;fournisseur_id;date_debut;date_fin;conditions;document;actif", [
    "GAR-0001;EQ-0001;FOU-0001;2025-06-01;2027-03-31;Pièces et main-d'œuvre;garantie-GAR-0001-2025-06-01.pdf;1",
    "GAR-0002;EQ-0001;FOU-0002;2024-02-01;2025-01-31;;;1",
    "GAR-0003;EQ-0001;;2023-01-01;2023-12-31;;;1",
    "GAR-0004;EQ-0001;;2022-01-01;2022-12-31;;;1",
    "GAR-0005;EQ-0001;;2021-01-01;2021-12-31;;;1",
    "GAR-0006;EQ-0001;FOU-0001;2027-04-01;2029-03-31;Extension de garantie;;1",
    # retirée : jamais affichée ni rappelée, même en cours
    "GAR-0007;EQ-0001;FOU-0002;2025-01-01;2030-12-31;Retirée;;0",
    "GAR-0008;EQ-0002;FOU-0002;2026-01-01;2026-12-31;" + CONDITIONS_LONGUES + ";garantie-GAR-0008-absente.pdf;1",
    "GAR-0009;EQ-0005;;;2027-01-31;;;1",
    "GAR-0010;EQ-0002;;;2026-02-30;;;1",
])

CONTRATS = csv("id;fournisseur_id;objet;equipement_ids;perimetre;date_debut;date_fin;preavis_mois;reconduction_tacite;"
               "reconduction_mois;montant_annuel;document;actif", [
    # CS173 : fin 31/12/2026, préavis 3 mois, reconduction tacite
    "CTP-0001;FOU-0002;Maintenance des compresseurs;\"EQ-0001;EQ-0004\";;2026-01-01;2026-12-31;3;1;12;4800;"
    "contrat-CTP-0001-2026-01-01.pdf;1",
    "CTP-0002;FOU-0001;Vérification des compresseurs;EQ-0001;;2024-07-01;2025-06-30;1;0;;1000;;1",
    # reconduit tacitement, fin passée, durée d'une reconduction inconnue : dates à mettre à jour
    "CTP-0003;FOU-0001;Thermographie;EQ-0004;;2025-01-01;2025-12-31;3;1;;1350,50;;1",
    "CTP-0004;FOU-0001;Contrat retiré;EQ-0001;;2026-01-01;2027-12-31;3;1;12;9999;;0",
])

JOUR = "2026-08-16"           # CS173 : CTP-0001 « à décider » (date limite 30/09/2026, dans 45 jours)


class CasEncarts(CasNavigateur):

    def setUp(self):
        super().setUp()
        charger_scripts(self.page, SCRIPTS)
        self.page.evaluate("""async (tables) => {
          Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Poste test', profil: 'Responsable test' });
          await Donnees.chargerTout();
        }""", {"equipements": EQUIPEMENTS, "fournisseurs": FOURNISSEURS, "garanties": GARANTIES,
               "contrats_prestataires": CONTRATS})

    def js(self, script, argument=None):
        return self.page.evaluate(script, argument)


class TestBadge(CasEncarts):

    def badge(self, equipement, jour):
        return self.js("""([equipement, jour]) => {
          const fragment = Garanties.badgeEquipement(equipement, jour);
          if (!String(fragment)) return null;
          const zone = document.createElement('p');
          UI.remplir(zone, fragment);
          const badge = zone.querySelector('.garanties-badge-equipement');
          return { texte: zone.textContent.trim(), garantie: badge.dataset.garantie,
                   classes: badge.querySelector('.badge').className };
        }""", [equipement, jour])

    def test_badge_sous_garantie_jusqu_a_la_fin_la_plus_lointaine_en_cours(self):
        badge = self.badge("EQ-0001", JOUR)
        self.assertEqual(badge["texte"], "Sous garantie jusqu'au 31/03/2027")
        self.assertEqual(badge["garantie"], "GAR-0001")      # GAR-0007, retirée, finit en 2030 : ignorée
        self.assertIn("ok", badge["classes"].split())

    def test_badge_ambre_sous_le_delai_d_alerte(self):
        badge = self.badge("EQ-0001", "2027-02-15")           # 44 jours avant la fin
        self.assertEqual(badge["texte"], "Sous garantie jusqu'au 31/03/2027")
        self.assertIn("attention", badge["classes"].split())

    def test_badge_bornes_incluses_puis_garantie_suivante(self):
        self.assertEqual(self.badge("EQ-0001", "2025-06-01")["garantie"], "GAR-0001")
        self.assertEqual(self.badge("EQ-0001", "2027-03-31")["texte"], "Sous garantie jusqu'au 31/03/2027")
        self.assertEqual(self.badge("EQ-0001", "2027-04-01")["texte"], "Sous garantie jusqu'au 31/03/2029")
        self.assertIsNone(self.badge("EQ-0001", "2029-04-01"))

    def test_badge_vide_sans_garantie_en_cours(self):
        self.assertIsNone(self.badge("EQ-0003", JOUR))
        self.assertIsNone(self.badge("EQ-0004", JOUR))         # contrat seulement
        self.assertIsNone(self.badge("EQ-0002", "2027-01-01"))  # GAR-0008 terminée, GAR-0010 fin illisible
        self.assertIsNone(self.badge("", JOUR))

    def test_badge_accepte_la_ligne_de_l_equipement(self):
        texte = self.js("""(jour) => {
          const zone = document.createElement('p');
          UI.remplir(zone, Garanties.badgeEquipement(Donnees.trouver('equipements', 'EQ-0005'), jour));
          return zone.textContent.trim();
        }""", JOUR)
        self.assertEqual(texte, "Sous garantie jusqu'au 31/01/2027")


class TestRappel(CasEncarts):

    def rappel(self, equipement, type_ot, jour=JOUR):
        return self.js("""([equipement, type, jour]) => {
          const bandeau = Garanties.rappelOt(equipement, type, jour);
          if (bandeau === null) return null;
          const tel = bandeau.querySelector('a[href^="tel:"]');
          return { element: bandeau instanceof HTMLElement, classes: bandeau.className, role: bandeau.getAttribute('role'),
                   garantie: bandeau.dataset.garantie, paragraphes: [...bandeau.querySelectorAll('p')].map((p) => p.textContent),
                   tel: tel ? tel.getAttribute('href') : null, boutons: bandeau.querySelectorAll('button, input').length };
        }""", [equipement, type_ot, jour])

    def test_rappel_correctif_immediat_sous_garantie(self):
        rappel = self.rappel("EQ-0001", "correctif immédiat")
        self.assertTrue(rappel["element"])
        self.assertEqual(set(rappel["classes"].split()), {"alerte", "attention", "garanties-rappel"})
        self.assertEqual(rappel["role"], "status")             # un rappel, pas une alerte bloquante
        self.assertEqual(rappel["boutons"], 0)
        self.assertEqual(rappel["garantie"], "GAR-0001")
        self.assertEqual(rappel["paragraphes"], [
            "Équipement sous garantie jusqu'au 31/03/2027 (Hydraulique Services, tél. 04 65 71 00 99). "
            "Appeler le fournisseur avant d'intervenir ?",
            "Conditions : Pièces et main-d'œuvre"])
        self.assertEqual(rappel["tel"], "tel:0465710099")

    def test_rappel_correctif_differe_et_ligne_de_l_equipement(self):
        self.assertEqual(self.rappel("EQ-0001", "correctif différé")["garantie"], "GAR-0001")
        garantie = self.js("""(jour) => Garanties.rappelOt(Donnees.trouver('equipements', 'EQ-0001'), 'correctif immédiat',
          jour).dataset.garantie""", JOUR)
        self.assertEqual(garantie, "GAR-0001")

    def test_rappel_null_pour_un_preventif_ou_une_amelioration(self):
        for type_ot in ("préventif systématique", "préventif conditionnel", "amélioration", "", None):
            with self.subTest(type_ot=type_ot):
                self.assertIsNone(self.rappel("EQ-0001", type_ot))

    def test_rappel_null_sans_garantie_en_cours(self):
        self.assertIsNone(self.rappel("EQ-0003", "correctif immédiat"))
        self.assertIsNone(self.rappel("EQ-0004", "correctif immédiat"))            # contrat seulement
        self.assertIsNone(self.rappel("EQ-0001", "correctif immédiat", "2029-04-01"))
        self.assertIsNone(self.rappel("EQ-0001", "correctif immédiat", "2025-05-31"))  # avant le début
        self.assertIsNone(self.rappel("", "correctif immédiat"))

    def test_rappel_fournisseur_sans_telephone_et_conditions_sur_plusieurs_lignes(self):
        rappel = self.rappel("EQ-0002", "correctif différé")
        self.assertEqual(rappel["paragraphes"][0], "Équipement sous garantie jusqu'au 31/12/2026 (Air Maintenance). "
                                                   "Appeler le fournisseur avant d'intervenir ?")
        self.assertTrue(rappel["paragraphes"][1].startswith("Conditions : Pièces et main-d'œuvre.\nPièces d'usure"))
        self.assertIsNone(rappel["tel"])

    def test_rappel_sans_fournisseur_ni_conditions(self):
        rappel = self.rappel("EQ-0005", "correctif immédiat")
        self.assertEqual(rappel["paragraphes"], ["Équipement sous garantie jusqu'au 31/01/2027. "
                                                 "Appeler le fournisseur avant d'intervenir ?"])

    def test_rappel_n_ecrit_rien_au_journal(self):
        nombres = self.js("""(jour) => {
          const avant = Donnees.lignes('journal').length;
          Garanties.rappelOt('EQ-0001', 'correctif immédiat', jour);
          return [avant, Donnees.lignes('journal').length, Donnees.lignes('garanties').length];
        }""", JOUR)
        self.assertEqual(nombres, [0, 0, 10])

    def test_rappel_en_anglais(self):
        self.js("() => I18n.choisir('en')")
        rappel = self.rappel("EQ-0001", "correctif immédiat")
        self.assertEqual(rappel["paragraphes"], [
            "Equipment under warranty until 31/03/2027 (Hydraulique Services, tel. 04 65 71 00 99). "
            "Call the supplier before any work?",
            "Terms: Pièces et main-d'œuvre"])


class TestCarte(CasEncarts):

    def carte(self, equipement, responsable, jour=JOUR):
        return self.js("""([equipement, responsable, jour]) => {
          const carte = Garanties.carteEquipement(equipement, responsable, jour);
          document.body.appendChild(carte);
          const textes = (selecteur, racine) => [...(racine || carte).querySelectorAll(selecteur)].map((e) => e.textContent.replace(/\\s+/g, ' ').trim());
          const items = (selecteur) => [...carte.querySelectorAll(selecteur)].map((li) => {
            const statut = li.querySelector('.garanties-statut');
            return { id: li.dataset.garantie || li.dataset.contrat, texte: li.textContent.replace(/\\s+/g, ' ').trim(),
                     statut: statut ? statut.dataset.statut : null,
                     liens: [...li.querySelectorAll('a')].map((a) => a.getAttribute('href')) };
          });
          const ajouter = carte.querySelector('#garanties-ajouter-garantie');
          return {
            element: carte.tagName, titre: textes('h2')[0], sousTitres: textes('h3'),
            ajouter: ajouter ? ajouter.getAttribute('href') : null,
            vide: textes('p.muted'), notes: textes('p.note'), pasSousGarantie: textes('.garanties-encart-pas-sous-garantie'),
            enCours: items('.garanties-encart-en-cours'), autres: items('.garanties-encart-autres > li'),
            contrats: items('.garanties-encart-contrats > li'),
            liensResponsable: [...carte.querySelectorAll('a[href^="#/garanties"]')].map((a) => a.getAttribute('href')),
            texte: carte.textContent, html: carte.innerHTML,
          };
        }""", [equipement, responsable, jour])

    def assert_sans_montant(self, carte):
        for interdit in ("€", "4800", "4 800", "1350", "1 350", "9999", "montant", "contrat-CTP-0001"):
            with self.subTest(interdit=interdit):
                self.assertNotIn(interdit, carte["html"])

    def test_carte_technicien_garantie_en_cours_et_contrats(self):
        carte = self.carte("EQ-0001", False)
        self.assertEqual(carte["element"], "ARTICLE")
        self.assertEqual(carte["titre"], "Garanties et contrats")
        self.assertIsNone(carte["ajouter"])
        self.assertEqual(carte["liensResponsable"], [])         # écrans du responsable seul
        self.assertEqual([g["id"] for g in carte["enCours"]], ["GAR-0001"])
        en_cours = carte["enCours"][0]
        self.assertTrue(en_cours["texte"].startswith("Sous garantie jusqu'au 31/03/2027 en cours"))
        self.assertIn("Hydraulique Services", en_cours["texte"])
        self.assertIn("M. Roux", en_cours["texte"])
        self.assertIn("tel:0465710099", en_cours["liens"])
        self.assertIn("Conditions Pièces et main-d'œuvre", en_cours["texte"])
        self.assertIn("garantie-GAR-0001-2025-06-01.pdf", en_cours["texte"])   # page sans application : le nom
        self.assertEqual(carte["sousTitres"], ["Autres garanties", "Contrats de prestataires"])
        # à venir, puis les 3 dernières terminées (GAR-0005, la plus ancienne, n'est pas affichée) ; GAR-0007 retirée
        self.assertEqual([g["id"] for g in carte["autres"]], ["GAR-0006", "GAR-0002", "GAR-0003", "GAR-0004"])
        self.assertEqual(carte["autres"][0]["texte"], "à venir commence le 01/04/2027 Hydraulique Services")
        self.assertEqual(carte["autres"][1]["texte"], "terminée terminée le 31/01/2025 Air Maintenance")
        self.assertEqual(carte["notes"], ["1 garantie terminée plus ancienne n'est pas affichée."])
        self.assertNotIn("GAR-0007", carte["html"])
        self.assertNotIn("Retirée", carte["texte"])
        # contrats actifs qui citent l'équipement, les terminés en dernier ; ni statut ni lien pour le technicien
        self.assertEqual([c["id"] for c in carte["contrats"]], ["CTP-0001", "CTP-0002"])
        self.assertEqual(carte["contrats"][0]["texte"], "Maintenance des compresseurs Air Maintenance jusqu'au 31/12/2026")
        self.assertEqual(carte["contrats"][1]["texte"],
                         "Vérification des compresseurs Hydraulique Services · 04 65 71 00 99 terminé le 30/06/2025")
        self.assertEqual(carte["contrats"][1]["liens"], ["tel:0465710099"])
        self.assertTrue(all(c["statut"] is None for c in carte["contrats"]))
        self.assert_sans_montant(carte)

    def test_carte_responsable_ajouter_liens_statut_des_contrats(self):
        carte = self.carte("EQ-0001", True)
        self.assertEqual(carte["ajouter"], "#/garanties/garantie/nouvelle?equipement=EQ-0001")
        self.assertIn("#/garanties/garantie/GAR-0001", carte["enCours"][0]["liens"])
        self.assertEqual(carte["autres"][0]["liens"], ["#/garanties/garantie/GAR-0006"])
        self.assertEqual(carte["contrats"][0]["liens"], ["#/garanties/contrat/CTP-0001"])
        self.assertEqual(carte["contrats"][0]["statut"], "a_decider")
        self.assertEqual(carte["contrats"][0]["texte"],
                         "Maintenance des compresseurs à décider Air Maintenance à résilier au plus tard le 30/09/2026 "
                         "(dans 45 jours), sinon il est reconduit le 31/12/2026")
        self.assertEqual(carte["contrats"][1]["statut"], "termine")
        self.assert_sans_montant(carte)

    def test_carte_garantie_qui_se_termine_bientot(self):
        carte = self.carte("EQ-0001", False, "2027-02-15")
        self.assertEqual(carte["enCours"][0]["statut"], "bientot")
        self.assertIn("se termine bientôt se termine dans 44 jours, le 31/03/2027", carte["enCours"][0]["texte"])

    def test_carte_pas_sous_garantie_aujourd_hui(self):
        carte = self.carte("EQ-0001", False, "2029-04-01")
        self.assertEqual(carte["pasSousGarantie"], ["Pas sous garantie aujourd'hui."])
        self.assertEqual(carte["enCours"], [])
        self.assertEqual([g["id"] for g in carte["autres"]], ["GAR-0006", "GAR-0001", "GAR-0002"])
        self.assertEqual(carte["notes"], ["3 garanties terminées plus anciennes ne sont pas affichées."])

    def test_carte_vide_expliquee(self):
        for responsable in (False, True):
            with self.subTest(responsable=responsable):
                carte = self.carte("EQ-0003", responsable)
                self.assertEqual(carte["vide"], ["Aucune garantie ni aucun contrat pour cet équipement."])
                self.assertEqual(carte["sousTitres"], [])
                self.assertEqual(carte["ajouter"] is not None, responsable)

    def test_carte_contrats_seuls_reconduit_tacitement(self):
        carte = self.carte("EQ-0004", False)
        self.assertEqual(carte["vide"], [])
        self.assertEqual(carte["pasSousGarantie"], [])          # aucune garantie enregistrée : rien à dire
        self.assertEqual(carte["sousTitres"], ["Contrats de prestataires"])
        self.assertEqual([c["id"] for c in carte["contrats"]], ["CTP-0003", "CTP-0001"])
        self.assertEqual(carte["contrats"][0]["texte"],
                         "Thermographie Hydraulique Services · 04 65 71 00 99 reconduit tacitement le 31/12/2025")
        self.assert_sans_montant(carte)
        # période reconduite calculée (reconduction_mois connu) : le technicien lit jusqu'à quand
        texte = self.carte("EQ-0004", False, "2027-02-01")["contrats"][1]["texte"]
        self.assertEqual(texte, "Maintenance des compresseurs Air Maintenance reconduit tacitement le 31/12/2026, "
                                "jusqu'au 31/12/2027")

    def test_carte_fin_inconnue_et_conditions_courtes_sans_bouton(self):
        carte = self.carte("EQ-0002", False, "2026-06-01")
        self.assertEqual([g["id"] for g in carte["autres"]], ["GAR-0010"])
        self.assertEqual(carte["autres"][0]["statut"], "fin_inconnue")
        self.assertEqual(carte["autres"][0]["texte"], "fin inconnue date de fin non renseignée")
        self.assertEqual(self.js("() => document.querySelectorAll('.garanties-encart-deplier').length"), 1)
        self.js("() => { document.body.textContent = ''; }")
        self.carte("EQ-0001", False)
        self.assertEqual(self.js("() => document.querySelectorAll('.garanties-encart-deplier').length"), 0)

    def test_carte_conditions_repliees_au_dela_de_3_lignes(self):
        self.carte("EQ-0002", False, "2026-06-01")
        def etat():
            return self.js("""() => {
              const zone = document.querySelector('.garanties-encart-conditions');
              const bouton = document.querySelector('.garanties-encart-deplier');
              const ligne = parseFloat(getComputedStyle(zone).lineHeight) || 24;
              return { replie: zone.classList.contains('replie'), lignes: Math.round(zone.getBoundingClientRect().height / ligne),
                       ouvert: bouton.getAttribute('aria-expanded'), bouton: bouton.textContent,
                       controle: bouton.getAttribute('aria-controls') === zone.id };
            }""")
        # la feuille du module n'est pas chargée dans la page vide : elle est ajoutée pour mesurer le pliage
        self.page.add_style_tag(path=str(RACINE / "css" / "modules" / "garanties.css"))
        self.page.add_style_tag(content=".garanties-encart-conditions { line-height: 20px; }")
        replie = etat()
        self.assertEqual(replie, {"replie": True, "lignes": 3, "ouvert": "false", "bouton": "Afficher toutes les conditions",
                                  "controle": True})
        self.page.click(".garanties-encart-deplier")
        deplie = etat()
        self.assertFalse(deplie["replie"])
        self.assertEqual(deplie["lignes"], 5)
        self.assertEqual((deplie["ouvert"], deplie["bouton"]), ("true", "Replier les conditions"))
        self.page.click(".garanties-encart-deplier")
        self.assertTrue(etat()["replie"])

    def test_carte_documents_relies_par_le_stockage(self):
        self.js("""() => { window.App = { adaptateur: { urlDocument: async (nom) =>
          (nom === 'garantie-GAR-0001-2025-06-01.pdf' ? 'blob:essai/' + nom : null) } }; }""")
        self.carte("EQ-0001", False)
        self.page.wait_for_function("() => !document.querySelector('.garanties-carte-equipement [data-document]')")
        lien = self.js("""() => { const a = document.querySelector('.garanties-encart-document a.garanties-document');
          return [a.getAttribute('href'), a.getAttribute('target'), a.textContent.trim(),
                  document.querySelector('.garanties-encart-document').textContent.replace(/\\s+/g, ' ').trim()]; }""")
        self.assertEqual(lien, ["blob:essai/garantie-GAR-0001-2025-06-01.pdf", "_blank", "Ouvrir",
                                "Ouvrir garantie-GAR-0001-2025-06-01.pdf"])
        self.js("() => { document.body.textContent = ''; }")
        self.carte("EQ-0002", False, "2026-06-01")
        self.page.wait_for_function("() => !document.querySelector('.garanties-carte-equipement [data-document]')")
        self.assertEqual(self.js("() => document.querySelector('.garanties-encart-document').textContent.trim()"),
                         "Fichier introuvable : garantie-GAR-0008-absente.pdf")

    def test_carte_accepte_la_ligne_et_rend_un_element(self):
        resultat = self.js("""(jour) => {
          const carte = Garanties.carteEquipement(Donnees.trouver('equipements', 'EQ-0005'), false, jour);
          return [carte instanceof HTMLElement, carte.dataset.equipement,
                  carte.querySelector('.garanties-encart-en-cours').textContent.replace(/\\s+/g, ' ').trim()];
        }""", JOUR)
        self.assertEqual(resultat, [True, "EQ-0005", "Sous garantie jusqu'au 31/01/2027 en cours"])

    def test_carte_en_anglais(self):
        self.js("() => I18n.choisir('en')")
        carte = self.carte("EQ-0004", False)
        self.assertEqual(carte["titre"], "Warranties and contracts")
        self.assertEqual(carte["sousTitres"], ["Contractor agreements"])
        self.assertEqual(carte["contrats"][1]["texte"], "Maintenance des compresseurs Air Maintenance until 31/12/2026")


if __name__ == "__main__":
    unittest.main()
