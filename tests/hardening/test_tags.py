"""Check the public hardening tag contract without touching a remote host."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
ROLE_TAGS = {
    "users": "users_hardening",
    "ssh": "ssh_hardening",
    "firewall": "firewall_hardening",
    "fail2ban": "fail2ban",
    "updates": "updates_hardening",
}


class HardeningTagsTest(unittest.TestCase):
    def run_playbook(self, extra_args):
        with tempfile.TemporaryDirectory(prefix="aegisops-hardening-tags-") as temp:
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
                    "playbooks/hardening.yml",
                    *extra_args,
                ],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

    def test_untagged_run_lists_every_role(self):
        result = self.run_playbook(["--list-tasks"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for role in ROLE_TAGS.values():
            self.assertIn(f"{role} : ", result.stdout)

    def test_public_role_tags_are_listed(self):
        result = self.run_playbook(["--list-tags"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for tag in ROLE_TAGS:
            self.assertIn(tag, result.stdout)

    def test_each_tag_lists_only_its_role(self):
        for tag, expected_role in ROLE_TAGS.items():
            with self.subTest(tag=tag):
                result = self.run_playbook(["--list-tasks", "--tags", tag])
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn(f"{expected_role} : ", result.stdout)
                for other in ROLE_TAGS.values():
                    if other != expected_role:
                        self.assertNotIn(f"{other} : ", result.stdout)

    def test_users_tag_enters_preflight_without_mutating_localhost(self):
        result = self.run_playbook(["--tags", "users"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Set a non-root administrator", result.stdout)
        self.assertIn("changed=0", result.stdout)
        self.assertNotIn("ssh_hardening :", result.stdout)


if __name__ == "__main__":
    unittest.main()
