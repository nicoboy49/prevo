# Installing Prévo: the IT person's guide

*Version française : [INSTALLATION.fr.md](INSTALLATION.fr.md)*

This document is for the person who installs Prévo on a server or on the workshop PC, and who wants to know
exactly what it does. It applies from Prévo 2 onwards.

- For users (sign-in, phones, Solo mode): [GUIDE.en.html](../GUIDE.en.html), chapters 2 and 8.
- For the technical contract (API, roles per route, formats): [ARCHITECTURE.md](ARCHITECTURE.md) (in French), §22.
- In most workshops, the installation wizard is enough: it asks three questions and sets up everything that
  follows. This document says what it does, and how to do it by hand.

## 1. What the zip contains

The release zip contains a single folder, `prevo-<version>/`. In it you will find:

| Item | Purpose |
| --- | --- |
| `serveur.py` | The server: a single Python file, standard library only. |
| `index.html`, `favicon.svg`, `css/`, `js/` | The application, served to browsers. |
| `acces/` | The front door: the “Trust the workshop PC” page and its illustrations. |
| `GUIDE.html`, `README.md`, `FICHE_TECHNIQUE_CSV.md` | The guide, the introduction, the format of the CSV files. |
| `Lancer_GMAO.bat`, `lancer.sh` | The launchers (Windows; Mac and Linux). |
| `Reinitialiser_mot_de_passe.bat` | Gives an account a temporary password (Windows). |
| `python/` | Official embedded Python for 64-bit Windows: nothing to install on Windows. |
| `outils-tiers/` | mkcert 1.4.4 for 64-bit Windows, with its licence: it makes the workshop certificate. |
| `outils/empreintes-tiers.json` | SHA-256 fingerprints of mkcert, checked by `serveur.py` before every launch. |
| `LICENSE`, `NOTICE` | Prévo's MIT licence, the licences of the bundled libraries. |

The zip does **not** contain a `donnees/` folder: `serveur.py` creates it on first launch. An update
therefore never touches the data. It does not contain this document either (`docs/` stays in the repository).

As it is used, Prévo creates next to `serveur.py`:

- `prevo.config.json`: the configuration (§4), written by the wizard;
- `Installer_demarrage.ps1`, `Retirer_demarrage.ps1`, `Demarrage_session.ps1` (Windows), `prevo.service` (Linux) or
  `pro.prevo.serveur.plist` (macOS): the start-up scripts (§8), written before they are run, so that you
  can read them;
- `donnees/`: the 24 CSV files, `documents/` (photos, PDFs, frozen reports), `sauvegardes/`, `acces/` (accounts,
  devices, sign-in log, the workshop certificate), `journal-serveur.log`, `copie-externe.json`, and
  `installation.json` during the wizard.

## 2. Scopes: who can reach Prévo

One rule: **beyond this PC, accounts and https are mandatory.** `serveur.py` checks it at start-up,
before opening any port. If the configuration does not respect it, it refuses to start, says why on the
console and in `donnees/journal-serveur.log`, and exits with code 2. No option bypasses it.

| Scope | Listens on | Accounts | https | Reverse proxy |
| --- | --- | --- | --- | --- |
| This PC (default) | `127.0.0.1` | no (profiles, as in 1.2) | no | no |
| The workshop Wi-Fi | all interfaces | yes | workshop certificate (§6) | no |
| Also outside the workshop | all interfaces | yes | workshop certificate | yes, `tailscale serve` (§7.2) |
| Intranet, behind a reverse proxy | `127.0.0.1` | yes | provided by the proxy | yes (§7) |

The wizard's three paths:

- **Solo**: one PC, one person. Scope “this PC”, with no account and no https. For a phone, Tailscale, and a
  password becomes mandatory.
- **Workshop**: a small team on the Wi-Fi. Accounts for the manager and the technicians, requesters' phones
  enrolled by QR, certificate made by Prévo, start-up with the PC.
- **Intranet**: you install Prévo behind the company's reverse proxy or VPN, with your own
  certificate; everyone has an account, requesters included.

## 3. Installing

### 3.1 Windows

1. Unzip the zip into `C:\Prevo` (recommended: a short path, outside the user profile; the resulting
   `C:\Prevo\prevo-<version>` folder is fine as it is). Elsewhere, the wizard offers to copy Prévo into
   `C:\Prevo`: each file is copied then checked, and the old folder is never deleted.
2. Double-click `Lancer_GMAO.bat`. It uses the zip's `python\python.exe`, otherwise a Python 3.11 or newer
   already installed (`py -3` or `python`).
