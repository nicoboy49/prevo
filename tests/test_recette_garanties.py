"""Recette du L4 de la 2.2 « garanties et contrats de prestataires » (T461 ; CDC §3.4, CS173, CS175 côté Garanties et
contrats, CS177 côté réseau ; décisions D182, D187, D190 ; QUESTIONS-L2-L6 : L4-L6 Q1, Q3, Q6, Q7, Q12, et réponse
PROVISOIRE n° 3 pour les contrats signés, à confirmer par Nicolas). De bout en bout, à l'écran, comme un responsable
puis comme un technicien, horloge du navigateur figée (jamais la date réelle) ; les tests de chaque partie
(test_garanties_*, test_parc_garanties, test_ordres_garantie, test_parametres_alerte) ne sont pas recopiés ici ;
l'alerte d'accueil de CS173 est au L6 (T485, QUESTIONS-L2-L6 L4-L6 Q8).

Le parcours (CasRecette.parcours), le même dans trois modes :
    TestParcoursServeur         serveur.py sur une COPIE du jeu de démo, sans comptes (portée « ce PC ») ; données et
                                documents relus sur le disque ; le technicien : un autre contexte, son profil ;
    TestParcoursServeurComptes  la même chose avec les trois comptes de test (session du responsable), puis la session
                                du technicien : contrats reçus sans montant, refus 403 du serveur à l'écriture des deux
                                tables et au contrat signé, certificat de la garantie servi ;
    TestParcoursDemo            index.html en file://, « Essayer avec les données de démo » ; données en mémoire ; le
                                technicien : changement de profil dans la même page (recharger perdrait la démo).
Étapes, profil Responsable ; E : un équipement suivi de la démo, sans garantie ni contrat :
    31/07/2026  garantie de E créée depuis sa fiche (« Ajouter une garantie »), certificat PDF joint, jusqu'au
                31/05/2028 : fiche, document servi, journal ; contrat de CS173 créé par le formulaire (fin 31/12/2026,
                préavis 3 mois, reconduction tacite par périodes de 12 mois, 4 800,50 € HT, contrat signé joint, E
                cité) : « Date limite de résiliation : 30/09/2026 » avant l'enregistrement ; « en cours » la veille du
                délai ;
    01/08/2026  CS173 : « à décider » (liste, compteur « Contrats à décider », fiche : bandeau, « Écrire au
                prestataire ») ;
    Paramètres  délai d'alerte réglé à 30 jours (écrit) : « en cours » le 01/08 et le 30/08, « à décider » le 31/08 ;
    15/01/2027  fin passée sans rien faire, reconduction tacite : « dates à mettre à jour », rien d'écrit ;
    31/08/2027  période reconduite calculée : « à décider » avant le 30/09/2027, rien d'écrit (Q3) ; « Reconduire »
                (01/01/2027-31/12/2027 : écrit, journal) ; « Noter la résiliation » (reconduction tacite à non,
                journal) ; retrait d'une garantie terminée de E (avec son document) et d'un autre contrat de E : actif
                à 0, ligne inchangée sinon, document gardé, journal gardé ; ni l'une ni l'autre dans les listes ni sur
                la fiche de E (Q12) ; fiche de E : badge « Sous garantie jusqu'au 31/05/2028 », carte « Garanties et
                contrats » (liens du responsable, aucun montant) ; OT correctif créé depuis la fiche de E : rappel
                « Appeler le fournisseur avant d'intervenir ? » (absent pour un préventif), création non bloquée, rien
                au journal sur la garantie (Q7) ;
    01/05/2028  garantie de E « se termine bientôt » (30 jours avant sa fin ; « en cours » la veille), badge ambre ;
                retour au 31/08/2027.
Phrase D182 sur les écrans Garanties et contrats (liste, fiches) ; aucun « conforme » sur aucun écran du parcours.
Puis, profil Technicien (31/08/2027) : ni menu ni adresse Garanties ; fiche de E : badge, carte sans lien vers les écrans
du responsable ni montant, ni la garantie ni le contrat retirés ; il ouvre le certificat de la garantie depuis la fiche ;
l'application refuse ses écritures (garantie, contrat, retrait, résiliation) et n'écrit rien. Avec comptes, en plus :
contrats_prestataires reçu sans montant_annuel ; PUT et ajout de garanties et de contrats_prestataires refusés (403,
fichiers inchangés) ; contrat signé refusé (403), servi au responsable ; certificat de la garantie servi.
Aucune requête vers une autre adresse que l'application (serveur local, file:, blob:, data:), sauf la lecture de
version existante de T305 (prevo.pro/version.json, servie par le contexte des tests) : aucune sortie nouvelle (CS177).

Chaque cas travaille sur une copie du jeu de démo dans un dossier temporaire (serveur), ou en mémoire (démo) : jamais
de données réelles. Garanties, contrats et équipement trouvés par les données, aucun identifiant écrit en dur.

Bibliothèque standard + Playwright. Lancer depuis la racine du projet (au travers du verrou des navigateurs) :
    py -X utf8 -m unittest discover -s tests -p "test_recette_garanties.py" -v
"""
import datetime
import unittest
from pathlib import Path

from commun import (ADRESSE_VERSION_JSON, COMPTES_DE_TEST, CasNavigateur, ServeurPrevo, attendre_pret,
                    preregler_profil, url_fichier)
from test_droits_format4 import BOM, REFUS_DOCUMENT, premiere_ligne, requete
from test_principe_suivi import MOT_CONFORME, PHRASE
from test_rapport import lire_csv

# ---------------------------------------------------------------------------
# Ce que la recette attend
# ---------------------------------------------------------------------------

# Jours du parcours (horloge du navigateur figée à 9 h).
J0, J1 = "2026-07-31", "2026-08-01"                    # veille du délai de 60 jours, puis premier jour « à décider »
J2_VEILLE, J2 = "2026-08-30", "2026-08-31"             # délai réglé à 30 jours
J3, J4 = "2027-01-15", "2027-08-31"                    # fin passée (reconduction tacite), période calculée à décider

PDF_GARANTIE = b"%PDF-1.4\n% certificat de garantie (recette T461)\n%%EOF\n"
PDF_CONTRAT = b"%PDF-1.4\n% contrat signe, avec son prix (recette T461)\n%%EOF\n"
PDF_ANCIENNE = b"%PDF-1.4\n% ancienne garantie terminee (recette T461)\n%%EOF\n"

GARANTIE = {"date_debut": "2026-06-01", "date_fin": "2028-05-31",
            "conditions": "Pièces et main-d'œuvre ; appeler le fournisseur avant tout démontage (recette L4)."}
