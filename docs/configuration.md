# Configuration

Cette page est la référence des variables d'AegisOps. Les valeurs par défaut
viennent de `roles/*/defaults/main.yml` ; le modèle à copier est
`hardening-vars.yml.example`.

## Où vivent les variables

| Fichier | Contenu | Versionné ? |
|---|---|---|
| `inventories/production/hosts.local.yml` | Adresse, utilisateur et port SSH du serveur | Non |
| `hardening-vars.yml` | Toutes les variables des rôles | Non |
| `monitoring-vault.yml` | Mot de passe Grafana, chiffré par Vault | Non |
| `hardening-vars.yml.example` | Modèle avec des valeurs fictives | Oui |

Les quatre playbooks chargent `hardening-vars.yml` automatiquement. S'il
n'existe pas, ils chargent `hardening-vars.yml.example` à la place : ses
valeurs fictives font alors échouer les gardes, sans rien modifier.

`monitoring-vault.yml` n'est **pas** chargé automatiquement : passe-le avec
`-e @monitoring-vault.yml`.

Dans les tableaux, la colonne « Requis » signifie :

- **oui** : sans valeur correcte, le rôle s'arrête avant tout changement ;
- **si …** : requis seulement dans ce cas ;
- **non** : la valeur par défaut convient.

## Inventaire

| Variable | Exemple | Requis | Signification |
|---|---|---|---|
| `ansible_host` | `203.0.113.10` | oui | Adresse du serveur. |
| `ansible_user` | `root` | oui | Utilisateur de la première connexion et de `audit.yml`. Après le durcissement SSH : `aegisadmin`. |
| `ansible_port` | `22` | oui | Port SSH réel. UFW l'autorise et Fail2ban le surveille. |
| `ansible_ssh_private_key_file` | `~/.ssh/aegisops_admin` | non | Clé utilisée par `audit.yml` une fois root désactivé. |

Le nom de l'hôte (par exemple `my-vps`) est `inventory_hostname`. Toutes les
approbations `*_approved_host` doivent valoir exactement ce nom.

## Utilisateurs (`users_hardening_*`)

| Variable | Défaut | Requis | Signification |
|---|---|---|---|
| `users_hardening_admin_bootstrapped` | `false` | oui | `false` : le play 1 crée le compte. Passe à `true` après avoir testé la connexion et `sudo -n true`. |
| `users_hardening_admin_username` | `""` | oui | Nom du compte (minuscules, chiffres, `_`, `-`), jamais `root`. Aussi utilisé pour se connecter dans le play 2, `verify.yml` et `monitoring.yml`. |
| `users_hardening_admin_shell` | `/bin/bash` | non | Shell du compte. Doit exister sur le serveur. |
| `users_hardening_admin_groups` | `[]` | non | Groupes supplémentaires. Ils doivent déjà exister. |
| `users_hardening_admin_public_keys` | `[]` | oui | Au moins une clé publique SSH complète. Les clés déjà présentes sont conservées. |
| `users_hardening_sudo_mode` | `""` | oui | `nopasswd` ou `password`. Le durcissement complet exige `nopasswd`. `password` n'est accepté que pour un compte qui existe déjà. |
| `users_hardening_admin_password_hash` | `""` | non | Hash `crypt` (commence par `$`). Vide : mot de passe Unix verrouillé. S'il est renseigné, chiffre le fichier avec Vault. |

## Clé de l'administrateur (partagée)

| Variable | Défaut | Requis | Signification |
|---|---|---|---|
| `ssh_hardening_probe_private_key` | `""` | oui (sauf `--tags users`) | Chemin **absolu** de la clé privée de l'administrateur sur ton poste. C'est la clé de connexion du play 2, de `verify.yml` et de `monitoring.yml`, et la clé de test du rôle SSH. |

## SSH (`ssh_hardening_*`)

| Variable | Défaut | Requis | Signification |
|---|---|---|---|
| `ssh_hardening_disable_root_login` | `true` | non | Écrit `PermitRootLogin no`. |
| `ssh_hardening_disable_password_auth` | `true` | non | Écrit `PasswordAuthentication no`. |
| `ssh_hardening_disable_keyboard_interactive` | `true` | non | Écrit `KbdInteractiveAuthentication no`. |
| `ssh_hardening_address_family` | `any` | non | `any`, `inet` (IPv4 seulement) ou `inet6`. Mets `inet` si tu utilises Fail2ban. |
| `ssh_hardening_approved_host` | `""` | oui | Nom exact de l'hôte dans l'inventaire. |
| `ssh_hardening_recovery_confirmed` | `false` | oui | **Confirmation** : console ou snapshot disponibles. |
| `ssh_hardening_independent_login_confirmed` | `false` | oui | **Confirmation** : tu as testé une nouvelle connexion admin avec `sudo -n true`. |
| `ssh_hardening_admin_user` | `""` | oui | Doit être égal à `users_hardening_admin_username`. |