3. The PC's browser opens on the wizard (`http://localhost:8080/#/installation`). Choose “I am the company's IT
   person”: all the steps appear on one page, and nothing happens without a click.

Until the installation is finished, Prévo listens only on this PC. Nothing is written to
`prevo.config.json` before “Finish”; Prévo then restarts with the configuration.

With no data to start from, the last step asks what to begin with (empty, or the demo data) and the
**Prévo language** (suggested from the browser's language: French or English today). “Finish”
writes it to `parametres.csv` (`langue_defaut`): it is the language of the workstations that have not chosen their own and of the
texts that Prévo writes into the data; it can be changed afterwards in Settings, “Company” section. Data already
there (Prévo 1.2) is not touched: its language stays French until Settings changes it.

### 3.2 Linux or macOS

Python 3.11 or newer is needed (standard library only). The zip bundles neither Python nor mkcert for
these systems.

```sh
sudo mkdir -p /opt/prevo
sudo cp -r prevo-<version>/. /opt/prevo/
cd /opt/prevo && ./lancer.sh --sans-navigateur
```

- Prévo is under `/opt/prevo` only as an example. Avoid a home folder: the systemd unit in §8.2
  protects home folders (`ProtectHome=yes`).
- For the workshop certificate (§6), put your system's mkcert in `outils-tiers/`, under the name used on the
  mkcert releases page (`mkcert-v1.4.4-linux-amd64`, `mkcert-v1.4.4-linux-arm64`,
  `mkcert-v1.4.4-darwin-arm64`…), and make it executable (`chmod +x`). Prévo compares its fingerprint with
  `outils/empreintes-tiers.json` and refuses a different file. Without mkcert, supply your own PEM files or
  use a reverse proxy.

### 3.3 A server with no screen

The wizard answers only to the PC itself (`127.0.0.1`): from the network, its addresses do not exist (404).
On a server with no browser, open an SSH tunnel from your workstation:

```sh
ssh -L 8080:127.0.0.1:8080 vous@serveur
```

then open `http://localhost:8080/#/installation` on your workstation: for Prévo, the request comes from
`127.0.0.1`.

## 4. Configuration: `prevo.config.json`

### 4.1 Where, when, in what order

- **Where**: next to `serveur.py` (or the file given by `--config`). Never in `donnees/`: Prévo neither
  backs it up nor exports it. Back it up yourself, and protect it if it contains `ia_cle`.
- **Who writes it**: the wizard, at “Finish”; then Settings › Access and installation (from the server PC),
  key by key. Unknown keys and `_aide` are kept as they are. You can also edit it by hand.
- **Format**: JSON in UTF-8. Keys that start with `_` are comments (`_aide`).
- **Priority**: the defaults, then the file, then the command line (§5), which wins.
- **When**: the file is read at start-up only. After a change, restart Prévo.
- **Errors**: an unknown key is ignored and reported on the console; an invalid value stops the start-up
  (code 2), with the name of the key.
- **Up-to-date list**: `serveur.py --aide` prints each key, its type, its default and its help.

**The first account.** With `"comptes": true` written by hand and no manager account created yet, Prévo
listens only on this PC, opens no session and keeps the wizard reachable **from this PC only**: the
console gives its address (`http://localhost:8080/#/installation`), and the server PC's browser opens it
by itself. Create the account there (“Your account” step); as soon as it exists, the wizard can be reached only through
a manager's session (Settings › Access and installation).

### 4.2 All the keys

A faithful copy of `serveur.py --aide` (the default is written as in the JSON file):

<!-- cles-configuration:debut -->
| Clé | Type | Défaut | Effet |
| --- | --- | --- | --- |
| `portee` | one of ce-pc, atelier, dehors | `"ce-pc"` | Where Prévo can be opened from: this PC only, the workshop Wi-Fi, or also outside the workshop. Beyond this PC, a password and https are mandatory. |
| `ecoute` | one of 127.0.0.1, 0.0.0.0 | `"127.0.0.1"` | Listening address: 127.0.0.1 (this PC only) or 0.0.0.0 (the network). |
| `port_http` | integer | `8080` | Port of the application on this PC and of the front door on the network. Changing the port makes printed labels obsolete. |
| `port_https` | integer | `8443` | Port of the application over https on the network. |
| `noms` | list | `[]` | Names by which this PC is called, in addition to its address and its Windows name (Tailscale name, company network name). An unknown name is refused, for security. |
| `certificat` | text | `""` | The server's https certificate (PEM file), with its key. |
| `cle` | text | `""` | The certificate's private key (PEM file). |
| `certificat_auto` | boolean | `true` | Certificate made by Prévo for the workshop, to be accepted once per device. |
| `mandataire` | boolean | `false` | Prévo is behind a reverse proxy (tailscale serve, Caddy, nginx, IIS) that carries the https: the X-Forwarded-Proto and X-Forwarded-Host headers coming from this PC are believed. |
| `comptes` | boolean | `false` | Sign-in mandatory: each person has an account, or an enrolled device for requesters. |
| `demandeurs_avec_compte` | boolean | `false` | No: a requester gives their name on a device enrolled by QR. Yes: each requester has a password. |
| `session_heures` | integer | `12` | After this long without activity, the person must sign in again. |
| `session_longue_jours` | integer | `30` | Length of “stay signed in on this device”. |
| `invitation_heures` | integer | `24` | Validity of a device invitation (1 to 168 hours). |
| `demarrage` | one of aucun, systeme, session | `"aucun"` | Prévo starts with the PC (systeme), at session sign-in (session), or by hand (aucun). |
| `veille_desactivee` | boolean | `false` | The PC no longer goes to sleep when on mains power. |
| `copie_sauvegardes` | text | `""` | Folder where the day's backup is copied every night (USB stick, NAS, synchronised folder); empty: no copy. |
| `quota_documents_mo` | integer | `4096` | Maximum space for attached documents, in megabytes. |
| `ia_fournisseur` | one of ollama, openai | `"ollama"` | Type of AI service: ollama (Ollama) or openai (any OpenAI-compatible API: LM Studio, Mistral…). |
| `ia_url` | text | `"http://localhost:11434"` | Address of the AI service that all workstations use. Set here only, never on a phone. |
| `ia_cle` | text | `""` | Key of the AI service, kept on this PC, never sent to browsers. The PREVO_IA_CLE environment variable takes precedence; never on the command line. |
| `ia_en_ligne` | boolean | `false` | Allow an online AI service: the texts sent go to that provider. |
<!-- cles-configuration:fin -->

`serveur.py --aide` prints this list in French.

Notes:

- **What counts at start-up**: `ecoute`, `comptes`, `certificat` and `cle` (or `certificat_auto`) and
  `mandataire`. `portee` summarises these choices for the wizard and Settings. `demarrage` and `veille_desactivee` record
  what has been installed: changing these two keys by hand neither installs nor removes anything (§8).
- **Integer ranges**: `port_http`: 1 to 65535; `port_https`: 1 to 65535; `session_heures`: 1 to 720;
  `session_longue_jours`: 1 to 365; `invitation_heures`: 1 to 168; `quota_documents_mo`: 1 to 1048576.
- **Ports**: if a port is taken, Prévo takes the next free one (up to 20 further on) and says so on the console.
  Behind a reverse proxy or a firewall set for a specific port, choose a free port.
- **`noms`**: in lower case; the `Host` header (and `X-Forwarded-Host` behind a reverse proxy) must be an
  IP address, `localhost`, the PC's name or one of these names. Otherwise, refusal (403).
- **`copie_sauvegardes`**: a relative path starts from Prévo's folder. The folder must exist and must not be
  inside `donnees/`.
- **`quota_documents_mo`**: 4,096 MB (4 GB) by default, as much as the largest ZIP that Prévo imports: an export
  from Prévo, even from folder mode (which has no ceiling), can be re-imported in server mode. Beyond that, uploading a
  document (or importing a ZIP) is refused, “Documents folder full”, and nothing is written. To increase it:
  Settings › Access and installation, on the server PC (section “Requester accounts, session lengths,
  documents”, then “Apply and restart”), or this key.
- **AI**: the service key never goes through the screen or the command line (it would be visible in the
  process list). Put it in `ia_cle` (protected file) or in the `PREVO_IA_CLE` environment variable
  of the account that runs Prévo.

### 4.3 Examples

Workshop (what the wizard writes, reduced to the keys that change):

```json
{
  "portee": "atelier",
  "ecoute": "0.0.0.0",
  "comptes": true,
  "certificat_auto": true,
  "demarrage": "systeme",
  "veille_desactivee": true
}
```

Intranet behind a reverse proxy on the same server (§7):

```json
{
  "portee": "atelier",
  "ecoute": "127.0.0.1",
  "port_http": 8080,
  "noms": ["prevo.entreprise.example"],
  "certificat_auto": false,
  "mandataire": true,
  "comptes": true,
  "demandeurs_avec_compte": true,
  "demarrage": "systeme"
}
```

Intranet without a reverse proxy, with the company certificate (the door stays on http on `port_http` and leads
browsers to the application over https on `port_https`):

```json
{
  "portee": "atelier",
  "ecoute": "0.0.0.0",
  "noms": ["prevo.entreprise.example"],
  "certificat": "/etc/prevo/certificat.pem",
  "cle": "/etc/prevo/cle.pem",
  "certificat_auto": false,
  "comptes": true,
  "demandeurs_avec_compte": true
}
```

## 5. Command line

`serveur.py` (Windows: `python\python.exe serveur.py`; elsewhere: `python3 serveur.py`). The launchers
`Lancer_GMAO.bat` and `lancer.sh` pass these options on.

| Option | Effect |
| --- | --- |
| `--port PORT` | Replaces `port_http`. |
| `--ecoute 127.0.0.1` or `--ecoute 0.0.0.0` | Replaces `ecoute` (the rules of §2 are still checked). |
| `--hote NOM` | Adds a name to `noms` (repeatable). |
| `--certificat FICHIER --cle FICHIER` | Replace `certificat` and `cle` (PEM files, always together). |
| `--ia-url URL`, `--ia-fournisseur ollama\|openai`, `--ia-en-ligne` | Replace `ia_url`, `ia_fournisseur`, `ia_en_ligne`. Never the key. |
| `--config FICHIER` | A configuration file other than `prevo.config.json` next to `serveur.py`. |
| `--donnees DOSSIER` | A data folder other than `donnees/` next to `serveur.py`. |
| `--sans-navigateur` | Does not open the browser at start-up (service, server with no screen). |
| `--journal` | Also writes the console to `donnees/journal-serveur.log` (automatic with no console). |
| `--aide` | Prints each configuration key with its help, then stops. |
| `--reinitialiser IDENTIFIANT` | Gives an account a temporary password (§9), then stops. |
| `--servir-tests` | For automated tests only; not needed in normal use. |

The console and `journal-serveur.log` are in French or English depending on the Prévo language (Settings ›
Company, “Prévo language”); before that setting is made, depending on the language of Windows (or of the system). A change applies at
the next restart.

Automatic start-up (§8) runs `serveur.py --sans-navigateur` with no other option: keep the data in
`donnees/` next to `serveur.py`, or add the option to the task or service yourself.

## 6. Front door and workshop certificate

Outside the “this PC” scope, Prévo opens two ports:

- **the door**, over http on `port_http` (8080): this is the only address Prévo gives out (home screen QR,
  labels, access sheet). It serves only its page, its illustrations and `/acces/ca.crt`; it never reads
  any data. A browser that already trusts the PC is taken straight to https, on the same page; otherwise, the
  “Trust the workshop PC” page guides the installation of the certificate (Android, iPhone);
- **the application**, over https on `port_https` (8443). This address is never to be typed.

The certificate can be set up in three ways:

1. **Made by Prévo** (`certificat_auto`, the default): mkcert, driven by Prévo, creates an authority specific to
   the workshop in `donnees/acces/autorite/` (`rootCA.pem`, which the door serves under the name `prevo-ca.crt`) and the
   server certificate in `donnees/acces/certificat.pem` and `cle.pem`, for the IP address, the PC's name,
   `<nom>.local`, `localhost`, `127.0.0.1` and the `noms`. It is remade at start-up if the address or the names
   change; phones have nothing to redo. Each device trusts the authority once. Never
   distribute `rootCA-key.pem`: with it, anyone can make certificates that your devices would believe. Prévo neither
   reads nor serves it.
2. **Your PEM files** (`certificat` and `cle`, or `--certificat` and `--cle`): a company certificate,
   recognised by your devices. Nothing to do on the phones.
3. **A reverse proxy** (§7) carries the https; Prévo stays on http on `127.0.0.1`.

Without a valid certificate outside “this PC”, Prévo refuses to start (code 2).

Prévo sets its own security headers (`Content-Security-Policy`, `X-Frame-Options`, `Referrer-Policy`,
`Permissions-Policy`) and `Strict-Transport-Security` (180 days) for a name in `noms` served over https. A
reverse proxy must not replace them.

## 7. Behind a reverse proxy

### 7.1 The rules

- The proxy runs **on the same server** as Prévo and reaches it over http on `127.0.0.1:<port_http>`. Prévo
  believes the `X-Forwarded-*` headers only from a connection coming from `127.0.0.1` or `::1`, and only with
  `"mandataire": true`. A proxy installed on another machine is not recognised: install a local relay
  (Caddy, nginx) on Prévo's server.
- The proxy sets **`X-Forwarded-Proto`** (`https`) and **`X-Forwarded-Host`** (the public name). Without them, the
  request is treated as coming from this PC: cookie without `Secure`, wrong addresses and QR codes. `X-Forwarded-For` gives
  the person's address to the sign-in log (Prévo takes the last address in the list).
- The public name is in **`noms`**, otherwise Prévo answers 403 “Origin host name refused (X-Forwarded-Host)”.
- **`"comptes": true`** is mandatory with `"mandataire": true`.
- Let through requests of **50 MB** (saving a whole table, for example `ordres_travail.csv` of a
  large database; a document or a photo: 10 MB at most) and responses that take up to
  **120 seconds** (AI relay). Prévo uses no WebSocket.
- Prévo may be exposed on the Internet only behind Tailscale, the company VPN or a proxy over https.
  Prévo has no two-factor authentication: preferably put your own access control in front.

Prévo configuration for all the examples below (with the name of your choice):

```json
{
  "ecoute": "127.0.0.1",
  "port_http": 8080,
  "noms": ["prevo.entreprise.example"],
  "certificat_auto": false,
  "mandataire": true,
  "comptes": true
}
```

### 7.2 `tailscale serve` (outside the workshop)

The wizard sets it up itself (“Away from the workshop” step). By hand, on the server connected to your
Tailscale network:

```sh
tailscale serve --bg --https=443 http://127.0.0.1:8080
tailscale serve status
```

In `prevo.config.json`: the PC's Tailscale name in `noms` (for example `pc-atelier.tail1234.ts.net`) and
`"mandataire": true`. `tailscale serve` carries the https with a certificate recognised everywhere, and sets `X-Forwarded-Proto`,
`X-Forwarded-Host`, `X-Forwarded-For` and `Tailscale-User-Login`: the sign-in log records the Tailscale account
of each session. On Windows, `tailscale set --unattended=true` makes it run with no session open.
Turn off key expiry for the server in the Tailscale console.

In the scope “also outside the workshop”, Prévo also listens on the workshop network with its own certificate
(`"ecoute": "0.0.0.0"`, `"certificat_auto": true`): both accesses coexist.

### 7.3 Caddy

```caddyfile
prevo.entreprise.example {
	# Company certificate; without this line, Caddy asks Let's Encrypt for one
	# (the name must then be reachable from the Internet).
	tls /etc/prevo/certificat.pem /etc/prevo/cle.pem

	# Caddy itself sets X-Forwarded-Proto, X-Forwarded-Host and X-Forwarded-For.
	reverse_proxy 127.0.0.1:8080
}
```

### 7.4 nginx

```nginx
server {
    listen 443 ssl;
    server_name prevo.entreprise.example;

    ssl_certificate     /etc/prevo/certificat.pem;
    ssl_certificate_key /etc/prevo/cle.pem;

    client_max_body_size 52m;      # Prévo accepts 50 MB for a table, 10 MB for a document
    proxy_read_timeout   180s;     # the AI relay can take 120 s to answer

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host              $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host  $host;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    }
}

server {
    listen 80;
    server_name prevo.entreprise.example;
    return 301 https://$host$request_uri;
}
```

### 7.5 IIS (URL Rewrite and ARR)

1. Install Microsoft's **URL Rewrite** and **Application Request Routing** (ARR) modules.
2. IIS Manager, server node, “Application Request Routing Cache”, “Server Proxy Settings”: tick
   “Enable proxy”, set the time-out (“Time-out”) to 180 seconds and untick “Include TCP port from client IP”
   (otherwise `X-Forwarded-For` carries a port and Prévo cannot read the address).
3. URL Rewrite, “View Server Variables”: add `HTTP_X_FORWARDED_PROTO` and `HTTP_X_FORWARDED_HOST`.
4. Create a site bound over https to `prevo.entreprise.example` with the company certificate, and put this
   `web.config` in its folder:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <system.webServer>
    <rewrite>
      <rules>
        <rule name="Prevo" stopProcessing="true">
          <match url="(.*)" />
          <serverVariables>
            <set name="HTTP_X_FORWARDED_PROTO" value="https" />
            <set name="HTTP_X_FORWARDED_HOST" value="{HTTP_HOST}" />
          </serverVariables>
          <action type="Rewrite" url="http://127.0.0.1:8080/{R:1}" />
        </rule>
      </rules>
    </rewrite>
    <security>
      <requestFiltering>
        <!-- 50 MB per table (by default IIS refuses anything above about 30 MB) -->
        <requestLimits maxAllowedContentLength="54525952" />
      </requestFiltering>
    </security>
  </system.webServer>
</configuration>
```

### 7.6 Cloudflare Tunnel

Cloudflare Tunnel makes Prévo reachable from the Internet without opening a port: keep it for a company that
already uses it, with Cloudflare Access in front of Prévo. Cloudflare decrypts the traffic: it is a processor, to be
entered in the register of processing activities. Cloudflare cuts a response that takes longer than 100 seconds: a very slow AI
response may fail.

So that Prévo reliably receives `X-Forwarded-Proto` and `X-Forwarded-Host`, `cloudflared` goes through a small
Caddy relay on the same server:

```yaml
# cloudflared configuration (config.yml)
tunnel: ID-DU-TUNNEL
credentials-file: /etc/cloudflared/ID-DU-TUNNEL.json
ingress:
  - hostname: prevo.entreprise.example
    service: http://127.0.0.1:8081
  - service: http_status:404
```

```caddyfile
# Local relay: receives cloudflared on 127.0.0.1:8081, sets the headers, passes on to Prévo
http://:8081 {
	bind 127.0.0.1
	reverse_proxy 127.0.0.1:8080 {
		header_up X-Forwarded-Proto https
		header_up X-Forwarded-Host prevo.entreprise.example
		header_up X-Forwarded-For {http.request.header.Cf-Connecting-Ip}
	}
}
```

### 7.7 Checking

- `curl https://prevo.entreprise.example/api/ping` answers `{"application": "Prévo", …}`. A 403 answer “Origin host
  name refused”: the name is missing from `noms`.
