# hermes-ops

Plugins and skills for [Hermes Agent](https://github.com/NousResearch/hermes-agent), built and
run daily on a multi-profile setup (Windows + Linux VPS). Each entry ships only after it has
solved a real problem here, with the measurement that motivated it.

| Entry | Status |
|---|---|
| [`plugin/account-usage`](plugin/account-usage) — account limits + identity in one call for the agent and the shell | v0.1, tested on Hermes v0.20.0 |

---

# account-usage — Hermes plugin

**One call instead of twenty.** Gives the Hermes agent and your shell the same account-limit
data that the `/usage` slash command shows — plus which account is logged in — for the
active provider of a profile, or for all profiles at once.

Measured on Hermes v0.20.0 (2026-09-19): the question *"which account are you on and how much
weekly limit is left?"* took the agent **17 model cycles, 20 tool calls, 449 s** (it had to
find and read the core source to reach the data). With this plugin: **2 tool calls, one model
turn, 56 s**.

## What you get

- agent tool `account_usage(provider?, all_profiles?)` — the model answers quota questions directly;
- CLI `hermes -p <profile> usage [--provider X] [--all-profiles] [--json]`;
- identity for OpenAI Codex (email, plan, account id) from non-secret JWT claims — tokens are never printed;
- Nous credits for profiles on the `nous` provider;
- fail-soft: a provider without data renders `Limits: unavailable (<reason>)`.

Providers covered = whatever the host's `agent.account_usage` supports (openai-codex, anthropic,
openrouter) + Nous credits. For 9-provider coverage and a Desktop status chip see
[rarf/hermes-quota-plugin](https://github.com/rarf/hermes-quota-plugin); this plugin does not
duplicate its fetchers.

## Install (plug-and-play)

```bash
python install.py --profile mastermind        # repeat --profile for more; --global for ~/.hermes
```

Copies `plugin/account-usage/` to `<HERMES_HOME>/plugins/account-usage/` and adds
`account-usage` to `plugins.enabled` in that profile's `config.yaml` (backup written first,
comments preserved). Restart the profile's gateway/TUI/Desktop. Verify:

```bash
hermes -p mastermind plugins list      # account-usage  enabled
hermes -p mastermind usage             # Profile / Account / Session / Weekly
```

Uninstall: `python install.py --profile mastermind --uninstall` and remove the line from `plugins.enabled`.

## Example

```
Profile: mastermind · provider: openai-codex
Account: user@example.com (plus)
📈 Account limits
Provider: openai-codex (Plus)
Session: 51% remaining (49% used) • resets in 2h 36m (…)
Weekly: 92% remaining (8% used) • resets in 6d 21h (…)
```

`--json` returns `{profile, provider, identity{…}, usage{available, windows[{label, used_percent, reset_at}], lines[], unavailable_reason}}`; `reset_at` is ISO-8601.

## Tested with

| Hermes | OS | Profiles | Date |
|---|---|---|---|
| v0.20.0 (2026.8.3), Desktop 0.20.0 | Windows 11 | openai-codex ×2, nous ×1 | 2026-09-19 |

Not tested: Anthropic/OpenRouter as primary provider, Linux, Hermes ≥ v2026.9.x (upstream
renamed nothing we use as of main on 2026-09-19, but this is unverified at runtime).

## Limits and support

- No thresholds, alerts or history (see `docs/BACKLOG.md`).
- `--all-profiles` runs one subprocess per profile, sequentially.
- Identity only for openai-codex.
- First-round support: bug reports with `hermes version` + the `--json` output (redact email).

## Development

DEV Framework project: `PROJECT.md`, `docs/` (requirements, architecture, use cases,
regression, known errors, backlog + active checklist), `.devframework/check.py doctor|finish`.

```bash
python -m unittest discover -s tests -v       # 7 tests, no Hermes, no network
python .devframework/check.py finish          # counted evidence + source digest
```

License: MIT.
