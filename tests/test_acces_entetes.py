"""Lot 7 — en-têtes de sécurité de l'application (audit F1 ; ARCHITECTURE.md §22.13 ; CS125 ; tâche T163).

Ce qui est vérifié :
    application  index.html, GUIDE.html, css/ et js/ portent Content-Security-Policy (script-src 'self', aucune
                 origine extérieure sauf https://prevo.pro pour la mise à jour signalée), X-Frame-Options: DENY,
                 Referrer-Policy: no-referrer, Permissions-Policy (caméra et micro sur la page seulement) ;
    documents    un document déposé garde « Content-Security-Policy: sandbox » et ne reçoit pas ces en-têtes ;
    en ligne     index.html ne contient plus aucun script en ligne (préchargement de la police dans js/prechargement.js) ;
    HSTS         jamais pour une adresse IP ; seulement en https et pour un nom déclaré (--hote) ;
    écrans       en mode serveur, les écrans principaux s'affichent sans aucune violation de la politique (événement
                 securitypolicyviolation et console).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_acces_entetes.py" -v
"""
import http.client
import re
import shutil
import ssl
import tempfile
import unittest
from pathlib import Path

from commun import RACINE, CasNavigateur, ServeurPrevo, preregler_profil
from test_https import fabriquer_certificat

ECRANS = ["#/accueil", "#/di", "#/ot", "#/parc", "#/equipement/EQ-0001", "#/preventif", "#/magasin", "#/planning",
          "#/controles", "#/equipe", "#/indicateurs", "#/parametres", "#/import", "#/poste", "#/wiki",
          "#/wiki/machines", "#/wiki-journal", "#/apropos"]

NOTER_VIOLATIONS = """
window.__violations = [];
document.addEventListener('securitypolicyviolation', (e) => {
  window.__violations.push(e.violatedDirective + ' ' + (e.blockedURI || '') + ' ' + (e.sourceFile || '') + ':' + e.lineNumber);
});
"""


def entetes(serveur, chemin, hote=None, contexte=None):
    morceaux = serveur.url.split("://")[1].split(":")
    if contexte is not None:
        connexion = http.client.HTTPSConnection(morceaux[0], int(morceaux[1]), context=contexte, timeout=10)
    else:
        connexion = http.client.HTTPConnection(morceaux[0], int(morceaux[1]), timeout=10)
    try:
        connexion.request("GET", chemin, headers={"Host": hote or "%s:%s" % tuple(morceaux)})
        reponse = connexion.getresponse()
        reponse.read()
        return reponse.status, {nom.lower(): valeur for nom, valeur in reponse.getheaders()}
    finally:
        connexion.close()


class TestEntetes(unittest.TestCase):

    def test_application_porte_les_entetes(self):
        with ServeurPrevo() as serveur:
            for chemin in ("/", "/index.html", "/GUIDE.html", "/css/style.css", "/js/app.js", "/js/prechargement.js"):
                with self.subTest(chemin=chemin):
                    statut, recus = entetes(serveur, chemin)
                    self.assertEqual(statut, 200)
                    politique = recus["content-security-policy"]
                    self.assertIn("script-src 'self';", politique)
                    self.assertIn("frame-ancestors 'none'", politique)
                    self.assertIn("object-src 'none'", politique)
                    self.assertIn("connect-src 'self' https://prevo.pro", politique)
                    self.assertEqual(recus["x-frame-options"], "DENY")
                    self.assertEqual(recus["referrer-policy"], "no-referrer")
                    self.assertEqual(recus["permissions-policy"], "camera=(self), microphone=(self), geolocation=()")
                    self.assertEqual(recus["x-content-type-options"], "nosniff")
                    self.assertNotIn("strict-transport-security", recus)

    def test_documents_gardent_sandbox_sans_entetes_application(self):
        with ServeurPrevo() as serveur:
            reponse = serveur.requete("PUT", "/api/documents/essai-entetes.pdf", corps=b"%PDF-1.4\n%essai\n",
                                      entetes={"X-Prevo": "1"}) if hasattr(serveur, "requete") else None
            if reponse is None:
                morceaux = serveur.url.split("://")[1].split(":")
                connexion = http.client.HTTPConnection(morceaux[0], int(morceaux[1]), timeout=10)
                connexion.request("PUT", "/api/documents/essai-entetes.pdf", body=b"%PDF-1.4\n%essai\n",
                                  headers={"X-Prevo": "1", "Content-Type": "application/pdf"})
                self.assertIn(connexion.getresponse().status, (200, 201))
                connexion.close()
            statut, recus = entetes(serveur, "/api/documents/essai-entetes.pdf")
            self.assertEqual(statut, 200)
            self.assertEqual(recus["content-security-policy"], "sandbox")
            self.assertNotIn("x-frame-options", recus)

    def test_aucun_script_en_ligne_dans_index(self):
        texte = (RACINE / "index.html").read_text(encoding="utf-8")
        scripts = re.findall(r"<script\b([^>]*)>(.*?)</script>", texte, flags=re.S)
        self.assertTrue(scripts)
        for attributs, contenu in scripts:
            with self.subTest(script=attributs):
                self.assertIn("src=", attributs)
                self.assertEqual(contenu.strip(), "")
        self.assertIn('<script src="js/prechargement.js"></script>', texte)
        self.assertNotRegex(texte, r"\son[a-z]+\s*=\s*\"")


