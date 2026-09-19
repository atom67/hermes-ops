# v0.1 — one-call account limits for the agent and the shell, on profile `mastermind`

**Started:** 2026-09-19
**Status:** awaiting acceptance

## Scope agreed with the operator

Operator instruction (2026-09-19): "разработай прототип plug-and-play решения hermes
который я мог бы тестировать, документация и флоу по dev framework где это применимо".
Development and testing on the local profile `mastermind` (agreed earlier the same day).

- In: agent tool, CLI command, all-profiles view, installer, unit tests, framework docs.
- Out: own provider fetchers, alerts/thresholds, history, UI, server profiles, upstream PR.

## Portions

### 1. Plugin + installer + verification
- [x] `plugin.yaml`, `__init__.py` (register tool + CLI), `usage_core.py`
- [x] unit tests (7) for pure helpers, token-leak guard
- [x] `install.py` with config backup; installed into `mastermind`
- [x] `hermes -p mastermind plugins list` shows `account-usage enabled`; `hermes -p mastermind tools list` shows `account_usage` enabled
- [x] `hermes -p mastermind usage` returns identity + Session/Weekly windows
- [x] end-to-end: `hermes -p mastermind chat -q "<limit question>"` -> 2 tool calls, 56 s (session `20260919_212926_ad1a57`)
- [x] `--all-profiles`: default (nous -> credits path), daria, mastermind in 4.8 s

**Acceptance:** the operator asks the same question in Hermes Desktop on profile
`mastermind` and sees the answer within one model turn; `hermes -p mastermind usage`
matches `/usage`.

### 2. Framework documents
- [x] PROJECT.md, ARCHITECTURE.md, REQUIREMENTS.md, USE_CASES.md, KNOWN_ERRORS.md, REGRESSION_TEST.md, BACKLOG.md
- [x] `python .devframework/check.py doctor` -> READY (2026-09-19)
- [x] `python .devframework/check.py finish` -> 7 tests, 0 skipped; SOURCE SHA256 cb1b93a8425df200bf776027043232537eddfd3cf75e5de249b7a889c2831ad2 (2026-09-19)

**Acceptance:** doctor and finish are green; digest recorded below.

## Deliberate limitations

- Providers = host fetchers only (openai-codex, anthropic, openrouter) + Nous credits.
  Ceiling: any other provider reports `unavailable`. Upgrade: contribute fetchers to
  `rarf/hermes-quota-plugin` rather than here.
- `--all-profiles` = sequential subprocesses (about 1.5 s each). Ceiling about 10 profiles.
- Identity only for `openai-codex` (JWT claims). Anthropic/OpenRouter identity is not
  available locally in a non-secret form.
- `install.py` patches `config.yaml` by text; unusual `plugins:` layouts fall back to
  inserting `enabled:` at the top of the block — verify by `hermes plugins list`.

## Handoff — update at every portion boundary and provider switch

- Branch/base commit and task-owned uncommitted changes: no git repository yet (owner
  decides whether this becomes a public repo — see strategy doc). All files are new.
- Current portion and next concrete step: portions 1-2 done; next =
  owner acceptance test in Desktop, then decision on upstream form (BACKLOG -> Next).
- Agreed decisions and links: profile `mastermind` for dev/test (operator, 2026-09-19);
  reuse host fetchers (ARCHITECTURE -> Decisions).
- Commands/checks actually run, date, result/counts, environment and evidence: see
  "Verification log" below.
- Checks not run, reason and remaining risk: Desktop chat path not exercised by me (owner
  action); Anthropic/OpenRouter providers not exercised (no profile uses them as primary);
  VPS profiles untouched (v0.19.1 API not verified).

## Verification log

- 2026-09-19 unit tests: 7 passed (venv python 3.11, `python -m unittest discover -s tests`).
- 2026-09-19 live CLI/tool/all-profiles runs: see docs/REGRESSION_TEST.md R-01..R-03; R-05 second install run: `already enabled`, one config line.
- 2026-09-19 `check.py finish`: PASSED, 7 tests, SOURCE SHA256 cb1b93a8425df200bf776027043232537eddfd3cf75e5de249b7a889c2831ad2 (worktree only, no commit).
