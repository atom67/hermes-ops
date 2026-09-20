"""Plug-and-play installer: copy the plugin into Hermes profile(s), enable it, and
optionally set up the quota/auth watchdog.

    python install.py --profile mastermind                       # plugin only
    python install.py --profile mastermind --profile daria
    python install.py --global                                   # ~/.hermes (the `default` profile)
    python install.py --profile mastermind --watchdog 60m --deliver telegram \\
                      --weekly 15 --session 10 --balance-usd 5 --budget-usd 20
    python install.py --profile mastermind --uninstall

After copying, the installer prints the providers seen in the last 7 days across all
profiles (from state.db, read-only) so you know what the report will cover. The
watchdog is OFF unless --watchdog is given; it is a normal Hermes cron job
(--no-agent) delivering only on threshold breach. Thresholds are stored with
``hermes config set plugins.entries.account-usage.settings.<key>``.

Config edit for ``plugins.enabled`` is a minimal text patch with a timestamped backup;
comments in config.yaml are preserved. Nothing is launched, restarted or committed.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PLUGIN_NAME = "account-usage"
SRC = Path(__file__).resolve().parent / "plugin" / PLUGIN_NAME
DESKTOP_SRC = Path(__file__).resolve().parent / "desktop" / PLUGIN_NAME
WATCH_SCRIPT = "quota_watch.py"
JOB_NAME = "quota-watch"
SETTING_KEYS = {"weekly": "weekly_min_percent", "session": "session_min_percent",
                "balance_usd": "balance_min_usd", "budget_usd": "budget_usd", "days": "days",
                "watch_scope": "watch_scope", "watch_top": "watch_top"}


def hermes_root() -> Path:
    env = os.environ.get("HERMES_ROOT")
    if env:
        return Path(env)
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "hermes"
    return Path.home() / ".hermes"


def hermes_bin() -> str:
    exe = "hermes.exe" if sys.platform == "win32" else "hermes"
    cand = Path(sys.executable).with_name(exe)
    return str(cand) if cand.exists() else "hermes"


def hermes(profile: str | None, *args: str) -> subprocess.CompletedProcess:
    cmd = [hermes_bin()] + (["-p", profile] if profile else []) + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=120)


def enable_in_config(config_path: Path, name: str) -> str:
    text = config_path.read_text(encoding="utf-8")
    if re.search(rf"^\s*-\s*{re.escape(name)}\s*$", text, re.M):
        return "already enabled"
    backup = config_path.with_name(f"config.yaml.bak-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}")
    shutil.copy2(config_path, backup)
    m = re.search(r"^plugins:\s*\n((?:[ \t]+.*\n?)*)", text, re.M)
    if not m:
        text = text.rstrip("\n") + f"\nplugins:\n  enabled:\n    - {name}\n"
    else:
        block = m.group(1)
        if re.search(r"^\s+enabled:\s*\[\s*\]\s*$", block, re.M):
            block = re.sub(r"^(\s+)enabled:\s*\[\s*\]\s*$", rf"\1enabled:\n\1  - {name}", block, count=1, flags=re.M)
        elif re.search(r"^\s+enabled:\s*$", block, re.M):
            block = re.sub(r"^(\s+)enabled:\s*$", rf"\1enabled:\n\1  - {name}", block, count=1, flags=re.M)
        else:
            block = f"  enabled:\n    - {name}\n" + block
        text = text[: m.start(1)] + block + text[m.end(1):]
    config_path.write_text(text, encoding="utf-8")
    return f"enabled (backup: {backup.name})"


def load_core():
    spec = importlib.util.spec_from_file_location("account_usage_core", SRC / "usage_core.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def detected_providers(home: Path) -> str:
    """Providers active in the last 7 days across all profiles (state.db, read-only)."""
    try:
        uc = load_core()
        root = uc.hermes_root(home)
        homes = [root] + sorted(p for p in (root / "profiles").glob("*") if (p / "config.yaml").exists())
        lines = []
        for h in homes:
            act = uc.activity(7, h)
            summary = ", ".join(f"{p} ({a['calls']} calls)" for p, a in act.items()) or "no activity"
            lines.append(f"  {uc.profile_name(h)}: {summary}")
        return "\n".join(lines)
    except Exception as exc:
        return f"  (could not read activity: {exc})"


def setup_watchdog(home: Path, profile: str | None, args) -> None:
    for flag, key in SETTING_KEYS.items():
        val = getattr(args, flag, None)
        if val is not None:
            r = hermes(profile, "config", "set", f"plugins.entries.{PLUGIN_NAME}.settings.{key}", str(val), "--force")
            print(f"  setting {key}={val}: {'ok' if r.returncode == 0 else (r.stderr or r.stdout).strip()[-200:]}")
    for item in args.balance_min:  # PROVIDER=AMOUNT, in the unit the provider reports (USD or credits)
        prov, _, amount = item.partition("=")
        r = hermes(profile, "config", "set", f"plugins.entries.{PLUGIN_NAME}.settings.balance_min.{prov.strip()}",
                   amount.strip(), "--force")
        print(f"  balance floor {prov.strip()}={amount.strip()}: {'ok' if r.returncode == 0 else (r.stderr or r.stdout).strip()[-200:]}")
    scripts = home / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC / WATCH_SCRIPT, scripts / WATCH_SCRIPT)
    if JOB_NAME in hermes(profile, "cron", "list").stdout:
        print(f"  cron job '{JOB_NAME}' already exists — not recreated (edit with `hermes cron edit`)")
        return
    every = args.watchdog.strip()
    if re.fullmatch(r"\d+[smhd]", every):
        every = "every " + every  # a bare '60m' is a ONE-SHOT delay in Hermes cron; recurring needs 'every 60m'
    r = hermes(profile, "cron", "create", every, "--name", JOB_NAME, "--script", WATCH_SCRIPT,
               "--no-agent", "--deliver", args.deliver)
    status = "created" if r.returncode == 0 else (r.stderr or r.stdout).strip()[-300:]
    print(f"  cron job '{JOB_NAME}' ({every}), deliver={args.deliver}: {status}")


def install_desktop(home: Path, root: Path, uninstall: bool) -> None:
    """Desktop pane: the app reads <active profile home>/desktop-plugins/ and the root home."""
    for base in {home, root}:
        dst = base / "desktop-plugins" / PLUGIN_NAME
        if uninstall:
            shutil.rmtree(dst, ignore_errors=True)
            continue
        shutil.copytree(DESKTOP_SRC, dst, dirs_exist_ok=True)
        print(f"{base.name or base}: desktop pane copied to {dst} (Settings -> Plugins -> Rescan, or restart Desktop)")


def install(home: Path, uninstall: bool) -> None:
    dst = home / "plugins" / PLUGIN_NAME
    if uninstall:
        shutil.rmtree(dst, ignore_errors=True)
        (home / "scripts" / WATCH_SCRIPT).unlink(missing_ok=True)
        print(f"{home.name or home}: removed {dst} and scripts/{WATCH_SCRIPT}; remove '- {PLUGIN_NAME}' from "
              f"plugins.enabled and the '{JOB_NAME}' cron job by hand")
        return
    if not (home / "config.yaml").exists():
        sys.exit(f"no config.yaml in {home}")
    shutil.copytree(SRC, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    status = enable_in_config(home / "config.yaml", PLUGIN_NAME)
    print(f"{home.name or home}: plugin copied to {dst}; plugins.enabled -> {status}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", action="append", default=[], help="profile name (repeatable)")
    ap.add_argument("--global", dest="global_", action="store_true", help="install into the root hermes home")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--watchdog", metavar="EVERY", help="enable the watchdog cron job, e.g. 60m or '0 * * * *'")
    ap.add_argument("--deliver", default="local", choices=["local", "telegram", "discord", "origin"],
                    help="watchdog delivery target (default local; telegram = push via the profile's bot)")
    ap.add_argument("--weekly", type=int, help="alert when a weekly window has < N%% remaining (default 15)")
    ap.add_argument("--session", type=int, help="alert when a session window has < N%% remaining (default 10)")
    ap.add_argument("--balance-usd", dest="balance_usd", type=float, help="alert when a prepaid balance < $X (default 5)")
    ap.add_argument("--budget-usd", dest="budget_usd", type=float,
                    help="alert when pay-as-you-go spend over the window > $X (off by default)")
    ap.add_argument("--days", type=int, help="activity window in days (default 7)")
    ap.add_argument("--watch-scope", dest="watch_scope", choices=["profile", "all"],
                    help="watchdog follows this profile's top channels or the top channels across all profiles (default all)")
    ap.add_argument("--watch-top", dest="watch_top",
                    help="how many most-used providers the watchdog follows: N or 'all' (default 2 for profile, 4 for all)")
    ap.add_argument("--balance-min", dest="balance_min", action="append", default=[], metavar="PROVIDER=AMOUNT",
                    help="per-provider balance floor in USD or credits, e.g. nous=100 (repeatable)")
    ap.add_argument("--no-desktop", action="store_true", help="skip the Desktop pane (desktop-plugins/)")
    args = ap.parse_args()
    root = hermes_root()
    homes = [root / "profiles" / p for p in args.profile] + ([root] if args.global_ else [])
    if not homes:
        ap.error("give --profile NAME and/or --global")
    for home in homes:
        install(home, args.uninstall)
        if not args.no_desktop:
            install_desktop(home, root, args.uninstall)
        if args.uninstall:
            continue
        profile = home.name if home.parent.name == "profiles" else None
        print("Providers active in the last 7 days (all profiles):")
        print(detected_providers(home))
        if args.watchdog:
            print(f"Watchdog for {profile or 'default'}:")
            setup_watchdog(home, profile, args)
    if not args.uninstall:
        print("Restart the profile's gateway/TUI/Desktop so the plugin loads; verify with: hermes -p <profile> usage")
        if not args.watchdog:
            print("Watchdog not enabled (optional): re-run with --watchdog 60m [--deliver telegram] to add it.")


if __name__ == "__main__":
    main()
