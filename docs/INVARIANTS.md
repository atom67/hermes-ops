# Product invariant register

An invariant is a product property that must remain true across ordinary entry points,
failures and supported restarts. Read the [recipe](../.devframework/patterns/entry-point-invariants.md).
Populate applicable rows during design; examples are not implemented coverage.

| ID | Requirement / invariant | Owner and effect boundary | Entry points / consumers | Denial, crash and bypass test | Evidence / limits |
|---|---|---|---|---|---|
| INV-001 | No token, API key or refresh token ever appears in any output of the plugin (text, JSON, pane, cron stdout, logs) — only non-secret JWT claims | `usage_core` (render, JSON, xai fetcher) | agent tool, `/quota`, `hermes usage --json`, `quota_watch.py`, Desktop `cli.exec` | `test_render_never_leaks_tokens` renders a report containing JWT-shaped strings in every field and asserts none survive; xai bearer is used in a request header only (`usage_for_xai`) | covered for render/JSON; cron and pane reuse the same JSON (no separate path); host stderr on exceptions is truncated to 300 chars and could echo a host message — not a token by construction, not tested |
| INV-002 | A failing provider or profile never hides the others and never raises out of the plugin | `usage_for`, `provider_block`, `all_profiles_reports` | same as INV-001 | `test_unavailable_snapshot_renders_reason`, `test_render_all_lists_alerts_then_profiles` (profile with `error`), R-03 | subprocess timeout 40 s per profile is the ceiling |
| INV-003 | An account is alerted once, whatever the number of profiles logged into it | `dedupe`, `breaches` | `/quota`, watchdog, pane | `test_dedupe_marks_identical_quota_and_mutes_its_alerts` | identity-less providers rely on equal numbers; a percentage that changes between two fetches yields a second alert once |

Use stable INV-NNN IDs for real rows. Link tests instead of copying source. For exceptions
record scope, product approval and a distinguishing path name. New adapters/shared rules
trigger a review. Discovery of entry points is stack-specific, not provided by this package.
