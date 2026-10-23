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
