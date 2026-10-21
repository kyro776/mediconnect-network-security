## 7. Portail web, reverse proxy et authentification multifacteur

### 7.1 Besoin et principe

Le portail est le seul service de MediConnect exposé à Internet : les patients y prennent rendez-vous, les médecins y consultent leur agenda. C'est donc la cible la plus probable d'une attaque. Sa protection repose sur trois idées :

1. **un seul point d'entrée** : le reverse proxy, qui termine le HTTPS ; l'application n'est jamais joignable directement ;
2. **des zones séparées** : le portail est en DMZ, la base de données en zone SERVEURS, et chaque flux entre les deux est ouvert individuellement ;
3. **une authentification forte pour les médecins** : mot de passe, puis code à usage unique (TOTP).

Chemin d'une requête :

| Étape | Élément | Adresse |
|---|---|---|
| 1 | Patient ou médecin sur Internet | `203.0.113.100` (poste de test) |
| 2 | Pare-feu du siège : redirection du port 443 | `203.0.113.2` |
| 3 | Reverse proxy Nginx (HTTPS) | `10.1.10.10:443` |
| 4 | Application (gunicorn, HTTP interne) | `10.1.10.20:8000` |
| 5 | Base PostgreSQL, connexion chiffrée | `10.1.30.20:5432` |

### 7.2 Le serveur de la DMZ

`SRV-DMZ` (Debian 13, sans interface graphique) porte deux adresses sur sa carte de la DMZ : `10.1.10.10` (reverse proxy) et `10.1.10.20` (application), conformément au plan d'adressage (section 3). Les deux rôles sont séparés par l'adresse d'écoute : Nginx n'écoute que sur `10.1.10.10`, l'application que sur `10.1.10.20`.

Pour joindre la zone SERVEURS, le serveur passe par le pare-feu (route vers `10.1.30.0/24` via `10.1.10.1`). Cette route impose l'adresse source `10.1.10.20` : la règle du pare-feu n'autorise que le serveur web, et le reverse proxy n'a aucune raison d'interroger la base.

Une carte NAT temporaire sert à installer les logiciels (nginx, python, bibliothèques) ; elle ne fait pas partie de l'architecture (voir 7.9).

![07-01-srv-dmz-installe](../captures/07-01-srv-dmz-installe.png)
*Capture : SRV-DMZ installé*

### 7.3 La base de données

