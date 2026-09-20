"""Account limits, balances and spend across Hermes profiles — one report.

Pure functions (testable without Hermes) at the top; Hermes-backed collectors
below, all fail-soft: any error becomes a reason string, never an exception.
Tokens are never returned — only non-secret JWT claims (email, plan, account id).

Provider kinds
  windows  packaged limit with reset windows (Codex/ChatGPT Plus, Anthropic Max)
  balance  prepaid remaining amount (OpenRouter / Nous credits)
  spend    pay-as-you-go without a remote balance: local spend from state.db
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

IDENTITY_KEYS = ("email", "email_verified", "name", "chatgpt_plan_type", "plan_type", "chatgpt_account_id")
BALANCE_PROVIDERS = {"openrouter", "nous"}
AUX_PROVIDERS = {"", "auto"}          # title generation etc. — not a real billing provider
PROFILE_TIMEOUT_SECONDS = 40
DEFAULT_DAYS = 7
PLUGIN_ID = "account-usage"
DEFAULT_SETTINGS = {"days": DEFAULT_DAYS, "weekly_min_percent": 15, "session_min_percent": 10,
                    "balance_min_usd": 5.0, "balance_min": {}, "budget_usd": None,
                    "watch_scope": "all", "watch_top": None}
# balance_min: per-provider floor in the unit the provider reports (USD or credits), e.g. {"nous": 100}.
# watch_scope: "profile" (this profile's top channels) | "all" (top channels across every profile).
# watch_top: how many most-used providers the watchdog follows; None = default per scope; "all" = every one.
DEFAULT_WATCH_TOP = {"profile": 2, "all": 4}


# ---------------------------------------------------------------- pure helpers
def jwt_claims(token: str) -> Dict[str, Any]:
    """Decode a JWT payload WITHOUT verification. Returns {} for non-JWT input."""
    parts = str(token or "").split(".")
    if len(parts) != 3:
        return {}
    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def pick_identity(claims: Dict[str, Any]) -> Dict[str, Any]:
    """Collect identity claims from a nested dict (OpenAI namespaces them under URL keys)."""
    found: Dict[str, Any] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in IDENTITY_KEYS and key not in found and isinstance(value, (str, bool, int)):
                    found[key] = value
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(claims)
    return found


def find_jwts(node: Any, _out: Optional[List[str]] = None) -> List[str]:
    """Return every JWT-looking string inside a nested structure (never logged)."""
    out = [] if _out is None else _out
    if isinstance(node, str):
        if node.count(".") == 2 and jwt_claims(node):
            out.append(node)
    elif isinstance(node, dict):
        for value in node.values():
            find_jwts(value, out)
    elif isinstance(node, list):
        for item in node:
            find_jwts(item, out)
    return out


def snapshot_to_dict(snapshot: Any) -> Dict[str, Any]:
    """AccountUsageSnapshot (dataclass) -> plain dict with ISO dates."""
    if snapshot is None:
        return {"available": False, "unavailable_reason": "no snapshot"}
    data = asdict(snapshot) if is_dataclass(snapshot) else dict(snapshot)
    for window in data.get("windows") or []:
        reset_at = window.get("reset_at")
        if isinstance(reset_at, datetime):
            window["reset_at"] = reset_at.isoformat()
    fetched = data.get("fetched_at")
    if isinstance(fetched, datetime):
        data["fetched_at"] = fetched.isoformat()
    data["available"] = bool(data.get("windows") or data.get("details")) and not data.get("unavailable_reason")
    return data


BALANCE_RE = re.compile(r"(?:balance|total usable)[^$\n]*\$\s*([\d][\d,]*(?:\.\d+)?)", re.I)


def extract_balance(usage: Dict[str, Any]) -> Optional[float]:
    """Prepaid remaining amount in USD from the host's rendered lines/details, if any."""
    for line in list(usage.get("lines") or []) + list(usage.get("details") or []):
        m = BALANCE_RE.search(str(line))
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                continue
    return None


def cost_label(billing_mode: str, actual_usd: float, estimated_usd: float) -> str:
    """How to read the spend number: actual invoice, subscription, estimate, or unknown."""
    if actual_usd > 0:
        return "actual"
    if billing_mode in {"subscription_included", "codex_responses"}:
        return "included in subscription"
    if estimated_usd > 0:
        return "estimate, local accounting"
    return "no pricing data"


def spend_text(act: Dict[str, Any]) -> str:
    source = act.get("cost_source") or "no pricing data"
    spend = act.get("spend_usd") or 0.0
    if source == "actual":
        return f"${spend:.2f} (actual)"
    if source == "included in subscription":
        return "included in subscription"
    if source == "estimate, local accounting":
        return f"≈${spend:.2f} (estimate, local accounting)"
    return "cost n/a (no pricing data)"


