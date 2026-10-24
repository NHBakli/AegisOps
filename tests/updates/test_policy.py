"""Local tests for reboot approval and effective APT precedence."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class UpdatesHardeningTest(unittest.TestCase):
    def run_playbook(self, playbook, variables, temp):
        env = os.environ.copy()
        env["ANSIBLE_LOCAL_TEMP"] = str(Path(temp) / "ansible")
        env["ANSIBLE_REMOTE_TEMP"] = str(Path(temp) / "remote")
        env["XDG_CACHE_HOME"] = str(Path(temp) / "cache")
        return subprocess.run(
            [
                "ansible-playbook",
                "-i",
                "localhost,",
                playbook,
                "-e",
                json.dumps(variables),
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_reboot_requires_host_approval_and_recovery(self):
        with tempfile.TemporaryDirectory(prefix="aegisops-updates-") as temp:
            result = self.run_playbook(
                "tests/updates/preflight.yml",
                {
                    "updates_hardening_include_esm": False,
                    "updates_hardening_automatic_reboot": True,
                    "updates_hardening_reboot_time": "03:00",
                    "updates_hardening_reboot_approved_host": "",
                    "updates_hardening_recovery_confirmed": False,
                },
                temp,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("host-specific approval", result.stdout)
            self.assertIn("changed=0", result.stdout)

    def test_custom_origins_require_review_before_replacement(self):
        base = {
            "fixture_existing_lines": [
                'Unattended-Upgrade::Allowed-Origins:: "Custom:stable";'
            ],
            "updates_hardening_replace_existing_origins_confirmed": False,
        }
        with tempfile.TemporaryDirectory(prefix="aegisops-updates-") as temp:
            rejected = self.run_playbook(
                "tests/updates/review_existing_origins.yml", base, temp
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("Existing custom unattended-upgrades origins", rejected.stdout)
            approved = self.run_playbook(
                "tests/updates/review_existing_origins.yml",
                {**base, "updates_hardening_replace_existing_origins_confirmed": True},
                temp,
            )
            self.assertEqual(approved.returncode, 0, approved.stdout + approved.stderr)

    def test_policy_replaces_broad_origins_and_disables_reboot(self):
        with tempfile.TemporaryDirectory(prefix="aegisops-updates-") as temp:
            config_dir = Path(temp) / "apt.conf.d"
            config_dir.mkdir()
            (config_dir / "50unattended-upgrades").write_text(
                'Unattended-Upgrade::Allowed-Origins { "${distro_id}:${distro_codename}"; };\n'
                'Unattended-Upgrade::Origins-Pattern { "origin=Ubuntu"; };\n'
                'Unattended-Upgrade::Automatic-Reboot "true";\n'
            )
            apt_config = Path(temp) / "apt.conf"
            apt_config.write_text(
                f'Dir::Etc::Parts "{config_dir}";\n'
                'Dir::Etc::Main "/dev/null";\n'
            )
            variables = {
                "fixture_config_dir": str(config_dir),
                "fixture_apt_config": str(apt_config),
                "updates_hardening_include_esm": False,
                "updates_hardening_automatic_reboot": False,
                "updates_hardening_reboot_time": "03:00",
            }
            render = self.run_playbook("tests/updates/render.yml", variables, temp)
            self.assertEqual(render.returncode, 0, render.stdout + render.stderr)
            verify = self.run_playbook("tests/updates/verify_policy.yml", variables, temp)
            self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)


if __name__ == "__main__":
    unittest.main()
