"""Optional quota/auth watchdog for Hermes cron (--no-agent).

Prints ONLY when a threshold is breached (cron delivers non-empty stdout), and at
most once per breach-set per day, so a low balance does not spam every hour.
Thresholds come from plugins.entries.account-usage.settings (see install.py).

Installed by install.py into <HERMES_HOME>/scripts/quota_watch.py; the plugin
module is loaded from <HERMES_HOME>/plugins/account-usage/usage_core.py.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

STATE_FILE = "quota_watch_state.json"
REPEAT_AFTER_SECONDS = 24 * 3600


def _home() -> Path:
    try:
        from hermes_constants import get_hermes_home
        return Path(get_hermes_home())
    except Exception:
        return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")


def _core(home: Path):
    path = home / "plugins" / "account-usage" / "usage_core.py"
    spec = importlib.util.spec_from_file_location("account_usage_core", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def main() -> int:
    home = _home()
    uc = _core(home)
    settings = uc.load_settings()
    scope = "profile" if str(settings.get("watch_scope") or "all").lower() == "profile" else "all"
    reports = [uc.report(days=settings["days"])] if scope == "profile" \
        else uc.dedupe(uc.all_profiles_reports(days=settings["days"]))
    top = settings.get("watch_top") or uc.DEFAULT_WATCH_TOP[scope]
    targets = set(uc.watch_targets(reports, top))
    alerts = sorted(f"{r.get('profile')}/{line}" for r in reports for b in (r.get("providers") or [])
                    if b["provider"] in targets for line in uc.breaches(b, settings))
    state_path = home / "state" / STATE_FILE
    state = {}
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    if not alerts:
        if state.get("alerts"):
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps({"alerts": [], "sent_at": time.time()}), encoding="utf-8")
            print("✅ quota watch: all clear again")
        return 0
    same = alerts == state.get("alerts") and time.time() - float(state.get("sent_at", 0)) < REPEAT_AFTER_SECONDS
    if same:
        return 0  # already reported today — stay silent
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"alerts": alerts, "sent_at": time.time()}), encoding="utf-8")
    print(f"⚠ Quota watch ({scope}, top {top}: {', '.join(sorted(targets))}) — " + time.strftime("%Y-%m-%d %H:%M"))
    for line in alerts:
        print("• " + line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
