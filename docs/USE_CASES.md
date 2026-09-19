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
| SET-001 | Plugin installed and enabled: `python install.py --profile <name>` copies `plugin/account-usage` to `<HERMES_HOME>/plugins/` and adds `account-usage` to `plugins.enabled`; restart the profile's gateway/TUI/Desktop | project root / profile `config.yaml` | required | UC-001, UC-002, UC-003 |
| SET-002 | Provider login of the profile (`hermes -p <name> auth login openai-codex` etc.) — the plugin reads the resulting token store, it never logs in itself | Hermes auth | required for limits; without it the report says `unavailable` | UC-001, UC-002, UC-003 |

---

## Modules

### Module: Account limits

**Value this module delivers:** the operator (or the agent on their behalf) learns which
account is in use and how much quota remains, in one step, without reading source code.
**Architecture components involved:** `usage_core.collectors`, `usage_core.pure`,
`__init__.py → register(ctx)` (docs/ARCHITECTURE.md → Components).

#### UC-001 — Agent answers a quota question with one tool call

- **Trigger:** Interactive — the user asks the agent about limits, remaining usage or the account in use.
- **Actor:** the agent (model) calling tool `account_usage`.
- **Preconditions:** SET-001, SET-002.
- **Flow:** model calls `account_usage` (optionally `provider`) → `report()` reads `model.provider`, decodes identity claims, calls the host fetcher (one HTTPS GET to the provider usage endpoint) → rendered text returned → model answers.
- **Outcome (value / function achieved):** the answer arrives in one model turn; 2026-09-19 measurement: 2 tool calls / 56 s versus 20 calls / 449 s without the plugin.
- **Test:** NFV (needs a real OAuth token and provider network) — manual regression R-01; the pure transformations are covered by `tests/test_usage_core.py`.

#### UC-002 — Operator checks limits from the shell

- **Trigger:** Interactive — `hermes -p <profile> usage [--provider X] [--json]`.
- **Actor:** the operator or a script.
- **Preconditions:** SET-001, SET-002.
- **Flow:** CLI handler → `report()` → text or JSON on stdout; exit code 1 when the report carries `error`.
- **Outcome (value / function achieved):** scripts and cron jobs get the same numbers as `/usage` without an agent turn.
- **Test:** NFV (real token/network) — manual regression R-02; JSON shape guarded by `test_snapshot_dates_become_iso_and_available_flag_set`.

#### UC-003 — All profiles at once

- **Trigger:** Interactive — `hermes usage --all-profiles` or tool argument `all_profiles=true`.
- **Actor:** the operator or the agent.
- **Preconditions:** SET-001 in the calling profile; SET-002 in each profile that should show limits.
- **Flow:** `all_profiles_reports()` spawns `usage_core.py --json` per profile home with its own `HERMES_HOME`; failures become per-profile `error` rows; results are concatenated.
- **Outcome (value / function achieved):** one view of every account/provider the operator runs, without switching profiles.
- **Test:** NFV (multiple real profiles) — manual regression R-03.

---

## Not functionally verifiable — keep in mind during development

| Case | Why it is NFV | How it is actually checked | Development constraint to preserve |
|---|---|---|---|
| UC-001 | needs a live OAuth token and the provider's usage endpoint | manual regression R-01 | the tool must return text (never raise) when the token is expired or the provider unknown |
| UC-002 | same | manual regression R-02 | `--json` output must stay parseable and token-free |
| UC-003 | needs several real profiles | manual regression R-03 | a failing profile must not hide the others |

## Traceability

| Case | Trigger | Requirement | Architecture component | Test |
|---|---|---|---|---|
| UC-001 | Interactive | FR-001, FR-004, NFR-001 | `__init__.py`, `usage_core.collectors` | NFV |
| UC-002 | Interactive | FR-002, NFR-002 | `__init__.py`, `usage_core.collectors` | NFV |
| UC-003 | Interactive | FR-003, NFR-002 | `usage_core.all_profiles_reports` | NFV |
