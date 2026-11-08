# Mises à jour de sécurité (`updates_hardening`)

## À quoi ça sert

Ce rôle configure `unattended-upgrades` pour installer chaque jour, tout seul,
les **mises à jour de sécurité** d'Ubuntu. Il ne lance pas de mise à jour
immédiate. **Le redémarrage automatique reste désactivé par défaut.**

## Ce que le rôle modifie

- Écrit `/etc/apt/apt.conf.d/99aegisops-unattended-upgrades` (avec
  sauvegarde) **avant** d'installer le paquet, pour que la politique sûre soit
  en place dès l'installation :

  ```text
  APT::Periodic::Update-Package-Lists "1";
  APT::Periodic::Unattended-Upgrade "1";
  Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
  };
  Unattended-Upgrade::Automatic-Reboot "false";
  Unattended-Upgrade::Automatic-Reboot-WithUsers "false";
  Unattended-Upgrade::Automatic-Reboot-Time "03:00";
  ```

  `${distro_codename}` vaut `jammy` sur 22.04 et `noble` sur 24.04. Le fichier
  **remplace** les origines définies ailleurs : seules les mises à jour de
  sécurité restent (plus ESM si tu le demandes).
- Installe `unattended-upgrades`.
- Active et démarre `apt-daily.timer` et `apt-daily-upgrade.timer`.

## Prérequis et confirmations

- Ubuntu 22.04 ou 24.04, sans mode `--check`.
- `updates_hardening_include_esm` et `updates_hardening_automatic_reboot` sont
  des booléens, et l'heure est au format `HH:MM`.
- **Origines personnalisées** : si APT contient déjà d'autres origines que
  celles d'Ubuntu (dépôt tiers, `Origins-Pattern`), le rôle s'arrête. Après
  revue de `apt-config dump`, accepte leur remplacement avec
  `updates_hardening_replace_existing_origins_confirmed: true`.
- **Redémarrage automatique** : décision séparée. Il faut
  `updates_hardening_automatic_reboot: true`,
  `updates_hardening_reboot_approved_host` égal au nom de l'hôte et
  `updates_hardening_recovery_confirmed: true`. N'active cette option qu'avec
  une fenêtre de maintenance prévue.

## Variables

```yaml
updates_hardening_include_esm: false
updates_hardening_replace_existing_origins_confirmed: false
updates_hardening_automatic_reboot: false
updates_hardening_reboot_time: "03:00"
updates_hardening_reboot_approved_host: ""
updates_hardening_recovery_confirmed: false
```

Référence complète :
[configuration.md](configuration.md#mises-à-jour-updates_hardening_).

## Lancer

```bash
ansible-playbook -i inventories/production/hosts.local.yml \
  playbooks/hardening.yml --tags updates
```

Ajoute `--ask-vault-pass` si `hardening-vars.yml` est chiffré.

Le rôle relit la configuration effective (`apt-config dump`) avant et après
l'installation du paquet, puis l'état des deux timers.

## Vérifier

```bash
ssh -i ~/.ssh/aegisops_admin aegisadmin@203.0.113.10 \
  'apt-config dump | grep -E "Periodic|Allowed-Origins|Automatic-Reboot"; systemctl list-timers "apt-daily*"'
```

Pour un essai à blanc de `unattended-upgrades` sur le serveur :

```bash
sudo unattended-upgrade --dry-run --debug
```

Puis active `verify_updates: true` et lance `verify.yml` (voir
[verify.md](verify.md)).

## Revenir en arrière / dépannage

- **`Existing custom unattended-upgrades origins would be replaced`** : un
  autre fichier de `/etc/apt/apt.conf.d/` ajoute des origines. Revois-le, puis
  confirme le remplacement ou abandonne.
- **Même sans redémarrage automatique**, une mise à jour peut redémarrer
  certains services. Un redémarrage requis est signalé par
  `/var/run/reboot-required` (et dans le tableau de bord de supervision).
- **Annuler la politique AegisOps** :
  `sudo rm /etc/apt/apt.conf.d/99aegisops-unattended-upgrades`. Les réglages
  d'Ubuntu reprennent effet. Voir
  [recovery.md](recovery.md#mises-à-jour-automatiques).
- Dans un conteneur LXC, les mises à jour du noyau et le redémarrage dépendent
  aussi de l'hôte.
