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
