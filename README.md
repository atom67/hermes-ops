# hermes-ops

Plugins and skills for [Hermes Agent](https://github.com/NousResearch/hermes-agent), built and
run daily on a multi-profile setup (Windows + Linux VPS). Each entry ships only after it has
solved a real problem here, with the measurement that motivated it.

| Entry | Status |
|---|---|
| [`plugin/account-usage`](plugin/account-usage) — account limits, balances and spend across profiles for the agent, the chat (`/quota`) and the shell | v0.4, tested on Hermes v0.20.0 |
| [`desktop/account-usage`](desktop/account-usage) — Hermes Desktop pane for the same data (progress bars, alerts, per-model activity) | v0.4, pane accepted 2026-09-20 |

---

# account-usage — Hermes plugin

**One call instead of twenty, across all your profiles.** Gives the Hermes agent, the chat
and your shell the account-limit data behind the `/usage` slash command — plus which account
is logged in, prepaid balances, and what each profile actually used in the last 7 days.

Measured on Hermes v0.20.0 (2026-09-19): the question *"which account are you on and how much
weekly limit is left?"* took the agent **17 model cycles, 20 tool calls, 449 s**. With this
plugin: **2 tool calls, one turn**. In Hermes Desktop the built-in `/usage` showed no Codex
limits at all (upstream #45713); `/quota` does.

## Four ways in

| Where | How | Scope |
|---|---|---|
| chat (Desktop, TUI, Telegram…) | ask in plain words: *"общий отчёт по лимитам"*, *"сколько осталось на этом профиле?"* → the agent calls `account_usage(scope=all|local|<profile>)` | all profiles by default |
| chat slash command | `/quota` · `/quota local` · `/quota daria` · `/quota --days 30` | no model turn, instant |
| shell / cron | `hermes -p <profile> usage [--local | --profile NAME] [--days N] [--json]` | scripts, watchdog |
| **Hermes Desktop pane** | tab `quota` in the right dock: progress bars per window, balances, ⚠ alerts on top, per-model activity, All/This profile toggle, auto-refresh 5 min | readable UI — Desktop renders slash output dim and small |

## What a report contains

Per profile → per provider (the configured one + any provider seen in `state.db` in the last N days):

| Kind | Providers | Shown | Threshold |
|---|---|---|---|
| **windows** | ChatGPT Plus / Codex, Anthropic Max, OpenRouter API-key quota | % used per window, reset time | weekly < 15 %, session < 10 % |
| **balance** | OpenRouter credits, Nous credits | remaining $ | balance < $5 |
| **spend** | pay-as-you-go keys without a balance API (Gemini, OpenAI key…) | local spend estimate for the window, models, calls | over budget (opt-in) |

Identity (email, plan) is shown for openai-codex from non-secret JWT claims. Tokens are never printed.
`xai-oauth` limits come from the Grok CLI billing proxy (`cli-chat-proxy.grok.com/v1/billing`) with the stored OAuth bearer — core has no fetcher yet (upstream PR #114949). Providers the host cannot fetch render `unavailable (<reason>)`; nothing raises.

## Install (plug-and-play)

```bash
python install.py                                 # every home (root + all profiles) — recommended for Desktop
python install.py --profile mastermind            # one profile only, lists providers seen in 7 days
python install.py --profile mastermind --watchdog 60m --deliver telegram --weekly 15 --balance-usd 5
python install.py --profile mastermind --watchdog 60m --deliver local --watch-scope all --watch-top 4 --balance-min nous=100
```

Copies `plugin/account-usage/` into `<HERMES_HOME>/plugins/`, adds `account-usage` to
`plugins.enabled` (backup written, comments preserved), and copies the Desktop pane
(`desktop/account-usage/plugin.js`) into `<HERMES_HOME>/desktop-plugins/` and the root home
(`--no-desktop` to skip). **Restart** the profile's gateway/TUI/Desktop; for the pane alone,
Settings → Plugins → Rescan is enough (runtime plugins hot-reload). The watchdog is optional: a normal Hermes cron job (`--no-agent`) that
prints only on a threshold breach, once per breach-set per day; `--deliver telegram` pushes via
the profile's bot, `local` keeps it in cron output. Thresholds live in
`plugins.entries.account-usage.settings.*` (`hermes config set …`).

Two watchdog modes: `--watch-scope profile` follows this profile's `--watch-top` most-used providers of the
last week (default 2); `--watch-scope all` (default) follows the top providers across every profile (default 4).
`--watch-top all` watches every provider, idle ones included. Paid providers get their own floor in the unit
they report — dollars or credits — with `--balance-min PROVIDER=AMOUNT` (repeatable); `--balance-usd` stays
the default for the rest.

One account used by several profiles (e.g. one ChatGPT Plus login) is shown once: the later block says
`same account as profile X — limits shown there` and keeps only its own activity; alerts fire once per account.

Uninstall: `python install.py --profile mastermind --uninstall` (then drop the config line and cron job).

## Example (`hermes usage`)

```
Account usage — 3 profile(s) · 1 alert(s)
  ⚠ nous: balance $0.00 (< $5.0)

Profile: daria
openai-codex [windows] · user@example.com (plus)
  Session: 100% remaining (0% used) • resets in 4h 28m (…)
  Weekly: 92% remaining (8% used) • resets in 6d 8h (…)
  last 7d: 840 calls, gpt-5.6-sol, gpt-6-astra, ≈$0.00 (estimate, local accounting)
openrouter [windows]
  API key quota: 79% remaining (21% used) • $11.91 of $15.00 remaining • resets monthly
  Credits balance: $17.30
  last 7d: 62 calls, deepseek/deepseek-v4-flash-0731, deepseek/deepseek-v4-pro, ≈$0.98 (estimate, local accounting)
```

`--json` returns a list of `{profile, primary, days, providers[{provider, kind, identity, usage{windows[], lines[], balance_usd, unavailable_reason}, activity{calls, models, spend_usd, cost_source, last_seen}}]}`.

## Tested with

| Hermes | OS | Profiles | Date |
|---|---|---|---|
| v0.20.0 (2026.8.3), Desktop 0.20.0 | Windows 11 | openai-codex ×2, openrouter ×1, nous ×1 | 2026-09-20 |

Not tested: Anthropic as primary provider, Linux, Hermes ≥ v2026.9.x (unverified at runtime).

## Limits and support

- Providers = what the host's `agent.account_usage` can fetch (+ Nous credits). No fetchers of our own —
  for 9-provider coverage and a Desktop status chip see [rarf/hermes-quota-plugin](https://github.com/rarf/hermes-quota-plugin).
- `spend` is a local estimate from Hermes' own accounting, not a provider invoice.
- `--all-profiles` = one subprocess per profile, sequential (≈1.5 s each).
- First-round support: issues with `hermes version` + `--json` output (redact email).

## Desktop pane — how it works

Plain ESM (`desktop/account-usage/plugin.js`), loaded by Hermes Desktop's runtime plugin
door (`<hermes home>/desktop-plugins/<name>/plugin.js`, hot-reloaded, listed in Settings →
Plugins). It registers one pane (`area: 'panes'`, right dock) and gets its data through the
gateway RPC `cli.exec` → `hermes usage --json`, so no chat session is needed and the numbers
are exactly those of `/quota`. Note: Desktop runtime plugins execute with full app authority
by the host's design — read the file before installing, as with any local plugin.

## Development

DEV Framework project: `PROJECT.md`, `docs/` (requirements, architecture, use cases, regression,
known errors, backlog + active checklist), `.devframework/check.py doctor|finish`.

```bash
python -m unittest discover -s tests -v       # 13 tests, no Hermes, no network
python .devframework/check.py finish          # counted evidence + source digest
node --check desktop/account-usage/plugin.js  # (copy to .mjs first) Desktop pane syntax
```

License: MIT.
