# AegisOps

AegisOps est un projet Ansible qui **audite**, **durcit** puis **vérifie** la
sécurité d'un serveur Ubuntu, et peut y ajouter une **supervision** locale
(Prometheus et Grafana). Chaque étape est un playbook séparé. Les changements
sensibles (SSH, pare-feu, redémarrages) ne s'appliquent qu'après des
confirmations explicites, propres à chaque serveur, pour ne jamais te couper
l'accès.

Plateformes prises en charge : **Ubuntu 22.04 et 24.04**. La cible de référence
est un VPS Ubuntu 24.04 sur une machine virtuelle KVM. Les rôles savent aussi
reconnaître un conteneur LXC et y exigent des confirmations supplémentaires.

## Ce que fait AegisOps

- Audit en lecture seule avec un rapport JSON (`reports/<hôte>.json`).
- Création d'un administrateur non-root avec clé SSH et `sudo` explicite.
- SSH : interdiction de root, des mots de passe et de l'authentification
  interactive, avec test d'une nouvelle connexion et retour arrière automatique.
- UFW : règles préparées, activation seulement sur décision séparée.
- Fail2ban : jail SSH qui ignore ton adresse d'administration.
- Mises à jour de sécurité automatiques, sans redémarrage par défaut.
- Vérification indépendante de l'état réel du serveur.
- Supervision accessible uniquement par tunnel SSH (aucun port ouvert).

## Ce qu'il ne fait pas

- Il ne promet pas une sécurité absolue : c'est une base raisonnable et
  vérifiable.
- Il ne gère pas les applications installées sur le serveur (par exemple K3s),
  le filtrage réseau de l'hébergeur ou de Proxmox, ni IPv6 pour Fail2ban.
- Il ne supprime pas de compte, ne remplace pas toute la configuration SSH et
  n'active pas UFW ni le redémarrage automatique sans ton accord explicite.

## Le principe en un schéma

```text
             ┌───────────┐    ┌──────────────┐    ┌────────────┐
 ton poste   │   audit   │ -> │  hardening   │ -> │   verify   │
 (Ansible) ->│ lecture   │    │ users → ssh  │    │  lecture   │
             │ seule     │    │ → firewall → │    │  seule     │
             │ + rapport │    │ fail2ban →   │    │            │
             └───────────┘    │ updates      │    └─────┬──────┘
                              └──────────────┘          │
                                                ┌───────▼────────┐
                                                │   monitoring   │
                                                │ Prometheus +   │
                                                │ Grafana via    │
                                                │ tunnel SSH     │
                                                └────────────────┘
```

## Prérequis

- Un poste Linux avec Python 3, `ansible-core` (la CI utilise la version 2.16
  fournie par Ubuntu 24.04) et un client OpenSSH.
- Un serveur Ubuntu 22.04 ou 24.04 joignable en SSH par clé, avec `root` ou un
  utilisateur `sudo` pour la première connexion.
- Un accès de secours : console de l'hébergeur et, si possible, un snapshot.

## Démarrage rapide

Le guide détaillé, avec les explications de chaque étape, est dans
[docs/getting-started.md](docs/getting-started.md).

```bash
# 1. Collections Ansible épinglées
ansible-galaxy collection install -r requirements.yml

# 2. Inventaire local (ignoré par Git) : adresse, utilisateur initial, port
mkdir -p inventories/production
cp inventories/example/hosts.yml inventories/production/hosts.local.yml
# édite ce fichier : ansible_host, ansible_user (root au départ), ansible_port

# 3. Variables locales (ignorées par Git)
cp hardening-vars.yml.example hardening-vars.yml
ssh-keygen -t ed25519 -f ~/.ssh/aegisops_admin -C "aegisadmin@aegisops"
# colle ~/.ssh/aegisops_admin.pub dans users_hardening_admin_public_keys

# 4. Audit (ne modifie rien)
ansible-playbook -i inventories/production/hosts.local.yml playbooks/audit.yml

# 5. Création de l'administrateur seulement
ansible-playbook -i inventories/production/hosts.local.yml \
  playbooks/hardening.yml --tags users

# 6. Test manuel, dans un autre terminal (garde la session root ouverte)
ssh -i ~/.ssh/aegisops_admin aegisadmin@203.0.113.10 'sudo -n true && echo OK'
# puis users_hardening_admin_bootstrapped: true et les confirmations

# 7. Durcissement complet (ssh, firewall, fail2ban, updates)
ansible-playbook -i inventories/production/hosts.local.yml playbooks/hardening.yml

# 8. Vérification indépendante (choisis les sections verify_*)
ansible-playbook -i inventories/production/hosts.local.yml playbooks/verify.yml

# 9. Supervision, puis tunnel SSH vers Grafana
ansible-playbook -i inventories/production/hosts.local.yml \
  playbooks/monitoring.yml -e @monitoring-vault.yml --ask-vault-pass
ssh -N -L 3000:127.0.0.1:3000 -i ~/.ssh/aegisops_admin aegisadmin@203.0.113.10
# ouvre http://localhost:3000
```

