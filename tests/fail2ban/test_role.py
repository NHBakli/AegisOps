"""Exercise Fail2ban guards and rendering without touching a host firewall."""

import configparser
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class Fail2banLocalTest(unittest.TestCase):
    def run_fixture(self, playbook, variables):
        with tempfile.TemporaryDirectory(prefix="aegisops-fail2ban-") as temp:
            environment = os.environ.copy()
            environment["ANSIBLE_LOCAL_TEMP"] = str(Path(temp) / "ansible")
            environment["ANSIBLE_REMOTE_TEMP"] = str(Path(temp) / "remote")
            environment["XDG_CACHE_HOME"] = str(Path(temp) / "cache")
            dest = Path(temp) / "jail.local"
            result = subprocess.run(
                [
                    "ansible-playbook",
                    "-i",
                    "localhost,",
                    f"tests/fail2ban/{playbook}",
                    "-e",
                    json.dumps({**variables, "fixture_dest": str(dest)}),
                ],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            contents = dest.read_text() if dest.exists() else None
            return result, contents

    def test_role_rejects_missing_approval_before_mutation(self):
        result, _ = self.run_fixture("preflight_role.yml", {})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("changed=0", result.stdout)
        self.assertIn("Fail2ban requires Ubuntu 22.04", result.stdout)

    def test_jail_uses_ssh_journal_and_explicit_admin_exception(self):
        result, contents = self.run_fixture("render.yml", {})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        jail = configparser.ConfigParser(interpolation=None)
        jail.read_string(contents)
        self.assertEqual(jail["sshd"]["backend"], "systemd")
        self.assertEqual(jail["sshd"]["port"], "2222")
        self.assertEqual(jail["sshd"]["maxretry"], "4")
        self.assertEqual(jail["sshd"]["findtime"], "900")
        self.assertEqual(jail["sshd"]["bantime"], "3600")
        self.assertIn("198.51.100.7", jail["sshd"]["ignoreip"].split())
        self.assertIn("ssh.service", jail["sshd"]["journalmatch"])
        self.assertNotIn("logpath", jail["sshd"])

    def test_ignore_list_requires_exact_source_and_excludes_probe_network(self):
        cases = (
            ("These IP addresses/networks are ignored:\n|- 127.0.0.0/8\n`- 198.51.100.7\n", True),
            ("127.0.0.0/8 ::1 198.51.100.7", True),
            ("['127.0.0.0/8', '::1', '198.51.100.7']", True),
            ("127.0.0.0/8 1198.51.100.7", False),
            ("127.0.0.0/8 198.51.100.7 192.0.2.0/24", False),
        )
        for output, accepted in cases:
            with self.subTest(output=output):
                result, _ = self.run_fixture(
                    "verify_ignoreip.yml", {"fixture_ignoreip": output}
                )
                self.assertEqual(
                    result.returncode == 0, accepted, result.stdout + result.stderr
                )

    def test_ban_rule_must_be_on_ssh_jail_chain(self):
        cases = (
            ("-A INPUT -p tcp -m multiport --dports 22 -j f2b-sshd\n"
             "-A f2b-sshd -s 192.0.2.123/32 -j REJECT\n", True),
            ("-A other -s 192.0.2.123/32 -j REJECT\n-A f2b-sshd -j RETURN\n", False),
            ("-A f2b-sshd -s 192.0.2.123/32 -j REJECT\n", False),
            ("-A INPUT -p tcp -j f2b-sshd\n"
             "-A f2b-sshd -s 192.0.2.124/32 -j REJECT\n", False),
        )
        for rules, accepted in cases:
            with self.subTest(rules=rules):
                result, _ = self.run_fixture(
                    "verify_probe_rule.yml", {"fixture_iptables": rules}
                )
                self.assertEqual(
                    result.returncode == 0, accepted, result.stdout + result.stderr
                )

    def test_existing_local_ssh_jails_are_rejected(self):
        cases = (
            ("[other]\nenabled = true\n", True),
            ("# [sshd]\n[other]\n", True),
            ("[sshd]\nenabled = true\n", False),
            ("  [SSHD] ; alternate jail\n", False),
        )
        for jail, accepted in cases:
            with self.subTest(jail=jail):
                result, _ = self.run_fixture(
                    "competing_jails.yml", {"fixture_jail": jail}
                )
                self.assertEqual(
                    result.returncode == 0, accepted, result.stdout + result.stderr
                )

    def test_independent_ssh_source_matches_ignored_address(self):
        cases = (
            ("198.51.100.7 54321 203.0.113.8 22", True),
            ("198.51.100.8 54321 203.0.113.8 22", False),
            ("", False),
        )
        for connection, accepted in cases:
            with self.subTest(connection=connection):
                result, _ = self.run_fixture(
                    "verify_probe_source.yml", {"fixture_connection": connection}
                )
                self.assertEqual(
                    result.returncode == 0, accepted, result.stdout + result.stderr
                )

    def test_ipv4_only_admin_source(self):
        for source, accepted in (("198.51.100.7", True), ("2001:db8::7", False)):
            with self.subTest(source=source):
                result, _ = self.run_fixture(
                    "validate_addresses.yml",
                    {"fail2ban_hardening_admin_source_ip": source},
                )
                self.assertEqual(
                    result.returncode == 0, accepted, result.stdout + result.stderr
                )

    def test_ipv6_ssh_listener_is_rejected(self):
        header = "  sl  local_address                         remote_address                        st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n"
        address = "00000000000000000000000000000000"
        for state, port, accepted in (("0A", "0016", False), ("0A", "0050", True), ("01", "0016", True)):
            with self.subTest(state=state, port=port):
                row = f"   0: {address}:{port} {address}:0000 {state} 00000000:00000000 00:00000000 00000000 0 0 0\n"
                result, _ = self.run_fixture(
                    "verify_ipv4_scope.yml", {"fixture_tcp6": header + row}
                )
                self.assertEqual(
                    result.returncode == 0, accepted, result.stdout + result.stderr
                )


if __name__ == "__main__":
    unittest.main()
