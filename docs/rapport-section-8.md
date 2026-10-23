## 8. Politique de filtrage, règles d'identité et contrôle applicatif

### 8.1 Principes

La politique de filtrage applique trois règles, sur toutes les interfaces du pare-feu du siège :

1. **Tout est interdit par défaut**, et chaque zone se termine par une règle de blocage explicite **journalisée** : toute tentative non prévue laisse une trace nommée (« DMZ : tout le reste interdit », « VPN : tout le reste interdit »…).
2. **Chaque flux autorisé est le plus étroit possible** : une source, une destination, un protocole et un port.
3. **Les règles utilisent des alias**, c'est-à-dire des noms donnés aux adresses : une règle « `VPN_COMMERCIAUX` vers `H_CRM` » se lit sans connaître le plan d'adressage, et une adresse se modifie en un seul endroit.

| Alias | Contenu | Rôle |
|---|---|---|
| `H_REVPROXY`, `H_WEB` | `10.1.10.10`, `10.1.10.20` | Reverse proxy et serveur web (DMZ) |
| `H_LDAP`, `H_DB` | `10.1.30.10`, `10.1.30.20` | Annuaire et base de données |
| `H_CRM`, `H_SUPPORT` | `10.1.30.30`, `10.1.30.50` | CRM et serveur support |
| `H_BASTION`, `H_LOGS` | `10.1.99.10`, `10.1.99.20` | Bastion (prévu) et serveur de journalisation |
| `VPN_SUPPORT`, `VPN_ADMINS`, `VPN_COMMERCIAUX` | `10.8.10.0/24`, `10.8.50.0/24`, `10.8.60.0/24` | Pools VPN par groupe |
| `LAN_SITE2` | `10.2.40.0/21` | LAN du site secondaire |

L'ordre des règles est déterminant : le pare-feu s'arrête à la première règle qui correspond. La règle de blocage est donc toujours la dernière de chaque interface (voir 8.7).

![08-01-alias](../captures/08-01-alias.png)
*Capture : alias du pare-feu du siège*

### 8.2 Règles par zone

| Interface | Source | Destination | Port | Action |
|---|---|---|---|---|
| WAN | Toute adresse | Redirection vers `H_REVPROXY` | TCP 443 | Autoriser (section 7) |
| WAN | Pare-feu du site secondaire | Pare-feu du siège | IPsec | Autoriser (section 5) |
| WAN | Toute adresse | Pare-feu du siège | UDP 1194 à 1196 (OpenVPN) | Autoriser (section 6) |
| DMZ | `H_WEB` | `H_DB` | TCP 5432 | Autoriser, journalisé |
| DMZ | DMZ | Pare-feu (DMZ) | DNS 53, NTP 123 | Autoriser |
| DMZ | DMZ | `H_LOGS` | TCP 514 (syslog) | Autoriser, journalisé |
| DMZ | Tout | Tout | Tout | **Bloquer, journalisé** |
| DEMO | DEMO | Pare-feu (DEMO) | DNS 53, NTP 123 | Autoriser |
| DEMO | Tout | Tout | Tout | **Bloquer, journalisé** |
| SERVEURS | SERVEURS | Pare-feu (SERVEURS) | DNS 53, NTP 123 | Autoriser |
| SERVEURS | Tout | Tout | Tout | **Bloquer, journalisé** |
| ADMIN | Poste d'administration `10.1.99.50` | Pare-feu | HTTPS 443 | Autoriser (section 4) |
| ADMIN | `H_LOGS` | Pare-feu (ADMIN) | NTP 123 | Autoriser |

Les services DNS et NTP ne sont autorisés que vers la passerelle de chaque zone, jamais vers Internet ni vers une autre zone : un serveur compromis ne peut pas s'en servir pour faire sortir des données. Les journaux le montrent : le serveur de la DMZ, qui tentait de joindre des serveurs de temps publics sur Internet, est bloqué par la règle finale de la DMZ.

Les zones SERVEURS et DEMO n'initient aucun autre flux : elles ne font que répondre aux connexions autorisées vers elles.

![08-02-regles-dmz](../captures/08-02-regles-dmz.png)
*Capture : règles de la DMZ*

![08-03-regles-serveurs](../captures/08-03-regles-serveurs.png)
*Capture : règles de la zone SERVEURS*

![08-04-regles-demo](../captures/08-04-regles-demo.png)
*Capture : règles de la zone DEMO*

### 8.3 Règles basées sur l'identité

L'identité d'un utilisateur distant est traduite en adresse par le VPN : chaque groupe de l'annuaire a son serveur OpenVPN et son pool d'adresses (section 6). Le pare-feu reconnaît donc le groupe à l'adresse source et applique les droits correspondants.

