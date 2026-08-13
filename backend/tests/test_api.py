"""API layer tests - only runnable where fastapi/httpx are installed.

This sandbox cannot `pip install` anything (PyPI is network-blocked, see
PHASE2_NOTES.md's precedent for nautilus_trader) so these are skipped
locally and verified for real by the `backend-api-tests` CI job instead
(.github/workflows/ci.yml) - the same "write it for real, verify via CI"
pattern already used for nautilus_trader in Phase 2.
"""

from __future__ import annotations

import importlib.util
import unittest

_HAS_FASTAPI = (
    importlib.util.find_spec("fastapi") is not None and importlib.util.find_spec("httpx") is not None
)


@unittest.skipUnless(_HAS_FASTAPI, "fastapi/httpx not installed in this environment")
class TestApi(unittest.TestCase):
    def setUp(self) -> None:
        from fastapi.testclient import TestClient

        from app.api.main import app

        self.client = TestClient(app)

    def test_health(self) -> None:
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "ok"})

    def test_list_strategies_returns_all_registered(self) -> None:
        from app.api.registry import STRATEGY_REGISTRY

        resp = self.client.get("/api/strategies")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body), len(STRATEGY_REGISTRY))
        names = {s["name"] for s in body}
        self.assertEqual(names, set(STRATEGY_REGISTRY.keys()))
        # none may be presented as validated/recommended - see registry.py
        self.assertTrue(all(s["validated"] is False for s in body))

    def test_signals_list_labeled_synthetic_and_uncalibrated(self) -> None:
        resp = self.client.get("/api/signals?limit=5")
        self.assertEqual(resp.status_code, 200)
        for sig in resp.json():
            self.assertEqual(sig["data_source"], "synthetic_demo")
            self.assertEqual(sig["confidence"], "UNCALIBRATED")  # no CalibratedModel wired up yet
            self.assertIsNone(sig["score"])
            self.assertLess(sig["stop"], sig["entry"])
            self.assertGreater(sig["target"], sig["entry"])

    def test_bars_endpoint_returns_chronological_ohlcv(self) -> None:
        resp = self.client.get("/api/signals/AAPL/bars?num_trading_days=3")
        self.assertEqual(resp.status_code, 200)
        bars = resp.json()
        self.assertGreater(len(bars), 0)
        timestamps = [b["timestamp"] for b in bars]
        self.assertEqual(timestamps, sorted(timestamps))
        for b in bars:
            self.assertGreaterEqual(b["high"], b["low"])

    def test_signal_detail_unknown_strategy_404s(self) -> None:
        resp = self.client.get("/api/signals/AAPL?strategy=not_a_real_strategy")
        self.assertEqual(resp.status_code, 404)

    def test_dashboard_reports_zero_validated_strategies(self) -> None:
        resp = self.client.get("/api/dashboard")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        # PHASE7_NOTES.md: both gate-tested strategies failed; the other
        # three were never run through the gate at all.
        self.assertEqual(body["validated_strategy_count"], 0)
        self.assertEqual(body["strategy_count"], 5)
        self.assertEqual(body["data_source"], "synthetic_demo")

    def test_trade_journal_is_empty(self) -> None:
        resp = self.client.get("/api/trades")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["entries"], [])
        self.assertIn("Phase 9", body["note"])


if __name__ == "__main__":
    unittest.main()
