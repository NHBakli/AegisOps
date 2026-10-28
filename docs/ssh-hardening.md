# SSH

## Avant de lancer

Prévu pour Ubuntu 22.04 et 24.04. Le rôle bloque root, les mots de passe et
l'authentification interactive. `ssh_hardening_address_family: inet` limite
seulement SSH à IPv4 ; IPv6 reste actif au niveau du système. Le rôle exige un
administrateur non-root, une console ou un snapshot, et une clé SSH disponible
sur le contrôleur.

Sur Ubuntu 24.04, OpenSSH peut écouter via `ssh.socket`. Le rôle vérifie ce
mode, régénère la configuration systemd après un changement d'adresse et
contrôle les ports réellement à l'écoute avant de tester une nouvelle
connexion. Un échec déclenche la restauration de la configuration sauvegardée.
L'accès console reste indispensable si la connexion tombe pendant cette étape.

Configure dans `hardening-vars.yml` :

```yaml
ssh_hardening_approved_host: my-vps
ssh_hardening_recovery_confirmed: true
ssh_hardening_independent_login_confirmed: true
ssh_hardening_admin_user: aegisadmin
ssh_hardening_probe_private_key: /chemin/vers/id_ed25519
ssh_hardening_address_family: inet
```

Au premier passage, le compte est créé via la connexion d'inventaire. Après
avoir testé sa connexion et `sudo -n true`, passe
`users_hardening_admin_bootstrapped` à `true` dans le fichier central. Le play
SSH utilise alors directement cet administrateur. La sonde ne prend pas en
charge les hôtes accessibles via bastion. Le rôle refuse les configurations
SSH contenant des règles `Match` ou des inclusions non standard.

## Lancer

Sur une VM de test, crée un inventaire dédié à partir de
`inventories/example/hosts.yml`, puis remplace le chemin ci-dessous par le
chemin de cet inventaire. Lance ensuite le tag SSH :

```bash
ansible-playbook -i inventories/test/hosts.yml playbooks/hardening.yml \
  --tags ssh
```

Ajoute `--ask-vault-pass` si `hardening-vars.yml` est chiffré avec Vault.

Le rôle sauvegarde `sshd_config`, le valide, le recharge et teste une nouvelle
connexion. En cas d'échec accessible, il restaure la sauvegarde. Une perte de
connexion peut empêcher le retour automatique : utilise alors la console et
la [procédure de récupération](recovery.md).