PostgreSQL est installé sur le serveur de la zone SERVEURS, avec sa propre adresse `10.1.30.20` (seconde adresse de la machine qui porte l'annuaire, pour économiser les ressources de la maquette).

**Un compte aux droits minimaux.** L'application ne se connecte pas en administrateur mais avec `portail_app`, qui ne peut que :

| Table | Droits de `portail_app` | Pourquoi |
|---|---|---|
| `medecins` | Lire ; modifier uniquement `totp_secret` et `totp_actif` | Vérifier la connexion, activer le second facteur |
| `rendez_vous` | Lire et ajouter | Prendre et afficher les rendez-vous |
| Toute autre opération | Interdit | Pas de suppression, pas de création de médecin |

Si le portail est compromis, l'attaquant ne peut ni supprimer les rendez-vous ni créer un faux médecin. Les comptes des médecins sont créés par l'administrateur directement dans la base.

**Accès restreint.** PostgreSQL n'écoute que sur `localhost` et `10.1.30.20`. Dans le fichier de contrôle d'accès (`pg_hba.conf`), **une seule ligne** autorise une connexion venant d'une autre machine : connexion chiffrée (`hostssl`), base `mediconnect`, compte `portail_app`, depuis `10.1.10.20/32`, avec authentification `scram-sha-256`. Toute autre machine est refusée, y compris le reverse proxy.

**Mots de passe.**
- Le mot de passe de `portail_app` est généré aléatoirement à l'installation et copié d'un serveur à l'autre par `scp`, sans passer par le presse-papiers (une première tentative par copier-coller avait échoué).
- Les mots de passe des médecins ne sont jamais stockés : seule leur empreinte (algorithme scrypt) l'est. Ils sont saisis sans affichage, hachés sur SRV-DMZ, et seul le fichier d'empreintes est transféré puis détruit.

![07-03-connexion-base-chiffree](../captures/07-03-connexion-base-chiffree.png)
*Capture : connexion du compte applicatif à la base, chiffrée (`ssl = t`)*

![07-04-comptes-medecins](../captures/07-04-comptes-medecins.png)
*Capture : comptes des médecins, second facteur non encore activé*

### 7.4 L'application

L'application (Python, Flask, servie par gunicorn) tourne sous un compte système dédié, sans droits, avec un service systemd durci : système de fichiers en lecture seule, dossiers personnels invisibles, interdiction d'obtenir de nouveaux privilèges, dossier temporaire privé. Sa configuration (clé de session aléatoire, accès à la base) est dans un fichier lisible par ce seul compte.

| Menace | Mesure |
|---|---|
| Injection SQL | Requêtes paramétrées : aucune saisie n'est insérée dans le texte SQL |
| Requête forgée depuis un autre site (CSRF) | Jeton secret par session, vérifié sur chaque formulaire |
| Vol de cookie | Cookie `Secure` (HTTPS uniquement), `HttpOnly` (invisible du JavaScript), `SameSite=Strict` |
| Fixation de session | Nouvelle session après chaque étape d'authentification |
| Session abandonnée | Expiration au bout de 30 minutes, déconnexion explicite |
| Recherche des comptes existants | Message identique pour un identifiant inconnu ou un mauvais mot de passe, et vérification du mot de passe effectuée dans les deux cas |
| Devinette du code à usage unique | 5 essais, puis retour à la page de connexion |
| Mise en cache de pages médicales | En-tête `Cache-Control: no-store` sur l'espace médecin |
| Saisies invalides ou volumineuses | Contrôle des champs, date future obligatoire, corps de requête limité à 64 Ko |
| Absence de traces | Chaque échec de mot de passe ou de code, chaque activation et chaque connexion réussie est journalisé avec l'adresse source |

**Authentification multifacteur.** Le médecin saisit son identifiant et son mot de passe (premier facteur : ce qu'il sait), puis un code à 6 chiffres calculé par son téléphone (second facteur : ce qu'il possède). Le code change toutes les 30 secondes (TOTP, norme RFC 6238) et n'est valable qu'avec le secret enregistré lors de l'enrôlement. Lors de la première connexion, le portail affiche un QR code que le médecin scanne avec une application d'authentification ; le compte n'est marqué « actif » qu'après la saisie d'un premier code correct. Aux connexions suivantes, seul le code est demandé.

![07-05-service-portail](../captures/07-05-service-portail.png)
*Capture : service du portail actif*

![07-10-enrolement-totp](../captures/07-10-enrolement-totp.png)
*Capture : enrôlement du second facteur (QR code masqué)*

![07-11-espace-medecin](../captures/07-11-espace-medecin.png)
*Capture : espace médecin après authentification à deux facteurs*

### 7.5 Le reverse proxy

Nginx est le seul composant visible d'Internet. Il écoute uniquement sur `10.1.10.10`, port 443 : le port 80 n'est pas ouvert.

| Fonction | Réglage |
|---|---|
| Chiffrement | TLS 1.2 minimum (TLS 1.3 accepté), certificat avec nom `portail.mediconnect.local` et adresse `203.0.113.2` |
| Protection des navigateurs | `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Content-Security-Policy` |
| Limitation de débit | L'espace médecin accepte 10 requêtes par minute et par adresse (rafale de 10) ; au-delà, code 429 |
| Discrétion | Version du serveur masquée, page par défaut supprimée |
| Taille des requêtes | 64 Ko au maximum |
| Transmission à l'application | Adresse réelle du client et protocole d'origine, utilisés pour les journaux et les cookies |

![07-06-nginx-reverse-proxy](../captures/07-06-nginx-reverse-proxy.png)
*Capture : Nginx à l'écoute sur `10.1.10.10:443` et en-têtes de sécurité*

### 7.6 Règles du pare-feu

Deux règles seulement ouvrent le chemin du portail. Tout le reste de la DMZ reste interdit par défaut.

| Interface | Source | Destination | Port | Rôle |
|---|---|---|---|---|
| WAN | Toute adresse | `203.0.113.2` redirigé vers `10.1.10.10` | TCP 443 | Redirection de port (NAT de destination) et règle de passage associée, journalisée |
| DMZ | `10.1.10.20` | `10.1.30.20` | TCP 5432 | Serveur web vers base de données, journalisée |

L'adresse du reverse proxy n'a donc aucun accès à la zone SERVEURS, et celle du serveur web n'a accès qu'à un port d'une machine. Les deux rôles partageant la même machine dans la maquette, cette séparation par adresse n'arrête pas un attaquant qui prendrait le contrôle du serveur (voir 7.9).

![07-02-regle-dmz-base](../captures/07-02-regle-dmz-base.png)
*Capture : règle DMZ vers la base de données*

![07-07-nat-portail](../captures/07-07-nat-portail.png)
*Capture : redirection du port 443 vers le reverse proxy*

### 7.7 Vérifications

| Test | Résultat attendu | Résultat obtenu |
|---|---|---|
| Requête HTTPS depuis le poste « Internet » (`203.0.113.100`) vers `203.0.113.2` | Page du portail, en-têtes de sécurité | `200 OK`, tous les en-têtes présents |
| Requête mal formée envoyée au reverse proxy | Refus | `400 Bad Request` |
| Connexion à la base depuis le serveur web | Acceptée, chiffrée | `portail_app`, `ssl = t` |
| Prise de rendez-vous par un patient | Enregistrement | Message de confirmation |
| Connexion d'un médecin : mot de passe, enrôlement TOTP, code | Accès à l'espace médecin | Accès accordé, `totp_active` et `connexion_reussie` dans le journal |
| Mauvais mot de passe | Refus sans indication | « Identifiant ou mot de passe incorrect », `echec_mot_de_passe` journalisé |
| Cinq codes à usage unique faux de suite | Retour à la connexion | Déconnexion à la 5ᵉ erreur, cinq `echec_totp` journalisés |

![07-08-acces-internet-portail](../captures/07-08-acces-internet-portail.png)
*Capture : réponse du portail depuis le poste Internet*

![07-09-prise-rendez-vous](../captures/07-09-prise-rendez-vous.png)
*Capture : prise de rendez-vous par un patient*

![07-13-refus-authentification](../captures/07-13-refus-authentification.png)
*Capture : refus d'un mot de passe incorrect*

![07-14-journal-securite](../captures/07-14-journal-securite.png)
*Capture : événements de sécurité du portail dans le journal*

### 7.8 Difficultés rencontrées

1. **Connexion à la base bloquée (délai dépassé).** La règle du pare-feu n'autorise que la source `10.1.10.20`, mais le serveur, qui porte deux adresses, utilisait la première (`10.1.10.10`) pour sortir : le pare-feu bloquait à juste titre. La route vers la zone SERVEURS impose désormais l'adresse source `10.1.10.20`. La règle est restée aussi stricte qu'avant : on a corrigé le serveur, pas assoupli le filtrage.
2. **Authentification refusée par la base.** Le mot de passe du compte applicatif avait été altéré par un copier-coller dans la console. Il est maintenant transféré par `scp` entre les serveurs, sans intermédiaire humain.
3. **Règle de redirection sans effet.** Le champ « Firewall rule » de la redirection de port était sur `Manual` : aucune règle de passage n'était créée, le trafic redirigé aurait été bloqué. Il a été placé sur `Pass`.
4. **Codes à usage unique refusés alors que le téléphone était à l'heure.** Après deux jours d'arrêt de la maquette, l'horloge du serveur avait deux heures d'avance, soit exactement l'écart entre l'heure de Paris et l'heure UTC : une heure locale a vraisemblablement été prise pour une heure UTC. Le code calculé par le serveur pour vérification était différent de celui du téléphone. Le journal conserve la trace du saut d'horloge lors de la correction. Cet incident confirme la justification de la section 2.4 : sans heure commune, l'authentification multifacteur est inutilisable. Une synchronisation NTP est mise en place dans la partie journalisation.

![07-12-echecs-totp-journal](../captures/07-12-echecs-totp-journal.png)
*Capture : codes refusés, code attendu côté serveur différent de celui du téléphone (horloge décalée)*

### 7.9 Limites

- **Certificat auto-signé.** Le navigateur affiche un avertissement ; en production, un certificat d'une autorité publique serait utilisé. La connexion du serveur web à PostgreSQL est chiffrée mais le certificat de la base n'est pas vérifié (`sslmode=require` et non `verify-full`).
- **Pas de pare-feu applicatif (WAF).** Le reverse proxy filtre le débit et les en-têtes, mais n'analyse pas le contenu des requêtes (injections, scripts) ; un module de type ModSecurity ou le contrôle applicatif du pare-feu pourrait le compléter.
- **Blocage par session, non par compte.** Après 5 codes faux, la session est détruite, mais un attaquant qui connaît le mot de passe peut recommencer ; seule la limitation de débit de Nginx le ralentit. En production, le compte serait verrouillé temporairement après plusieurs échecs.
- **Secret TOTP stocké en clair dans la base**, et pas de codes de secours si le téléphone est perdu. En production, le secret serait chiffré et une procédure de récupération serait prévue.
- **Reverse proxy et serveur web sur la même machine.** Un attaquant qui compromet l'un atteint l'autre (limite déjà signalée en section 2.5). La base de données partage aussi sa machine avec l'annuaire, pour économiser les ressources.
- **Test depuis un tunnel SSH.** Le navigateur de l'administrateur n'est pas sur le réseau « Internet » de la maquette : les tests de l'interface ont été faits par un tunnel temporaire, ce qui explique que les journaux affichent l'adresse source `10.1.10.10`. Le test depuis un vrai client Internet (`203.0.113.100`) n'a porté que sur l'accès HTTPS.
- **Cartes réseau d'installation.** Les cartes NAT de SRV-DMZ et du serveur de base de données sont conservées le temps de la maquette pour les installations ; elles seraient retirées en production.
- **Journaux locaux.** Pour l'instant, les journaux du portail ne sont que sur SRV-DMZ ; ils seront envoyés au serveur de journalisation de la zone ADMIN (section 10).
