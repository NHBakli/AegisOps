# Supervision du VPS (`monitoring`)

## À quoi ça sert

`playbooks/monitoring.yml` installe un tableau de bord Grafana qui affiche :

- **les ressources** : CPU, RAM, swap, disques, I/O, réseau, charge, uptime,
  connexions TCP ;
- **la sécurité** : IP bannies par Fail2ban et tentatives échouées, état
  d'UFW, conformité SSH, connexions SSH ouvertes ;
- **la maintenance** : mises à jour en attente, redémarrage requis, état des
  services (SSH, Fail2ban, UFW, unattended-upgrades, supervision) ;
- **la supervision elle-même** : mémoire consommée et santé des cibles.

Ce n'est pas un rôle de durcissement : il n'est pas lancé par
`hardening.yml` et n'ouvre aucun port.

## Comment ça marche

```text
 ton poste                                 VPS (KVM, Ubuntu 24.04)
 ─────────                                 ────────────────────────────────────────
 navigateur                                127.0.0.1:3000  Grafana (tableau de bord)
 http://localhost:3000                          │ interroge
      │                                    127.0.0.1:9090  Prometheus (stocke 15 j)
      │  tunnel SSH chiffré                     │ collecte toutes les 30 s
      └── ssh -L 3000:127.0.0.1:3000 ──►   127.0.0.1:9100  node_exporter
          (clé aegisadmin, port 22)             │ lit aussi les fichiers .prom de
                                                ▼ /var/lib/prometheus/node-exporter/
                                           aegisops-security-exporter (chaque minute)
                                           → fail2ban-client, ufw status, sshd -T, ss
                                           prometheus-node-exporter-apt (15 min)
                                           → mises à jour en attente, reboot requis
```

Les trois services écoutent **uniquement sur `127.0.0.1`**. Depuis Internet,
on ne voit que le port SSH. Pour ouvrir le tableau de bord, il faut d'abord une
session SSH valide avec la clé administrateur.

## Deux façons d'accéder au tableau de bord

La variable `monitoring_grafana_access` choisit le mode d'accès :

| | `ssh_tunnel` (par défaut) | `vpn` |
|---|---|---|
| Grafana écoute sur | `127.0.0.1:3000` | `10.66.66.1:3000` (interface `wg0`) |
| Adresse dans le navigateur | <http://localhost:3000> | <http://10.66.66.1:3000> |
| Ce qu'il faut lancer | `ssh -N -L 3000:127.0.0.1:3000 …` à chaque fois | rien : le VPN reste connecté |
| Appareils | ordinateur avec client SSH et clé admin | PC, téléphone, autre ordinateur |
| Port ouvert sur Internet | aucun | `51820/udp` (WireGuard) |
| Prérequis | aucun | `playbooks/vpn.yml` déployé avant, voir [vpn.md](vpn.md) |

Dans les deux modes, Prometheus et node_exporter restent sur `127.0.0.1`.
Grafana garde son mot de passe et refuse tout autre nom d'hôte que le sien, ce
qui bloque les attaques par DNS rebinding. Son unité systemd n'accepte en plus
que les connexions venant de la boucle locale, et du réseau VPN en mode `vpn`
(`IPAddressDeny=any`). Ce filtre ne dépend pas d'UFW : même un pod K3s, que
d'autres règles UFW autorisent, ne peut pas joindre Grafana.

Le tunnel SSH ne nécessite aucune ouverture de port et réutilise ton accès SSH
déjà durci. Le VPN est plus pratique au quotidien et fonctionne sur téléphone.
En contrepartie, il ouvre un port UDP, qui reste invisible aux scanners.

## Ce que le rôle modifie sur le serveur