- Sign in: on the manager's home screen, the “Connect a phone” card gives
  `https://prevo.entreprise.example/`; in the browser's tools, the `id` cookie carries `Secure`.
- Team › Access › Sign-in log: the “adresse” column shows the person's address, not
  `127.0.0.1`.

## 8. Starting with the machine

### 8.1 Windows

The wizard (“Startup” step) writes `Installer_demarrage.ps1` into Prévo's folder, displays it, then
runs it with a single administrator prompt. The script:

- creates the scheduled task **`Prevo`**: at PC start-up, 30 seconds later, under the System account, with no
  window (`python\pythonw.exe serveur.py --sans-navigateur`);
- adds the inbound firewall rule **`Prevo`**: private profile, local subnet, `pythonw.exe`, ports
  `port_http` and `port_https`;
- has Windows recognise the workshop authority (`mkcert -install`) when Prévo makes the certificate;
- if `veille_desactivee`: no sleep or hibernation on mains power (screen off after 15 minutes), and
  keeps the previous settings in `donnees\acces\veille-avant.json`.

If the administrator prompt is refused, nothing is installed; `Demarrage_session.ps1` offers a fallback that needs no
rights: a task at the user's sign-in (otherwise `Prevo.cmd` in their Startup folder).

**Removing**: Settings › Access and installation (start-up “Manually”), or `Retirer_demarrage.ps1` as
administrator (right-click, “Run with PowerShell”): the task and the rule are removed, and sleep is put back
as before.

