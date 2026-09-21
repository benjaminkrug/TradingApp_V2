import json
import tempfile
import unittest
from pathlib import Path

from app.validation.results_store import RunRecord, load_runs, record_run


def make_record(strategy="OpeningRangeBreakout", verdict=None, mean_bp=1.0):
    return RunRecord(
        strategy=strategy,
        strategy_params={"range_bars": 6},
        symbols=["AAPL"],
        data_start="2026-03-05",
        data_end="2026-09-21",
        timeframe="5Min",
        data_source="alpaca/iex",
        engine="paper",
        metrics={"mean_bp": mean_bp},
        verdict=verdict,
    )


class TestResultsStore(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "runs.jsonl"
            record_run(make_record(), store)
            runs = load_runs(store)

        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["strategy"], "OpeningRangeBreakout")
        self.assertEqual(runs[0]["metrics"]["mean_bp"], 1.0)
        self.assertIsNotNone(runs[0]["recorded_at"])

    def test_is_append_only(self):
        """DECISIONS.md #8 / VALIDATION_PROTOCOL.md: failing runs must survive,
        so a second write must never replace the first."""
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "runs.jsonl"
            record_run(make_record(strategy="A", verdict="FAIL", mean_bp=-2.0), store)
            record_run(make_record(strategy="B", verdict="PASS", mean_bp=7.0), store)
            runs = load_runs(store)

        self.assertEqual([r["strategy"] for r in runs], ["A", "B"])
        self.assertEqual([r["verdict"] for r in runs], ["FAIL", "PASS"])

    def test_missing_store_reads_as_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_runs(Path(tmp) / "does_not_exist.jsonl"), [])

    def test_each_line_is_independently_parseable(self):
        """JSONL rather than one big JSON array, specifically so an
        interrupted run cannot corrupt previously recorded results."""
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "runs.jsonl"
            record_run(make_record(strategy="A"), store)
            record_run(make_record(strategy="B"), store)
            lines = store.read_text(encoding="utf-8").strip().splitlines()

        self.assertEqual(len(lines), 2)
        for line in lines:
            self.assertIn("strategy", json.loads(line))


if __name__ == "__main__":
    unittest.main()
