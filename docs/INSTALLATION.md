# Installer Prévo : le guide de l'informaticien

Ce document s'adresse à la personne qui installe Prévo sur un serveur ou sur le PC de l'atelier, et qui veut
savoir exactement ce qu'il fait. Il vaut à partir de Prévo 2.

- Pour les utilisateurs (connexion, téléphones, mode Solo) : [GUIDE.html](../GUIDE.html), chapitres 2 et 8.
- Pour le contrat technique (API, rôles par route, formats) : [ARCHITECTURE.md](ARCHITECTURE.md), §22.
- Dans la plupart des ateliers, l'assistant d'installation suffit : il pose trois questions et règle tout ce qui
  suit. Ce document dit ce qu'il fait, et comment le faire à la main.

## 1. Ce que contient le zip

Le zip de la release contient un seul dossier, `prevo-<version>/`. On y trouve :

| Élément | Rôle |
| --- | --- |
| `serveur.py` | Le serveur : un seul fichier Python, bibliothèque standard seulement. |
| `index.html`, `favicon.svg`, `css/`, `js/` | L'application, servie aux navigateurs. |
| `acces/` | La porte d'entrée : la page « Faites confiance au PC atelier » et ses illustrations. |
| `GUIDE.html`, `README.md`, `FICHE_TECHNIQUE_CSV.md` | Le guide, la présentation, le format des fichiers CSV. |
| `Lancer_GMAO.bat`, `lancer.sh` | Les lanceurs (Windows ; Mac et Linux). |
| `Reinitialiser_mot_de_passe.bat` | Donne un mot de passe provisoire à un compte (Windows). |
| `python/` | Python embarqué officiel pour Windows 64 bits : rien à installer sous Windows. |
| `outils-tiers/` | mkcert 1.4.4 pour Windows 64 bits, avec sa licence : il fabrique le certificat de l'atelier. |
| `outils/empreintes-tiers.json` | Empreintes SHA-256 de mkcert, vérifiées par `serveur.py` avant tout lancement. |
| `LICENSE`, `NOTICE` | Licence MIT de Prévo, licences des bibliothèques embarquées. |

Le zip ne contient **pas** de dossier `donnees/` : `serveur.py` le crée au premier lancement. Une mise à jour ne
touche donc jamais aux données. Il ne contient pas non plus ce document (`docs/` reste dans le dépôt).

Au fil de l'usage, Prévo crée à côté de `serveur.py` :

- `prevo.config.json` : la configuration (§4), écrite par l'assistant ;
- `Installer_demarrage.ps1`, `Retirer_demarrage.ps1`, `Demarrage_session.ps1` (Windows), `prevo.service` (Linux) ou
  `pro.prevo.serveur.plist` (macOS) : les scripts de démarrage (§8), écrits avant d'être lancés, pour que vous
  puissiez les lire ;
