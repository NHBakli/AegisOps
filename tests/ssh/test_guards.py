"""Exercise SSH guardrails using a local inventory, never a real VPS."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class SSHHardeningGuardsTest(unittest.TestCase):
    def test_selected_ssh_role_requires_approval(self):
        with tempfile.TemporaryDirectory(prefix="aegisops-ssh-disabled-") as temp:
            inventory = Path(temp) / "hosts.ini"
            inventory.write_text(
                "[vps]\nlocalhost ansible_connection=local ansible_become=false\n"
            )
            environment = os.environ.copy()
            environment["ANSIBLE_LOCAL_TEMP"] = str(Path(temp) / "ansible-tmp")
            environment["ANSIBLE_REMOTE_TEMP"] = str(Path(temp) / "remote-tmp")
            environment["XDG_CACHE_HOME"] = str(Path(temp) / "cache")
            result = subprocess.run(
                ["ansible-playbook", "-i", str(inventory), "playbooks/hardening.yml", "--tags", "ssh"],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SSH changes require Ubuntu 22.04", result.stdout)
            self.assertIn("changed=0", result.stdout)

    def test_match_and_nonstandard_include_are_rejected(self):
        cases = {
            "safe": ("Include /etc/ssh/sshd_config.d/*.conf\nPermitRootLogin yes\n", None, True),
            "main_match": ("Include /etc/ssh/sshd_config.d/*.conf\nMatch User root\nPermitRootLogin yes\n", None, False),
            "other_include": ("Include /tmp/elsewhere/*.conf\n", None, False),
            "nested_match": ("Include /etc/ssh/sshd_config.d/*.conf\n", "match User root\n", False),
        }
        for name, (config, nested, expected_success) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory(prefix="aegisops-ssh-config-") as temp:
                config_path = Path(temp) / "sshd_config"
                config_path.write_text(config)
                include_dir = Path(temp) / "sshd_config.d"
                include_dir.mkdir()
                if nested is not None:
                    (include_dir / "override.conf").write_text(nested)
                environment = os.environ.copy()
                environment["ANSIBLE_LOCAL_TEMP"] = str(Path(temp) / "ansible-tmp")
                environment["ANSIBLE_REMOTE_TEMP"] = str(Path(temp) / "remote-tmp")
                environment["XDG_CACHE_HOME"] = str(Path(temp) / "cache")
                result = subprocess.run(
                    [
                        "ansible-playbook",
                        "-i",
                        "localhost,",
                        "tests/ssh/config_safety.yml",
                        "-e",
                        json.dumps(
                            {
                                "fixture_config_path": str(config_path),
                                "ssh_hardening_include_directory_path": str(include_dir),
                            }
                        ),
                    ],
                    cwd=ROOT,
                    env=environment,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(
                    result.returncode == 0,
                    expected_success,
                    result.stdout + result.stderr,
                )

    def test_symlinked_include_directory_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="aegisops-ssh-link-") as temp:
            config_path = Path(temp) / "sshd_config"
            config_path.write_text("Include /etc/ssh/sshd_config.d/*.conf\n")
            real_directory = Path(temp) / "real"
            real_directory.mkdir()
            include_link = Path(temp) / "sshd_config.d"
            include_link.symlink_to(real_directory, target_is_directory=True)
            environment = os.environ.copy()
            environment["ANSIBLE_LOCAL_TEMP"] = str(Path(temp) / "ansible-tmp")
            environment["ANSIBLE_REMOTE_TEMP"] = str(Path(temp) / "remote-tmp")
            environment["XDG_CACHE_HOME"] = str(Path(temp) / "cache")
            result = subprocess.run(
                [
                    "ansible-playbook",
                    "-i",
                    "localhost,",
                    "tests/ssh/config_safety.yml",
                    "-e",
                    json.dumps(
                        {
                            "fixture_config_path": str(config_path),
                            "ssh_hardening_include_directory_path": str(include_link),
                        }
                    ),
                ],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("symlinked SSH include path", result.stdout)


if __name__ == "__main__":
    unittest.main()
