"""Faux fournisseur d'IA pour les tests (ARCHITECTURE.md §17.10) : jamais un vrai modèle dans la suite.

Imite les deux familles de fournisseurs de Prévo (brief §10) :
    - Ollama            : GET /api/tags, POST /api/chat ;
    - API compatible OpenAI (adresse de base <url>/v1) : GET /v1/models, POST /v1/chat/completions.
Il ouvre CORS à toute origine (une page en file:// envoie l'origine « null »), garde chaque requête
reçue (chemin, en-têtes, corps) pour que les tests vérifient les données envoyées et la clé transmise,
et choisit sa réponse d'après la fonction (premier message système « Fonction : <nom> ») et le modèle :

    faux            réponse correcte (codes pris dans la liste fermée du schéma demandé ; colonnes d'un
                    import : le n-ième titre reçoit le n-ième champ de la liste) ;
    faux-lent       même réponse, après `lenteur_s` secondes (délai dépassé, « Annuler ») ;
    faux-invente    codes : une cause inventée (C42) qui n'existe pas dans la liste ; colonnes d'un import :
                    un champ hors liste, un titre jamais envoyé, un champ donné à deux colonnes ;
    faux-illisible  du texte qui n'est pas du JSON ;
    faux-chiffres   commentaire du rapport qui écrit un nombre en clair (« 92 % ») ;
    faux-schema     API compatible OpenAI : refuse `response_format` json_schema (400), accepte json_object ;
    faux-enorme     réponse de plus de 2 Mo ;
    faux-redirige   répond par une redirection 302 (le relais ne doit pas la suivre) ;
    faux-tronque    réponse coupée : Content-Length annonce plus d'octets que le corps envoyé, puis la
                    connexion est fermée ;
    faux-tronque-morceaux  idem en « Transfer-Encoding: chunked » : le morceau annoncé n'arrive pas en entier ;
    faux-html       réponse piégée : du HTML qui exécuterait du code s'il était inséré tel quel (PIEGE) dans
                    chaque champ texte, codes compris.

    Ingestion du wiki (ingestionWiki, lot 6) : réponse construite à partir du message envoyé par Prévo,
    variantes par modèle (faux-rien, faux-contradiction, faux-recent, faux-invente, faux-retire, faux-consigne,
    faux-sans-ot, faux-cree-mode) : voir tests/faux_wiki.py.


    with FauxFournisseur() as faux:
        faux.url            # 'http://127.0.0.1:54321'  (Ollama) ; faux.url + '/v1' (OpenAI)
        faux.requetes       # [{'methode', 'chemin', 'entetes', 'corps'}]
        faux.cle_attendue   # si renseignée, /v1/… exige « Authorization: Bearer <clé> » (sinon 401)
"""
import http.server
import json
import re
import threading
import time

from faux_wiki import reponse_ingestion

MODELES = ["faux", "faux-lent", "faux-invente", "faux-illisible", "faux-chiffres", "faux-schema",
           "faux-enorme", "faux-redirige", "faux-tronque", "faux-tronque-morceaux", "faux-html",
           "faux-sans-ot", "faux-trop-long", "faux-trop-de-mots", "faux-consigne", "faux-alimentation",
           "faux-rien", "faux-contradiction", "faux-recent", "faux-retire", "faux-cree-mode"]
# Texte piégé : une image dont l'erreur de chargement poserait window.__xss (aucun chiffre : le commentaire
# du rapport le refuserait sinon).
PIEGE = '<img src=x onerror="window.__xss=true">'
MOTIF_FONCTION = re.compile(r"^Fonction\s*:\s*(\w+)")

# Réponses correctes par fonction (les codes sont pris dans le schéma quand il en donne la liste).
REPONSES = {
    "reformulerDI": {"symptome": "Fuite d'huile sous le vérin de la presse", "impact": "dégradé"},
    "compteRendu": {"texte": "Constat : fuite à la garniture mécanique.\nCause : garniture usée.\n"
                             "Action : garniture remplacée, essai sans fuite.\nPièces : 1 kit garniture.\n"
                             "Reste à faire : rien."},
    "checkList": {"operations": [
        {"operation": "Contrôler l'absence de fuite à la garniture", "valeur_attendue": "Aucune goutte"},
        {"operation": "Mesurer les vibrations au palier", "valeur_attendue": "< 4,5 mm/s"},
        {"operation": "Contrôler le serrage de l'accouplement", "valeur_attendue": "Serré"}]},
    "commentaireRapport": {"texte": "La disponibilité du mois s'établit à {disponibilite} ; "
                                    "le coût du mois est de {cout_du_mois}."},
}
CODES_PAR_DEFAUT = {"symptome": "S01", "cause": "C01", "remede": "R01"}


