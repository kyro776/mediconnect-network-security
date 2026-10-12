## 1. Contexte et analyse du besoin

### 1.1 Présentation du projet

MediConnect est une entreprise française en forte croissance qui lance une plateforme numérique de prise de rendez-vous médicaux, concurrente de Doctolib. Elle met en relation des patients et des professionnels de santé : recherche d'un praticien, consultation de ses disponibilités, réservation en ligne.

L'application web est déjà développée et ne fait pas partie du périmètre de ce projet. Le travail porte exclusivement sur l'architecture réseau qui l'entoure : segmentation, sécurisation des accès, VPN, filtrage, supervision. Pour les besoins de la maquette, le portail MediConnect est simulé par un serveur web simple.

### 1.2 Organisation de l'entreprise

L'entreprise est répartie sur deux sites, chacun disposant de son propre accès Internet :

- **Le site principal (siège)** : direction, équipes administratives et commerciales, support client, équipe informatique, serveurs, équipements de sécurité et plateforme accessible depuis Internet.
- **Le site secondaire** : employés, une partie du support et des commerciaux, qui ont besoin d'accéder aux ressources hébergées au siège.

Ces deux sites doivent être interconnectés de façon sécurisée, sans dépendre d'un lien dédié.

### 1.3 Populations d'utilisateurs et besoins

Le point central du projet est que les utilisateurs n'ont pas tous le même profil, ni le même niveau de confiance. Six populations ont été identifiées :

| Population | Provenance | Accès nécessaires | Niveau de confiance |
|---|---|---|---|
| Patients | Internet | Portail public, espace personnel authentifié | Nul |
| Médecins | Internet (cabinet, domicile, déplacement) | Espace professionnel uniquement, en HTTPS avec MFA | Faible |
| Télétravailleurs | Internet, via VPN | Ressources internes selon leur groupe | Moyen |
| Commerciaux itinérants | Cabinets médicaux, via VPN | CRM et zone de démonstration uniquement | Moyen |
| Employés des deux sites | Réseaux locaux | Ressources bureautiques selon leur profil | Moyen à élevé |
| Administrateurs | Réseau d'administration dédié | Pare-feu, routeurs, serveurs, passerelles VPN, équipements de sécurité | Très élevé |

### 1.4 Exigences de sécurité identifiées

1. **Cloisonnement des populations externes.** Les patients et les médecins n'ont aucun accès au système d'information interne. Les médecins, plus sensibles, bénéficient d'un point d'entrée distinct et d'une authentification multifacteur (MFA).
2. **Exposition maîtrisée de la plateforme.** Le portail est accessible exclusivement en HTTPS, depuis une zone isolée du réseau interne.
3. **Accès distant par profil.** Les télétravailleurs et les commerciaux accèdent aux ressources par VPN, et leurs droits dépendent de leur identité (leur groupe).
4. **Séparation production et démonstration.** Les démonstrations devant les médecins n'utilisent jamais l'environnement de production : une zone DEMO contient une copie simplifiée avec uniquement des données fictives.
5. **Administration isolée.** Les flux d'administration sont séparés des flux utilisateurs : un utilisateur du réseau local ne peut pas administrer directement les équipements.
6. **Interconnexion sécurisée des sites.** Les deux sites communiquent via un tunnel chiffré.
7. **Traçabilité.** Les événements de sécurité sont journalisés et centralisés.

### 1.5 Principes directeurs

- **Moindre privilège** : chaque utilisateur n'accède qu'aux ressources nécessaires à son activité.
- **Politique par défaut « tout interdit »** : seuls les flux explicitement autorisés sont permis.
- **Défense en profondeur** : plusieurs couches de protection (segmentation, filtrage, authentification, journalisation), pour qu'une défaillance isolée ne compromette pas le tout.
- **Séparation selon la confiance** : plus une zone est sensible, plus elle est isolée et surveillée.
