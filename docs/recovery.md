# Récupération et retour arrière

Cette page dit quoi faire quand un changement tourne mal, domaine par
domaine. **Lis-la avant ton premier durcissement**, pas pendant la panne.

## Avant tout changement

- Ouvre une fois la **console de l'hébergeur** (VNC ou console série) et
  vérifie que tu peux t'y connecter. Comme root ne peut plus se connecter en
  SSH après le durcissement, la console reste ta porte de secours.
- Fais un **snapshot** si ton hébergeur le permet.
- **Garde une session SSH ouverte** pendant chaque changement d'accès, et
  teste toujours une connexion **neuve** dans un autre terminal avant de la
  fermer.

## Un garde a arrêté le playbook

Si une tâche `assert` échoue au début d'un rôle (message `Assertion failed`
suivi d'une explication), **rien n'a été modifié** par ce rôle. Lis le
message, corrige la variable ou la situation indiquée, puis relance. Les
messages les plus fréquents sont expliqués dans la section « dépannage » de
chaque page de rôle.

## Compte administrateur

Le rôle `users_hardening` ajoute un accès sans en retirer. En cas de problème,
depuis la session root encore ouverte ou la console :

```bash
sudo ls -la /home/aegisadmin/.ssh/
sudo cat /home/aegisadmin/.ssh/authorized_keys
sudo visudo -cf /etc/sudoers.d/90-aegisops-aegisadmin
sudo -l -U aegisadmin
```

- `.ssh` doit être en `0700` et `authorized_keys` en `0600`, propriété de
  `aegisadmin`.
- Pour retirer les droits `sudo` donnés par AegisOps :
  `sudo rm /etc/sudoers.d/90-aegisops-aegisadmin`.
- Le rôle ne supprime jamais le compte. Pour le supprimer volontairement,
  fais-le à la main (`sudo deluser aegisadmin`) **seulement** si un autre accès
  administrateur fonctionne.

## SSH inaccessible

Le rôle SSH garde une sauvegarde de `/etc/ssh/sshd_config` et revient
automatiquement en arrière si le test de connexion échoue alors que le serveur
répond encore. Si la connexion a été coupée avant, passe par la console ou
une session encore ouverte.

1. Trouve la sauvegarde (le chemin est aussi affiché par Ansible) :

   ```bash
   sudo ls -lt /etc/ssh/sshd_config*
   ```

2. Restaure-la et valide la configuration :

   ```bash
   sudo cp -a '/etc/ssh/sshd_config.BACKUP' /etc/ssh/sshd_config
   sudo /usr/sbin/sshd -t
   ```

   Remplace `sshd_config.BACKUP` par le vrai nom (de la forme
   `sshd_config.<nombre>.<date>@<heure>~`). Sans sauvegarde, supprime
   simplement le bloc entre `# BEGIN AEGISOPS SSH HARDENING` et
   `# END AEGISOPS SSH HARDENING`.

3. **Ne recharge pas SSH si `sshd -t` affiche une erreur.** S'il ne dit rien :

   ```bash
   sudo systemctl reload ssh
   sudo systemctl status ssh --no-pager
   ```

4. Teste une connexion neuve avant de fermer la session de récupération.

Si le serveur reste injoignable, restaure le snapshot ou contacte
l'hébergeur. Une règle locale correcte ne garantit pas l'accès si un pare-feu
de l'hébergeur (ou de Proxmox pour un conteneur) bloque le trafic.

### Ubuntu 24.04 avec activation par socket

Si `systemctl is-active ssh.socket` répond `active`, Ubuntu 24.04 tire les
ports et adresses d'écoute de `sshd_config` via un générateur systemd. Après
avoir restauré le fichier et obtenu un `sshd -t` valide :

```bash
sudo systemctl daemon-reload
sudo systemctl restart ssh.socket
sudo systemctl reload ssh.service
sudo systemctl status ssh.socket ssh.service --no-pager
```

Teste ensuite une connexion neuve. Ne ferme pas la session de récupération
avant ce test.

## UFW bloque SSH

Si l'activation coupe ta connexion et que le test d'Ansible échoue, le rôle
désactive UFW lui-même lorsque le serveur répond encore. Sinon, depuis la
console :

```bash
sudo ufw disable
sudo ufw status verbose
```

Les règles préparées sont conservées : `ufw disable` arrête seulement le
filtrage. Vérifie ensuite que `ansible_port` dans ton inventaire correspond au
vrai port SSH (`sudo ss -tlnp | grep ssh`), corrige, et réessaie.

## Adresse bannie par Fail2ban

Ton adresse d'administration est dans `ignoreip`, mais si ton adresse publique
a changé, tu peux être banni après plusieurs échecs. Depuis la console ou une
autre connexion :

```bash
sudo fail2ban-client status sshd
sudo fail2ban-client set sshd unbanip 198.51.100.7
```

Relance ensuite le rôle Fail2ban depuis ta nouvelle adresse pour la mettre à
jour (vide `fail2ban_hardening_admin_source_ip` pour une détection
automatique).

Si le test de bannissement facultatif n'a pas pu nettoyer l'adresse de test :

```bash
sudo fail2ban-client set sshd unbanip 192.0.2.123
```

Pour désactiver la jail AegisOps :

```bash
sudo rm /etc/fail2ban/jail.d/90-aegisops-sshd.local
sudo fail2ban-client reload
```

## Mises à jour automatiques

Pour retirer la politique AegisOps et revenir aux réglages d'Ubuntu :

```bash
sudo rm /etc/apt/apt.conf.d/99aegisops-unattended-upgrades
apt-config dump | grep -E 'Periodic|Allowed-Origins|Automatic-Reboot'
```

Pour suspendre complètement les mises à jour automatiques :

```bash
sudo systemctl disable --now apt-daily-upgrade.timer
```

Si un redémarrage automatique s'est mal passé, utilise la console de
l'hébergeur pour voir l'écran de démarrage.

## Supervision

La supervision n'ouvre aucun port et ne touche pas à SSH. Si elle consomme
trop de ressources ou pose problème :

```bash
sudo systemctl stop grafana-server prometheus prometheus-node-exporter aegisops-security-exporter.timer
sudo systemctl status grafana-server prometheus --no-pager
```

Chaque service est plafonné en mémoire (`MemoryMax`). Les détails, dont le
mot de passe Grafana et les plafonds, sont dans [monitoring.md](monitoring.md).

## VPN WireGuard

Le VPN ne remplace jamais SSH : même s'il tombe, l'accès d'administration par
SSH reste intact. Pour le couper immédiatement :

```bash
sudo systemctl stop wg-quick@wg0      # Grafana (mode VPN) s'arrête avec lui
sudo ufw delete allow 51820/udp       # ferme le port, si tu veux le retirer
```

Un appareil perdu se révoque en le retirant de `wireguard_peers` puis en
relançant `vpn.yml`. Tout est détaillé dans [vpn.md](vpn.md).
