# Mises à jour de sécurité

Le rôle configure `unattended-upgrades` pour installer les mises à jour de
sécurité Ubuntu, puis active les timers APT. Il ne lance pas de mise à jour
immédiate. **Le redémarrage automatique reste désactivé par défaut.**

Le play complet crée d'abord l'administrateur puis se reconnecte avec lui.
`--tags updates` saute la création : le compte doit déjà exister. Charge aussi
`admin-vars.yml` afin que le playbook utilise ce compte :

```bash
ansible-playbook -i inventories/production/hosts.yml playbooks/hardening.yml \
  --tags updates -e @admin-vars.yml
```

Ajoute `--ask-vault-pass` seulement si `admin-vars.yml` est chiffré avec
Vault.

Par défaut, seules les mises à jour `jammy-security` sont configurées. Si APT
contient des origines personnalisées, le rôle s'arrête. Après revue, leur
remplacement dans la politique effective demande
`updates_hardening_replace_existing_origins_confirmed: true`. ESM peut être
ajouté avec `updates_hardening_include_esm: true`.

Pour autoriser les redémarrages, il faut aussi définir
`updates_hardening_automatic_reboot: true`, approuver le nom exact de l'hôte
avec `updates_hardening_reboot_approved_host` et confirmer l'accès console via
`updates_hardening_recovery_confirmed: true`. N'active cette option qu'avec une
fenêtre de maintenance prévue.

Le rôle cible Ubuntu 22.04. Même sans redémarrage automatique, des mises à jour
peuvent redémarrer certains services. Sous LXC, les mises à jour du noyau et le
redémarrage du conteneur dépendent aussi de l'hôte Proxmox.
