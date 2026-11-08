# VPN WireGuard (`wireguard`)

## À quoi ça sert

`playbooks/vpn.yml` installe un serveur **WireGuard** sur le VPS. Une fois
connecté au VPN, ton PC, ton téléphone ou un autre ordinateur ouvre le tableau
de bord à l'adresse **<http://10.66.66.1:3000>**, sans commande SSH à lancer.

Le VPN ne donne accès **qu'au VPS lui-même** : ta navigation Internet ne passe
pas par le serveur, et aucun routage ni NAT n'est activé.

```text
 PC Linux   10.66.66.2 ─┐
 Téléphone  10.66.66.3 ─┼── WireGuard, UDP 51820, chiffré ──► VPS wg0 10.66.66.1
 Laptop     10.66.66.4 ─┘                                       └─ Grafana :3000
                                                                   (seulement via wg0)
```

## Pourquoi WireGuard plutôt qu'OpenVPN

| | WireGuard | OpenVPN |
|---|---|---|
| Où il tourne | intégré au noyau Linux | démon à installer et faire tourner |
| Clés | une paire de clés par appareil, comme SSH | autorité de certification et certificats à renouveler |
| Configuration | une dizaine de lignes | nombreuses options, plus de risques d'erreur |
| Face aux scanners | invisible : aucune réponse sans clé valide | répond sur son port |
| Téléphone | rapide, économe en batterie | plus lourd |
| Avantage propre | — | peut passer par TCP 443 sur les réseaux qui bloquent l'UDP (ici, 443 est déjà utilisé par K3s) |

## Ce que le rôle modifie sur le serveur

| Élément | Détail |
|---|---|
| Paquet | `wireguard-tools` (le module noyau est déjà présent sur la VM KVM) |
| Clé du serveur | `/etc/wireguard/server.key` (0600), générée **sur le serveur**, jamais lue par Ansible ; clé publique dans `server.pub` |
| Interface | `/etc/wireguard/wg0.conf` (0600) : adresse `10.66.66.1/24`, port 51820, MTU 1280 et un bloc `[Peer]` par appareil. La clé privée y est chargée au démarrage (`PostUp`), elle n'est jamais écrite dans ce fichier |
| Cloisonnement | au démarrage de `wg0` : routage désactivé sur l'interface, et règle `iptables -t raw` qui rejette tout paquet venant du VPN qui ne vise pas `10.66.66.1` |
| Service | `wg-quick@wg0`, activé au démarrage |
| Pare-feu | une règle UFW : `51820/udp ALLOW Anywhere`, commentée « AegisOps WireGuard » |

Si tu passes la supervision en mode VPN (voir plus bas), le rôle `monitoring`
ajoute une seconde règle : le port 3000 autorisé sur l'interface `wg0`,
commentée « AegisOps Grafana via VPN ».

## Ce qu'un appareil connecté peut atteindre

Seulement `10.66.66.1`, c'est-à-dire le VPS lui-même, et sur ce VPS seulement
ce que le pare-feu autorise (Grafana). Trois protections s'additionnent :

1. **Cloisonnement du tunnel.** Le VPS route déjà des paquets pour K3s
   (`ip_forward=1`, `route_localnet=1`). Sans protection, un appareil du VPN
   pourrait atteindre les pods (`10.42.0.0/16`), les services (`10.43.0.0/16`)
   ou `127.0.0.1`. La règle `raw` rejette ces paquets avant tout autre
   traitement, et le routage est coupé sur `wg0`.
2. **UFW.** La politique par défaut refuse tout ce qui n'est pas autorisé.
3. **Filtre propre à Grafana.** L'unité systemd de Grafana n'accepte que la
   boucle locale et le réseau VPN (`IPAddressDeny=any` +
   `IPAddressAllow=localhost 10.66.66.0/24`). C'est nécessaire, parce qu'une
   règle UFW d'un autre projet autorise tout le réseau des pods K3s : un pod
   compromis ne peut donc pas joindre Grafana.

À l'inverse, le VPN n'est pas une porte d'entrée vers ta machine : le serveur
ne peut joindre que l'adresse VPN de chaque appareil, et rien n'est routé entre
appareils.