Useful commands (administrator prompt): `schtasks /run /tn Prevo`, `schtasks /end /tn Prevo`,
`schtasks /query /tn Prevo /v`.

### 8.2 Linux (systemd)

The wizard writes `prevo.service` next to `serveur.py` and gives the commands. Example for `/opt/prevo`:

```ini
# /etc/systemd/system/prevo.service: written by Prévo (ARCHITECTURE.md §22.9).
[Unit]
Description=Prévo (GMAO)
After=network-online.target
Wants=network-online.target

[Service]
User=prevo
Group=prevo
WorkingDirectory=/opt/prevo
ExecStart=/usr/bin/python3 /opt/prevo/serveur.py --sans-navigateur
Restart=on-failure
RestartSec=5
NoNewPrivileges=yes
ProtectSystem=full
ProtectHome=yes
ReadWritePaths=/opt/prevo/donnees

[Install]
WantedBy=multi-user.target
```

```sh
sudo useradd --system --home /opt/prevo --shell /usr/sbin/nologin prevo
sudo chown -R prevo:prevo /opt/prevo
sudo cp prevo.service /etc/systemd/system/prevo.service
sudo systemctl daemon-reload
sudo systemctl enable --now prevo
```

Under systemd, the console goes to the system journal (`journalctl -u prevo`). Add `--journal` to
`ExecStart` to also get `donnees/journal-serveur.log`, which Settings › Access and installation displays.
Open only `port_http` and `port_https` to the local network, for example
`sudo ufw allow from 192.168.1.0/24 to any port 8080,8443 proto tcp`. To remove:
`sudo systemctl disable --now prevo`.

