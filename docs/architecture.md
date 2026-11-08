# Architecture

Cette page explique comment le dépôt est organisé et pourquoi il est conçu
ainsi. Pour l'utiliser, commence plutôt par
[getting-started.md](getting-started.md).

## Le dépôt, fichier par fichier

```text
AegisOps/
├── ansible.cfg                  réglages Ansible : inventaire d'exemple par défaut, rôles dans ./roles
├── requirements.yml             collections Ansible épinglées (ansible.posix, community.general)
├── hardening-vars.yml.example   modèle des variables ; copie-le en hardening-vars.yml
├── hardening-vars.yml           tes variables locales (ignoré par Git)
├── monitoring-vault.yml         secret Grafana chiffré par Vault (ignoré par Git)
├── inventories/
│   ├── example/hosts.yml        inventaire fictif (203.0.113.10), versionné
│   └── production/hosts.local.yml  ton inventaire réel (ignoré par Git)
├── playbooks/
│   ├── audit.yml                audit en lecture seule + rapport JSON
│   ├── hardening.yml            durcissement, en deux plays
│   ├── verify.yml               vérification indépendante, en lecture seule
│   ├── monitoring.yml           déploiement de Prometheus et Grafana
│   └── vpn.yml                  serveur VPN WireGuard (accès au tableau de bord)
├── roles/
│   ├── audit/                   contrôles et rapport (tasks/ uniquement)
│   ├── users_hardening/         compte administrateur non-root et sudo
│   ├── ssh_hardening/           politique SSH avec test et retour arrière
│   ├── firewall_hardening/      préparation et activation d'UFW
│   ├── fail2ban/                jail SSH et test de bannissement facultatif
│   ├── updates_hardening/       unattended-upgrades et timers APT
│   ├── verify/                  relecture de l'état réel, section par section
│   ├── monitoring/              Prometheus, node_exporter, Grafana, collecteur
│   └── wireguard/               serveur WireGuard wg0 et configurations des appareils
├── scripts/
│   └── aegisops-wg-peer         crée la clé d'un appareil VPN, affiche son QR code
├── reports/                     rapports d'audit <hôte>.json (ignoré par Git)
├── tests/                       tests locaux Python + fixtures Ansible
├── docs/                        cette documentation
├── .github/workflows/quality.yml  CI : syntaxe, lint, tests
└── LICENSE                      licence MIT
```

Dans chaque rôle, on retrouve la structure standard d'Ansible :

| Dossier | Contenu |
|---|---|
| `tasks/` | Les tâches. `main.yml` importe les autres fichiers. |
| `defaults/main.yml` | Les valeurs **modifiables** par l'utilisateur, avec des valeurs sûres par défaut. |
| `vars/main.yml` | Les valeurs **internes et fixes** (commande de test SSH, ports de supervision). Ne les surcharge pas. |
| `handlers/` | Actions déclenchées seulement après un changement (recharger SSH, Fail2ban). |
| `templates/` | Fichiers Jinja2 rendus sur le serveur (jail Fail2ban, politique APT, configuration Grafana). |
| `files/` | Fichiers copiés tels quels (clé APT de Grafana, collecteur, tableau de bord). |

## Le flux de travail

```text
audit  ->  hardening  ->  verify  ->  monitoring
(lit)      (modifie)      (lit)       (installe)
```

Les quatre playbooks sont indépendants. Ils visent tous le groupe `vps` et
chargent tous le même fichier de variables : `hardening-vars.yml`, ou à défaut
`hardening-vars.yml.example`.

- **`audit.yml`** se connecte avec l'utilisateur de l'inventaire. Il ne fait
  qu'observer. Le rapport est écrit sur ton poste, pas sur le serveur.
- **`hardening.yml`** applique les changements (voir plus bas).
- **`verify.yml`** ne croit pas les variables : il lit l'état réel (`sshd -T`,
  `ufw status verbose`, `fail2ban-client`, `apt-config dump`…) et le compare à
  ce que tu attends.
- **`monitoring.yml`** n'est pas un domaine de durcissement : il est donc
  séparé de `hardening.yml` et n'ouvre aucun port.

## Les deux plays de `hardening.yml`

Le durcissement a un problème de poule et d'œuf : il faut un administrateur
non-root pour durcir SSH, mais cet administrateur n'existe pas encore. Le
playbook est donc découpé en deux plays.

```text
Play 1 « Bootstrap »                     Play 2 « Durcissement »
connexion : utilisateur de l'inventaire  connexion : NOUVELLE session SSH
            (root au départ)                         users_hardening_admin_username
rôle : users_hardening (tag users)                   + ssh_hardening_probe_private_key
exécuté seulement si                     rôles : ssh_hardening    (tag ssh)
users_hardening_admin_bootstrapped              firewall_hardening (tag firewall)
vaut false                                      fail2ban           (tag fail2ban)
                                                updates_hardening  (tag updates)
```

- `--tags users` ne lance que le play 1 : il crée le compte, rien d'autre.
- Les autres tags ne lancent que leur rôle dans le play 2. Ils supposent que
  le compte existe déjà.
- Sans tag, les deux plays s'enchaînent. Le play 2 ouvre une nouvelle
  connexion avec l'administrateur : si sa clé ou son `sudo` ne marchent pas,
  l'échec arrive avant tout changement SSH.
