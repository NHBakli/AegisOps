# Tests

Les tests d'AegisOps tournent **sur ton poste**, sans serveur distant. Ils
vérifient que les gardes refusent les situations dangereuses et que les
assertions de vérification détectent les mauvais états.

## Lancer les vérifications locales

Depuis la racine du dépôt :

```bash
# 1. Collections épinglées
ansible-galaxy collection install -r requirements.yml --force

# 2. Syntaxe des quatre playbooks, avec l'inventaire d'exemple
ansible-playbook -i inventories/example/hosts.yml playbooks/audit.yml --syntax-check
ansible-playbook -i inventories/example/hosts.yml playbooks/hardening.yml --syntax-check
ansible-playbook -i inventories/example/hosts.yml playbooks/verify.yml --syntax-check
ansible-playbook -i inventories/example/hosts.yml playbooks/monitoring.yml --syntax-check

# 3. Bonnes pratiques Ansible, sans téléchargement
ansible-lint --offline

# 4. Tests fonctionnels locaux
python3 -m unittest discover -s tests -p 'test_*.py'
```

Pour lancer un seul domaine ou un seul test :

```bash
python3 -m unittest discover -s tests/firewall -t . -p 'test_*.py'
python3 -m unittest tests.verify.test_verify -v
```

Tout doit se terminer par `OK` (tests) et sans erreur (syntaxe, lint).

## Comment un test fonctionne

Chaque fichier `test_*.py` utilise `unittest` et lance `ansible-playbook` sur
`localhost` avec un petit playbook du même dossier. Ce playbook :

1. définit des données fabriquées : sortie de `ufw status`, de `sshd -T`,
   contenu de `/proc/net/tcp6`, fichiers Fail2ban, etc. ;
2. importe **le vrai fichier de tâches** du rôle (par exemple
   `roles/firewall_hardening/tasks/manifest_safety.yml`) ;
3. vérifie que l'assertion réussit dans le bon cas et échoue dans le mauvais.

Les tests utilisent des dossiers temporaires pour Ansible et ne modifient ni
ton poste, ni un serveur.

## Ce que couvre chaque dossier

| Dossier | Ce qui est testé |
|---|---|
| `tests/audit/` | Les compteurs du rapport JSON sont des entiers ; `--tags report` inclut bien les contrôles nécessaires. |
| `tests/hardening/` | Le contrat des tags de `hardening.yml` : sans tag, tous les rôles ; chaque tag, son seul rôle ; `--tags users` s'arrête au préflight sans rien modifier. |
| `tests/users/` | Le rôle refuse une configuration manquante, le compte `root` et un nouveau compte avec `sudo` par mot de passe, avant toute modification. |
| `tests/ssh/` | Approbation requise ; refus des `Match`, des `Include` non standard et d'un dossier d'inclusion en lien symbolique ; contrôles de `ssh.socket` sur 24.04. |
| `tests/firewall/` | Plateformes acceptées, détection de la virtualisation, refus d'une installation qui supprime des paquets, règles invalides ou en double, manifestes AegisOps, lecture de `CAP_NET_ADMIN`, état d'un UFW actif. |
| `tests/fail2ban/` | Approbation requise, plateformes, source du journal SSH (service ou socket), rendu de la jail, liste `ignoreip`, règle de bannissement, refus d'une autre jail `[sshd]`, adresse IPv4 seulement, refus d'un SSH en IPv6. |
| `tests/updates/` | Redémarrage soumis à approbation, plateformes, revue des origines APT personnalisées, politique de sécurité seule. |
| `tests/verify/` | Refus d'une vérification vide ou filtrée par tags ; détection d'une régression SSH (root ou mot de passe), d'un sudoers absent, d'un UFW inactif, d'une jail incorrecte, d'un écouteur IPv6, d'une origine APT non sécurité. |
| `tests/monitoring/` | Gardes du préflight (et secret jamais affiché), écoute sur `127.0.0.1` seulement dans les modèles, collecteur de sécurité, assertions de `verify_monitoring`, empreinte de la clé Grafana, tableau de bord. |

## Ce que les tests locaux ne peuvent pas prouver

Les fixtures imitent les sorties de commandes. Elles ne remplacent pas un vrai
système. Restent à valider sur une VM de test, puis sur le serveur :

- le comportement réel d'OpenSSH et de `ssh.socket` sur Ubuntu 24.04 après un
  rechargement ;
- le filtrage réel d'UFW et d'iptables par le noyau, et le filtrage de
  l'hébergeur ou de Proxmox ;
- un vrai bannissement Fail2ban depuis Internet ;
- l'installation des paquets APT, les timers systemd et `unattended-upgrades` ;
- le démarrage réel de Prometheus et Grafana et leurs plafonds mémoire ;
- l'idempotence (deux exécutions successives) sur un vrai serveur.

Pour une vérification sur un serveur réel, utilise `verify.yml` : il lit
l'état effectif sans le modifier.

## La CI GitHub

`.github/workflows/quality.yml` s'exécute à chaque push et pull request, sur
`ubuntu-24.04`. Il installe `ansible-core` et `ansible-lint` depuis les
paquets Ubuntu, installe les collections de `requirements.yml`, puis lance
exactement les commandes de la section précédente : vérification de syntaxe
des quatre playbooks, `ansible-lint --offline` et les tests `unittest`.

La CI ne se connecte à aucun serveur et n'utilise aucun secret.