| Élément | Emplacement |
|---|---|
| Paquets Ubuntu | `prometheus`, `prometheus-node-exporter`, `prometheus-node-exporter-collectors`, `dbus`, `gpg` |
| Paquet Grafana | `grafana`, depuis `apt.grafana.com` |
| Clé du dépôt Grafana | `/etc/apt/keyrings/grafana.asc` (empreinte vérifiée) |
| Dépôt et restriction APT | `/etc/apt/sources.list.d/grafana.list`, `/etc/apt/preferences.d/aegisops-grafana` |
| Écoute locale et plafonds mémoire | `/etc/systemd/system/{prometheus,prometheus-node-exporter,grafana-server}.service.d/aegisops.conf` |
| Réglages et secret Grafana | `/etc/aegisops/grafana.env` (0600, root) |
| Cibles Prometheus | `/etc/prometheus/prometheus.yml` |
| Source de données et tableau de bord | `/etc/grafana/provisioning/{datasources,dashboards}/aegisops.yml`, `/var/lib/grafana/dashboards/aegisops/` |
| Collecteur de sécurité | `/usr/local/sbin/aegisops-security-exporter` et ses unités `aegisops-security-exporter.{service,timer}` |
| Sondes matérielles inutiles | timers SMART, NVMe, IPMI et Mellanox masqués |
| Règle UFW (mode `vpn` seulement) | port 3000 autorisé uniquement sur l'interface `wg0`, commentaire « AegisOps Grafana via VPN » ; supprimée si tu reviens au mode `ssh_tunnel` |

Rien d'autre n'est touché : ni SSH, ni Fail2ban, ni K3s, ni les autres règles UFW.

## Prérequis et confirmations

- Ubuntu 22.04 ou 24.04, administrateur `aegisadmin` déjà créé
  (voir [users-hardening.md](users-hardening.md)).
