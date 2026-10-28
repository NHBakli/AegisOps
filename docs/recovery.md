# Récupérer l'accès SSH

Avant tout changement SSH, vérifie l'accès à la console du fournisseur ou
Proxmox et garde une session SSH existante ouverte. Un snapshot récent est
recommandé.

Le rôle conserve une sauvegarde horodatée de `/etc/ssh/sshd_config`. En cas
d'échec, retrouve le chemin exact dans la sortie Ansible ou sur le serveur :

```bash
sudo ls -lt /etc/ssh/sshd_config*
```

Depuis la console ou une session encore ouverte, restaure cette sauvegarde :

```bash
sudo cp -a /etc/ssh/sshd_config.BACKUP /etc/ssh/sshd_config
sudo /usr/sbin/sshd -t
```

Remplace `sshd_config.BACKUP` par le vrai nom du fichier. **Ne recharge pas SSH
si `sshd -t` échoue.** S'il réussit :

```bash
sudo systemctl reload ssh
sudo systemctl status ssh --no-pager
```

Teste ensuite une nouvelle connexion avant de fermer la session existante.
Si la sauvegarde manque ou si le serveur reste inaccessible, restaure le
snapshot ou demande l'accès console au fournisseur. Sous LXC, vérifie aussi
le filtrage réseau côté Proxmox. Une règle locale correcte ne garantit pas
l'accès depuis Internet.

## Ubuntu 24.04 avec activation par socket

Si `systemctl is-active ssh.socket` répond `active`, Ubuntu 24.04 peut tirer
les paramètres d'écoute de `sshd_config` via un générateur systemd. Après
avoir restauré le fichier et obtenu un `sshd -t` valide, exécute depuis la
console ou une session encore ouverte :

```bash
sudo systemctl daemon-reload
sudo systemctl restart ssh.socket
sudo systemctl reload ssh.service
sudo systemctl status ssh.socket ssh.service --no-pager
```

Teste ensuite une nouvelle connexion indépendante. Ne ferme pas la session
de récupération avant ce test.
