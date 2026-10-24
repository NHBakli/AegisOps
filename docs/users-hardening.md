# Compte administrateur

Crée `admin-vars.yml` **à la racine du dépôt**, au même niveau que
`ansible.cfg`. Le playbook crée ce compte avec la connexion actuelle, puis
ouvre une nouvelle connexion SSH avec lui pour continuer le hardening.

## `admin-vars.yml`

```yaml
users_hardening_admin_username: aegisadmin
users_hardening_admin_shell: /bin/bash
users_hardening_admin_groups: []
users_hardening_admin_public_keys:
  - "ssh-ed25519 AAAA... ta-clé-publique"
users_hardening_sudo_mode: nopasswd
ssh_hardening_probe_private_key: /home/you/.ssh/id_ed25519
```

Le compte n'a pas besoin de mot de passe pour SSH par clé avec sudo
`nopasswd`. Sans hash fourni, le rôle verrouille le mot de passe Unix.
Ubuntu permet toujours l'accès SSH par clé à ce compte. Remplace la clé par le
contenu du fichier `.pub`. Le chemin de clé privée doit lui correspondre et
rester sur ta machine. Les rôles suivants utilisent `sudo -n`.

Aucun mot de passe ni Vault ne sont requis pour le flux normal. Si tu as besoin
d'un mot de passe local, ajoute son hash SHA-512 dans
`users_hardening_admin_password_hash` et chiffre le fichier. Vault ne sauvegarde
pas automatiquement les mots de passe générés par un playbook. Ne mets jamais
un mot de passe en clair dans ce fichier.

Pour créer seulement le compte :

```bash
ansible-playbook playbooks/hardening.yml --tags users -e @admin-vars.yml
```

Pour lancer tous les rôles, ajoute `-e @admin-vars.yml` à la commande du
README après avoir renseigné les prérequis SSH et pare-feu. Si le fichier
contient un hash Vaulté, ajoute `--ask-vault-pass`. Le premier play crée le
compte avec la connexion actuelle ; le second se reconnecte avec l'admin.
Le rôle conserve les clés existantes et ajoute une règle sudo dédiée.

Ne partage et ne stocke jamais une clé privée dans le dépôt. `--check` ne
permet pas de tester la nouvelle connexion.