def fonction_demandee(messages):
    for message in messages or []:
        if message.get("role") == "system":
            trouve = MOTIF_FONCTION.match(str(message.get("content", "")).strip())
            if trouve:
                return trouve.group(1)
    return ""


def schema_demande(corps, openai):
    """Schéma JSON demandé : `format` (Ollama) ou `response_format.json_schema.schema` (OpenAI)."""
    if openai:
        format_reponse = corps.get("response_format") or {}
        return (format_reponse.get("json_schema") or {}).get("schema") or {}
    format_ollama = corps.get("format")
    return format_ollama if isinstance(format_ollama, dict) else {}


def codes_du_schema(schema):
    """Premier code de chaque liste fermée (enum) du schéma, sinon S01 / C01 / R01."""
    codes = dict(CODES_PAR_DEFAUT)
    for nom, propriete in (schema.get("properties") or {}).items():
        valeurs = propriete.get("enum") if isinstance(propriete, dict) else None
        if nom in codes and valeurs:
            codes[nom] = valeurs[0]
    return codes


def colonnes_du_schema(schema, invente=False):
    """colonnesImport : le n-ième titre de la liste fermée reçoit le n-ième champ (hors « »). « faux-invente » :
    en plus, un champ hors liste, un titre jamais envoyé et un champ déjà pris pour une autre colonne."""
    proprietes = (((schema.get("properties") or {}).get("colonnes") or {}).get("items") or {}).get("properties") or {}
    entetes = (proprietes.get("entete") or {}).get("enum") or []
    champs = [champ for champ in (proprietes.get("champ") or {}).get("enum") or [] if champ]
    colonnes = [{"entete": entete, "champ": champ} for entete, champ in zip(entetes, champs)]
    if invente and colonnes:
        colonnes = colonnes[:1] + [{"entete": entetes[-1], "champ": "champ_invente"},
                                   {"entete": "Colonne jamais envoyée", "champ": champs[-1]},
                                   {"entete": entetes[-1], "champ": colonnes[0]["champ"]}]
    return {"colonnes": colonnes}


def reponse_piegee(fonction):
    """Réponse de « faux-html » : PIEGE dans chaque champ texte de la fonction."""
    if fonction == "reformulerDI":
        return {"symptome": PIEGE + " fuite", "impact": "dégradé"}
    if fonction == "codes":
        return {"symptome": PIEGE, "cause": "<b>C01</b>", "remede": PIEGE}
    if fonction == "checkList":
        return {"operations": [{"operation": PIEGE + " contrôle", "valeur_attendue": PIEGE}]}
    return {"texte": PIEGE + " texte proposé"}


def message_utilisateur(messages):
    return next((str(m.get("content", "")) for m in messages or [] if m.get("role") == "user"), "")


def contenu_reponse(modele, fonction, schema, messages=None):
    """Texte que le faux modèle « écrit » (le plus souvent du JSON)."""
    if modele == "faux-illisible":
        return "Bien sûr ! Voici ma proposition : la garniture est usée."
    if modele == "faux-html":
        return json.dumps(reponse_piegee(fonction), ensure_ascii=False)
    if modele == "faux-enorme":
        return json.dumps({"texte": "x" * (3 * 1024 * 1024)})
    if fonction == "ingestionWiki":
        return json.dumps(reponse_ingestion(message_utilisateur(messages), modele), ensure_ascii=False)
    if fonction == "colonnesImport":
        return json.dumps(colonnes_du_schema(schema, modele == "faux-invente"), ensure_ascii=False)
    if fonction == "codes":
        codes = codes_du_schema(schema)
        if modele == "faux-invente":
            codes["cause"] = "C42"
        return json.dumps(codes, ensure_ascii=False)
    if fonction == "commentaireRapport" and modele == "faux-chiffres":
        return json.dumps({"texte": "La disponibilité atteint 92 % ce mois-ci."}, ensure_ascii=False)
    return json.dumps(REPONSES.get(fonction, {"texte": "Réponse du faux fournisseur."}), ensure_ascii=False)


