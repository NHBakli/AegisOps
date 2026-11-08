# Audit

## À quoi ça sert

`playbooks/audit.yml` fait l'état des lieux de la sécurité du serveur et écrit
un rapport JSON sur ton poste. **Il ne modifie jamais le serveur** : il lit des
informations et des commandes en lecture seule. Lance-le avant le
durcissement pour connaître ton point de départ, puis après pour comparer.

## Lancer

```bash
ansible-playbook -i inventories/production/hosts.local.yml playbooks/audit.yml
```

L'audit se connecte avec l'utilisateur de l'inventaire (`ansible_user`) et
utilise `sudo`. Après le durcissement SSH, root ne peut plus se connecter :
mets `ansible_user: aegisadmin` et `ansible_ssh_private_key_file` dans ton
inventaire (voir [getting-started.md](getting-started.md)).

## Ce que l'audit contrôle

| Tag | Fichier | Ce qui est lu | Contrôles notés |
|---|---|---|---|
| `system` | `system.yml` | Distribution, version, noyau, architecture, mémoire | aucun (affichage seulement) |
| `ssh` | `ssh.yml` | Configuration effective globale, `sshd -T` | `root_login`, `password_auth`, `pubkey_auth`, `keyboard_interactive` |
| `user` | `user.yml` | Comptes (`getent passwd`), groupe `sudo`, comptes UID 0 | `root_accounts`, `ssh_admin_user`, `sudo_members` |
| `network` | `network.yml` | Ports en écoute, `ss -tuln` | aucun (affichage seulement) |
| `firewall` | `firewall.yml` | Paquets et état d'UFW et de Fail2ban | `ufw_installed`, `ufw_active`, `fail2ban_installed`, `fail2ban_active` |
| `updates` | `updates.yml` | Paquet `unattended-upgrades`, `apt-config dump`, `apt-daily-upgrade.timer` | `package_installed`, `periodic_updates`, `upgrade_timer` |
| `report` | `report.yml` | Résultats des contrôles ci-dessus | écrit le rapport JSON |

Soit 14 contrôles notés au total.

Quelques précisions :

- **SSH** : `sshd -T` sans contexte montre la configuration **globale**. Des
  règles `Match` peuvent changer le comportement pour certains utilisateurs ou
  adresses ; elles demandent une revue séparée. `verify.yml` fait un contrôle
  plus précis, avec le contexte de connexion.
- **`ssh_admin_user`** vaut `WARN` si l'audit se connecte en `root`.
- **`sudo_members`** vaut toujours `REVIEW` : c'est à toi de regarder qui a
  des droits d'administration.
- **Réseau et système** sont affichés pour information, sans statut.

## Les statuts

| Statut | Signification |
|---|---|
| `PASS` | Le contrôle est conforme. |
| `FAIL` | Problème de sécurité net (par exemple root autorisé en SSH). |
| `WARN` | Protection absente ou inactive (par exemple Fail2ban non installé). |
| `REVIEW` | Impossible de conclure automatiquement : la commande a échoué ou le point demande un regard humain. |

## Les tags

Tu peux lancer une partie de l'audit seulement :

```bash
ansible-playbook -i inventories/production/hosts.local.yml playbooks/audit.yml --tags ssh
```

Les tâches `ssh`, `user`, `firewall` et `updates` portent aussi le tag
`report`. Donc :

- `--tags report` lance automatiquement ces quatre contrôles **et** écrit le
  rapport ;
- `--tags ssh` (ou `user`, `firewall`, `updates`) affiche le résultat du
  domaine, **sans écrire de rapport** ;
- `--tags system` et `--tags network` affichent seulement des informations.

Attention : le tag de l'audit est `user`, au singulier, alors que celui du
durcissement est `users`.

## Le rapport JSON

Le rapport est écrit sur **ton poste** (pas sur le serveur) dans
`reports/<inventory_hostname>.json`, par exemple `reports/my-vps.json`. Le
dossier est créé avec les droits `0700` et le fichier avec `0600`, car il
décrit les faiblesses de ton serveur. `reports/` est ignoré par Git.

Structure :

```json
{
  "tool": "AegisOps",
  "hostname": "my-vps",
  "summary": {
    "total": 14,
    "passed": 5,
    "failed": 2,
    "warnings": 6,
    "review": 1
  },
  "system": {
    "os": "Ubuntu",
    "version": "24.04",
    "kernel": "6.8.0-...-generic",
    "architecture": "x86_64"
  },
  "checks": {
    "ssh": {
      "root_login": {
        "status": "FAIL",
        "description": "Global sshd configuration should disable root login; Match rules require separate review"
      }
    },
    "users": {},
    "firewall": {},
    "updates": {}
  }
}
```

- Les compteurs de `summary` sont des **nombres entiers** JSON (pas des
  chaînes) : tu peux les comparer directement dans un script. Un test
  (`tests/audit/test_report.py`) le garantit.
- Chaque contrôle de `checks` contient un `status` et une `description`.
- Pour écrire le rapport ailleurs, passe
  `-e audit_report_directory=/chemin/absolu`.

Exemple de lecture rapide :

```bash
python3 -m json.tool reports/my-vps.json
python3 -c 'import json; print(json.load(open("reports/my-vps.json"))["summary"])'
```

## Vérifier

Après un audit, le `PLAY RECAP` doit afficher `changed=0` : aucune
modification n'a eu lieu sur le serveur. Le seul fichier écrit est le
rapport, sur ton poste.

## Dépannage

- **`UNREACHABLE`** : connexion SSH impossible. Vérifie l'inventaire
  (`ansible_host`, `ansible_user`, `ansible_port`) et teste `ssh` à la main.
- **Statut `REVIEW` sur un contrôle SSH** : `sshd -T` a échoué, souvent à cause
  d'une configuration SSH invalide. Lance `sudo sshd -t` sur le serveur.
- **Pas de fichier dans `reports/`** : tu as lancé un tag sans `report`.
