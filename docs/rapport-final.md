# MediConnect : sécurisation de l'infrastructure réseau d'une plateforme de prise de rendez-vous médicaux

**Projet de Sécurité des réseaux – Salim Benayoune**

**Auteur :** [Prénom Nom]  
**Date :** octobre 2026  
**Vidéo de démonstration :** [lien vers la vidéo]  
**Dépôt du projet :** [lien GitHub, si rendu public]

---

## Sommaire

1. Contexte et objectifs
2. Architecture et zones de sécurité
3. Plan d'adressage
4. Mise en place de la topologie : pare-feu du siège
5. VPN site-à-site IPsec
6. VPN d'accès distant et authentification par l'annuaire
7. Portail web, reverse proxy et authentification multifacteur
8. Politique de filtrage, règles d'identité et contrôle applicatif
9. Sécurisation de l'administration
10. Stratégie de journalisation et synchronisation de l'heure
11. Tests réalisés et limites de la solution
12. Conclusion

Annexe : captures complémentaires

---


## 1. Contexte et objectifs

MediConnect est une entreprise française qui lance une plateforme de prise de rendez-vous médicaux en ligne. Elle dispose de deux sites, chacun avec son propre accès Internet : un siège, qui héberge les serveurs, les équipements de sécurité et la plateforme publique, et un site secondaire, dont les employés ont besoin des ressources du siège.

Cinq populations utilisent le système d'information, avec des besoins et des niveaux de confiance différents :

| Population | Accès | Exigence principale |
|---|---|---|
| Patients | Portail public, depuis Internet | HTTPS uniquement, aucun accès au système interne |
| Médecins | Espace professionnel, depuis Internet | Niveau de sécurité supérieur (authentification multifacteur), jamais d'accès direct aux serveurs internes |
| Employés en télétravail | VPN d'accès distant | Ressources accessibles selon le profil (support, comptabilité, employés, informaticiens, administrateurs) |
| Commerciaux itinérants | VPN d'accès distant | CRM et démonstrations uniquement, sur une zone DEMO séparée de la production |
| Administrateurs | Équipements et serveurs | Flux d'administration séparés des flux des utilisateurs |

Le développement de l'application web n'entre pas dans le périmètre : le travail porte sur l'architecture réseau, la segmentation, les VPN, le filtrage, l'authentification et la supervision. Un portail simple a été développé uniquement pour disposer d'un service réaliste à protéger et à tester.

La solution est réalisée sous forme de maquette virtualisée (VMware Workstation, pare-feu OPNsense, serveurs Debian). Chaque section présente les choix, leur justification, les vérifications réalisées, les difficultés rencontrées et les limites.

---

## 2. Architecture et zones de sécurité

### 2.1 Choix architecturaux

L'architecture repose sur cinq décisions :

- **Un pare-feu par site**, chacun connecté à son propre accès Internet, comme l'impose le sujet. Les deux sites sont reliés par un tunnel VPN IPsec site-à-site.
- **Un pare-feu central au siège, doté d'une interface par zone de sécurité.** Tout flux entre deux zones traverse ce pare-feu, ce qui permet d'appliquer la politique de sécurité en un point unique et de journaliser chaque flux.
- **Les VPN d'accès distant se terminent au siège**, là où se trouvent les serveurs. Les utilisateurs distants arrivent dans une zone dédiée et sont filtrés comme n'importe quel autre flux.
- **Les services d'infrastructure (DNS et NTP) sont fournis par les pare-feu.** Chaque pare-feu sert de résolveur DNS et de source de temps pour les zones de son site (voir 2.4).
- **Politique par défaut « tout interdit »** : seuls les flux explicitement nécessaires sont autorisés.

### 2.2 Zones de sécurité et niveaux de confiance

| Zone | Contenu | Niveau de confiance |
|---|---|---|
| INTERNET | Patients, médecins, attaquants potentiels | 0 : non fiable |
| DMZ | Reverse proxy, serveur web du portail | 1 : exposée |
| DEMO | Copie simplifiée du portail, données fictives | 2 : isolée, jetable |
| VPN-USERS | Télétravailleurs et commerciaux connectés par VPN, un pool d'adresses par groupe | 2 à 3 : selon le groupe |
| LAN-USERS | Postes des employés (siège et site secondaire), un VLAN par service | 3 : interne |
| SERVEURS | Annuaire LDAP, base de données, CRM, comptabilité, support | 4 : sensible |
| ADMIN | Bastion d'administration, serveur de journalisation | 5 : critique |

Le niveau de confiance détermine le sens des flux. Un flux d'une zone peu fiable vers une zone plus fiable est interdit par défaut et n'est ouvert que de façon ciblée. Un flux vers une zone moins fiable est plus facile à autoriser.

