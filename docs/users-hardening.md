# Compte administrateur (`users_hardening`)

## À quoi ça sert

Ce rôle crée un administrateur non-root, qui se connecte par clé SSH et
utilise `sudo`. C'est la première étape : les autres rôles se connectent
ensuite avec ce compte, ce qui permet d'interdire la connexion root.

## Ce que le rôle modifie

- Crée le compte (par exemple `aegisadmin`) avec son dossier personnel, ou
  met à jour son shell et ses groupes s'il existe. Les groupes sont
  **ajoutés**, jamais retirés.
- Sans hash fourni, **verrouille le mot de passe Unix** : seule la clé SSH
  permet d'entrer. Un hash fourni n'est posé qu'à la création du compte.
- Ajoute les clés publiques dans `~/.ssh/authorized_keys` **sans retirer** les
  clés déjà présentes (dossier `.ssh` en `0700`).
- Écrit `/etc/sudoers.d/90-aegisops-<compte>` (mode `0440`), validé par
  `visudo` avant d'être installé :

  ```text
  aegisadmin ALL=(ALL:ALL) NOPASSWD:ALL
  ```

Le rôle ne supprime jamais de compte et ne remplace pas le mot de passe d'un
compte existant. Attention : si tu choisis un compte **qui existe déjà** et ne
fournis pas de hash, son mot de passe Unix est verrouillé lui aussi.

## Prérequis et confirmations

- Une connexion qui fonctionne avec l'utilisateur de l'inventaire (`root`, ou
  un utilisateur `sudo`).
- `sudo`, `visudo`, `su` et le shell choisi présents sur le serveur.
- Une paire de clés dédiée sur ton poste (voir
  [getting-started.md](getting-started.md#étape-2--créer-la-clé-ssh-de-ladministrateur)).
- Pour le durcissement complet (sans tag ou avec un autre tag) :
  `users_hardening_sudo_mode: nopasswd` et `ssh_hardening_probe_private_key`
  pointant vers une clé privée qui existe sur ton poste.

Ce rôle ne demande pas de confirmation `*_confirmed` : il ajoute un accès sans
en retirer.

## Variables

```yaml
users_hardening_admin_bootstrapped: false
users_hardening_admin_username: aegisadmin
users_hardening_admin_shell: /bin/bash
users_hardening_admin_groups: []
users_hardening_admin_public_keys:
  - "ssh-ed25519 AAAA... aegisadmin@aegisops"
users_hardening_sudo_mode: nopasswd
users_hardening_admin_password_hash: ""
ssh_hardening_probe_private_key: /home/toi/.ssh/aegisops_admin
```

Référence complète : [configuration.md](configuration.md#utilisateurs-users_hardening_).

## Lancer

Pour créer le compte seulement, laisse
`users_hardening_admin_bootstrapped: false` puis lance :

```bash
ansible-playbook -i inventories/production/hosts.local.yml \
  playbooks/hardening.yml --tags users
```

Le rôle tourne dans le **premier play** de `hardening.yml`, avec la connexion
de l'inventaire. Il est sauté dès que
`users_hardening_admin_bootstrapped: true`.

## Vérifier

**Garde ta session initiale ouverte.** Dans un autre terminal, teste une
connexion neuve :

```bash
ssh -i ~/.ssh/aegisops_admin aegisadmin@203.0.113.10
sudo -n true && echo "sudo OK"
```

Quand ces deux tests réussissent, passe
`users_hardening_admin_bootstrapped: true` dans `hardening-vars.yml`. Les
exécutions suivantes se connecteront directement avec ce compte.

Le rôle vérifie déjà que `sudo -l -U aegisadmin` reconnaît la politique et que
`sudo -n true` fonctionne. Plus tard, `verify_users: true` contrôle le compte,
les permissions de `.ssh`, les clés et le fichier sudoers (voir
[verify.md](verify.md)).

## Revenir en arrière / dépannage

- **Le rôle s'arrête au début** : une assertion indique la valeur à corriger
  (nom invalide ou `root`, aucune clé, mode sudo absent, groupe inexistant,
  clé privée introuvable). Rien n'a été modifié.
- **`Password based sudo requires an existing administrator account`** : un
  nouveau compte doit utiliser `nopasswd`.
- **La connexion avec la clé échoue** : depuis la session encore ouverte,
  regarde `/home/aegisadmin/.ssh/authorized_keys` et ses droits, et le journal
  `journalctl -u ssh -n 50`.
- **Retirer l'accès sudo** :
  `sudo rm /etc/sudoers.d/90-aegisops-aegisadmin`.

Plus de détails dans [recovery.md](recovery.md#compte-administrateur).

Si tu ajoutes un hash de mot de passe, chiffre tout le fichier avec
`ansible-vault encrypt hardening-vars.yml`. Ne mets jamais un mot de passe en
clair et ne partage jamais la clé privée.
