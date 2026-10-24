# Mettre en ligne la démo de Prévo

Adresse de la démo : **https://demo.prevo.pro**

But : permettre d'essayer Prévo dans le navigateur avant de le télécharger. La démo en ligne est un
**site statique** : une copie de l'application (pages, styles, scripts) que le navigateur du visiteur
fait tourner seul. Les données de démo restent dans la mémoire de son navigateur ; rien n'est
enregistré sur le serveur, rien n'est envoyé ailleurs. L'assistant IA y est visible mais n'appelle
rien : il affiche un message qui renvoie au guide.

> **Ne mettez jamais serveur.py en ligne.** Il n'a aucune authentification : il lit et écrit les
> fichiers de données de l'atelier et n'est fait que pour le réseau local d'une entreprise. Sur le VPS,
> ne le lancez pas, ne le copiez pas, et ne faites pointer nginx vers aucun programme : nginx sert
> uniquement le dossier `dist/demo-web/`, qui ne contient pas serveur.py.

Ce qu'il faut avant de commencer :

- l'accès à l'espace client OVH (zone DNS de `prevo.pro`) ;
- un accès SSH au VPS avec les droits `sudo`, nginx et certbot installés ;
- sur le PC : Python 3 et une copie du dépôt Prévo.

Dans les commandes ci-dessous, remplacez `<IP du VPS>` par l'adresse IPv4 du VPS et `<utilisateur>`
par votre compte SSH. Les chemins nginx (`sites-available`, `sites-enabled`) sont ceux des systèmes
de la famille Debian et Ubuntu ; si votre VPS n'a que `/etc/nginx/conf.d/`, placez-y le fichier de
configuration (nom terminé par `.conf`) et sautez l'étape du lien.

---

## 1. Construire la démo sur le PC

Dans le dossier du dépôt (là où se trouve `index.html`) :

```
py outils/construire_demo_web.py
```

Le script produit `dist/demo-web/` avec **uniquement** `index.html`, `favicon.svg`, `GUIDE.html`,
`css/` et `js/`, et active la version web dans sa copie de `js/app.js` (`const VERSION_WEB = true;`).
Le dépôt lui-même n'est pas modifié. Le dossier `dist/` n'est pas versionné.

Pour une mise en ligne, construisez depuis une **copie propre de l'étiquette** publiée, comme le zip de
la release ([RELEASE.md](RELEASE.md)) : un travail en cours du dossier de travail n'y entre pas.

```
git worktree add ../prevo-v1.1.0 v1.1.0
py ../prevo-v1.1.0/outils/construire_demo_web.py
```

