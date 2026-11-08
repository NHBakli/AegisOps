# SSH (`ssh_hardening`)

## À quoi ça sert

Ce rôle ferme les portes d'entrée SSH les plus attaquées : la connexion
`root`, les mots de passe et l'authentification interactive. Seules les clés
SSH restent acceptées. Il teste une connexion neuve avant et après le
changement, et revient en arrière si ce test échoue.

## Ce que le rôle modifie

- Ajoute en **tête** de `/etc/ssh/sshd_config` un bloc géré, après en avoir
  fait une sauvegarde horodatée :

  ```text
  # BEGIN AEGISOPS SSH HARDENING
  PermitRootLogin no
  PasswordAuthentication no
  KbdInteractiveAuthentication no
  AddressFamily inet
  PubkeyAuthentication yes
  # END AEGISOPS SSH HARDENING
  ```

  Le reste du fichier n'est pas touché. Comme OpenSSH garde la première
  valeur rencontrée, ce bloc l'emporte sur les lignes suivantes.
- Recharge SSH. Sur Ubuntu 24.04 avec `ssh.socket` actif, régénère aussi les
  unités systemd et redémarre `ssh.socket`, pour que le changement d'adresse
  d'écoute soit pris en compte.

`AddressFamily inet` limite **seulement SSH** à IPv4 ; IPv6 reste actif pour
le reste du système.

## Prérequis et confirmations

Avant tout changement, le rôle vérifie que :

- le serveur est sous Ubuntu 22.04 ou 24.04, et tu n'es pas en mode `--check` ;
- `ssh_hardening_approved_host` vaut le nom de l'hôte dans l'inventaire ;
- `ssh_hardening_recovery_confirmed: true` : tu as vérifié l'accès console ;
- `ssh_hardening_independent_login_confirmed: true` : tu as réellement testé
  une connexion admin neuve avec `sudo -n true` ;
- Ansible est connecté avec l'administrateur (`ssh_hardening_admin_user`), pas
  avec root ;
- la clé privée `ssh_hardening_probe_private_key` existe sur ton poste ;
- `sshd -t` valide la configuration actuelle ;
- la configuration ne contient **pas** de bloc `Match`, ni d'`Include` autre
  que `/etc/ssh/sshd_config.d/*.conf`, ni de `Match`/`Include` dans
  `/etc/ssh/sshd_config.d/` (ces règles demandent une revue manuelle) ;
- sur 24.04, `ssh.socket` est dans un état stable et n'a pas d'override
  personnalisé ;
- une connexion SSH neuve, par clé seulement, réussit **avant** le changement.

La connexion de test (`ssh -F /dev/null`, `StrictHostKeyChecking=yes`) exige
que l'empreinte du serveur soit déjà dans ton `~/.ssh/known_hosts`. Elle ne
passe pas par un bastion.

## Variables

```yaml
ssh_hardening_disable_root_login: true
ssh_hardening_disable_password_auth: true
ssh_hardening_disable_keyboard_interactive: true
ssh_hardening_address_family: inet   # any par défaut ; inet si tu utilises Fail2ban
ssh_hardening_approved_host: my-vps
ssh_hardening_recovery_confirmed: true
ssh_hardening_independent_login_confirmed: true
ssh_hardening_admin_user: aegisadmin
ssh_hardening_probe_private_key: /home/toi/.ssh/aegisops_admin
```

Référence complète : [configuration.md](configuration.md#ssh-ssh_hardening_).

## Lancer

Le compte administrateur doit exister et
`users_hardening_admin_bootstrapped` valoir `true` (voir
[users-hardening.md](users-hardening.md)). Garde une session SSH ouverte,
puis :

```bash
ansible-playbook -i inventories/production/hosts.local.yml \
  playbooks/hardening.yml --tags ssh
```

Ajoute `--ask-vault-pass` si `hardening-vars.yml` est chiffré.

Déroulé : sauvegarde et écriture du bloc (validé par `sshd -t`), lecture de
`sshd -T` pour confirmer les valeurs effectives, rechargement, contrôle des
ports en écoute (24.04 avec `inet`), puis **nouvelle connexion de test**. Le
chemin de la sauvegarde est affiché à la fin.

## Vérifier

Dans un nouveau terminal :

```bash
ssh -i ~/.ssh/aegisops_admin aegisadmin@203.0.113.10 'sudo sshd -T | grep -E "permitrootlogin|passwordauthentication|kbdinteractive|addressfamily"'
ssh root@203.0.113.10   # doit être refusé
```

Puis active `verify_ssh: true` et lance `verify.yml` : il lit la
configuration effective pour l'administrateur **et** pour root, depuis ton
adresse (voir [verify.md](verify.md)). L'audit doit maintenant afficher `PASS`
pour les quatre contrôles SSH.

Root étant refusé, mets `ansible_user: aegisadmin` et
`ansible_ssh_private_key_file` dans ton inventaire pour `audit.yml`.

## Revenir en arrière / dépannage

- **Le rôle s'arrête au début** : lis le message de l'assertion. Aucun
  fichier n'a été modifié.
- **`Existing Match clauses or nonstandard Include directives`** : ta
  configuration contient des règles conditionnelles. Revois-les à la main ;
  le rôle ne les durcit pas automatiquement.
- **La connexion de test échoue après le changement** : le rôle restaure la
  sauvegarde, recharge SSH et s'arrête avec le chemin de la sauvegarde. Si la
  connexion a été coupée avant cette restauration, utilise la console et
  [recovery.md](recovery.md#ssh-inaccessible).
- **Annuler volontairement** : restaure la sauvegarde affichée par Ansible
  (de la forme `/etc/ssh/sshd_config.<nombre>.<date>@<heure>~`), ou retire le bloc
  `AEGISOPS SSH HARDENING`, puis `sudo sshd -t` et rechargement (procédure
  dans [recovery.md](recovery.md#ssh-inaccessible)).
