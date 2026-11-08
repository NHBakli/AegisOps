#!/usr/bin/env python3
"""Export AegisOps security state for the node_exporter textfile collector.

The script is read-only: it queries fail2ban-client, ufw and sshd -T, then
atomically writes Prometheus text-format metrics. A failing section is
reported through aegisops_exporter_section_success instead of aborting the
whole export, so one broken source never hides the others.
"""

import argparse
import ipaddress
import os
import re
import subprocess
import sys
import tempfile
import time

COMMAND_TIMEOUT = 15
JAIL_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
SSH_CHECKS = {
    "root_login_disabled": ("permitrootlogin", {"no"}),
    "password_auth_disabled": ("passwordauthentication", {"no"}),
    "pubkey_auth_enabled": ("pubkeyauthentication", {"yes"}),
    "kbd_interactive_disabled": ("kbdinteractiveauthentication", {"no"}),
}


def run(argv):
    """Run a command without a shell and return its stdout."""
    result = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT,
        check=True,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"},
    )
    return result.stdout


def escape_label(value):
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def sample(name, value, labels=None):
    if labels:
        rendered = ",".join(
            f'{key}="{escape_label(str(val))}"' for key, val in labels.items()
        )
        return f"{name}{{{rendered}}} {value}"
    return f"{name} {value}"


def parse_jail_list(text):
    """Return jail names from `fail2ban-client status`."""
    for line in text.splitlines():
        if "Jail list:" in line:
            raw = line.split("Jail list:", 1)[1]
            jails = [item.strip() for item in raw.split(",") if item.strip()]
            return [jail for jail in jails if JAIL_NAME.match(jail)]
    raise ValueError("fail2ban status output has no jail list")


def parse_jail_status(text):
    """Return counters and banned IPs from `fail2ban-client status <jail>`."""
    fields = {
        "Currently failed:": "failed_current",
        "Total failed:": "failed_total",
        "Currently banned:": "banned_current",
        "Total banned:": "banned_total",
    }
    status = {"banned_ips": []}
    for line in text.splitlines():
        for marker, key in fields.items():
            if marker in line:
                status[key] = int(line.split(marker, 1)[1].strip())
        if "Banned IP list:" in line:
            for token in line.split("Banned IP list:", 1)[1].split():
                address = normalise_address(token)
                if address and address not in status["banned_ips"]:
                    status["banned_ips"].append(address)
    missing = [key for key in fields.values() if key not in status]
    if missing:
        raise ValueError(f"fail2ban jail output misses {', '.join(missing)}")
    return status


def normalise_address(token):
    """Return a canonical IP (or CIDR) string, or None for anything else."""
    try:
        return str(ipaddress.ip_address(token))
    except ValueError:
        pass
    try:
        return str(ipaddress.ip_network(token, strict=False))
    except ValueError:
        return None


def parse_ufw_status(text):
    """Return (active, rule_count) from `ufw status`."""
    active = None
    rules = 0
    in_rules = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Status:"):
            active = stripped.split(":", 1)[1].strip() == "active"
        elif stripped.startswith("--"):
            in_rules = True
        elif in_rules and stripped:
            rules += 1
    if active is None:
        raise ValueError("ufw status output has no Status line")
    return active, rules


def parse_sshd_config(text):
    """Return AegisOps SSH compliance flags from `sshd -T` output."""
    effective = {}
    for line in text.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2:
            effective.setdefault(parts[0].lower(), parts[1].strip().lower())
    checks = {}
    for check, (keyword, compliant) in SSH_CHECKS.items():
        if keyword not in effective:
            raise ValueError(f"sshd -T output misses {keyword}")
        checks[check] = 1 if effective[keyword] in compliant else 0
    return checks, effective.get("port", "22").split()[0]


def count_established(text):
    return sum(1 for line in text.splitlines() if line.strip())


def collect_fail2ban(lines, max_ips):
    jails = parse_jail_list(run(["fail2ban-client", "status"]))
    lines.append(sample("aegisops_fail2ban_up", 1))
    for jail in jails:
        status = parse_jail_status(run(["fail2ban-client", "status", jail]))
        for key in ("banned_current", "banned_total", "failed_current", "failed_total"):
            lines.append(sample(f"aegisops_fail2ban_jail_{key}", status[key], {"jail": jail}))
        for address in status["banned_ips"][:max_ips]:
            lines.append(sample("aegisops_fail2ban_banned_ip", 1, {"jail": jail, "ip": address}))
        truncated = 1 if len(status["banned_ips"]) > max_ips else 0
        lines.append(sample("aegisops_fail2ban_banned_ip_truncated", truncated, {"jail": jail}))


def collect_ufw(lines):
    active, rules = parse_ufw_status(run(["ufw", "status"]))
    lines.append(sample("aegisops_ufw_active", 1 if active else 0))
    lines.append(sample("aegisops_ufw_rules", rules))


def collect_ssh(lines):
    checks, port = parse_sshd_config(run(["sshd", "-T"]))
    for check, value in checks.items():
        lines.append(sample("aegisops_ssh_check", value, {"check": check}))
    if not port.isdigit():
        raise ValueError("sshd -T returned a non-numeric port")
    established = run(["ss", "-Htn", "state", "established", f"( sport = :{port} )"])
    lines.append(sample("aegisops_ssh_established_connections", count_established(established)))


def render(max_ips):
    lines = []
    success = {}
    for section, collector in (
        ("fail2ban", lambda: collect_fail2ban(lines, max_ips)),
        ("ufw", lambda: collect_ufw(lines)),
        ("ssh", lambda: collect_ssh(lines)),
    ):
        mark = len(lines)
        try:
            collector()
            success[section] = 1
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            del lines[mark:]
            success[section] = 0
            print(f"aegisops-security-exporter: {section}: {error}", file=sys.stderr)
    if not success["fail2ban"]:
        lines.append(sample("aegisops_fail2ban_up", 0))
    for section, value in success.items():
        lines.append(sample("aegisops_exporter_section_success", value, {"section": section}))
    lines.append(sample("aegisops_exporter_last_run_timestamp_seconds", int(time.time())))
    return format_families(lines)


def metric_name(line):
    return re.split(r"[{ ]", line, maxsplit=1)[0]


def format_families(lines):
    """Group samples by family, each preceded by its TYPE line."""
    output = []
    current = None
    # Prometheus requires all samples of one family to be contiguous.
    for line in sorted(lines, key=metric_name):
        name = metric_name(line)
        if name != current:
            output.append(f"# TYPE {name} gauge")
            current = name
        output.append(line)
    return "\n".join(output) + "\n"


def write_atomically(path, content):
    directory = os.path.dirname(path)
    descriptor, temporary = tempfile.mkstemp(prefix=".aegisops-", dir=directory)
    try:
        with os.fdopen(descriptor, "w") as handle:
            handle.write(content)
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="Destination .prom file")
    parser.add_argument("--max-banned-ips", type=int, default=500)
    args = parser.parse_args(argv)
    if not args.output.endswith(".prom"):
        parser.error("--output must end with .prom")
    write_atomically(args.output, render(max(args.max_banned_ips, 0)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