- Une fois `users_hardening_admin_bootstrapped: true`, le play 1 est sauté.
  C'est indispensable dès que root ne peut plus se connecter.

`verify.yml` et `monitoring.yml` se connectent eux aussi directement avec
l'administrateur et `ssh_hardening_probe_private_key`.

## Les gardes : vérifier avant de modifier

Chaque rôle qui modifie le serveur commence par un **préflight** : une série
d'assertions (`ansible.builtin.assert`) qui arrête le playbook **avant le
premier changement** si une condition manque. Exemples :

- plateforme : Ubuntu 22.04 ou 24.04 uniquement ;
- mode `--check` refusé pour SSH, UFW, Fail2ban, mises à jour et supervision,
  car il ne peut pas tester réellement une connexion ;
- approbation de l'hôte : `ssh_hardening_approved_host`,
  `firewall_hardening_approved_host`, `fail2ban_hardening_approved_host`,
  `updates_hardening_reboot_approved_host`, `monitoring_approved_host` doivent
  valoir exactement `inventory_hostname`. Une approbation écrite pour `my-vps`
  ne vaut rien pour un autre serveur ;
- confirmations explicites : `*_recovery_confirmed` (console ou snapshot
  disponible), `*_independent_login_confirmed` (connexion admin testée),
  `*_lxc_compatibility_confirmed` (filtrage validé dans un conteneur) ;
- sécurité de l'existant : configuration SSH avec `Match` refusée, UFW déjà
  actif sans manifeste AegisOps refusé, autre jail `[sshd]` refusée, origines
  APT personnalisées refusées sans revue.

Après le changement, les rôles sensibles **retestent** avec une connexion SSH
indépendante (`ssh -F /dev/null`, sans réutiliser la session d'Ansible). En
cas d'échec, un bloc `rescue` restaure l'état précédent : configuration SSH
sauvegardée, UFW désactivé, jail Fail2ban précédente.

### Les gardes LXC

La cible actuelle est une VM KVM. Les rôles UFW et Fail2ban détectent quand
même les conteneurs (`lxc`, `container`, `openvz`, `docker`, `podman`). Dans
un conteneur, la capacité `CAP_NET_ADMIN` ne prouve pas que l'hôte filtre
vraiment les paquets : ces rôles exigent alors une confirmation supplémentaire
(`*_lxc_compatibility_confirmed`). Ces gardes restent utiles pour d'autres
serveurs.

## Conventions de nommage

- Un rôle par domaine, nommé `<domaine>_hardening` (sauf `fail2ban`, `audit`,
  `verify` et `monitoring`).
- **Chaque rôle préfixe ses variables** par son nom : `users_hardening_*`,
  `ssh_hardening_*`, `firewall_hardening_*`, `updates_hardening_*`. Le rôle
  `fail2ban` utilise `fail2ban_hardening_*`, `verify` utilise `verify_*`,
  `monitoring` utilise `monitoring_*`, et les variables internes de l'audit
  commencent par `audit_`. Tu sais ainsi toujours quel rôle lit une variable.
- `verify` relit volontairement les variables des autres rôles (par exemple
  `ssh_hardening_disable_root_login`) : la vérification attend ce que tu as
  demandé au durcissement.
- Les fichiers posés sur le serveur portent le nom `aegisops` :
  `/etc/sudoers.d/90-aegisops-<admin>`, `/etc/fail2ban/jail.d/90-aegisops-sshd.local`,
  `/etc/apt/apt.conf.d/99aegisops-unattended-upgrades`, `/var/lib/aegisops/`,
  le bloc `# BEGIN AEGISOPS SSH HARDENING` dans `sshd_config`.

## Pourquoi tant de petits fichiers de tâches

Les assertions importantes sont isolées dans de petits fichiers
(`config_safety.yml`, `manifest_safety.yml`, `verify_ignoreip.yml`…). Les
tests peuvent ainsi importer **exactement le même fichier** que le rôle et lui
donner des sorties de commandes fabriquées, sans toucher à un vrai serveur.

## Comment fonctionnent les tests

Les tests sont écrits avec `unittest` (Python standard). Chaque test lance
`ansible-playbook` sur `localhost` avec un petit playbook de test
(`tests/<domaine>/*.yml`) qui :

1. définit des données d'entrée (« fixtures ») : sortie de `ufw status`, de
   `sshd -T`, de `/proc/net/tcp6`, etc. ;
2. importe le fichier de tâches réel du rôle ;
3. vérifie que l'assertion réussit ou échoue comme prévu.

Aucun test ne se connecte à un serveur distant ni ne modifie ton poste. Voir
[testing.md](testing.md).

## La CI

`.github/workflows/quality.yml` tourne à chaque push et pull request, sur
Ubuntu 24.04 :

1. installe `ansible-core` et `ansible-lint` depuis les paquets Ubuntu ;
2. installe les collections de `requirements.yml` ;
3. vérifie la syntaxe des quatre playbooks avec l'inventaire d'exemple ;
4. lance `ansible-lint --offline` ;
5. lance tous les tests `python3 -m unittest discover -s tests -p 'test_*.py'`.