def classify(provider: str, usage: Dict[str, Any], billing_mode: str = "") -> str:
    """windows | balance | spend — what kind of number this provider can give us.
    codex_responses = OAuth subscription routed through the Codex responses API (e.g. xai-oauth)."""
    if usage.get("windows") or billing_mode in {"subscription_included", "codex_responses"}:
        return "windows"
    if provider in BALANCE_PROVIDERS or usage.get("details"):
        return "balance"
    return "spend"


def breaches(block: Dict[str, Any], settings: Dict[str, Any]) -> List[str]:
    """Threshold violations for one provider block, as human lines. Pure."""
    out: List[str] = []
    if block.get("same_as"):
        return out  # identical account already checked under another profile
    usage = block.get("usage") or {}
    kind = block.get("kind")
    if usage.get("unavailable_reason") and kind != "spend" and not usage.get("not_fetchable"):
        out.append(f"{block['provider']}: limits unavailable ({usage['unavailable_reason']})")
    if kind == "windows":
        for w in usage.get("windows") or []:
            used = w.get("used_percent")
            if used is None:
                continue
            label = str(w.get("label") or "")
            floor = settings["weekly_min_percent"] if "week" in label.lower() else settings["session_min_percent"]
            if 100 - float(used) < float(floor):
                out.append(f"{block['provider']} {label}: {100 - float(used):.0f}% remaining (< {floor}%)")
    if kind != "spend":
        bal = usage.get("balance_usd")
        floor = (settings.get("balance_min") or {}).get(block["provider"], settings["balance_min_usd"])
        if bal is not None and float(bal) < float(floor):
            out.append(f"{block['provider']}: balance ${float(bal):.2f} (< ${floor})")
    if kind == "spend":
        budget = settings.get("budget_usd")
        spent = (block.get("activity") or {}).get("spend_usd")
        if budget and spent is not None and float(spent) > float(budget):
            out.append(f"{block['provider']}: spend ${float(spent):.2f} over {settings['days']}d (> ${budget})")
    return out


def _quota_signature(block: Dict[str, Any]) -> Optional[str]:
    """Same provider + same remote numbers = same account; None when there is nothing remote to compare."""
    ident = block.get("identity") or {}
    who = ident.get("chatgpt_account_id") or ident.get("email")
    if who:
        return json.dumps([block.get("provider"), who])  # a known account id is the whole story
    usage = block.get("usage") or {}
    # ponytail: no identity -> compare the numbers only; rendered lines carry "resets in 43m" and drift between fetches
    remote = {"windows": [(w.get("label"), w.get("used_percent")) for w in usage.get("windows") or []],
              "balance": usage.get("balance_usd"), "details": usage.get("details")}
    if not any(remote.values()):
        return None
    return json.dumps([block.get("provider"), remote], sort_keys=True, default=str)