Au moins une des quatre premières options doit changer quelque chose, sinon le
rôle refuse de tourner.

## Pare-feu (`firewall_hardening_*`)

| Variable | Défaut | Requis | Signification |
|---|---|---|---|
| `firewall_hardening_activate` | `false` | non | `false` : prépare les règles, UFW reste inactif. `true` : active UFW (décision séparée). |
| `firewall_hardening_allowed_inbound` | `[]` | non | Liste de ports entrants autorisés, en plus du port SSH. Format : `{port: 443, proto: tcp}`, `proto` vaut `tcp` ou `udp`, pas de doublon ni de règle pour le port SSH. |
| `firewall_hardening_default_incoming` | `deny` | non | `deny` ou `reject`. |
| `firewall_hardening_default_outgoing` | `allow` | non | Seule valeur acceptée : `allow`. |
| `firewall_hardening_approved_host` | `""` | si activation | Nom exact de l'hôte. |
| `firewall_hardening_recovery_confirmed` | `false` | si activation | **Confirmation** : console ou snapshot. |
| `firewall_hardening_independent_login_confirmed` | `false` | si activation | **Confirmation** : connexion admin testée. |
| `firewall_hardening_lxc_compatibility_confirmed` | `false` | si activation dans un conteneur | **Confirmation** : filtrage réseau validé dans ce conteneur. Inutile sur une VM KVM. |
| `firewall_hardening_admin_user` | `""` | si activation | Administrateur utilisé pour le test SSH, égal à `users_hardening_admin_username`. |
| `firewall_hardening_probe_private_key` | `""` | si activation | Chemin absolu de sa clé privée. |

## Fail2ban (`fail2ban_hardening_*`)

| Variable | Défaut | Requis | Signification |
|---|---|---|---|
| `fail2ban_hardening_approved_host` | `""` | oui | Nom exact de l'hôte. |
| `fail2ban_hardening_recovery_confirmed` | `false` | oui | **Confirmation** : console ou snapshot. |
| `fail2ban_hardening_lxc_compatibility_confirmed` | `false` | si conteneur | **Confirmation** : bannissement validé dans ce conteneur. |
| `fail2ban_hardening_admin_user` | `""` | oui | Égal à `users_hardening_admin_username`. |
| `fail2ban_hardening_probe_private_key` | `""` | oui | Chemin absolu de la clé privée. |
| `fail2ban_hardening_admin_source_ip` | `""` | non (oui pour `verify_fail2ban`) | IPv4 de ton poste vue par le serveur. Vide : détectée automatiquement. Renseignée : le rôle vérifie qu'elle correspond. |
| `fail2ban_hardening_maxretry` | `5` | non | Échecs avant bannissement (entier ≥ 1). |
| `fail2ban_hardening_findtime` | `600` | non | Fenêtre de comptage, en secondes. |
| `fail2ban_hardening_bantime` | `600` | non | Durée du bannissement, en secondes. |
| `fail2ban_hardening_banaction` | `iptables-multiport` | non | Seule valeur acceptée. |
| `fail2ban_hardening_ban_probe_enabled` | `false` | non | `true` : teste un vrai bannissement de l'adresse de test, puis le retire. |
| `fail2ban_hardening_probe_ip` | `192.0.2.123` | non | Adresse de test réservée. Seule valeur acceptée. |

## Mises à jour (`updates_hardening_*`)

| Variable | Défaut | Requis | Signification |
|---|---|---|---|
| `updates_hardening_include_esm` | `false` | non | Ajoute les dépôts de sécurité ESM (Ubuntu Pro). |
| `updates_hardening_replace_existing_origins_confirmed` | `false` | si origines personnalisées | **Confirmation** : tu as revu les origines APT existantes et acceptes de les remplacer. |
| `updates_hardening_automatic_reboot` | `false` | non | `true` : redémarre le serveur si une mise à jour l'exige (décision séparée). |
| `updates_hardening_reboot_time` | `"03:00"` | non | Heure du redémarrage, format `HH:MM`. |
| `updates_hardening_reboot_approved_host` | `""` | si redémarrage | Nom exact de l'hôte. |
| `updates_hardening_recovery_confirmed` | `false` | si redémarrage | **Confirmation** : console disponible en cas de mauvais redémarrage. |

