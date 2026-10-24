# SSH

## Avant de lancer

Prévu pour Ubuntu 22.04. Le rôle bloque root, les mots de passe et
l'authentification interactive. Il exige un administrateur non-root, une
console ou un snapshot, et une clé SSH disponible sur le contrôleur.

Configure dans un fichier de variables :

```yaml
ssh_hardening_approved_host: my-vps
ssh_hardening_recovery_confirmed: true
ssh_hardening_independent_login_confirmed: true
ssh_hardening_admin_user: aegisadmin
ssh_hardening_probe_private_key: /chemin/vers/id_ed25519
```

Sans tag, `hardening.yml` crée d'abord le compte depuis la connexion actuelle,
puis ouvre une nouvelle connexion sous ce compte. `--tags ssh` saute cette
étape : l'administrateur doit déjà exister. Dans ce cas, charge aussi les
variables du compte afin que le playbook utilise son nom et sa clé. Il n'est
pas nécessaire de modifier `ansible_user` dans l'inventaire. La sonde ne prend
pas en charge les hôtes accessibles via bastion. Le rôle refuse les
configurations SSH contenant des règles `Match` ou des inclusions non standard.

## Lancer

Sur une VM de test, crée `inventories/lab/hosts.yml` ou remplace ce chemin par
celui de ton inventaire de test. Lance ensuite le tag SSH :

```bash
ansible-playbook -i inventories/lab/hosts.yml playbooks/hardening.yml \
  --tags ssh -e @admin-vars.yml -e @ssh-vars.yml
```

Ajoute `--ask-vault-pass` seulement si l'un des fichiers passés à `-e` est
chiffré avec Vault.

Le rôle sauvegarde `sshd_config`, le valide, le recharge et teste une nouvelle
connexion. En cas d'échec accessible, il restaure la sauvegarde. Une perte de
connexion peut empêcher le retour automatique : utilise alors la console et
la [procédure de récupération](recovery.md).
