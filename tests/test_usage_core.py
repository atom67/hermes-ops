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
        text = uc.render({"profile": "p", "provider": "openai-codex", "identity": {},
                          "usage": {"available": False, "unavailable_reason": "token_expired"}})
        self.assertIn("unavailable (token_expired)", text)

    def test_render_prefers_core_lines_and_shows_identity(self):
        text = uc.render({"profile": "mastermind", "provider": "openai-codex",
                          "identity": {"email": "user@example.com", "chatgpt_plan_type": "plus"},
                          "usage": {"available": True, "lines": ["Weekly: 16% remaining"]}})
        self.assertEqual(text.splitlines(), ["Profile: mastermind · provider: openai-codex",
                                             "Account: user@example.com (plus)", "Weekly: 16% remaining"])

    def test_render_never_leaks_tokens(self):
        token = fake_jwt({"email": "user@example.com"})
        report = {"profile": "p", "provider": "openai-codex", "identity": uc.pick_identity(uc.jwt_claims(token)),
                  "usage": {"available": False, "unavailable_reason": "offline"}}
        self.assertNotIn(token, uc.render(report))
        self.assertNotIn(token, json.dumps(report))


if __name__ == "__main__":
    unittest.main()
