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

Configure les règles et approbations dans `hardening-vars.yml`. Le playbook
charge ce fichier automatiquement. Pour ta VM de test, crée un inventaire
dédié à partir de `inventories/example/hosts.yml`, puis remplace le chemin
ci-dessous par le chemin de cet inventaire :

```bash
ansible-playbook -i inventories/test/hosts.yml playbooks/hardening.yml \
  --tags firewall
```

Ajoute `--ask-vault-pass` si `hardening-vars.yml` est chiffré avec Vault.

Pour activer UFW, `firewall_hardening_activate: true` exige aussi une
approbation du nom d'hôte, une console ou un snapshot, une connexion
administrateur indépendante et, sous LXC, confirmation réseau et
`CAP_NET_ADMIN`. Teste d'abord en VM. Le rôle refuse un UFW actif non géré ou
des règles préexistantes inconnues.

Le rôle ne gère pas `before.rules` / `after.rules` ni le filtrage Proxmox.
`CAP_NET_ADMIN` ne prouve pas que LXC filtre réellement le trafic. Ne compte
pas sur UFW pour protéger le VPS avant un test réseau isolé.
