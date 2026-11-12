"""Documents réservés au responsable par leur NOM, en plus de la citation (T501 ; D196 ; relecture du 12/11 : R2, R3, R4).

Défaut fermé : un justificatif d'habilitation ou un document de contrat n'était réservé que tant qu'une ligne le
citait (documents_reserves de serveur.py). Remplacé, ligne supprimée, réécrit sous un nom neuf par un import ZIP, ou
envoyé mais pas encore cité, il était servi au technicien (GET /api/documents/<nom> : 200), qui lit son nom au journal.

Ce qui est vérifié, en mode serveur avec comptes (vraies sessions sur la copie du jeu f4-v2.2.0 préparée par
tests/test_droits_format4.py, dont ce fichier reprend les outils) :
    nommage          les noms que le navigateur donne à ces documents (lus dans js/modules/garanties-ecritures.js et
                     js/modules/equipe-ecritures.js) sont reconnus par MOTIF_DOCUMENT_RESERVE de serveur.py, avec le
                     préfixe d'horodatage du serveur ; les autres documents (garanties, rapports de contrôle, photos
                     de demandes, documents d'équipements, rapports mensuels) ne le sont pas ;
    contrat          scénario de R2 : 403 au technicien avant ; document remplacé ; 403 sur l'ancien ET le nouveau,
                     et sur le nouveau dès son envoi (avant d'être cité) ;
    justificatif     ligne d'habilitation supprimée : toujours 403 au technicien ;
    import ZIP       le document réécrit sous un nom neuf (R3) : ancien et nouveau noms réservés ;
    inchangé         documents de garantie, d'équipement, rapports de contrôle, photos de demandes, document au nom
                     libre cité nulle part : servis comme avant ; un document au nom libre CITÉ reste réservé ;
    envoi            le demandeur n'envoie pas un document au nom réservé (403) ; le technicien n'écrase jamais un
                     document réservé (le serveur impose un nom neuf).

Limite écrite (pas de décision) : un document réservé au nom libre (hors motif, ex. « …-titre-habilitation-BR.pdf »
des données d'avant) qui n'est plus cité redevient lisible du technicien (test_limite_nom_libre_plus_cite).

Aucune donnée réelle : copie temporaire du jeu f4-v2.2.0. Sans navigateur.
Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_documents_reserves_nom.py" -v
"""
import re

import test_droits_format4 as droits
from commun import RACINE

PDF = droits.PDF
REFUS = droits.REFUS_DOCUMENT
JS_GARANTIES = RACINE / "js" / "modules" / "garanties-ecritures.js"
JS_EQUIPE = RACINE / "js" / "modules" / "equipe-ecritures.js"
HORODATAGE = "20261112-103643-"


def noms_du_navigateur():
    """Noms demandés par le navigateur, reconstruits d'après le code JS : {"contrat", "habilitation", "garantie"}.
    Échoue si le nommage a changé (le motif du serveur est alors à revoir)."""
    garanties = JS_GARANTIES.read_text(encoding="utf-8")
    equipe = JS_EQUIPE.read_text(encoding="utf-8")
    debuts = {}
    for sorte, table in (("contrat", "contrats_prestataires"), ("garantie", "garanties")):
        trouve = re.search(r"table: '%s',[^\n]*prefixeId: '([^']+)', debutDocument: '([^']+)'" % table, garanties)
        if not trouve:
            raise AssertionError("garanties-ecritures.js : début du nom des documents de %s introuvable" % table)
        debuts[sorte] = trouve.group(2) + trouve.group(1)
    if "const base = (sorte.debutDocument + texte(id) + '-' + (dateIso(date) || Donnees.aujourdhui()))" not in garanties:
        raise AssertionError("garanties-ecritures.js : le nom d'un document n'est plus « <début><id>-<date> »")
    trouve = re.search(r"const base = \['([^']+)', technicien, morceau, jour\]\.filter\(Boolean\)\.join\('-'\);", equipe)
    if not trouve:
        raise AssertionError("equipe-ecritures.js : le nom d'un justificatif n'est plus « habilitation-<technicien>-… »")
    return {
        "contrat": debuts["contrat"] + "0001-2026-11-12.pdf",
        "garantie": debuts["garantie"] + "0001-2026-11-12.pdf",
        "habilitation": trouve.group(1) + "-TEC-0001-BR-2024-01-15.pdf",
    }