class _Gestionnaire(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *arguments):    # silence
        pass

    @property
    def faux(self):
        return self.server.faux

    def _envoyer(self, statut, donnees, type_contenu="application/json; charset=utf-8", entetes=None):
        octets = donnees if isinstance(donnees, bytes) else json.dumps(donnees, ensure_ascii=False).encode("utf-8")
        self.send_response(statut)
        self.send_header("Content-Type", type_contenu)
        self.send_header("Content-Length", str(len(octets)))
        self.send_header("Access-Control-Allow-Origin", "*")
        for nom, valeur in (entetes or {}).items():
            self.send_header(nom, valeur)
        self.end_headers()
        self.wfile.write(octets)

    def _envoyer_tronque(self, modele):
        """Le début de la réponse seulement, puis la connexion fermée (faux-tronque, faux-tronque-morceaux)."""
        debut = b'{"model": "faux", "message": {"content": "Constat'      # 49 octets, JSON inachevé
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        if modele == "faux-tronque-morceaux":
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            self.wfile.write(b"%x\r\n" % 4096 + debut)          # morceau de 4 096 octets annoncé, 49 envoyés
        else:
            self.send_header("Content-Length", str(len(debut) + 1000))
            self.end_headers()
            self.wfile.write(debut)
        self.wfile.flush()
        self.close_connection = True

    def _noter(self, corps):
        self.faux.requetes.append({"methode": self.command, "chemin": self.path,
                                   "entetes": {k.lower(): v for k, v in self.headers.items()}, "corps": corps})

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _cle_refusee(self):
        if not self.path.startswith("/v1/") or not self.faux.cle_attendue:
            return False
        if self.headers.get("Authorization") == "Bearer " + self.faux.cle_attendue:
            return False
        self._envoyer(401, {"error": {"message": "Clé absente ou fausse."}})
        return True

    def do_GET(self):
        self._noter(None)
        if self._cle_refusee():
            return
        if self.path == "/api/tags":
            return self._envoyer(200, {"models": [{"name": m} for m in self.faux.modeles]})
        if self.path == "/v1/models":
            return self._envoyer(200, {"object": "list", "data": [{"id": m, "object": "model"} for m in self.faux.modeles]})
        if self.path == "/redirection-cible":
            return self._envoyer(200, {"texte": "cible de la redirection"})
        self._envoyer(404, {"error": "inconnu"})

    def do_POST(self):
        longueur = int(self.headers.get("Content-Length") or 0)
        texte = self.rfile.read(longueur).decode("utf-8") if longueur else ""
        try:
            corps = json.loads(texte) if texte else {}
        except ValueError:
            corps = {"_texte": texte}
        self._noter(corps)
        if self._cle_refusee():
            return
        openai = self.path == "/v1/chat/completions"
        if self.path not in ("/api/chat", "/v1/chat/completions"):
            return self._envoyer(404, {"error": "inconnu"})
        modele = str(corps.get("model", "faux"))
        if modele == "faux-redirige":
            return self._envoyer(302, {}, entetes={"Location": "/redirection-cible"})
        if modele in ("faux-tronque", "faux-tronque-morceaux"):
            return self._envoyer_tronque(modele)
        if modele == "faux-lent":
            time.sleep(self.faux.lenteur_s)
        if openai and modele == "faux-schema" and (corps.get("response_format") or {}).get("type") == "json_schema":
            return self._envoyer(400, {"error": {"message": "response_format json_schema non pris en charge"}})
        fonction = fonction_demandee(corps.get("messages"))
        contenu = contenu_reponse(modele, fonction, schema_demande(corps, openai), corps.get("messages"))
        if openai:
            return self._envoyer(200, {"id": "faux-1", "object": "chat.completion", "model": modele,
                                       "choices": [{"index": 0, "message": {"role": "assistant", "content": contenu},
                                                    "finish_reason": "stop"}]})
        self._envoyer(200, {"model": modele, "message": {"role": "assistant", "content": contenu}, "done": True})


class _Serveur(http.server.ThreadingHTTPServer):
    daemon_threads = True


class FauxFournisseur:
    """Serveur du faux fournisseur, sur 127.0.0.1 et un port libre, dans un fil d'exécution."""

    def __init__(self, lenteur_s=5, cle_attendue=None, modeles=None):
        self.lenteur_s = lenteur_s
        self.cle_attendue = cle_attendue
        self.modeles = list(modeles or MODELES)
        self.requetes = []
        self._serveur = None
        self._fil = None
        self.url = None

    def __enter__(self):
        self.demarrer()
        return self

    def __exit__(self, *erreur):
        self.arreter()
        return False

    def demarrer(self):
        self._serveur = _Serveur(("127.0.0.1", 0), _Gestionnaire)
        self._serveur.faux = self
        self.url = "http://127.0.0.1:%d" % self._serveur.server_address[1]
        self._fil = threading.Thread(target=self._serveur.serve_forever, daemon=True)
        self._fil.start()

    def arreter(self):
        if self._serveur is not None:
            self._serveur.shutdown()
            self._serveur.server_close()
            self._serveur = None

    def requetes_vers(self, chemin):
        return [r for r in self.requetes if r["chemin"] == chemin]
