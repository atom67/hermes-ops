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
| v0.1 prototype on profile `mastermind` | tool + CLI + installer + docs; checklist: [CHECKLIST_v0.1.md](CHECKLIST_v0.1.md) | awaiting acceptance |

## Next

| Task | Scope | Priority |
|---|---|---|
| Owner test in Hermes Desktop (mastermind): ask the limit question in chat, compare with `/usage` | acceptance evidence for UC-001 | P1 |
| Decide upstream form: (a) core PR `hermes usage` CLI reusing `agent.account_usage`; (b) tool contribution to `rarf/hermes-quota-plugin`; (c) keep standalone | see `D:\DEV\Hermes\docs\HERMES_CONTRIBUTION_STRATEGY_2026-09-18.md` | P1 |
| FR-005 threshold alert (weekly < N %) via gateway delivery | needs decision on delivery path (cron job vs hook) | P2 |
| Install on VPS profiles (kevinashton, horizon) after server upgrade to >= 0.20 | server is v0.19.1 — `agent.account_usage` API must be verified there first | P2 |

## Recently finished (keep three)

| Task | Version | What landed / what was left |
|---|---|---|
| Recon: core `/usage` + community `rarf/hermes-quota-plugin` | — | Findings in `D:\DEV\Hermes\docs\RECON_2026-09-19_limits_and_council.md`; remaining: none |
| Measured baseline (agent without plugin) | — | 20 calls / 449 s, `D:\DEV\Hermes\docs\research\gpt-account-limit-answer-audit.md` |
