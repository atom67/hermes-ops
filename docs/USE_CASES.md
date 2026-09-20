# Use cases — Hermes Account Usage Plugin

**What this is:** a modular catalogue of how the product delivers value — every case
driven either by a user action or by an automatic tool — with the achieved benefit stated
at the end of each. Text only, no screenshots.
**Who reads it:** the product owner (what value exists and where), and the engineer (the
source list for functional tests).
**Update when:** a capability is added, or a case's trigger, flow, or outcome changes.
See `AGENTS.md` section 3. Copy-ready blocks: [`USE_CASE_TEMPLATE.md`](USE_CASE_TEMPLATE.md).
An edition or public cut of this catalogue: [`USE_CASES_SLICE_TEMPLATE.md`](USE_CASES_SLICE_TEMPLATE.md).

**Sibling of `ARCHITECTURE.md`.** The two live in parallel and must not duplicate each
other: `ARCHITECTURE.md` says how the system is built (components, schema, flows);
`USE_CASES.md` says what value it produces and how that value is exercised. Every case
names the architecture components it runs through, by reference, not by copy.

**Starting point for functional autotests.** Each case is written so it maps to one
functional test: a defined trigger, defined preconditions, an observable outcome. The
`Test` field carries one of three states (see *Identifiers*). A case that is merely
untested is a coverage gap; a case that *cannot* be tested by standard functional means is
a different thing entirely — it is recorded in the *Not functionally verifiable* register
below so that it is kept in mind during development even though no automated test guards
it.

---

## How to read this document

- **Modules** are value areas / capability domains. One module groups the cases that
  deliver one kind of benefit. A module usually contains both interactive and automatic
  cases — that is expected, and they sit together because they serve the same value.
- **A case** is one path to one benefit. It has a stable ID, a trigger type, the
  preconditions it needs, the steps, and the outcome it achieves.
- **Setup and settings are not inside cases.** They live in the separate *Setup &
  settings* block below and are referenced by ID (`SET-###`). A case names the setup it
  needs; it does not re-describe how to configure it. This keeps configuration in one
  place and the cases readable.
- **Human meaning is not a case.** If several paths share a glossary (what a calendar
  row *means*, what a status word means), write that glossary once in the module. Cases
  do not restate it.

## Identifiers

- `UC-###` — a use case. Permanent and unique; never reused for a different case.
- **Trigger** — how the value is initiated:
  - **Interactive** — a deliberate user action (open a screen, press a control, drop an
    item).
  - **Automatic** — no user present at the moment: a timer, a background service, a
    connector, a scheduled job, or an inbound external event.
- `SET-###` — a setup or settings item in the block below.
- **Test status** — every case carries exactly one:
  - **covered** — a link to the automated test that guards it.
  - **gap** — testable by standard functional means, but not yet covered. An open
    functional-coverage item; record it in `docs/BACKLOG.md`.
  - **NFV** (not functionally verifiable) — cannot be checked by a standard automated
    functional test. It still ships and still matters, so it is listed in the *Not
    functionally verifiable* register with the reason, and is verified by hand or held as
    a development constraint. `NFV` is a deliberate classification, never a synonym for
    "no test yet".
- Link out to `FR-###` in `docs/REQUIREMENTS.md` and to components in
  `docs/ARCHITECTURE.md`. Do not restate their text here.
- A SET row's **Enables** column and a case's **Preconditions** may only name IDs that
  exist as `#### UC-` headings or SET rows. Ellipsis ranges (`UC-150…155`) are expanded:
  every number in the range must have a case. Do not pad a range to a round number.
  `UC-150+` means UC-150 exists, not an open-ended list.
- When the product has more than one store or API, **Flow** names which one this case
  uses. Do not paste a safety slogan from another path (for example "read-only replica")
  onto a case that actually calls a server API.

---

## Setup & settings (separate block)

