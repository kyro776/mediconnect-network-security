## 3. Plan d'adressage

### 3.1 Principes de conception

1. **Adresses privées RFC 1918, dans `10.0.0.0/8`.** Le `192.168.0.0/16` est évité : les box des domiciles utilisent presque toutes `192.168.0.0/24` ou `192.168.1.0/24`, ce qui créerait un conflit de routage pour un télétravailleur connecté au VPN.
2. **Un sous-réseau par zone de sécurité**, pour écrire une règle de filtrage par zone.
3. **Une structure lisible : `10.<site>.<zone>.0/24`.** Le deuxième octet identifie le site (1 siège, 2 site secondaire, 8 VPN) et le troisième la zone.
4. **Aucun chevauchement** entre les sites, les zones et les pools VPN.
5. **Des masques `/24`** : 254 hôtes par zone, suffisant et lisible.

### 3.2 Sous-réseaux du siège

| Zone | Sous-réseau | Passerelle (pare-feu) |
|---|---|---|
| DMZ | `10.1.10.0/24` | `10.1.10.1` |
| DEMO | `10.1.20.0/24` | `10.1.20.1` |
| SERVEURS | `10.1.30.0/24` | `10.1.30.1` |
| LAN-USERS | `10.1.40.0/24` | `10.1.40.1` |
| ADMIN | `10.1.99.0/24` | `10.1.99.1` |

### 3.3 Site secondaire

| Zone | Sous-réseau | Passerelle |
|---|---|---|
| LAN-SITE2 | `10.2.40.0/24` | `10.2.40.1` |

### 3.4 VPN d'accès distant : un pool par groupe

| Groupe | Pool d'adresses | Ressources autorisées |
|---|---|---|
| Support | `10.8.10.0/24` | Applications de support |
| Comptabilité | `10.8.20.0/24` | Serveurs comptables |
| Employés | `10.8.30.0/24` | Ressources bureautiques |
| Informaticiens | `10.8.40.0/24` | Ressources techniques autorisées |
| Administrateurs | `10.8.50.0/24` | Infrastructure d'administration |
| Commerciaux | `10.8.60.0/24` | CRM et zone DEMO uniquement |

L'identité de l'utilisateur est traduite en règles réseau : à la connexion, son groupe dans l'annuaire LDAP détermine le pool d'adresses qu'il reçoit, et les règles de pare-feu s'appliquent à chaque pool.

### 3.5 Liaisons entre sites et accès Internet

| Lien | Adresse | Remarque |
|---|---|---|
| Tunnel IPsec site-à-site | `10.255.0.0/30` | Siège `.1`, site 2 `.2` |
| WAN siège | `203.0.113.2/24` | Plage de documentation (RFC 5737) |
| WAN site 2 | `203.0.113.3/24` | Même segment : Internet simulé |
| Client Internet de test | `203.0.113.100/24` | Simule patients, médecins, attaquant |

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

Conventions : `.1` est la passerelle, les serveurs ont des adresses fixes à partir de `.10`, les postes reçoivent du DHCP de `.100` à `.200`.

### 3.7 Limites du plan

- Le plan `10.x.x.x` peut entrer en conflit avec un réseau utilisant la même plage (cabinet médical, entreprise).
- Le segment WAN unique simule Internet sans reproduire deux opérateurs distincts.
