"""Run real verification assertions with local command-output fixtures."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class VerifyTest(unittest.TestCase):
    def run_playbook(self, playbook, variables, extra_args=()):
        with tempfile.TemporaryDirectory(prefix="aegisops-verify-") as temp:
            inventory = Path(temp) / "hosts.ini"
            inventory.write_text(
                "[vps]\nlocalhost ansible_connection=local ansible_become=false\n"
            )
            env = os.environ.copy()
            env["ANSIBLE_LOCAL_TEMP"] = str(Path(temp) / "ansible")
            env["ANSIBLE_REMOTE_TEMP"] = str(Path(temp) / "remote")
            env["XDG_CACHE_HOME"] = str(Path(temp) / "cache")
            return subprocess.run(
                ["ansible-playbook", "-i", str(inventory), playbook,
                 "-e", json.dumps(variables), *extra_args],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

    def assert_fixture(self, variables, expected_success):
        result = self.run_playbook("tests/verify/assertions.yml", variables)
        self.assertEqual(result.returncode == 0, expected_success,
                         result.stdout + result.stderr)
        self.assertIn("changed=0", result.stdout)

    def test_empty_verification_refuses_to_claim_success(self):
        result = self.run_playbook("playbooks/verify.yml", {})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Select at least one verify_* section", result.stdout)
        self.assertIn("changed=0", result.stdout)

    def test_tags_cannot_hide_selected_checks(self):
        result = self.run_playbook(
            "playbooks/verify.yml", {"verify_updates": True}, ("--tags", "ssh")
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("run without --tags", result.stdout)
        self.assertIn("changed=0", result.stdout)

    def test_ssh_contexts_detect_root_or_password_regression(self):
        admin = ["port 22", "pubkeyauthentication yes",
                 "passwordauthentication no", "kbdinteractiveauthentication no"]
        root = ["permitrootlogin no", "passwordauthentication no",
                "kbdinteractiveauthentication no"]
        base = {"fixture_kind": "ssh", "fixture_admin_ssh_lines": admin,
                "fixture_root_ssh_lines": root}
        self.assert_fixture(base, True)
        self.assert_fixture({**base, "fixture_root_ssh_lines":
                             [*root[:-1], "kbdinteractiveauthentication yes"]}, False)

    def test_users_requires_managed_sudoers_policy(self):
        base = {"fixture_kind": "users"}
        self.assert_fixture({**base, "fixture_sudoers":
                             "aegisadmin ALL=(ALL:ALL) NOPASSWD:ALL\n"}, True)
        self.assert_fixture({**base, "fixture_sudoers":
                             "aegisadmin ALL=(ALL:ALL) ALL\n"}, False)

    def test_firewall_rejects_inactive_or_missing_ssh_allowance(self):
        base = "Status: active\nDefault: deny (incoming), allow (outgoing), disabled (routed)\n"
        self.assert_fixture({"fixture_kind": "firewall", "fixture_ufw_output":
                             base + "22/tcp  ALLOW IN  Anywhere\n"}, True)
        self.assert_fixture({"fixture_kind": "firewall", "fixture_ufw_output":
                             base + "80/tcp  ALLOW IN  Anywhere\n"}, False)
        self.assert_fixture({"fixture_kind": "firewall", "fixture_ufw_output":
                             base + "22/tcp  ALLOW IN  Anywhere\n"
                             + "3306/tcp  ALLOW IN  Anywhere\n"}, False)
        self.assert_fixture({"fixture_kind": "firewall", "fixture_ufw_output":
                             base + "22/tcp  ALLOW IN  Anywhere\n"
                             + "443/tcp  ALLOW IN  Anywhere\n",
                             "firewall_hardening_allowed_inbound":
                                 [{"port": 443, "proto": "tcp"}]}, True)

    def test_fail2ban_requires_real_jail_and_expected_action(self):
        settings = ["These IP addresses/networks are ignored:\n|- 127.0.0.1/8 ::1", "_SYSTEMD_UNIT=ssh.service",
                    "iptables-multiport", "5", "600", "600"]
        base = {"fixture_kind": "fail2ban", "fixture_fail2ban_service": "active",
                "fixture_fail2ban_jail": "Status for the jail: sshd",
                "fixture_fail2ban_settings": [{"stdout": s} for s in settings]}
        self.assert_fixture(base, True)
        bad = [{"stdout": s} for s in [*settings[:2], "nftables", *settings[3:]]]
        self.assert_fixture({**base, "fixture_fail2ban_settings": bad}, False)
        wrong_ignore = [{"stdout": s} for s in ["203.0.113.1", *settings[1:]]]
        self.assert_fixture({**base, "fixture_fail2ban_settings": wrong_ignore}, False)

    def test_ipv6_ssh_listener_is_outside_ban_scope(self):
        header = "sl  local_address rem_address st\n"
        line = "0: 00000000000000000000000000000000:{port} 00000000000000000000000000000000:0000 0A\n"
        accepted = self.run_playbook(
            "tests/verify/tcp6.yml", {"fixture_tcp6": header + line.format(port="0050")}
        )
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
        self.assertIn("changed=0", accepted.stdout)
        rejected = self.run_playbook(
            "tests/verify/tcp6.yml", {"fixture_tcp6": header + line.format(port="0016")}
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("IPv4-only ban probe is insufficient", rejected.stdout)

    def test_updates_rejects_nonsecurity_origin(self):
        lines = [
            'APT::Periodic::Update-Package-Lists "1";',
            'APT::Periodic::Unattended-Upgrade "1";',
            'Unattended-Upgrade::Allowed-Origins:: "${distro_id}:${distro_codename}-security";',
            'Unattended-Upgrade::Automatic-Reboot "false";',
            'Unattended-Upgrade::Automatic-Reboot-WithUsers "false";',
        ]
        base = {"fixture_kind": "updates", "fixture_apt_lines": lines}
        self.assert_fixture(base, True)
        self.assert_fixture({**base, "fixture_apt_lines":
                             [*lines, 'Unattended-Upgrade::Allowed-Origins:: "Ubuntu:jammy";']}, False)


if __name__ == "__main__":
    unittest.main()
