## 12. Conclusion

La maquette met en œuvre une architecture où **chaque flux est justifié, filtré et journalisé** : deux sites reliés par un tunnel IPsec chiffré, des accès distants dont les droits dépendent de l'identité de l'utilisateur dans l'annuaire, un portail exposé uniquement en HTTPS derrière un reverse proxy et un pare-feu applicatif, des médecins authentifiés par deux facteurs, une zone de démonstration incapable d'atteindre la production, et une administration isolée des utilisateurs.

Trois principes ont guidé tous les choix : **tout interdire par défaut**, **n'ouvrir que le strict nécessaire** et **conserver une trace** de chaque décision. Les tests le montrent : deux utilisatrices connectées au même pare-feu par le même type de VPN obtiennent des droits différents, une attaque cachée dans un flux autorisé est bloquée, et chaque refus apparaît dans les journaux avec le nom de la règle responsable.

Les difficultés rencontrées ont aussi été instructives. Plusieurs « pannes » étaient en réalité le pare-feu qui faisait son travail : la bonne réponse a toujours été de corriger la machine ou l'ordre des règles, jamais d'assouplir le filtrage. Et la synchronisation de l'heure, qui semblait un détail, s'est révélée indispensable à l'authentification multifacteur, aux certificats et à la lecture des journaux.

Les principales évolutions pour une mise en production seraient un IPS sur le pare-feu, un bastion d'administration, des VLAN par service, un second facteur pour les administrateurs et la redondance des équipements critiques.
