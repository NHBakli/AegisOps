# Vérification (`verify`)

## À quoi ça sert

`playbooks/verify.yml` contrôle que les protections sont **réellement**
actives sur le serveur. Il ne se contente pas de relire tes variables : il lit
l'état effectif (`sshd -T`, `ufw status verbose`, `fail2ban-client`,
`apt-config dump`, `systemctl`, `ss`) et le compare à ce que tu attends.
**Il ne modifie rien.**

## Ce que le rôle modifie

Rien. Toutes les tâches sont en lecture seule ; le `PLAY RECAP` affiche
`changed=0`.

## Prérequis et confirmations

- Ubuntu 22.04 ou 24.04.
- Au moins une section `verify_*` à `true`.
- **Pas de `--tags` ni de `--skip-tags`** : un filtre pourrait masquer des
  contrôles, le playbook le refuse.
- Le compte administrateur existe : le playbook se connecte avec
  `users_hardening_admin_username` et `ssh_hardening_probe_private_key`.
- N'active que les sections correspondant à ce que tu as **appliqué**.

## Variables

Chaque section relit les variables du rôle correspondant, pour savoir ce
qu'elle doit trouver.

| Section | Contrôles | Variables nécessaires |
|---|---|---|
| `verify_users` | Compte (UID non nul, shell), `.ssh` en `0700`, `authorized_keys` en `0600` avec les clés attendues, sudoers géré en `0440` et validé par `visudo`, `sudo -n true` | `users_hardening_admin_username`, `_admin_shell`, `_admin_public_keys`, `_sudo_mode` |
| `verify_ssh` | Configuration sans `Match` ni `Include` non standard ; `sshd -T -C` pour l'admin **et** pour root depuis ton adresse ; pas d'écoute IPv6 si `inet` ; `ssh.service` ou `ssh.socket` actif ; nouvelle connexion SSH + `sudo -n true` | `ssh_hardening_disable_*`, `ssh_hardening_address_family`, `verify_ssh_admin_user`, `verify_ssh_source_ip`, `verify_ssh_source_host`, `verify_ssh_probe_private_key` |
| `verify_firewall` | UFW **actif**, politiques par défaut, port SSH autorisé, **exactement** les ports déclarés ouverts (les deux règles VPN commentées « AegisOps » sont contrôlées par `verify_wireguard` et `verify_monitoring`), aucune règle `LIMIT` | `ansible_port`, `firewall_hardening_allowed_inbound`, `_default_incoming`, `_default_outgoing` |
| `verify_fail2ban` | Pas d'écoute SSH IPv6 ; service actif ; jail `sshd` ; journal `ssh.service` ; action `iptables-multiport` ; `maxretry`, `findtime`, `bantime` ; ton adresse dans `ignoreip` | `fail2ban_hardening_admin_source_ip` (IPv4), `fail2ban_hardening_maxretry`, `_findtime`, `_bantime` |
| `verify_updates` | Paquet installé ; listes et mises à jour quotidiennes ; origines de sécurité seulement (+ ESM si demandé) ; redémarrage conforme ; timers APT activés et actifs | `updates_hardening_include_esm`, `updates_hardening_automatic_reboot` |
| `verify_monitoring` | `prometheus`, `prometheus-node-exporter`, `grafana-server` et le timer du collecteur actifs ; 9090 et 9100 en écoute **uniquement** sur `127.0.0.1`, 3000 uniquement sur `127.0.0.1` (ou sur l'adresse VPN en mode `vpn`) ; Grafana protégé par `IPAddressDeny=any` ; métriques de sécurité rafraîchies il y a moins de 10 minutes | `monitoring_grafana_access`, `wireguard_server_address` en mode VPN |
| `verify_wireguard` | `wg0` porte l'adresse du serveur et démarre au boot ; clé publique et port conformes ; **exactement** les appareils déclarés, chacun limité à son adresse ; routage coupé et règle de cloisonnement `raw` présente ; règle UFW `51820/udp` ouverte à tous | `wireguard_port`, `wireguard_server_address`, `wireguard_peers` |

Pour connaître l'adresse source vue par le serveur :

```bash
ssh -i ~/.ssh/aegisops_admin aegisadmin@203.0.113.10 'echo "$SSH_CONNECTION"'
```

La première valeur est ton IPv4. Mets-la dans `verify_ssh_source_ip`,
`verify_ssh_source_host` et `fail2ban_hardening_admin_source_ip`. Pour
`verify_ssh_source_host`, la même adresse convient s'il n'y a pas de règle SSH
basée sur un nom d'hôte.

Exemple après un durcissement complet et la supervision :

```yaml
verify_users: true
verify_ssh: true
verify_firewall: true       # false tant qu'UFW n'est pas actif
verify_fail2ban: true
verify_updates: true
verify_monitoring: true
verify_wireguard: true    # si le VPN est déployé
verify_ssh_admin_user: aegisadmin
verify_ssh_probe_private_key: /home/toi/.ssh/aegisops_admin
verify_ssh_source_ip: "198.51.100.7"
verify_ssh_source_host: "198.51.100.7"
fail2ban_hardening_admin_source_ip: "198.51.100.7"
```

Référence complète :
[configuration.md](configuration.md#vérification-verify_).

## Lancer

```bash
ansible-playbook -i inventories/production/hosts.local.yml playbooks/verify.yml
```

Ajoute `--ask-vault-pass` si `hardening-vars.yml` est chiffré.

## Vérifier

- `failed=0` et `unreachable=0` : toutes les sections **activées** sont
  conformes.
- Les tâches des sections désactivées apparaissent en `skipped` : elles n'ont
  rien vérifié.
- `changed=0` : rien n'a été modifié.

## Revenir en arrière / dépannage

Il n'y a rien à annuler. Un échec signifie que l'état réel ne correspond pas
à l'attendu :

- **`Select at least one verify_* section and run without --tags`** : active
  une section et retire tes `--tags`.
- **Échec SSH** : une règle a été modifiée à la main, ou l'adresse source a
  changé. Compare `sudo sshd -T` avec tes variables.
- **Échec UFW** : UFW inactif, ou un port ouvert en plus de ceux déclarés.
  Regarde `sudo ufw status verbose`.
- **Échec Fail2ban** : ton adresse n'est plus dans `ignoreip` (adresse
  changée) ; relance le rôle Fail2ban.
- **Échec supervision** : un service est arrêté ou le collecteur ne tourne
  plus ; voir [monitoring.md](monitoring.md).

Limites : le contrôle Fail2ban ne teste pas de vrai bannissement, et le
contrôle UFW ne mesure pas le filtrage de l'hébergeur. Pour ça, teste depuis
l'extérieur.