## Vérification (`verify_*`)

| Variable | Défaut | Requis | Signification |
|---|---|---|---|
| `verify_users` | `false` | au moins une section | Vérifie le compte, ses clés et sudo. |
| `verify_ssh` | `false` | au moins une section | Vérifie la politique SSH effective. |
| `verify_firewall` | `false` | au moins une section | Vérifie UFW **actif**. Laisse `false` si UFW n'est pas activé. |
| `verify_fail2ban` | `false` | au moins une section | Vérifie la jail SSH. |
| `verify_updates` | `false` | au moins une section | Vérifie la politique APT et les timers. |
| `verify_monitoring` | `false` | au moins une section | Vérifie la supervision. |
| `verify_wireguard` | `false` | au moins une section | Vérifie le tunnel WireGuard, ses appareils, son cloisonnement et sa règle UFW. |
| `verify_ssh_admin_user` | `""` | si `verify_ssh` | Administrateur, jamais `root`. |
| `verify_ssh_source_ip` | `""` | si `verify_ssh` | Adresse de ton poste vue par le serveur. |
| `verify_ssh_source_host` | `""` | si `verify_ssh` | Nom d'hôte de ce poste pour `sshd -T -C`. La même adresse IP convient sans règle SSH par nom. |
| `verify_ssh_probe_private_key` | `""` | si `verify_ssh` | Chemin absolu de la clé privée pour la connexion de test. |

`verify.yml` relit aussi les variables des autres rôles (`users_hardening_*`,
`ssh_hardening_*`, `firewall_hardening_*`, `fail2ban_hardening_*`,
`updates_hardening_*`) pour savoir ce qu'il doit trouver. Voir
[verify.md](verify.md).

## Supervision (`monitoring_*`)

| Variable | Défaut | Requis | Signification |
|---|---|---|---|
| `monitoring_approved_host` | `""` | oui | Nom exact de l'hôte. |
| `monitoring_admin_user` | `""` | oui | Égal à `users_hardening_admin_username`. |
| `monitoring_grafana_access` | `ssh_tunnel` | non | `ssh_tunnel` : Grafana sur `127.0.0.1`, accès par `ssh -L`. `vpn` : Grafana sur `wireguard_server_address`, accès par le VPN (déployer `vpn.yml` avant). |
| `monitoring_grafana_admin_user` | `admin` | non | Identifiant Grafana. Ne le change pas après le premier déploiement. |
| `monitoring_grafana_admin_password` | `""` | oui | Secret de 16 à 128 caractères, **dans `monitoring-vault.yml`**. |
| `monitoring_prometheus_retention_time` | `15d` | non | Durée de conservation des métriques. |
| `monitoring_prometheus_retention_size` | `1GB` | non | Taille maximale des métriques. |
| `monitoring_scrape_interval` | `30s` | non | Fréquence de collecte, 10 s minimum. |
| `monitoring_prometheus_memory_max_mb` | `512` | non | Plafond mémoire de Prometheus (≥ 128). |
| `monitoring_grafana_memory_max_mb` | `512` | non | Plafond mémoire de Grafana (≥ 128). |
| `monitoring_node_exporter_memory_max_mb` | `64` | non | Plafond mémoire de node_exporter (≥ 32). |
| `monitoring_memory_reserve_mb` | `1024` | non | Mémoire qui doit rester libre (≥ 256). |
| `monitoring_collector_interval` | `1min` | non | Cadence du collecteur de sécurité. |
| `monitoring_collector_max_banned_ips` | `500` | non | Nombre maximal d'IP bannies publiées par jail (0 à 1000). |

Détails dans [monitoring.md](monitoring.md).

## VPN (`wireguard_*`)