CONTRAT = {"objet": "Maintenance préventive (recette L4)", "date_debut": "2026-01-01", "date_fin": "2026-12-31",
           "preavis_mois": "3", "reconduction_tacite": "1", "reconduction_mois": "12", "montant_annuel": "4800.50"}
MONTANT_SAISI, MONTANT_AFFICHE = "4 800,50", "4 800,50 €"
# Ce que le technicien ne voit jamais, sous aucune forme (D126 prolongé, Q6) ; « 1250 » : le contrat retiré.
MONTANTS = ("4 800,50", "4800,50", "4800.50", "1 250,00")
ANCIENNE = {"date_debut": "2024-01-01", "date_fin": "2025-12-31", "conditions": "Ancienne garantie (recette L4)"}
CONTRAT_RETIRE = {"objet": "Contrat à retirer (recette L4)", "date_debut": "2027-01-01", "date_fin": "2027-12-31",
                  "preavis_mois": "1", "reconduction_tacite": "0", "montant_annuel": "1250"}
LETTRE = "Lettre recommandée avec accusé de réception (recette L4)"

REFUS_APPLICATION = "Seul le responsable enregistre les garanties et les contrats."
REFUS_TABLE = "Accès refusé : la table « {table} » ne se modifie que par le responsable."
ESPACES = {0xA0: " ", 0x202F: " "}

FENETRE = "dialog[open] "
BADGE = "#contenu .parc-badges-fiche .garanties-badge-equipement"
CARTE = "#contenu .garanties-carte-equipement"
PANNEAU = ".panneau-onglet[data-onglet='%s']:not([hidden])"
CHAMP_DELAI = "#form-parametres [name=alerte_echeances_jours]"
ZONE_RAPPEL = "#form-nouvel-ot .ot-zone-garantie"

# Si location.hash est déjà la route, l'écran est redessiné (App.reafficher), sinon on y va.
ALLER_JS = "(route) => { if (location.hash === route) return App.reafficher(); location.hash = route; return null; }"
LIGNES_JS = "(table) => Donnees.lignes(table).map((ligne) => Object.assign({}, ligne))"
# Un équipement suivi, avec un repère, sans habilitation exigée, qu'aucune garantie ni aucun contrat ne cite.
EQUIPEMENT_LIBRE_JS = """() => {
  const garanties = Donnees.lignes('garanties'), contrats = Donnees.lignes('contrats_prestataires');
  const e = Donnees.lignes('equipements').find((e) => String(e.actif) !== '0' && e.statut !== 'rebut'
    && String(e.repere || '').trim() && !String(e.habilitation_requise || '').trim()
    && !garanties.some((g) => g.equipement_id === e.id)
    && !contrats.some((c) => Garanties.equipementsDuContrat(c).includes(e.id)));
  return { id: e.id, repere: e.repere, designation: e.designation }; }"""
# Deux fournisseurs avec téléphone et e-mail : { id, nom, telephone, email } (téléphone : chiffres du lien tel:).
FOURNISSEURS_JS = """() => Donnees.lignes('fournisseurs').filter((f) => String(f.telephone || '').replace(/[^0-9+]/g, '')
  && String(f.email || '').trim()).slice(0, 2).map((f) => ({ id: f.id, nom: f.nom,
  telephone: String(f.telephone).replace(/[^0-9+]/g, ''), email: String(f.email).trim() }))"""
# Appel d'une fonction de l'application (« Garanties.creerContrat ») : { accepte } ou { refus, validation }.
APPEL_JS = """async ([chemin, arguments_]) => {
  const [objet, fonction] = chemin.split('.');
  try { return { accepte: await eval(objet)[fonction](...arguments_) }; }
  catch (erreur) { return { refus: erreur.message, validation: erreur instanceof Donnees.ErreurValidation }; } }"""
# Garantie créée par l'application avec un document joint (File construit dans la page).
GARANTIE_AVEC_DOCUMENT_JS = """async ([valeurs, octets, nom]) => Garanties.creerGarantie(valeurs,
  new File([new Uint8Array(octets)], nom, { type: 'application/pdf' }))"""
# Document ouvert par un lien de la page : { statut, octets }.
LIRE_LIEN_JS = """async (selecteur) => {
  const reponse = await fetch(document.querySelector(selecteur).href);
  return { statut: reponse.status, octets: Array.from(new Uint8Array(await reponse.arrayBuffer())) }; }"""
# Document lu par l'adaptateur de stockage (le même chemin que les liens « Ouvrir ») : octets, ou null.
LIRE_DOCUMENT_JS = """async (nom) => { const adresse = await App.adaptateur.urlDocument(nom);
  if (!adresse) return null; const reponse = await fetch(adresse);
  return reponse.ok ? Array.from(new Uint8Array(await reponse.arrayBuffer())) : null; }"""
# { identifiant : statut } des lignes de la liste affichée (onglet visible).
STATUTS_JS = """(panneau) => Object.fromEntries(Array.from(document.querySelectorAll(panneau
  + ' .garanties-liste tbody tr')).map((ligne) => [decodeURIComponent(ligne.querySelector('a.garanties-lien')
  .getAttribute('href').split('/').pop()), ligne.querySelector('[data-statut]').dataset.statut]))"""
# Valeur (dd) d'un libellé (dt) de la carte d'une fiche.
VALEUR_FICHE_JS = """(libelle) => { const dt = Array.from(document.querySelectorAll('.garanties-fiche .carte dt'))
  .find((d) => d.textContent.trim() === libelle); return dt ? dt.nextElementSibling.textContent.trim() : null; }"""
ETAT_CONTRAT_JS = """(id) => { const e = Garanties.etatContrat(Donnees.trouver('contrats_prestataires', id));
  return [e.statut, e.finPeriode, e.dateLimite, e.periodeCalculee]; }"""


def brut(valeur):
    """Valeur d'une cellule (CSV ou mémoire), sans l'apostrophe de protection contre Excel."""
    valeur = "" if valeur is None else str(valeur).strip()
    return valeur[1:] if valeur.startswith("'") else valeur


def propre(ligne):
    return {cle: brut(valeur) for cle, valeur in ligne.items() if cle is not None}


def heure(jour):
    return jour + "T09:00:00"


def fiche(identifiant):
    return "#/garanties/%s/%s" % ("contrat" if identifiant.startswith("CTP-") else "garantie", identifiant)


# ---------------------------------------------------------------------------
# Aides d'écran communes
# ---------------------------------------------------------------------------