| ID | Setting | Where configured | Required / optional | Enables |
|---|---|---|---|---|
| SET-001 | Plugin installed and enabled: `python install.py --profile <name>` copies `plugin/account-usage` to `<HERMES_HOME>/plugins/` and adds `account-usage` to `plugins.enabled`; restart the profile's gateway/TUI/Desktop | project root / profile `config.yaml` | required | UC-001, UC-002, UC-003, UC-004, UC-005, UC-006 |
| SET-003 | Watchdog (optional): `python install.py --profile <name> --watchdog 60m --deliver telegram\|local [--weekly N --session N --balance-usd X --budget-usd Y --days N]` — creates cron job `quota-watch` and stores thresholds in `plugins.entries.account-usage.settings` | installer / `hermes config set` / `hermes cron` | optional | UC-006 |
| SET-004 | Desktop pane: `desktop/account-usage/plugin.js` copied to `<HERMES_HOME>/desktop-plugins/account-usage/` (installer does it; `--no-desktop` skips) | installer | optional | UC-007 |
| SET-002 | Provider login of the profile (`hermes -p <name> auth login openai-codex` etc.) — the plugin reads the resulting token store, it never logs in itself | Hermes auth | required for limits; without it the report says `unavailable` | UC-001, UC-002, UC-003, UC-004 |

---

## Modules

### Module: Account limits

**Value this module delivers:** the operator (or the agent on their behalf) learns which
account is in use and how much quota remains, in one step, without reading source code.
**Architecture components involved:** `usage_core.collectors`, `usage_core.pure`,
`__init__.py → register(ctx)` (docs/ARCHITECTURE.md → Components).

#### UC-001 — Agent answers a quota question with one tool call

- **Trigger:** Interactive — the user asks the agent about limits, remaining usage, balance, spend or the account in use ("общий отчёт" → all profiles, "локальный" → this profile).
- **Actor:** the agent (model) calling tool `account_usage`.
- **Preconditions:** SET-001, SET-002.
- **Flow:** model calls `account_usage(scope=all|local|<profile>)` → `usage_core.run()` → per profile: `model.provider` + providers active in the last N days (UC-005), identity claims, host fetcher (one HTTPS GET per provider) → rendered text with an alert header → model answers.
- **Outcome (value / function achieved):** the answer arrives in one model turn; 2026-09-19 measurement: 2 tool calls / 56 s versus 20 calls / 449 s without the plugin.
- **Test:** NFV (needs a real OAuth token and provider network) — manual regression R-01; the pure transformations are covered by `tests/test_usage_core.py`.

#### UC-002 — Operator checks limits from the shell

- **Trigger:** Interactive — `hermes -p <profile> usage [--local | --profile NAME] [--provider X] [--days N] [--json]` (default: all profiles).
- **Actor:** the operator or a script.
- **Preconditions:** SET-001, SET-002.
- **Flow:** CLI handler → `report()` → text or JSON on stdout; exit code 1 when the report carries `error`.
- **Outcome (value / function achieved):** scripts and cron jobs get the same numbers as `/usage` without an agent turn.
- **Test:** NFV (real token/network) — manual regression R-02; JSON shape guarded by `test_snapshot_dates_become_iso_and_available_flag_set`.

#### UC-003 — All profiles at once

- **Trigger:** Interactive — default scope of every entry point; explicitly `scope=all`, `/quota`, `hermes usage`.
- **Actor:** the operator or the agent.
- **Preconditions:** SET-001 in the calling profile; SET-002 in each profile that should show limits.
- **Flow:** `all_profiles_reports()` spawns `usage_core.py --json` per profile home with its own `HERMES_HOME`; failures become per-profile `error` rows; results are concatenated.
- **Outcome (value / function achieved):** one view of every account/provider the operator runs, without switching profiles.
- **Test:** NFV (multiple real profiles) — manual regression R-03.

#### UC-004 — Slash command in chat, no model turn

- **Trigger:** Interactive — `/quota`, `/quota local`, `/quota <profile>`, `/quota --days N` in Desktop, TUI or gateway chat.
- **Actor:** the operator.
- **Preconditions:** SET-001 in the profile whose chat is used; SET-002 in each profile that should show limits.
- **Flow:** the host dispatches the plugin slash command (`tui_gateway/methods_tools.py` / gateway) → `usage_core.run(scope)` → text returned directly, no LLM call.
- **Outcome (value / function achieved):** instant multi-profile report in the chat surface the operator already has open; works in Desktop where the built-in `/usage` shows no Codex limits (KE-2026-09-20-DESKTOP-USAGE-NO-LIMITS).
- **Test:** NFV (needs a running chat surface) — manual regression R-07; handler registration and output verified in-process (R-08).

#### UC-005 — Providers used in the last N days are reported automatically