| Groupe | Source | Destination autorisée | Port |
|---|---|---|---|
| Commerciaux | `VPN_COMMERCIAUX` | `H_CRM` | TCP 80 |
| Commerciaux | `VPN_COMMERCIAUX` | Zone DEMO | TCP 443 |
| Support | `VPN_SUPPORT` | `H_SUPPORT` | TCP 80 |
| Administrateurs | `VPN_ADMINS` | `H_LDAP` | TCP 22 (temporaire) |
| Tous | Tout | Tout | **Bloquer, journalisé** |

Le CRM et le serveur support sont simulés par deux petits services web de démonstration, sur deux adresses supplémentaires du serveur de la zone SERVEURS, exécutés sous un utilisateur temporaire sans droits.

**Démonstration.** Les deux tests sont faits depuis le même poste Internet, avec une route forcée vers toute la zone SERVEURS : seul le pare-feu décide.

| Utilisateur | CRM (`10.1.30.30`) | Serveur support (`10.1.30.50`) |
|---|---|---|
| `c.durand` (commerciale, `10.8.60.x`) | Autorisé : `200 OK` | Bloqué : délai d'attente dépassé |
| `s.martin` (support, `10.8.10.x`) | Bloqué : délai d'attente dépassé | Autorisé : `200 OK` |

Les journaux du pare-feu confirment chaque décision, avec le nom de la règle appliquée : « Commerciaux : CRM » pour l'accès autorisé, « VPN : tout le reste interdit » pour l'accès refusé.

![08-05-regles-vpn-identite](../captures/08-05-regles-vpn-identite.png)
*Capture : règles basées sur l'identité (interface OpenVPN)*

![08-06-test-commerciale](../captures/08-06-test-commerciale.png)
*Capture : la commerciale atteint le CRM, pas le serveur support*

![08-07-test-support](../captures/08-07-test-support.png)
*Capture : le support atteint son serveur, pas le CRM*

![08-08-log-blocage-vpn](../captures/08-08-log-blocage-vpn.png)
*Capture : décisions du pare-feu pour la même utilisatrice, selon la destination*

### 8.4 Séparation entre production et démonstration

Le sujet impose que les démonstrations faites devant les médecins n'utilisent pas la production. La zone DEMO contient le serveur `SRV-DEMO` (`10.1.20.10`), copie du portail avec :

- **sa propre base de données, locale**, contenant uniquement des données fictives (médecins et patients inventés, adresses en `exemple.invalid`) ;
- **ses propres secrets** : clé de session, mot de passe de base de données et certificat différents de ceux de la production, supprimés puis régénérés après la copie ;
- **un bandeau visible** « Environnement de démonstration – données fictives » sur chaque page ;
- **aucune carte réseau d'installation** : après l'installation, sa seule interface est dans la zone DEMO.

| Test depuis la zone DEMO | Résultat |
|---|---|
| Base de données de production (`10.1.30.20:5432`) | Bloqué |
| Annuaire (`10.1.30.10:636`) | Bloqué |
| Portail de production (`10.1.10.10:443`) | Bloqué |
| Commerciale connectée au VPN → portail DEMO (`10.1.20.10:443`) | Autorisé : `200 OK`, page de démonstration |

Même compromise ou mal manipulée lors d'une démonstration, la zone DEMO n'expose aucune donnée réelle et ne permet d'atteindre aucune autre zone.

![08-12-demo-isolee](../captures/08-12-demo-isolee.png)
*Capture : la zone DEMO ne peut joindre aucune ressource de production*

![08-13-commerciale-demo](../captures/08-13-commerciale-demo.png)
*Capture : accès de la commerciale au portail de démonstration par le VPN*

### 8.5 Contrôle applicatif : pare-feu applicatif web (WAF)

Le filtrage du pare-feu décide selon les adresses et les ports. Il ne voit pas ce que contient une connexion autorisée : une attaque envoyée sur le port 443 du portail passe la règle comme une requête normale. De plus, le trafic du portail est chiffré : seul le reverse proxy, qui termine le HTTPS, voit les requêtes en clair. C'est donc là que le contrôle applicatif du trafic web est placé.

| Élément | Choix |
|---|---|
| Moteur | ModSecurity 3, intégré à Nginx |
| Règles | OWASP Core Rule Set (924 règles chargées) : injections SQL, scripts intersites, inclusion de fichiers, analyse de protocole… |
| Mode | Blocage (`SecRuleEngine On`) : une requête dont le score de suspicion dépasse le seuil reçoit `403 Forbidden` |
| Journal | Journal d'audit, transmis au serveur de journalisation (section 10) |

| Test | Résultat |
|---|---|
| Requête normale | `200 OK` |
| Injection SQL (`?id=1' OR 1=1--`) | `403 Forbidden`, « SQL Injection Attack Detected via libinjection » |
| Prise de rendez-vous, connexion d'un médecin avec code TOTP, affichage de ses rendez-vous | Fonctionnent normalement, sans faux positif |

Le portail de démonstration, copié après l'installation du WAF, bénéficie de la même protection.

