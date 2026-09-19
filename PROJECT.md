# Hermes Account Usage Plugin

Project-owned facts. Process: [AGENTS.md](AGENTS.md). Commands:
[project.json](.devframework/project.json), the executable source of truth.

## Product and stack

Users: operators of Hermes Agent (NousResearch/hermes-agent) who run one or more profiles
on subscription providers (OpenAI Codex/ChatGPT Plus, Anthropic OAuth, OpenRouter, Nous).
Problem: the account limits exist only behind the user slash command `/usage`; the agent
and scripts cannot reach them. Measured on 2026-09-19: the question "which account, what
weekly limit" cost the agent 17 model cycles, 20 tool calls and 449 s
(`D:\DEV\Hermes\docs\research\gpt-account-limit-answer-audit.md`). With this plugin the
same question took 2 tool calls and one model turn (56 s, session `20260919_212926_ad1a57`).

Runtime: Python 3.11 (the Hermes venv), Hermes Agent v0.20.0 (2026.8.3). Standard library
only; the plugin imports the host's `agent.account_usage` and `hermes_cli.auth` at call
time. No third-party packages, no network I/O of its own.

## File map and boundaries

| Path | Role |
|---|---|
| `plugin/account-usage/plugin.yaml` | manifest read by the Hermes plugin loader |
| `plugin/account-usage/__init__.py` | `register(ctx)`: agent tool `account_usage`, CLI `hermes usage` |
| `plugin/account-usage/usage_core.py` | pure helpers (JWT claims, identity pick, snapshot→dict, render) + Hermes-backed collectors; runnable as a script (used per profile in `--all-profiles`) |
| `tests/test_usage_core.py` | unit tests of the pure helpers, synthetic data only |
| `install.py` | copies the plugin into `<HERMES_HOME>/plugins/account-usage` and enables it in `config.yaml` |
| `docs/` | DEV Framework documents (this project owns them) |

Consumers of shared code: the plugin is consumed by the Hermes loader; nothing else imports it.

## Workflow profile

Selected at installation: **generic**. Read
[the selected profile](.devframework/profiles/generic.md).
Project-specific overrides must be explicit here and must not silently weaken safety.
For a profile change, also update the selected link and verification configuration.

## Data and environments

- Reads: `<HERMES_HOME>/config.yaml` (`model.provider`), OAuth token store via host API
  (only to decode non-secret JWT claims: email, plan, account id). Tokens are never printed.
- Writes: nothing at runtime. `install.py` writes `<HERMES_HOME>/plugins/account-usage/`
  and patches `plugins.enabled` in `config.yaml` after a timestamped backup.
- Environments: developer = `D:\DEV\hermes-account-usage`; test = unit tests, no Hermes
  home touched; "production" = the owner's local profiles under
  `%LOCALAPPDATA%\hermes\profiles\<name>` (first target: `mastermind`). Server profiles on
  the VPS are out of scope for v0.1.
- No database, no schema (see docs/ARCHITECTURE.md).

## Commands and outputs

Configured in `.devframework/project.json`: no build (interpreted plugin); test =
`.devframework/run_unittest.py --start tests`. Outputs: test report JSON outside the repo
(framework-managed). No process locks. Manual end-to-end checks: docs/REGRESSION_TEST.md.

## Target scale and worked cost example

Initial planning target: **1,000 users** (1000 users).
Assumption: one request/minute/client, all clients active 24 hours/day, no retries.
Per client: 1,440 requests/day. Total: **1,440,000 requests/day**,
**16.67 requests/second** on average while active.
This is an example, not a measured capacity claim. Real cost driver for this plugin: one
HTTPS call to the provider usage endpoint per invocation, per profile; `--all-profiles`
spawns one subprocess per profile (4.8 s for 3 profiles on 2026-09-19).

## Conventions and decisions

Language: Python, PEP 8, type hints; docs in Russian/English as the owner writes them.
Deliberate limitations of v0.1 (each marked `ponytail:` in code where relevant):
- providers = whatever the host's `fetch_account_usage` supports (openai-codex, anthropic,
  openrouter) plus Nous credits; no fetchers of our own (the community plugin
  `rarf/hermes-quota-plugin` covers 9 providers — contribute there rather than duplicate);
- `--all-profiles` runs sequential subprocesses (ceiling ≈ 10 profiles; parallelise then);
- no thresholds/alerts, no history — see docs/BACKLOG.md.
Architectural rationale and reversal triggers: docs/ARCHITECTURE.md. The active checklist
and handoff are linked from docs/BACKLOG.md.
