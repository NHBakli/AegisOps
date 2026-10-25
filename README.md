# AegisOps

Ansible pour auditer, durcir et vérifier des serveurs Ubuntu. La cible
actuelle est Ubuntu 22.04 sous LXC. UFW est préparé mais reste inactif par
défaut ; son activation dépend des capacités réseau disponibles dans LXC.
Le projet est distribué sous licence [MIT](LICENSE).

## Cible

`ansible.cfg` utilise l'inventaire d'exemple par défaut pour éviter de viser un
serveur réel par inadvertance. `inventories/example/hosts.yml` utilise une
adresse réservée à la documentation. Pour un vrai serveur, crée ton inventaire
local, ignoré par Git :

```bash
cp inventories/example/hosts.yml inventories/production/hosts.local.yml
```

Modifie ensuite `inventories/production/hosts.local.yml` et indique ce chemin
avec `-i` à chaque commande ciblant ce serveur. Pour auditer :

```bash
ansible-playbook -i inventories/production/hosts.local.yml playbooks/audit.yml
```

## Durcissement

Sans tag, `hardening.yml` parcourt les rôles dans l'ordre : utilisateurs, SSH,
UFW, Fail2ban, mises à jour. Les playbooks chargent automatiquement le fichier
local `hardening-vars.yml`, commun à l'audit, au durcissement et à la
vérification. Prépare-le une seule fois :

1. Copie le modèle :

   ```bash
   cp hardening-vars.yml.example hardening-vars.yml
   ```

2. Génère une paire de clés dédiée sur ta machine. Choisis un autre nom si ce
   fichier existe déjà :

   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/aegisops_admin -C "aegisadmin@aegisops"
   ```

   Copie la clé publique dans `users_hardening_admin_public_keys` :

   ```bash
   cat ~/.ssh/aegisops_admin.pub
   ```

   Garde la clé privée `~/.ssh/aegisops_admin` sur ta machine. Renseigne son
   chemin absolu dans les variables de sonde. Ne partage jamais cette clé.
3. Complète dans `hardening-vars.yml` le nom d'hôte et les confirmations
   nécessaires. Fail2ban découvre automatiquement l'IPv4 source avec une
   connexion SSH indépendante. Le pare-feu reste inactif par défaut. Ce
   fichier est ignoré par Git.
4. Pour créer le compte seulement, laisse
   `users_hardening_admin_bootstrapped: false` et lance :

   ```bash
   ansible-playbook -i inventories/production/hosts.local.yml \
     playbooks/hardening.yml --tags users
   ```

Teste ensuite une nouvelle connexion SSH avec cet administrateur et vérifie
`sudo -n true`. Quand ces tests réussissent, passe
`users_hardening_admin_bootstrapped` à `true`. Les prochaines exécutions
passeront automatiquement l'étape de bootstrap root et utiliseront le compte
administrateur. Pour lancer un seul domaine, utilise `--tags ssh`,
`--tags firewall`, `--tags fail2ban` ou `--tags updates`.

Si tu ajoutes un hash de mot de passe local, chiffre le fichier complet avec
`ansible-vault encrypt hardening-vars.yml`, puis ajoute `--ask-vault-pass` aux
commandes. Les prérequis sensibles restent vérifiés avant toute modification.

## Vérifier l'état appliqué

`verify.yml` contrôle l'état réellement présent sur le VPS sans le modifier.
Les sections à exécuter se choisissent dans `hardening-vars.yml` avec
`verify_users`, `verify_ssh`, `verify_firewall`, `verify_fail2ban` et
`verify_updates`. Active uniquement les sections correspondant aux protections
que tu veux vérifier. Laisse `verify_firewall: false` tant qu'UFW n'est pas
activé.

Pour les contrôles SSH et Fail2ban, récupère l'IPv4 source vue par le VPS avec
une connexion SSH indépendante :

```bash
VPS_IP=203.0.113.10 # remplace par l'adresse de ton VPS
ssh -i ~/.ssh/aegisops_admin "aegisadmin@$VPS_IP" 'echo "$SSH_CONNECTION"'
```

La première valeur affichée est l'IPv4 source. Renseigne-la dans
`verify_ssh_source_ip`, `verify_ssh_source_host` et
`fail2ban_hardening_admin_source_ip`. Pour `verify_ssh_source_host`, la même
adresse convient lorsqu'il n'y a pas de règle SSH conditionnelle basée sur un
nom d'hôte.

Exemple de sections activées après le hardening SSH, Fail2ban et mises à jour :

```yaml
verify_users: true
verify_ssh: true
verify_firewall: false
verify_fail2ban: true
verify_updates: true
verify_ssh_source_ip: "203.0.113.10"
verify_ssh_source_host: "203.0.113.10"
fail2ban_hardening_admin_source_ip: "203.0.113.10"
```

Lance ensuite la vérification :

```bash
ansible-playbook -i inventories/production/hosts.local.yml playbooks/verify.yml
```

Le playbook se connecte avec `aegisadmin` et la clé déclarée dans le fichier
central. Un résultat `failed=0` confirme uniquement les sections activées ;
les tâches des autres sections apparaissent comme ignorées.

## Vérifications locales

```bash
ansible-galaxy collection install -r requirements.yml --force
ansible-playbook -i inventories/example/hosts.yml playbooks/hardening.yml --syntax-check
ansible-lint --offline
python3 -m unittest discover -s tests -p 'test_*.py'
```

Si Ansible affiche que `community.general 13.0.1` ne supporte pas Core 2.16,
la commande Galaxy ci-dessus installe la version 8.3.0 épinglée par le projet.
Les tests locaux ne remplacent pas un essai sur Ubuntu 22.04 isolé.

Voir [docs/users-hardening.md](docs/users-hardening.md),
[docs/verify.md](docs/verify.md) et les guides spécialisés dans `docs/`.
