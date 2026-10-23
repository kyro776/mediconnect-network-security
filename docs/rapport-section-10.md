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

![08-16-srv-logs](../captures/08-16-srv-logs.png)
*Capture : serveur de journalisation à l'écoute*

![08-17-logs-pare-feu-centralises](../captures/08-17-logs-pare-feu-centralises.png)
*Capture : journaux du pare-feu reçus sur le serveur central*

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

![08-14-ntp-pare-feu](../captures/08-14-ntp-pare-feu.png)
*Capture : service de temps du pare-feu, limité aux interfaces internes*

![08-15-ntp-serveur](../captures/08-15-ntp-serveur.png)
*Capture : serveur synchronisé sur sa passerelle*

### 10.4 Difficultés rencontrées

- **Réponses perdues.** Le serveur de journalisation, qui avait encore sa carte d'installation, renvoyait ses réponses par celle-ci : la DMZ ne parvenait pas à établir la connexion. Des routes vers les réseaux internes via le pare-feu ont corrigé le problème.
- **Ordre des règles.** Les journaux de la DMZ étaient d'abord bloqués par la règle finale de la zone : la règle d'autorisation avait été placée après elle (section 8.7).
- **La même heure n'est pas la bonne heure.** Le pare-feu de référence, réglé à la main, avait quelques minutes d'avance : toutes les machines étaient d'accord entre elles, mais les codes à usage unique, calculés par un téléphone à l'heure exacte, étaient refusés. L'heure du pare-feu a été corrigée à la seconde près.

### 10.5 Limites

- **Couverture partielle.** Seuls le pare-feu du siège et le serveur de la DMZ envoient leurs journaux ; le pare-feu du site secondaire, l'annuaire et le serveur DEMO les conservent localement. Le principe est le même et serait étendu en production.
- **Pas d'analyse automatique.** Les journaux sont collectés mais pas analysés : un outil de corrélation (SIEM) déclencherait des alertes, par exemple après plusieurs échecs de code à usage unique.
- **Transport non chiffré et non signé.** Les journaux circulent en clair sur le réseau interne, et le pare-feu les envoie en UDP, sans garantie de réception ; en production, on utiliserait syslog sur TLS.
- **Heure de référence non garantie exacte.** En production, le pare-feu se synchroniserait sur plusieurs serveurs de temps publics.