| Variable | Défaut | Requis | Signification |
|---|---|---|---|
| `wireguard_approved_host` | `""` | oui | Nom exact de l'hôte. |
| `wireguard_admin_user` | `""` | oui | Égal à `users_hardening_admin_username`. |
| `wireguard_ufw_rule_confirmed` | `false` | oui | `true` pour accepter la règle UFW `51820/udp`. |
| `wireguard_endpoint` | `ansible_host` | non | Adresse publique que les appareils contactent. |
| `wireguard_port` | `51820` | non | Port UDP (1024 à 65535). |
| `wireguard_network` | `10.66.66.0/24` | non | Réseau privé du VPN ; ne doit chevaucher aucune route du serveur (K3s : 10.42/10.43). |
| `wireguard_reserved_networks` | `[10.42.0.0/16, 10.43.0.0/16]` | non | Plages que le VPN ne doit jamais chevaucher, même sans route (K3s). |
| `wireguard_server_address` | `10.66.66.1` | oui si mode VPN | Adresse du serveur dans le VPN, aussi utilisée par `monitoring` et `verify`. |
| `wireguard_peers` | `[]` | oui (≥ 1) | Appareils : `name`, `address`, `public_key`, créés avec `scripts/aegisops-wg-peer new <nom>`. |
| `wireguard_client_directory` | `~/.config/aegisops/wireguard` | non | Où vivent les clés privées des appareils et leurs `.conf`, sur ton PC. |

Détails dans [vpn.md](vpn.md).

## Audit

| Variable | Défaut | Requis | Signification |
|---|---|---|---|
| `audit_report_directory` | `reports/` du dépôt | non | Dossier du rapport JSON sur ton poste. |

## Les confirmations : des faits, pas des interrupteurs

Les variables qui finissent par `_confirmed` ne « débloquent » pas
simplement un rôle. Elles déclarent un fait que tu as **vérifié toi-même** :

| Confirmation | Le fait à vérifier avant de mettre `true` |
|---|---|
| `*_recovery_confirmed` | Tu as ouvert la console de l'hébergeur et elle fonctionne. Un snapshot récent existe si possible. |
| `*_independent_login_confirmed` | Dans un nouveau terminal, `ssh -i <clé> aegisadmin@<serveur>` puis `sudo -n true` ont réussi. |
| `*_lxc_compatibility_confirmed` | Dans un conteneur LXC, tu as testé que le filtrage ou le bannissement bloque vraiment le trafic. |
| `updates_hardening_replace_existing_origins_confirmed` | Tu as lu `apt-config dump` et les origines personnalisées peuvent être remplacées. |

Les rôles retestent ce qu'ils peuvent (connexion SSH neuve, `CAP_NET_ADMIN`),
mais ils ne peuvent pas vérifier que ta console fonctionne.

## Éviter les répétitions avec les ancres YAML

Le même administrateur, la même clé et le même nom d'hôte reviennent dans
plusieurs rôles. Le modèle `hardening-vars.yml.example` les écrit en clair,
mais tu peux utiliser des **ancres YAML** dans ton fichier local :

- `&nom` pose une ancre sur une valeur ;
- `*nom` réutilise cette valeur plus loin dans **le même fichier**.

```yaml
users_hardening_admin_username: &admin_user aegisadmin
ssh_hardening_probe_private_key: &admin_key /home/toi/.ssh/aegisops_admin
ssh_hardening_approved_host: &target_host my-vps

ssh_hardening_admin_user: *admin_user
firewall_hardening_admin_user: *admin_user
firewall_hardening_probe_private_key: *admin_key
firewall_hardening_approved_host: *target_host
fail2ban_hardening_admin_user: *admin_user
fail2ban_hardening_probe_private_key: *admin_key
fail2ban_hardening_approved_host: *target_host
fail2ban_hardening_admin_source_ip: &admin_source_ip "198.51.100.7"
verify_ssh_admin_user: *admin_user
verify_ssh_probe_private_key: *admin_key
verify_ssh_source_ip: *admin_source_ip
verify_ssh_source_host: *admin_source_ip
monitoring_admin_user: *admin_user
monitoring_approved_host: *target_host
```

L'ancre doit être définie **avant** son utilisation. Change une seule ligne et
toutes les copies suivent.

## Secrets et Ansible Vault

- **Mot de passe Grafana** : toujours dans `monitoring-vault.yml`, créé avec
  `ansible-vault encrypt_string` (voir [monitoring.md](monitoring.md)).
- **Hash de mot de passe de l'administrateur** (facultatif) : chiffre tout
  `hardening-vars.yml` avec `ansible-vault encrypt hardening-vars.yml`.
- Quand Vault demande « New Vault password », il s'agit du mot de passe que tu
  choisis pour **ce chiffrement**. Vault ne le stocke nulle part.
- Pour déchiffrer, ajoute `--ask-vault-pass` aux commandes, ou indique un
  fichier contenant ce mot de passe :

  ```bash
  export ANSIBLE_VAULT_PASSWORD_FILE=~/.config/aegisops/vault-pass
  ```

  Garde ce fichier hors du dépôt, en mode `600`.
- La clé privée SSH n'est jamais copiée : seul son **chemin** apparaît dans
  les variables.