- **Trigger:** Automatic — every report (tool, slash, CLI) reads `state.db` of each profile.
- **Actor:** `usage_core.activity()`.
- **Preconditions:** none beyond SET-001 (works without login: activity is local).
- **Flow:** read-only SQLite query over `session_model_usage` (`last_seen > now − N days`, aux providers excluded) → per provider: calls, models, spend (actual if the host recorded it, else estimate), billing mode → each active provider gets its own block with `kind` windows/balance/spend.
- **Outcome (value / function achieved):** the report covers what was actually used (e.g. OpenRouter under a Codex-primary profile) without the operator listing providers by hand; pay-as-you-go providers get a spend figure instead of a fake percentage.
- **Test:** covered — `tests/test_usage_core.py` (`classify`, `extract_balance`, `breaches`, `render_all`); the SQL path itself is NFV (live database) — manual R-09.

#### UC-006 — Optional threshold watchdog

- **Trigger:** Automatic — Hermes cron job `quota-watch` (`--no-agent`), created only with `install.py --watchdog EVERY [--deliver telegram|local]`.
- **Actor:** `quota_watch.py` in `<HERMES_HOME>/scripts/`.
- **Preconditions:** SET-001, SET-003.
- **Flow:** all-profiles report → `breaches()` against `plugins.entries.account-usage.settings` → prints only on a breach, once per breach-set per 24 h (state in `state/quota_watch_state.json`), plus one "all clear" line when the breach clears → cron delivers non-empty stdout to the chosen target.
- **Outcome (value / function achieved):** the operator learns about a dying token, an exhausted weekly window or a depleted balance without asking; no pushes when nothing changed.
- **Test:** NFV (cron scheduling, delivery) — manual R-10; threshold logic covered by `test_breach_*`.

#### UC-007 — Readable report in the Desktop UI

- **Trigger:** Interactive — the operator opens the `quota` pane in Hermes Desktop (right dock) or presses ↻; Automatic — refresh every 5 minutes while open.
- **Actor:** `desktop/account-usage/plugin.js` (Desktop runtime plugin).
- **Preconditions:** SET-001 in the profile the Desktop backend runs; SET-004.
- **Flow:** pane → `host.request('cli.exec', {argv: ['usage','--json']})` → backend runs `hermes usage --json` in the active profile → JSON reports → progress bars per window (colour by remaining %), balances, ⚠ alerts, per-model activity.
- **Outcome (value / function achieved):** the same numbers as `/quota`, but readable: full-contrast UI instead of the dim 11px system line Desktop uses for slash output (KE-2026-09-20-DESKTOP-SLASH-OUTPUT-DIM).
- **Test:** NFV (Electron UI) — manual regression R-11; data path covered by the CLI tests.

---

## Not functionally verifiable — keep in mind during development

| Case | Why it is NFV | How it is actually checked | Development constraint to preserve |
|---|---|---|---|
| UC-001 | needs a live OAuth token and the provider's usage endpoint | manual regression R-01 | the tool must return text (never raise) when the token is expired or the provider unknown |
| UC-002 | same | manual regression R-02 | `--json` output must stay parseable and token-free |
| UC-003 | needs several real profiles | manual regression R-03 | a failing profile must not hide the others |
| UC-004 | needs a running chat surface (Desktop/TUI/gateway) | manual R-07 + in-process handler check R-08 | `/quota` must never call the model |
| UC-006 | cron scheduling and delivery are host behaviour | manual R-10 | silent when nothing breached; one message per breach-set per day |
| UC-007 | Electron UI rendering | manual R-11 | pane must never block the app: every fetch error renders inline |

## Traceability

| Case | Trigger | Requirement | Architecture component | Test |
|---|---|---|---|---|
| UC-001 | Interactive | FR-001, FR-004, NFR-001 | `__init__.py`, `usage_core.collectors` | NFV |
| UC-002 | Interactive | FR-002, NFR-002 | `__init__.py`, `usage_core.collectors` | NFV |
| UC-003 | Interactive | FR-003, NFR-002 | `usage_core.all_profiles_reports` | NFV |
| UC-004 | Interactive | FR-007 | `__init__.py` (`register_command`) | NFV |
| UC-005 | Automatic | FR-008, FR-009 | `usage_core.activity`, `classify`, `extract_balance` | covered |
| UC-006 | Automatic | FR-005 | `quota_watch.py`, `install.py` | NFV |
| UC-007 | Interactive | FR-010 | `desktop/account-usage/plugin.js` | NFV |