### 8.3 macOS

The wizard writes `pro.prevo.serveur.plist` (launch agent, `RunAtLoad`, `KeepAlive`) and the command
`launchctl load -w <path of the file>`; to remove: `launchctl unload -w <path of the file>`.

### 8.4 With no console

Started with no console (scheduled task, `pythonw.exe`), Prévo writes what it does to `donnees/journal-serveur.log`
(5 files of 1 MB at most). Settings › Access and installation shows the last 20 lines.

## 9. Accounts, roles and devices

- **Accounts**: identifier of the form `prenom.nom`. The first manager is created by the wizard; the other
  accounts by the manager, in Team › Access (create, edit, reset, deactivate, activate). There is
  always at least one active manager.
  The identifier is written in plain letters (“Ayşe Işık” → `ayse.isik`) and is typed with no concern for case or Turkish
  letters (“AYŞE.IŞIK” opens `ayse.isik`). A second account with the same first name and last name is refused, unless you
  tick “This is a different person”. If a typed identifier matches several accounts (old accounts whose name
  was written two ways), Prévo refuses the sign-in and asks for the exact identifier.
- **Language of each account**: the person chooses it in “This workstation” (“For my account”: it follows them on all
  workstations; “For this workstation only”: this browser only), the manager in Team › Access; empty, it is the
  installation language; on sign-out, the screen goes back to the workstation's or the installation's language.