class Ecran:
    """À mêler à un CasNavigateur ; le mode fournit lignes(table) (disque ou mémoire) et document(nom)."""

    def lignes(self, table):  # pragma: no cover - fourni par le mode
        raise NotImplementedError

    def document(self, nom):  # pragma: no cover - fourni par le mode
        raise NotImplementedError

    def js(self, script, argument=None, page=None):
        return (page or self.page).evaluate(script, argument)

    def appeler(self, chemin, *arguments, page=None):
        return self.js(APPEL_JS, [chemin, list(arguments)], page)

    def accepte(self, chemin, *arguments, page=None):
        resultat = self.appeler(chemin, *arguments, page=page)
        self.assertIn("accepte", resultat, resultat)
        return resultat["accepte"]

    def aller(self, route, selecteur, page=None):
        page = page or self.page
        page.evaluate(ALLER_JS, route)
        page.wait_for_selector(selecteur)

    def jour(self, date, route, selecteur):
        """Change le jour de l'horloge figée, puis (re)dessine l'écran de la route."""
        self.page.clock.set_fixed_time(heure(date))
        self.assertEqual(self.js("Donnees.aujourdhui()"), date)
        self.aller(route, selecteur)

    def attendre(self, condition, message="", delai_s=10):
        """Attend qu'une condition sur les données devienne vraie (le serveur écrit après la réponse de l'écran)."""
        fin = datetime.datetime.now() + datetime.timedelta(seconds=delai_s)
        while datetime.datetime.now() < fin:
            if condition():
                return
            self.page.wait_for_timeout(200)
        self.assertTrue(condition(), message)

    def attendre_toast(self, texte, page=None):
        # text_content : le toast entre par une transition de visibility (inner_text rendrait '' au premier instant).
        (page or self.page).wait_for_function(
            "(t) => document.getElementById('toast').textContent.includes(t)", arg=texte)

    def texte(self, selecteur, page=None):
        return (page or self.page).inner_text(selecteur).translate(ESPACES)

    def ligne(self, table, identifiant):
        return next(ligne for ligne in self.lignes(table) if ligne["id"] == identifiant)

    def journal_de(self, table, identifiant):
        return [j["action"] for j in self.lignes("journal") if j["table"] == table and j["id_ligne"] == identifiant]

    def parametre(self, cle):
        return next((p["valeur"] for p in self.lignes("parametres") if p["cle"] == cle), None)

    def sans_conforme(self, ecran, page=None):
        page = page or self.page
        texte = page.evaluate("() => document.querySelector('#contenu').innerText + ' ' + "
                              "Array.from(document.querySelectorAll('dialog[open]')).map((d) => d.innerText).join(' ')")
        self.assertIsNone(MOT_CONFORME.search(texte), "« conforme » sur l'écran %s" % ecran)

    def verifier_principe(self, ecran, zone):
        """CS175 côté Garanties et contrats : la phrase D182 dans la zone, une fois ; aucun « conforme » à l'écran."""
        with self.subTest(ecran=ecran):
            phrases = self.page.eval_on_selector_all(
                zone + " .garanties-principe", "l => l.filter((e) => e.getClientRects().length).map((e) => e.textContent.trim())")
            self.assertEqual(phrases, [PHRASE])
            self.sans_conforme(ecran)

    def verifier_lien(self, selecteur, octets, page=None):
        page = page or self.page
        page.wait_for_selector(selecteur)
        self.assertEqual(page.get_attribute(selecteur, "target"), "_blank")
        lu = page.evaluate(LIRE_LIEN_JS, selecteur)
        self.assertEqual((lu["statut"], bytes(lu["octets"])), (200, octets))

    # -- listes et fiches ---------------------------------------------------------------------------

    def statuts(self, onglet, page=None):
        return (page or self.page).evaluate(STATUTS_JS, PANNEAU % onglet)

    def liste(self, onglet):
        route = "#/garanties?onglet=" + onglet
        return route, PANNEAU % onglet + " .garanties-liste"

    def ligne_liste(self, onglet, identifiant):
        return self.texte(PANNEAU % onglet + " .garanties-liste tbody tr:has(a.garanties-lien[href='%s'])"
                          % fiche(identifiant))

    def statut_contrat(self, date, ctp):
        """Statut du contrat dans la liste des contrats, le jour donné."""
        self.jour(date, *self.liste("contrats"))
        return self.statuts("contrats")[ctp]

    def ouvrir_fiche(self, identifiant):
        cle = "data-contrat" if identifiant.startswith("CTP-") else "data-garantie"
        self.aller(fiche(identifiant), ".garanties-fiche[%s='%s']" % (cle, identifiant))
        self.verifier_principe("fiche " + identifiant, ".garanties-fiche")

    def statut_fiche(self):
        return self.page.get_attribute(".garanties-fiche .garanties-badges [data-statut]", "data-statut")

    def fiche_equipement(self, equipement, page=None):
        self.aller("#/equipement/" + equipement, CARTE + "[data-equipement='%s']" % equipement, page)
        self.sans_conforme("fiche de l'équipement", page)

    def retirer_depuis_la_fiche(self, identifiant, toast, onglet):
        """« Retirer » sur la fiche : confirmation, toast, retour à la liste ; la ligne reste, actif à 0, le reste
        inchangé ; le journal garde tout et ajoute le retrait (Q12 : jamais de suppression)."""
        page = self.page
        table = "contrats_prestataires" if identifiant.startswith("CTP-") else "garanties"
        avant, journal = self.ligne(table, identifiant), self.journal_de(table, identifiant)
        self.ouvrir_fiche(identifiant)
        page.click("#%s-retirer" % ("contrat" if table == "contrats_prestataires" else "garantie"))
        page.wait_for_selector(FENETRE + ".btn-danger")
        page.click(FENETRE + ".btn-danger")
        self.attendre_toast(toast)
        page.wait_for_function("(h) => location.hash === h", arg="#/garanties?onglet=" + onglet)
        self.attendre(lambda: self.ligne(table, identifiant)["actif"] == "0", identifiant + " pas retiré")
        self.assertEqual(self.ligne(table, identifiant), dict(avant, actif="0"))
        self.assertEqual(self.journal_de(table, identifiant)[:len(journal)], journal)
        self.assertEqual(self.journal_de(table, identifiant)[len(journal):],
                         ["modification : actif — %s" % ("contrat retiré" if table == "contrats_prestataires"
                                                          else "garantie retirée")])
        page.wait_for_selector(PANNEAU % onglet + " .garanties-liste")
        self.assertNotIn(identifiant, self.statuts(onglet))
        return avant


# ---------------------------------------------------------------------------
# Le parcours
# ---------------------------------------------------------------------------

