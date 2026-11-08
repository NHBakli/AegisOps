# Guide de démarrage

Ce guide t'emmène d'un clone tout neuf du dépôt à un serveur durci, vérifié et
supervisé. Suis les étapes dans l'ordre : chacune prépare la suivante.

Dans les exemples :

- `my-vps` est le nom de l'hôte dans l'inventaire ;
- `203.0.113.10` est l'adresse du serveur (adresse réservée à la
  documentation, remplace-la par la tienne) ;
- `198.51.100.7` est l'adresse IPv4 publique de ton poste vue par le serveur ;
- `aegisadmin` est le futur compte administrateur ;
- `~/.ssh/aegisops_admin` est sa clé privée.

## Étape 0 — Avant de toucher au serveur

Vérifie que tu peux ouvrir la **console de ton hébergeur** (accès « VNC » ou
« console série »). C'est ta porte de secours si SSH ne répond plus. Si ton
hébergeur le permet, fais un **snapshot**.

Lis [recovery.md](recovery.md) une première fois maintenant, pas pendant une
panne.

## Étape 1 — Préparer ton poste

Il te faut Python 3, Git, un client OpenSSH et `ansible-core`. La CI du projet
utilise `ansible-core` 2.16, la version fournie par Ubuntu 24.04 :

```bash
sudo apt install ansible-core git openssh-client
ansible --version
```

Clone le dépôt et installe les collections Ansible. Leurs versions sont
épinglées dans `requirements.yml` (`ansible.posix` 2.2.0 et
`community.general` 8.3.0) :

```bash
git clone <url-du-dépôt> AegisOps
cd AegisOps
ansible-galaxy collection install -r requirements.yml --force
```

`--force` remplace une version plus récente déjà installée. Si Ansible affiche
que `community.general 13.x` ne supporte pas Core 2.16, c'est cette commande
qui règle le problème.

Toutes les commandes suivantes se lancent depuis la racine du dépôt.

**Si ça échoue** : `ansible-galaxy` a besoin d'Internet. Vérifie aussi que tu
es bien dans le dossier qui contient `requirements.yml`.

## Étape 2 — Créer la clé SSH de l'administrateur

Génère une paire de clés dédiée. Choisis un autre nom si le fichier existe
déjà :

```bash
ssh-keygen -t ed25519 -f ~/.ssh/aegisops_admin -C "aegisadmin@aegisops"
cat ~/.ssh/aegisops_admin.pub
```

- `~/.ssh/aegisops_admin` est la **clé privée** : elle reste sur ton poste et
  ne se partage jamais.
- `~/.ssh/aegisops_admin.pub` est la **clé publique** : c'est elle qui sera
  copiée sur le serveur.

Connecte-toi ensuite une fois au serveur avec ton accès actuel, pour
enregistrer son empreinte dans `~/.ssh/known_hosts`. Compare l'empreinte
affichée avec celle donnée par la console de l'hébergeur :

```bash
ssh root@203.0.113.10
```

C'est indispensable : les tests de connexion d'AegisOps refusent un serveur
dont l'empreinte est inconnue (`StrictHostKeyChecking=yes`).

## Étape 3 — Créer ton inventaire local

L'inventaire dit à Ansible quel serveur viser. `ansible.cfg` pointe par défaut
vers `inventories/example/hosts.yml`, qui contient une adresse fictive : tu ne
peux donc pas viser un vrai serveur par accident. Crée ton propre inventaire,
ignoré par Git :

```bash
mkdir -p inventories/production
cp inventories/example/hosts.yml inventories/production/hosts.local.yml
```

Édite `inventories/production/hosts.local.yml` :

```yaml
---
all:
  children:
    vps:
      hosts:
        my-vps:
          ansible_host: 203.0.113.10
          ansible_user: root
          ansible_port: 22
```

- Le groupe doit s'appeler `vps` : tous les playbooks visent ce groupe.
- `my-vps` est le nom de l'hôte. Retiens-le : les approbations
  (`*_approved_host`) devront valoir exactement ce nom.
- `ansible_user` est l'utilisateur de la **première** connexion : `root`, ou
  l'utilisateur `sudo` fourni par l'hébergeur.
- `ansible_port` est le port SSH réel. Il est obligatoire pour UFW et
  Fail2ban.

Chaque commande qui vise ce serveur doit contenir
`-i inventories/production/hosts.local.yml`.

## Étape 4 — Préparer `hardening-vars.yml`

Tous les playbooks chargent automatiquement `hardening-vars.yml` à la racine.
S'il n'existe pas, ils prennent `hardening-vars.yml.example`, dont les valeurs
fictives font échouer les gardes. Crée ton fichier local, ignoré par Git :

