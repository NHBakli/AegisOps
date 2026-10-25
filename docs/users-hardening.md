# Compte administrateur

Les playbooks chargent automatiquement `hardening-vars.yml` à la racine du
dépôt. Crée ce fichier depuis `hardening-vars.yml.example`, puis renseigne le
nom du compte, sa clé publique et le chemin absolu de la clé privée locale.

Sans hash de mot de passe, le rôle verrouille le mot de passe Unix. L'accès se
fait par clé SSH, avec les droits `sudo` définis explicitement. Le rôle
conserve les clés déjà installées et ne supprime pas de compte.

Pour créer le compte seulement, laisse
`users_hardening_admin_bootstrapped: false` puis lance :

```bash
ansible-playbook -i inventories/production/hosts.local.yml \
  playbooks/hardening.yml --tags users
```

Garde la session initiale ouverte. Teste une nouvelle connexion SSH avec le
compte créé, puis vérifie `sudo -n true`. Quand ces tests réussissent, passe
`users_hardening_admin_bootstrapped` à `true` dans `hardening-vars.yml`. Les
exécutions suivantes passeront le bootstrap et se connecteront directement
avec le compte administrateur.

Si tu ajoutes un hash de mot de passe local, chiffre le fichier complet avec
Ansible Vault. Ne mets jamais un mot de passe en clair et ne partage jamais
la clé privée.