class CasRecette(Ecran, CasNavigateur):
    """Le mode ouvre l'application (profil Responsable, horloge figée au 31/07/2026), appelle parcours(), puis ouvre
    la vue du technicien."""

    def noter_requetes(self, page):
        page.on("request", lambda requete: self.requetes.append(requete.url))

    def verifier_reseau(self, origine):
        """CS177 : aucune requête hors de l'application ; seule la lecture de version de T305 (existante) sort."""
        locales = (origine, "file:", "blob:", "data:", "about:")
        externes = [u for u in self.requetes if not u.startswith(locales) and u != ADRESSE_VERSION_JSON]
        self.assertGreater(len(self.requetes), 10)
        self.assertEqual(externes, [], "requêtes vers une autre adresse que l'application")

    def parcours(self):
        self.assertEqual(self.js("Donnees.aujourdhui()"), J0)
        self.e = self.js(EQUIPEMENT_LIBRE_JS)
        self.f1, self.f2 = self.js(FOURNISSEURS_JS)
        g1 = self.garantie_depuis_la_fiche()
        ctp = self.contrat_cs173()
        self.cs173_a_decider(ctp)
        self.reglage_a_30_jours(ctp)
        self.reconduction_tacite(ctp)
        retires = self.retraits()
        self.fiche_equipement_du_responsable(g1, ctp, retires)
        ot = self.rappel_a_l_ot_correctif(g1)
        self.echeance_de_la_garantie(g1)
        return {"g1": g1, "ctp": ctp, "retires": retires, "ot": ot}

    # -- 31/07/2026 : la garantie, depuis la fiche de E ---------------------------------------------

    def garantie_depuis_la_fiche(self):
        page, e = self.page, self.e["id"]
        self.fiche_equipement(e)
        self.assertEqual(page.locator(BADGE).count(), 0)
        self.assertIn("Aucune garantie ni aucun contrat pour cet équipement.", page.inner_text(CARTE))
        page.click(CARTE + " #garanties-ajouter-garantie")
        page.wait_for_selector("#form-garantie .selecteur-choisi:not([hidden])")
        self.assertEqual(page.input_value("#form-garantie input[name=equipement_id]"), e)
        page.select_option("#form-garantie [name=fournisseur_id]", self.f1["id"])
        for nom in ("date_debut", "date_fin", "conditions"):
            page.fill("#form-garantie [name=%s]" % nom, GARANTIE[nom])
        page.set_input_files("#form-garantie input[type=file]",
                             files=[{"name": "certificat.pdf", "mimeType": "application/pdf", "buffer": PDF_GARANTIE}])
        page.click("#form-garantie button[type=submit]")
        self.attendre_toast("Garantie enregistrée.")
        page.wait_for_function("() => /^#\\/garanties\\/garantie\\/GAR-/.test(location.hash)")
        g1 = self.js("decodeURIComponent(location.hash.split('/').pop())")
        self.attendre(lambda: any(g["id"] == g1 for g in self.lignes("garanties")), "garantie non écrite")

        ligne = self.ligne("garanties", g1)
        self.assertEqual({c: ligne[c] for c in ("equipement_id", "fournisseur_id", "date_debut", "date_fin", "conditions",
                                                "actif")}, dict(GARANTIE, equipement_id=e, fournisseur_id=self.f1["id"], actif="1"))
        self.assertRegex(ligne["document"], r"(^|-)garantie-%s-%s\.pdf$" % (g1, J0))
        self.assertEqual(self.document(ligne["document"]), PDF_GARANTIE)
        self.assertEqual(self.journal_de("garanties", g1), ["création — garantie enregistrée ; document : " + ligne["document"]])

        # La fiche : en cours jusqu'au 31/05/2028, fournisseur joignable, conditions, certificat servi, phrase D182.
        self.ouvrir_fiche(g1)
        self.assertEqual(self.statut_fiche(), "en_cours")
        self.assertIn("jusqu'au 31/05/2028", page.inner_text(".garanties-fiche .garanties-raison"))
        self.assertEqual(page.get_attribute(".garanties-fournisseur a[href^='tel:']", "href"), "tel:" + self.f1["telephone"])
        self.assertIn(GARANTIE["conditions"], page.inner_text(".garanties-texte-long"))
        self.verifier_lien(".garanties-fiche a.garanties-document", PDF_GARANTIE)
        return g1

    # -- 31/07/2026 : le contrat de CS173, par le formulaire -----------------------------------------

    def contrat_cs173(self):
        page, e = self.page, self.e["id"]
        self.aller("#/garanties", ".garanties-ecran .garanties-onglets")
        self.verifier_principe("liste des garanties et contrats", ".garanties-ecran .entete-page")
        page.click("#garanties-nouveau-contrat")
        page.wait_for_selector("#form-contrat")
        self.assertIn("HT", page.inner_text("#form-contrat .champ[data-champ=montant_annuel] .libelle"))
        self.sans_conforme("nouveau contrat")
        page.select_option("#form-contrat [name=fournisseur_id]", self.f2["id"])
        page.fill("#form-contrat [name=objet]", CONTRAT["objet"])
        for nom in ("date_debut", "date_fin", "preavis_mois"):
            page.fill("#form-contrat [name=%s]" % nom, CONTRAT[nom])
        # CS173 : la date limite de résiliation se voit à la saisie, avant tout enregistrement.
        self.assertEqual(page.inner_text("#form-contrat .garanties-date-limite").strip(),
                         "Date limite de résiliation : 30/09/2026")
        page.check("#form-contrat [name=reconduction_tacite]")
        page.fill("#form-contrat [name=reconduction_mois]", CONTRAT["reconduction_mois"])
        page.fill("#form-contrat .garanties-selecteur input[type=search]", self.e["repere"])
        page.click("#form-contrat .garanties-selecteur .selecteur-option[data-id='%s']" % e)
        page.click("#form-contrat .garanties-ajouter-equipement")
        self.assertEqual(page.input_value("#form-contrat input[name=equipement_ids]"), e)
        page.fill("#form-contrat [name=montant_annuel]", MONTANT_SAISI)
        page.set_input_files("#form-contrat input[type=file]",
                             files=[{"name": "contrat signé.pdf", "mimeType": "application/pdf", "buffer": PDF_CONTRAT}])
        self.assertFalse(any(c["objet"] == CONTRAT["objet"] for c in self.lignes("contrats_prestataires")))
        page.click("#form-contrat button[type=submit]")
        self.attendre_toast("Contrat enregistré.")
        page.wait_for_function("() => /^#\\/garanties\\/contrat\\/CTP-/.test(location.hash)")
        ctp = self.js("decodeURIComponent(location.hash.split('/').pop())")
        self.attendre(lambda: any(c["id"] == ctp for c in self.lignes("contrats_prestataires")), "contrat non écrit")

        ligne = self.ligne("contrats_prestataires", ctp)
        self.assertEqual({c: ligne[c] for c in list(CONTRAT) + ["fournisseur_id", "equipement_ids", "actif"]},
                         dict(CONTRAT, fournisseur_id=self.f2["id"], equipement_ids=e, actif="1"))
        self.assertRegex(ligne["document"], r"(^|-)contrat-%s-%s\.pdf$" % (ctp, J0))
        self.assertEqual(self.document(ligne["document"]), PDF_CONTRAT)
        self.assertEqual(self.journal_de("contrats_prestataires", ctp),
                         ["création — contrat enregistré ; document : " + ligne["document"]])

        # La fiche, la veille du délai : en cours, date limite dans 61 jours, montant pour le responsable, pas de bandeau.
        self.ouvrir_fiche(ctp)
        self.assertEqual(self.statut_fiche(), "en_cours")
        self.assertEqual(self.texte(".garanties-fiche .garanties-raison"),
                         "jusqu'au 31/12/2026 (date limite de résiliation le 30/09/2026)")
        carte = self.texte(".garanties-fiche .carte")
        for morceau in ("3 mois", "30/09/2026, dans 61 jours", "Oui, par périodes de 12 mois", MONTANT_AFFICHE):
            self.assertIn(morceau, carte)
        self.assertEqual(page.get_attribute(".garanties-equipements-liste a", "href"), "#/equipement/" + e)
        self.assertEqual(page.locator(".garanties-bandeau").count(), 0)
        self.verifier_lien(".garanties-fiche a.garanties-document", PDF_CONTRAT)
        self.assertEqual(self.statut_contrat(J0, ctp), "en_cours")
        self.assertIn(MONTANT_AFFICHE, self.ligne_liste("contrats", ctp))
        return ctp

    # -- 01/08/2026 : CS173, « à décider » au délai par défaut (60 jours) ----------------------------

    def cs173_a_decider(self, ctp):
        page = self.page
        self.assertEqual(self.statut_contrat(J1, ctp), "a_decider")
        self.assertIn("à résilier au plus tard le 30/09/2026 (dans 60 jours), sinon il est reconduit le 31/12/2026",
                      self.ligne_liste("contrats", ctp))
        self.sans_conforme("liste des contrats")
        page.click(".garanties-compteurs a[data-compteur='a-decider']")
        page.wait_for_function("location.hash === '#/garanties?onglet=contrats&filtre=a-decider'")
        page.wait_for_selector(PANNEAU % "contrats" + " .garanties-liste tbody tr")
        self.assertEqual(self.statuts("contrats").get(ctp), "a_decider")
        self.ouvrir_fiche(ctp)
        self.assertEqual(self.statut_fiche(), "a_decider")
        self.assertEqual(self.texte(".garanties-bandeau p"),
                         "Pour ne pas être reconduit le 31/12/2026, ce contrat doit être résilié au plus tard le "
                         "30/09/2026 (dans 60 jours). Prévo n'envoie rien : écrivez au prestataire.")
        self.assertTrue(page.get_attribute("#contrat-ecrire", "href").startswith("mailto:" + self.f2["email"] + "?subject="))

    # -- Paramètres : délai réglé à 30 jours → « à décider » le 31/08/2026 ---------------------------

    def reglage_a_30_jours(self, ctp):
        page = self.page
        self.aller("#/parametres", CHAMP_DELAI)
        self.assertEqual(page.input_value(CHAMP_DELAI), "60")
        page.fill(CHAMP_DELAI, "30")
        page.click("#form-parametres button[type=submit]")
        self.attendre_toast("Paramètres enregistrés")
        self.attendre(lambda: self.parametre("alerte_echeances_jours") == "30", "délai non écrit")
        self.assertEqual(self.js("Garanties.delaiAlerte()"), 30)
        self.sans_conforme("Paramètres")
        self.assertEqual(self.statut_contrat(J1, ctp), "en_cours")
        self.assertEqual(self.statut_contrat(J2_VEILLE, ctp), "en_cours")
        self.assertEqual(self.statut_contrat(J2, ctp), "a_decider")
        self.assertIn("à résilier au plus tard le 30/09/2026 (dans 30 jours)", self.ligne_liste("contrats", ctp))

    # -- 2027 : reconduction tacite, « Reconduire », « Noter la résiliation » ------------------------

    def reconduction_tacite(self, ctp):
        page = self.page
        avant = self.ligne("contrats_prestataires", ctp)
        # 15/01/2027 : la fin enregistrée est passée, rien n'a été fait : le contrat continue, dates à mettre à jour.
        self.assertEqual(self.statut_contrat(J3, ctp), "a_mettre_a_jour")
        self.assertIn("reconduit tacitement le 31/12/2026 : saisissez la nouvelle période", self.ligne_liste("contrats", ctp))
        self.assertEqual(self.js(ETAT_CONTRAT_JS, ctp), ["a_mettre_a_jour", "2027-12-31", "2027-09-30", True])
        self.ouvrir_fiche(ctp)
        self.assertEqual(self.texte(".garanties-bandeau p"),
                         "Reconduit tacitement le 31/12/2026 : saisissez la nouvelle période (« Reconduire »).")
        # 31/08/2027 : la période reconduite est calculée (12 mois) : à décider avant le 30/09/2027 (Q3).
        self.assertEqual(self.statut_contrat(J4, ctp), "a_decider")
        self.assertIn("reconduit tacitement le 31/12/2026 ; période calculée : à résilier au plus tard le 30/09/2027 "
                      "(dans 30 jours) ; saisissez la nouvelle période", self.ligne_liste("contrats", ctp))
        self.assertEqual(self.ligne("contrats_prestataires", ctp), avant)              # rien d'écrit sans clic

        # « Reconduire » : la période proposée (fin + 12 mois), écrite, au journal.
        self.ouvrir_fiche(ctp)
        page.click("#contrat-reconduire")
        page.wait_for_selector(FENETRE + "[name=date_fin]")
        self.assertEqual((page.input_value(FENETRE + "[name=date_debut]"), page.input_value(FENETRE + "[name=date_fin]")),
                         ("2027-01-01", "2027-12-31"))
        page.click(FENETRE + ".fenetre-actions .btn-primaire")
        self.attendre_toast("Contrat reconduit jusqu'au 31/12/2027.")
        self.attendre(lambda: self.ligne("contrats_prestataires", ctp)["date_fin"] == "2027-12-31", "reconduction non écrite")
        self.assertEqual(self.ligne("contrats_prestataires", ctp), dict(avant, date_debut="2027-01-01", date_fin="2027-12-31"))
        self.assertEqual(self.journal_de("contrats_prestataires", ctp)[-1],
                         "modification : date_debut, date_fin — reconduction : du 01/01/2026 au 31/12/2026 → "
                         "du 01/01/2027 au 31/12/2027")
        page.wait_for_selector(".garanties-fiche .garanties-bandeau")
        self.assertEqual(self.texte(".garanties-bandeau p"),
                         "Pour ne pas être reconduit le 31/12/2027, ce contrat doit être résilié au plus tard le "
                         "30/09/2027 (dans 30 jours). Prévo n'envoie rien : écrivez au prestataire.")
        self.verifier_principe("fiche du contrat reconduit", ".garanties-fiche")

        # « Noter la résiliation » : lettre du jour ; la reconduction tacite passe à non ; plus de bouton.
        page.click("#contrat-resiliation")
        page.wait_for_selector(FENETRE + "[name=commentaire]")
        self.assertEqual(page.input_value(FENETRE + "[name=date]"), J4)
        page.fill(FENETRE + "[name=commentaire]", LETTRE)
        page.click(FENETRE + ".fenetre-actions .btn-primaire")
        self.attendre_toast("Résiliation notée : le contrat se termine le 31/12/2027.")
        self.attendre(lambda: self.ligne("contrats_prestataires", ctp)["reconduction_tacite"] == "0", "résiliation non écrite")
        self.assertEqual(self.journal_de("contrats_prestataires", ctp)[-1],
                         "modification : reconduction_tacite — résiliation notée : lettre du 31/08/2027 ; " + LETTRE)
        page.wait_for_function("!document.querySelector('#contrat-resiliation')")
        self.assertEqual(page.locator("#contrat-reconduire").count(), 0)
        self.assertEqual(self.js(VALEUR_FICHE_JS, "Reconduction tacite"), "Non")
        self.verifier_principe("fiche du contrat résilié", ".garanties-fiche")

    # -- 31/08/2027 : retraits (actif à 0, rien d'effacé) --------------------------------------------

    def retraits(self):
        page, e = self.page, self.e["id"]
        ancienne = self.js(GARANTIE_AVEC_DOCUMENT_JS, [dict(ANCIENNE, equipement_id=e, fournisseur_id=self.f1["id"]),
                                                         list(PDF_ANCIENNE), "ancienne-garantie.pdf"])
        retire = self.accepte("Garanties.creerContrat", dict(CONTRAT_RETIRE, fournisseur_id=self.f1["id"], equipement_ids=e))
        self.fiche_equipement(e)
        self.assertEqual(page.locator(CARTE + " li[data-garantie='%s']" % ancienne).count(), 1)
        self.assertEqual(page.locator(CARTE + " li[data-contrat='%s']" % retire).count(), 1)

        document = self.retirer_depuis_la_fiche(ancienne, "Garantie retirée.", "garanties")["document"]
        self.assertTrue(document)
        self.assertEqual(self.document(document), PDF_ANCIENNE)               # le document est gardé
        self.retirer_depuis_la_fiche(retire, "Contrat retiré.", "contrats")
        self.ouvrir_fiche(retire)
        self.assertIn("Contrat retiré : il n'est plus affiché ni rappelé ; il reste au journal.",
                      page.inner_text(".garanties-fiche .alerte"))
        self.assertEqual(page.locator("#contrat-modifier, #contrat-retirer, #contrat-reconduire").count(), 0)
        self.fiche_equipement(e)
        self.assertEqual(page.locator(CARTE + " [data-garantie='%s'], %s [data-contrat='%s']" % (ancienne, CARTE, retire)).count(), 0)
        return [ancienne, retire]

    # -- 31/08/2027 : la fiche de E pour le responsable ----------------------------------------------

    def fiche_equipement_du_responsable(self, g1, ctp, retires):
        page = self.page
        self.fiche_equipement(self.e["id"])
        self.assertEqual(self.texte(BADGE), "Sous garantie jusqu'au 31/05/2028")
        en_cours = CARTE + " li.garanties-encart-en-cours[data-garantie='%s']" % g1
        self.assertEqual(page.get_attribute(en_cours + " .garanties-encart-tete a", "href"), fiche(g1))
        self.assertEqual(page.get_attribute(CARTE + " li[data-contrat='%s'] a" % ctp, "href"), fiche(ctp))
        self.assertEqual(page.locator(CARTE + " li[data-contrat='%s'] [data-statut]" % ctp).count(), 1)
        self.assertEqual(page.locator(CARTE + " #garanties-ajouter-garantie").count(), 1)
        self.verifier_lien(en_cours + " a.garanties-document", PDF_GARANTIE)
        carte = self.texte(CARTE)
        self.assertIn(GARANTIE["conditions"], carte)
        self.assertNotIn("€", carte)                                           # jamais de montant sur cette carte
        for montant in MONTANTS:
            self.assertNotIn(montant, carte)

    # -- 31/08/2027 : rappel à la création d'un OT correctif (Q7 : un rappel, jamais un blocage) ------

    def rappel_a_l_ot_correctif(self, g1):
        page, e = self.page, self.e["id"]
        page.click(".parc-actions a[href='#/ot/nouveau?equipement=%s']" % e)
        page.wait_for_selector(ZONE_RAPPEL + " .garanties-rappel")
        self.assertEqual(page.input_value("#form-nouvel-ot [name=type]"), "correctif différé")
        rappel = self.texte(ZONE_RAPPEL)
        self.assertIn("Équipement sous garantie jusqu'au 31/05/2028 (%s, tél. " % self.f1["nom"], rappel)
        self.assertIn("Appeler le fournisseur avant d'intervenir ?", rappel)
        self.assertIn("Conditions : " + GARANTIE["conditions"], rappel)
        self.assertEqual(page.get_attribute(ZONE_RAPPEL + " a[href^='tel:']", "href"), "tel:" + self.f1["telephone"])
        self.assertEqual(page.get_attribute(ZONE_RAPPEL + " .garanties-rappel", "data-garantie"), g1)
        page.select_option("#form-nouvel-ot [name=type]", "préventif systématique")
        self.assertEqual(page.locator(ZONE_RAPPEL + " .garanties-rappel").count(), 0)
        page.select_option("#form-nouvel-ot [name=type]", "correctif immédiat")
        self.assertEqual(page.locator(ZONE_RAPPEL + " .garanties-rappel").count(), 1)
        self.sans_conforme("nouvel OT")
        page.fill("#form-nouvel-ot [name=titre]", "Fuite sur le vérin (recette L4)")
        page.click("#form-nouvel-ot button[type=submit]")
        page.wait_for_function("() => /^#\\/ot\\/OT-/.test(location.hash) && document.querySelector('.ot-fiche .ot-numero')")
        ot = page.inner_text(".ot-fiche .ot-numero")
        self.attendre(lambda: len(self.journal_de("ordres_travail", ot)) >= 1, "OT non écrit")
        self.assertEqual((self.ligne("ordres_travail", ot)["equipement_id"], self.ligne("ordres_travail", ot)["type"]),
                         (e, "correctif immédiat"))
        self.assertFalse(any("garantie" in action for action in self.journal_de("ordres_travail", ot)))
        return ot

    # -- échéance de la garantie (D187 : même délai réglé, 30 jours ici), puis retour au 31/08/2027 -------

    def echeance_de_la_garantie(self, g1):
        page = self.page
        for jour, statut in ((J4, "en_cours"), ("2028-04-30", "en_cours"), ("2028-05-01", "bientot")):
            with self.subTest(jour=jour):
                self.jour(jour, *self.liste("garanties"))
                self.assertEqual(self.statuts("garanties")[g1], statut)
        self.assertIn("se termine dans 30 jours, le 31/05/2028", self.ligne_liste("garanties", g1))
        self.sans_conforme("liste des garanties")
        self.fiche_equipement(self.e["id"])
        self.assertEqual(self.texte(BADGE), "Sous garantie jusqu'au 31/05/2028")
        self.assertIn("attention", page.get_attribute(BADGE + " .badge", "class"))      # ambre sous le délai
        self.page.clock.set_fixed_time(heure(J4))
        self.fiche_equipement(self.e["id"])
        self.assertNotIn("attention", page.get_attribute(BADGE + " .badge", "class"))

    # -- profil Technicien ----------------------------------------------------------------------------

    def vue_du_technicien(self, page, cree, technicien):
        """La page est ouverte sous le profil Technicien (technicien : son identifiant), horloge au 31/08/2027."""
        self.assertEqual((page.evaluate("App.profil.type"), page.evaluate("App.profil.technicienId"),
                          page.evaluate("App.estResponsable()"), page.evaluate("Donnees.aujourdhui()")),
                         ("technicien", technicien, False, J4))
        g1, ctp = cree["g1"], cree["ctp"]

        # Ni menu ni adresse Garanties (écrans du responsable seul).
        self.assertEqual(page.locator("#menu a[data-ecran='garanties']").count(), 0)
        for route in ("#/garanties", "#/garanties?onglet=contrats", fiche(ctp), fiche(g1), "#/garanties/contrat/nouveau"):
            with self.subTest(route=route):
                page.evaluate("(r) => { location.hash = '#/parc'; }", route)
                page.wait_for_function("location.hash === '#/parc'")
                page.evaluate("(r) => { location.hash = r; }", route)
                page.wait_for_function("location.hash === '#/accueil'")
                self.assertEqual(page.locator(".garanties-ecran, .garanties-fiche, #form-contrat").count(), 0)

        # Fiche de E : badge, carte sans lien vers les écrans du responsable, sans montant, sans les lignes retirées.
        self.fiche_equipement(self.e["id"], page)
        self.assertEqual(self.texte(BADGE, page), "Sous garantie jusqu'au 31/05/2028")
        en_cours = CARTE + " li.garanties-encart-en-cours[data-garantie='%s']" % g1
        self.assertEqual(page.inner_text(en_cours + " .garanties-encart-tete b"), "Sous garantie jusqu'au 31/05/2028")
        self.assertIn(GARANTIE["conditions"], page.inner_text(en_cours))
        self.assertEqual(page.inner_text(CARTE + " li[data-contrat='%s'] b" % ctp), CONTRAT["objet"])
        self.assertIn("jusqu'au 31/12/2027", self.texte(CARTE + " li[data-contrat='%s']" % ctp, page))
        self.assertEqual(page.locator(CARTE + " a[href^='#/garanties'], %s #garanties-ajouter-garantie" % CARTE).count(), 0)
        for retire in cree["retires"]:
            self.assertEqual(page.locator(CARTE + " [data-garantie='%s'], %s [data-contrat='%s']" % (retire, CARTE, retire)).count(), 0)
        self.assertNotIn("€", self.texte(CARTE, page))
        tout = page.evaluate("() => document.body.innerText + ' ' + document.body.innerHTML").translate(ESPACES)
        for montant in MONTANTS:
            self.assertNotIn(montant, tout)
        # Il ouvre le certificat de la garantie depuis la fiche de E.
        self.verifier_lien(en_cours + " a.garanties-document", PDF_GARANTIE, page)

        # Par l'application elle-même : écritures refusées, rien d'écrit.
        tables = ("garanties", "contrats_prestataires", "journal")
        avant = [self.lignes(table) for table in tables]
        e = self.e["id"]
        for chemin, arguments in (
                ("Garanties.creerGarantie", [dict(GARANTIE, equipement_id=e)]),
                ("Garanties.creerContrat", [dict(CONTRAT, fournisseur_id=self.f2["id"], equipement_ids=e)]),
                ("Garanties.retirerGarantie", [g1]),
                ("Garanties.retirerContrat", [ctp]),
                ("Garanties.reconduireContrat", [ctp, {}]),
                ("Garanties.noterResiliation", [ctp, {"date": J4, "commentaire": "par le technicien"}])):
            with self.subTest(appel=chemin):
                refus = self.appeler(chemin, *arguments, page=page)
                self.assertEqual((refus.get("refus"), refus.get("validation")), (REFUS_APPLICATION, True), refus)
        self.assertEqual([self.lignes(table) for table in tables], avant)


