## 2. Architecture et zones de sécurité

### 2.1 Choix architecturaux

- **Un pare-feu par site**, chacun connecté à son propre accès Internet. Les deux sites sont reliés par un tunnel VPN IPsec site-à-site.
- **Un pare-feu central au siège, doté d'une interface par zone de sécurité.** Tout flux entre deux zones traverse ce pare-feu : la politique est appliquée en un point unique et chaque flux peut être journalisé.
- **Les VPN d'accès distant se terminent au siège**, là où se trouvent les serveurs. Les utilisateurs distants arrivent dans une zone dédiée et sont filtrés comme n'importe quel autre flux.
- **Politique par défaut « tout interdit »** : seuls les flux explicitement nécessaires sont autorisés.

### 2.2 Zones de sécurité et niveaux de confiance

| Zone | Contenu | Niveau de confiance |
|---|---|---|
| INTERNET | Patients, médecins, attaquants potentiels | 0 : non fiable |
| DMZ | Reverse proxy, serveur web du portail | 1 : exposée |
| DEMO | Copie simplifiée du portail, données fictives | 2 : isolée, jetable |
| VPN-USERS | Télétravailleurs et commerciaux connectés par VPN | 2 à 3 : selon le groupe |
| LAN-USERS | Postes des employés (siège et site secondaire) | 3 : interne |
| SERVEURS | Annuaire LDAP, base de données, CRM, comptabilité, support | 4 : sensible |
| ADMIN | Bastion d'administration, serveur de journalisation | 5 : critique |

### 2.3 Justification des zones

**DMZ.** Le portail doit être joignable depuis Internet, ce qui l'expose aux attaques. Il est placé dans une zone dédiée, séparée du réseau interne. Si la DMZ est compromise, l'attaquant n'a aucun accès direct aux serveurs internes.

**Base de données en zone SERVEURS.** Seul le serveur web peut l'interroger, sur un port unique et avec une connexion initiée depuis la DMZ.

**DEMO.** Les démonstrations n'utilisent jamais la production. La zone contient des données fictives et n'a aucun accès vers les autres zones internes.

**VPN-USERS.** Les utilisateurs distants viennent de réseaux non maîtrisés. Leur zone est subdivisée en pools d'adresses par groupe, ce qui permet d'appliquer des règles selon leur identité.

**LAN-USERS.** Les postes des employés sont des cibles privilégiées. Ils n'accèdent qu'aux serveurs nécessaires, jamais à l'administration.

**SERVEURS.** Cette zone concentre les données sensibles et n'est jamais joignable directement depuis Internet.

**ADMIN.** Les flux d'administration sont isolés des flux utilisateurs. Le serveur de journalisation y est placé pour qu'un attaquant ayant compromis la DMZ ne puisse pas effacer les traces.

### 2.4 Flux autorisés

| Source | Destination | Autorisé | Justification |
|---|---|---|---|
| INTERNET | DMZ | HTTPS (443) vers le reverse proxy uniquement | Seul service public |
| INTERNET | Autres zones | Interdit | Aucune confiance |
| DMZ | SERVEURS | Serveur web vers base de données, port dédié | Fonctionnement du portail |
| DMZ | LAN, ADMIN, DEMO | Interdit | Limiter la propagation |
| DEMO | Zones internes | Interdit | Zone isolée et jetable |
| VPN-USERS | SERVEURS, DEMO | Selon le pool (groupe) | Moindre privilège |
| LAN-USERS | SERVEURS | Selon le profil | Moindre privilège |
| LAN-USERS | ADMIN | Interdit | Séparation de l'administration |
| ADMIN | Toutes les zones | Protocoles d'administration depuis le bastion | Administration sécurisée |
| Toutes les zones | Serveur de logs | Syslog uniquement | Journalisation centralisée |
| Site secondaire | Siège | Via le tunnel IPsec, selon le profil | Interconnexion sécurisée |

### 2.5 Schéma d'architecture

![Architecture](architecture.png)
