"""Pure-function tests for usage_core — no Hermes, no network, synthetic data only."""
import base64
import importlib.util
import json
import unittest
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

CORE = Path(__file__).resolve().parents[1] / "plugin" / "account-usage" / "usage_core.py"
spec = importlib.util.spec_from_file_location("usage_core_under_test", CORE)
uc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uc)


def fake_jwt(payload: dict) -> str:
    b64 = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return f"{b64({'alg': 'none'})}.{b64(payload)}.sig"


@dataclass(frozen=True)
class Window:
    label: str
    used_percent: float = None
    reset_at: datetime = None
    detail: str = None


@dataclass(frozen=True)
class Snapshot:
    provider: str
    source: str
    fetched_at: datetime
    plan: str = None
    windows: tuple = field(default_factory=tuple)
    details: tuple = field(default_factory=tuple)
    unavailable_reason: str = None


class JwtAndIdentity(unittest.TestCase):
    def test_claims_decoded_from_namespaced_payload(self):
        token = fake_jwt({"exp": 1, "https://api.openai.com/profile": {"email": "user@example.com"},
                          "https://api.openai.com/auth": {"chatgpt_plan_type": "plus", "chatgpt_account_id": "acc_1"}})
        identity = uc.pick_identity(uc.jwt_claims(token))
        self.assertEqual(identity, {"email": "user@example.com", "chatgpt_plan_type": "plus", "chatgpt_account_id": "acc_1"})

    def test_non_jwt_strings_are_ignored(self):
        self.assertEqual(uc.jwt_claims("not.a.jwt"), {})
        self.assertEqual(uc.jwt_claims("sk-plainkey"), {})
        self.assertEqual(uc.find_jwts({"tokens": {"first": "abc", "n": 1}}), [])

    def test_find_jwts_walks_nested_structures(self):
        token = fake_jwt({"email": "user@example.com"})
        found = uc.find_jwts({"tokens": {"first": token, "other": "rt"}, "pool": [{"nested": token}]})
        self.assertEqual(found, [token, token])


class SnapshotAndRender(unittest.TestCase):
    def test_snapshot_dates_become_iso_and_available_flag_set(self):
        reset = datetime(2026, 9, 19, 15, 24, tzinfo=timezone.utc)
        snap = Snapshot("openai-codex", "codex", reset, plan="plus", windows=(Window("Weekly", 84.0, reset),))
        data = uc.snapshot_to_dict(snap)
        self.assertTrue(data["available"])
        self.assertEqual(data["windows"][0]["reset_at"], "2026-09-19T15:24:00+00:00")

    def test_unavailable_snapshot_renders_reason(self):
        text = uc.render({"profile": "p", "providers": [{"provider": "openai-codex", "kind": "windows", "identity": {},
                          "usage": {"available": False, "unavailable_reason": "token_expired"}}]})
        self.assertIn("unavailable (token_expired)", text)

    def test_render_prefers_core_lines_and_shows_identity(self):
        text = uc.render({"profile": "mastermind", "providers": [{"provider": "openai-codex", "kind": "windows",
                          "identity": {"email": "user@example.com", "chatgpt_plan_type": "plus"},
                          "usage": {"available": True, "lines": ["Weekly: 16% remaining"]},
                          "activity": {"days": 7, "calls": 7, "models": {"gpt-5.6-terra": {"calls": 7, "usd": 0.0}},
                                       "spend_usd": 0.0, "cost_source": "included in subscription"}}]})
        self.assertEqual(text.splitlines(), ["Profile: mastermind",
                                             "openai-codex [windows] · user@example.com (plus)",
                                             "  Weekly: 16% remaining",
                                             "  last 7d: 7 calls · included in subscription",
                                             "    gpt-5.6-terra: 7 calls"])

    def test_cost_label_and_spend_text(self):
        self.assertEqual(uc.cost_label("subscription_included", 0.0, 0.0), "included in subscription")
        self.assertEqual(uc.cost_label("", 0.0, 0.0), "no pricing data")
        self.assertEqual(uc.cost_label("", 0.0, 0.98), "estimate, local accounting")
        self.assertEqual(uc.cost_label("", 1.5, 9.9), "actual")
        self.assertEqual(uc.spend_text({"cost_source": "no pricing data", "spend_usd": 0.0}), "cost n/a (no pricing data)")
        self.assertEqual(uc.spend_text({"cost_source": "actual", "spend_usd": 1.5}), "$1.50 (actual)")
        self.assertEqual(uc.classify("xai-oauth", {}, "codex_responses"), "windows")

    def test_render_never_leaks_tokens(self):
        token = fake_jwt({"email": "user@example.com"})
        report = {"profile": "p", "providers": [{"provider": "openai-codex", "kind": "windows",
                  "identity": uc.pick_identity(uc.jwt_claims(token)),
                  "usage": {"available": False, "unavailable_reason": "offline"}}]}
        self.assertNotIn(token, uc.render(report))
        self.assertNotIn(token, json.dumps(report))


