# Pare-feu UFW (`firewall_hardening`)

## À quoi ça sert

Ce rôle prépare UFW pour n'accepter en entrée que SSH et les ports que tu
déclares. Par défaut, il **prépare sans activer** : les règles sont écrites,
mais UFW reste inactif. L'activation est une décision séparée, protégée par
des confirmations et un test de connexion.

## Ce que le rôle modifie

En préparation (`firewall_hardening_activate: false`) :

- installe le paquet `ufw` s'il manque, après avoir simulé l'installation et
  refusé toute suppression de paquet prévue par APT ;
- autorise d'abord le **port SSH** (`ansible_port`, TCP), puis chaque port de
  `firewall_hardening_allowed_inbound` ;
- règle les politiques par défaut : entrée `deny` (ou `reject`), sortie
  `allow` ;
- enregistre les règles et la politique demandées dans
  `/var/lib/aegisops/ufw-added-rules.txt` et `/var/lib/aegisops/ufw-intent.json`
  (dossier `0700`, fichiers `0600`). Ces « manifestes » permettent de
  reconnaître, à l'exécution suivante, des règles posées par AegisOps.

Avec `firewall_hardening_activate: true` : en plus, **active UFW**, puis
contrôle les règles actives et teste une connexion SSH neuve.

Si UFW est **déjà actif** et préparé par AegisOps, le rôle ne change plus ses
règles : il vérifie seulement qu'elles correspondent aux manifestes et que SSH
passe toujours.

Le rôle ne gère pas `before.rules` / `after.rules`, ni le pare-feu de
l'hébergeur ou de Proxmox.

## Prérequis et confirmations

Toujours :

- Ubuntu 22.04 ou 24.04, pas de mode `--check` ;
- `ansible_port` défini dans l'inventaire ;
- des règles valides : port entier de 1 à 65535, `proto` `tcp` ou `udp`, pas
  de doublon, pas de règle pour le port SSH (il est géré à part) ;
- UFW inactif, ou actif **avec** les manifestes AegisOps ;
- aucune règle inconnue dans un UFW inactif, et une politique identique à la
  préparation précédente.

Pour l'activation, en plus :

- `firewall_hardening_approved_host` vaut le nom de l'hôte ;
- `firewall_hardening_recovery_confirmed: true` (console vérifiée) ;
- `firewall_hardening_independent_login_confirmed: true` (connexion admin
  testée) ;
- Ansible est connecté avec `firewall_hardening_admin_user` et la clé
  `firewall_hardening_probe_private_key` existe ;
- le processus a la capacité `CAP_NET_ADMIN` ;
- une connexion SSH neuve réussit avant l'activation ;
- dans un conteneur (LXC, OpenVZ, Docker, Podman) :
  `firewall_hardening_lxc_compatibility_confirmed: true`. Sur une VM KVM, ce
  n'est pas demandé.

**Attention aux autres logiciels.** Une fois UFW actif, tout port entrant non
déclaré est bloqué. Par exemple, les ports de K3s (API 6443, kubelet 10250)
ne sont plus joignables depuis Internet. C'est voulu si ces services n'ont pas
à être publics ; sinon, déclare-les avant d'activer.

## Variables

```yaml
firewall_hardening_activate: false     # true = décision d'activer
firewall_hardening_allowed_inbound:
  - port: 443
    proto: tcp
firewall_hardening_default_incoming: deny
firewall_hardening_default_outgoing: allow
# Requis pour l'activation :
firewall_hardening_approved_host: my-vps
firewall_hardening_recovery_confirmed: true
firewall_hardening_independent_login_confirmed: true
firewall_hardening_lxc_compatibility_confirmed: false
firewall_hardening_admin_user: aegisadmin
firewall_hardening_probe_private_key: /home/toi/.ssh/aegisops_admin
```

Référence complète :
[configuration.md](configuration.md#pare-feu-firewall_hardening_).

## Lancer

```bash
ansible-playbook -i inventories/production/hosts.local.yml \
  playbooks/hardening.yml --tags firewall
```

Ajoute `--ask-vault-pass` si `hardening-vars.yml` est chiffré.

Conseil : lance d'abord avec `firewall_hardening_activate: false` et regarde
les règles préparées (`sudo ufw show added`). Si possible, teste l'activation
sur une VM de test avant le serveur réel. Passe ensuite à `true`.

Une fois UFW actif, garde `firewall_hardening_activate: true` : avec `false`,
le rôle refuse de tourner face à un UFW actif.

## Vérifier

```bash
ssh -i ~/.ssh/aegisops_admin aegisadmin@203.0.113.10 'sudo ufw status verbose'
```

Tu dois voir `Status: active`, `Default: deny (incoming), allow (outgoing)`,
ton port SSH et tes ports déclarés en `ALLOW IN`.

Puis active `verify_firewall: true` et lance `verify.yml`. Il exige UFW actif,
les bonnes politiques et **exactement** les ports attendus : un port ouvert en
plus, ou une règle `LIMIT`, le fait échouer (voir [verify.md](verify.md)).

Pour tester depuis l'extérieur, essaie depuis ton poste un port non déclaré :
la connexion doit expirer.

## Revenir en arrière / dépannage

- **Le rôle s'arrête au début** : lis le message. Aucune règle n'a été
  modifiée.
- **`Inactive UFW contains unknown or changed rules`** : UFW contient des
  règles qu'AegisOps n'a pas posées, ou tu as changé la liste de ports depuis
  la dernière préparation. Le rôle ne supprime pas de règle tout seul.
  Compare `sudo ufw show added` avec `/var/lib/aegisops/ufw-added-rules.txt`,
  puis corrige à la main.
- **`Active UFW has no AegisOps preparation manifests`** : UFW a été activé
  hors d'AegisOps. Revois ses règles à la main.
- **Changer les ports d'un UFW déjà actif** : ce n'est pas encore automatisé.
  Le rôle refuse, car la nouvelle liste diffère des manifestes enregistrés.
  Un changement manuel (`sudo ufw allow <port>/<proto>`) fera aussi échouer
  les exécutions suivantes du rôle tant que les manifestes de
  `/var/lib/aegisops/` ne sont pas revus. Planifie ce changement comme une
  opération manuelle, avec la console à portée de main.
- **L'activation coupe SSH** : si le test échoue et que le serveur répond
  encore, le rôle désactive UFW en gardant les règles. Sinon, depuis la
  console : `sudo ufw disable`. Voir
  [recovery.md](recovery.md#ufw-bloque-ssh).