Rien d'autre ne change. SSH, Fail2ban, K3s et les autres règles UFW restent
tels quels. Le réseau `10.66.66.0/24` a été choisi pour ne pas chevaucher K3s.
Le préflight refuse tout réseau qui chevauche une route existante ou une plage
réservée (`wireguard_reserved_networks`, par défaut `10.42.0.0/16` et
`10.43.0.0/16`, car les services K3s n'ont pas de route).

## Prérequis et confirmations

- Administrateur `aegisadmin` en place et UFW installé (étapes de durcissement).
- Sur ton PC : `sudo apt install wireguard-tools qrencode`.
- Dans `hardening-vars.yml` :

  ```yaml
  wireguard_approved_host: my-vps
  wireguard_admin_user: aegisadmin
  wireguard_ufw_rule_confirmed: true   # tu acceptes d'ouvrir 51820/udp
  wireguard_server_address: 10.66.66.1
  wireguard_peers: []                  # rempli à l'étape suivante
  ```

Avant toute modification, le rôle vérifie :

- la plateforme et l'approbation de l'hôte ;
- la confirmation UFW ;
- la présence du module noyau WireGuard ;
- la validité de chaque appareil (nom, adresse, clé) et leur unicité ;
- l'absence de chevauchement avec les routes du serveur.

## Lancer

### 1. Créer une clé par appareil (sur ton PC)

```bash
scripts/aegisops-wg-peer new pc-linux
scripts/aegisops-wg-peer new phone
scripts/aegisops-wg-peer new laptop
```

Chaque commande crée une clé privée dans
`~/.config/aegisops/wireguard/peers/<nom>.key` (0600), avec sa clé publique
dans `<nom>.pub`. Elle affiche aussi le bloc à coller dans `hardening-vars.yml`.
Le playbook vérifie que la clé locale correspond bien au bloc déclaré. Choisis une adresse différente pour
chaque appareil :

```yaml
wireguard_peers:
  - name: pc-linux
    address: 10.66.66.2
    public_key: "…clé publique affichée…"
  - name: phone
    address: 10.66.66.3
    public_key: "…"
  - name: laptop
    address: 10.66.66.4
    public_key: "…"
```

Seules les **clés publiques** vont dans ce fichier et sur le serveur.

### 2. Déployer le serveur

```bash
ansible-playbook -i inventories/production/hosts.local.yml playbooks/vpn.yml
```

À la fin, le rôle écrit sur ton PC un fichier de configuration par appareil :
`~/.config/aegisops/wireguard/<nom>.conf` (0600).

### 3. Installer le VPN sur chaque appareil

**PC Linux**

```bash
sudo install -m 600 ~/.config/aegisops/wireguard/pc-linux.conf /etc/wireguard/aegisops.conf
sudo systemctl enable --now wg-quick@aegisops   # connecté maintenant et à chaque démarrage
```

Pour te déconnecter : `sudo systemctl stop wg-quick@aegisops`.

**Téléphone (Android ou iPhone)**

1. Installe l'application officielle **WireGuard**.
2. Sur ton PC, affiche le QR code :

   ```bash
   scripts/aegisops-wg-peer qr phone
   ```

3. Dans l'application : **+** → **Scanner un code QR** → nomme le tunnel
   `aegisops` → active-le.
4. Efface l'écran du PC (`clear`). Le QR code contient la clé privée du
   téléphone.

**Autre ordinateur (Windows, macOS, Linux)**

1. Installe le client officiel WireGuard (wireguard.com/install).
2. Copie `~/.config/aegisops/wireguard/laptop.conf` sur cet ordinateur par un
   moyen sûr : clé USB ou `scp`. Jamais par e-mail ni messagerie.
3. Dans le client : **Importer un tunnel depuis un fichier**, puis
   **Activer**.

Une fois l'appareil configuré, tu peux supprimer de ton PC les fichiers `.key`
et `.conf` du téléphone et du laptop. Le playbook signalera alors seulement
qu'il ne peut plus régénérer leur configuration (`missing_local_key`).

### 4. Passer Grafana sur le VPN

Dans `hardening-vars.yml` :

```yaml
monitoring_grafana_access: vpn
```

Puis relance la supervision :

```bash
ansible-playbook -i inventories/production/hosts.local.yml \
  playbooks/monitoring.yml -e @monitoring-vault.yml --ask-vault-pass
```

Grafana écoute alors sur `10.66.66.1:3000` (et plus sur `127.0.0.1`).
Prometheus et node_exporter restent sur la boucle locale. Ouvre
**<http://10.66.66.1:3000>** depuis un appareil connecté au VPN.

## Vérifier

- Sur ton PC : `sudo wg show`. La ligne `latest handshake` doit dater de
  quelques secondes ou minutes.
- `ping 10.66.66.1` doit répondre.
- Le playbook vérifie lui-même :
  - la clé publique, le port et l'adresse de `wg0` ;
  - la liste exacte des appareils et leurs adresses ;
  - le démarrage automatique ;
  - le cloisonnement (règle `raw`, routage coupé) ;
  - la règle UFW.
- Contrôle indépendant : mets `verify_wireguard: true` dans
  `hardening-vars.yml`, puis lance `playbooks/verify.yml`.

## Ajouter ou retirer un appareil

- **Ajouter :** `scripts/aegisops-wg-peer new <nom>`, ajoute le bloc dans
  `wireguard_peers`, puis relance `vpn.yml`.
- **Retirer (appareil perdu ou volé) :** supprime son bloc de
  `wireguard_peers` et relance `vpn.yml`. Sa clé est refusée immédiatement.

À chaque changement, le serveur redémarre `wg0` : les appareils connectés
sont coupés une seconde, puis se reconnectent seuls. En mode VPN, Grafana
redémarre avec lui. Si `wg0` met du temps à démarrer au boot, Grafana réessaie
toutes les 5 secondes jusqu'à ce que l'adresse existe.

## Dépannage

| Symptôme | Cause et solution |
|---|---|
| `latest handshake` n'apparaît jamais | Le port UDP 51820 est bloqué : vérifie `sudo ufw status \| grep 51820` sur le VPS et le pare-feu du panneau de l'hébergeur. Certains réseaux publics (hôtels, entreprises) bloquent l'UDP : essaie en 4G. |
| Handshake OK mais page inaccessible | Vérifie `monitoring_grafana_access: vpn` et relance `monitoring.yml`. Sur le VPS, `sudo ufw status` doit afficher la règle « AegisOps Grafana via VPN ». |
| Le navigateur redirige ailleurs | Utilise exactement `http://10.66.66.1:3000` : Grafana refuse les autres noms. |
| `wg0 does not carry 10.66.66.1` dans `monitoring.yml` | Lance d'abord `vpn.yml`. |
| `scripts/aegisops-wg-peer new` n'affiche rien et laisse une clé vide | Ancienne version du script : sur Ubuntu récent, le profil AppArmor de `wg` l'empêche d'écrire hors de `/etc/wireguard`. Le script passe maintenant par des tubes et régénère automatiquement une clé vide : relance simplement la commande. |
| `the local key does not match public_key` | La clé de l'appareil a été recréée : recopie dans `wireguard_peers` la clé publique affichée par `scripts/aegisops-wg-peer new <nom>`. |
| Pages qui se figent sur réseau mobile | Le MTU est déjà réduit à 1280. Si ça persiste, essaie un autre réseau pour confirmer, puis signale-le. |
| Conflit de port avec K3s | Si K3s passe un jour au backend flannel `wireguard-native`, il utilisera aussi 51820/udp : choisis un autre `wireguard_port` (par exemple 51821). |
| `overlaps the existing route` | Choisis un autre `wireguard_network` et `wireguard_server_address` (par exemple `10.77.77.0/24` et `10.77.77.1`), ainsi que les adresses des appareils. |
| Le tunnel SSH ne marche plus | Normal en mode VPN : Grafana n'écoute plus sur `127.0.0.1`. Repasse `monitoring_grafana_access: ssh_tunnel` pour revenir au tunnel. |

## Revenir en arrière

1. Remets `monitoring_grafana_access: ssh_tunnel` et relance `monitoring.yml`.
   Grafana revient sur `127.0.0.1` et la règle UFW du port 3000 est supprimée.
2. Sur le VPS :

   ```bash
   sudo systemctl disable --now wg-quick@wg0
   sudo ufw delete allow 51820/udp
   sudo rm -f /etc/wireguard/wg0.conf /etc/wireguard/server.key /etc/wireguard/server.pub
   ```

3. Sur chaque appareil, supprime le tunnel `aegisops`.

L'accès SSH n'est jamais concerné par ces étapes.