# ---------------------------------------------------------------------------
# Les modes
# ---------------------------------------------------------------------------

class CasParcoursServeur(CasRecette):
    """serveur.py sur une copie du jeu de démo ; données et documents relus sur le disque."""

    COMPTES = False

    def lignes(self, table):
        if not (self.dossier / (table + ".csv")).exists():
            return []
        return [propre(ligne) for ligne in lire_csv(self.dossier, table + ".csv")]

    def document(self, nom):
        return (self.dossier / "documents" / nom).read_bytes()

    def lancer(self):
        self.requetes = []
        with ServeurPrevo(comptes=self.COMPTES) as serveur:
            self.serveur, self.dossier = serveur, Path(serveur.dossier)
            if self.COMPTES:
                serveur.poser_session(self.contexte, "responsable")
            else:
                preregler_profil(self.contexte, "responsable", "Nicolas Briand")
            self.contexte.clock.set_fixed_time(heure(J0))
            self.noter_requetes(self.page)
            self.page.set_viewport_size({"width": 1440, "height": 1200})
            self.page.goto(serveur.url + "/#/accueil")
            attendre_pret(self.page)
            self.page.wait_for_load_state("networkidle")       # écritures du démarrage (OT préventifs échus) finies
            self.assertEqual(self.js("App.profil.type"), "responsable")
            cree = self.parcours()
            self.page.close()
            self.technicien(serveur, cree)
            self.verifier_reseau(serveur.url + "/")

    def page_technicien(self, serveur, technicien):
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1440, "height": 1200})
        self.addCleanup(contexte.close)
        contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        contexte.clock.set_fixed_time(heure(J4))
        if self.COMPTES:
            serveur.poser_session(contexte, "technicien")
        else:
            preregler_profil(contexte, "technicien", technicien_id=technicien)
        page = contexte.new_page()
        self.surveiller(page)
        self.noter_requetes(page)
        page.goto(serveur.url + "/#/accueil")
        attendre_pret(page)
        page.wait_for_load_state("networkidle")
        self.page = page                                        # attendre() et les aides lisent self.page
        return page

    def technicien(self, serveur, cree):
        """Sans comptes : un technicien de la démo (son profil sur ce poste)."""
        technicien = next(t["id"] for t in self.lignes("techniciens") if t.get("actif") != "0")
        page = self.page_technicien(serveur, technicien)
        self.vue_du_technicien(page, cree, technicien)


