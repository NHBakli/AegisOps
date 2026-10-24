# Vérifier le durcissement

`verify.yml` lit l'état réel de l'hôte et ne modifie rien. Choisis les
contrôles dans un fichier `verify-vars.yml`, puis lance :

```bash
ansible-playbook -i inventories/production/hosts.yml playbooks/verify.yml -e @verify-vars.yml
```

Au moins une section `verify_*` doit être à `true`. Les contrôles sélectionnés
échouent si l'état réel ne correspond pas aux variables attendues.

## Variables à fournir

- **Utilisateurs** : `verify_users: true` et les variables `users_hardening_*`
  du compte attendu.
- **SSH** : `verify_ssh: true`, les variables de politique `ssh_hardening_*`,
  `verify_ssh_admin_user`, `verify_ssh_source_ip`, `verify_ssh_source_host` et
  le chemin local `verify_ssh_probe_private_key`.
- **UFW** : `verify_firewall: true`, `ansible_port` et les variables
  `firewall_hardening_*` attendues.
- **Fail2ban** : `verify_fail2ban: true` et les variables
  `fail2ban_hardening_*` attendues.
- **Mises à jour** : `verify_updates: true` et les variables
  `updates_hardening_*` attendues.

Exemple minimal :

```yaml
verify_users: true
verify_ssh: true
verify_firewall: false
verify_fail2ban: false
verify_updates: false

users_hardening_admin_username: aegisadmin
users_hardening_admin_shell: /bin/bash
users_hardening_admin_public_keys:
  - "ssh-ed25519 AAAA... ta-clé-publique"
users_hardening_sudo_mode: nopasswd

ssh_hardening_disable_root_login: true
ssh_hardening_disable_password_auth: true
ssh_hardening_disable_keyboard_interactive: true
verify_ssh_admin_user: aegisadmin
verify_ssh_source_ip: 203.0.113.10
verify_ssh_source_host: admin.example.invalid
verify_ssh_probe_private_key: /home/you/.ssh/id_ed25519
```

La clé privée de la sonde SSH reste sur le contrôleur ; son chemin seul est
fourni. Le contrôle Fail2ban vérifie la jail, mais ne teste pas de bannissement.
Le contrôle UFW ne mesure pas le filtrage externe de l'hôte Proxmox.
