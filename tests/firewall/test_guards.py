"""Check UFW guards locally without installing or enabling a firewall."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class FirewallGuardsTest(unittest.TestCase):
    def run_playbook(self, playbook, variables):
        with tempfile.TemporaryDirectory(prefix="aegisops-firewall-") as temp:
            inventory = Path(temp) / "hosts.ini"
            inventory.write_text(
                "[vps]\nlocalhost ansible_connection=local ansible_become=false\n"
            )
            environment = os.environ.copy()
            environment["ANSIBLE_LOCAL_TEMP"] = str(Path(temp) / "ansible-tmp")
            environment["ANSIBLE_REMOTE_TEMP"] = str(Path(temp) / "remote-tmp")
            environment["XDG_CACHE_HOME"] = str(Path(temp) / "cache")
            return subprocess.run(
                [
                    "ansible-playbook",
                    "-i",
                    str(inventory),
                    playbook,
                    "-e",
                    json.dumps(variables),
                ],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

    def test_platform_probe_collects_virtualization_type(self):
        result = self.run_playbook("tests/firewall/platform_facts.yml", {})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("changed=0", result.stdout)

    def test_rules_reject_duplicates_ssh_conflicts_and_unsafe_defaults(self):
        cases = {
            "valid": ({"firewall_hardening_allowed_inbound": [
                {"port": 80, "proto": "tcp"}, {"port": 443, "proto": "tcp"}
            ]}, True),
            "duplicate": ({"firewall_hardening_allowed_inbound": [
                {"port": 443, "proto": "tcp"}, {"port": 443, "proto": "tcp"}
            ]}, False),
            "ssh_conflict": ({"firewall_hardening_allowed_inbound": [
                {"port": 22, "proto": "tcp"}
            ]}, False),
            "unsafe_outbound": ({"firewall_hardening_default_outgoing": "deny"}, False),
            "unknown_key": ({"firewall_hardening_allowed_inbound": [
                {"port": 443, "proto": "tcp", "rule": "deny"}
            ]}, False),
        }
        for name, (variables, expected_success) in cases.items():
            with self.subTest(name=name):
                result = self.run_playbook(
                    "tests/firewall/validate_rules.yml", variables
                )
                self.assertEqual(
                    result.returncode == 0,
                    expected_success,
                    result.stdout + result.stderr,
                )
                self.assertIn("changed=0", result.stdout)

    def test_existing_ufw_rules_must_match_previous_intent(self):
        header = "Added user rules (see 'ufw status' for running firewall):\n"
        rule = header + "ufw allow 22/tcp\n"
        intent = {
            "ssh_port": 22,
            "allowed_inbound": [],
            "default_incoming": "deny",
            "default_outgoing": "allow",
        }
        cases = {
            "clean_first_run": (header, False, "", False, intent, intent, True),
            "unknown_existing_rule": (rule, False, "", False, intent, intent, False),
            "unchanged_rerun": (rule, True, rule, True, intent, intent, True),
            "rule_drift": (rule, True, header, True, intent, intent, False),
            "intent_drift": (rule, True, rule, True, intent, {**intent, "ssh_port": 23}, False),
        }
        for name, (added, has_manifest, prior, has_intent, old_intent, new_intent, expected_success) in cases.items():
            with self.subTest(name=name):
                result = self.run_playbook(
                    "tests/firewall/manifest_safety.yml",
                    {
                        "fixture_added_rules": added,
                        "fixture_manifest_exists": has_manifest,
                        "fixture_manifest": prior,
                        "fixture_intent_exists": has_intent,
                        "fixture_previous_intent": old_intent,
                        "fixture_requested_intent": new_intent,
                    },
                )
                self.assertEqual(result.returncode == 0, expected_success, result.stdout + result.stderr)
                self.assertIn("changed=0", result.stdout)

    def test_cap_net_admin_parser(self):
        for mask, expected_success in (("0000000000001000", True), ("0000000000000000", False)):
            with self.subTest(mask=mask):
                result = self.run_playbook(
                    "tests/firewall/capability.yml",
                    {"fixture_process_status": f"Name:\tansible\nCapEff:\t{mask}\n"},
                )
                self.assertEqual(result.returncode == 0, expected_success, result.stdout + result.stderr)
                self.assertIn("changed=0", result.stdout)

    def test_active_ufw_requires_both_preparation_manifests(self):
        for rule_exists, intent_exists, expected_success in (
            (False, False, False),
            (True, False, False),
            (True, True, True),
        ):
            with self.subTest(rule_exists=rule_exists, intent_exists=intent_exists):
                result = self.run_playbook(
                    "tests/firewall/active_manifest_requirement.yml",
                    {
                        "fixture_rule_manifest_exists": rule_exists,
                        "fixture_intent_manifest_exists": intent_exists,
                    },
                )
                self.assertEqual(result.returncode == 0, expected_success, result.stdout + result.stderr)
                self.assertIn("changed=0", result.stdout)

    def test_active_ufw_requires_policy_and_ssh_allowance(self):
        header = "Status: active\nLogging: on (low)\nDefault: deny (incoming), allow (outgoing), disabled (routed)\n"
        cases = {
            "expected": (header + "22/tcp                     ALLOW IN    Anywhere\n", True),
            "missing_ssh": (header + "80/tcp                     ALLOW IN    Anywhere\n", False),
            "wrong_policy": (
                "Status: active\nDefault: allow (incoming), allow (outgoing)\n"
                "22/tcp                     ALLOW IN    Anywhere\n", False
            ),
        }
        for name, (status, expected_success) in cases.items():
            with self.subTest(name=name):
                result = self.run_playbook(
                    "tests/firewall/verify_active_state.yml",
                    {"fixture_ufw_status": status},
                )
                self.assertEqual(result.returncode == 0, expected_success, result.stdout + result.stderr)
                self.assertIn("changed=0", result.stdout)


if __name__ == "__main__":
    unittest.main()
