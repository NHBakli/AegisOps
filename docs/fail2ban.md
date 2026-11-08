# Fail2ban (`fail2ban`)

## À quoi ça sert

Fail2ban lit le journal de SSH et bannit pendant un temps les adresses qui
échouent trop souvent à se connecter. Ce rôle installe Fail2ban avec une jail
SSH et ajoute **ton adresse d'administration** à la liste des adresses jamais
bannies, pour ne pas te bloquer toi-même.

## Ce que le rôle modifie

- Installe `fail2ban`, `python3-systemd` et `iptables`, sans démarrer le
  service pendant l'installation.
- Écrit `/etc/fail2ban/jail.d/90-aegisops-sshd.local` (sauvegarde de
  l'ancienne version s'il y en avait une) :

  ```ini
  [sshd]
  enabled = true
  filter = sshd
  backend = systemd
  journalmatch = _SYSTEMD_UNIT=ssh.service + _COMM=sshd
  port = 22
  protocol = tcp
  maxretry = 5
  findtime = 600
  bantime = 600
  ignoreip = 127.0.0.1/8 ::1 198.51.100.7
  banaction = iptables-multiport
  ```

- Valide la configuration (`fail2ban-client -t`), démarre ou recharge
  Fail2ban, puis l'active au démarrage du serveur une fois tout vérifié.

Les autres fichiers de `/etc/fail2ban/` ne sont pas modifiés.

## Prérequis et confirmations

Avant de modifier quoi que ce soit, le rôle vérifie que :

- le serveur est sous Ubuntu 22.04 ou 24.04, sans mode `--check` ;
- `fail2ban_hardening_approved_host` vaut le nom de l'hôte ;
- `fail2ban_hardening_recovery_confirmed: true` (console vérifiée) ;
- Ansible est connecté avec `fail2ban_hardening_admin_user`, et sa clé
  `fail2ban_hardening_probe_private_key` existe sur ton poste ;
- les valeurs `maxretry`, `findtime`, `bantime` sont des entiers ≥ 1 et
  `banaction` vaut `iptables-multiport` ;
- **SSH n'écoute pas en IPv6** sur son port : le rôle ne sait protéger et
  tester que l'IPv4. Mets `ssh_hardening_address_family: inet` d'abord ;
- le processus a la capacité `CAP_NET_ADMIN` (nécessaire pour iptables) ;
- aucun autre fichier local (`jail.local`, `jail.d/*.local`) ne définit déjà
  une jail `[sshd]` ;
- `ssh.service` ou `ssh.socket` est actif et le journal SSH contient au moins
  un événement ;
- dans un conteneur : `fail2ban_hardening_lxc_compatibility_confirmed: true`.
  Sur une VM KVM, ce n'est pas demandé.

**Détection de ton adresse.** Le rôle ouvre une connexion SSH indépendante et
lit `$SSH_CONNECTION` sur le serveur : la première valeur est l'IPv4 de ton
poste vue par le serveur. Si tu as renseigné
`fail2ban_hardening_admin_source_ip`, elle doit correspondre, sinon le rôle
s'arrête.

Si ton adresse publique change souvent (connexion domestique, 4G), la jail
protège seulement l'adresse vue lors de l'exécution. Relance le rôle après un
changement d'adresse.

## Variables

```yaml
fail2ban_hardening_approved_host: my-vps
fail2ban_hardening_recovery_confirmed: true
fail2ban_hardening_lxc_compatibility_confirmed: false
fail2ban_hardening_admin_user: aegisadmin
fail2ban_hardening_probe_private_key: /home/toi/.ssh/aegisops_admin
fail2ban_hardening_admin_source_ip: ""   # facultatif : adresse attendue
fail2ban_hardening_maxretry: 5
fail2ban_hardening_findtime: 600
fail2ban_hardening_bantime: 600
fail2ban_hardening_ban_probe_enabled: false
```

Référence complète :
[configuration.md](configuration.md#fail2ban-fail2ban_hardening_).

## Lancer

```bash
ansible-playbook -i inventories/production/hosts.local.yml \
  playbooks/hardening.yml --tags fail2ban
```

Ajoute `--ask-vault-pass` si `hardening-vars.yml` est chiffré.

Après la configuration, le rôle relit les valeurs effectives de la jail
(`fail2ban-client get sshd ...`), vérifie que ton adresse est bien ignorée,
puis refait une connexion SSH de test.

**Test de bannissement (facultatif).** Avec
`fail2ban_hardening_ban_probe_enabled: true`, le rôle bannit l'adresse de test
réservée `192.0.2.123`, vérifie qu'une vraie règle iptables apparaît, puis la
débannit et vérifie qu'elle a disparu. Cela prouve le mécanisme local, pas le
filtrage de l'hébergeur ni l'accessibilité depuis Internet.

## Vérifier

```bash
ssh -i ~/.ssh/aegisops_admin aegisadmin@203.0.113.10 \
  'sudo fail2ban-client status sshd; sudo fail2ban-client get sshd ignoreip'
```

Puis renseigne `fail2ban_hardening_admin_source_ip`, active
`verify_fail2ban: true` et lance `verify.yml` (voir [verify.md](verify.md)).
La vérification contrôle la jail et ses valeurs, mais ne teste pas de
bannissement.

## Revenir en arrière / dépannage

- **Le rôle s'arrête au début** : lis le message de l'assertion. Rien n'a été
  installé.
- **`SSH listens on IPv6`** : passe d'abord le rôle SSH avec
  `ssh_hardening_address_family: inet`.
- **`Another local Fail2ban file defines [sshd]`** : une autre configuration
  gère déjà la jail SSH. Revois ce fichier avant de continuer.
- **`observed administrator SSH source differs`** : ton adresse a changé.
  Vide `fail2ban_hardening_admin_source_ip` ou mets la nouvelle valeur.
- **Échec après l'installation** : le rôle restaure l'ancienne jail (ou
  supprime la nouvelle) et remet le service dans son état initial.
- **Tu es banni** : voir
  [recovery.md](recovery.md#adresse-bannie-par-fail2ban).
- **Désactiver la jail AegisOps** :
  `sudo rm /etc/fail2ban/jail.d/90-aegisops-sshd.local && sudo fail2ban-client reload`.
