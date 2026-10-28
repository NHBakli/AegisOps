# Fail2ban

Lance ce rôle seul avec `--tags fail2ban`. Il configure une jail SSH qui lit le
journal systemd et ignore l'adresse source réelle de l'administrateur. Le
garde de plateforme accepte Ubuntu 22.04 et 24.04 ; sur 24.04, le rôle
reconnaît aussi `ssh.socket` comme point d'entrée SSH actif.

Configure les valeurs ci-dessous dans `hardening-vars.yml`. Le playbook
charge automatiquement ce fichier. Vérifie que `sudo -n true` fonctionne et
confirme l'accès à la console ou à un snapshot :

```yaml
fail2ban_hardening_approved_host: my-vps
fail2ban_hardening_recovery_confirmed: true
fail2ban_hardening_admin_user: aegisadmin
fail2ban_hardening_probe_private_key: /home/you/.ssh/id_ed25519
fail2ban_hardening_admin_source_ip: "" # facultatif : adresse attendue à vérifier
fail2ban_hardening_lxc_compatibility_confirmed: false # après validation du bannissement
```

Le rôle ouvre une connexion SSH indépendante et récupère automatiquement
l'IPv4 source depuis `SSH_CONNECTION` sur le VPS. La variable
`fail2ban_hardening_admin_source_ip` est facultative : si elle est renseignée,
le rôle vérifie qu'elle correspond à l'adresse observée. Sur LXC, ne confirme
la compatibilité qu'après avoir validé le mécanisme de bannissement. Le rôle
vérifie `CAP_NET_ADMIN`, mais cela ne prouve pas que LXC/Proxmox filtre
réellement les paquets.

```bash
ansible-playbook -i inventories/production/hosts.local.yml playbooks/hardening.yml \
  --tags fail2ban
```

Ajoute `--ask-vault-pass` si `hardening-vars.yml` est chiffré avec Vault.

Le rôle exige `CAP_NET_ADMIN`, mais cela ne prouve pas que LXC/Proxmox filtre
réellement les paquets. Il refuse une adresse d'administration IPv6 ou une
écoute SSH IPv6 : sa sonde ne vérifie que l'IPv4. Le test de bannissement
`192.0.2.123` est séparé et désactivé par défaut ; il ajoute puis retire
temporairement une règle iptables. Ce test confirme le mécanisme local, pas le
filtrage réseau de l'hôte Proxmox ou l'accessibilité depuis Internet. Les
seuils par défaut sont 5 essais en 600 secondes et 600 secondes de
bannissement.