class KindsAndThresholds(unittest.TestCase):
    S = dict(uc.DEFAULT_SETTINGS, budget_usd=20)

    def test_classify_windows_balance_spend(self):
        self.assertEqual(uc.classify("openai-codex", {"windows": [{"label": "Weekly"}]}), "windows")
        self.assertEqual(uc.classify("anthropic", {}, "subscription_included"), "windows")
        self.assertEqual(uc.classify("openrouter", {"details": ["Credits: $12.30"]}), "balance")
        self.assertEqual(uc.classify("nous", {}), "balance")
        self.assertEqual(uc.classify("gemini", {}), "spend")

    def test_breach_weekly_below_floor_and_session_ok(self):
        block = {"provider": "openai-codex", "kind": "windows",
                 "usage": {"windows": [{"label": "Weekly", "used_percent": 90.0}, {"label": "Session", "used_percent": 50.0}]}}
        out = uc.breaches(block, self.S)
        self.assertEqual(len(out), 1)
        self.assertIn("Weekly: 10% remaining (< 15%)", out[0])

    def test_extract_balance_from_host_lines(self):
        self.assertEqual(uc.extract_balance({"lines": ["Credits balance: $17.30", "x"]}), 17.30)
        self.assertEqual(uc.extract_balance({"details": ["Total usable: $0.00"]}), 0.0)
        self.assertEqual(uc.extract_balance({"lines": ["API key quota: 79% remaining"]}), None)

    def test_breach_balance_and_spend_and_unavailable(self):
        low = {"provider": "openrouter", "kind": "balance", "usage": {"balance_usd": 2.5}}
        self.assertIn("balance $2.50", uc.breaches(low, self.S)[0])
        spend = {"provider": "gemini", "kind": "spend", "usage": {}, "activity": {"spend_usd": 25.0}}
        self.assertIn("spend $25.00", uc.breaches(spend, self.S)[0])
        dead = {"provider": "openai-codex", "kind": "windows", "usage": {"unavailable_reason": "token_expired"}}
        self.assertIn("token_expired", uc.breaches(dead, self.S)[0])
        self.assertEqual(uc.breaches({"provider": "gemini", "kind": "spend", "usage": {}, "activity": {}}, self.S), [])
        gap = {"provider": "xai-oauth", "kind": "windows", "usage": {"unavailable_reason": "not fetchable", "not_fetchable": True}}
        self.assertEqual(uc.breaches(gap, self.S), [])

    def test_render_all_lists_alerts_then_profiles(self):
        reports = [{"profile": "a", "providers": [{"provider": "openai-codex", "kind": "windows",
                    "usage": {"available": True, "lines": ["Weekly: 5% remaining"], "windows": [{"label": "Weekly", "used_percent": 95}]},
                    "activity": {"days": 7, "calls": 3, "models": {"m": {"calls": 3, "usd": 0.0}}, "spend_usd": 0.0, "cost_source": "included in subscription"}}]},
                   {"profile": "b", "providers": [], "error": "no such profile"}]
        text = uc.render_all(reports, uc.DEFAULT_SETTINGS)
        self.assertTrue(text.startswith("Account usage — 2 profile(s) · 1 alert(s)"))
        self.assertIn("⚠ a/openai-codex Weekly: 5% remaining", text)
        self.assertIn("Profile: a", text)
        self.assertIn("Error: no such profile", text)

    def test_per_provider_balance_floor_in_credits_or_usd(self):
        nous = {"provider": "nous", "kind": "balance", "usage": {"balance_usd": 50.0}}
        self.assertEqual(uc.breaches(nous, self.S), [])                       # default floor 5
        self.assertIn("balance $50.00 (< $100)", uc.breaches(nous, {**self.S, "balance_min": {"nous": 100}})[0])

    def test_dedupe_marks_identical_quota_and_mutes_its_alerts(self):
        codex = {"provider": "openai-codex", "kind": "windows", "identity": {"chatgpt_account_id": "acc"},
                 "usage": {"available": True, "windows": [{"label": "Weekly", "used_percent": 95}]},
                 "activity": {"days": 7, "calls": 10}}
        reports = [{"profile": "a", "providers": [codex]},
                   {"profile": "b", "providers": [{**codex, "activity": {"days": 7, "calls": 30}}]},
                   {"profile": "c", "providers": [{**codex, "usage": {"available": True, "windows": [{"label": "Weekly", "used_percent": 10}]}}]}]
        out = uc.dedupe(reports)
        self.assertNotIn("same_as", out[0]["providers"][0])
        self.assertEqual(out[1]["providers"][0]["same_as"], "a")
        self.assertEqual(out[2]["providers"][0]["same_as"], "a")               # same account id wins even if numbers drifted between fetches
        anon = {"provider": "openrouter", "kind": "windows", "usage": {"lines": ["resets in 43m"], "windows": [{"label": "Key", "used_percent": 21}]}}
        drift = {**anon, "usage": {"lines": ["resets in 42m"], "windows": [{"label": "Key", "used_percent": 21}]}}
        other = {**anon, "usage": {"windows": [{"label": "Key", "used_percent": 50}]}}
        anon_out = uc.dedupe([{"profile": "x", "providers": [anon]}, {"profile": "y", "providers": [drift, other]}])
        self.assertEqual(anon_out[1]["providers"][0]["same_as"], "x")           # no identity: same numbers, drifting text
        self.assertNotIn("same_as", anon_out[1]["providers"][1])                # different numbers = different key
        self.assertEqual(out[1]["providers"][0]["activity"]["calls"], 30)        # activity stays per profile
        self.assertEqual(uc.breaches(out[1]["providers"][0], self.S), [])
        self.assertIs(reports[1]["providers"][0].get("same_as"), None)          # input untouched
        text = uc.render_all(reports, self.S)
        self.assertEqual(text.count("⚠ "), 1)
        self.assertIn("same account as profile 'a'", text)

    def test_xai_billing_payload_becomes_weekly_window(self):
        payload = {"config": {"currentPeriod": {"type": "USAGE_PERIOD_TYPE_WEEKLY", "end": "2026-09-22T06:41:56+00:00"},
                              "creditUsagePercent": 36.0, "productUsage": [{"product": "GrokBuild", "usagePercent": 36.0}],
                              "prepaidBalance": {"val": 0}}}
        u = uc.xai_windows(payload)
        self.assertTrue(u["available"])
        self.assertEqual(u["windows"], [{"label": "Weekly", "used_percent": 36.0, "reset_at": "2026-09-22T06:41:56+00:00"}])
        self.assertIn("Weekly: 64% remaining (36% used)", u["lines"][2])
        self.assertIn("GrokBuild: 36% used", u["lines"][3])
        self.assertFalse(uc.xai_windows({"config": {}})["available"])
        self.assertIn("10% remaining", uc.breaches({"provider": "xai-oauth", "kind": "windows", "usage": {**u, "windows": [{"label": "Weekly", "used_percent": 90}]}}, self.S)[0])

    def test_watch_targets_top_n_or_all(self):
        reports = [{"profile": "a", "providers": [{"provider": "openai-codex", "activity": {"calls": 5}},
                                                  {"provider": "nous", "activity": {"calls": 0}}]},
                   {"profile": "b", "providers": [{"provider": "openrouter", "activity": {"calls": 3}},
                                                  {"provider": "openai-codex", "activity": {"calls": 4}}]}]
        self.assertEqual(uc.watch_targets(reports, 2), ["openai-codex", "openrouter"])
        self.assertEqual(uc.watch_targets(reports, 4), ["openai-codex", "openrouter"])  # idle providers are not channels
        self.assertEqual(uc.watch_targets(reports, "all"), ["openai-codex", "openrouter", "nous"])
        self.assertEqual(uc.watch_targets(reports, None), ["openai-codex", "openrouter", "nous"])
