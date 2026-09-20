# v0.4 — Watchdog modes, per-provider floors, dedupe of shared accounts

**Started:** 2026-09-20
**Status:** implemented 2026-09-20; global watchdog enabled on `mastermind`; awaiting owner acceptance of the deduped pane

## Scope agreed with the operator

Operator (2026-09-20): «сторож тоже должен настраиваться 2 способами - для профиля - мониторя только
топ 2 канала ллм для него за последнюю неделю, или общий сторож на топ 4 по всем профилям (число топ
должно настраиваться, 2 и 4 это дефолт значения, должно быть с возможностью мониторить ВСЕ, сторож
платных провайдеров - указывать сумму в кредитах или долларах для алерта). настрой мне общий вариант /
так же я хочу чтобы не дублировалась идентичная квота в общем отчете - например на скрине я вижу 2 раза
блок codex с одинаковыми значениями».

- In: settings `watch_scope` (profile|all), `watch_top` (N|all; defaults 2/4), `balance_min.<provider>`;
  installer flags `--watch-scope`, `--watch-top`, `--balance-min PROVIDER=AMOUNT`; `dedupe()` +
  `same_as` in text, JSON and pane; pane mutes `not fetchable`; alerts prefixed with the profile.
- Out: pane reading thresholds from settings; Telegram delivery (owner has not chosen a bot).

## Portions

### 1. Core + watchdog
- [x] `usage_core.py`: `DEFAULT_WATCH_TOP`, `dedupe`, `watch_targets`, per-provider floor in `breaches`, `same_as` render
- [x] `quota_watch.py`: scope/top from settings, targets by calls, profile-prefixed alerts
- [x] `install.py`: new flags; bare interval → `every …` (KE-2026-09-20-CRON-BARE-INTERVAL-ONE-SHOT)
- [x] tests: 16 pass (`test_dedupe_*`, `test_watch_targets_*`, `test_per_provider_balance_floor_*`)
- [x] installed on `mastermind`: `watch_scope=all`, `watch_top=4`, cron `quota-watch` every 60m, deliver local (R-10 pass)
- [x] R-12 dedupe live: mastermind Codex block → `same account as profile 'daria'`
- [x] R-13 nested floor key via `hermes config set` — works; test value unset again

### 2. Pane
- [x] `same_as` line, bars/balance hidden for the duplicate, alerts skip it; `not fetchable` muted
- [x] `node --check` ok; copied to profile and root `desktop-plugins/`
- [x] owner screenshot 2026-09-20 14:19: one Codex card with bars (daria), mastermind says "same account as daria", xai-oauth muted
- [x] focus strip on top (owner request): one row per deduped source, 5h and weekly % left coloured on a red->yellow->green hue, balance-only sources show the amount; details follow below
- [x] owner screenshot 16:04: strip renders (nous $0.00 red, codex 5h/wk, openrouter $17.30) — but data stale, see KE-2026-09-20-PANE-STALE-ON-UNREGISTERED-USAGE
- [ ] owner: Rescan, press ↻, numbers must match the API (Session ≈41 %, Weekly ≈80 % at 17:42)

### 3. Documents
- [x] README, REQUIREMENTS FR-011/012, USE_CASES UC-008 + SET-003, REGRESSION R-10/12/13, KNOWN_ERRORS, BACKLOG
- [x] finish PASSED: 16 tests, SOURCE SHA256 e704ab8f6d78e8a0f06c3a2034f232079d58853453579f83d89c7e27845e5ae2 (2026-09-20)

## Deliberate limitations

- Top-N ranks by call count only; a provider with 0 calls in the window is not a channel and is skipped
  unless `watch_top: all` (so the idle `default/nous` $0 balance stops alerting in the global watchdog).
- Dedupe: a known account id (Codex JWT claim) decides sameness on its own; providers without identity
  are compared by window percentages and balance only. The first version also compared the host's
  rendered lines, and "resets in 43m" vs "42m" between two subprocess fetches broke the match — the
  owner saw Codex twice in the focus strip (2026-09-20 15:12); fixed, covered by `test_dedupe_*`.
- `--deliver local` for a Desktop-run cron: where the output surfaces has not been observed yet (R-10 note).

## Handoff

- Base commit: `de60b0c` (v0.3 accepted).
- Next concrete step: owner opens the pane; if a Telegram bot is chosen:
  `hermes -p mastermind cron delete quota-watch` then re-run the installer with `--deliver telegram`.

## Verification log

- 2026-09-20 `python -m unittest discover -s tests` → 16 OK; `hermes -p mastermind usage` → dedupe visible;
  `quota_watch.py` manual run → silent (no breach among top-4 active); `cron list` → `every 60m, Repeat: ∞`.