class TestParcoursServeur(CasParcoursServeur):

    def test_garanties_et_contrats_serveur_sans_comptes(self):
        self.lancer()


class TestParcoursServeurComptes(CasParcoursServeur):

    COMPTES = True

    def test_garanties_et_contrats_avec_comptes_puis_refus_du_serveur_au_technicien(self):
        self.lancer()

    def technicien(self, serveur, cree):
        """Le compte technicien : la vue, les contrats reçus sans montant, puis les refus 403 du serveur."""
        technicien = COMPTES_DE_TEST["technicien"][4]
        page = self.page_technicien(serveur, technicien)
        self.vue_du_technicien(page, cree, technicien)

        # Contrats reçus sans montant_annuel (Q6) : ni la colonne ni la valeur dans les données de la page.
        recus = page.evaluate(LIGNES_JS, "contrats_prestataires")
        self.assertTrue(any(c["id"] == cree["ctp"] for c in recus))
        self.assertEqual([c["id"] for c in recus if brut(c.get("montant_annuel"))], [])
        self.assertNotIn("4800", page.evaluate("JSON.stringify(Donnees.lignes('contrats_prestataires'))"))

        # Le serveur : écriture des deux tables refusée au technicien (PUT, ajout), fichiers inchangés.
        cookie, responsable = serveur.session("technicien"), serveur.session("responsable")
        nouvelles = {"garanties": "GAR-0990;%s;;2026-11-01;2028-10-31;;;1" % self.e["id"],
                     "contrats_prestataires": "CTP-0990;%s;Essai du technicien;;;2026-11-01;2027-10-31;2;0;;;;1"
                                              % self.f1["id"]}
        for table, nouvelle in nouvelles.items():
            with self.subTest(table=table):
                chemin = self.dossier / (table + ".csv")
                avant = chemin.read_bytes()
                entete = premiere_ligne(avant)
                envoi = requete(serveur, "PUT", "/api/csv/" + table, BOM + entete + b"\r\n", cookie,
                                {"X-Version-Attendue": "0" * 16})
                ajout = requete(serveur, "POST", "/api/csv/%s/ajout" % table,
                                entete + ("\r\n" + nouvelle + "\r\n").encode("utf-8"), cookie)
                for reponse in (envoi, ajout):
                    self.assertEqual(reponse.statut, 403, reponse.octets[:300])
                    self.assertEqual(reponse.json()["erreur"], REFUS_TABLE.format(table=table))
                self.assertEqual(chemin.read_bytes(), avant)

        # Documents : contrat signé refusé au technicien, servi au responsable ; certificat de la garantie servi.
        contrat = self.ligne("contrats_prestataires", cree["ctp"])["document"]
        refus = requete(serveur, "GET", "/api/documents/" + contrat, cookie=cookie)
        self.assertEqual(refus.statut, 403, refus.octets[:300])
        self.assertEqual(refus.json()["erreur"], REFUS_DOCUMENT.format(role="technicien"))
        servi = requete(serveur, "GET", "/api/documents/" + contrat, cookie=responsable)
        self.assertEqual((servi.statut, servi.octets), (200, PDF_CONTRAT))
        certificat = self.ligne("garanties", cree["g1"])["document"]
        servi = requete(serveur, "GET", "/api/documents/" + certificat, cookie=cookie)
        self.assertEqual((servi.statut, servi.octets), (200, PDF_GARANTIE))


