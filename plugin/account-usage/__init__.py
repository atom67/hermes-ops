"""account-usage — Hermes plugin: account limits, balances and spend across profiles.

Registers
  * agent tool ``account_usage(scope, provider?, days?)`` — scope: all | local | <profile>
  * slash command ``/quota [local|all|<profile>]`` (CLI, gateway, Desktop chat)
  * CLI ``hermes usage [--local|--profile NAME] [--provider X] [--days N] [--json]``

All three delegate to :mod:`usage_core`, which wraps the host ``agent.account_usage``
fetchers (same data as ``/usage``), adds non-secret OAuth identity and per-profile
activity from ``state.db`` (read-only). Nothing here performs network I/O of its own.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_CORE_PATH = Path(__file__).with_name("usage_core.py")
_spec = importlib.util.spec_from_file_location("account_usage_core", _CORE_PATH)
usage_core = importlib.util.module_from_spec(_spec)
sys.modules["account_usage_core"] = usage_core
_spec.loader.exec_module(usage_core)  # type: ignore[union-attr]

TOOL_SCHEMA = {
    "name": "account_usage",
    "description": (
        "Account limits / credit balance / local spend and account identity (email, plan) for the "
        "LLM providers used by Hermes. Use it whenever the user asks about quota, limits, remaining "
        "usage, balance, spend, or which account is in use — never read source code or auth files "
        "for that. scope='all' (default) reports every Hermes profile; scope='local' only this "
        "profile; scope='<profile name>' one profile. Providers active in the last N days are "
        "included automatically."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "scope": {"type": "string",
                      "description": "all (default, every profile) | local (this profile only) | a profile name"},
            "provider": {"type": "string", "description": "override the primary provider, e.g. openai-codex"},
            "days": {"type": "integer", "description": "activity window in days (default 7)"},
        },
        "required": [],
    },
}


def _tool_handler(args: dict, **_kwargs) -> str:
    args = args or {}
    return usage_core.run(args.get("scope") or "all", args.get("provider"), args.get("days"))


def _slash_handler(raw_args: str) -> str:
    argv = (raw_args or "").split()
    if argv and argv[0] in {"help", "-h", "--help"}:
        return ("/quota            — all profiles\n/quota local      — this profile only\n"
                "/quota <profile>  — one profile\n/quota ... --days N · --json (machine-readable; used by the Desktop pane)")
    days = None
    if "--days" in argv:
        i = argv.index("--days")
        days = int(argv[i + 1]) if i + 1 < len(argv) else None
        argv = argv[:i] + argv[i + 2:]
    as_json = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    scope = argv[0] if argv else "all"
    return usage_core.run(scope, None, days, as_json)


def _cli_setup(parser) -> None:
    parser.add_argument("--local", action="store_true", help="current profile only (default: all profiles)")
    parser.add_argument("--profile", help="one named profile")
    parser.add_argument("--provider", help="override the primary provider")
    parser.add_argument("--days", type=int, help="activity window in days (default 7)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")


def _cli_handler(args) -> int:
    scope = "local" if args.local else (args.profile or "all")
    text = usage_core.run(scope, args.provider, args.days, args.json)
    print(text)
    return 1 if '"error"' in text or "Error:" in text else 0


def register(ctx) -> None:
    ctx.register_tool(
        name="account_usage",
        toolset="account_usage",
        schema=TOOL_SCHEMA,
        handler=_tool_handler,
        description=TOOL_SCHEMA["description"],
        emoji="📊",
    )
    ctx.register_command(
        "quota",
        handler=_slash_handler,
        description="Account limits, balances and spend: all profiles, local, or one profile",
        args_hint="[local|all|<profile>] [--days N]",
    )
    ctx.register_cli_command(
        "usage",
        help="Account limits, balances and spend across profiles (same data as /usage, plus activity)",
        setup_fn=_cli_setup,
        handler_fn=_cli_handler,
        description="Default: all profiles. --local for this profile, --profile NAME for one.",
    )
