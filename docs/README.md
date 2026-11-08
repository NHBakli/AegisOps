# Documentation AegisOps

Commence par le [README du projet](../README.md) pour la vue d'ensemble.
Ensuite, lis les documents dans cet ordre.

## 1. Comprendre et démarrer

1. [getting-started.md](getting-started.md) : le guide pas à pas, du clone du
   dépôt à un serveur durci, vérifié et supervisé.
2. [architecture.md](architecture.md) : comment le dépôt est organisé, pourquoi
   `hardening.yml` a deux plays, et le principe des gardes de sécurité.
3. [configuration.md](configuration.md) : la référence de chaque variable de
   `hardening-vars.yml`, avec sa valeur par défaut.

## 2. Une page par étape

4. [audit.md](audit.md) : ce que l'audit contrôle et le format du rapport JSON.
5. [users-hardening.md](users-hardening.md) : création de l'administrateur
   non-root (tag `users`).
6. [ssh-hardening.md](ssh-hardening.md) : durcissement SSH (tag `ssh`).
7. [firewall-hardening.md](firewall-hardening.md) : préparation et activation
   d'UFW (tag `firewall`).
8. [fail2ban.md](fail2ban.md) : jail SSH Fail2ban (tag `fail2ban`).
9. [updates-hardening.md](updates-hardening.md) : mises à jour de sécurité
   automatiques (tag `updates`).
10. [verify.md](verify.md) : vérification indépendante de l'état réel.
11. [monitoring.md](monitoring.md) : supervision Prometheus et Grafana, par
    tunnel SSH ou par VPN.
12. [vpn.md](vpn.md) : VPN WireGuard pour ouvrir le tableau de bord depuis ton
    PC, ton téléphone ou un autre ordinateur.

## 3. En cas de problème et pour contribuer

13. [recovery.md](recovery.md) : récupérer l'accès SSH et annuler chaque
    changement. **Lis-le avant ton premier durcissement.**
14. [testing.md](testing.md) : lancer les tests locaux, comprendre ce qu'ils
    prouvent et la CI GitHub.

## Comment sont écrites les pages par étape

Chaque page de durcissement suit le même plan :

- **À quoi ça sert** : le but, en deux phrases.
- **Ce que le rôle modifie** : les fichiers et services touchés.
- **Prérequis et confirmations** : ce qui doit être vrai avant de lancer.
- **Variables** : l'essentiel, avec un lien vers
  [configuration.md](configuration.md).
- **Lancer** : la commande exacte.
- **Vérifier** : comment contrôler le résultat.
- **Revenir en arrière / dépannage** : quoi faire si ça échoue.
