# Architecture — Hermes Account Usage Plugin

**What this is:** how the system is put together — components, data schema, data flows.
**Update when:** the data schema changes, tables or migrations are added, new services or
components appear, or data flows change. See `AGENTS.md` section 3.

**Sibling of `USE_CASES.md`.** This file says how the system is built; `USE_CASES.md` says
what value it delivers and how each path is exercised.

**Schema authority:** N/A — the plugin has no database and no migrations. The only
versioned contract is the report JSON produced by `usage_core.report()` (below) and the
plugin version in `plugin/account-usage/plugin.yaml`.

## Components

| Component | Responsibility | Depends on |
|---|---|---|
| `plugin.yaml` | manifest: name, version, description; loader gates it by `plugins.enabled` | Hermes plugin loader (`hermes_cli/plugins.py`) |
| `__init__.py` → `register(ctx)` | registers tool `account_usage(scope)`, slash command `/quota`, CLI `hermes usage` | `ctx.register_tool`, `ctx.register_command`, `ctx.register_cli_command` |
| `usage_core.activity` | providers used in the last N days per profile, from `state.db` (`session_model_usage`, read-only `mode=ro`) | sqlite3 |
| `usage_core.classify` / `extract_balance` / `breaches` | provider kind (windows / balance / spend), prepaid balance from host lines, threshold checks | pure |
| `quota_watch.py` (optional) | cron `--no-agent` script: `watch_scope` profile (own report) or all (deduped all-profiles report) → `watch_targets` top-N by calls → breaches → print once per breach-set per day | `usage_core`, `state/quota_watch_state.json`, settings `watch_scope`/`watch_top`/`balance_min` |
| `usage_core.dedupe` / `_quota_signature` / `watch_targets` | mark identical accounts across profiles (`same_as`), rank providers by calls for the watchdog | pure |
| `usage_core.usage_for_xai` / `xai_windows` | the one provider fetched by the plugin itself: Grok CLI billing proxy with the stored `xai-oauth` bearer → weekly window | `hermes_cli.auth.resolve_xai_oauth_runtime_credentials`, `urllib` |
| `desktop/account-usage/plugin.js` | Hermes Desktop runtime plugin: pane `quota` (focus strip, alerts, per-profile cards); data via `host.request('cli.exec', ['usage','--json'])` | `@hermes/plugin-sdk`, React singleton of the app |
| `usage_core.pure` (`jwt_claims`, `pick_identity`, `find_jwts`, `snapshot_to_dict`, `render`) | testable transformations; no I/O | stdlib |
| `usage_core.collectors` (`active_provider`, `codex_identity`, `usage_for`, `report`) | read host config + token store, call host fetchers; fail soft | `hermes_cli.config.load_config`, `hermes_cli.auth._read_codex_tokens` / `resolve_codex_runtime_credentials`, `agent.account_usage.fetch_account_usage` / `render_account_usage_lines` / `nous_credits_lines` |
| `usage_core.all_profiles_reports` | one subprocess per profile with its own `HERMES_HOME` | `sys.executable`, `PYTHONPATH` = host package dir |
| `install.py` | plug-and-play copy + `plugins.enabled` text patch with backup | filesystem only |

## Data schema

No tables. Report object (one per profile):

| Field | Type | Notes |
|---|---|---|
| `profile` | string | profile directory name, or `default` |
| `primary` | string \| null | the profile's `model.provider` |
| `days` | int | activity window |
| `providers[]` | block per provider: `provider`, `kind` (windows\|balance\|spend), `identity`, `usage`, `activity` | primary first, then providers seen in `state.db` |
| `providers[].activity` | `{days, calls, models, billing_mode, spend_usd, cost_source, last_seen}` | `spend_usd` = actual if recorded else estimate; `last_seen` ISO-8601 local, minutes |
| `providers[].usage.balance_usd` | number \| null | parsed from host lines (`Credits balance: $X`, `Total usable: $X`) |
| `providers[].same_as` | string (optional) | profile whose block already shows this account (same provider + account id, or same numbers when no identity); text/pane show a one-line pointer, `breaches()` skips it |
| `providers[].usage.not_fetchable` | bool (optional) | capability gap of the host, not an alert |
| `provider` | string \| null | `model.provider` of that profile or the `--provider` override |
| `identity` | object | subset of `email`, `email_verified`, `name`, `chatgpt_plan_type`, `plan_type`, `chatgpt_account_id`; only for `openai-codex`; never tokens |
| `usage.available` | bool | windows or details present and no `unavailable_reason` |
| `usage.windows[]` | `{label, used_percent, reset_at, detail}` | `reset_at` ISO-8601 with offset, e.g. `2026-09-19T15:24:00+00:00` |
| `usage.lines[]` | string[] | host-rendered lines (same text as `/usage`) |
| `usage.unavailable_reason` | string \| null | e.g. `token_expired`, `provider 'x' has no account-usage fetcher in this Hermes version` |
| `error` | string (optional) | report-level failure (no provider, subprocess failure) |