- Dépôt Ubuntu `universe` activé (c'est le cas par défaut).
- Dans `hardening-vars.yml` :

  ```yaml
  monitoring_approved_host: my-vps     # doit être l'hôte ciblé
  monitoring_admin_user: aegisadmin
  ```

- Un mot de passe Grafana dans un fichier Vault séparé (voir plus bas).

Avant toute modification, le rôle vérifie :

- la plateforme et l'approbation de l'hôte ;
- l'utilisateur non root ;
- la robustesse du mot de passe ;
- le fonctionnement du sandboxing systemd ;
- la mémoire libre : elle doit couvrir le budget, plus 1 Go de réserve.

Si une condition manque, il s'arrête avec `changed=0`.

## Budget mémoire

Chaque service a un plafond dur (`MemoryMax`) et une limite douce pour le
ramasse-miettes Go (`GOMEMLIMIT`, 80 % du plafond).

| Service | Plafond | Mesuré sur le VPS après déploiement |
|---|---|---|
| Prometheus (rétention 15 j / 1 Go) | 512 Mo | ~80 Mo |
| Grafana | 512 Mo | ~320 Mo |
| node_exporter | 64 Mo | ~10 Mo |
| Collecteur AegisOps (quelques secondes par minute) | 64 Mo | — |

Le total est plafonné à environ 1,1 Go, soit moins de 10 % des 12 Go du VPS.
Une relance du playbook tient compte de la mémoire déjà utilisée par la stack.
Elle n'est donc pas refusée à cause d'elle.

Sur la VM KVM, `MemoryMax` s'applique (vérifié). Dans un conteneur LXC, il ne
s'applique que si le contrôleur cgroup `memory` est délégué : le rapport final
indique `memory_cap_enforced`. Sur Ubuntu 22.04, Prometheus et node_exporter
sont compilés avec un Go trop ancien pour `GOMEMLIMIT`.

## Lancer

### 1. Créer le secret Grafana (une seule fois)

```bash
openssl rand -base64 24 | tr -d '\n' \
  | ansible-vault encrypt_string --stdin-name monitoring_grafana_admin_password \
  > monitoring-vault.yml
chmod 600 monitoring-vault.yml
```

Le mot de passe est chiffré directement : il n'est jamais écrit en clair.
`monitoring-vault.yml` est ignoré par Git.

> **« New Vault password » ?** Vault ne mémorise aucun mot de passe. Chaque
> chiffrement utilise celui que tu tapes. Pour réutiliser ton mot de passe
> habituel, tape-le simplement. Pour ne plus le taper du tout :
>
> ```bash
> mkdir -p ~/.config/aegisops && chmod 700 ~/.config/aegisops
> ( umask 077; read -rsp 'Vault password: ' p && printf '%s\n' "$p" > ~/.config/aegisops/vault-pass ); echo
> echo 'export ANSIBLE_VAULT_PASSWORD_FILE=~/.config/aegisops/vault-pass' >> ~/.bashrc
> ```
>
> `--ask-vault-pass` devient alors inutile.

### 2. Déployer

```bash
ansible-playbook -i inventories/production/hosts.local.yml \
  playbooks/monitoring.yml -e @monitoring-vault.yml --ask-vault-pass
```

Le playbook est idempotent : tu peux le relancer à tout moment, par exemple
après une modification du tableau de bord ou des plafonds.

### 3. Ouvrir le tableau de bord

En mode `vpn`, connecte le VPN et ouvre <http://10.66.66.1:3000> ; voir
[vpn.md](vpn.md). En mode `ssh_tunnel` :

```bash
ssh -N -L 3000:127.0.0.1:3000 -i ~/.ssh/aegisops_admin aegisadmin@<IP_DU_VPS>
```

Laisse cette commande tourner (elle n'affiche rien), puis ouvre
**<http://localhost:3000>**. Utilise bien `localhost` : Grafana refuse les
autres noms, ce qui bloque les attaques par DNS rebinding. Identifiant
`admin`. Pour lire le mot de passe :

```bash
ansible localhost -m debug -a var=monitoring_grafana_admin_password \
  -e @monitoring-vault.yml --ask-vault-pass
```

Raccourci dans `~/.ssh/config`, à lancer ensuite avec `ssh aegisops-dashboard` :

```text
Host aegisops-dashboard
    HostName <IP_DU_VPS>
    User aegisadmin
    IdentityFile ~/.ssh/aegisops_admin
    IdentitiesOnly yes
    LocalForward 3000 127.0.0.1:3000
    SessionType none
```

L'interface Prometheus (port 9090) n'a pas d'authentification. N'ajoute
`-L 9090:127.0.0.1:9090` que le temps d'une consultation.

## Vérifier

À la fin de chaque déploiement, le rôle contrôle :

1. chaque port écoute uniquement sur son adresse prévue : 9090 et 9100 sur
   `127.0.0.1`, 3000 sur `127.0.0.1` ou, en mode `vpn`, sur `10.66.66.1` ;
2. Prometheus et Grafana répondent ;
3. le mot de passe Grafana déclaré fonctionne (sinon il est réinitialisé) ;
4. le collecteur lit Fail2ban, UFW et SSH sans erreur ;
5. les trois cibles Prometheus sont `up` ;
6. la mémoire réellement consommée (tâche « Report collector sections and
   memory footprint »).

Pour un contrôle indépendant plus tard, mets `verify_monitoring: true` dans
`hardening-vars.yml` et lance `playbooks/verify.yml`. Il vérifie les services,
l'écoute locale et la fraîcheur des métriques de sécurité (moins de 10 min).

## Les deux pages du tableau de bord

Dans Grafana, le dossier **AegisOps** contient deux pages, reliées par le lien
« AegisOps » en haut à droite :

- **AegisOps — VPS** (page d'accueil) : ressources, sécurité, services et
  supervision, comme décrit plus haut.
- **AegisOps — IP bannies** : l'historique Fail2ban. Elle s'ouvre aussi depuis
  le tableau « IP actuellement bannies » de la première page (clic sur le
  tableau → lien « Voir l'historique »).

La page **IP bannies** montre, pour la période choisie en haut à droite (7
jours par défaut, jusqu'aux 15 jours conservés par Prometheus) :

| Panneau | Contenu |
|---|---|
| Compteurs | IP bannies maintenant, IP distinctes sur la période, bannissements, tentatives échouées, liste complète ou tronquée, état de Fail2ban |
| IP bannies dans le temps / nouveaux bannissements par heure | l'activité, jail par jail |
| **Toutes les IP bannies sur la période** | une ligne par adresse : jail, « bannie maintenant », première et dernière vue, durée cumulée. Tri par colonne, filtre par adresse (entonnoir), nombre de lignes en bas |
| Top 10 | les IP restées bannies le plus longtemps |
| Tentatives échouées par heure | les attaques, même celles qui n'ont pas mené à un bannissement |

Le menu **Jail** en haut filtre toutes les vues (`sshd` aujourd'hui, d'autres
jails si tu en ajoutes).

Limites à connaître :

- L'historique commence au déploiement de la supervision.
- Le collecteur passe chaque minute. Un bannissement plus court qu'une minute
  peut donc échapper au tableau (le `bantime` d'AegisOps est de 10 minutes).
- Au-delà de 500 IP bannies **en même temps** dans une jail, la liste est
  tronquée. Le compteur « Liste des IP » l'indique.

## Ce qui est collecté

**node_exporter** fournit les métriques système standard et l'état des unités
systemd suivies : SSH, Fail2ban, UFW, unattended-upgrades et les services de
supervision.

**prometheus-node-exporter-apt** fournit `apt_upgrades_pending` et
`node_reboot_required`.

**aegisops-security-exporter** est un collecteur en lecture seule, écrit en
Python et testé localement. Il produit :

| Métrique | Signification |
|---|---|
| `aegisops_fail2ban_up` | Fail2ban répond |
| `aegisops_fail2ban_jail_banned_current{jail}` / `_banned_total` | IP bannies actuellement / depuis le démarrage |
| `aegisops_fail2ban_jail_failed_current{jail}` / `_failed_total` | tentatives échouées |
| `aegisops_fail2ban_banned_ip{jail,ip}` | liste des IP bannies (500 au maximum par jail) |
| `aegisops_ufw_active`, `aegisops_ufw_rules` | UFW actif, nombre de règles |
| `aegisops_ssh_check{check}` | 1 = conforme (root interdit, mot de passe désactivé, clé activée, keyboard-interactive désactivé) |
| `aegisops_ssh_established_connections` | sessions SSH ouvertes |
| `aegisops_exporter_section_success{section}` | 1 si la section a pu être lue |

Si une source échoue, seule sa section passe à 0. Les autres restent publiées.

## Sécurité de la chaîne logicielle

- Prometheus et node_exporter viennent des dépôts Ubuntu.
- Grafana vient de `apt.grafana.com`. Sa clé publique est versionnée dans le
  rôle (`roles/monitoring/files/grafana-apt.asc`), et son empreinte
  `B53AE77BADB630A683046005963FA27710458545` est vérifiée avant l'ajout du
  dépôt. **Cette clé expire en août 2027** : il faudra la remplacer avant cette
  date.
- Une préférence APT limite ce dépôt tiers au seul paquet `grafana` : il ne
  peut remplacer aucun paquet système.
- `unattended-upgrades` ne met pas Grafana à jour. Fais-le régulièrement :
  `sudo apt update && sudo apt install --only-upgrade grafana`.
- Grafana fonctionne sans inscription, sans accès anonyme, sans
  authentification HTTP Basic, sans télémétrie, sans vérification de mise à
  jour et sans préinstallation de plugins.

## Variables

| Variable | Défaut | Rôle |
|---|---|---|
| `monitoring_approved_host` | `""` | doit valoir l'`inventory_hostname` ciblé |
| `monitoring_admin_user` | `""` | administrateur non root utilisé par Ansible |
| `monitoring_grafana_access` | `ssh_tunnel` | `ssh_tunnel` ou `vpn` (voir plus haut) |
| `monitoring_grafana_admin_user` | `admin` | identifiant Grafana (ne pas changer après le premier déploiement) |
| `monitoring_grafana_admin_password` | `""` | secret Vault, 16 à 128 caractères `[A-Za-z0-9+/=._~@%^*!:,-]` |
| `monitoring_prometheus_retention_time` | `15d` | durée de conservation |
| `monitoring_prometheus_retention_size` | `1GB` | taille maximale de la base |
| `monitoring_scrape_interval` | `30s` | 10 s au minimum |
| `monitoring_prometheus_memory_max_mb` | `512` | plafond Prometheus |
| `monitoring_grafana_memory_max_mb` | `512` | plafond Grafana |
| `monitoring_node_exporter_memory_max_mb` | `64` | plafond node_exporter |
| `monitoring_memory_reserve_mb` | `1024` | mémoire qui doit rester libre |
| `monitoring_collector_interval` | `1min` | cadence du collecteur |
| `monitoring_collector_max_banned_ips` | `500` | taille maximale de la liste d'IP bannies, par jail |

L'adresse d'écoute et les ports sont fixés dans `roles/monitoring/vars/main.yml`.
Ce sont des choix de sécurité, pas des réglages.

## Dépannage

| Symptôme | Cause et solution |
|---|---|
| `channel 2: open failed: connect failed: Connection refused` dans le tunnel | Grafana n'écoute pas : la supervision n'est pas déployée, ou `grafana-server` est arrêté (`sudo systemctl status grafana-server`). |
| Le navigateur redirige ou refuse `http://127.0.0.1:3000` | Utilise `http://localhost:3000`. |
| `bind [127.0.0.1]:3000: Address already in use` | Un autre programme ou tunnel utilise le port 3000 sur ton poste : ferme-le, ou utilise `-L 3001:127.0.0.1:3000` et ouvre `http://localhost:3001`. |
| `No package matching 'grafana' is available` | Index APT pas à jour. Le rôle le rafraîchit maintenant automatiquement ; sinon lance `sudo apt update` sur le VPS. |
| Panneaux Fail2ban ou UFW vides | `sudo systemctl start aegisops-security-exporter.service`, puis `journalctl -u aegisops-security-exporter.service` et `cat /var/lib/prometheus/node-exporter/aegisops.prom`. |
| « Fraîcheur du collecteur » en rouge | Le timer ne tourne plus : `systemctl status aegisops-security-exporter.timer`. |
| Mot de passe Grafana refusé | Relance le playbook : il réapplique le mot de passe du fichier Vault. |
| Grafana redémarre en boucle | Plafond mémoire atteint : `systemctl show -p MemoryCurrent,MemoryMax grafana-server`, puis augmente `monitoring_grafana_memory_max_mb`. |

## Revenir en arrière

La désinstallation est manuelle et sans risque pour l'accès SSH. Sur le VPS :

```bash
sudo systemctl disable --now aegisops-security-exporter.timer grafana-server prometheus prometheus-node-exporter
sudo apt purge grafana prometheus prometheus-node-exporter prometheus-node-exporter-collectors
sudo rm -rf /etc/systemd/system/{prometheus,prometheus-node-exporter,grafana-server}.service.d \
  /etc/systemd/system/aegisops-security-exporter.* /usr/local/sbin/aegisops-security-exporter \
  /etc/aegisops /etc/apt/sources.list.d/grafana.list /etc/apt/preferences.d/aegisops-grafana \
  /etc/apt/keyrings/grafana.asc /var/lib/grafana /var/lib/prometheus
sudo systemctl daemon-reload && sudo apt update
```

`/var/lib/prometheus` contient l'historique des métriques : il sera perdu.
