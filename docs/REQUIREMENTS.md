# Requirements — Hermes Account Usage Plugin

**What this is:** every requirement the product has, numbered, with its current status.
**Update when:** an incoming request asks for a new feature, a behaviour change, or a
correction to an existing function. See `AGENTS.md` section 3.

## Identifiers

- `FR-###` — functional requirement. `NFR-###` — non-functional requirement.
Numbers are permanent and unique; superseded ones are struck through, never reused.

## Product principles

1. One call, same numbers as `/usage` — never a second implementation of provider quirks.
2. Identity yes, secrets never: tokens do not appear in output, logs or JSON.
3. Fail soft: a provider without data renders `unavailable (<reason>)`, never a crash.
4. Plug-and-play: install = copy a directory + one config line; uninstall is symmetric.

## Functional requirements

| ID | Requirement | Status |
|---|---|---|
| FR-001 | The agent can obtain account limits and identity with one tool call (`account_usage`), for all profiles by default or one profile on request. | done (v0.2) |
| FR-002 | `hermes usage` prints the same report for the current profile; `--json` gives the report object. | done (v0.1) |
| FR-003 | Every entry point reports all profile homes (default + `profiles/*`) unless scoped to `local` or a profile name. | done (v0.2) |
| FR-004 | Identity (email, plan, account id) is shown for `openai-codex`; Nous credits are shown for `nous`. | done (v0.1) |
| FR-005 | Optional threshold watchdog (weekly/session %, balance $, spend budget) as a cron job with Telegram/local delivery; silent unless breached. | done (v0.2, opt-in) |
| FR-007 | Slash command `/quota [local\|all\|<profile>] [--days N]` in every chat surface, no model turn. | done (v0.2) |
| FR-008 | Providers active in the last N days (from `state.db`) are included automatically with calls, models and spend. | done (v0.2) |
| FR-009 | Each provider block carries a kind — windows / balance / spend — with matching numbers and thresholds; no invented percentages for pay-as-you-go providers. | done (v0.2) |
| FR-006 | History of snapshots for trend view. | idea — not agreed |

## Non-functional requirements

| ID | Requirement | Status |
|---|---|---|
| NFR-001 | No tokens or API keys in any output; guarded by `test_render_never_leaks_tokens`. | done |
| NFR-002 | Single-profile report ≤ 5 s; all-profiles ≤ 40 s per profile (subprocess timeout). | done (3 profiles: 4.8 s on 2026-09-19) |
| NFR-003 | Standard library only inside the plugin; host modules imported lazily so unit tests run without Hermes. | done |
| NFR-004 | Installer never launches, restarts, commits or deletes user data; config edits are backed up. | done |

## Superseded

None yet.
