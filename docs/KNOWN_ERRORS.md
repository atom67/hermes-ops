# Known errors — Hermes Account Usage Plugin

**What this is:** every known bug, limitation, and piece of technical debt.
**Read it before** "fixing" anything or explaining odd behaviour — the thing may already
be recorded, with a workaround and a reason.
**Update when:** any bug or limitation is found, during development, testing, or review.
See `AGENTS.md` section 3.

## Entry format

Identifier: `KE-YYYY-MM-DD-SHORT-SLUG`. Stable, so code comments can quote it — that is
how the reason for a non-obvious defence survives the next refactor.

```
### KE-2026-01-31-EXAMPLE-SLUG — one-line summary

**Where:** path/to/file.ext:123
**Introduced / detected:** commit or unknown / date and evidence
**Impact:** what the user or the data actually loses. Not "it is wrong" — what breaks.
**Cause:** the mechanism, in one or two sentences.
**Status:** not fixed / fixed in <commit or version>
**Workaround:** what to do until it is fixed, or "none".
**Verification:** regression test, observed result and coverage limitations
```

Rules:

- A fixed entry is **marked** fixed, with the commit or version. It is not deleted:
  the same mistake gets made again, and the record is what makes it recognisable.
- State the affected scope precisely. A local fix is not proof every consumer is fixed.
  Separate confirmed defects, hypotheses and accepted risks; do not invent dates.
- If a defence in the code exists because of an entry here, the code comment names the ID.

## Open

### KE-YYYY-MM-DD-... — ...

**Where:**
**Introduced / detected:**
**Impact:**
**Cause:**
**Status:** not fixed
**Workaround:**
**Verification:**

## Fixed

### KE-YYYY-MM-DD-... — ...

**Status:** fixed in ...

### KE-2026-09-19-AGENT-QUOTA-ARCHAEOLOGY — agent needs 20 tool calls to answer a quota question without this plugin
**Where:** Hermes core v0.20.0 — `/usage` is a user slash command; no agent tool, no `hermes usage` CLI (also absent on upstream main, checked 2026-09-19)
**Introduced / detected:** detected 2026-09-19, `D:\DEV\Hermes\docs\research\gpt-account-limit-answer-audit.md`
**Impact:** 449 s, 17 model cycles, 20 tool calls, source-code reading and JWT parsing by the model for a one-line answer
**Cause:** capability exists only on the user-facing surface; the bundled `hermes-agent` skill points to "the internal account usage mechanism" without naming a command
**Status:** worked around by this plugin (2 calls / 56 s); root cause open upstream
**Workaround:** install this plugin; or type `/usage` yourself
**Verification:** end-to-end run on `mastermind`, session `20260919_212926_ad1a57`

### KE-2026-09-19-SUBPROCESS-CP1251 — `--all-profiles` printed a replacement character instead of the middle dot on Windows
**Where:** `plugin/account-usage/usage_core.py` (`all_profiles_reports`)
**Introduced / detected:** first `--all-profiles` run, 2026-09-19
**Impact:** cosmetic mojibake in per-profile headers when the child process used the console code page
**Cause:** `subprocess.run(text=True)` decoded stdout with the locale encoding (cp1251) while the child printed UTF-8
**Status:** fixed in v0.1 (`encoding="utf-8"` + `PYTHONIOENCODING=utf-8` for the child)
**Workaround:** none needed
**Verification:** re-run of `--all-profiles`; no automated test (needs a Windows console)

### KE-2026-09-19-PROVIDER-WITHOUT-FETCHER — providers other than openai-codex/anthropic/openrouter/nous report `unavailable`
**Where:** `plugin/account-usage/usage_core.py` (`usage_for`)
**Introduced / detected:** design limitation, 2026-09-19 (the `default` profile on `nous` first showed "no snapshot" before the Nous credits branch was added)
**Impact:** a profile on gemini/kimi/copilot etc. gets no numbers
**Cause:** the host's `fetch_account_usage` covers three providers; we deliberately add no fetchers of our own
**Status:** accepted limitation
**Workaround:** `rarf/hermes-quota-plugin` covers 9 providers
**Verification:** message text asserted by `test_unavailable_snapshot_renders_reason`

### KE-2026-09-20-DESKTOP-USAGE-NO-LIMITS — Desktop `/usage` shows no account limits for openai-codex
**Where:** Hermes Desktop 0.20.0 (backend v0.20.0), `/usage` slash command in chat
**Introduced / detected:** detected 2026-09-20 by the owner during UC-001 acceptance (screenshot); matches upstream issues #45713 and #42904 (open)
**Impact:** in Desktop the operator cannot see Codex Session/Weekly windows at all without this plugin — `/usage` prints "Session Token Usage" with zeros before any agent turn and no Account limits block
**Cause:** upstream: the Desktop `/usage` no-agent path omits the account-usage fetch (per #42904 title); not investigated here
**Status:** not fixed upstream; worked around by asking the agent (tool `account_usage`)
**Workaround:** ask the agent in chat, or run `hermes -p <profile> usage`
**Verification:** manual, regression R-06; candidate for an upstream bug report with this repro

### KE-2026-09-20-DESKTOP-SLASH-OUTPUT-DIM — Desktop renders every slash-command result at 11px and 60 % opacity
**Where:** Hermes Desktop 0.20.0, `apps/desktop/src/components/assistant-ui/thread/system-message.tsx:47-49` (`text-[0.6875rem] text-muted-foreground/60 w-[60%]`)
**Introduced / detected:** detected 2026-09-20 by the owner (`/usage` and `/quota` output barely readable)
**Impact:** multi-line command output (usage tables, quota reports) is hard to read; plain text only, no markdown
**Cause:** one style for all system lines, designed for one-line statuses; the code comment acknowledges multiline output needs more room but keeps the colour/size
**Status:** not fixed upstream; worked around by the Desktop pane (v0.3) and by asking the agent in words
**Workaround:** open the `quota` pane, or ask the agent — a normal assistant bubble
**Verification:** manual; candidate upstream PR: full colour and 12–13 px for multiline output