La démo est alors dans `../prevo-v1.1.0/dist/demo-web/` (à copier à l'étape 5) ; supprimez la copie
ensuite par `git worktree remove ../prevo-v1.1.0`.

Vérification rapide sur le PC, avant d'envoyer quoi que ce soit :

```
py -m http.server 8000 --directory dist/demo-web
```

puis ouvrez http://localhost:8000 : l'écran de démarrage ne propose que « Essayer avec les données de
démo » et « Télécharger Prévo ». Arrêtez ensuite ce petit serveur (Ctrl+C) : il ne sert qu'à cette
vérification.

## 2. Enregistrement DNS chez OVH

1. Espace client OVH > **Web Cloud** > **Noms de domaine** > `prevo.pro` > onglet **Zone DNS**.
2. **Ajouter une entrée** > type **A**.
3. Sous-domaine : `demo` ; cible : `<IP du VPS>` ; TTL : laisser la valeur par défaut. Valider.
4. Si le VPS a une adresse IPv6 que nginx écoute, ajoutez de même une entrée **AAAA** (`demo` vers
   l'adresse IPv6). Sinon, n'en mettez pas : une entrée AAAA fausse ferait échouer le certificat.
5. Attendez la propagation (de quelques minutes à quelques heures), puis vérifiez depuis le PC :

```
nslookup demo.prevo.pro
```

La réponse doit donner `<IP du VPS>`. Ne passez à l'étape 4 (certificat) qu'à ce moment-là.

## 3. Site statique nginx sur le VPS

Connectez-vous au VPS (`ssh <utilisateur>@<IP du VPS>`), puis créez le dossier du site, dont vous
serez propriétaire (les copies de l'étape 5 se feront alors sans `sudo`) :

```
sudo mkdir -p /var/www/prevo-demo
sudo chown <utilisateur>: /var/www/prevo-demo
```

Créez le fichier `/etc/nginx/sites-available/prevo-demo` (par exemple avec `sudo nano`) :

```nginx
# Démo en ligne de Prévo : fichiers statiques seulement (jamais serveur.py, aucun programme).
server {
    listen 80;
    listen [::]:80;
    server_name demo.prevo.pro;

    root /var/www/prevo-demo;
    index index.html;
    autoindex off;
    server_tokens off;
    charset utf-8;

    # Revalidés à chaque visite : une mise à jour de la démo est vue tout de suite.
    add_header Cache-Control "no-cache" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "same-origin" always;
    add_header X-Frame-Options "SAMEORIGIN" always;

    # Fichiers cachés (.git, .env…) : jamais servis.
    location ~ /\. {
        deny all;
    }

    # Un fichier du dossier, sinon 404 : pas de programme, pas d'API.
    location / {
        try_files $uri $uri/ =404;
    }
}
```

Activez le site, contrôlez la configuration, puis rechargez nginx :

```
sudo ln -s /etc/nginx/sites-available/prevo-demo /etc/nginx/sites-enabled/prevo-demo
sudo nginx -t
sudo systemctl reload nginx
```

`nginx -t` doit répondre « syntax is ok » et « test is successful » ; sinon, corrigez avant de recharger.

## 4. Certificat Let's Encrypt (certbot)

Une fois le DNS propagé (étape 2) :

```
sudo certbot --nginx -d demo.prevo.pro
```

certbot obtient le certificat, ajoute la partie https au fichier `prevo-demo` et, s'il vous le
demande, choisissez la **redirection** de http vers https. Contrôlez ensuite le renouvellement
automatique :

```
sudo certbot renew --dry-run
```

Le https est aussi utile à la démo elle-même : la dictée vocale n'est proposée par le navigateur que
sur une page sécurisée.

## 5. Copier dist/demo-web/ sur le VPS

Le contenu de `dist/demo-web/` doit arriver **dans** `/var/www/prevo-demo/` (sans sous-dossier
`demo-web`). L'option `--delete` retire du VPS les fichiers qui n'existent plus dans la nouvelle
construction.

**Avec rsync** (Mac, Linux, ou WSL sous Windows), depuis le dossier du dépôt — attention aux deux
barres obliques finales :

```
rsync -av --delete dist/demo-web/ <utilisateur>@<IP du VPS>:/var/www/prevo-demo/
```

**Avec scp** (Windows, PowerShell), en deux temps : envoi dans un dossier temporaire du VPS, puis mise
en place sur le VPS :

```
scp -r dist/demo-web <utilisateur>@<IP du VPS>:/tmp/prevo-demo-nouvelle
ssh <utilisateur>@<IP du VPS> "rsync -a --delete /tmp/prevo-demo-nouvelle/ /var/www/prevo-demo/ && rm -rf /tmp/prevo-demo-nouvelle"
```

(si `rsync` manque sur le VPS : `sudo apt install rsync` sur Debian ou Ubuntu.)

Droits de lecture pour nginx, si besoin :

```
ssh <utilisateur>@<IP du VPS> "chmod -R a+rX /var/www/prevo-demo"
```

## 6. Vérifier

Depuis le PC :

```
curl -I https://demo.prevo.pro/
curl -I http://demo.prevo.pro/
curl -I https://demo.prevo.pro/serveur.py
curl -I https://demo.prevo.pro/api/ping
curl -s https://demo.prevo.pro/js/app.js | findstr VERSION_WEB
```

(sous Mac ou Linux, `grep` à la place de `findstr`.) Attendu, dans l'ordre : `200` ; une redirection
(`301`) vers https ; `404` (serveur.py n'est pas en ligne) ; `404` (aucune API) ;
`const VERSION_WEB = true;`.

Puis dans un navigateur, sur https://demo.prevo.pro :

1. Le cadenas est affiché. L'écran de démarrage ne propose que **« Essayer avec les données de démo »**
   et **« Télécharger Prévo »** (ni dossier, ni dépôt de fichiers CSV, ni mention du mode serveur).
2. « Télécharger Prévo » mène à la dernière release du dépôt GitHub. **Ce lien ne marche pour les
   visiteurs que lorsque le dépôt est public et qu'une release existe** : mettez la démo en ligne
   après le passage en public, ou acceptez que le lien soit en erreur d'ici là.
3. « Essayer avec les données de démo », choisir un profil : l'atelier fictif s'affiche, avec le bandeau
   « Démo — rien n'est enregistré ».
4. Assistant IA : dans « Signaler » (écrire un mot puis « Proposer avec l'IA ») et dans « Ce poste »
   (« Tester la connexion »), le message « L'assistant IA n'est pas proposé dans cette démo en
   ligne… » s'affiche.
5. Outils de développement du navigateur (F12) > onglet **Réseau**, page rechargée : toutes les
   requêtes vont vers `demo.prevo.pro`, et aucune vers `/api/`.

## Mettre à jour la démo

À chaque nouvelle version de Prévo : refaire l'étape 1 (construction) puis l'étape 5 (copie avec
`--delete`). Rien à changer dans nginx ni dans le DNS. Grâce à `Cache-Control: no-cache`, les
visiteurs ont la nouvelle version à leur prochaine visite.

## Retirer la démo

```
sudo rm /etc/nginx/sites-enabled/prevo-demo
sudo nginx -t && sudo systemctl reload nginx
```

puis, si vous le souhaitez : supprimer `/var/www/prevo-demo`, révoquer le certificat
(`sudo certbot delete --cert-name demo.prevo.pro`) et supprimer l'entrée `demo` dans la zone DNS
chez OVH.