class TestMotif(droits.unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.module = droits.charger_module("serveur_t501")
        cls.noms = noms_du_navigateur()

    def reserve(self, nom):
        return bool(self.module.MOTIF_DOCUMENT_RESERVE.fullmatch(nom))

    def test_noms_du_navigateur_reserves(self):
        self.assertEqual(self.noms["contrat"], "contrat-CTP-0001-2026-11-12.pdf")
        self.assertEqual(self.noms["habilitation"], "habilitation-TEC-0001-BR-2024-01-15.pdf")
        for demande in (self.noms["contrat"], self.noms["habilitation"]):
            base, extension = demande.rsplit(".", 1)
            for nom in (demande, HORODATAGE + demande, HORODATAGE + base + "-2." + extension,
                        HORODATAGE + base + "_20261112-103643_k3f9." + extension,     # UI.nomFichierUnique
                        HORODATAGE + "20250310-090000-" + demande,                    # deux horodatages (import ZIP)
                        (HORODATAGE + demande).upper(), HORODATAGE + base + ".jpg"):
                with self.subTest(nom=nom):
                    self.assertTrue(self.reserve(nom))

    def test_nom_impose_par_le_serveur(self):
        """Le nom enregistré (nom_de_document_impose) d'un nom du navigateur est reconnu."""
        config = self.module.Configuration(droits.tempfile.gettempdir(), [])
        for sorte in ("contrat", "habilitation"):
            impose = self.module.nom_de_document_impose(config, self.noms[sorte])
            self.assertTrue(impose.endswith("-" + self.noms[sorte]), impose)
            self.assertTrue(self.reserve(impose), impose)

    def test_autres_documents_pas_reserves(self):
        for nom in (self.noms["garantie"], HORODATAGE + self.noms["garantie"],
                    HORODATAGE + "controle-CTR-0002-2026-10-20.pdf",
                    HORODATAGE + "photo-20261112-103640-AB12.jpg", "photo-20261112-103640-AB12.jpg",
                    HORODATAGE + "CP-01_20261019-153012_k3f9.pdf", HORODATAGE + "rapport-2026-10.html",
                    HORODATAGE + "notice-contrat-CTP-0001.pdf", HORODATAGE + "titre-habilitation-BR.pdf",
                    HORODATAGE + "contrat-entretien.pdf", HORODATAGE + "habilitations.pdf",
                    droits.GARANTIE, droits.DOCUMENT_EQUIPEMENT, droits.AUTRE, droits.NOUVEAU):
            with self.subTest(nom=nom):
                self.assertFalse(self.reserve(nom))
        self.assertTrue(self.module.MOTIF_PHOTO_DE_DEMANDE.fullmatch(HORODATAGE + "photo-20261112-103640-AB12.jpg"))


class TestReserveParLeNom(droits.CasServeur):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.noms = noms_du_navigateur()

    def lire(self, role, nom):
        return self.requete(role, "GET", "/api/documents/" + nom)

    def envoyer(self, role, nom, contenu):
        return self.requete(role, "PUT", "/api/documents/" + nom, contenu)

    def assertReserve(self, nom, contenu=None):
        """403 au technicien et au demandeur, 200 au responsable (avec ce contenu s'il est donné)."""
        for role in ("technicien", "demandeur"):
            self.assertRefus(self.lire(role, nom), REFUS.format(role=role))
        reponse = self.lire("responsable", nom)
        self.assertEqual(reponse.statut, 200, reponse.octets[:300])
        if contenu is not None:
            self.assertEqual(reponse.octets, contenu)

    def deposer(self, nom, contenu):
        """Document posé dans le dossier des documents (comme une copie du dossier ou des données d'avant)."""
        (self.serveur.dossier / "documents" / nom).write_bytes(contenu)

    def test_contrat_remplace_reste_reserve(self):
        """Scénario de R2 : 403 avant ; document remplacé ; 403 sur l'ancien ET le nouveau."""
        ancien = droits.CONTRAT                                   # cité par CTP-0001
        self.assertReserve(ancien, PDF + ancien.encode("ascii"))
        self.assertEqual(self.requete("technicien", "GET", "/api/csv/journal").statut, 200)
        envoi = self.envoyer("responsable", self.noms["contrat"], PDF + b"avenant")
        self.assertEqual(envoi.statut, 201, envoi.octets[:300])
        nouveau = envoi.json()["nom"]
        self.assertRegex(nouveau, r"^\d{8}-\d{6}-" + re.escape(self.noms["contrat"]) + "$")
        self.assertReserve(nouveau, PDF + b"avenant")             # avant d'être cité (fenêtre de R3 et R4)
        modifie = droits.avec_cellule(self.fichier("contrats_prestataires"), "CTP-0001", "document", nouveau)
        self.assertEqual(self.ecrire("responsable", "contrats_prestataires", modifie).statut, 200)
        self.assertNotIn(ancien.encode("ascii"), self.fichier("contrats_prestataires"))
        self.assertReserve(ancien, PDF + ancien.encode("ascii"))  # plus cité : toujours réservé
        self.assertReserve(nouveau, PDF + b"avenant")

    def test_justificatif_de_ligne_supprimee_reste_reserve(self):
        envoi = self.envoyer("responsable", self.noms["habilitation"], PDF + b"attestation")
        self.assertEqual(envoi.statut, 201, envoi.octets[:300])
        nom = envoi.json()["nom"]
        self.assertReserve(nom, PDF + b"attestation")             # envoyé, pas encore cité
        cite = droits.avec_cellule(self.fichier("habilitations"), "HAB-0003", "justificatif", nom)
        self.assertEqual(self.ecrire("responsable", "habilitations", cite).statut, 200)
        self.assertReserve(nom)
        entete, lignes = droits.lire_tableau(self.fichier("habilitations"))
        sans = droits.ecrire_tableau(entete, [ligne for ligne in lignes if ligne[0] != "HAB-0003"])
        self.assertEqual(self.ecrire("responsable", "habilitations", sans).statut, 200)
        self.assertNotIn(nom.encode("ascii"), self.fichier("habilitations"))
        self.assertReserve(nom, PDF + b"attestation")             # ligne supprimée : toujours réservé

    def test_apres_un_import_zip_ancien_et_nouveau_noms_reserves(self):
        """R3 : l'import ZIP réécrit chaque document sous un nom neuf, l'ancien reste dans le dossier, plus cité."""
        ancien = "20250310-090000-" + self.noms["habilitation"].replace("-BR-", "-B2V-")
        self.deposer(ancien, PDF + b"avant import")
        self.assertReserve(ancien)
        # parametres-zip.js (nomDemande) : nom du ZIP sans l'horodatage du serveur, qui en remet un.
        envoi = self.envoyer("responsable", ancien[len("20250310-090000-"):], PDF + b"avant import")
        self.assertEqual(envoi.statut, 201, envoi.octets[:300])
        self.assertNotEqual(envoi.json()["nom"], ancien)
        self.assertReserve(envoi.json()["nom"])
        self.assertReserve(ancien, PDF + b"avant import")
        double = "20261112-103643-20250310-090000-" + self.noms["contrat"]      # horodatage gardé puis remis
        self.deposer(double, PDF)
        self.assertReserve(double)

    def test_casse_du_nom_ignoree(self):
        nom = "20250310-090000-" + self.noms["contrat"].replace("0001", "0002")
        self.deposer(nom, PDF)
        for variante in (nom.upper(), nom.replace("contrat", "Contrat"), nom.replace("CTP", "ctp")):
            with self.subTest(nom=variante):
                self.assertRefus(self.lire("technicien", variante), REFUS.format(role="technicien"))

    def test_autres_documents_servis_comme_avant(self):
        photo = "20261112-103643-photo-20261112-103640-AB12.jpg"
        rapport = "20261020-101500-controle-CTR-0002-2026-10-20.pdf"
        garantie = "20261112-103643-" + self.noms["garantie"]
        for nom in (photo, rapport, garantie):
            self.deposer(nom, PDF + nom.encode("ascii"))
        for nom in (droits.GARANTIE, droits.DOCUMENT_EQUIPEMENT, droits.AUTRE, photo, rapport, garantie):
            with self.subTest(nom=nom):
                self.assertDocument(self.lire("technicien", nom), nom)
                self.assertDocument(self.lire("responsable", nom), nom)
        for nom in (droits.DOCUMENT_EQUIPEMENT, photo):
            with self.subTest(nom=nom, role="demandeur"):
                self.assertDocument(self.lire("demandeur", nom), nom)
        for nom in (droits.GARANTIE, droits.AUTRE, rapport, garantie):
            with self.subTest(nom=nom, role="demandeur"):
                self.assertEqual(self.lire("demandeur", nom).statut, 403)

    def test_nom_libre_cite_reste_reserve(self):
        """La règle « cité par » est gardée : PARTAGE (« …-schema-armoire.pdf ») est le justificatif de HAB-0002."""
        self.assertFalse(re.search("habilitation|contrat", droits.PARTAGE))
        self.assertReserve(droits.PARTAGE, PDF + droits.PARTAGE.encode("ascii"))

    def test_limite_nom_libre_plus_cite(self):
        """Limite écrite : un nom libre (hors motif) n'est réservé que tant qu'il est cité."""
        nom = "20211202-090000-caces-r489.pdf"                    # justificatif de HAB-0004 dans le jeu
        self.deposer(nom, PDF + nom.encode("ascii"))
        self.assertReserve(nom)
        vide = droits.avec_cellule(self.fichier("habilitations"), "HAB-0004", "justificatif", "")
        self.assertEqual(self.ecrire("responsable", "habilitations", vide).statut, 200)
        self.assertDocument(self.lire("technicien", nom), nom)

    def test_envoi_sous_un_nom_reserve(self):
        """Le demandeur n'envoie que des photos ; le technicien n'écrase jamais un document (nom neuf imposé)."""
        self.assertEqual(self.envoyer("demandeur", self.noms["contrat"], PDF).statut, 403)
        self.assertEqual(self.envoyer("demandeur", self.noms["habilitation"], PDF).statut, 403)
        demande = self.noms["contrat"].replace("0001", "0002").replace("2026-11-12", "2026-11-13")
        premier = self.envoyer("responsable", demande, PDF + b"du responsable")
        self.assertEqual(premier.statut, 201, premier.octets[:300])
        second = self.envoyer("technicien", demande, PDF + b"du technicien")
        self.assertIn(second.statut, (201, 409), second.octets[:300])       # 409 : même seconde, rien d'écrit
        if second.statut == 201:
            self.assertNotEqual(second.json()["nom"], premier.json()["nom"])
            self.assertRefus(self.lire("technicien", second.json()["nom"]), REFUS.format(role="technicien"))
        self.assertReserve(premier.json()["nom"], PDF + b"du responsable")


if __name__ == "__main__":
    droits.unittest.main()