Les zones LAN-USERS et VPN-USERS sont subdivisées par service (VLAN sur le LAN, pool d'adresses pour le VPN, voir section 3). Le pare-feu peut ainsi appliquer des droits différents selon le service de l'utilisateur, et les mêmes droits qu'il soit au siège, au site secondaire ou en télétravail.

### 2.3 Justification des zones

**DMZ.** Le portail doit être joignable depuis Internet, ce qui l'expose aux attaques. Il est donc placé dans une zone dédiée, séparée du réseau interne. Si la DMZ est compromise, l'attaquant ne dispose d'aucun accès direct aux serveurs internes. Le reverse proxy est le seul point d'entrée : il termine le HTTPS et relaie les requêtes vers le serveur web.

**Base de données en zone SERVEURS.** La base de données du portail n'est pas en DMZ. Seul le serveur web peut l'interroger, sur un port unique et avec une connexion initiée depuis la DMZ. Un attaquant qui prend le contrôle du serveur web n'obtient pas pour autant les données.

**DEMO.** Les démonstrations aux médecins n'utilisent jamais la production. La zone DEMO contient une copie simplifiée avec des données fictives : même en cas d'erreur de manipulation ou de compromission, aucune donnée réelle n'est exposée. Elle n'a aucun accès vers les autres zones internes.

**VPN-USERS.** Les utilisateurs distants se connectent depuis des réseaux que l'entreprise ne maîtrise pas (domicile, cabinet médical). Leur zone est séparée du LAN et subdivisée en pools d'adresses par groupe, ce qui permet de leur appliquer des règles différentes selon leur identité.

**LAN-USERS.** Les postes des employés ont une confiance moyenne à élevée, mais restent des cibles privilégiées (hameçonnage, logiciels malveillants). Le LAN est découpé en un VLAN par service : un poste compromis au support ne peut pas atteindre les serveurs comptables. Aucun VLAN utilisateur n'a accès à l'administration.

**SERVEURS.** Cette zone concentre les données et les services sensibles. Elle n'est jamais joignable directement depuis Internet.

**ADMIN.** Les flux d'administration sont isolés des flux utilisateurs : un utilisateur du LAN ne peut pas administrer les équipements. Le serveur de journalisation y est placé volontairement : si la DMZ est compromise, l'attaquant ne peut pas effacer les traces de son intrusion.

### 2.4 Services d'infrastructure : DNS et NTP

Deux services sont indispensables au fonctionnement de l'architecture :

- **NTP (synchronisation de l'heure).** L'authentification multifacteur des médecins repose sur des codes à usage unique (TOTP) valables 30 secondes : une horloge serveur décalée provoquerait des refus d'authentification. Une heure commune à tous les équipements est aussi nécessaire pour corréler les journaux des deux sites lors d'une analyse d'incident.
- **DNS (résolution de noms).** Les certificats HTTPS reposent sur des noms de domaine (portail public et espace des médecins), et les postes comme les clients VPN doivent résoudre les noms des serveurs internes.

Ces services sont assurés par les pare-feu eux-mêmes (résolveur DNS Unbound et service NTP intégrés à OPNsense), ce qui évite d'ajouter un serveur et d'ouvrir des flux supplémentaires. Chaque zone interroge uniquement la passerelle de son propre sous-réseau. Le pare-feu du siège se synchronise sur des serveurs NTP publics (dans la maquette, sans Internet réel, il sert lui-même de référence, voir 3.8), et celui du site secondaire sur le siège, via le tunnel.

La DMZ et la zone DEMO ne peuvent pas résoudre les noms internes, ce qui limite les informations disponibles pour un attaquant qui les compromettrait.

### 2.5 Flux autorisés

| Source | Destination | Autorisé | Justification |
|---|---|---|---|
| INTERNET | DMZ | HTTPS (443) vers le reverse proxy (`10.1.10.10`) uniquement | Seul service public |
| INTERNET | Pare-feu du siège (WAN) | OpenVPN (UDP, un port par instance) | Accès distant, authentifié avant tout accès interne |
| Pare-feu du site secondaire | Pare-feu du siège (WAN) | IPsec (UDP 500, UDP 4500, ESP), depuis la seule adresse `203.0.113.3` | Établissement du tunnel site-à-site |
| INTERNET | Toutes les autres zones | Interdit | Aucune confiance |
| DMZ | SERVEURS | Serveur web (`10.1.10.20`) vers base de données (`10.1.30.20`), TCP 5432 (PostgreSQL) uniquement | Fonctionnement du portail |
| DMZ | ADMIN | Syslog vers le serveur de logs (`10.1.99.20`) uniquement | Journalisation, sans accès à l'administration |
| DMZ | LAN, DEMO, autres flux vers ADMIN | Interdit | Limiter la propagation d'une compromission |
| DEMO | Toutes les autres zones | Interdit (ses flux sont journalisés par le pare-feu) | Zone isolée et jetable |
| VPN-USERS | SERVEURS, DEMO | Selon le pool (groupe) de l'utilisateur | Moindre privilège |
| LAN-USERS | SERVEURS | Selon le VLAN du service | Moindre privilège |
| LAN-USERS, VPN-USERS (hors administrateurs) | ADMIN | Interdit | Séparation de l'administration |
| ADMIN | Toutes les zones | Protocoles d'administration depuis le bastion | Administration sécurisée |
| SERVEURS, pare-feu | Serveur de logs | Syslog uniquement | Journalisation centralisée |
| Toutes les zones | Leur passerelle | DNS (53) et NTP (123) | Services d'infrastructure |
| Pare-feu du siège | Annuaire LDAP (`10.1.30.10`) | LDAPS (636) uniquement, avec un compte en lecture seule | Authentification des utilisateurs VPN |
| Site secondaire | Siège | Via le tunnel IPsec, selon le VLAN du service | Interconnexion sécurisée |

Le flux de journalisation depuis la DMZ est la seule exception à l'interdiction DMZ → ADMIN : il est limité à un protocole et à une machine, et le serveur de logs ne fait que recevoir.

Le reverse proxy et le serveur web sont dans le même sous-réseau : leurs échanges ne traversent pas le pare-feu. Ce risque est accepté pour la maquette ; en production, on placerait le serveur web dans un second segment de DMZ.

Le détail des règles est présenté dans la section consacrée à la politique de filtrage.

### 2.6 Schéma d'architecture

![Architecture](architecture.png)

*Architecture globale de MediConnect : zones de sécurité, pare-feu et interconnexion des sites.*

---

## 3. Plan d'adressage

### 3.1 Principes de conception

1. **Adresses privées RFC 1918, dans `10.0.0.0/8`.** Ces plages ne sont pas routées sur Internet. Le `192.168.0.0/16` est volontairement évité : les box des domiciles utilisent presque toutes `192.168.0.0/24` ou `192.168.1.0/24`, ce qui créerait un conflit de routage pour un télétravailleur connecté au VPN.
2. **Un sous-réseau par zone de sécurité et par service.** Chaque zone, et chaque service à l'intérieur du LAN, possède sa propre plage. Le pare-feu peut ainsi appliquer une règle différente à chacun.
3. **Une structure lisible : `10.<site>.<zone>.0/24`.** Le deuxième octet identifie le site (1 siège, 2 site secondaire, 8 VPN d'accès distant) et le troisième identifie la zone ou le service. Une adresse suffit à savoir où se trouve une machine et à quel service elle appartient.
4. **Des blocs agrégables.** Les sous-réseaux des services d'un même site sont regroupés dans un bloc `/21` (`10.1.40.0/21` au siège, `10.2.40.0/21` au site secondaire). Une seule règle peut ainsi viser tout le LAN d'un site, par exemple pour lui interdire l'accès à la zone ADMIN.
5. **Aucun chevauchement** entre les sites, les zones et les pools VPN, sinon le routage et les tunnels IPsec ne fonctionnent pas.
6. **Des masques `/24`** pour chaque sous-réseau de zone ou de service : 254 hôtes, largement suffisant, et lecture simplifiée. Seul le lien du tunnel, qui n'a besoin que de deux adresses, est en `/30` (voir 3.5).

### 3.2 Zones du siège

| Zone | Sous-réseau | Passerelle (pare-feu) |
|---|---|---|
| DMZ | `10.1.10.0/24` | `10.1.10.1` |
| DEMO | `10.1.20.0/24` | `10.1.20.1` |
| SERVEURS | `10.1.30.0/24` | `10.1.30.1` |
| LAN-USERS (bloc) | `10.1.40.0/21` | voir 3.3 |
| ADMIN | `10.1.99.0/24` | `10.1.99.1` |

### 3.3 Réseaux locaux : un VLAN par service

Le LAN de chaque site est découpé en VLAN, un par service. Le numéro de VLAN est identique au troisième octet de l'adresse, ce qui facilite la lecture et le dépannage.

| Service | VLAN | Siège | Site secondaire | Pool VPN correspondant |
|---|---|---|---|---|
| Support | 41 | `10.1.41.0/24` | `10.2.41.0/24` | `10.8.10.0/24` |
| Comptabilité | 42 | `10.1.42.0/24` | — | `10.8.20.0/24` |
| Employés / direction | 43 | `10.1.43.0/24` | `10.2.43.0/24` | `10.8.30.0/24` |
| Informaticiens | 44 | `10.1.44.0/24` | — | `10.8.40.0/24` |
| Commerciaux | 46 | `10.1.46.0/24` | `10.2.46.0/24` | `10.8.60.0/24` |

La passerelle de chaque VLAN est l'adresse `.1` (par exemple `10.1.41.1` pour le support du siège). Le site secondaire n'accueille que les services décrits par le sujet : employés, support et commerciaux.

Les administrateurs n'ont pas de VLAN utilisateur : ils travaillent depuis la zone ADMIN (`10.1.99.0/24`) ou depuis leur pool VPN dédié, conformément à l'exigence de séparation des flux d'administration. C'est pourquoi le VLAN 45 n'est pas utilisé, alors que le pool VPN correspondant (`10.8.50.0/24`) existe.

Cette segmentation permet d'appliquer les mêmes droits à un utilisateur qu'il soit au bureau ou en télétravail : un commercial n'atteint que le CRM et la zone DEMO, qu'il soit dans `10.1.46.0/24`, `10.2.46.0/24` ou `10.8.60.0/24`.

### 3.4 VPN d'accès distant : un pool par groupe

| Groupe LDAP | Pool d'adresses | Ressources autorisées |
|---|---|---|
| Support | `10.8.10.0/24` | Applications de support |
| Comptabilité | `10.8.20.0/24` | Serveurs comptables |
| Employés | `10.8.30.0/24` | Ressources bureautiques |
| Informaticiens | `10.8.40.0/24` | Ressources techniques autorisées |
| Administrateurs | `10.8.50.0/24` | Infrastructure d'administration (via le bastion) |
| Commerciaux | `10.8.60.0/24` | CRM et zone DEMO uniquement |

**Mécanisme d'attribution.** L'identité de l'utilisateur est traduite en règles réseau. Chaque groupe dispose de sa propre instance de serveur OpenVPN, avec son pool d'adresses. Chaque instance authentifie les utilisateurs auprès de l'annuaire LDAP et n'accepte que les membres de son groupe. Un utilisateur reçoit donc une adresse dans le pool de son groupe, et les règles du pare-feu s'appliquent à ce pool.

Exemple : un commercial qui se connecte reçoit une adresse dans `10.8.60.0/24`. Les règles associées à ce pool ne lui ouvrent que le CRM et la zone DEMO ; il ne peut pas atteindre les serveurs comptables.

Dans la maquette, trois groupes sont mis en œuvre (Support, Commerciaux, Administrateurs). Les autres suivent exactement le même modèle.

### 3.5 Liaisons entre sites et accès Internet

| Lien | Adresse | Remarque |
|---|---|---|
| Tunnel IPsec site-à-site | `10.255.0.0/30` | Siège `.1`, site 2 `.2` |
| WAN siège | `203.0.113.2/24` | Plage de documentation (RFC 5737) |
| WAN site 2 | `203.0.113.3/24` | Même segment : Internet simulé |
| Client Internet de test | `203.0.113.100/24` | Simule patients, médecins, attaquant |

Le tunnel IPsec est configuré en mode **route-based** : chaque pare-feu dispose d'une interface virtuelle de tunnel (VTI), adressée dans le `/30`. Ce mode permet de traiter le tunnel comme une interface ordinaire : le trafic venant du site secondaire est filtré par des règles dédiées, comme celui de n'importe quelle zone. Un `/30` fournit exactement deux adresses utilisables, une par pare-feu.

Les adresses WAN appartiennent à une plage réservée à la documentation, jamais routée sur Internet. Dans la maquette, un seul segment partagé simule Internet.

### 3.6 Adresses des machines

| Machine | Adresse | Zone |
|---|---|---|
| Reverse proxy / WAF | `10.1.10.10` | DMZ |
| Serveur web du portail | `10.1.10.20` | DMZ |
| Portail DEMO | `10.1.20.10` | DEMO |
| Annuaire LDAP | `10.1.30.10` | SERVEURS |
| Base de données | `10.1.30.20` | SERVEURS |
| CRM | `10.1.30.30` | SERVEURS |
| Serveur comptable | `10.1.30.40` | SERVEURS |
| Serveur support | `10.1.30.50` | SERVEURS |
| Bastion d'administration | `10.1.99.10` | ADMIN |
| Serveur de journalisation | `10.1.99.20` | ADMIN |
| Poste d'administration (poste hôte de la maquette) | `10.1.99.50` | ADMIN |
| Pare-feu du site secondaire, interface d'administration | `10.2.99.1` | ADMIN du site secondaire |
| Poste d'administration, côté site secondaire | `10.2.99.50` | ADMIN du site secondaire |

Le réseau `10.2.99.0/24` est un réseau d'administration dédié au pare-feu du site secondaire, suivant la même convention `10.<site>.99.0/24` que la zone ADMIN du siège. Il a permis de configurer ce pare-feu avant que le tunnel IPsec n'existe.

Conventions : `.1` est la passerelle (le pare-feu), les serveurs ont des adresses fixes à partir de `.10`, et les postes utilisateurs reçoivent une adresse par DHCP de `.100` à `.200`, ce qui évite les collisions avec les serveurs.

### 3.7 DNS et NTP

La passerelle `.1` de chaque sous-réseau joue aussi le rôle de serveur DNS et NTP pour ce sous-réseau. Le DHCP distribue automatiquement ces adresses aux postes. Les serveurs à adresse fixe sont configurés avec la même valeur.

| Élément | DNS et NTP utilisés |
|---|---|
| Postes et serveurs d'une zone du siège | Passerelle de la zone (ex. `10.1.30.1` pour SERVEURS) |
| Postes du site secondaire | Passerelle de leur VLAN (ex. `10.2.41.1`) |
| Clients VPN | Passerelle de leur pool, poussée par le serveur OpenVPN |
| Pare-feu du siège | Serveurs NTP publics |
| Pare-feu du site secondaire | Pare-feu du siège, via le tunnel (`10.255.0.1`) |

Une zone interne de noms (par exemple `mediconnect.local`) permet de nommer les serveurs internes (`ldap`, `crm`, `logs`). Elle n'est pas résolue depuis la DMZ ni depuis la zone DEMO.

### 3.8 Limites du plan

- Le plan `10.x.x.x` peut entrer en conflit avec un réseau distant utilisant la même plage (cabinet médical, autre entreprise), rare mais possible pour un utilisateur nomade.
- L'identité est déduite de l'adresse IP : si un utilisateur parvenait à changer d'adresse sur le LAN, il changerait de droits. Le risque est limité par le fait que chaque VLAN est un réseau séparé, et qu'en production on ajouterait une authentification des postes sur les ports réseau (802.1X).
- Dans la maquette, tous les VLAN et tous les groupes VPN ne sont pas montés : seuls ceux nécessaires à la démonstration le sont.
- Le segment WAN unique simule Internet sans reproduire deux opérateurs distincts.
- Le segment WAN de la maquette n'a pas d'accès réel à Internet : le pare-feu du siège ne peut pas joindre de serveurs NTP publics. Il sert donc lui-même de référence de temps (mode « orphelin » du service NTP d'OPNsense). Toute la maquette reste à la même heure, ce qui suffit pour le TOTP et la corrélation des journaux, mais cette heure n'est pas garantie exacte.

---

## 4. Mise en place de la topologie : pare-feu du siège

### 4.1 Environnement de virtualisation

La maquette est réalisée dans **VMware Workstation Pro 26H1** sur un poste Windows 11 (16 Go de mémoire vive). Ce choix permet de reproduire une infrastructure complète sur une seule machine, avec des réseaux virtuels isolés les uns des autres. Les pare-feu fonctionnent sous **OPNsense 26.7** (basé sur FreeBSD 15.1), une solution libre qui couvre l'ensemble des fonctions demandées par le sujet : filtrage, VPN IPsec et OpenVPN, authentification LDAP, journalisation et contrôle applicatif.

Les serveurs et les postes de test fonctionnent sous Debian, sans interface graphique pour limiter la consommation de ressources.

### 4.2 Vérification de l'intégrité du logiciel

Avant toute installation, l'image d'installation d'OPNsense a été contrôlée : son empreinte SHA-256 a été calculée localement puis comparée à celle publiée par l'éditeur sur son propre site, distinct du miroir de téléchargement. Cette vérification protège contre une image corrompue ou volontairement modifiée sur le miroir (attaque de la chaîne d'approvisionnement). Elle est particulièrement importante ici, car le pare-feu voit tout le trafic entre les zones : un pare-feu compromis annulerait l'ensemble de l'architecture.

### 4.3 Création de la machine virtuelle du pare-feu du siège

La machine `FW-SIEGE` est dimensionnée au plus juste pour un pare-feu : 2 cœurs, 2 Go de mémoire et un disque de 20 Go.

Le réseau est construit avec des **segments LAN VMware**. Un segment LAN est un commutateur virtuel privé : seules les machines branchées sur le même segment communiquent entre elles, sans lien avec le poste hôte ni avec le réseau physique. Chaque zone de sécurité est un segment distinct, et le pare-feu est la seule machine branchée sur tous : tout flux entre deux zones traverse donc obligatoirement le pare-feu, comme le prévoit l'architecture (section 2).

| Carte | Segment | Zone |
|---|---|---|
| 1 | `SEG-INTERNET` | WAN (Internet simulé) |
| 2 | `SEG-DMZ` | DMZ |
| 3 | `SEG-DEMO` | DEMO |
| 4 | `SEG-SERVEURS` | SERVEURS |
| 5 | `SEG-LAN1` | LAN-USERS |
| 6 | VMnet2 (hôte uniquement) | ADMIN |

### 4.4 Installation d'OPNsense

OPNsense est installé sur le disque virtuel à partir de l'image d'installation, puis l'image est retirée du lecteur virtuel pour que la machine démarre sur le système installé. Le compte administrateur reçoit un mot de passe choisi à l'installation, différent du mot de passe par défaut du mode d'essai.

### 4.5 Affectation des interfaces et adressage

Chaque carte réseau est affectée à un rôle, puis reçoit l'adresse de passerelle prévue par le plan d'adressage (section 3). La correspondance entre les cartes virtuelles et les interfaces d'OPNsense a été vérifiée en comparant leurs adresses MAC : une inversion aurait branché une zone sur le mauvais segment.

Après l'assistant de configuration initial, l'interface WAN a été contrôlée : l'assistant l'avait repassée en DHCP, et son adresse fixe `203.0.113.2/24` a dû être rétablie (voir 5.7).

| Rôle | Carte | Description | Adresse |
|---|---|---|---|
| WAN | `le0` | WAN | `203.0.113.2/24` |
| LAN | `le4` | LAN_USERS | `10.1.40.1/24` (provisoire, voir 4.8) |
| OPT1 | `le1` | DMZ | `10.1.10.1/24` |
| OPT2 | `le2` | DEMO | `10.1.20.1/24` |
| OPT3 | `le3` | SERVEURS | `10.1.30.1/24` |
| OPT4 | `le5` | ADMIN | `10.1.99.1/24` |

### 4.6 Accès d'administration

Les segments LAN étant isolés du poste hôte, l'interface web d'OPNsense n'est pas joignable depuis le poste de travail. La zone ADMIN est donc réalisée avec un réseau VMware **hôte uniquement** (VMnet2, sans service DHCP) sur lequel le poste physique reçoit l'adresse fixe `10.1.99.50`. Il joue ainsi le rôle de **poste d'administration**, situé dans le réseau d'administration dédié et non dans le réseau des utilisateurs.

Une règle de pare-feu, limitée à ce seul poste, autorise l'accès HTTPS à l'interface du pare-feu :

| Interface | Action | Protocole | Source | Destination | Port |
|---|---|---|---|---|---|
| ADMIN | Autoriser | TCP | `10.1.99.50` | Le pare-feu lui-même | 443 |

Toute autre machine qui se brancherait sur la zone ADMIN serait bloquée. Cette règle applique le principe du moindre privilège.

![03-09-regle-admin-https](../captures/03-09-regle-admin-https.png)
*Capture : 03-09-regle-admin-https*

**Suppression des règles par défaut du LAN.** À l'installation, OPNsense ajoute deux règles automatiques sur l'interface LAN : une règle qui autorise tout le trafic sortant du LAN, et une règle « anti-verrouillage » qui ouvre l'interface d'administration (HTTPS et SSH) depuis le LAN. Ces règles servent à ne pas perdre l'accès au premier démarrage, mais elles contredisent l'architecture : le LAN accueille les utilisateurs, qui ne doivent ni administrer le pare-feu ni accéder librement aux autres zones. Une fois l'accès depuis la zone ADMIN validé :

- la règle anti-verrouillage est désactivée ;
- les règles « Default allow LAN to any » (IPv4 et IPv6) sont supprimées ;
- l'interface web d'administration n'écoute plus que sur l'interface ADMIN.

Le LAN est ainsi soumis au même principe « tout interdit par défaut » que les autres zones ; ses flux légitimes seront ouverts service par service avec les VLAN.

![03-11-regles-lan-supprimees](../captures/03-11-regles-lan-supprimees.png)
*Capture : 03-11-regles-lan-supprimees*

Dans la maquette, le poste hôte administre directement le pare-feu. La politique cible (section 2.5) fait passer l'administration par le bastion ; ce point est traité dans la section consacrée à l'administration sécurisée.

### 4.7 Vérifications

Le comportement « tout interdit par défaut » est vérifié depuis le poste d'administration :

- la page d'administration en HTTPS s'affiche (flux autorisé) ;
- un ping vers le pare-feu échoue (flux non autorisé) : le filtrage bloque tout ce qui n'a pas été explicitement ouvert, y compris un test aussi simple que le ping.

Un instantané de la machine virtuelle est enregistré à ce stade, ce qui permet de revenir à un état connu après une erreur de configuration.

### 4.8 Limites et points d'attention

- **Amorçage de l'accès web.** Une interface sans règle bloque tout, y compris l'accès à la page qui permet de créer une règle. Pour sortir de ce cercle, le filtrage a été désactivé depuis la console pendant la durée de la création de la règle, puis réactivé. Cette opération n'a été possible que parce que la console de la machine virtuelle est un accès d'urgence physique ; en production, la règle d'administration serait préparée avant la mise en service.
- **Poste d'administration.** Le poste physique appartient à la zone ADMIN, mais il reste connecté à d'autres réseaux (Internet, réseau local de l'hôte). Une compromission du poste hôte compromettrait donc l'administration. En production, on utiliserait un poste dédié ou un bastion, point développé dans la section sur l'administration sécurisée.
- **Adresse du LAN provisoire.** Le plan prévoit un VLAN par service au sein du LAN-USERS ; l'interface LAN porte pour l'instant une adresse provisoire, remplacée lors de la mise en place des VLAN.
- **Cartes réseau émulées.** VMware présente à OPNsense des cartes de type AMD PCnet (`le`), suffisantes pour une maquette mais plus lentes que des cartes de production.
- **Internet simulé.** Les deux pare-feu partageront un seul segment WAN : il simule Internet sans reproduire deux opérateurs distincts ni de véritables adresses publiques.

---

## 5. VPN site-à-site IPsec

### 5.1 Besoin et choix techniques

Le site secondaire doit accéder à certaines ressources du siège à travers Internet, un réseau que l'entreprise ne maîtrise pas. Le sujet impose un VPN IPsec site-à-site entre les deux pare-feu : le trafic entre les sites est chiffré et authentifié, et un attaquant placé sur Internet ne voit que des paquets chiffrés.

| Choix | Justification |
|---|---|
| **IKEv2** | Version actuelle du protocole d'échange de clés : plus simple, plus robuste et plus sûre qu'IKEv1 |
| **Mode route-based (interface virtuelle VTI)** | Le tunnel apparaît comme une interface réseau (`ipsec1`). Le trafic qui en sort est filtré par des règles dédiées, comme celui de n'importe quelle zone, et ajouter un réseau ne demande qu'une route, pas une nouvelle négociation |
| **Authentification par clé pré-partagée** | Simple à mettre en œuvre dans la maquette ; les certificats sont recommandés en production (voir 5.8) |
| **Le siège initie, le site secondaire répond** | Le siège démarre le tunnel ; le site secondaire attend l'appel, ce qui évite deux négociations simultanées |

### 5.2 Mise en place du pare-feu du site secondaire

La machine `FW-SITE2` reprend la démarche du siège (section 4) : installation d'OPNsense 26.7, mot de passe administrateur distinct de celui du siège, et trois interfaces.

| Interface | Carte | Segment | Adresse |
|---|---|---|---|
| WAN | `le0` | `SEG-INTERNET` (partagé avec le siège) | `203.0.113.3/24` |
| LAN | `le1` | `SEG-LAN2` | `10.2.40.1/24` (provisoire, avant les VLAN) |
| ADMIN_SITE2 | `le2` | VMnet3 (hôte uniquement) | `10.2.99.1/24` |

Le site secondaire reçoit le même durcissement que le siège :

- l'interface web n'est accessible que depuis le poste d'administration (`10.2.99.50`), en HTTPS, et n'écoute que sur l'interface ADMIN_SITE2 ;
- les règles automatiques du LAN (« tout autoriser » et anti-verrouillage) sont supprimées : le LAN est soumis au principe « tout interdit par défaut ».

### 5.3 Ouverture du WAN au seul pair

Chaque pare-feu bloque par défaut tout ce qui arrive d'Internet. Trois flux sont ouverts, et **uniquement depuis l'adresse de l'autre pare-feu** : un tiers sur Internet ne peut pas engager de négociation IPsec.

| Pare-feu | Protocole | Port | Source autorisée | Rôle |
|---|---|---|---|---|
| FW-SIEGE | UDP | 500 | `203.0.113.3` | IKE : authentification et négociation des clés |
| FW-SIEGE | UDP | 4500 | `203.0.113.3` | IKE et ESP encapsulés en cas de traduction d'adresses |
| FW-SIEGE | ESP | — | `203.0.113.3` | Données chiffrées du tunnel |
| FW-SITE2 | idem | idem | `203.0.113.2` | Règles symétriques |

Le blocage des réseaux « bogon » a été désactivé sur les deux WAN : la plage `203.0.113.0/24` est réservée à la documentation et figure dans cette liste. Cette exception est propre à la maquette (voir 5.8).

### 5.4 Paramètres du tunnel

| Élément | Valeur |
|---|---|
| Version | IKEv2 |
| Identifiants | Adresse WAN de chaque pare-feu (`203.0.113.2` et `203.0.113.3`) |
| Clé pré-partagée | 32 caractères aléatoires, conservée hors du dépôt de code |
| Algorithmes IKE négociés | AES-CBC-128, HMAC-SHA2-256, échange de clés ECP-256 (courbe elliptique) |
| Algorithmes ESP négociés | AES-GCM-128 (chiffrement et intégrité), ECP-256 (confidentialité persistante) |
| Détection de pair mort (DPD) | 10 secondes |
| MOBIKE | Désactivé (adresses fixes entre deux sites) |
| Sélecteurs de trafic | `0.0.0.0/0` des deux côtés, mode tunnel |
| Politiques IPsec | **Désactivées** : le trafic n'entre dans le tunnel que par routage vers `ipsec1` |
| Request ID | `1`, identique dans le tunnel et dans l'interface virtuelle |
| Interface virtuelle | `ipsec1` : siège `10.255.0.1`, site secondaire `10.255.0.2`, masque `/30` |

Les sélecteurs `0.0.0.0/0` signifient que le tunnel accepte tout trafic ; c'est le routage et le pare-feu qui décident de ce qui y entre et de ce qui en sort. Ce fonctionnement n'est correct que si les politiques IPsec sont désactivées (voir 5.7).

### 5.5 Filtrage du trafic du tunnel

Le tunnel n'est pas une zone de confiance : le trafic qui en sort est filtré comme celui de n'importe quelle interface, et rien n'est autorisé par défaut. Pour valider le tunnel, une seule règle de test est ouverte sur le site secondaire :

| Interface | Action | Protocole | Source | Destination |
|---|---|---|---|---|
| IPsec (FW-SITE2) | Autoriser | ICMP | `10.255.0.1` | `10.255.0.2` |

Les règles définitives (par exemple, les VLAN du site secondaire vers certains serveurs du siège) sont décrites dans la section consacrée à la politique de filtrage.

### 5.6 Vérifications

- **Phase 1 établie** (`ESTABLISHED`) : les deux pare-feu se sont authentifiés mutuellement.
- **Phase 2 installée** (`INSTALLED`) : le tunnel de données est actif, avec des compteurs d'octets dans les deux sens.
- **Identifiants de session (SPI) croisés** : le SPI sortant du siège (`c628f131`) est le SPI entrant du site secondaire, et inversement (`c06234d6`). Les deux pare-feu partagent donc bien la même association de sécurité, avec les mêmes clés.
- **Ping de `10.255.0.1` vers `10.255.0.2` réussi**, avec le filtrage actif sur les deux pare-feu.
- **Accès d'administration conservé** sur les deux pare-feu pendant que le tunnel est actif.

![05-04-ipsec-etabli](../captures/05-04-ipsec-etabli.png)
*Capture : phases 1 et 2 établies, vues depuis le siège*

![05-05-ping-tunnel](../captures/05-05-ping-tunnel.png)
*Capture : ping à travers le tunnel chiffré*

### 5.7 Difficultés rencontrées et diagnostic

La mise en service a révélé trois problèmes, résolus en vérifiant le réseau couche par couche plutôt qu'en modifiant la configuration au hasard.

1. **Absence de communication entre les WAN.** La négociation IPsec n'aboutissait pas. Une table ARP incomplète sur FW-SITE2 (`arp -a`), puis une capture `tcpdump` sur le WAN du siège ont montré que ce dernier envoyait des requêtes DHCP : l'assistant de configuration initial avait remplacé l'adresse fixe par le mode DHCP. L'adresse `203.0.113.2/24` a été rétablie, ce qui a été vérifié avec `ifconfig`.
2. **Perte de l'accès d'administration lorsque le tunnel était actif.** Avec des sélecteurs `0.0.0.0/0`, les politiques IPsec installées par défaut envoyaient **tout** le trafic du pare-feu dans le tunnel, y compris les réponses au poste d'administration. La désactivation des politiques a rétabli un fonctionnement purement route-based : seul le trafic routé vers `ipsec1` est chiffré.
3. **Ping sans réponse malgré un tunnel établi.** Un test de quelques secondes, filtrage désactivé sur FW-SITE2 (`pfctl -d`, puis immédiatement `pfctl -e`), a montré que le tunnel fonctionnait et que le pare-feu rejetait le trafic du tunnel faute de règle. C'est le comportement attendu du principe « tout interdit par défaut », corrigé par une règle limitée au seul flux de test.

### 5.8 Limites

- **Clé pré-partagée.** Sa compromission permettrait d'usurper un pare-feu. En production, une authentification par certificats, émis par une autorité interne, éviterait de stocker et de transmettre un secret commun.
- **Algorithmes négociés par défaut.** Les propositions par défaut ont abouti à AES-128 et ECP-256, solides aujourd'hui. Fixer explicitement AES-256-GCM et une courbe plus robuste renforcerait la configuration et empêcherait toute négociation vers un algorithme plus faible.
- **Internet simulé.** Les deux pare-feu partagent un seul segment WAN dont les adresses appartiennent à une plage de documentation ; le filtrage des réseaux bogon a dû être désactivé, ce qui ne serait pas le cas avec de vraies adresses publiques.
- **Un seul tunnel, sans redondance.** La perte d'un lien Internet coupe l'interconnexion ; un second accès ou un second tunnel serait nécessaire en production.
- **Administration du site secondaire.** Elle passe par un réseau d'administration dédié (VMnet3) relié au poste hôte, et non à travers le tunnel depuis la zone ADMIN du siège comme le prévoit l'architecture cible.

---

## 6. VPN d'accès distant et authentification par l'annuaire

### 6.1 Besoin et principe

Les télétravailleurs et les commerciaux se connectent depuis des réseaux que l'entreprise ne maîtrise pas. Le sujet demande que leurs droits dépendent de leur **identité** : un commercial ne doit pas obtenir les accès d'un administrateur, même s'il est connecté au même VPN.

Le principe retenu traduit l'identité en adresse réseau, puis l'adresse en règles de filtrage :

1. un **annuaire LDAP** central contient les comptes, rangés par service ;
2. **un serveur OpenVPN par groupe**, chacun n'acceptant que les membres de son service ;
3. **une plage d'adresses par groupe** : le pare-feu reconnaît le groupe à l'adresse attribuée et applique les règles correspondantes.

Trois groupes sont mis en œuvre dans la maquette (Support, Commerciaux, Administrateurs) ; les autres suivent le même modèle (section 3.4).

### 6.2 L'annuaire LDAP

Le serveur `SRV-LDAP` (Debian 13, sans interface graphique) est placé dans la zone SERVEURS, à l'adresse `10.1.30.10`. Comme pour OPNsense, l'image d'installation a été vérifiée avant usage : son empreinte SHA-256 figure dans la liste publiée par Debian. Le serveur fait fonctionner OpenLDAP, avec la racine `dc=mediconnect,dc=local`.

| Entrée | Rôle |
|---|---|
| `ou=support,ou=people` | Comptes du support (ex. `s.martin`) |
| `ou=commerciaux,ou=people` | Comptes des commerciaux (ex. `c.durand`) |
| `ou=admins,ou=people` | Comptes des administrateurs (ex. `a.bernard`) |
| `cn=opnsense-bind,ou=services` | Compte de service utilisé par le pare-feu pour consulter l'annuaire |

L'annuaire a été durci :

- **Lecture anonyme interdite.** Par défaut, OpenLDAP laissait lister tous les employés sans authentification. Les règles d'accès ont été remplacées : les mots de passe ne sont lisibles par personne (seule la vérification à la connexion est possible), le reste n'est lisible que par le compte de service du pare-feu et par chaque utilisateur pour sa propre fiche. Une recherche anonyme renvoie désormais `No such object`.
- **Compte de service dédié.** Le pare-feu n'utilise pas le compte administrateur de l'annuaire, mais un compte en lecture seule (moindre privilège).
- **Mots de passe hachés.** Ils sont définis avec `ldappasswd` et stockés sous forme hachée ; aucun mot de passe n'est écrit en clair dans un fichier.
- **Communications chiffrées (LDAPS).** Une autorité de certification propre au laboratoire (« MediConnect Lab CA ») a signé le certificat du serveur, valable pour son nom et pour son adresse `10.1.30.10`. L'annuaire n'écoute plus que sur le port 636 (LDAPS) : le port 389, en clair, est fermé. Un mot de passe vérifié par le pare-feu ne circule donc jamais en clair sur le réseau.
- **Aucun accès direct à Internet.** Une carte réseau NAT temporaire a servi à installer les logiciels, puis a été retirée : le serveur ne communique plus qu'à travers le pare-feu.

### 6.3 Liaison entre le pare-feu et l'annuaire

Le pare-feu du siège fait confiance à l'autorité du laboratoire (certificat importé, sans clé privée). Trois serveurs d'authentification LDAP sont déclarés, identiques à un champ près : le **conteneur d'authentification**, qui limite la recherche des comptes au classeur d'un seul service.

| Serveur d'authentification | Conteneur |
|---|---|
| `LDAP-Support` | `ou=support,ou=people,dc=mediconnect,dc=local` |
| `LDAP-Commerciaux` | `ou=commerciaux,ou=people,dc=mediconnect,dc=local` |
| `LDAP-Admins` | `ou=admins,ou=people,dc=mediconnect,dc=local` |

Les tests confirment ce cloisonnement : `c.durand` est acceptée par `LDAP-Commerciaux`, alors que `s.martin` y est refusée **avec un mot de passe correct**, car elle n'appartient pas à ce service.

### 6.4 Les serveurs OpenVPN

| Instance | Port UDP | Plage d'adresses | Authentification | Réseaux annoncés |
|---|---|---|---|---|
| `VPN-Support` | 1194 | `10.8.10.0/24` | `LDAP-Support` | Serveur support |
| `VPN-Admin` | 1195 | `10.8.50.0/24` | `LDAP-Admins` | Bastion (et, temporairement, SRV-LDAP) |
| `VPN-Commerciaux` | 1196 | `10.8.60.0/24` | `LDAP-Commerciaux` | CRM et zone DEMO |

Paramètres communs :

- **Certificat du serveur** émis par une autorité dédiée au VPN (« MediConnect VPN CA »), distincte de celle de l'annuaire, pour séparer les usages.
- **Chiffrement AES-256-GCM**, sans algorithme de repli plus faible.
- **Clé `tls-crypt`** : le canal de contrôle est chiffré et authentifié. Tout paquet qui ne porte pas cette clé est ignoré sans réponse ; un balayage d'Internet ne révèle donc pas l'existence du VPN et ne permet pas de tenter des mots de passe.
- **Authentification par l'annuaire**, limitée au service de l'instance.

Sur le WAN, les trois ports sont ouverts depuis toute adresse : un télétravailleur peut se connecter de n'importe quel réseau. Ce choix est acceptable grâce à `tls-crypt`, qui rend le service muet pour qui ne possède pas le fichier de configuration.

![06-16-instances-openvpn](../captures/06-16-instances-openvpn.png)
*Capture : les trois instances OpenVPN*

### 6.5 Poste de test et fichier de configuration

Le poste `CLIENT-TEST` (Debian 13, adresse `203.0.113.100`) représente un télétravailleur sur Internet. Le fichier de configuration est exporté :

- **sans certificat** : l'option qui aurait inclus le certificat et la clé privée du serveur a été écartée, car elle permettrait à un utilisateur d'usurper le pare-feu ;
- avec **vérification du nom du serveur**, pour détecter un faux serveur ;
- avec **interdiction d'enregistrer le mot de passe** : en cas de vol du poste, le fichier seul ne suffit pas.

Une connexion de `c.durand` reçoit l'adresse `10.8.60.2` : le pare-feu l'identifie comme commerciale.

### 6.6 Règles basées sur l'identité et vérifications

Seul l'annuaire existe à ce stade ; il sert de cible pour démontrer que les groupes n'ont pas les mêmes droits. Une règle unique est créée sur l'interface OpenVPN, tout le reste étant interdit par défaut :

| Source | Destination | Port | Action | Remarque |
|---|---|---|---|---|
| `10.8.50.0/24` (administrateurs) | `10.1.30.10` | TCP 22 | Autoriser, journalisé | Temporaire, remplacé par l'accès via le bastion (section 9) |

| Test | Résultat attendu | Résultat obtenu |
|---|---|---|
| `s.martin` se connecte au VPN des commerciaux | Refus | `AUTH_FAILED` |
| `c.durand` force une route vers SRV-LDAP et tente une connexion SSH | Blocage par le pare-feu | `Connection timed out` |
| `a.bernard` (VPN des administrateurs, `10.8.50.2`) tente une connexion SSH | Autorisation | Le serveur répond |

Le deuxième test est le plus significatif : même un utilisateur qui modifie sa table de routage pour contourner les réseaux annoncés reste bloqué, parce que le contrôle est fait par le pare-feu et non par le poste.

![06-23-test-commercial-bloque](../captures/06-23-test-commercial-bloque.png)
*Capture : la commerciale est bloquée malgré une route forcée*

### 6.7 Difficultés rencontrées

- **Certificat « pas encore valide ».** Le premier test LDAPS a échoué (`certificate is not yet valid`) : l'horloge du pare-feu était en retard sur celle du serveur qui avait émis le certificat. Les pare-feu n'ont ni accès à Internet ni outils de synchronisation avec l'hôte ; leur horloge dérive, en particulier lorsqu'une machine virtuelle est suspendue puis reprise. L'heure a été corrigée manuellement ; une synchronisation NTP centralisée est mise en place dans la partie journalisation. Cet incident illustre la justification de la section 2.4 : sans heure commune, le chiffrement, l'authentification multifacteur et la corrélation des journaux sont compromis.
- **Saisie dans les consoles.** Le copier-coller n'étant pas possible dans la console VMware, la configuration des serveurs Debian a été faite en SSH depuis le poste d'administration, pendant la phase d'installation.

### 6.8 Limites

- **Pas de second facteur pour le VPN.** L'accès repose sur le fichier de configuration (clé `tls-crypt`) et sur le mot de passe. En production, un code à usage unique (TOTP), au minimum pour les administrateurs, ou un certificat par utilisateur renforcerait l'authentification.
- **Clé `tls-crypt` commune aux trois instances.** Un fichier de configuration valide pour un groupe permet d'atteindre les autres instances en changeant seulement le port (la maquette l'a d'ailleurs utilisé pour tester le VPN des administrateurs). La barrière restante est l'annuaire, qui refuse les comptes d'un autre service. Une clé distincte par instance ajouterait une barrière supplémentaire.
- **Appartenance à un groupe par emplacement dans l'annuaire.** Un compte ne peut appartenir qu'à un seul service. Une gestion par groupes LDAP permettrait des appartenances multiples, au prix d'une configuration plus complexe.
- **Annuaire unique.** Sa panne empêcherait toute connexion VPN ; un second serveur répliqué serait nécessaire en production.
- **Autorité de certification du laboratoire.** Sa clé est conservée sur le serveur d'annuaire et aucune liste de révocation n'est publiée ; en production, la clé serait conservée hors ligne.
- **Règle SSH temporaire.** L'accès direct des administrateurs à SRV-LDAP sera remplacé par un passage obligatoire par le bastion.

---

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

![07-14-journal-securite](../captures/07-14-journal-securite.png)
*Capture : événements de sécurité du portail dans le journal*

### 7.8 Difficultés rencontrées

1. **Connexion à la base bloquée (délai dépassé).** La règle du pare-feu n'autorise que la source `10.1.10.20`, mais le serveur, qui porte deux adresses, utilisait la première (`10.1.10.10`) pour sortir : le pare-feu bloquait à juste titre. La route vers la zone SERVEURS impose désormais l'adresse source `10.1.10.20`. La règle est restée aussi stricte qu'avant : on a corrigé le serveur, pas assoupli le filtrage.
2. **Authentification refusée par la base.** Le mot de passe du compte applicatif avait été altéré par un copier-coller dans la console. Il est maintenant transféré par `scp` entre les serveurs, sans intermédiaire humain.
3. **Règle de redirection sans effet.** Le champ « Firewall rule » de la redirection de port était sur `Manual` : aucune règle de passage n'était créée, le trafic redirigé aurait été bloqué. Il a été placé sur `Pass`.
4. **Codes à usage unique refusés alors que le téléphone était à l'heure.** Après deux jours d'arrêt de la maquette, l'horloge du serveur avait deux heures d'avance, soit exactement l'écart entre l'heure de Paris et l'heure UTC : une heure locale a vraisemblablement été prise pour une heure UTC. Le code calculé par le serveur pour vérification était différent de celui du téléphone. Le journal conserve la trace du saut d'horloge lors de la correction. Cet incident confirme la justification de la section 2.4 : sans heure commune, l'authentification multifacteur est inutilisable. Une synchronisation NTP est mise en place dans la partie journalisation.

### 7.9 Limites

- **Certificat auto-signé.** Le navigateur affiche un avertissement ; en production, un certificat d'une autorité publique serait utilisé. La connexion du serveur web à PostgreSQL est chiffrée mais le certificat de la base n'est pas vérifié (`sslmode=require` et non `verify-full`).
- **Pare-feu applicatif ajouté ensuite.** À ce stade, le reverse proxy filtre le débit et les en-têtes mais n'analyse pas le contenu des requêtes ; le WAF (ModSecurity et règles OWASP), ajouté en section 8.5, comble ce manque.
- **Blocage par session, non par compte.** Après 5 codes faux, la session est détruite, mais un attaquant qui connaît le mot de passe peut recommencer ; seule la limitation de débit de Nginx le ralentit. En production, le compte serait verrouillé temporairement après plusieurs échecs.
- **Secret TOTP stocké en clair dans la base**, et pas de codes de secours si le téléphone est perdu. En production, le secret serait chiffré et une procédure de récupération serait prévue.
- **Reverse proxy et serveur web sur la même machine.** Un attaquant qui compromet l'un atteint l'autre (limite déjà signalée en section 2.5). La base de données partage aussi sa machine avec l'annuaire, pour économiser les ressources.
- **Test depuis un tunnel SSH.** Le navigateur de l'administrateur n'est pas sur le réseau « Internet » de la maquette : les tests de l'interface ont été faits par un tunnel temporaire, ce qui explique que les journaux affichent l'adresse source `10.1.10.10`. Le test depuis un vrai client Internet (`203.0.113.100`) n'a porté que sur l'accès HTTPS.
- **Cartes réseau d'installation.** Les cartes NAT de SRV-DMZ et du serveur de base de données sont conservées le temps de la maquette pour les installations ; elles seraient retirées en production.
- **Journaux.** Les journaux du portail, d'abord conservés sur SRV-DMZ, sont ensuite copiés sur le serveur de journalisation de la zone ADMIN (section 10).

---

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

![08-22-site2-support-ok](../captures/08-22-site2-support-ok.png)
*Capture : le site secondaire atteint le serveur support du siège*

### 8.7 Difficultés rencontrées

- **Noms proches dans les listes.** Une règle DNS de la DMZ visait « DEMO address » au lieu de « DMZ address ». L'erreur, détectée en relisant la liste complète des règles, aurait ouvert un flux vers la mauvaise zone ; chaque liste de règles a ensuite été relue colonne par colonne.
- **Ordre des règles.** La règle autorisant l'envoi des journaux de la DMZ avait été créée après la règle de blocage : les journaux du pare-feu affichaient le blocage avec le nom de la règle responsable, ce qui a permis de corriger l'ordre immédiatement.
- **Serveur d'authentification jamais testé.** Le premier test du VPN du support a échoué (`AUTH_FAILED`) : le conteneur de recherche du serveur `LDAP-Support` contenait une erreur. Le testeur d'authentification du pare-feu (« User DN not found ») a localisé le problème. Les trois serveurs d'authentification ont ensuite été testés avec succès.
- **Route perdue au redémarrage.** Après un redémarrage du serveur de la DMZ, le portail affichait une erreur interne : la route vers la base de données, qui impose l'adresse source du serveur web, était déclarée avant que cette adresse existe et n'était donc pas créée au démarrage. La route a été rattachée à la déclaration de l'adresse elle-même. Le pare-feu, en refusant la mauvaise adresse source, a empêché un contournement silencieux de la règle.
- **Tunnel non rétabli.** Après le redémarrage des machines virtuelles, le tunnel IPsec ne s'était pas reconstruit ; le diagnostic (aucune trace dans les journaux du siège, puis état du tunnel) a conduit à relancer le service IPsec.



---

## 9. Sécurisation de l'administration

### 9.1 Exigence

Le sujet impose que les flux d'administration soient séparés des flux des utilisateurs : un utilisateur connecté au LAN ne doit pas pouvoir administrer les équipements. Les équipements à administrer sont les deux pare-feu (qui sont aussi les passerelles VPN), les serveurs et les services de sécurité.

### 9.2 Mesures mises en œuvre

| Mesure | Mise en œuvre | Section |
|---|---|---|
| Réseau d'administration dédié | Zone ADMIN `10.1.99.0/24` au siège, réseau `10.2.99.0/24` pour le pare-feu du site secondaire ; aucun utilisateur n'y est raccordé | 3, 4 |
| Interface d'administration des pare-feu limitée | L'interface web n'écoute que sur l'interface d'administration ; HTTPS uniquement ; une règle n'autorise qu'un seul poste (`10.1.99.50` au siège, `10.2.99.50` au site secondaire) | 4, 5 |
| LAN sans droit d'administration | Règle « anti-verrouillage » désactivée et règles par défaut du LAN supprimées : depuis le LAN, l'interface d'administration n'est plus joignable | 4 |
| Administration à distance réservée | VPN dédié aux administrateurs (`VPN-Admin`), authentifié par l'annuaire et limité au groupe `admins` ; les autres groupes VPN n'ont aucun accès à l'administration | 6 |
| Comptes de service à privilèges minimaux | Le pare-feu interroge l'annuaire avec un compte en lecture seule ; le portail utilise un compte de base de données limité | 6, 7 |
| Mots de passe distincts et secrets protégés | Mot de passe administrateur différent sur chaque pare-feu ; secrets générés aléatoirement, stockés dans des fichiers lisibles par le seul compte concerné, transférés par `scp` ; aucun secret dans le dépôt de code (fichier `.gitignore`) | 5, 7 |
| Logiciels vérifiés | Empreinte SHA-256 des images OPNsense et Debian comparée à la liste officielle avant installation | 4, 6 |
| Serveur de journalisation dans la zone ADMIN | Joignable depuis le poste d'administration sans traverser une zone utilisateur ; aucune zone ne peut l'administrer | 10 |
| Retour arrière possible | Instantanés des machines virtuelles à chaque étape validée | 4 |

Le serveur de journalisation montre le modèle cible : il est administré en SSH depuis le poste d'administration, sur le réseau ADMIN, sans aucun passage par une zone utilisateur.

### 9.3 Ce qui n'est pas réalisé

- **Bastion d'administration.** L'adresse `10.1.99.10` et l'alias `H_BASTION` sont réservés, mais le bastion n'a pas été déployé. Dans la maquette, les serveurs Debian ont été administrés par la console des machines virtuelles et, pendant la phase d'installation, en SSH par leurs cartes réseau temporaires. En production, tout accès SSH aux serveurs passerait obligatoirement par le bastion (seule source autorisée sur le port 22), avec une authentification forte et l'enregistrement des sessions ; la règle temporaire « administrateurs VPN vers l'annuaire en SSH » serait remplacée par « administrateurs VPN vers le bastion ».
- **Comptes nominatifs.** Les pare-feu sont administrés avec le compte `root`. En production, chaque administrateur aurait son propre compte (authentifié par l'annuaire), ce qui rend chaque action attribuable dans les journaux.
- **Second facteur pour les administrateurs.** Ni l'interface des pare-feu ni le VPN des administrateurs n'exigent de code à usage unique ; OPNsense le permet et ce serait la première mesure à ajouter.

---

## 10. Stratégie de journalisation et synchronisation de l'heure

### 10.1 Ce qui est journalisé

| Source | Événements | Utilité |
|---|---|---|
| Pare-feu du siège | Chaque blocage par la règle finale d'une zone, avec le nom de la règle ; chaque passage par une règle sensible (base de données, CRM, portail DEMO, journalisation, accès Internet au portail) | Prouver qui a tenté quoi, et quelle règle a décidé |
| Pare-feu du siège | Connexions et authentifications VPN, état du tunnel IPsec | Suivre les accès distants |
| Portail (application) | `echec_mot_de_passe`, `echec_totp` (avec le numéro d'essai), `totp_active`, `connexion_reussie`, avec l'adresse source | Détecter une attaque sur les comptes des médecins |
| WAF | Motif de chaque requête bloquée (injection SQL, score d'anomalie) | Comprendre une attaque applicative |
| Nginx | Accès au portail | Reconstituer une session |

Les flux autorisés très fréquents (DNS, heure) ne sont pas journalisés, pour que les événements utiles restent lisibles.

### 10.2 Centralisation

Les journaux restent sur chaque machine, mais une copie est envoyée en temps réel au serveur `SRV-LOGS` (`10.1.99.20`, zone ADMIN), qui les classe dans un fichier par machine émettrice.

| Choix | Justification |
|---|---|
| Serveur dans la zone ADMIN | Un attaquant qui compromet la DMZ ou un serveur ne peut pas effacer la copie de ses traces : aucune zone n'a d'accès d'administration à ce serveur |
| Seule exception DMZ → ADMIN : TCP 514 vers ce seul serveur | Le serveur de journalisation ne fait que recevoir ; la règle est journalisée elle-même |
| Envoi en TCP avec file d'attente sur disque (serveurs Debian) | Aucun message perdu si le serveur de journalisation est momentanément injoignable : les messages attendent puis sont renvoyés |
| Format RFC 5424 (pare-feu) | Chaque ligne porte son fuseau horaire ; sans lui, les heures du pare-feu (en UTC) étaient interprétées comme l'heure de Paris |
| Conservation de 52 semaines, compressée | Permet d'analyser un incident découvert tardivement |

| Machine émettrice | Envoi |
|---|---|
| Pare-feu du siège | UDP 514, tous les journaux |
| Serveur de la DMZ (portail, Nginx, WAF) | TCP 514, tous les journaux, dont le journal du WAF |

![08-18-logs-dmz-centralises](../captures/08-18-logs-dmz-centralises.png)
*Capture : blocage du WAF reçu sur le serveur central*

![08-20-syslog-autorise](../captures/08-20-syslog-autorise.png)
*Capture : envoi des journaux de la DMZ, d'abord bloqué, puis autorisé par sa règle*

### 10.3 Une heure commune

Des journaux ne sont exploitables que si toutes les machines ont la même heure ; l'authentification multifacteur l'exige aussi (section 7).

| Machine | Source de temps |
|---|---|
| Pare-feu du siège | Référence de la maquette (mode « orphelin », strate 10) : sans accès à Internet, il ne peut pas joindre de serveur public |
| Serveurs de chaque zone | Passerelle de leur zone (`10.1.10.1`, `10.1.20.1`, `10.1.30.1`, `10.1.99.1`), autorisée par les règles NTP de chaque zone |
| Pare-feu du site secondaire | Pare-feu du siège, à travers le tunnel (`10.255.0.1`) |

### 10.4 Difficultés rencontrées

- **Réponses perdues.** Le serveur de journalisation, qui avait encore sa carte d'installation, renvoyait ses réponses par celle-ci : la DMZ ne parvenait pas à établir la connexion. Des routes vers les réseaux internes via le pare-feu ont corrigé le problème.
- **Ordre des règles.** Les journaux de la DMZ étaient d'abord bloqués par la règle finale de la zone : la règle d'autorisation avait été placée après elle (section 8.7).
- **La même heure n'est pas la bonne heure.** Le pare-feu de référence, réglé à la main, avait quelques minutes d'avance : toutes les machines étaient d'accord entre elles, mais les codes à usage unique, calculés par un téléphone à l'heure exacte, étaient refusés. L'heure du pare-feu a été corrigée à la seconde près.

### 10.5 Limites

- **Couverture partielle.** Seuls le pare-feu du siège et le serveur de la DMZ envoient leurs journaux ; le pare-feu du site secondaire, l'annuaire et le serveur DEMO les conservent localement. Le principe est le même et serait étendu en production.
- **Pas d'analyse automatique.** Les journaux sont collectés mais pas analysés : un outil de corrélation (SIEM) déclencherait des alertes, par exemple après plusieurs échecs de code à usage unique.
- **Transport non chiffré et non signé.** Les journaux circulent en clair sur le réseau interne, et le pare-feu les envoie en UDP, sans garantie de réception ; en production, on utiliserait syslog sur TLS.
- **Heure de référence non garantie exacte.** En production, le pare-feu se synchroniserait sur plusieurs serveurs de temps publics.

---

## 11. Tests réalisés et limites de la solution

### 11.1 Démarche

Chaque mesure a été testée deux fois : une fois pour vérifier que le flux légitime passe, une fois pour vérifier que le flux interdit est bloqué. Un blocage n'est retenu comme preuve que si le paquet atteint réellement le pare-feu : lors des tests VPN, une route forcée envoie tout le trafic dans le tunnel, de sorte que seul le pare-feu décide. Chaque décision est confirmée par les journaux, qui indiquent la règle appliquée.

### 11.2 Synthèse des tests

| Objectif du sujet | Test | Attendu | Obtenu | Section |
|---|---|---|---|---|
| Interconnexion sécurisée des sites | Phases IKE et ESP, identifiants de session croisés | Tunnel établi | `ESTABLISHED`, `INSTALLED` | 5 |
| | Site secondaire vers serveur support du siège | Autorisé | Connexion réussie | 8.6 |
| | Site secondaire vers annuaire du siège | Bloqué | Délai dépassé | 8.6 |
| Accès distant des employés | Compte du support sur le VPN des commerciaux | Refusé | `AUTH_FAILED` | 6 |
| Politiques selon l'identité | Commerciale vers CRM / vers serveur support | Autorisé / bloqué | `200 OK` / délai dépassé | 8.3 |
| | Support vers serveur support / vers CRM | Autorisé / bloqué | `200 OK` / délai dépassé | 8.3 |
| | Commerciale vers annuaire (route forcée) | Bloqué | Délai dépassé | 6 |
| | Administrateur vers annuaire (SSH) | Autorisé | Le serveur répond | 6 |
| Accès Internet des patients | Requête HTTPS depuis Internet | Page du portail | `200 OK`, en-têtes de sécurité | 7 |
| | Prise de rendez-vous | Enregistrée | Confirmation | 7 |
| Accès authentifié des médecins | Mot de passe puis code TOTP | Accès | Espace médecin | 7 |
| | Mauvais mot de passe | Refus sans indice | Message neutre, journalisé | 7 |
| | Cinq codes faux | Session détruite | Retour à la connexion, journalisé | 7 |
| Exposition sécurisée du portail | Injection SQL | Bloquée | `403 Forbidden` | 8.5 |
| | Usage normal avec WAF actif | Aucune gêne | Parcours complet réussi | 8.5 |
| | Base de données depuis le serveur web | Autorisé, chiffré | `ssl = t` | 7 |
| Séparation production / démonstration | Zone DEMO vers base, annuaire, portail de production | Bloqué | Bloqué (×3) | 8.4 |
| | Commerciale vers portail DEMO | Autorisé | `200 OK`, page de démonstration | 8.4 |
| Contrôle applicatif | Requête malveillante dans un flux autorisé (port 443) | Bloquée | `403`, motif dans le journal | 8.5 |
| Administration sécurisée | Accès web au pare-feu depuis le poste d'administration | Autorisé | Page affichée | 4 |
| | Ping vers le pare-feu depuis ce même poste | Bloqué | Sans réponse | 4 |
| Journalisation | Journaux du pare-feu et du WAF sur le serveur central | Reçus | Fichier par machine | 10 |
| | Journaux de la DMZ sans règle d'autorisation | Bloqués | Blocage visible dans les journaux | 10 |

### 11.3 Limites de la solution

Les limites sont classées par importance. Pour chacune, la mesure de production est indiquée.

**Fonctions partiellement couvertes**

| Limite | En production |
|---|---|
| Contrôle applicatif limité au trafic web du portail (WAF) ; pas d'IPS sur le pare-feu, faute d'accès Internet pour télécharger les signatures | IPS Suricata en mode blocage sur les interfaces internes, ou pare-feu de nouvelle génération reconnaissant les applications |
| Pas de bastion : l'administration des serveurs n'est pas centralisée | Bastion seul autorisé en SSH, avec authentification forte et enregistrement des sessions |
| Pas de VLAN par service sur les LAN ; trois groupes VPN sur six mis en œuvre | VLAN par service (le plan d'adressage les prévoit), authentification des postes 802.1X, groupes restants sur le même modèle |
| Journalisation centralisée pour deux sources seulement, sans analyse | Toutes les machines, transport TLS, outil de corrélation et d'alerte |

**Authentification**

| Limite | En production |
|---|---|
| Pas de second facteur pour le VPN ni pour l'administration | Code TOTP au minimum pour les administrateurs |
| Clé pré-partagée pour le tunnel IPsec, clé `tls-crypt` commune aux VPN | Certificats pour IPsec, une clé par instance VPN |
| Certificats auto-signés (portail) ou d'une autorité de laboratoire | Certificat public pour le portail, autorité interne avec clé hors ligne et liste de révocation |
| Verrouillage après 5 codes faux par session, et non par compte ; secret TOTP non chiffré en base | Verrouillage temporaire du compte, secret chiffré, codes de secours |

**Architecture de la maquette**

| Limite | En production |
|---|---|
| Un seul pare-feu, un seul annuaire, un seul tunnel : aucune redondance | Pare-feu en haute disponibilité, annuaire répliqué, second lien |
| Rôles regroupés sur une même machine (reverse proxy et serveur web ; annuaire et base de données) | Une machine, voire un segment, par rôle |
| Heure de référence locale (mode orphelin), Internet simulé, plages de documentation | Serveurs de temps publics, vrais accès Internet et adresses publiques |
| Cartes réseau d'installation conservées sur certains serveurs | Installation depuis un miroir interne, aucune sortie directe |
| Tunnel IPsec non relancé automatiquement après un redémarrage | Relance automatique et supervision du tunnel |

---

## 12. Conclusion

La maquette met en œuvre une architecture où **chaque flux est justifié, filtré et journalisé** : deux sites reliés par un tunnel IPsec chiffré, des accès distants dont les droits dépendent de l'identité de l'utilisateur dans l'annuaire, un portail exposé uniquement en HTTPS derrière un reverse proxy et un pare-feu applicatif, des médecins authentifiés par deux facteurs, une zone de démonstration incapable d'atteindre la production, et une administration isolée des utilisateurs.

Trois principes ont guidé tous les choix : **tout interdire par défaut**, **n'ouvrir que le strict nécessaire** et **conserver une trace** de chaque décision. Les tests le montrent : deux utilisatrices connectées au même pare-feu par le même type de VPN obtiennent des droits différents, une attaque cachée dans un flux autorisé est bloquée, et chaque refus apparaît dans les journaux avec le nom de la règle responsable.

Les difficultés rencontrées ont aussi été instructives. Plusieurs « pannes » étaient en réalité le pare-feu qui faisait son travail : la bonne réponse a toujours été de corriger la machine ou l'ordre des règles, jamais d'assouplir le filtrage. Et la synchronisation de l'heure, qui semblait un détail, s'est révélée indispensable à l'authentification multifacteur, aux certificats et à la lecture des journaux.

Les principales évolutions pour une mise en production seraient un IPS sur le pare-feu, un bastion d'administration, des VLAN par service, un second facteur pour les administrateurs et la redondance des équipements critiques.

---

## Annexe : captures complémentaires

Les captures ci-dessous complètent les sections du rapport ; elles sont classées par section.

### Annexe 4 – 4. Mise en place de la topologie : pare-feu du siège

![03-01-verification-iso](../captures/03-01-verification-iso.png)
*Capture : 03-01-verification-iso*

![03-02-vm-cartes-reseau](../captures/03-02-vm-cartes-reseau.png)
*Capture : 03-02-vm-cartes-reseau*

![03-03-opnsense-installe](../captures/03-03-opnsense-installe.png)
*Capture : 03-03-opnsense-installe*

![03-04-assignation-interfaces](../captures/03-04-assignation-interfaces.png)
*Capture : 03-04-assignation-interfaces*

![03-05-interfaces-configurees](../captures/03-05-interfaces-configurees.png)
*Capture : 03-05-interfaces-configurees*

![03-10-interfaces-nommees](../captures/03-10-interfaces-nommees.png)
*Capture : 03-10-interfaces-nommees*

![03-07-dashboard-opnsense](../captures/03-07-dashboard-opnsense.png)
*Capture : 03-07-dashboard-opnsense*

![03-08-seul-https-autorise](../captures/03-08-seul-https-autorise.png)
*Capture : 03-08-seul-https-autorise*

### Annexe 5 – 5. VPN site-à-site IPsec

![04-01-vm-fw-site2](../captures/04-01-vm-fw-site2.png)
*Capture : machine virtuelle FW-SITE2 et ses trois cartes réseau*

![04-02-interfaces-site2](../captures/04-02-interfaces-site2.png)
*Capture : interfaces et adresses de FW-SITE2*

![04-03-regle-admin-site2](../captures/04-03-regle-admin-site2.png)
*Capture : règle d'accès d'administration limitée au poste 10.2.99.50*

![04-04-regles-lan-site2-supprimees](../captures/04-04-regles-lan-site2-supprimees.png)
*Capture : aucune règle sur le LAN, tout est interdit par défaut*

![04-05-bogon-desactive](../captures/04-05-bogon-desactive.png)
*Capture : blocage des réseaux bogon désactivé sur le WAN*

![05-01-regles-wan-ipsec](../captures/05-01-regles-wan-ipsec.png)
*Capture : les trois règles WAN de FW-SIEGE, limitées à l'adresse du site secondaire*

![05-02-ipsec-connexion-siege](../captures/05-02-ipsec-connexion-siege.png)
*Capture : connexion IPsec du siège (sans la clé)*

![05-03-vti-siege](../captures/05-03-vti-siege.png)
*Capture : interface virtuelle du tunnel*

![05-07-child-policies](../captures/05-07-child-policies.png)
*Capture : politiques IPsec désactivées dans le tunnel*

![05-06-regle-ipsec-site2](../captures/05-06-regle-ipsec-site2.png)
*Capture : règle de test sur l'interface IPsec du site secondaire*

![05-04b-ipsec-etabli-site2](../captures/05-04b-ipsec-etabli-site2.png)
*Capture : le même tunnel vu depuis le site secondaire, SPI croisés*

### Annexe 6 – 6. VPN d'accès distant et authentification par l'annuaire

![06-01-verification-iso-debian](../captures/06-01-verification-iso-debian.png)
*Capture : empreinte de l'image Debian présente dans la liste officielle*

![06-05-ldap-utilisateurs](../captures/06-05-ldap-utilisateurs.png)
*Capture : comptes par service et vérification d'un mot de passe*

![06-06-ldap-acl](../captures/06-06-ldap-acl.png)
*Capture : lecture anonyme refusée, lecture autorisée pour le compte de service*

![06-07-ldaps](../captures/06-07-ldaps.png)
*Capture : seul le port 636 est ouvert, connexion chiffrée vérifiée*

![06-08-srv-ldap-reseau](../captures/06-08-srv-ldap-reseau.png)
*Capture : adresse définitive dans la zone SERVEURS*

![06-10-serveurs-ldap](../captures/06-10-serveurs-ldap.png)
*Capture : les trois serveurs d'authentification*

![06-11-test-ldap-ok](../captures/06-11-test-ldap-ok.png)
*Capture : authentification réussie d'une commerciale*

![06-12-test-ldap-refus](../captures/06-12-test-ldap-refus.png)
*Capture : refus d'un compte du support sur le serveur des commerciaux*

![06-17-regles-wan-openvpn](../captures/06-17-regles-wan-openvpn.png)
*Capture : règles WAN des VPN*

![06-18-client-export](../captures/06-18-client-export.png)
*Capture : export de la configuration, sans certificat*

![06-21-connection-status](../captures/06-21-connection-status.png)
*Capture : session VPN de c.durand, adresse 10.8.60.2*

![06-22-vpn-refus-identite](../captures/06-22-vpn-refus-identite.png)
*Capture : connexion refusée pour un compte d'un autre service*

![06-24-test-admin-autorise](../captures/06-24-test-admin-autorise.png)
*Capture : l'administrateur atteint le serveur*

![06-25-regle-openvpn](../captures/06-25-regle-openvpn.png)
*Capture : règle de l'interface OpenVPN*

![06-26-log-blocage](../captures/06-26-log-blocage.png)
*Capture : le blocage apparaît dans les journaux du pare-feu*

![06-11a-erreur-horloge](../captures/06-11a-erreur-horloge.png)
*Capture : refus du certificat dû au décalage d'horloge*

### Annexe 7 – 7. Portail web, reverse proxy et authentification multifacteur

![07-01-srv-dmz-installe](../captures/07-01-srv-dmz-installe.png)
*Capture : SRV-DMZ installé*

![07-03-connexion-base-chiffree](../captures/07-03-connexion-base-chiffree.png)
*Capture : connexion du compte applicatif à la base, chiffrée (`ssl = t`)*

![07-04-comptes-medecins](../captures/07-04-comptes-medecins.png)
*Capture : comptes des médecins, second facteur non encore activé*

![07-05-service-portail](../captures/07-05-service-portail.png)
*Capture : service du portail actif*

![07-10-enrolement-totp](../captures/07-10-enrolement-totp.png)
*Capture : enrôlement du second facteur (QR code masqué)*

![07-02-regle-dmz-base](../captures/07-02-regle-dmz-base.png)
*Capture : règle DMZ vers la base de données*

![07-07-nat-portail](../captures/07-07-nat-portail.png)
*Capture : redirection du port 443 vers le reverse proxy*

![07-08-acces-internet-portail](../captures/07-08-acces-internet-portail.png)
*Capture : réponse du portail depuis le poste Internet*

![07-09-prise-rendez-vous](../captures/07-09-prise-rendez-vous.png)
*Capture : prise de rendez-vous par un patient*

![07-13-refus-authentification](../captures/07-13-refus-authentification.png)
*Capture : refus d'un mot de passe incorrect*

![07-12-echecs-totp-journal](../captures/07-12-echecs-totp-journal.png)
*Capture : codes refusés, code attendu côté serveur différent de celui du téléphone (horloge décalée)*

### Annexe 8 – 8. Politique de filtrage, règles d'identité et contrôle applicatif

![08-01-alias](../captures/08-01-alias.png)
*Capture : alias du pare-feu du siège*

![08-02-regles-dmz](../captures/08-02-regles-dmz.png)
*Capture : règles de la DMZ*

![08-03-regles-serveurs](../captures/08-03-regles-serveurs.png)
*Capture : règles de la zone SERVEURS*

![08-04-regles-demo](../captures/08-04-regles-demo.png)
*Capture : règles de la zone DEMO*

![08-05-regles-vpn-identite](../captures/08-05-regles-vpn-identite.png)
*Capture : règles basées sur l'identité (interface OpenVPN)*

![08-06-test-commerciale](../captures/08-06-test-commerciale.png)
*Capture : la commerciale atteint le CRM, pas le serveur support*

![08-07-test-support](../captures/08-07-test-support.png)
*Capture : le support atteint son serveur, pas le CRM*

![08-13-commerciale-demo](../captures/08-13-commerciale-demo.png)
*Capture : accès de la commerciale au portail de démonstration par le VPN*

![08-11-waf-journal](../captures/08-11-waf-journal.png)
*Capture : motif du blocage dans le journal du WAF*

![08-25-portail-avec-waf](../captures/08-25-portail-avec-waf.png)
*Capture : parcours complet d'un médecin (mot de passe, code TOTP, rendez-vous) avec le WAF actif*

![08-21-regles-tunnel-siege](../captures/08-21-regles-tunnel-siege.png)
*Capture : règles appliquées au trafic venant du site secondaire*

![08-23-site2-annuaire-bloque](../captures/08-23-site2-annuaire-bloque.png)
*Capture : l'annuaire du siège reste inaccessible depuis le site secondaire*

![08-09-ldap-support-corrige](../captures/08-09-ldap-support-corrige.png)
*Capture : authentification du compte du support après correction*

![08-24-ldap-admins-ok](../captures/08-24-ldap-admins-ok.png)
*Capture : authentification d'un administrateur*

### Annexe 10 – 10. Stratégie de journalisation et synchronisation de l'heure

![08-16-srv-logs](../captures/08-16-srv-logs.png)
*Capture : serveur de journalisation à l'écoute*

![08-17-logs-pare-feu-centralises](../captures/08-17-logs-pare-feu-centralises.png)
*Capture : journaux du pare-feu reçus sur le serveur central*

![08-14-ntp-pare-feu](../captures/08-14-ntp-pare-feu.png)
*Capture : service de temps du pare-feu, limité aux interfaces internes*

![08-15-ntp-serveur](../captures/08-15-ntp-serveur.png)
*Capture : serveur synchronisé sur sa passerelle*
