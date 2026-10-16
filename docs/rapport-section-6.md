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

### 6.3 Liaison entre le pare-feu et l'annuaire

Le pare-feu du siège fait confiance à l'autorité du laboratoire (certificat importé, sans clé privée). Trois serveurs d'authentification LDAP sont déclarés, identiques à un champ près : le **conteneur d'authentification**, qui limite la recherche des comptes au classeur d'un seul service.

| Serveur d'authentification | Conteneur |
|---|---|
| `LDAP-Support` | `ou=support,ou=people,dc=mediconnect,dc=local` |
| `LDAP-Commerciaux` | `ou=commerciaux,ou=people,dc=mediconnect,dc=local` |
| `LDAP-Admins` | `ou=admins,ou=people,dc=mediconnect,dc=local` |

Les tests confirment ce cloisonnement : `c.durand` est acceptée par `LDAP-Commerciaux`, alors que `s.martin` y est refusée **avec un mot de passe correct**, car elle n'appartient pas à ce service.

![06-10-serveurs-ldap](../captures/06-10-serveurs-ldap.png)
*Capture : les trois serveurs d'authentification*

![06-11-test-ldap-ok](../captures/06-11-test-ldap-ok.png)
*Capture : authentification réussie d'une commerciale*

![06-12-test-ldap-refus](../captures/06-12-test-ldap-refus.png)
*Capture : refus d'un compte du support sur le serveur des commerciaux*

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

![06-17-regles-wan-openvpn](../captures/06-17-regles-wan-openvpn.png)
*Capture : règles WAN des VPN*

### 6.5 Poste de test et fichier de configuration

Le poste `CLIENT-TEST` (Debian 13, adresse `203.0.113.100`) représente un télétravailleur sur Internet. Le fichier de configuration est exporté :

- **sans certificat** : l'option qui aurait inclus le certificat et la clé privée du serveur a été écartée, car elle permettrait à un utilisateur d'usurper le pare-feu ;
- avec **vérification du nom du serveur**, pour détecter un faux serveur ;
- avec **interdiction d'enregistrer le mot de passe** : en cas de vol du poste, le fichier seul ne suffit pas.

Une connexion de `c.durand` reçoit l'adresse `10.8.60.2` : le pare-feu l'identifie comme commerciale.

![06-18-client-export](../captures/06-18-client-export.png)
*Capture : export de la configuration, sans certificat*

![06-21-connection-status](../captures/06-21-connection-status.png)
*Capture : session VPN de c.durand, adresse 10.8.60.2*

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

![06-22-vpn-refus-identite](../captures/06-22-vpn-refus-identite.png)
*Capture : connexion refusée pour un compte d'un autre service*

![06-23-test-commercial-bloque](../captures/06-23-test-commercial-bloque.png)
*Capture : la commerciale est bloquée malgré une route forcée*

![06-24-test-admin-autorise](../captures/06-24-test-admin-autorise.png)
*Capture : l'administrateur atteint le serveur*

![06-25-regle-openvpn](../captures/06-25-regle-openvpn.png)
*Capture : règle de l'interface OpenVPN*

![06-26-log-blocage](../captures/06-26-log-blocage.png)
*Capture : le blocage apparaît dans les journaux du pare-feu*

### 6.7 Difficultés rencontrées

- **Certificat « pas encore valide ».** Le premier test LDAPS a échoué (`certificate is not yet valid`) : l'horloge du pare-feu était en retard sur celle du serveur qui avait émis le certificat. Les pare-feu n'ont ni accès à Internet ni outils de synchronisation avec l'hôte ; leur horloge dérive, en particulier lorsqu'une machine virtuelle est suspendue puis reprise. L'heure a été corrigée manuellement ; une synchronisation NTP centralisée est mise en place dans la partie journalisation. Cet incident illustre la justification de la section 2.4 : sans heure commune, le chiffrement, l'authentification multifacteur et la corrélation des journaux sont compromis.
- **Saisie dans les consoles.** Le copier-coller n'étant pas possible dans la console VMware, la configuration des serveurs Debian a été faite en SSH depuis le poste d'administration, pendant la phase d'installation.

![06-11a-erreur-horloge](../captures/06-11a-erreur-horloge.png)
*Capture : refus du certificat dû au décalage d'horloge*

### 6.8 Limites

- **Pas de second facteur pour le VPN.** L'accès repose sur le fichier de configuration (clé `tls-crypt`) et sur le mot de passe. En production, un code à usage unique (TOTP), au minimum pour les administrateurs, ou un certificat par utilisateur renforcerait l'authentification.
- **Clé `tls-crypt` commune aux trois instances.** Un fichier de configuration valide pour un groupe permet d'atteindre les autres instances en changeant seulement le port (la maquette l'a d'ailleurs utilisé pour tester le VPN des administrateurs). La barrière restante est l'annuaire, qui refuse les comptes d'un autre service. Une clé distincte par instance ajouterait une barrière supplémentaire.
- **Appartenance à un groupe par emplacement dans l'annuaire.** Un compte ne peut appartenir qu'à un seul service. Une gestion par groupes LDAP permettrait des appartenances multiples, au prix d'une configuration plus complexe.
- **Annuaire unique.** Sa panne empêcherait toute connexion VPN ; un second serveur répliqué serait nécessaire en production.
- **Autorité de certification du laboratoire.** Sa clé est conservée sur le serveur d'annuaire et aucune liste de révocation n'est publiée ; en production, la clé serait conservée hors ligne.
- **Règle SSH temporaire.** L'accès direct des administrateurs à SRV-LDAP sera remplacé par un passage obligatoire par le bastion.