```bash
cp hardening-vars.yml.example hardening-vars.yml
```

Pour la première exécution, seules ces valeurs comptent :

```yaml
users_hardening_admin_bootstrapped: false   # le compte n'existe pas encore
users_hardening_admin_username: aegisadmin  # nom du compte, jamais root
users_hardening_admin_shell: /bin/bash
users_hardening_admin_groups: []            # groupes en plus, ils doivent exister
users_hardening_admin_public_keys:
  - "ssh-ed25519 AAAA... aegisadmin@aegisops"  # contenu de ~/.ssh/aegisops_admin.pub
users_hardening_sudo_mode: nopasswd         # sudo sans mot de passe, requis ensuite
users_hardening_admin_password_hash: ""     # vide : mot de passe Unix verrouillé

ssh_hardening_probe_private_key: /home/toi/.ssh/aegisops_admin  # chemin absolu
```

Pourquoi ces choix :

- **Pas de mot de passe** : sans hash, le mot de passe Unix du compte est
  verrouillé. L'accès se fait uniquement par clé SSH.
- **`nopasswd`** : à partir de la deuxième partie du durcissement, Ansible se
  connecte avec ce compte et doit lancer `sudo` sans saisie.
- **`ssh_hardening_probe_private_key`** : c'est la clé qu'Ansible utilisera
  pour se reconnecter en tant qu'administrateur. Écris un chemin absolu
  (`/home/...`), pas `~`.

Toutes les variables sont décrites dans [configuration.md](configuration.md).

## Étape 5 — Lancer l'audit

L'audit lit l'état du serveur et ne modifie rien :

```bash
ansible-playbook -i inventories/production/hosts.local.yml playbooks/audit.yml
```

Le rapport est écrit sur ton poste dans `reports/my-vps.json`. Sur un serveur
neuf, attends-toi à des `FAIL` (root et mots de passe autorisés) et des `WARN`
(Fail2ban absent, UFW inactif). C'est ton point de départ. Détails dans
[audit.md](audit.md).

**Si ça échoue** : `UNREACHABLE` signifie que la connexion SSH a échoué.
Vérifie l'adresse, le port, l'utilisateur et que `ssh root@203.0.113.10`
fonctionne à la main.

## Étape 6 — Créer l'administrateur (bootstrap)

```bash
ansible-playbook -i inventories/production/hosts.local.yml \
  playbooks/hardening.yml --tags users
```

Avec `--tags users`, seul le compte est créé, avec la connexion de
l'inventaire (`root`). Le rôle :

- crée `aegisadmin` sans supprimer de compte existant ;
- ajoute ta clé publique sans retirer les clés déjà présentes ;
- écrit `/etc/sudoers.d/90-aegisops-aegisadmin`, validé par `visudo` ;
- vérifie que `sudo -n true` fonctionne pour ce compte.

Détails dans [users-hardening.md](users-hardening.md).

