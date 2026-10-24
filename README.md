# AegisOps

Ansible pour auditer et durcir des serveurs Ubuntu. La cible testée est
Ubuntu 22.04 sous LXC ; UFW et Fail2ban doivent encore être validés dans un
environnement isolé.

## Cible

`ansible.cfg` utilise l'inventaire de production par défaut. Précise `-i`
pour choisir une autre cible. `inventories/example/hosts.yml` est un exemple,
pas un serveur de test prêt à l'emploi.

L'audit du VPS a déjà été lancé. Pour le relancer :

```bash
ansible-playbook playbooks/audit.yml
```

## Durcissement

Sans tag, `hardening.yml` parcourt les rôles dans l'ordre : utilisateurs, SSH,
UFW, Fail2ban, mises à jour. Le premier play crée l'administrateur avec la
connexion actuelle ; le suivant se reconnecte avec ce compte pour continuer.
Le compte utilise une clé SSH et n'a pas de mot de passe Unix actif par défaut.
Prépare `admin-vars.yml` à la racine du dépôt :

1. À la racine du dépôt, à côté de `ansible.cfg`, crée `admin-vars.yml` avec
   les paramètres de compte (exemple dans [docs/users-hardening.md](docs/users-hardening.md)).
   La clé publique et le chemin de sa clé privée locale sont requis. Le fichier
   est ignoré par Git. Aucun mot de passe ni Vault ne sont requis par défaut.
2. Lance le playbook complet quand les prérequis de chaque rôle sont configurés :

   ```bash
   ansible-playbook -i inventories/production/hosts.yml playbooks/hardening.yml -e @admin-vars.yml
   ```

Si tu ajoutes un hash de mot de passe local, chiffre le fichier avec
`ansible-vault encrypt admin-vars.yml` et ajoute `--ask-vault-pass` à la
commande. Le playbook s'arrête si un prérequis manque. `--tags users` ne crée
que le compte ; les autres tags présument que l'administrateur existe déjà.
UFW reste inactif par défaut. Les changements SSH et pare-feu exigent leurs
prérequis et une méthode de récupération.

## Suite à reprendre

Renseigner les valeurs réelles dans `admin-vars.yml`, relire les prérequis SSH
et pare-feu, puis lancer d'abord `--syntax-check`. Le hardening du VPS reste à
faire après validation de ces paramètres.

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
