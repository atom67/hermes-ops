# v0.2 — multi-profile reports, `/quota` in chat, activity-based provider detection, optional watchdog

**Started:** 2026-09-20
**Status:** awaiting acceptance

## Scope agreed with the operator

Operator (2026-09-20): "телеграм мониторинг с пушами - это опциональная фича"; "предлагать вывод
лимитов по тем провайдерам, которые были активны последние 7 дней"; "что делать с провайдерами
где баланс кредитов или токенов а не пакетный лимит"; "отчеты должны быть мультипрофильные…
хочу локальный отчет - хочу общий отчет и командами терминала в чате десктоп приложения '/'".

- In: default scope = all profiles; `scope=local|<profile>`; `/quota`; activity from `state.db`;
  kinds windows/balance/spend with thresholds; optional watchdog cron (Telegram/local); installer
  prints detected providers; thresholds via `hermes config set`.
- Out: Desktop UI widget (rarf has one), history/trends, own provider fetchers, VPS profiles.

## Portions

### 1. Core + entry points
- [x] `usage_core` v0.2: `activity()`, `classify()`, `extract_balance()`, `breaches()`, `render_all()`, `run(scope)`
- [x] tool `account_usage(scope, provider, days)`; slash `/quota`; CLI default all, `--local`, `--profile`
- [x] 12 unit tests green
- [x] live: `hermes -p mastermind usage` → 3 profiles in 6.5 s; daria shows openrouter auto-detected; alert `nous: balance $0.00`
- [x] `/quota` registered and handler verified in-process (R-08)

**Acceptance:** owner runs `/quota` and `/quota local` in Desktop (profile mastermind) and asks
"общий отчёт по лимитам" in plain words — all three return the multi-profile/local report.

### 2. Optional watchdog + installer
- [x] `quota_watch.py` (once-per-day dedupe, all-clear line); `install.py --watchdog/--deliver/--weekly/--session/--balance-usd/--budget-usd/--days`
- [x] installer prints providers active in 7 days across profiles
- [ ] R-10 on one profile (owner decides profile/bot) — not run

**Acceptance:** cron job `quota-watch` exists; first run silent (no breach) or one alert message; second run silent.

### 3. Documents
- [x] README, USE_CASES (UC-004..006, SET-003), REQUIREMENTS (FR-005/007/008/009), REGRESSION (R-07..R-10), ARCHITECTURE, BACKLOG
- [x] doctor READY; finish PASSED: 12 tests, SOURCE SHA256 d4d19ec54f4cf534ef78f5ca5c35823f0cd144f17962d172dd2dbf77d1cfd691 (2026-09-20)

## Deliberate limitations

- OpenRouter is classified `windows` because the host returns API-key quota windows; its credits
  balance is still parsed and threshold-checked. Nous is `balance`.
- `spend` = local estimate from Hermes accounting (`estimated_cost_usd`), not an invoice.
- Balance parsing is a regex over host-rendered lines (`balance: $X`, `total usable: $X`) —
  breaks if upstream rewords them; guarded by `test_extract_balance_from_host_lines`.
- Watchdog dedupe = same alert-set within 24 h; a changed set re-alerts immediately.

## Handoff — update at every portion boundary and provider switch

- Branch/base commit and task-owned uncommitted changes: `main` at `bb7a778` (v0.1 published); v0.2 uncommitted until the owner authorizes commit/push.
- Current portion and next concrete step: portions 1–3 done except R-10; next = owner `/quota` test in Desktop, then commit/push v0.2, then decide watchdog profile.
- Agreed decisions and links: Telegram optional (operator 2026-09-20); providers by 7-day activity; kinds windows/balance/spend.
- Commands/checks actually run: unit tests 12/12 (2026-09-20); `hermes -p mastermind usage` all/local/`--profile daria`; in-process `/quota` handler; `check.py finish` (see Verification log).
- Checks not run, reason and remaining risk: R-07 (Desktop needs restart by owner); R-10 (watchdog not enabled anywhere); Anthropic provider untested.

## Verification log

- 2026-09-20 unit tests: 14 passed (per-model breakdown, cost labels, not-fetchable gap).
- 2026-09-20 live all-profiles: default/daria/mastermind, 6.5 s, 1 alert (nous balance $0.00).
