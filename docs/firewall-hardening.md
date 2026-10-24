# UFW

Le tag `firewall` prépare UFW, mais ne l'active pas. Il autorise d'abord le
port SSH indiqué par `ansible_port`, puis les ports déclarés dans
`firewall_hardening_allowed_inbound`. Ubuntu 22.04 seulement.

Exemple de variables :

```yaml
firewall_hardening_activate: false
firewall_hardening_allowed_inbound:
  - port: 443
    proto: tcp
```

Crée `inventories/lab/hosts.yml` pour ta VM de test ou remplace ce chemin par
celui de ton inventaire de test. Un lancement `--tags firewall` saute la
création du compte : l'administrateur doit déjà exister. Charge aussi
`admin-vars.yml` pour que le playbook se connecte avec ce compte :

```bash
ansible-playbook -i inventories/lab/hosts.yml playbooks/hardening.yml \
  --tags firewall -e @admin-vars.yml -e @firewall-vars.yml
```

Ajoute `--ask-vault-pass` seulement si l'un des fichiers passés à `-e` est
chiffré avec Vault.

Pour activer UFW, `firewall_hardening_activate: true` exige aussi une
approbation du nom d'hôte, une console ou un snapshot, une connexion
administrateur indépendante et, sous LXC, confirmation réseau et
`CAP_NET_ADMIN`. Teste d'abord en VM. Le rôle refuse un UFW actif non géré ou
des règles préexistantes inconnues.

Le rôle ne gère pas `before.rules` / `after.rules` ni le filtrage Proxmox.
`CAP_NET_ADMIN` ne prouve pas que LXC filtre réellement le trafic. Ne compte
pas sur UFW pour protéger le VPS avant un test réseau isolé.
