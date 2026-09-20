# v0.3 — Desktop pane (readable multi-profile quota UI)

**Started:** 2026-09-20
**Status:** awaiting acceptance

## Scope agreed with the operator

Operator (2026-09-20): slash output in Desktop is barely readable; "мы через свой плагин кастомный
вывод настроить не можем?" → answer: not for the chat line (host style), yes as a Desktop runtime
plugin pane; "делай доработки".

- In: `desktop/account-usage/plugin.js` pane (right dock): All/This profile toggle, ↻, auto-refresh
  5 min, alerts, progress bars per window, balances, per-model activity; installer copies it to
  `<profile>/desktop-plugins/` and the root home; `/quota --json` for future in-chat use.
- Out: status-bar chip, settings UI for thresholds, charts/history.

## Portions

### 1. Pane
- [x] `plugin.js` (plain ESM, React from the app singleton, SDK `host.request('cli.exec')`, `Button`, `PANES_AREA`)
- [x] `node --check` passes
- [x] installer step `install_desktop` (+ `--no-desktop`); installed for mastermind and root home
- [ ] R-11: owner opens the pane (Rescan or restart), numbers equal `/quota`

**Acceptance:** the `quota` tab is visible in the right dock; All/This profile switch works; an
alert row appears for the depleted Nous balance; no error box.

### 2. Documents
- [x] README (Desktop section), USE_CASES UC-007 + SET-004, REQUIREMENTS FR-010, REGRESSION R-11, KNOWN_ERRORS (dim slash output), BACKLOG
- [x] doctor READY; finish PASSED: 13 tests, SOURCE SHA256 fca78bb40712b85d6d37f7ec0b8de5d27fcfc3962096e7e5329e4893ef932027 (2026-09-20)

## Deliberate limitations

- Data path is `cli.exec` → a subprocess per refresh (~6 s for 3 profiles); fine at 5-minute
  refresh, wasteful under 30 s. Upgrade: backend REST route (`ctx.rest`) if refresh gets frequent.
- The pane uses the backend of the *active* profile: the `usage` command must be enabled there
  (the installer enables it per profile; `--global` for the root/default profile).
- Alerts in the pane use fixed thresholds (15 % weekly, $5 balance); the backend's configured
  thresholds are not read by the JS yet. Upgrade: expose `settings` in the JSON.
- Runtime plugins run with full app authority (host design) — the file is small and reviewable.

## Handoff — update at every portion boundary and provider switch

- Branch/base commit: `main` at `b3a7ef0` (v0.2 pushed); v0.3 committed after this checklist.
- Current portion and next concrete step: portion 1 awaits R-11 by the owner; then decide status-bar chip / threshold pass-through.
- Agreed decisions: pane instead of chat styling (host limitation, 2026-09-20).
- Commands/checks actually run: `node --check` OK; installer copied files; `check.py finish` (Verification log).
- Checks not run: R-11 (needs the Electron UI); pane behaviour under the `default` profile backend (usage command not enabled there).

## Verification log

- 2026-09-20 `node --check desktop/account-usage/plugin.js` (as .mjs): syntax ok.