class TestHsts(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dossier = Path(tempfile.mkdtemp(prefix="prevo-hsts-"))
        cls.addClassCleanup(shutil.rmtree, cls.dossier, True)
        cls.certificat, cls.cle = fabriquer_certificat(cls.dossier)

    def test_hsts_jamais_pour_une_ip_et_pour_un_nom_declare(self):
        contexte = ssl.create_default_context()
        contexte.check_hostname = False
        contexte.verify_mode = ssl.CERT_NONE
        arguments = ["--certificat", str(self.certificat), "--cle", str(self.cle), "--hote", "prevo.essai"]
        with ServeurPrevo(arguments=arguments) as serveur:
            port = serveur.url.rsplit(":", 1)[1]
            _, recus_ip = entetes(serveur, "/", hote="127.0.0.1:" + port, contexte=contexte)
            self.assertNotIn("strict-transport-security", recus_ip)
            _, recus_nom = entetes(serveur, "/", hote="prevo.essai:" + port, contexte=contexte)
            self.assertRegex(recus_nom.get("strict-transport-security", ""), r"^max-age=\d+$")


def attendre(page, expression, argument=None, delai_s=15):
    """Attente sans eval (page.evaluate passe par le protocole du navigateur, hors politique) : wait_for_function
    évalue son prédicat par eval, que script-src 'self' interdit."""
    import time
    limite = time.time() + delai_s
    while time.time() < limite:
        if page.evaluate(expression, argument):
            return
        page.wait_for_timeout(100)
    raise AssertionError("attente dépassée : " + expression)


class TestEcransSousLaPolitique(CasNavigateur):
    CSP_REELLE = True

    def test_ecrans_principaux_sans_violation(self):
        with ServeurPrevo() as serveur:
            preregler_profil(self.contexte, "responsable", "Responsable")
            self.contexte.add_init_script(NOTER_VIOLATIONS)
            page = self.page
            page.goto(serveur.url + "/")
            attendre(page, "() => document.documentElement.dataset.etat === 'pret'")
            for route in ECRANS:
                with self.subTest(route=route):
                    if page.evaluate("location.hash") == route:
                        continue                     # écran déjà affiché (l'accueil au démarrage)
                    # marque posée sur le contenu actuel : l'écran suivant le remplace (certains écrans ajoutent leur
                    # onglet à l'adresse, d'où une attente sur le contenu plutôt que sur l'adresse exacte)
                    page.evaluate("() => { const c = document.querySelector('#contenu'); c.dataset.ancien = '1'; "
                                  "if (c.firstElementChild) c.firstElementChild.dataset.ancien = '1'; }")
                    page.evaluate("(route) => { location.hash = route; }", route)
                    attendre(page, "() => { const p = document.querySelector('#contenu > *'); "
                                   "return p !== null && p.dataset.ancien !== '1'; }")
                    page.wait_for_timeout(200)
            self.assertEqual(page.evaluate("window.__violations"), [], "violations de la politique")
            # le préchargement de la police est bien fait par le fichier
            self.assertEqual(page.evaluate("document.querySelectorAll('link[rel=preload][as=font]').length"), 1)


if __name__ == "__main__":
    unittest.main()
