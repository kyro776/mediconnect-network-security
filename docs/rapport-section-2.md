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
