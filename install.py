"""Plug-and-play installer: copy the plugin into Hermes profile(s) and enable it.

    python install.py --profile mastermind            # one profile
    python install.py --profile mastermind --profile daria
    python install.py --global                        # ~/.hermes (the `default` profile)
    python install.py --profile mastermind --uninstall

Config edit is a minimal text patch of ``plugins.enabled`` with a timestamped backup;
comments in config.yaml are preserved. Nothing is launched, restarted or committed.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

PLUGIN_NAME = "account-usage"
SRC = Path(__file__).resolve().parent / "plugin" / PLUGIN_NAME


def hermes_root() -> Path:
    env = os.environ.get("HERMES_ROOT")
    if env:
        return Path(env)
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "hermes"
    return Path.home() / ".hermes"


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


def install(home: Path, uninstall: bool) -> None:
    dst = home / "plugins" / PLUGIN_NAME
    if uninstall:
        shutil.rmtree(dst, ignore_errors=True)
        print(f"{home.name or home}: removed {dst}; remove '- {PLUGIN_NAME}' from plugins.enabled by hand")
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
    args = ap.parse_args()
    root = hermes_root()
    homes = [root / "profiles" / p for p in args.profile] + ([root] if args.global_ else [])
    if not homes:
        ap.error("give --profile NAME and/or --global")
    for home in homes:
        install(home, args.uninstall)
    print("Restart the profile's gateway/TUI/Desktop so the plugin loads; verify with: hermes -p <profile> usage")


if __name__ == "__main__":
    main()