- **Passwords**: 12 to 256 characters, no composition rule (a passphrase is recommended).
  Only a salted hash is kept (scrypt; PBKDF2 if Python has no scrypt), in
  `donnees/acces/comptes.json`. A temporary password
  is shown once only and must be changed at first sign-in.
- **Failures**: same message in every case; increasing delay from the 5th failure in a row, account locked
  for 15 minutes at the 10th; an address that exceeds 20 failures per hour is slowed down.
- **Sessions**: 12 hours without activity (`session_heures`); 30 days with “Stay signed in on this device”
  (`session_longue_jours`). `HttpOnly` cookie, `SameSite=Lax`, `Secure` over https. A changed password closes the
  account's other sessions; a reset password or a deactivated account closes them all.
- **Forgotten password**: no email. On the server PC, `Reinitialiser_mot_de_passe.bat` asks for the
  identifier and displays a temporary password. Elsewhere: `python3 serveur.py --reinitialiser prenom.nom`,
  run in Prévo's folder by the account that runs Prévo (Linux:
  `sudo -u prevo python3 /opt/prevo/serveur.py --reinitialiser prenom.nom`). There is no need to stop Prévo. Whoever has
  control of the server has control of Prévo.
- **Deactivating**: Team › Access, “Deactivate”. The account stays in the list (history) and can no longer
  sign in; its sessions are closed at once.
