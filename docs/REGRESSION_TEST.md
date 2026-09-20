# Regression test plan — Hermes Account Usage Plugin

**What this is:** a risk/coverage index and the remaining manual engineering checks.
**Update when:** features are added or existing behaviour changes. See `AGENTS.md`
section 3.

## When to run

Run the configured automated suite after implementation. On a behaviour change, update
affected cases and exercise relevant boundaries. Before release, run the agreed release
coverage and record any unavailable check as a limitation, not a pass.

## What belongs here and what does not

Automate repeatable assertions using the existing test framework. Crash/restart and
permission failures can often be tested in isolated child processes or environments;
they are not inherently manual. Never corrupt the operator's actual settings to test.

Keep a short link to automated coverage rather than duplicate the test procedure here.
Manual cases cover remaining UX/environment behaviour and are performed by the engineer,
not handed back to the product owner as debugging chores.

## Case format

| # | Area | Steps | Expected result | Result |
|---|---|---|---|---|
| 1 | Example: recovery | In an isolated temporary profile, supply invalid settings and start a child process | Recovery is explicit; existing bytes survive; close/restart never becomes a silent first run | not run |

## Automated coverage index

| Risk / requirement | Test command or source | What is NOT covered |
|---|---|---|
| NFR-001 token leak, FR-004 identity, FR-009 kinds/thresholds/balance parsing, multi-profile rendering | `python .devframework/run_unittest.py --start tests` -> `tests/test_usage_core.py` (13 tests) | real provider HTTP, real token store, Hermes loader registration |

## Cases

| # | Area | Steps | Expected result | Result |
|---|---|---|---|---|
| R-01 | UC-001 agent path | In profile `mastermind` (plugin installed, logged in): `hermes -p mastermind chat --yolo -q "<question about account and weekly limit>" --max-turns 4` | one model turn; tool trace shows `account_usage`; answer names account email/plan and Weekly/Session windows | pass 2026-09-19 headless (2 tool calls, 56 s, session `20260919_212926_ad1a57`); **pass 2026-09-20 in Hermes Desktop 0.20.0 by the owner: `Used 2 tools`, answer in one turn, numbers equal to CLI** |
| R-02 | UC-002 CLI | `hermes -p mastermind usage` and `hermes -p mastermind usage --json` | text block with Account + Session/Weekly; JSON parses, contains no token strings | pass 2026-09-19 |
| R-03 | UC-003 all profiles | `hermes -p mastermind usage --all-profiles` | one block per profile home; profiles without a fetcher show `unavailable (<reason>)`; total time < 40 s | pass 2026-09-19 (default/daria/mastermind, 4.8 s) |
| R-04 | expired token | with an expired/revoked Codex token: `hermes -p <p> usage` | `Limits: unavailable (...)` with the provider's reason; no traceback | not run (no expired profile available locally today) |
| R-06 | Desktop `/usage` control | In Desktop, profile mastermind, type `/usage` | Account limits block for openai-codex | **fail 2026-09-20: only "Session Token Usage" with zeros, no Account limits** -> KE-2026-09-20-DESKTOP-USAGE-NO-LIMITS (upstream #45713 / #42904) |
| R-07 | UC-004 slash in Desktop | Desktop, profile mastermind: `/quota`, then `/quota local`, then `/quota daria` | multi-profile report with alert header; local = one profile; no model turn in the trace | pass 2026-09-20 (owner screenshot, v0.3: alert header, 3 profiles, per-model lines, honest cost labels) |
| R-08 | UC-004 handler in-process | `discover_plugins(); get_plugin_command_handler('quota')('local')` with `HERMES_HOME`=mastermind | handler registered; returns `Profile: mastermind` block | pass 2026-09-20 |
| R-09 | UC-005 activity | `hermes -p mastermind usage` | daria block lists openrouter (62 calls, deepseek models) although its primary is openai-codex; default (nous) shows balance and an alert `nous: balance $0.00` | pass 2026-09-20 (6.5 s, 3 profiles) |
| R-10 | UC-006 watchdog | `install.py --profile <p> --watchdog 60m --deliver local`; `hermes -p <p> cron list`; trigger the job | job exists; output only when a threshold is breached; second run within 24 h silent | not run (watchdog not enabled on any profile yet) |
| R-11 | UC-007 Desktop pane | Settings → Plugins → Rescan (or restart); open the `quota` tab in the right dock; toggle All/This profile; press ↻ | pane lists profiles with progress bars and alerts; numbers equal `/quota`; no chat session required | pass 2026-09-20 (owner screenshot): `QUOTA` tab in the right zone, All/This profile toggle, alert row for default/nous, cards per profile with Session/Weekly bars, OpenRouter quota bar + balance, per-model activity; note: the right zone was collapsed at first and had to be opened from the title bar |
| R-05 | installer idempotence | run `python install.py --profile mastermind` twice | second run prints `already enabled`; exactly one `- account-usage` line in config | pass 2026-09-19 (second run: `already enabled`, 1 line) |

## Findings

R-03 first run: mojibake in headers -> KE-2026-09-19-SUBPROCESS-CP1251 (fixed).
