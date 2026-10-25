"""Local guard tests. These runs never execute account-changing tasks."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
PLAYBOOK = ROOT / "playbooks" / "hardening.yml"


class UsersHardeningGuardsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aegisops-users-")
        self.addCleanup(self.temp.cleanup)
        self.inventory = Path(self.temp.name) / "hosts.ini"
        self.inventory.write_text(
            "[vps]\nlocalhost ansible_connection=local ansible_become=false\n"
        )

    def run_playbook(self, variables):
        environment = os.environ.copy()
        environment["ANSIBLE_LOCAL_TEMP"] = str(Path(self.temp.name) / "ansible-tmp")
        environment["ANSIBLE_REMOTE_TEMP"] = str(Path(self.temp.name) / "remote-tmp")
        environment["XDG_CACHE_HOME"] = str(Path(self.temp.name) / "cache")
        test_variables = {
            "users_hardening_admin_bootstrapped": False,
            "users_hardening_admin_username": "",
            "users_hardening_admin_public_keys": [],
            "users_hardening_sudo_mode": "nopasswd",
        }
        test_variables.update(variables)
        return subprocess.run(
            [
                "ansible-playbook",
                "-i",
                str(self.inventory),
                str(PLAYBOOK),
                "--tags",
                "users",
                "-e",
                json.dumps(test_variables),
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_selected_users_role_requires_configuration(self):
        result = self.run_playbook({})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("changed=0", result.stdout)
        self.assertIn("Set a non-root administrator", result.stdout)

    def test_root_account_is_rejected_before_mutation(self):
        result = self.run_playbook(
            {
                "users_hardening_admin_username": "root",
                "users_hardening_admin_public_keys": [
                    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI0123456789012345678901234567890 test"
                ],
                "users_hardening_sudo_mode": "nopasswd",
            }
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("changed=0", result.stdout)

    def test_new_account_cannot_use_password_based_sudo(self):
        result = self.run_playbook(
            {
                "users_hardening_admin_username": "aegis_missing_test_account",
                "users_hardening_admin_public_keys": [
                    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI0123456789012345678901234567890 test"
                ],
                "users_hardening_sudo_mode": "password",
            }
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Password based sudo requires an existing", result.stdout)
        self.assertIn("changed=0", result.stdout)


if __name__ == "__main__":
    unittest.main()
