"""Local tests for the WireGuard role and the VPN access mode of monitoring."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SERVER_KEY = "yAnz5TF+lXXJte14tji3zlMNq+hd2rYUIgJBgB3fBmk="
PC_KEY = "xTIBA5rboUvnH4htodjb6e697QjLERt1NAB4mZqp8Dg="
PHONE_KEY = "TrMvSoP4jYQlY6RIzBgbssQqY3vxI2Pi+y71lOWWXX0="
PRIVATE_KEY = "gI6EdUSYvn8ugXOt8QQD6Yc+JyiZxIhp3GInSWRfWGE="
PEERS = [
    {"name": "pc-linux", "address": "10.66.66.2", "public_key": PC_KEY},
    {"name": "phone", "address": "10.66.66.3", "public_key": PHONE_KEY},
]
K3S_ROUTES = (
    "default via 203.0.113.1 dev ens18 proto static\n"
    "10.42.0.0/24 dev cni0 proto kernel scope link src 10.42.0.1\n"
    "10.66.66.0/24 dev wg0 proto kernel scope link src 10.66.66.1\n"
    "203.0.113.0/24 dev ens18 proto kernel scope link src 203.0.113.10\n"
)


def run_playbook(playbook, variables, inventory="localhost,"):
    with tempfile.TemporaryDirectory(prefix="aegisops-wireguard-") as temp:
        env = os.environ.copy()
        env["ANSIBLE_LOCAL_TEMP"] = str(Path(temp) / "ansible")
        env["ANSIBLE_REMOTE_TEMP"] = str(Path(temp) / "remote")
        env["XDG_CACHE_HOME"] = str(Path(temp) / "cache")
        return subprocess.run(
            ["ansible-playbook", "-i", inventory, playbook, "-e", json.dumps(variables)],
            cwd=ROOT, env=env, capture_output=True, text=True, check=False,
        )


class PreflightTest(unittest.TestCase):
    valid = {
        "wireguard_approved_host": "my-vps",
        "wireguard_admin_user": "aegisadmin",
        "wireguard_ufw_rule_confirmed": True,
        "wireguard_peers": PEERS,
        "fixture_routes": K3S_ROUTES,
    }

    def preflight(self, **overrides):
        variables = dict(self.valid)
        variables.update(overrides)
        return run_playbook("tests/wireguard/preflight.yml", variables, "my-vps,")

    def test_valid_configuration_passes_without_changes(self):
        result = self.preflight()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("changed=0", result.stdout)

    def test_guards_reject_unsafe_or_inconsistent_inputs(self):
        def peer(**change):
            return [dict(PEERS[0], **change), PEERS[1]]

        cases = {
            "unapproved host": {"wireguard_approved_host": "other"},
            "firewall rule not confirmed": {"wireguard_ufw_rule_confirmed": False},
            "root admin": {"wireguard_admin_user": "root"},
            "no peer": {"wireguard_peers": []},
            "privileged port": {"wireguard_port": 500},
            "bad key": {"wireguard_peers": peer(public_key="not-a-key")},
            "bad name": {"wireguard_peers": peer(name="PC Linux")},
            "extra field": {"wireguard_peers": peer(private_key=PRIVATE_KEY)},
            "duplicate address": {"wireguard_peers": peer(address="10.66.66.3")},
            "duplicate key": {"wireguard_peers": peer(public_key=PHONE_KEY)},
            "server address reused": {"wireguard_peers": peer(address="10.66.66.1")},
            "address outside network": {"wireguard_peers": peer(address="10.67.0.2")},
            "broadcast address": {"wireguard_peers": peer(address="10.66.66.255")},
            "public network": {"wireguard_network": "8.8.8.0/24",
                               "wireguard_server_address": "8.8.8.1"},
            "overlaps K3s": {"wireguard_network": "10.42.0.0/16",
                             "wireguard_server_address": "10.42.200.1",
                             "wireguard_peers": [dict(PEERS[0], address="10.42.200.2")]},
            "unsupported release": {"fixture_distribution_version": "20.04"},
            "K3s service range without route": {
                "wireguard_network": "10.43.5.0/24", "wireguard_server_address": "10.43.5.1",
                "wireguard_peers": [dict(PEERS[0], address="10.43.5.2")]},
            "route on a similarly named interface": {
                "fixture_routes": "10.66.66.0/24 dev wg01 proto kernel scope link\n"},
            "endpoint injection": {"wireguard_endpoint": "203.0.113.10\nPostUp = id"},
        }
        for name, override in cases.items():
            with self.subTest(case=name):
                result = self.preflight(**override)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("changed=0", result.stdout)


class TemplateTest(unittest.TestCase):
    def render(self, directory):
        result = run_playbook("tests/wireguard/render.yml", {
            "output_dir": directory,
            "wireguard_peers": PEERS,
            "fixture_server_key": SERVER_KEY,
            "fixture_client_key": PRIVATE_KEY,
        })
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return {path.name: path.read_text() for path in Path(directory).iterdir()}

    def test_server_configuration_never_contains_a_private_key(self):
        with tempfile.TemporaryDirectory() as directory:
            server = self.render(directory)["wg0.conf"]
        self.assertNotIn("PrivateKey", server)
        self.assertIn("PostUp = wg set %i private-key /etc/wireguard/server.key", server)
        self.assertIn("PostUp = sysctl -qw net.ipv4.conf.%i.forwarding=0", server)
        confine = "-t raw {} PREROUTING -i %i ! -d 10.66.66.1/32 -j DROP"
        self.assertIn("PostUp = iptables " + confine.format("-I"), server)
        self.assertIn("PreDown = iptables " + confine.format("-D"), server)
        self.assertIn("MTU = 1280", server)
        self.assertIn("Address = 10.66.66.1/24", server)
        self.assertIn("ListenPort = 51820", server)
        self.assertIn(f"PublicKey = {PC_KEY}\nAllowedIPs = 10.66.66.2/32", server)
        self.assertIn(f"PublicKey = {PHONE_KEY}\nAllowedIPs = 10.66.66.3/32", server)

    def test_client_only_routes_the_server_address(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.render(directory)["client.conf"]
        self.assertIn(f"PrivateKey = {PRIVATE_KEY}\n", client)
        self.assertIn("Address = 10.66.66.2/32", client)
        self.assertIn(f"PublicKey = {SERVER_KEY}", client)
        self.assertIn("Endpoint = 203.0.113.10:51820", client)
        self.assertIn("AllowedIPs = 10.66.66.1/32\n", client)
        self.assertNotIn("0.0.0.0/0", client)
        self.assertNotIn("DNS", client)
        self.assertNotIn("PersistentKeepalive", client)
        self.assertIn("MTU = 1280", client)


class VerifyAssertTest(unittest.TestCase):
    running = {
        "fixture_server_key": SERVER_KEY,
        "fixture_peers": PEERS,
        "fixture_running_key": SERVER_KEY,
        "fixture_running_port": "51820",
        "fixture_running_allowed": [f"{PHONE_KEY}\t10.66.66.3/32", f"{PC_KEY}\t10.66.66.2/32"],
        "fixture_enabled": "enabled",
        "fixture_forwarding": "0",
        "fixture_confinement_rc": 0,
        "fixture_address": "5: wg0    inet 10.66.66.1/24 scope global wg0",
        "fixture_ufw": ["Status: active", "51820/udp                  ALLOW       Anywhere"],
    }

    def check(self, **overrides):
        variables = dict(self.running)
        variables.update(overrides)
        return run_playbook("tests/wireguard/verify_assert.yml", variables)

    def test_matching_tunnel_passes(self):
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_drift_fails(self):
        cases = {
            "other server key": {"fixture_running_key": PC_KEY},
            "other port": {"fixture_running_port": "51821"},
            "missing address": {"fixture_address": ""},
            "unknown peer": {"fixture_running_allowed": [
                f"{PC_KEY}\t10.66.66.2/32", f"{PHONE_KEY}\t10.66.66.3/32",
                f"{PRIVATE_KEY}\t10.66.66.9/32"]},
            "missing peer": {"fixture_running_allowed": [f"{PC_KEY}\t10.66.66.2/32"]},
            "peer with wider allowed ips": {"fixture_running_allowed": [
                f"{PC_KEY}\t10.66.66.2/32 10.42.0.0/16", f"{PHONE_KEY}\t10.66.66.3/32"]},
            "not enabled at boot": {"fixture_enabled": "disabled"},
            "forwarding on": {"fixture_forwarding": "1"},
            "no confinement rule": {"fixture_confinement_rc": 1},
            "no firewall rule": {"fixture_ufw": ["Status: active"]},
            "rule limited to one source": {"fixture_ufw": [
                "51820/udp                  ALLOW       198.51.100.7"]},
        }
        for name, override in cases.items():
            with self.subTest(case=name):
                self.assertNotEqual(self.check(**override).returncode, 0)


class MonitoringVpnModeTest(unittest.TestCase):
    def test_grafana_binds_the_vpn_address_and_follows_wg0(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_playbook("tests/monitoring/render.yml", {
                "output_dir": directory,
                "monitoring_grafana_admin_password": "Zx9+Qw3/Lp7=Rt5.Kv8_Mn",
                "monitoring_grafana_access": "vpn",
                "wireguard_server_address": "10.66.66.1",
                "wireguard_network": "10.66.66.0/24",
            })
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            rendered = {p.name: p.read_text() for p in Path(directory).iterdir()}
        env = rendered["grafana.env"]
        self.assertIn("GF_SERVER_HTTP_ADDR=10.66.66.1\n", env)
        self.assertIn("GF_SERVER_DOMAIN=10.66.66.1\n", env)
        self.assertIn("GF_SERVER_ENFORCE_DOMAIN=true\n", env)
        unit = rendered["grafana-server.conf"]
        self.assertIn("PartOf=wg-quick@wg0.service", unit)
        self.assertIn("After=wg-quick@wg0.service", unit)
        self.assertIn("IPAddressAllow=localhost 10.66.66.0/24\n", unit)
        self.assertIn("StartLimitIntervalSec=0", unit)
        self.assertIn('targets: ["10.66.66.1:3000"]', rendered["prometheus.yml"])
        self.assertIn("--web.listen-address=127.0.0.1:9090", rendered["prometheus.conf"])

    def test_tunnel_mode_has_no_vpn_dependency(self):
        with tempfile.TemporaryDirectory() as directory:
            run_playbook("tests/monitoring/render.yml", {
                "output_dir": directory,
                "monitoring_grafana_admin_password": "Zx9+Qw3/Lp7=Rt5.Kv8_Mn",
            })
            unit = (Path(directory) / "grafana-server.conf").read_text()
        self.assertNotIn("wg-quick", unit)

    def test_verify_accepts_grafana_only_on_the_vpn_address(self):
        base = ["LISTEN 0 4096 127.0.0.1:9090 0.0.0.0:*",
                "LISTEN 0 4096 127.0.0.1:9100 0.0.0.0:*"]
        vpn = {"monitoring_grafana_access": "vpn", "wireguard_server_address": "10.66.66.1"}
        cases = {
            "vpn address": (base + ["LISTEN 0 4096 10.66.66.1:3000 0.0.0.0:*"], True),
            "loopback in vpn mode": (base + ["LISTEN 0 4096 127.0.0.1:3000 0.0.0.0:*"], False),
            "wildcard": (base + ["LISTEN 0 4096 0.0.0.0:3000 0.0.0.0:*"], False),
        }
        for name, (listeners, accepted) in cases.items():
            with self.subTest(case=name):
                result = run_playbook("tests/monitoring/verify_assert.yml",
                                      dict(vpn, fixture_listeners=listeners))
                self.assertEqual(result.returncode == 0, accepted, result.stdout)


class PeerScriptTest(unittest.TestCase):
    script = ROOT / "scripts" / "aegisops-wg-peer"

    def run_script(self, *args, env=None):
        return subprocess.run([str(self.script), *args], capture_output=True,
                              text=True, check=False, env=env)

    def test_rejects_invalid_names_and_usage(self):
        self.assertNotEqual(self.run_script("new", "../etc").returncode, 0)
        self.assertNotEqual(self.run_script("new").returncode, 0)
        self.assertNotEqual(self.run_script("delete", "pc").returncode, 0)

    @unittest.skipUnless(shutil.which("wg"), "wireguard-tools not installed")
    def test_new_key_is_private_and_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, AEGISOPS_WG_DIR=directory)
            first = self.run_script("new", "pc-linux", env=env)
            second = self.run_script("new", "pc-linux", env=env)
            key = Path(directory) / "peers" / "pc-linux.key"
            self.assertEqual(key.stat().st_mode & 0o777, 0o600)
            self.assertEqual(first.stdout, second.stdout)
            public = (Path(directory) / "peers" / "pc-linux.pub").read_text().strip()
            self.assertIn(public, first.stdout)
            self.assertNotIn(key.read_text().strip(), first.stdout)

    @unittest.skipUnless(shutil.which("wg"), "wireguard-tools not installed")
    def test_empty_key_left_by_a_failed_run_is_regenerated(self):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, AEGISOPS_WG_DIR=directory)
            peers = Path(directory) / "peers"
            peers.mkdir(mode=0o700)
            (peers / "phone.key").write_text("")
            result = self.run_script("new", "phone", env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len((peers / "phone.key").read_text().strip()), 44)
            self.assertIn((peers / "phone.pub").read_text().strip(), result.stdout)


if __name__ == "__main__":
    unittest.main()
