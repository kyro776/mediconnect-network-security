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