- `donnees/` : les 24 fichiers CSV, `documents/` (photos, PDF, rapports figés), `sauvegardes/`, `acces/` (comptes,
  appareils, journal des connexions, certificat de l'atelier), `journal-serveur.log`, `copie-externe.json`, et
  `installation.json` pendant l'assistant.

## 2. Les portées : qui peut joindre Prévo

Une seule règle : **au-delà de ce PC, comptes et https sont obligatoires.** `serveur.py` la vérifie au démarrage,
avant d'ouvrir le moindre port. Si la configuration ne la respecte pas, il refuse de démarrer, dit pourquoi sur la
console et dans `donnees/journal-serveur.log`, et sort avec le code 2. Aucune option ne la contourne.

| Portée | Écoute | Comptes | https | Mandataire |
| --- | --- | --- | --- | --- |
| Ce PC (défaut) | `127.0.0.1` | non (profils, comme en 1.2) | non | non |
| Le Wi-Fi de l'atelier | toutes les interfaces | oui | certificat de l'atelier (§6) | non |
| Aussi hors de l'atelier | toutes les interfaces | oui | certificat de l'atelier | oui, `tailscale serve` (§7.2) |
| Intranet, derrière un mandataire | `127.0.0.1` | oui | porté par le mandataire | oui (§7) |

Les trois parcours de l'assistant :

- **Solo** : un PC, une personne. Portée « ce PC », sans compte ni https. Pour un téléphone, Tailscale, et un
  mot de passe devient obligatoire.
- **Atelier** : une petite équipe sur le Wi-Fi. Comptes pour le responsable et les techniciens, téléphones des
  demandeurs enrôlés par QR, certificat fabriqué par Prévo, démarrage avec le PC.
- **Intranet** : vous installez Prévo derrière le mandataire inverse ou le VPN de l'entreprise, avec votre propre
  certificat ; chaque personne a un compte, demandeurs compris.

## 3. Installer

### 3.1 Windows

1. Dézippez le zip dans `C:\Prevo` (conseillé : chemin court, hors du profil d'utilisateur ; le dossier
   `C:\Prevo\prevo-<version>` obtenu convient tel quel). Ailleurs, l'assistant propose de copier Prévo dans
   `C:\Prevo` : chaque fichier est copié puis vérifié, l'ancien dossier n'est jamais supprimé.
2. Double-cliquez sur `Lancer_GMAO.bat`. Il utilise `python\python.exe` du zip, sinon un Python 3.11 ou plus
   récent déjà installé (`py -3` ou `python`).
3. Le navigateur du PC s'ouvre sur l'assistant (`http://localhost:8080/#/installation`). Choisissez « Je suis
   l'informaticien de l'entreprise » : toutes les étapes s'affichent sur une page, rien ne se fait sans clic.

Tant que l'installation n'est pas terminée, Prévo n'écoute que sur ce PC. Rien n'est écrit dans
`prevo.config.json` avant « Terminer » ; Prévo se relance alors avec la configuration.

### 3.2 Linux ou macOS

Il faut Python 3.11 ou plus récent (bibliothèque standard seulement). Le zip n'embarque ni Python ni mkcert pour
ces systèmes.

```sh
sudo mkdir -p /opt/prevo
sudo cp -r prevo-<version>/. /opt/prevo/
cd /opt/prevo && ./lancer.sh --sans-navigateur
```

- Prévo n'est sous `/opt/prevo` qu'à titre d'exemple. Évitez un dossier personnel : l'unité systemd de §8.2
  protège les dossiers personnels (`ProtectHome=yes`).
- Pour le certificat de l'atelier (§6), placez le mkcert de votre système dans `outils-tiers/`, sous le nom de la
  page des releases de mkcert (`mkcert-v1.4.4-linux-amd64`, `mkcert-v1.4.4-linux-arm64`,
  `mkcert-v1.4.4-darwin-arm64`…), et rendez-le exécutable (`chmod +x`). Prévo compare son empreinte à
  `outils/empreintes-tiers.json` et refuse un fichier différent. Sans mkcert, donnez vos propres fichiers PEM ou
  passez par un mandataire.

### 3.3 Un serveur sans écran

L'assistant ne répond qu'à ce PC lui-même (`127.0.0.1`) : vu du réseau, ses adresses n'existent pas (404).
Sur un serveur sans navigateur, ouvrez un tunnel SSH depuis votre poste :

```sh
ssh -L 8080:127.0.0.1:8080 vous@serveur
```

puis ouvrez `http://localhost:8080/#/installation` sur votre poste : pour Prévo, la demande vient de
`127.0.0.1`.

## 4. La configuration : `prevo.config.json`

### 4.1 Où, quand, dans quel ordre

- **Où** : à côté de `serveur.py` (ou le fichier donné par `--config`). Jamais dans `donnees/` : il n'est ni
  sauvegardé ni exporté par Prévo. Sauvegardez-le vous-même, et protégez-le s'il contient `ia_cle`.
- **Qui l'écrit** : l'assistant, à « Terminer » ; puis Paramètres › Accès et installation (depuis le PC serveur),
  clé par clé. Les clés inconnues et `_aide` sont gardées telles quelles. Vous pouvez aussi l'éditer à la main.
- **Format** : JSON en UTF-8. Les clés qui commencent par `_` sont des commentaires (`_aide`).
- **Priorité** : les défauts, puis le fichier, puis la ligne de commande (§5), qui l'emporte.
- **Quand** : le fichier est lu au démarrage seulement. Après une modification, relancez Prévo.
- **Erreurs** : une clé inconnue est ignorée et signalée sur la console ; une valeur invalide arrête le démarrage
  (code 2), avec le nom de la clé.
- **Liste à jour** : `serveur.py --aide` imprime chaque clé, son type, son défaut et son aide.

**Le premier compte.** Avec `"comptes": true` écrit à la main et aucun compte responsable encore créé, Prévo
n'écoute que sur ce PC, n'ouvre aucune session et garde l'assistant joignable **depuis ce PC seulement** : la
console donne son adresse (`http://localhost:8080/#/installation`), et le navigateur du PC serveur l'ouvre de
lui-même. Créez-y le compte (étape « Votre compte ») ; dès qu'il existe, l'assistant n'est plus joignable que par
une session du responsable (Paramètres › Accès et installation).

### 4.2 Toutes les clés

Recopie fidèle de `serveur.py --aide` (le défaut est écrit comme dans le fichier JSON) :

<!-- cles-configuration:debut -->
| Clé | Type | Défaut | Effet |
| --- | --- | --- | --- |
| `portee` | un parmi ce-pc, atelier, dehors | `"ce-pc"` | D'où Prévo peut être ouvert : ce PC seulement, le Wi-Fi de l'atelier, ou aussi hors de l'atelier. Au-delà de ce PC, mot de passe et https sont obligatoires. |
| `ecoute` | un parmi 127.0.0.1, 0.0.0.0 | `"127.0.0.1"` | Adresse d'écoute : 127.0.0.1 (ce PC seulement) ou 0.0.0.0 (le réseau). |
| `port_http` | entier | `8080` | Port de l'application sur ce PC et de la porte d'entrée sur le réseau. Changer de port rend les étiquettes imprimées caduques. |
| `port_https` | entier | `8443` | Port de l'application en https sur le réseau. |
| `noms` | liste | `[]` | Noms par lesquels on appelle ce PC, en plus de son adresse et de son nom Windows (nom Tailscale, nom du réseau de l'entreprise). Un nom inconnu est refusé, par sécurité. |
| `certificat` | texte | `""` | Certificat https du serveur (fichier PEM), avec sa clé. |
| `cle` | texte | `""` | Clé privée du certificat (fichier PEM). |
| `certificat_auto` | booleen | `true` | Certificat fabriqué par Prévo pour l'atelier, à faire reconnaître une fois par appareil. |
| `mandataire` | booleen | `false` | Prévo est derrière un mandataire (tailscale serve, Caddy, nginx, IIS) qui porte le https : les en-têtes X-Forwarded-Proto et X-Forwarded-Host venus de ce PC sont crus. |
| `comptes` | booleen | `false` | Connexion obligatoire : chaque personne a son compte, ou son appareil enrôlé pour les demandeurs. |
| `demandeurs_avec_compte` | booleen | `false` | Non : un demandeur donne son nom sur un appareil enrôlé par QR. Oui : chaque demandeur a un mot de passe. |
| `session_heures` | entier | `12` | Au bout de ce temps sans activité, il faut se reconnecter. |
| `session_longue_jours` | entier | `30` | Durée de « rester connecté sur cet appareil ». |
| `invitation_heures` | entier | `24` | Durée de validité d'une invitation d'appareils (1 à 168 heures). |
| `demarrage` | un parmi aucun, systeme, session | `"aucun"` | Prévo démarre avec le PC (systeme), à l'ouverture de session (session), ou à la main (aucun). |
| `veille_desactivee` | booleen | `false` | Le PC ne se met plus en veille quand il est sur secteur. |
| `copie_sauvegardes` | texte | `""` | Dossier où la sauvegarde du jour est copiée chaque nuit (clé USB, NAS, dossier synchronisé) ; vide : aucune copie. |
| `quota_documents_mo` | entier | `2048` | Place maximale des documents joints, en mégaoctets. |
| `ia_fournisseur` | un parmi ollama, openai | `"ollama"` | Type du service d'IA : ollama (Ollama) ou openai (toute API compatible OpenAI : LM Studio, Mistral…). |
| `ia_url` | texte | `"http://localhost:11434"` | Adresse du service d'IA que tous les postes utilisent. Réglée ici seulement, jamais sur un téléphone. |
| `ia_cle` | texte | `""` | Clé du service d'IA, gardée sur ce PC, jamais envoyée aux navigateurs. La variable d'environnement PREVO_IA_CLE passe avant ; jamais en ligne de commande. |
| `ia_en_ligne` | booleen | `false` | Autoriser un service d'IA en ligne : les textes envoyés partent chez ce fournisseur. |
<!-- cles-configuration:fin -->

Précisions :

- **Ce qui compte au démarrage** : `ecoute`, `comptes`, `certificat` et `cle` (ou `certificat_auto`) et
  `mandataire`. `portee` résume ces choix pour l'assistant et Paramètres. `demarrage` et `veille_desactivee` notent
  ce qui a été installé : changer ces deux clés à la main n'installe ni ne retire rien (§8).
- **Bornes des entiers** : `port_http` : 1 à 65535 ; `port_https` : 1 à 65535 ; `session_heures` : 1 à 720 ;
  `session_longue_jours` : 1 à 365 ; `invitation_heures` : 1 à 168 ; `quota_documents_mo` : 1 à 1048576.
- **Ports** : si un port est pris, Prévo prend le suivant libre (jusqu'à 20 plus loin) et le dit sur la console.
  Derrière un mandataire ou un pare-feu réglé sur un port précis, choisissez un port libre.
- **`noms`** : en minuscules ; l'en-tête `Host` (et `X-Forwarded-Host` derrière un mandataire) doit être une
  adresse IP, `localhost`, le nom du PC ou l'un de ces noms. Sinon, refus (403).
- **`copie_sauvegardes`** : un chemin relatif part du dossier de Prévo. Le dossier doit exister et ne pas être
  rangé dans `donnees/`.
- **IA** : la clé du service ne passe jamais par l'écran ni par la ligne de commande (elle serait visible dans la
  liste des processus). Mettez-la dans `ia_cle` (fichier protégé) ou dans la variable d'environnement
  `PREVO_IA_CLE` du compte qui lance Prévo.

### 4.3 Exemples

Atelier (ce que l'assistant écrit, réduit aux clés qui changent) :

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

Intranet derrière un mandataire sur le même serveur (§7) :

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

Intranet sans mandataire, avec le certificat de l'entreprise (la porte reste en http sur `port_http` et conduit les
navigateurs à l'application en https sur `port_https`) :

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

## 5. Ligne de commande

`serveur.py` (Windows : `python\python.exe serveur.py` ; ailleurs : `python3 serveur.py`). Les lanceurs
`Lancer_GMAO.bat` et `lancer.sh` transmettent ces options.

| Option | Effet |
| --- | --- |
| `--port PORT` | Remplace `port_http`. |
| `--ecoute 127.0.0.1` ou `--ecoute 0.0.0.0` | Remplace `ecoute` (les règles de §2 restent vérifiées). |
| `--hote NOM` | Ajoute un nom à `noms` (répétable). |
| `--certificat FICHIER --cle FICHIER` | Remplacent `certificat` et `cle` (fichiers PEM, toujours ensemble). |
| `--ia-url URL`, `--ia-fournisseur ollama\|openai`, `--ia-en-ligne` | Remplacent `ia_url`, `ia_fournisseur`, `ia_en_ligne`. Jamais la clé. |
| `--config FICHIER` | Autre fichier de configuration que `prevo.config.json` à côté de `serveur.py`. |
| `--donnees DOSSIER` | Autre dossier de données que `donnees/` à côté de `serveur.py`. |
| `--sans-navigateur` | N'ouvre pas le navigateur au démarrage (service, serveur sans écran). |
| `--journal` | Écrit aussi la console dans `donnees/journal-serveur.log` (automatique sans console). |
| `--aide` | Imprime chaque clé de la configuration avec son aide, puis s'arrête. |
| `--reinitialiser IDENTIFIANT` | Donne un mot de passe provisoire à un compte (§9), puis s'arrête. |
| `--servir-tests` | Pour les tests automatiques seulement ; inutile en usage normal. |

Le démarrage automatique (§8) lance `serveur.py --sans-navigateur` sans autre option : gardez les données dans
`donnees/` à côté de `serveur.py`, ou ajoutez vous-même l'option à la tâche ou au service.

## 6. Porte d'entrée et certificat de l'atelier

Hors de la portée « ce PC », Prévo ouvre deux ports :

- **la porte**, en http sur `port_http` (8080) : c'est la seule adresse que Prévo donne (QR de l'accueil,
  étiquettes, fiche d'accès). Elle ne sert que sa page, ses illustrations et `/acces/ca.crt` ; elle ne lit jamais
  de donnée. Un navigateur qui fait déjà confiance au PC est conduit aussitôt en https, sur la même page ; sinon, la
  page « Faites confiance au PC atelier » guide l'installation du certificat (Android, iPhone) ;
- **l'application**, en https sur `port_https` (8443). Cette adresse n'est jamais à taper.

Le certificat se règle de trois façons :

1. **Fabriqué par Prévo** (`certificat_auto`, le défaut) : mkcert, piloté par Prévo, crée une autorité propre à
   l'atelier dans `donnees/acces/autorite/` (`rootCA.pem`, que la porte sert sous le nom `prevo-ca.crt`) et le
   certificat du serveur dans `donnees/acces/certificat.pem` et `cle.pem`, pour l'adresse IP, le nom du PC,
   `<nom>.local`, `localhost`, `127.0.0.1` et les `noms`. Il est refait au démarrage si l'adresse ou les noms
   changent ; les téléphones n'ont rien à refaire. Chaque appareil fait confiance à l'autorité une fois. Ne
   diffusez jamais `rootCA-key.pem` : avec lui, on fabrique des certificats que vos appareils croiraient. Prévo ne
   le lit ni ne le sert.
2. **Vos fichiers PEM** (`certificat` et `cle`, ou `--certificat` et `--cle`) : un certificat de l'entreprise,
   reconnu par vos appareils. Rien à faire sur les téléphones.
3. **Un mandataire** (§7) porte le https ; Prévo reste en http sur `127.0.0.1`.

Sans certificat valable hors de « ce PC », Prévo refuse de démarrer (code 2).

Prévo pose ses propres en-têtes de sécurité (`Content-Security-Policy`, `X-Frame-Options`, `Referrer-Policy`,
`Permissions-Policy`) et `Strict-Transport-Security` (180 jours) pour un nom de `noms` servi en https. Un
mandataire ne doit pas les remplacer.

## 7. Derrière un mandataire inverse

### 7.1 Les règles

- Le mandataire tourne **sur le même serveur** que Prévo et le joint en http sur `127.0.0.1:<port_http>`. Prévo
  ne croit les en-têtes `X-Forwarded-*` que d'une connexion venue de `127.0.0.1` ou `::1`, et seulement avec
  `"mandataire": true`. Un mandataire installé sur une autre machine n'est pas reconnu : installez un relais local
  (Caddy, nginx) sur le serveur de Prévo.
- Le mandataire pose **`X-Forwarded-Proto`** (`https`) et **`X-Forwarded-Host`** (le nom public). Sans eux, la
  requête est traitée comme venue de ce PC : cookie sans `Secure`, adresses et QR faux. `X-Forwarded-For` donne
  l'adresse de la personne au journal des connexions (Prévo prend la dernière adresse de la liste).
- Le nom public est dans **`noms`**, sinon Prévo répond 403 « Nom d'hôte d'origine refusé (X-Forwarded-Host) ».
- **`"comptes": true`** est obligatoire avec `"mandataire": true`.
- Laissez passer des requêtes de **50 Mo** (enregistrement d'une table entière, par exemple `ordres_travail.csv` d'une
  grosse base ; un document ou une photo : 10 Mo au plus) et des réponses qui tardent jusqu'à
  **120 secondes** (relais de l'IA). Prévo n'utilise pas de WebSocket.
- Exposer Prévo sur Internet ne se fait que derrière Tailscale, le VPN de l'entreprise ou un mandataire en https.
  Prévo n'a pas de double facteur : mettez de préférence votre propre contrôle d'accès devant.

Configuration de Prévo pour tous les exemples ci-dessous (avec le nom de votre choix) :

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

### 7.2 `tailscale serve` (hors de l'atelier)

L'assistant le règle lui-même (étape « Hors de l'atelier »). À la main, sur le serveur connecté à votre réseau
Tailscale :

```sh
tailscale serve --bg --https=443 http://127.0.0.1:8080
tailscale serve status
```

Dans `prevo.config.json` : le nom Tailscale du PC dans `noms` (par exemple `pc-atelier.tail1234.ts.net`) et
`"mandataire": true`. `tailscale serve` porte le https avec un certificat reconnu partout, pose `X-Forwarded-Proto`,
`X-Forwarded-Host`, `X-Forwarded-For` et `Tailscale-User-Login` : le journal des connexions note le compte Tailscale
de chaque session. Sous Windows, `tailscale set --unattended=true` le fait tourner sans session ouverte.
Désactivez l'expiration de clé du serveur dans la console Tailscale.

En portée « aussi hors de l'atelier », Prévo écoute en plus le réseau de l'atelier avec son certificat
(`"ecoute": "0.0.0.0"`, `"certificat_auto": true`) : les deux accès coexistent.

### 7.3 Caddy

```caddyfile
prevo.entreprise.example {
	# Certificat de l'entreprise ; sans cette ligne, Caddy en demande un à Let's Encrypt
	# (le nom doit alors être joignable depuis Internet).
	tls /etc/prevo/certificat.pem /etc/prevo/cle.pem

	# Caddy pose lui-même X-Forwarded-Proto, X-Forwarded-Host et X-Forwarded-For.
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

    client_max_body_size 52m;      # Prévo accepte 50 Mo pour une table, 10 Mo pour un document
    proxy_read_timeout   180s;     # le relais de l'IA peut répondre en 120 s

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

### 7.5 IIS (URL Rewrite et ARR)

1. Installez les modules **URL Rewrite** et **Application Request Routing** (ARR) de Microsoft.
2. Gestionnaire IIS, nœud du serveur, « Application Request Routing Cache », « Server Proxy Settings » : cochez
   « Enable proxy », mettez le délai (« Time-out ») à 180 secondes et décochez « Include TCP port from client IP »
   (sinon `X-Forwarded-For` porte un port et Prévo ne lit pas l'adresse).
3. URL Rewrite, « View Server Variables » : ajoutez `HTTP_X_FORWARDED_PROTO` et `HTTP_X_FORWARDED_HOST`.
4. Créez un site lié en https à `prevo.entreprise.example` avec le certificat de l'entreprise, et mettez dans son
   dossier ce `web.config` :

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
        <!-- 50 Mo par table (IIS refuse au-delà d'environ 30 Mo par défaut) -->
        <requestLimits maxAllowedContentLength="54525952" />
      </requestFiltering>
    </security>
  </system.webServer>
</configuration>
```

### 7.6 Cloudflare Tunnel

Cloudflare Tunnel rend Prévo joignable depuis Internet sans ouvrir de port : réservez-le à une entreprise qui
l'utilise déjà, avec Cloudflare Access devant Prévo. Cloudflare déchiffre le trafic : c'est un sous-traitant, à
inscrire au registre des traitements. Cloudflare coupe une réponse qui tarde plus de 100 secondes : une réponse
d'IA très lente peut échouer.

Pour que Prévo reçoive sûrement `X-Forwarded-Proto` et `X-Forwarded-Host`, `cloudflared` passe par un petit relais
Caddy sur le même serveur :

```yaml
# Configuration de cloudflared (config.yml)
tunnel: ID-DU-TUNNEL
credentials-file: /etc/cloudflared/ID-DU-TUNNEL.json
ingress:
  - hostname: prevo.entreprise.example
    service: http://127.0.0.1:8081
  - service: http_status:404
```

```caddyfile
# Relais local : reçoit cloudflared sur 127.0.0.1:8081, pose les en-têtes, transmet à Prévo
http://:8081 {
	bind 127.0.0.1
	reverse_proxy 127.0.0.1:8080 {
		header_up X-Forwarded-Proto https
		header_up X-Forwarded-Host prevo.entreprise.example
		header_up X-Forwarded-For {http.request.header.Cf-Connecting-Ip}
	}
}
```

### 7.7 Vérifier

- `curl https://prevo.entreprise.example/api/ping` répond `{"application": "Prévo", …}`. Une réponse 403 « Nom
  d'hôte d'origine refusé » : le nom manque dans `noms`.
- Connectez-vous : sur l'accueil du responsable, la carte « Connecter un téléphone » donne
  `https://prevo.entreprise.example/` ; dans les outils du navigateur, le cookie `id` porte `Secure`.
- Équipe › Accès › Journal des connexions : la colonne « adresse » montre l'adresse de la personne, pas
  `127.0.0.1`.

## 8. Démarrer avec la machine

### 8.1 Windows

L'assistant (étape « Démarrage ») écrit `Installer_demarrage.ps1` dans le dossier de Prévo, l'affiche, puis le
lance avec une seule invite d'administrateur. Le script :

- crée la tâche planifiée **`Prevo`** : au démarrage du PC, 30 secondes après, sous le compte Système, sans
  fenêtre (`python\pythonw.exe serveur.py --sans-navigateur`) ;
- ajoute la règle de pare-feu entrante **`Prevo`** : profil privé, sous-réseau local, `pythonw.exe`, ports
  `port_http` et `port_https` ;
- fait reconnaître l'autorité de l'atelier par Windows (`mkcert -install`) quand Prévo fabrique le certificat ;
- si `veille_desactivee` : pas de veille ni de veille prolongée sur secteur (écran éteint après 15 minutes), et
  garde les réglages d'avant dans `donnees\acces\veille-avant.json`.

Si l'invite d'administrateur est refusée, rien n'est installé ; `Demarrage_session.ps1` propose un repli sans
droits : une tâche à l'ouverture de session de l'utilisateur (sinon `Prevo.cmd` dans son dossier Démarrage).

**Retirer** : Paramètres › Accès et installation (démarrage « à la main »), ou `Retirer_demarrage.ps1` en
administrateur (clic droit, « Exécuter avec PowerShell ») : la tâche et la règle sont retirées, la veille remise
comme avant.

Commandes utiles (invite d'administrateur) : `schtasks /run /tn Prevo`, `schtasks /end /tn Prevo`,
`schtasks /query /tn Prevo /v`.

### 8.2 Linux (systemd)

L'assistant écrit `prevo.service` à côté de `serveur.py` et donne les commandes. Exemple pour `/opt/prevo` :

```ini
# /etc/systemd/system/prevo.service : écrit par Prévo (ARCHITECTURE.md §22.9).
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

Sous systemd, la console va dans le journal du système (`journalctl -u prevo`). Ajoutez `--journal` à
`ExecStart` pour avoir aussi `donnees/journal-serveur.log`, que Paramètres › Accès et installation affiche.
Ouvrez au réseau local `port_http` et `port_https` seulement, par exemple
`sudo ufw allow from 192.168.1.0/24 to any port 8080,8443 proto tcp`. Retirer :
`sudo systemctl disable --now prevo`.

### 8.3 macOS

L'assistant écrit `pro.prevo.serveur.plist` (agent de lancement, `RunAtLoad`, `KeepAlive`) et la commande
`launchctl load -w <chemin du fichier>` ; retrait : `launchctl unload -w <chemin du fichier>`.

### 8.4 Sans console

Lancé sans console (tâche planifiée, `pythonw.exe`), Prévo écrit ce qu'il fait dans `donnees/journal-serveur.log`
(5 fichiers de 1 Mo au plus). Paramètres › Accès et installation en montre les 20 dernières lignes.

## 9. Comptes, rôles et appareils

- **Comptes** : identifiant de la forme `prenom.nom`. Le premier responsable est créé par l'assistant ; les autres
  comptes par le responsable, dans Équipe › Accès (créer, modifier, réinitialiser, désactiver, activer). Il reste
  toujours au moins un responsable actif.
- **Mots de passe** : 12 à 256 caractères, aucune règle de composition (une phrase de passe est conseillée).
  Seule une empreinte salée est gardée (scrypt ; PBKDF2 si le Python n'a pas scrypt), dans
  `donnees/acces/comptes.json`. Un mot de passe provisoire
  s'affiche une seule fois et doit être changé à la première connexion.
- **Échecs** : même message dans tous les cas ; attente croissante dès le 5e échec de suite, compte bloqué
  15 minutes au 10e ; une adresse qui dépasse 20 échecs par heure est ralentie.
- **Sessions** : 12 heures sans activité (`session_heures`) ; 30 jours avec « Rester connecté sur cet appareil »
  (`session_longue_jours`). Cookie `HttpOnly`, `SameSite=Lax`, `Secure` en https. Un mot de passe changé ferme les
  autres sessions du compte ; un mot de passe réinitialisé ou un compte désactivé les ferme toutes.
- **Mot de passe oublié** : aucun courriel. Sur le PC serveur, `Reinitialiser_mot_de_passe.bat` demande
  l'identifiant et affiche un mot de passe provisoire. Ailleurs : `python3 serveur.py --reinitialiser prenom.nom`,
  lancé dans le dossier de Prévo par le compte qui fait tourner Prévo (Linux :
  `sudo -u prevo python3 /opt/prevo/serveur.py --reinitialiser prenom.nom`). Inutile d'arrêter Prévo. Qui a la
  main sur le serveur a la main sur Prévo.
- **Désactiver** : Équipe › Accès, « Désactiver ». Le compte reste dans la liste (historique) et ne se connecte
  plus ; ses sessions sont fermées aussitôt.
- **Rôles** : demandeur, technicien, responsable, vérifiés par le serveur à chaque requête. Un demandeur ne lit ni
  les coûts, ni les techniciens, ni les ordres de travail, et n'ajoute que des demandes ; un technicien ne voit ni
  taux horaire ni prix. L'IA est réservée aux techniciens et au responsable. Table complète :
  [ARCHITECTURE.md](ARCHITECTURE.md) §22.5.
- **Appareils des demandeurs** : sans mot de passe, par invitation (Équipe › Accès › Appareils, QR valable 1 heure
  à 7 jours, `invitation_heures`) ; le téléphone donne un nom et reste reconnu un an, avec les droits du demandeur ;
  « Révoquer » le coupe dès sa requête suivante. Avec `"demandeurs_avec_compte": true`, l'enrôlement est désactivé
  et chaque demandeur a un compte.
- **Dossier `donnees/acces/`** : `comptes.json`, `sessions.json` (empreintes des jetons), `appareils.json`,
  `journal-acces.csv`, le certificat et l'autorité de l'atelier. Écrit par le serveur seul : ne le modifiez pas à
  la main, ne le servez pas, ne le joignez jamais à un signalement.

## 10. Journaux

| Journal | Où | Durée | Contenu |
| --- | --- | --- | --- |
| Connexions | `donnees/acces/journal-acces.csv` | un an, purgé chaque jour | `date;qui;adresse;agent;resultat;tailscale` : connexions, échecs, blocages, déconnexions, invitations, appareils, révocations, comptes créés, modifiés ou réinitialisés |
| Modifications | `donnees/journal.csv` | sans limite | qui a changé quoi dans les données (l'historique de la maintenance) |
| Serveur | `donnees/journal-serveur.log` | 5 fichiers de 1 Mo | démarrage, refus, copie externe, erreurs (sans console, ou avec `--journal`) |

Le journal des connexions s'exporte en CSV depuis Équipe › Accès › Journal des connexions (« Exporter (CSV) »).
Jamais un mot de passe ni un jeton n'y est écrit.

## 11. Sauvegardes et restauration

Ce que Prévo fait tout seul (mode serveur) :

- **Chaque jour**, avant la première modification : `donnees/sauvegardes/AAAA-MM-JJ/`, avec les 24 fichiers CSV et
  les fichiers de `donnees/acces/` **sauf `sessions.json`** (une session ne se restaure jamais) **et `cle.pem`** (la
  clé privée du certificat de l'atelier ne quitte pas le PC ; Prévo la refabrique au démarrage si elle manque).
- **Avant un import, une restauration ou un changement de format** : une sauvegarde complète dont le nom le dit
  (`…_avant-import`, `…_avant-restauration`, `…_avant-format-vN`).
- **Copie externe** (`copie_sauvegardes`) : au démarrage et chaque nuit, à la première modification après 2 h du
  matin, la sauvegarde du jour est copiée dans `<dossier>/AAAA-MM-JJ/` ; 30 copies gardées. Un échec est noté dans
  `journal-serveur.log` et affiché sur l'accueil du responsable.
- **Sauvegardes manuelles** : une par minute au plus, les 60 plus récentes gardées.

Ce qui n'est **pas** dans ces sauvegardes, à sauvegarder avec vos outils :

- `documents/` (photos, PDF, rapports figés) : seul « Exporter en ZIP » (Paramètres) les emporte ;
- `prevo.config.json` ;
- `donnees/acces/autorite/` : sans elle, une autorité neuve est créée et chaque téléphone doit refaire confiance
  au PC atelier ;
- `journal-serveur.log`.

La copie externe contient `comptes.json` (empreintes des mots de passe, jamais les mots de passe) : protégez son
dossier comme le serveur.

**Tester** (Paramètres › Sauvegardes, « Tester ») relit chaque table d'une sauvegarde et compte ses lignes, sans
rien écrire. **Restaurer…** remet toutes les tables ou une seule, après une copie de sécurité de l'état actuel.
La restauration ne touche jamais `donnees/acces/` : un compte désactivé ne revient pas avec une vieille
sauvegarde. Pour remettre les comptes après la perte du serveur, arrêtez Prévo et recopiez à la main les fichiers
du dossier `acces/` d'une sauvegarde dans `donnees/acces/`.

## 12. Mise à jour et retour arrière

**Mettre à jour** :

1. Lisez le `CHANGELOG.md` de la nouvelle version.
2. Paramètres › Sauvegardes, « Sauvegarder maintenant », puis copiez `donnees/` et `prevo.config.json` ailleurs.
3. Arrêtez Prévo : fermez la fenêtre noire, ou `schtasks /end /tn Prevo`, ou `sudo systemctl stop prevo`.
4. Copiez le contenu du dossier `prevo-<version>/` du nouveau zip par-dessus le dossier de Prévo, en remplaçant
   les fichiers. Le zip n'a ni `donnees/` ni `prevo.config.json` : ils restent tels quels. Sous Linux, refaites
   `sudo chown -R prevo:prevo /opt/prevo`.
5. Relancez Prévo. Si le format des fichiers change, Prévo fait d'abord une sauvegarde `…_avant-format-vN`.

Depuis Prévo 1.2 : même procédure. L'assistant s'ouvre et voit les fichiers CSV existants : il n'en remplace aucun
(en Solo, il ajoute seulement le technicien « moi » et les réglages du mode Solo). Les profils mémorisés sur les
postes sont remplacés par les comptes.

**Revenir en arrière** : gardez le zip de la version précédente. Arrêtez Prévo, remettez ses fichiers par-dessus,
relancez. Si la mise à jour avait changé le format des fichiers, remettez aussi les CSV de la sauvegarde
`…_avant-format-vN` dans `donnees/` (Prévo arrêté) : les modifications faites depuis sont perdues. Revenir à
Prévo 1.2, c'est revenir à un serveur sans comptes ni porte d'entrée, qui répond à tout appareil du réseau local
sans mot de passe : ne le faites que le temps d'un dépannage.

## 13. Annuaire de l'entreprise

Prévo ne se branche pas sur un annuaire (Active Directory, LDAP, Entra ID, Google Workspace) : pas de connexion
unique, pas de synchronisation des comptes. C'est un choix : Prévo doit rester installable par un atelier sans
informaticien. Ce qui existe :

- des **comptes locaux**, créés par le responsable ou par vous (un par salarié, demandeurs compris avec
  `"demandeurs_avec_compte": true`) ;
- l'**export du journal des connexions**, pour votre suivi ;
- le **mandataire inverse et le VPN de l'entreprise**, pour placer Prévo derrière vos propres contrôles d'accès
  (par exemple une authentification sur le mandataire, avant la page de connexion de Prévo).

## 14. Données personnelles (RGPD)

Toutes les données restent sur le serveur, dans `donnees/` ; les mots de passe n'y sont qu'en empreinte, le journal
des connexions est gardé un an, et l'IA (désactivée par défaut) n'envoie rien sans la décision du responsable sur
le serveur. Le détail pour votre registre des traitements est dans [GUIDE.html](../GUIDE.html), chapitre 8.9 « Vos
données et le RGPD ».

## 15. Désinstaller

1. Gardez les données : copiez `donnees/` et `prevo.config.json` ailleurs (ou « Exporter en ZIP »).
2. Retirez le démarrage : Paramètres › Accès et installation, ou `Retirer_demarrage.ps1` en administrateur ;
   supprimez aussi `Prevo.cmd` du dossier Démarrage si le repli sans droits a servi. Linux :
   `sudo systemctl disable --now prevo`, puis `sudo rm /etc/systemd/system/prevo.service`. macOS :
   `launchctl unload -w <chemin du fichier plist>`.
3. Retirez l'autorité de l'atelier de Windows (PowerShell en administrateur) :

   ```powershell
   $env:CAROOT = 'C:\Prevo\donnees\acces\autorite'
   & 'C:\Prevo\outils-tiers\mkcert-v1.4.4-windows-amd64.exe' -uninstall
   ```

   Sur chaque téléphone, retirez le certificat de l'atelier dans les réglages où il a été installé.
4. Si `tailscale serve` a été réglé : `tailscale serve reset`.
5. Supprimez le dossier de Prévo.
