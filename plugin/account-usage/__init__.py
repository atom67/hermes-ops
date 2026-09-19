"""account-usage — Hermes plugin: account limits + identity in one call.

Registers
  * agent tool ``account_usage`` (toolset ``account_usage``)
  * CLI ``hermes usage [--provider X] [--all-profiles] [--json]``

Both delegate to :mod:`usage_core`, which wraps the core ``agent.account_usage``
fetchers (the same code behind the ``/usage`` slash command) and adds the
non-secret OAuth identity. Nothing here performs network I/O of its own.
"""
from __future__ import annotations

import importlib.util
import json
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
        "Account limits (session/weekly windows, % used, reset time) and account identity "
        "(email, plan) for the active LLM provider of this profile. Use this instead of "
        "reading source code or auth files when the user asks about quota, limits, remaining "
        "usage, or which account is in use. Set all_profiles=true to list every Hermes profile."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "provider": {
                "type": "string",
                "description": "Provider override: openai-codex, anthropic or openrouter. Default: the profile's model.provider.",
            },
            "all_profiles": {
                "type": "boolean",
                "description": "Report every profile (default + profiles/*) instead of the current one.",
            },
        },
        "required": [],
    },
}


def _tool_handler(args: dict, **_kwargs) -> str:
    args = args or {}
    if args.get("all_profiles"):
        reports = usage_core.all_profiles_reports(args.get("provider"))
        return "\n\n".join(usage_core.render(r) for r in reports)
    return usage_core.render(usage_core.report(args.get("provider")))


def _cli_setup(parser) -> None:
    parser.add_argument("--provider", help="override provider (default: model.provider of the profile)")
    parser.add_argument("--all-profiles", action="store_true", help="one block per profile (default + profiles/*)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")


def _cli_handler(args) -> int:
    reports = (usage_core.all_profiles_reports(args.provider) if args.all_profiles
               else [usage_core.report(args.provider)])
    if args.json:
        print(json.dumps(reports if args.all_profiles else reports[0], ensure_ascii=False, indent=2))
    else:
        print("\n\n".join(usage_core.render(r) for r in reports))
    return 0 if all(not r.get("error") for r in reports) else 1


def register(ctx) -> None:
    ctx.register_tool(
        name="account_usage",
        toolset="account_usage",
        schema=TOOL_SCHEMA,
        handler=_tool_handler,
        description=TOOL_SCHEMA["description"],
        emoji="📊",
    )
    ctx.register_cli_command(
        "usage",
        help="Show account limits + identity for the active provider (current or all profiles)",
        setup_fn=_cli_setup,
        handler_fn=_cli_handler,
        description="Same data as the /usage slash command, callable from scripts and by the agent.",
    )
