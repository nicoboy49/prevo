"""Mandataire inverse minimal pour les tests (lot 7, ARCHITECTURE.md §22.7 ; D129, CS128 ; tâche T164).

Écoute sur 127.0.0.1 (port libre) et relaie chaque requête vers un serveur Prévo, comme le feraient tailscale serve,
Caddy, nginx ou IIS : il ajoute X-Forwarded-Proto, X-Forwarded-Host et X-Forwarded-For (l'adresse « vue » du client),
et au choix Tailscale-User-Login ; il recopie la réponse (code, en-têtes hors connexion, corps) telle quelle.
Bibliothèque standard seulement ; aucune sortie du PC.

    with MandataireTest(url_prevo, hote="prevo.tail1234.ts.net", protocole="https", client="100.64.0.7") as m:
        urllib.request.urlopen(m.url + "/api/info")
"""
import http.client
import http.server
import socketserver
from urllib.parse import urlsplit

ENTETES_NON_RELAYEES = {"connection", "keep-alive", "transfer-encoding", "proxy-connection", "upgrade", "host",
                        "content-length"}


class _Relais(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *arguments):      # silence
        pass

    def _relayer(self):
        serveur = self.server
        longueur = int(self.headers.get("Content-Length") or 0)
        corps = self.rfile.read(longueur) if longueur else b""
        entetes = {nom: valeur for nom, valeur in self.headers.items() if nom.lower() not in ENTETES_NON_RELAYEES}
        entetes["Host"] = serveur.hote_amont
        for nom, valeur in serveur.entetes_ajoutes().items():
            if valeur is not None:
                entetes[nom] = valeur
        if corps:
            entetes["Content-Length"] = str(len(corps))
        connexion = http.client.HTTPConnection(serveur.amont_hote, serveur.amont_port, timeout=30)
        try:
            connexion.request(self.command, self.path, body=corps or None, headers=entetes)
            reponse = connexion.getresponse()
            octets = reponse.read()
            self.send_response(reponse.status)
            for nom, valeur in reponse.getheaders():
                if nom.lower() not in ("connection", "transfer-encoding", "content-length", "keep-alive"):
                    self.send_header(nom, valeur)
            self.send_header("Content-Length", str(len(octets)))
            self.end_headers()
            self.wfile.write(octets)
        finally:
            connexion.close()

    do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = _relayer


class _ServeurRelais(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = False
    request_queue_size = 64


class MandataireTest:
    """Mandataire de test. hote : X-Forwarded-Host (avec son port s'il y en a un) ; protocole : X-Forwarded-Proto ;
    client : X-Forwarded-For (None : pas d'en-tête) ; tailscale : Tailscale-User-Login (None : pas d'en-tête) ;
    forwarded=False : aucun en-tête X-Forwarded-* (un simple relais)."""

    def __init__(self, url_prevo, hote="prevo.exemple", protocole="https", client="100.64.0.7", tailscale=None,
                 forwarded=True):
        morceaux = urlsplit(url_prevo)
        self.amont_hote, self.amont_port = morceaux.hostname, morceaux.port
        self.hote_amont = "%s:%d" % (self.amont_hote, self.amont_port)
        self.hote, self.protocole, self.client, self.tailscale, self.forwarded = hote, protocole, client, tailscale, forwarded
        self._serveur = None
        self.port = None
        self.url = None

    def entetes_ajoutes(self):
        if not self.forwarded:
            return {"Tailscale-User-Login": self.tailscale}
        return {"X-Forwarded-Proto": self.protocole, "X-Forwarded-Host": self.hote, "X-Forwarded-For": self.client,
                "Tailscale-User-Login": self.tailscale}

    def __enter__(self):
        self.demarrer()
        return self

    def __exit__(self, *exception):
        self.arreter()
        return False

    def demarrer(self):
        self._serveur = _ServeurRelais(("127.0.0.1", 0), _Relais)
        self._serveur.amont_hote, self._serveur.amont_port = self.amont_hote, self.amont_port
        self._serveur.hote_amont = self.hote_amont
        self._serveur.entetes_ajoutes = self.entetes_ajoutes
        self.port = self._serveur.server_address[1]
        self.url = "http://127.0.0.1:%d" % self.port
        import threading
        self._fil = threading.Thread(target=self._serveur.serve_forever, daemon=True)
        self._fil.start()

    def arreter(self):
        if self._serveur is not None:
            self._serveur.shutdown()
            self._serveur.server_close()
            self._serveur = None
