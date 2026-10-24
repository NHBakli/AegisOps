# Fail2ban

Lance ce rôle seul avec `--tags fail2ban`. Il configure une jail SSH qui lit le
journal systemd et ignore l'adresse source réelle de l'administrateur.

Le play complet crée d'abord l'administrateur puis se reconnecte avec lui.
`--tags fail2ban` saute la création : le compte doit déjà exister. Charge aussi
`admin-vars.yml` afin que le playbook utilise ce compte. Vérifie que
`sudo -n true` fonctionne et confirme l'accès à la console ou à un snapshot.
Remplace les exemples ci-dessous par les valeurs réelles dans ton fichier de
variables :

```yaml
fail2ban_hardening_approved_host: my-vps
fail2ban_hardening_recovery_confirmed: true
fail2ban_hardening_admin_user: aegisadmin
fail2ban_hardening_probe_private_key: /home/you/.ssh/id_ed25519
fail2ban_hardening_admin_source_ip: 198.51.100.7
fail2ban_hardening_lxc_compatibility_confirmed: true # si LXC
```

```bash
ansible-playbook -i inventories/production/hosts.yml playbooks/hardening.yml \
  --tags fail2ban -e @admin-vars.yml -e @fail2ban-vars.yml
```

Ajoute `--ask-vault-pass` seulement si l'un des fichiers passés à `-e` est
chiffré avec Vault.

Le rôle exige `CAP_NET_ADMIN`, mais cela ne prouve pas que LXC/Proxmox filtre
réellement les paquets. Il refuse une adresse d'administration IPv6 ou une
écoute SSH IPv6 : sa sonde ne vérifie que l'IPv4. Le test de bannissement
`192.0.2.123` est séparé et désactivé par défaut ; il modifie temporairement
iptables. Les seuils par défaut sont 5 essais en 600 secondes et 600 secondes
de bannissement. Valide le filtrage dans une VM isolée avant production.
