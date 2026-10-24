"""Exercise the real Ansible report task with local fixture data."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ReportTest(unittest.TestCase):
    def test_summary_counts_are_json_numbers(self):
        with tempfile.TemporaryDirectory(prefix="aegisops-report-") as tmp:
            report_dir = Path(tmp) / "reports"
            env = os.environ.copy()
            env["ANSIBLE_LOCAL_TEMP"] = str(Path(tmp) / "ansible")
            env["ANSIBLE_REMOTE_TEMP"] = str(Path(tmp) / "remote")
            env["XDG_CACHE_HOME"] = str(Path(tmp) / "cache")
            result = subprocess.run(
                [
                    "ansible-playbook",
                    "-i",
                    "localhost,",
                    "tests/audit/report.yml",
                    "-e",
                    f"audit_report_directory={report_dir}",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads((report_dir / "localhost.json").read_text())
            expected = {"total": 5, "passed": 2, "failed": 1, "warnings": 1, "review": 1}
            self.assertEqual(report["summary"], expected)
            for value in report["summary"].values():
                self.assertIs(type(value), int)

    def test_report_tag_includes_required_audits(self):
        with tempfile.TemporaryDirectory(prefix="aegisops-tags-") as tmp:
            inventory = Path(tmp) / "hosts.yml"
            inventory.write_text("all:\n  children:\n    vps:\n      hosts:\n        localhost:\n")
            env = os.environ.copy()
            env["ANSIBLE_LOCAL_TEMP"] = str(Path(tmp) / "ansible")
            env["XDG_CACHE_HOME"] = str(Path(tmp) / "cache")
            result = subprocess.run(
                [
                    "ansible-playbook",
                    "-i",
                    str(inventory),
                    "playbooks/audit.yml",
                    "--list-tasks",
                    "--tags",
                    "report",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for task in (
                "Collect SSH configuration",
                "Collect local user accounts",
                "Check if UFW is installed",
                "Check unattended-upgrades package",
                "Generate JSON security report",
            ):
                self.assertIn(task, result.stdout)


if __name__ == "__main__":
    unittest.main()
