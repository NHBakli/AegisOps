"""Local tests for the monitoring role: guards, templates, exporter, dashboard."""

import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
ROLE = ROOT / "roles" / "monitoring"
PASSWORD = "Zx9+Qw3/Lp7=Rt5.Kv8_Mn"


def load_exporter():
    spec = importlib.util.spec_from_file_location(
        "aegisops_security_exporter", ROLE / "files" / "aegisops-security-exporter.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EXPORTER = load_exporter()

F2B_STATUS = """Status
|- Number of jail:\t2
`- Jail list:\tsshd, recidive
"""
F2B_SSHD = """Status for the jail: sshd
|- Filter
|  |- Currently failed:\t3
|  |- Total failed:\t120
|  `- Journal matches:\t_SYSTEMD_UNIT=ssh.service + _COMM=sshd
`- Actions
   |- Currently banned:\t2
   |- Total banned:\t17
   `- Banned IP list:\t198.51.100.7 2001:db8::1 198.51.100.7 203.0.113.0/24 not-an-ip
"""
F2B_RECIDIVE = F2B_SSHD.replace("sshd", "recidive").replace(
    "Banned IP list:\t198.51.100.7 2001:db8::1 198.51.100.7 203.0.113.0/24 not-an-ip", "Banned IP list:\t"
)
UFW_ACTIVE = """Status: active

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       Anywhere
22/tcp (v6)                ALLOW       Anywhere (v6)
"""
SSHD_T = """port 22
permitrootlogin no
passwordauthentication no
pubkeyauthentication yes
kbdinteractiveauthentication no
"""


def fake_run(outputs):
    def run(argv):
        key = " ".join(argv)
        value = outputs.get(key)
        if isinstance(value, Exception):
            raise value
        if value is None:
            raise FileNotFoundError(key)
        return value
    return run


def parse_metrics(text):
    """Minimal text-format check: TYPE before samples, families contiguous."""
    samples, seen, current = {}, set(), None
    for line in text.splitlines():
        if line.startswith("# TYPE "):
            name = line.split()[2]
            if name in seen:
                raise AssertionError(f"family {name} is not contiguous")
            seen.add(name)
            current = name
            continue
        match = re.match(r'^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{.*\})? (-?[0-9.]+)$', line)
        if not match or match.group(1) != current:
            raise AssertionError(f"invalid or untyped sample: {line!r}")
        samples[match.group(1) + (match.group(2) or "")] = float(match.group(3))
    return samples


class ExporterTest(unittest.TestCase):
    outputs = {
        "fail2ban-client status": F2B_STATUS,
        "fail2ban-client status sshd": F2B_SSHD,
        "fail2ban-client status recidive": F2B_RECIDIVE,
        "ufw status": UFW_ACTIVE,
        "sshd -T": SSHD_T,
        "ss -Htn state established ( sport = :22 )": "ESTAB 0 0 10.0.0.2:22 198.51.100.9:5000\n",
    }

    def render(self, outputs, max_ips=100):
        with mock.patch.object(EXPORTER, "run", fake_run(outputs)):
            return parse_metrics(EXPORTER.render(max_ips))

    def test_full_collection(self):
        metrics = self.render(self.outputs)
        self.assertEqual(metrics['aegisops_fail2ban_up'], 1)
        self.assertEqual(metrics['aegisops_fail2ban_jail_banned_current{jail="sshd"}'], 2)
        self.assertEqual(metrics['aegisops_fail2ban_jail_failed_total{jail="sshd"}'], 120)
        self.assertEqual(metrics['aegisops_fail2ban_banned_ip{jail="sshd",ip="198.51.100.7"}'], 1)
        self.assertEqual(metrics['aegisops_fail2ban_banned_ip{jail="sshd",ip="2001:db8::1"}'], 1)
        self.assertEqual(metrics['aegisops_fail2ban_banned_ip{jail="sshd",ip="203.0.113.0/24"}'], 1)
        self.assertNotIn("not-an-ip", " ".join(metrics))
        banned = [key for key in metrics if key.startswith("aegisops_fail2ban_banned_ip{")]
        self.assertEqual(len(banned), 3)  # duplicates removed
        self.assertEqual(metrics['aegisops_ufw_active'], 1)
        self.assertEqual(metrics['aegisops_ufw_rules'], 2)
        self.assertEqual(metrics['aegisops_ssh_check{check="root_login_disabled"}'], 1)
        self.assertEqual(metrics['aegisops_ssh_established_connections'], 1)
        for section in ("fail2ban", "ufw", "ssh"):
            self.assertEqual(
                metrics[f'aegisops_exporter_section_success{{section="{section}"}}'], 1
            )

    def test_failing_section_is_isolated(self):
        outputs = dict(self.outputs)
        outputs["fail2ban-client status"] = subprocess.CalledProcessError(255, "f2b")
        outputs["sshd -T"] = SSHD_T.replace("permitrootlogin no", "permitrootlogin yes")
        metrics = self.render(outputs)
        self.assertEqual(metrics['aegisops_fail2ban_up'], 0)
        self.assertEqual(metrics['aegisops_exporter_section_success{section="fail2ban"}'], 0)
        self.assertEqual(metrics['aegisops_exporter_section_success{section="ufw"}'], 1)
        self.assertEqual(metrics['aegisops_ssh_check{check="root_login_disabled"}'], 0)
        self.assertFalse(any(key.startswith("aegisops_fail2ban_jail") for key in metrics))

    def test_partial_section_output_is_discarded(self):
        outputs = dict(self.outputs)
        outputs["fail2ban-client status recidive"] = "garbage"
        metrics = self.render(outputs)
        self.assertEqual(metrics['aegisops_exporter_section_success{section="fail2ban"}'], 0)
        self.assertFalse(any(key.startswith("aegisops_fail2ban_jail") for key in metrics))

    def test_banned_ip_list_is_capped(self):
        metrics = self.render(self.outputs, max_ips=1)
        banned = [key for key in metrics if key.startswith("aegisops_fail2ban_banned_ip{")]
        self.assertEqual(len(banned), 1)
        self.assertEqual(metrics['aegisops_fail2ban_banned_ip_truncated{jail="sshd"}'], 1)

    def test_parsers_reject_unexpected_output(self):
        with self.assertRaises(ValueError):
            EXPORTER.parse_ufw_status("ERROR: not root")
        with self.assertRaises(ValueError):
            EXPORTER.parse_sshd_config("port 22\n")
        with self.assertRaises(ValueError):
            EXPORTER.parse_jail_list("nothing")
        self.assertEqual(EXPORTER.parse_jail_list("`- Jail list:\tsshd, bad jail;"), ["sshd"])

    def test_ufw_inactive(self):
        self.assertEqual(EXPORTER.parse_ufw_status("Status: inactive\n"), (False, 0))

    def test_atomic_write_and_suffix_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            target = os.path.join(temp, "aegisops.prom")
            with mock.patch.object(EXPORTER, "run", fake_run(self.outputs)):
                EXPORTER.main(["--output", target])
            parse_metrics(Path(target).read_text())
            self.assertEqual(os.stat(target).st_mode & 0o777, 0o644)
            self.assertEqual([p for p in os.listdir(temp) if p.startswith(".")], [])
            with self.assertRaises(SystemExit), mock.patch("sys.stderr"):
                EXPORTER.main(["--output", os.path.join(temp, "x.txt")])


class AnsibleRunner:
    def run_playbook(self, playbook, variables, temp, inventory="localhost,"):
        env = os.environ.copy()
        env["ANSIBLE_LOCAL_TEMP"] = str(Path(temp) / "ansible")
        env["ANSIBLE_REMOTE_TEMP"] = str(Path(temp) / "remote")
        env["XDG_CACHE_HOME"] = str(Path(temp) / "cache")
        return subprocess.run(
            ["ansible-playbook", "-i", inventory, playbook, "-e", json.dumps(variables)],
            cwd=ROOT, env=env, capture_output=True, text=True, check=False,
        )


class PreflightTest(unittest.TestCase, AnsibleRunner):
    valid = {
        "monitoring_approved_host": "my-vps",
        "monitoring_admin_user": "aegisadmin",
        "monitoring_grafana_admin_password": PASSWORD,
    }

    def preflight(self, **overrides):
        variables = dict(self.valid)
        variables.update(overrides)
        with tempfile.TemporaryDirectory(prefix="aegisops-monitoring-") as temp:
            return self.run_playbook("tests/monitoring/preflight.yml", variables, temp, "my-vps,")

    def test_valid_inputs_pass_without_changes(self):
        result = self.preflight()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("changed=0", result.stdout)

    def test_secret_never_printed(self):
        for result in (self.preflight(), self.preflight(monitoring_grafana_admin_password="short")):
            self.assertNotIn(PASSWORD, result.stdout + result.stderr)
            self.assertNotIn('"short"', result.stdout + result.stderr)

    def test_guards_reject_unsafe_inputs(self):
        cases = {
            "unapproved host": {"monitoring_approved_host": "other"},
            "root admin": {"monitoring_admin_user": "root"},
            "weak password": {"monitoring_grafana_admin_password": "short"},
            "quoted password": {"monitoring_grafana_admin_password": 'a"' + PASSWORD},
            "unsupported release": {"fixture_distribution_version": "20.04"},
            "low memory": {"fixture_free_mb": 1500},
            "string ceiling": {"monitoring_grafana_memory_max_mb": "384"},
            "bad retention": {"monitoring_prometheus_retention_time": "forever"},
            "fast scrape": {"monitoring_scrape_interval": "1s"},
        }
        for name, override in cases.items():
            with self.subTest(case=name):
                result = self.preflight(**override)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("changed=0", result.stdout)


class TemplateTest(unittest.TestCase, AnsibleRunner):
    def test_rendered_services_listen_on_loopback_only(self):
        with tempfile.TemporaryDirectory(prefix="aegisops-monitoring-") as temp:
            out = Path(temp) / "out"
            out.mkdir()
            result = self.run_playbook(
                "tests/monitoring/render.yml",
                {"output_dir": str(out), "monitoring_grafana_admin_password": PASSWORD}, temp,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn(PASSWORD, result.stdout)
            rendered = {path.name: path.read_text() for path in out.iterdir()}
        self.assertIn("--web.listen-address=127.0.0.1:9090", rendered["prometheus.conf"])
        self.assertIn("MemoryMax=512M", rendered["prometheus.conf"])
        self.assertIn("GOMEMLIMIT=409MiB", rendered["prometheus.conf"])
        exporter = rendered["prometheus-node-exporter.conf"]
        self.assertIn("--web.listen-address=127.0.0.1:9100", exporter)
        self.assertIn("ssh[.]service|", exporter)
        include = re.search(r"unit-include=(\S+)", exporter).group(1)
        self.assertNotIn("\\", include)
        self.assertNotIn("$", include)
        env = rendered["grafana.env"]
        self.assertIn("GF_SERVER_HTTP_ADDR=127.0.0.1\n", env)
        self.assertIn("GF_AUTH_ANONYMOUS_ENABLED=false\n", env)
        self.assertIn("GF_USERS_ALLOW_SIGN_UP=false\n", env)
        self.assertIn(f"GF_SECURITY_ADMIN_PASSWORD={PASSWORD}\n", env)
        grafana_unit = rendered["grafana-server.conf"]
        self.assertIn("EnvironmentFile=/etc/aegisops/grafana.env", grafana_unit)
        self.assertIn("IPAddressDeny=any\n", grafana_unit)
        self.assertIn("IPAddressAllow=localhost\n", grafana_unit)
        targets = re.findall(r'targets: \["([^"]+)"\]', rendered["prometheus.yml"])
        self.assertEqual(len(targets), 3)
        self.assertEqual(targets, ["127.0.0.1:9090", "127.0.0.1:9100", "localhost:3000"])
        self.assertIn("ProtectSystem=full", rendered["aegisops-security-exporter.service"])
        self.assertIn("uid: aegisops-prometheus", rendered["grafana-datasource.yml"])
        if shutil.which("promtool"):
            subprocess.run(["promtool", "check", "config", "/dev/stdin"],
                           input=rendered["prometheus.yml"], text=True, check=True)


class VerifyAssertTest(unittest.TestCase, AnsibleRunner):
    loopback = [
        "LISTEN 0 4096 127.0.0.1:9090 0.0.0.0:*",
        "LISTEN 0 4096 127.0.0.1:9100 0.0.0.0:*",
        "LISTEN 0 4096 127.0.0.1:3000 0.0.0.0:*",
        "LISTEN 0 128 0.0.0.0:22 0.0.0.0:*",
    ]

    def check(self, **variables):
        with tempfile.TemporaryDirectory(prefix="aegisops-monitoring-") as temp:
            return self.run_playbook("tests/monitoring/verify_assert.yml", variables, temp)

    def test_loopback_listeners_pass(self):
        result = self.check(fixture_listeners=self.loopback)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_exposure_and_staleness_fail(self):
        cases = {
            "wildcard grafana": self.loopback[:2] + ["LISTEN 0 4096 *:3000 *:*"] + self.loopback[3:],
            "ipv6 exporter": self.loopback + ["LISTEN 0 4096 [::]:9100 [::]:*"],
            "public prometheus": ["LISTEN 0 4096 0.0.0.0:9090 0.0.0.0:*"] + self.loopback[1:],
            "missing listener": self.loopback[1:],
        }
        for name, listeners in cases.items():
            with self.subTest(case=name):
                self.assertNotEqual(self.check(fixture_listeners=listeners).returncode, 0)
        with self.subTest(case="stale metrics"):
            self.assertNotEqual(
                self.check(fixture_listeners=self.loopback, fixture_mtime=1).returncode, 0
            )
        with self.subTest(case="grafana without source filter"):
            self.assertNotEqual(
                self.check(fixture_listeners=self.loopback, fixture_ip_deny="").returncode, 0
            )
        with self.subTest(case="inactive grafana"):
            states = ["active", "active", "inactive", "active"]
            self.assertNotEqual(
                self.check(fixture_listeners=self.loopback, fixture_states=states).returncode, 0
            )


class ArtifactTest(unittest.TestCase):
    def test_vendored_grafana_key_matches_pinned_fingerprint(self):
        if not shutil.which("gpg"):
            self.skipTest("gpg unavailable")
        vars_text = (ROLE / "vars" / "main.yml").read_text()
        pinned = re.search(r"monitoring_grafana_key_fingerprint: (\w+)", vars_text).group(1)
        with tempfile.TemporaryDirectory() as home:
            listing = subprocess.run(
                ["gpg", "--homedir", home, "--batch", "--show-keys", "--with-colons",
                 str(ROLE / "files" / "grafana-apt.asc")],
                capture_output=True, text=True, check=True,
            ).stdout
        self.assertIn(f"fpr:::::::::{pinned}:", listing.splitlines())

    def dashboards(self):
        paths = sorted((ROLE / "files" / "dashboards").glob("*.json"))
        self.assertGreaterEqual(len(paths), 2)
        return {path.name: json.loads(path.read_text()) for path in paths}

    def test_dashboards_have_unique_uids_and_are_cross_linked(self):
        dashboards = self.dashboards()
        uids = [dashboard["uid"] for dashboard in dashboards.values()]
        self.assertEqual(len(uids), len(set(uids)))
        self.assertIn("aegisops-fail2ban", uids)
        for name, dashboard in dashboards.items():
            with self.subTest(dashboard=name):
                self.assertIn("aegisops", dashboard["tags"])
                self.assertTrue(any(link.get("tags") == ["aegisops"] for link in dashboard["links"]))

    def test_dashboards_use_only_the_local_datasource(self):
        def walk(node):
            if isinstance(node, dict):
                if isinstance(node.get("datasource"), dict):
                    self.assertEqual(node["datasource"].get("uid"), "aegisops-prometheus")
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        for name, dashboard in self.dashboards().items():
            with self.subTest(dashboard=name):
                walk(dashboard)
                urls = re.findall(r"https?://[^\s\"')]+", json.dumps(dashboard))
                self.assertTrue(all(url.startswith("http://127.0.0.1") for url in urls), urls)

    def test_panels_fit_the_grid_without_overlapping(self):
        for name, dashboard in self.dashboards().items():
            with self.subTest(dashboard=name):
                panels = dashboard["panels"]
                ids = [panel["id"] for panel in panels]
                self.assertEqual(len(ids), len(set(ids)))
                boxes = []
                for panel in panels:
                    grid = panel["gridPos"]
                    self.assertLessEqual(grid["x"] + grid["w"], 24, panel["title"])
                    for other, box in boxes:
                        overlap = (grid["x"] < box["x"] + box["w"] and box["x"] < grid["x"] + grid["w"]
                                   and grid["y"] < box["y"] + box["h"] and box["y"] < grid["y"] + grid["h"])
                        self.assertFalse(overlap, f"{panel['title']} overlaps {other}")
                    boxes.append((panel["title"], grid))

    def test_dashboards_query_only_metrics_the_collector_exports(self):
        exporter = (ROLE / "files" / "aegisops-security-exporter.py").read_text()
        exported = set(re.findall(r'"(aegisops_[a-z0-9_]+)"', exporter))
        exported |= {f"aegisops_fail2ban_jail_{key}" for key in
                     ("banned_current", "banned_total", "failed_current", "failed_total")}
        for name, dashboard in self.dashboards().items():
            with self.subTest(dashboard=name):
                queries = " ".join(
                    target["expr"] for panel in dashboard["panels"]
                    for target in panel.get("targets", []))
                used = set(re.findall(r"aegisops_[a-z0-9_]+", queries))
                self.assertTrue(used)
                self.assertLessEqual(used, exported)

if __name__ == "__main__":
    unittest.main()