Remplace `203.0.113.10` (adresse de documentation) par l'adresse de ton
serveur.

## Les playbooks

| Playbook | À quoi il sert | Modifie le serveur ? | Commande principale |
|---|---|---|---|
| `playbooks/audit.yml` | Inspecter et produire un rapport JSON | Non | `ansible-playbook -i <inventaire> playbooks/audit.yml` |
| `playbooks/hardening.yml` | Appliquer les cinq domaines de durcissement | Oui | `ansible-playbook -i <inventaire> playbooks/hardening.yml [--tags ssh]` |
| `playbooks/verify.yml` | Contrôler l'état réel, sans croire les variables | Non | `ansible-playbook -i <inventaire> playbooks/verify.yml` |
| `playbooks/vpn.yml` | Installer le VPN WireGuard (ouvre 51820/udp) pour accéder au tableau de bord | Oui | `ansible-playbook -i <inventaire> playbooks/vpn.yml` |
| `playbooks/monitoring.yml` | Installer Prometheus, node_exporter et Grafana (accès par tunnel SSH ou VPN) | Oui | `ansible-playbook -i <inventaire> playbooks/monitoring.yml -e @monitoring-vault.yml --ask-vault-pass` |

Tags de `hardening.yml` : `users`, `ssh`, `firewall`, `fail2ban`, `updates`.
Sans tag, tous les domaines sont parcourus dans cet ordre : chacun doit alors
être configuré, sinon son garde arrête le playbook avant de modifier ce
domaine.

## Documentation

| Document | Contenu |
|---|---|
| [docs/README.md](docs/README.md) | Index et ordre de lecture |
| [docs/getting-started.md](docs/getting-started.md) | Guide pas à pas, du clone au serveur supervisé |
| [docs/architecture.md](docs/architecture.md) | Organisation du dépôt, conventions, conception |
| [docs/configuration.md](docs/configuration.md) | Référence de toutes les variables |
| [docs/audit.md](docs/audit.md) | Contrôles de l'audit et format du rapport |
| [docs/users-hardening.md](docs/users-hardening.md) | Compte administrateur |
| [docs/ssh-hardening.md](docs/ssh-hardening.md) | Durcissement SSH |
| [docs/firewall-hardening.md](docs/firewall-hardening.md) | Pare-feu UFW |
| [docs/fail2ban.md](docs/fail2ban.md) | Jail SSH Fail2ban |
| [docs/updates-hardening.md](docs/updates-hardening.md) | Mises à jour automatiques |
| [docs/verify.md](docs/verify.md) | Vérification indépendante |
| [docs/monitoring.md](docs/monitoring.md) | Supervision Prometheus et Grafana |
| [docs/vpn.md](docs/vpn.md) | VPN WireGuard : accès au tableau de bord depuis PC, téléphone et laptop |
| [docs/recovery.md](docs/recovery.md) | Récupérer l'accès et annuler un changement |
| [docs/testing.md](docs/testing.md) | Tests locaux et CI |

## Principes de sécurité

- **Pas de verrouillage de root sans solution de rechange** : l'administrateur
  est créé et testé d'abord ; chaque changement d'accès est suivi d'une nouvelle
  connexion SSH indépendante, et SSH revient à l'ancienne configuration si ce
  test échoue.
- **Approbations par serveur** : les variables `*_approved_host` doivent valoir
  le nom exact de l'hôte dans l'inventaire. Une approbation ne s'applique donc
  jamais par erreur à un autre serveur.
- **Confirmations honnêtes** : les variables `*_confirmed` déclarent des faits
  que tu as vérifiés (console disponible, connexion testée). Ne les passe à
  `true` qu'après les avoir vraiment testés.
- **Décisions séparées** : activer UFW (`firewall_hardening_activate`) et
  autoriser le redémarrage automatique (`updates_hardening_automatic_reboot`)
  sont des choix distincts, désactivés par défaut.
- **L'audit ne modifie jamais rien**, et `verify.yml` non plus.
- **Aucun secret dans Git** : `hardening-vars.yml`, `monitoring-vault.yml`,
  l'inventaire local et `reports/` sont ignorés par Git.

## Vérifications locales

```bash
ansible-galaxy collection install -r requirements.yml --force
for p in audit hardening verify monitoring vpn; do
  ansible-playbook -i inventories/example/hosts.yml playbooks/$p.yml --syntax-check
done
ansible-lint --offline
python3 -m unittest discover -s tests -p 'test_*.py'
```

Ces tests tournent sur ton poste, sans serveur distant. Voir
[docs/testing.md](docs/testing.md) pour ce qu'ils couvrent et ce qu'ils ne
peuvent pas prouver.

## Licence

Projet distribué sous licence [MIT](LICENSE).