- **Roles**: requester, technician, manager, checked by the server on every request. A requester reads neither
  costs, nor technicians, nor work orders, and adds only requests; a technician sees neither hourly rate nor prices. The AI
  is reserved for technicians and the manager. Full table:
  [ARCHITECTURE.md](ARCHITECTURE.md) (in French) §22.5.
- **Requesters' devices**: no password, by invitation (Team › Access › Devices, QR valid from 1 hour
  to 7 days, `invitation_heures`); the phone gives a name and stays recognised for a year, with the requester's rights;
  “Revoke” cuts it off from its next request. With `"demandeurs_avec_compte": true`, enrolment is disabled
  and each requester has an account.
- **The `donnees/acces/` folder**: `comptes.json`, `sessions.json` (token hashes), `appareils.json`,
  `journal-acces.csv`, the workshop certificate and authority. Written by the server alone: do not edit it by
  hand, do not serve it, never attach it to a bug report.

## 10. Logs

| Log | Where | Kept | Content |
| --- | --- | --- | --- |
| Sign-ins | `donnees/acces/journal-acces.csv` | one year, purged every day | `date;qui;adresse;agent;resultat;tailscale`: sign-ins, failures, lock-outs, sign-outs, invitations, devices, revocations, accounts created, edited or reset |
| Changes | `donnees/journal.csv` | no limit | who changed what in the data (the maintenance history) |
| Server | `donnees/journal-serveur.log` | 5 files of 1 MB | start-up, refusals, external copy, errors (with no console, or with `--journal`) |

The sign-in log is exported as CSV from Team › Access › Sign-in log (“Export (CSV)”).
No password or token is ever written to it.

## 11. Backups and restoring

What Prévo does by itself (server mode):

- **Every day**, before the first change: `donnees/sauvegardes/AAAA-MM-JJ/`, with the 24 CSV files and
  the files of `donnees/acces/` **except `sessions.json`** (a session is never restored) **and `cle.pem`** (the
  private key of the workshop certificate does not leave the PC; Prévo remakes it at start-up if it is missing).