class TestParcoursDemo(CasRecette):
    """index.html en file:// (démo, données en mémoire) ; le technicien : changement de profil dans la même page."""

    def lignes(self, table):
        return [propre(ligne) for ligne in self.js(LIGNES_JS, table)]

    def document(self, nom):
        octets = self.js(LIRE_DOCUMENT_JS, nom)
        return None if octets is None else bytes(octets)

    def test_garanties_et_contrats_en_demo(self):
        self.requetes = []
        preregler_profil(self.contexte, "responsable", "Nicolas Briand")
        self.contexte.clock.set_fixed_time(heure(J0))
        self.noter_requetes(self.page)
        self.page.set_viewport_size({"width": 1440, "height": 1200})
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        self.assertEqual((self.js("App.mode"), self.js("App.profil.type")), ("demo", "responsable"))
        cree = self.parcours()

        # Profil Technicien, sans recharger : la démo serait perdue.
        page = self.page
        technicien = next(t["id"] for t in self.lignes("techniciens") if t.get("actif") != "0")
        page.evaluate("window.__memePage = true")
        page.click("#etat-poste")
        page.wait_for_function("document.documentElement.dataset.etat === 'profil'")
        page.click("#profil-technicien")
        page.click("#profil-techniciens [data-technicien='%s']" % technicien)
        attendre_pret(page)
        self.assertTrue(page.evaluate("window.__memePage === true"), "la page a été rechargée")
        self.vue_du_technicien(page, cree, technicien)
        self.verifier_reseau(url_fichier("index.html"))


if __name__ == "__main__":
    unittest.main()
