# Backlog — Hermes Account Usage Plugin

**What this is:** the operational queue. What is being worked on now, what is agreed next.
**Update when:** a task is taken up, finished, or appears. See `AGENTS.md` section 3.

## Statuses

`todo` — agreed, not started. `in progress` — being worked on now. `awaiting acceptance`
— implementation verified and presented, not yet accepted. `done` — accepted.
Link the active checklist; its Handoff section owns continuation details.

## Trimming rule

After the operator accepts a piece of work, cut this file back to everything active, the
next agreed items, and the three most recently finished features. Keep it under 80 KB.

## In progress

| Task | Scope | Status |
|---|---|---|
| v0.2: multi-profile default, `/quota`, activity from state.db, provider kinds, optional watchdog | checklist: [CHECKLIST_v0.2.md](CHECKLIST_v0.2.md) | done (owner ran `/quota`, `/quota local` in Desktop 2026-09-20) |
| v0.3: Desktop pane | checklist: [CHECKLIST_v0.3.md](CHECKLIST_v0.3.md) | awaiting acceptance (owner: Rescan, open `quota` pane) |
| v0.1 prototype on profile `mastermind` | tool + CLI + installer + docs; checklist: [CHECKLIST_v0.1.md](CHECKLIST_v0.1.md) | done (accepted 2026-09-20) |

## Next

| Task | Scope | Priority |
|---|---|---|
| Upstream: Desktop slash output contrast (KE-2026-09-20-DESKTOP-SLASH-OUTPUT-DIM) — one-line PR with before/after screenshots | second upstream candidate | P1 |
| Upstream bug report: Desktop `/usage` omits Codex account limits (KE-2026-09-20-DESKTOP-USAGE-NO-LIMITS, repro on 0.20.0, link to this plugin) | first upstream contribution candidate | P1 |
| Decide upstream form: (a) core PR `hermes usage` CLI reusing `agent.account_usage`; (b) tool contribution to `rarf/hermes-quota-plugin`; (c) keep standalone | see `D:\DEV\Hermes\docs\HERMES_CONTRIBUTION_STRATEGY_2026-09-18.md` | P1 |
| Enable the watchdog on one profile (`--watchdog 60m --deliver telegram`) and run R-10 | owner decision: which profile/bot | P2 |
| Install on VPS profiles (kevinashton, horizon) after server upgrade to >= 0.20 | server is v0.19.1 — `agent.account_usage` API must be verified there first | P2 |

## Recently finished (keep three)

| Task | Version | What landed / what was left |
|---|---|---|
| Recon: core `/usage` + community `rarf/hermes-quota-plugin` | — | Findings in `D:\DEV\Hermes\docs\RECON_2026-09-19_limits_and_council.md`; remaining: none |
| Measured baseline (agent without plugin) | — | 20 calls / 449 s, `D:\DEV\Hermes\docs\research\gpt-account-limit-answer-audit.md` |