def dedupe(reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Mark provider blocks whose quota is identical to one shown earlier: ``same_as = <profile>``.
    Activity stays per profile; only the remote numbers are shared. Returns new reports."""
    seen: Dict[str, str] = {}
    out = []
    for r in reports:
        blocks = []
        for b in r.get("providers") or []:
            sig = _quota_signature(b)
            if sig and sig in seen:
                blocks.append({**b, "same_as": seen[sig]})
            else:
                if sig:
                    seen[sig] = str(r.get("profile"))
                blocks.append(b)
        out.append({**r, "providers": blocks})
    return out


def watch_targets(reports: List[Dict[str, Any]], top: Any) -> List[str]:
    """Providers ranked by calls across the given reports; the first ``top`` of them.
    ``"all"``/None = every provider, including idle ones; a number = only providers used in the window."""
    calls: Dict[str, int] = {}
    for r in reports:
        for b in r.get("providers") or []:
            calls[b["provider"]] = calls.get(b["provider"], 0) + int((b.get("activity") or {}).get("calls") or 0)
    ranked = sorted(calls, key=lambda p: -calls[p])
    if top in (None, "all", "", 0):
        return ranked
    return [p for p in ranked if calls[p] > 0][: int(top)]


def render_block(block: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    identity = block.get("identity") or {}
    head = f"{block.get('provider')} [{block.get('kind')}]"
    if identity:
        who = identity.get("email") or identity.get("name") or "?"
        plan = identity.get("chatgpt_plan_type") or identity.get("plan_type")
        head += f" · {who}" + (f" ({plan})" if plan else "")
    lines.append(head)
    usage = block.get("usage") or {}
    if block.get("same_as"):
        lines.append(f"  same account as profile '{block['same_as']}' — limits shown there")
    elif usage.get("lines"):
        lines.extend("  " + str(line) for line in usage["lines"])
    elif usage.get("available"):
        for w in usage.get("windows") or []:
            lines.append(f"  {w.get('label')}: {w.get('used_percent')}% used · resets {w.get('reset_at')}")
    elif block.get("kind") == "spend":
        lines.append("  no remote balance for this provider — local accounting only")
    else:
        lines.append(f"  limits: unavailable ({usage.get('unavailable_reason') or 'unknown'})")
    act = block.get("activity") or {}
    if act:
        lines.append(f"  last {act.get('days')}d: {act.get('calls')} calls · {spend_text(act)}")
        models = act.get("models") or {}
        if isinstance(models, dict):
            for name, m in sorted(models.items(), key=lambda kv: -kv[1].get("calls", 0)):
                usd = m.get("usd") or 0.0
                lines.append(f"    {name}: {m.get('calls')} calls" + (f", ≈${usd:.2f}" if usd > 0 else ""))
    return lines


def render(report: Dict[str, Any]) -> str:
    """Human/agent-readable text for one profile report."""
    lines = [f"Profile: {report.get('profile') or '-'}"]
    for block in report.get("providers") or []:
        lines.extend(render_block(block))
    if not report.get("providers"):
        lines.append("  no provider configured and no activity")
    if report.get("error"):
        lines.append(f"  Error: {report['error']}")
    return "\n".join(lines)


def render_all(reports: List[Dict[str, Any]], settings: Optional[Dict[str, Any]] = None) -> str:
    settings = settings or DEFAULT_SETTINGS
    reports = dedupe(reports)
    alerts = [f"{r.get('profile')}/{line}" for r in reports for b in (r.get("providers") or [])
              for line in breaches(b, settings)]
    head = [f"Account usage — {len(reports)} profile(s)" + (f" · {len(alerts)} alert(s)" if alerts else " · no alerts")]
    head += ["  ⚠ " + a for a in alerts]
    return "\n".join(head) + "\n\n" + "\n\n".join(render(r) for r in reports)


# ---------------------------------------------------------- Hermes collectors
def hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home
        return Path(get_hermes_home())
    except Exception:
        return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")


def profile_name(home: Optional[Path] = None) -> str:
    home = home or hermes_home()
    return home.name if home.parent.name == "profiles" else "default"


def hermes_root(home: Optional[Path] = None) -> Path:
    """Root that holds ``profiles/``: the parent of a profile home, or the home itself."""
    home = home or hermes_home()
    return home.parent.parent if home.parent.name == "profiles" else home


def load_settings() -> Dict[str, Any]:
    """plugins.entries.account-usage.settings.* over defaults."""
    out = dict(DEFAULT_SETTINGS)
    try:
        from hermes_cli.config import load_config
        entry = ((load_config().get("plugins") or {}).get("entries") or {}).get(PLUGIN_ID) or {}
        for k, v in (entry.get("settings") or {}).items():
            if k in out:
                out[k] = v
    except Exception:
        pass
    return out


def active_provider() -> Optional[str]:
    try:
        from hermes_cli.config import load_config
        return str((load_config().get("model") or {}).get("provider") or "").strip() or None
    except Exception:
        return None


def activity(days: int = DEFAULT_DAYS, home: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """Providers used in the last N days, from the profile's state.db (read-only).
    ponytail: one aggregate query; no per-day breakdown until someone asks for a trend."""
    db = (home or hermes_home()) / "state.db"
    if not db.exists():
        return {}
    cutoff = time.time() - days * 86400
    out: Dict[str, Dict[str, Any]] = {}
    try:
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        rows = con.execute(
            "SELECT billing_provider, model, billing_mode, SUM(api_call_count), "
            "SUM(COALESCE(actual_cost_usd,0)), SUM(COALESCE(estimated_cost_usd,0)), MAX(last_seen) "
            "FROM session_model_usage WHERE last_seen > ? GROUP BY 1,2,3", (cutoff,)).fetchall()
        con.close()
    except Exception:
        return {}
    for provider, model, mode, calls, actual, estimated, last in rows:
        if provider in AUX_PROVIDERS:
            continue
        cur = out.setdefault(provider, {"days": days, "calls": 0, "models": {}, "billing_mode": mode or "",
                                        "actual_usd": 0.0, "estimated_usd": 0.0, "last_seen": 0.0})
        m = cur["models"].setdefault(model, {"calls": 0, "usd": 0.0})
        m["calls"] += int(calls or 0)
        m["usd"] += float(actual or 0) or float(estimated or 0)
        cur["calls"] += int(calls or 0)
        cur["actual_usd"] += float(actual or 0)
        cur["estimated_usd"] += float(estimated or 0)
        cur["last_seen"] = max(cur["last_seen"], float(last or 0))
        if mode in {"subscription_included", "codex_responses"}:
            cur["billing_mode"] = mode
    for cur in out.values():
        cur["spend_usd"] = cur["actual_usd"] if cur["actual_usd"] > 0 else cur["estimated_usd"]
        cur["cost_source"] = cost_label(cur["billing_mode"], cur["actual_usd"], cur["estimated_usd"])
        cur["last_seen"] = datetime.fromtimestamp(cur["last_seen"]).isoformat(timespec="minutes")
    return out


def codex_identity() -> Dict[str, Any]:
    """Non-secret claims from the Codex OAuth tokens of the current profile."""
    sources: List[Any] = []
    for mod, fn, kw in (("hermes_cli.auth", "_read_codex_tokens", {}),
                        ("hermes_cli.auth", "resolve_codex_runtime_credentials", {"refresh_if_expiring": False})):
        try:
            sources.append(getattr(__import__(mod, fromlist=[fn]), fn)(**kw))
        except Exception:
            pass
    for token in find_jwts(sources):
        identity = pick_identity(jwt_claims(token))
        if identity:
            return identity
    return {}


XAI_BILLING_URL = "https://cli-chat-proxy.grok.com/v1/billing?format=credits"   # what the official grok-cli calls
XAI_BILLING_HEADERS = {"X-XAI-Token-Auth": "xai-grok-cli", "Accept": "application/json"}


def xai_windows(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Grok billing JSON -> our usage dict (windows + lines). Pure; see tests."""
    cfg = payload.get("config") if isinstance(payload.get("config"), dict) else payload
    used = cfg.get("creditUsagePercent")
    period = cfg.get("currentPeriod") or {}
    label = str(period.get("type") or "").replace("USAGE_PERIOD_TYPE_", "").title() or "Period"
    windows = [{"label": label, "used_percent": float(used), "reset_at": period.get("end")}] if used is not None else []
    lines = ["📈 Account limits", "Provider: xai-oauth (Grok, via cli-chat-proxy billing)"]
    for w in windows:
        lines.append(f"{w['label']}: {100 - w['used_percent']:.0f}% remaining ({w['used_percent']:.0f}% used) • resets {str(w['reset_at'])[:16]}")
    for item in cfg.get("productUsage") or []:
        if item.get("product") and item.get("usagePercent") is not None:
            lines.append(f"  {item['product']}: {float(item['usagePercent']):.0f}% used")
    prepaid = (cfg.get("prepaidBalance") or {}).get("val")
    if prepaid:
        lines.append(f"Prepaid balance: ${float(prepaid):.2f}")
    return {"available": bool(windows), "windows": windows, "lines": lines, "details": [],
            "unavailable_reason": None if windows else "no creditUsagePercent in billing response"}


def usage_for_xai() -> Dict[str, Any]:
    """xai-oauth has no fetcher in core (upstream PR #114949 open); the stored OAuth bearer works on grok-cli's billing proxy."""
    import urllib.request
    from hermes_cli.auth import resolve_xai_oauth_runtime_credentials
    creds = resolve_xai_oauth_runtime_credentials() or {}
    token = creds.get("api_key") or creds.get("access_token")
    if not token:
        return {"available": False, "unavailable_reason": "no xai-oauth token (hermes auth login xai-oauth)"}
    req = urllib.request.Request(XAI_BILLING_URL, headers={**XAI_BILLING_HEADERS, "Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return xai_windows(json.loads(r.read()))


def usage_for(provider: str) -> Dict[str, Any]:
    try:
        if provider == "xai-oauth":
            return usage_for_xai()
        from agent.account_usage import fetch_account_usage, render_account_usage_lines
        if provider == "nous":
            from agent.account_usage import nous_credits_lines
            lines = nous_credits_lines()
            return {"available": bool(lines), "lines": lines, "details": lines,
                    "unavailable_reason": None if lines else "no Nous credits data"}
        snapshot = fetch_account_usage(provider)
        data = snapshot_to_dict(snapshot)
        data["lines"] = render_account_usage_lines(snapshot) if snapshot else []
        if not snapshot:
            data["unavailable_reason"] = f"no account-usage fetcher for '{provider}' in this Hermes version"
        return data
    except Exception as exc:  # fail soft
        return {"available": False, "unavailable_reason": f"{type(exc).__name__}: {exc}"}


def provider_block(provider: str, act: Dict[str, Any]) -> Dict[str, Any]:
    usage = usage_for(provider)
    usage["balance_usd"] = extract_balance(usage)
    block = {"provider": provider, "identity": codex_identity() if provider == "openai-codex" else {},
             "usage": usage, "activity": act, "kind": classify(provider, usage, act.get("billing_mode", ""))}
    if block["kind"] == "spend":
        block["usage"]["unavailable_reason"] = None
    elif block["kind"] == "windows" and not usage.get("windows") and not usage.get("details"):
        block["usage"]["unavailable_reason"] = f"limits not fetchable for '{provider}' in this Hermes version"
        block["usage"]["not_fetchable"] = True  # capability gap, not an alert
    return block


def report(provider: Optional[str] = None, days: Optional[int] = None) -> Dict[str, Any]:
    """Current profile: the configured provider plus every provider active in the last N days."""
    settings = load_settings()
    days = int(days or settings["days"])
    act = activity(days)
    primary = (provider or active_provider() or "").strip()
    providers = ([primary] if primary else []) + [p for p in act if p != primary]
    out: Dict[str, Any] = {"profile": profile_name(), "primary": primary or None, "days": days,
                           "providers": [provider_block(p, act.get(p, {})) for p in providers]}
    if not providers:
        out["error"] = "no provider configured (model.provider) and no activity"
    return out


def _hermes_agent_dir() -> Path:
    try:
        import agent  # noqa: F401 — package of the running Hermes install
        return Path(agent.__file__).resolve().parent.parent
    except Exception:
        return Path.cwd()


def all_profiles_reports(provider: Optional[str] = None, days: Optional[int] = None,
                         only: Optional[str] = None) -> List[Dict[str, Any]]:
    """One report per profile home (default + profiles/*), each in a subprocess with its own HERMES_HOME.
    ponytail: sequential; parallelise past ~10 profiles."""
    root = hermes_root()
    homes = [root] + sorted(p for p in (root / "profiles").glob("*") if (p / "config.yaml").exists())
    if only:
        homes = [h for h in homes if profile_name(h) == only]
    agent_dir = _hermes_agent_dir()
    reports = []
    for home in homes:
        env = dict(os.environ, HERMES_HOME=str(home), PYTHONPATH=str(agent_dir), PYTHONIOENCODING="utf-8")
        cmd = [sys.executable, str(Path(__file__).resolve()), "--local", "--json"]
        cmd += ["--provider", provider] if provider else []
        cmd += ["--days", str(days)] if days else []
        try:
            proc = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8",
                                  timeout=PROFILE_TIMEOUT_SECONDS)
            try:
                reports.append(json.loads(proc.stdout))  # a child error still comes back as a report
            except Exception:
                reports.append({"profile": profile_name(home), "providers": [],
                                "error": (proc.stderr or proc.stdout).strip()[-300:] or f"exit {proc.returncode}"})
        except Exception as exc:
            reports.append({"profile": profile_name(home), "providers": [], "error": f"{type(exc).__name__}: {exc}"})
    return reports


def run(scope: str = "all", provider: Optional[str] = None, days: Optional[int] = None, as_json: bool = False) -> str:
    """scope: 'all' | 'local' | '<profile name>'."""
    scope = (scope or "all").strip().lower()
    if scope == "local":
        reports = [report(provider, days)]
    else:
        reports = all_profiles_reports(provider, days, only=None if scope == "all" else scope)
        if not reports:
            reports = [{"profile": scope, "providers": [], "error": "no such profile"}]
        reports = dedupe(reports)
    if as_json:
        return json.dumps(reports[0] if scope == "local" else reports, ensure_ascii=False, indent=2)
    return render(reports[0]) if scope == "local" else render_all(reports, load_settings())


# -------------------------------------------------------------------- CLI
def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Account limits, balances and spend across profiles.")
    parser.add_argument("--local", action="store_true", help="current profile only (default: all profiles)")
    parser.add_argument("--profile", help="one named profile")
    parser.add_argument("--provider", help="override the primary provider")
    parser.add_argument("--days", type=int, help=f"activity window (default {DEFAULT_DAYS})")
    parser.add_argument("--json", action="store_true")
    a = parser.parse_args(argv)
    scope = "local" if a.local else (a.profile or "all")
    text = run(scope, a.provider, a.days, a.json)
    print(text)
    return 1 if '"error"' in text or "Error:" in text else 0


if __name__ == "__main__":
    sys.exit(main())