**Difficulté rencontrée.** Le fichier de chargement des règles fourni par Debian utilise une instruction (`IncludeOptional`) que ModSecurity 3 ne reconnaît pas : seules 7 règles de base étaient chargées et l'injection passait. Un fichier d'inclusion propre, chargeant directement la configuration et les règles OWASP, a corrigé le problème : le test du blocage a permis de détecter qu'un WAF « installé » n'était pas pour autant actif.

![08-10-waf-test](../captures/08-10-waf-test.png)
*Capture : requête normale acceptée, injection SQL bloquée*

![08-11-waf-journal](../captures/08-11-waf-journal.png)
*Capture : motif du blocage dans le journal du WAF*

![08-25-portail-avec-waf](../captures/08-25-portail-avec-waf.png)
*Capture : parcours complet d'un médecin (mot de passe, code TOTP, rendez-vous) avec le WAF actif*

### 8.6 Site secondaire

Le tunnel IPsec (section 5) est traité comme une zone à part entière : le trafic qui en sort est filtré, et rien n'y est autorisé par défaut.

| Élément | Configuration |
|---|---|
| Interface | Interface virtuelle du tunnel (`ipsec1`) assignée sur chaque pare-feu, avec une passerelle vers le pare-feu d'en face |
| Routage au siège | `10.2.0.0/16` via `10.255.0.2` (pare-feu du site secondaire) |
| Routage au site secondaire | `10.1.0.0/16` via `10.255.0.1` (pare-feu du siège) |
| Sortie du LAN du site secondaire | LAN vers `10.1.30.50`, TCP 80, journalisé ; tout le reste interdit |
| Entrée au siège | `LAN_SITE2` vers `H_SUPPORT`, TCP 80, journalisé |
| Heure | Le pare-feu du site secondaire se synchronise sur celui du siège à travers le tunnel (UDP 123) |
| Tout le reste | Bloqué et journalisé (« Tunnel : tout le reste interdit ») |

Le flux est filtré deux fois : à la sortie du site secondaire et à l'entrée du siège. Les employés et le support du site secondaire atteignent les applications de support du siège, mais pas l'annuaire, la base de données ni l'administration, même si le tunnel était utilisé par un poste compromis du site secondaire.

| Test depuis le pare-feu du site secondaire, adresse source du LAN (`10.2.40.1`) | Résultat |
|---|---|
| Serveur support du siège (`10.1.30.50`, TCP 80) | Connexion réussie |
| Annuaire du siège (`10.1.30.10`, TCP 636) | Délai d'attente dépassé (bloqué) |

Le site secondaire n'ayant pas de poste utilisateur dans la maquette, les tests sont faits avec l'outil de test de port du pare-feu, en imposant l'adresse du LAN comme source : le trafic est ainsi traité exactement comme celui d'un poste du site.

![08-21-regles-tunnel-siege](../captures/08-21-regles-tunnel-siege.png)
*Capture : règles appliquées au trafic venant du site secondaire*

![08-22-site2-support-ok](../captures/08-22-site2-support-ok.png)
*Capture : le site secondaire atteint le serveur support du siège*

![08-23-site2-annuaire-bloque](../captures/08-23-site2-annuaire-bloque.png)
*Capture : l'annuaire du siège reste inaccessible depuis le site secondaire*

### 8.7 Difficultés rencontrées

- **Noms proches dans les listes.** Une règle DNS de la DMZ visait « DEMO address » au lieu de « DMZ address ». L'erreur, détectée en relisant la liste complète des règles, aurait ouvert un flux vers la mauvaise zone ; chaque liste de règles a ensuite été relue colonne par colonne.
- **Ordre des règles.** La règle autorisant l'envoi des journaux de la DMZ avait été créée après la règle de blocage : les journaux du pare-feu affichaient le blocage avec le nom de la règle responsable, ce qui a permis de corriger l'ordre immédiatement.
- **Serveur d'authentification jamais testé.** Le premier test du VPN du support a échoué (`AUTH_FAILED`) : le conteneur de recherche du serveur `LDAP-Support` contenait une erreur. Le testeur d'authentification du pare-feu (« User DN not found ») a localisé le problème. Les trois serveurs d'authentification ont ensuite été testés avec succès.
- **Route perdue au redémarrage.** Après un redémarrage du serveur de la DMZ, le portail affichait une erreur interne : la route vers la base de données, qui impose l'adresse source du serveur web, était déclarée avant que cette adresse existe et n'était donc pas créée au démarrage. La route a été rattachée à la déclaration de l'adresse elle-même. Le pare-feu, en refusant la mauvaise adresse source, a empêché un contournement silencieux de la règle.
- **Tunnel non rétabli.** Après le redémarrage des machines virtuelles, le tunnel IPsec ne s'était pas reconstruit ; le diagnostic (aucune trace dans les journaux du siège, puis état du tunnel) a conduit à relancer le service IPsec.

![08-09-ldap-support-corrige](../captures/08-09-ldap-support-corrige.png)
*Capture : authentification du compte du support après correction*

![08-24-ldap-admins-ok](../captures/08-24-ldap-admins-ok.png)
*Capture : authentification d'un administrateur*