- **Before an import, a restore or a format change**: a full backup whose name says so
  (`…_avant-import`, `…_avant-restauration`, `…_avant-format-vN`).
- **External copy** (`copie_sauvegardes`): at start-up and every night, at the first change after 2 a.m., the
  day's backup is copied to `<folder>/AAAA-MM-JJ/`; 30 copies kept. A failure is noted in
  `journal-serveur.log` and shown on the manager's home screen.
- **Manual backups**: one per minute at most, the 60 most recent kept.

What is **not** in these backups, to be backed up with your own tools:

- `documents/` (photos, PDFs, frozen reports): only “Export as ZIP” (Settings) takes them;
- `prevo.config.json`;
- `donnees/acces/autorite/`: without it, a new authority is created and each phone must trust
  the workshop PC again;
- `journal-serveur.log`.

The external copy contains `comptes.json` (password hashes, never the passwords): protect its
folder like the server.

**Testing** (Settings › Backups, “Test”) re-reads each table of a backup and counts its rows, without
writing anything. **Restore…** puts back all the tables or just one, after a safety copy of the current state.
Restoring never touches `donnees/acces/`: a deactivated account does not come back with an old
backup. To put accounts back after losing the server, stop Prévo and copy by hand the files
from a backup's `acces/` folder into `donnees/acces/`.

## 12. Updating and rolling back

**Updating**:

1. Read the new version's `CHANGELOG.md` (in French).
2. Settings › Backups, “Back up now”, then copy `donnees/` and `prevo.config.json` elsewhere.
3. Stop Prévo: close the black window, or `schtasks /end /tn Prevo`, or `sudo systemctl stop prevo`.
4. Copy the contents of the new zip's `prevo-<version>/` folder over Prévo's folder, replacing
   the files. The zip has neither `donnees/` nor `prevo.config.json`: they stay as they are. On Linux, redo
   `sudo chown -R prevo:prevo /opt/prevo`.
5. Restart Prévo. If the file format changes, Prévo first makes a `…_avant-format-vN` backup.

From Prévo 1.2: same procedure. The wizard opens and sees the existing CSV files: it replaces none of them
(in Solo, it only adds the technician “me” and the Solo mode settings). The profiles remembered on
the workstations are replaced by accounts.

**Rolling back**: keep the previous version's zip. Stop Prévo, put its files back over the current ones,
restart. If the update had changed the file format, also put back the CSVs from the
`…_avant-format-vN` backup into `donnees/` (with Prévo stopped): changes made since are lost. Going back to
Prévo 1.2 means going back to a server with no accounts or front door, which answers any device on the local network
without a password: do it only for the duration of a troubleshooting session.

## 13. Company directory

Prévo does not plug into a directory (Active Directory, LDAP, Entra ID, Google Workspace): no single
sign-on, no account synchronisation. This is a choice: Prévo must remain installable by a workshop with no
IT person. What exists:

- **local accounts**, created by the manager or by you (one per employee, requesters included with
  `"demandeurs_avec_compte": true`);
- the **export of the sign-in log**, for your own monitoring;
- the company's **reverse proxy and VPN**, to place Prévo behind your own access controls
  (for example authentication on the proxy, before Prévo's sign-in page).

## 14. Personal data (GDPR)

All the data stays on the server, in `donnees/`; passwords are there only as hashes, the sign-in log
is kept for a year, and the AI (off by default) sends nothing without the manager's decision on
the server. The details for your register of processing activities are in [GUIDE.en.html](../GUIDE.en.html), chapter 8.9 “Your
data and the GDPR”.

## 15. Uninstalling

1. Keep the data: copy `donnees/` and `prevo.config.json` elsewhere (or “Export as ZIP”).
2. Remove the start-up: Settings › Access and installation, or `Retirer_demarrage.ps1` as administrator;
   also delete `Prevo.cmd` from the Startup folder if the fallback with no rights was used. Linux:
   `sudo systemctl disable --now prevo`, then `sudo rm /etc/systemd/system/prevo.service`. macOS:
   `launchctl unload -w <path of the plist file>`.
3. Remove the workshop authority from Windows (PowerShell as administrator):

   ```powershell
   $env:CAROOT = 'C:\Prevo\donnees\acces\autorite'
   & 'C:\Prevo\outils-tiers\mkcert-v1.4.4-windows-amd64.exe' -uninstall
   ```

   On each phone, remove the workshop certificate in the settings where it was installed.
4. If `tailscale serve` was set up: `tailscale serve reset`.
5. Delete Prévo's folder.