### Migration history

N/A. A change to the report shape bumps `plugin.yaml` version and is noted in docs/RELEASE.md.

## Data flows

1. **Agent path:** model calls `account_usage(provider?, all_profiles?)` → registry dispatches
   `_tool_handler(args)` → `usage_core.report()` → host fetcher performs one HTTPS GET to the
   provider usage endpoint with the profile's OAuth token → `render()` → text returned to the
   model. No source-code reading, no shell.
2. **CLI path:** `hermes -p <profile> usage [--json]` → same as (1) in-process.
3. **All profiles:** the CLI/tool spawns `python usage_core.py --json` once per profile home
   (`<root>` + `<root>/profiles/*` having `config.yaml`) with `HERMES_HOME` set; results are
   concatenated, then `dedupe()` marks repeated accounts. Each child resolves its own config, tokens and provider.
4. **Watchdog:** cron (`every N`, `--no-agent`) → `quota_watch.py` → (1) or (3) by `watch_scope` → top-N providers by calls → `breaches()` → non-empty stdout only on a new breach-set → cron delivery target.
5. **Desktop pane:** `cli.exec` in the *active* profile → `hermes usage --json` → JSON parsed from the first bare `[` line → focus strip (5h / weekly % left per deduped source, balance for prepaid) → alerts → cards. The `usage` command must exist in every profile the Desktop may activate — hence `install.py` with no target installs into every home.
6. **xai-oauth:** `usage_for_xai()` resolves the bearer through the host, one HTTPS GET to `cli-chat-proxy.grok.com/v1/billing?format=credits` with `X-XAI-Token-Auth: xai-grok-cli`, maps `creditUsagePercent`/`currentPeriod` to a `Weekly` window. The token is used in the request header only and never rendered.

## Decisions

| Decision | Rationale | Alternatives | Reversal trigger |
|---|---|---|---|
| Reuse host fetchers instead of own HTTP | same numbers as `/usage`, zero maintenance of provider quirks | own fetchers (as `rarf/hermes-quota-plugin`) | host removes/renames `agent.account_usage` |
| Exception: own fetcher for `xai-oauth` (v0.4) | core has none; upstream PR #114949 open; the grok-cli billing proxy is the only source of the weekly pool | wait for upstream; show `not fetchable` | PR #114949 merged into the installed Hermes → delete `usage_for_xai`, host fetcher takes over |
| Dedupe by account id first, numbers second | rendered lines drift between per-profile fetches (`resets in 43m` / `42m`) and broke matching | compare full usage dict | a provider exposes an identity we do not read |
| Watchdog top-N by call count, idle providers excluded | "channels used last week" is what the owner wants watched; an idle $0 balance is noise | watch every configured provider | owner sets `watch_top: all` |
| Pane data via `cli.exec` subprocess | the only SDK door without a backend REST route; ~6 s per refresh at 5-min cadence | `ctx.rest` route in the backend plugin | refresh < 30 s or > 10 profiles |
| Identity from JWT claims, decoded without verification | the only place email/plan exist locally; verification is pointless for display | `hermes auth status` (does not show identity) | host starts exposing identity in `auth status` |
| Subprocess per profile | `HERMES_HOME` is resolved process-wide by the host; isolation without touching host internals | context-local override `set_hermes_home_override` | >10 profiles or latency complaints |
| Text patch of `config.yaml` in installer | preserves comments; PyYAML round-trip would rewrite the file | `hermes config set` (no list support verified) | host offers `hermes plugins enable <name>` for user plugins |