**Si ça échoue** : le message de l'assertion indique la valeur à corriger.
Aucun changement n'a lieu avant ces contrôles. Voir
[recovery.md](recovery.md#un-garde-a-arrêté-le-playbook).

## Étape 7 — Tester l'administrateur, garder root ouvert

**Garde ta session root ouverte** dans un premier terminal. Dans un deuxième
terminal, teste une connexion toute neuve :

```bash
ssh -i ~/.ssh/aegisops_admin aegisadmin@203.0.113.10
sudo -n true && echo "sudo OK"
```

Si les deux fonctionnent, modifie `hardening-vars.yml` :

```yaml
users_hardening_admin_bootstrapped: true
```

À partir de maintenant, `hardening.yml` saute l'étape de création et se
connecte directement avec `aegisadmin`.

**Si ça échoue** : n'avance pas. Depuis la session root encore ouverte,
contrôle `/home/aegisadmin/.ssh/authorized_keys` et le fichier sudoers. Voir
[recovery.md](recovery.md#compte-administrateur).

## Étape 8 — Durcir SSH

Ajoute les confirmations SSH. Chaque `true` doit refléter un fait que tu as
vérifié, pas une supposition :

```yaml
ssh_hardening_approved_host: my-vps              # nom exact dans l'inventaire
ssh_hardening_recovery_confirmed: true           # console testée, snapshot si possible
ssh_hardening_independent_login_confirmed: true  # l'étape 7 a réussi
ssh_hardening_admin_user: aegisadmin
ssh_hardening_address_family: inet               # SSH en IPv4 seulement
```

Pourquoi `inet` : le rôle Fail2ban ne sait tester que l'IPv4 et refuse de
s'installer si SSH écoute aussi en IPv6. Garde `any` seulement si tu ne veux
pas de Fail2ban.

Puis :

```bash
ansible-playbook -i inventories/production/hosts.local.yml \
  playbooks/hardening.yml --tags ssh
```

Le rôle teste une connexion neuve avant et après le changement. Si le test
d'après échoue, il remet automatiquement l'ancienne configuration. Détails
dans [ssh-hardening.md](ssh-hardening.md).

Root ne peut plus se connecter en SSH. Mets donc ton inventaire à jour pour
`audit.yml`, qui utilise toujours l'utilisateur de l'inventaire :

```yaml
          ansible_user: aegisadmin
          ansible_ssh_private_key_file: ~/.ssh/aegisops_admin
```

`hardening.yml`, `verify.yml` et `monitoring.yml` choisissent eux-mêmes
`aegisadmin` et sa clé.

**Si ça échoue** : garde la session ouverte et suis
[recovery.md](recovery.md#ssh-inaccessible).

## Étape 9 — Préparer puis activer UFW

D'abord la **préparation** : UFW est installé et ses règles sont écrites, mais
il reste inactif. Déclare seulement les ports dont tu as besoin, en plus du
port SSH (ajouté automatiquement) :

```yaml
firewall_hardening_activate: false
firewall_hardening_allowed_inbound:
  - port: 443
    proto: tcp
```

```bash
ansible-playbook -i inventories/production/hosts.local.yml \
  playbooks/hardening.yml --tags firewall
```

L'**activation** est une décision séparée. Elle bloque toute connexion entrante
non déclarée, y compris les ports d'autres logiciels (par exemple l'API K3s
6443 ou le kubelet 10250). Quand tu es prêt :

```yaml
firewall_hardening_activate: true
firewall_hardening_approved_host: my-vps
firewall_hardening_recovery_confirmed: true
firewall_hardening_independent_login_confirmed: true
firewall_hardening_admin_user: aegisadmin
firewall_hardening_probe_private_key: /home/toi/.ssh/aegisops_admin
```

Relance la même commande. Si la connexion de test échoue après l'activation,
le rôle désactive UFW. Détails dans
[firewall-hardening.md](firewall-hardening.md).

**Si ça échoue** : voir [recovery.md](recovery.md#ufw-bloque-ssh).

## Étape 10 — Installer Fail2ban

```yaml
fail2ban_hardening_approved_host: my-vps
fail2ban_hardening_recovery_confirmed: true
fail2ban_hardening_admin_user: aegisadmin
fail2ban_hardening_probe_private_key: /home/toi/.ssh/aegisops_admin
fail2ban_hardening_admin_source_ip: ""   # vide : détectée automatiquement
```

```bash
ansible-playbook -i inventories/production/hosts.local.yml \
  playbooks/hardening.yml --tags fail2ban
```

Le rôle ouvre une connexion SSH indépendante, lit l'adresse IPv4 de ton poste
vue par le serveur et l'ajoute à la liste des adresses jamais bannies
(`ignoreip`). Détails dans [fail2ban.md](fail2ban.md).

**Si ça échoue** : voir
[recovery.md](recovery.md#adresse-bannie-par-fail2ban).

## Étape 11 — Activer les mises à jour de sécurité

Les valeurs par défaut suffisent : mises à jour de sécurité Ubuntu seulement,
**sans redémarrage automatique**.

```bash
ansible-playbook -i inventories/production/hosts.local.yml \
  playbooks/hardening.yml --tags updates
```

Détails dans [updates-hardening.md](updates-hardening.md).

**Si ça échoue** : voir
[recovery.md](recovery.md#mises-à-jour-automatiques).

## Étape 12 — Le durcissement complet

Une fois les domaines passés un par un, une exécution sans tag les parcourt
tous dans l'ordre (ssh, firewall, fail2ban, updates) :

```bash
ansible-playbook -i inventories/production/hosts.local.yml playbooks/hardening.yml
```

C'est la commande à relancer plus tard pour remettre le serveur dans l'état
déclaré. Tu peux aussi l'utiliser directement à la place des étapes 8 à 11 si
toutes les confirmations sont déjà renseignées.

## Étape 13 — Vérifier

`verify.yml` relit l'état réel du serveur sans le modifier. Choisis les
sections correspondant à ce que tu as réellement appliqué :

```yaml
verify_users: true
verify_ssh: true
verify_firewall: true      # seulement si UFW est actif
verify_fail2ban: true
verify_updates: true
verify_monitoring: false   # true après l'étape 14
verify_ssh_admin_user: aegisadmin
verify_ssh_probe_private_key: /home/toi/.ssh/aegisops_admin
verify_ssh_source_ip: "198.51.100.7"
verify_ssh_source_host: "198.51.100.7"
fail2ban_hardening_admin_source_ip: "198.51.100.7"
```

Pour connaître l'adresse source vue par le serveur :

```bash
ssh -i ~/.ssh/aegisops_admin aegisadmin@203.0.113.10 'echo "$SSH_CONNECTION"'
```

La première valeur affichée est ton adresse IPv4. Lance ensuite :

```bash
ansible-playbook -i inventories/production/hosts.local.yml playbooks/verify.yml
```

Détails dans [verify.md](verify.md).

## Étape 14 — Superviser

Ajoute dans `hardening-vars.yml` :

```yaml
monitoring_approved_host: my-vps
monitoring_admin_user: aegisadmin
```

Le mot de passe Grafana va dans un fichier **séparé et chiffré** par Ansible
Vault, `monitoring-vault.yml` (ignoré par Git) :

```bash
openssl rand -base64 24 | tr -d '\n' \
  | ansible-vault encrypt_string --stdin-name monitoring_grafana_admin_password \
  > monitoring-vault.yml
```

Vault demande « New Vault password » : c'est le mot de passe que tu choisis
pour **chiffrer ce fichier**. Vault ne le stocke nulle part : retiens-le, il
servira à chaque déploiement.

Pour ne pas le retaper, tu peux l'écrire dans un fichier hors du dépôt,
lisible par toi seul, et l'indiquer à Ansible :

```bash
mkdir -p ~/.config/aegisops
printf '%s\n' 'ton-mot-de-passe-vault' > ~/.config/aegisops/vault-pass
chmod 600 ~/.config/aegisops/vault-pass
export ANSIBLE_VAULT_PASSWORD_FILE=~/.config/aegisops/vault-pass
```

Avec cette variable, retire `--ask-vault-pass` des commandes. Ce fichier
contient le mot de passe en clair : protège ton poste en conséquence.

Déploie, puis ouvre le tunnel :

```bash
ansible-playbook -i inventories/production/hosts.local.yml \
  playbooks/monitoring.yml -e @monitoring-vault.yml --ask-vault-pass
ssh -N -L 3000:127.0.0.1:3000 -i ~/.ssh/aegisops_admin aegisadmin@203.0.113.10
```

Ouvre <http://localhost:3000> et connecte-toi avec `admin` et le mot de passe
Grafana. Pour le lire :

```bash
ansible localhost -m debug -a var=monitoring_grafana_admin_password \
  -e @monitoring-vault.yml --ask-vault-pass
```

Passe enfin `verify_monitoring: true` et relance `verify.yml`. Tout est
expliqué dans [monitoring.md](monitoring.md).

**Si ça échoue** : voir [recovery.md](recovery.md#supervision).

## Étape 15 — Accéder au tableau de bord par VPN (facultatif)

Le tunnel SSH suffit pour consulter le tableau de bord depuis ton PC. Pour y
accéder sans commande, et aussi depuis ton téléphone ou un autre ordinateur,
installe le VPN WireGuard :

1. `sudo apt install wireguard-tools qrencode` sur ton PC.
2. `scripts/aegisops-wg-peer new <appareil>` pour chaque appareil, puis
   recopie les blocs affichés dans `wireguard_peers`.
3. Renseigne `wireguard_approved_host`, `wireguard_admin_user` et
   `wireguard_ufw_rule_confirmed: true`, puis lance `playbooks/vpn.yml`.
4. Installe le tunnel sur chaque appareil, passe
   `monitoring_grafana_access: vpn` et relance `monitoring.yml`.
5. Ouvre <http://10.66.66.1:3000>.

Le guide complet, appareil par appareil, est dans [vpn.md](vpn.md).

**Si ça échoue** : voir [recovery.md](recovery.md#vpn-wireguard).

## Lire le résultat d'un playbook

Chaque exécution se termine par un `PLAY RECAP` :

```text
my-vps : ok=42 changed=3 unreachable=0 failed=0 skipped=12 rescued=0 ignored=0
```

- `ok` : tâches réussies.
- `changed` : tâches qui ont modifié quelque chose. Pour `audit.yml` et
  `verify.yml`, ce nombre reste à 0.
- `unreachable` : connexion impossible. Doit valoir 0.
- `failed` : tâches en échec, y compris les gardes (assertions). Doit valoir 0.
- `skipped` : tâches non applicables (section `verify_*` désactivée, Ubuntu
  22.04 contre 24.04, etc.). C'est normal.
- `rescued` : un bloc a échoué puis a été rattrapé. Pour SSH, UFW ou Fail2ban,
  cela signifie qu'un retour arrière a eu lieu ; le playbook s'arrête alors
  sur une erreur explicite.

**`failed=0` et `unreachable=0` signifient que toutes les tâches et toutes les
assertions sont passées.** Pour `verify.yml`, cela ne concerne que les
sections activées.
