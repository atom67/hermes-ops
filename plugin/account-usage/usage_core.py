"""Account limits + identity for the active provider, as one report.

Pure functions (testable without Hermes) live at the top; the Hermes-backed
collectors are below and fail soft: any error becomes ``unavailable_reason``.
Tokens are never returned — only non-secret JWT claims (email, plan, account id).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

IDENTITY_KEYS = ("email", "email_verified", "name", "chatgpt_plan_type", "plan_type", "chatgpt_account_id")
PROFILE_TIMEOUT_SECONDS = 40


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


def render(report: Dict[str, Any]) -> str:
    """Human/agent-readable block for one profile report."""
    lines = [f"Profile: {report.get('profile') or '-'} · provider: {report.get('provider') or '-'}"]
    identity = report.get("identity") or {}
    if identity:
        who = identity.get("email") or identity.get("name") or "?"
        plan = identity.get("chatgpt_plan_type") or identity.get("plan_type")
        lines.append(f"Account: {who}" + (f" ({plan})" if plan else ""))
    usage = report.get("usage") or {}
    if usage.get("lines"):
        lines.extend(str(line) for line in usage["lines"])
    elif usage.get("available"):
        for window in usage.get("windows") or []:
            used = window.get("used_percent")
            lines.append(f"{window.get('label')}: {used}% used · resets {window.get('reset_at')}")
    else:
        lines.append(f"Limits: unavailable ({usage.get('unavailable_reason') or 'unknown'})")
    if report.get("error"):
        lines.append(f"Error: {report['error']}")
    return "\n".join(lines)


# ---------------------------------------------------------- Hermes collectors
def active_provider() -> Optional[str]:
    try:
        from hermes_cli.config import load_config
        return str((load_config().get("model") or {}).get("provider") or "").strip() or None
    except Exception:
        return None


def profile_name() -> str:
    try:
        from hermes_constants import get_hermes_home
        home = Path(get_hermes_home())
    except Exception:
        home = Path(os.environ.get("HERMES_HOME") or "")
    return home.name if home.parent.name == "profiles" else "default"


def codex_identity() -> Dict[str, Any]:
    """Non-secret claims from the Codex OAuth tokens of the current profile."""
    sources: List[Any] = []
    try:
        from hermes_cli.auth import _read_codex_tokens
        sources.append(_read_codex_tokens())
    except Exception:
        pass
    try:
        from hermes_cli.auth import resolve_codex_runtime_credentials
        sources.append(resolve_codex_runtime_credentials(refresh_if_expiring=False))
    except Exception:
        pass
    for token in find_jwts(sources):
        identity = pick_identity(jwt_claims(token))
        if identity:
            return identity
    return {}


def usage_for(provider: str) -> Dict[str, Any]:
    try:
        from agent.account_usage import fetch_account_usage, render_account_usage_lines
        if provider == "nous":  # credits live behind a separate core helper
            from agent.account_usage import nous_credits_lines
            lines = nous_credits_lines()
            return {"available": bool(lines), "lines": lines, "unavailable_reason": None if lines else "no Nous credits data"}
        snapshot = fetch_account_usage(provider)
        data = snapshot_to_dict(snapshot)
        data["lines"] = render_account_usage_lines(snapshot) if snapshot else []
        if not snapshot:
            data["unavailable_reason"] = f"provider '{provider}' has no account-usage fetcher in this Hermes version"
        return data
    except Exception as exc:  # fail soft: the report still renders
        return {"available": False, "unavailable_reason": f"{type(exc).__name__}: {exc}"}


def report(provider: Optional[str] = None) -> Dict[str, Any]:
    provider = (provider or active_provider() or "").strip()
    out: Dict[str, Any] = {"profile": profile_name(), "provider": provider or None, "identity": {}, "usage": {}}
    if not provider:
        out["error"] = "no provider configured (model.provider)"
        return out
    if provider == "openai-codex":
        out["identity"] = codex_identity()
    out["usage"] = usage_for(provider)
    return out


def hermes_root() -> Path:
    """Root that holds ``profiles/``: the parent of a profile home, or the home itself."""
    try:
        from hermes_constants import get_hermes_home
        home = Path(get_hermes_home())
    except Exception:
        home = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")
    return home.parent.parent if home.parent.name == "profiles" else home


def all_profiles_reports(provider: Optional[str] = None) -> List[Dict[str, Any]]:
    """One report per profile (default + profiles/*), each in a subprocess with its own HERMES_HOME.
    ponytail: sequential subprocesses; parallelise if profile count grows past ~10."""
    root = hermes_root()
    homes = [root] + sorted(p for p in (root / "profiles").glob("*") if (p / "config.yaml").exists())
    agent_dir = _hermes_agent_dir()
    reports = []
    for home in homes:
        env = dict(os.environ, HERMES_HOME=str(home), PYTHONPATH=str(agent_dir), PYTHONIOENCODING="utf-8")
        cmd = [sys.executable, str(Path(__file__).resolve()), "--json"] + (["--provider", provider] if provider else [])
        try:
            proc = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8",
                                  timeout=PROFILE_TIMEOUT_SECONDS)
            reports.append(json.loads(proc.stdout) if proc.returncode == 0 and proc.stdout.strip() else
                           {"profile": home.name, "error": (proc.stderr or proc.stdout).strip()[-300:] or f"exit {proc.returncode}"})
        except Exception as exc:
            reports.append({"profile": home.name, "error": f"{type(exc).__name__}: {exc}"})
    return reports


def _hermes_agent_dir() -> Path:
    try:
        import agent  # noqa: F401 — package of the running Hermes install
        return Path(agent.__file__).resolve().parent.parent
    except Exception:
        return Path.cwd()


# -------------------------------------------------------------------- CLI
def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Account limits + identity for the active provider.")
    parser.add_argument("--provider", help="override provider (default: model.provider of the profile)")
    parser.add_argument("--all-profiles", action="store_true", help="one block per profile (default + profiles/*)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)
    reports = all_profiles_reports(args.provider) if args.all_profiles else [report(args.provider)]
    if args.json:
        print(json.dumps(reports if args.all_profiles else reports[0], ensure_ascii=False, indent=2))
    else:
        print("\n\n".join(render(r) for r in reports))
    return 0 if all(not r.get("error") for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
