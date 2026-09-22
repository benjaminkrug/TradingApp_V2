import json
import unittest
import urllib.error
from datetime import date, timedelta

from app.data.providers.gdelt import (
    ToneDay,
    _chunk_date_range,
    _get_with_backoff,
    _parse_timeline,
    fetch_tone_timeline,
)


class TestChunkDateRange(unittest.TestCase):
    def test_short_range_is_a_single_chunk(self):
        chunks = _chunk_date_range(date(2024, 1, 1), date(2024, 2, 1))
        self.assertEqual(chunks, [(date(2024, 1, 1), date(2024, 2, 1))])

    def test_long_range_is_split_at_90_days_with_no_gaps_or_overlaps(self):
        chunks = _chunk_date_range(date(2024, 1, 1), date(2024, 12, 31), max_span_days=90)

        # every day in [start, end] must be covered exactly once
        covered = set()
        for c_start, c_end in chunks:
            self.assertLessEqual((c_end - c_start).days, 89)  # at most 90 days inclusive
            d = c_start
            while d <= c_end:
                self.assertNotIn(d, covered, f"{d} covered twice")
                covered.add(d)
                d += timedelta(days=1)
        expected_days = (date(2024, 12, 31) - date(2024, 1, 1)).days + 1
        self.assertEqual(len(covered), expected_days)

    def test_single_day_range(self):
        chunks = _chunk_date_range(date(2024, 5, 1), date(2024, 5, 1))
        self.assertEqual(chunks, [(date(2024, 5, 1), date(2024, 5, 1))])


class TestParseTimeline(unittest.TestCase):
    def test_matches_hand_constructed_response(self):
        body = json.dumps({
            "timeline": [{
                "series": "Average Tone",
                "data": [
                    {"date": "20220601T000000Z", "value": -0.1629},
                    {"date": "20220602T000000Z", "value": 1.9843},
                ],
            }]
        })
        result = _parse_timeline(body)
        self.assertEqual(result, [
            ToneDay(day=date(2022, 6, 1), tone=-0.1629),
            ToneDay(day=date(2022, 6, 2), tone=1.9843),
        ])

    def test_empty_timeline(self):
        self.assertEqual(_parse_timeline(json.dumps({"timeline": []})), [])

    def test_malformed_json_returns_empty_not_raise(self):
        self.assertEqual(_parse_timeline("not json"), [])

    def test_missing_timeline_key(self):
        self.assertEqual(_parse_timeline(json.dumps({"query_details": {}})), [])

    def test_skips_points_with_bad_fields(self):
        body = json.dumps({"timeline": [{"data": [
            {"date": "20220601T000000Z", "value": 1.0},
            {"date": "not-a-date", "value": 2.0},
            {"value": 3.0},  # missing date
        ]}]})
        result = _parse_timeline(body)
        self.assertEqual(result, [ToneDay(day=date(2022, 6, 1), tone=1.0)])


class TestGetWithBackoff(unittest.TestCase):
    def test_succeeds_immediately_when_no_429(self):
        calls = []

        def fake_urlopen(req, timeout):
            class Resp:
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

                def read(self):
                    return b"ok"

            return Resp()

        import app.data.providers.gdelt as gdelt_module

        original = gdelt_module.urllib.request.urlopen
        gdelt_module.urllib.request.urlopen = fake_urlopen
        try:
            result = _get_with_backoff("http://example.test", sleep_fn=lambda s: calls.append(s))
        finally:
            gdelt_module.urllib.request.urlopen = original

        self.assertEqual(result, "ok")
        self.assertEqual(calls, [])

    def test_retries_with_increasing_wait_then_succeeds(self):
        attempts = {"n": 0}
        waits: list[float] = []

        def fake_urlopen(req, timeout):
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", None, None)

            class Resp:
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

                def read(self):
                    return b"ok-after-retries"

            return Resp()

        import app.data.providers.gdelt as gdelt_module

        original = gdelt_module.urllib.request.urlopen
        gdelt_module.urllib.request.urlopen = fake_urlopen
        try:
            result = _get_with_backoff(
                "http://example.test", base_wait=10.0, sleep_fn=lambda s: waits.append(s)
            )
        finally:
            gdelt_module.urllib.request.urlopen = original

        self.assertEqual(result, "ok-after-retries")
        self.assertEqual(attempts["n"], 3)
        # first failed attempt (attempt=1) waits base_wait*1, second (attempt=2) waits base_wait*2
        self.assertEqual(waits, [10.0, 20.0])

    def test_gives_up_after_max_attempts_returns_none(self):
        def fake_urlopen(req, timeout):
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", None, None)

        import app.data.providers.gdelt as gdelt_module

        original = gdelt_module.urllib.request.urlopen
        gdelt_module.urllib.request.urlopen = fake_urlopen
        try:
            result = _get_with_backoff("http://example.test", max_attempts=3, sleep_fn=lambda s: None)
        finally:
            gdelt_module.urllib.request.urlopen = original

        self.assertIsNone(result)

    def test_non_429_error_propagates(self):
        def fake_urlopen(req, timeout):
            raise urllib.error.HTTPError(req.full_url, 500, "Server Error", None, None)

        import app.data.providers.gdelt as gdelt_module

        original = gdelt_module.urllib.request.urlopen
        gdelt_module.urllib.request.urlopen = fake_urlopen
        try:
            with self.assertRaises(urllib.error.HTTPError):
                _get_with_backoff("http://example.test", sleep_fn=lambda s: None)
        finally:
            gdelt_module.urllib.request.urlopen = original


class TestFetchToneTimeline(unittest.TestCase):
    def test_stitches_multiple_chunks_and_paces_between_them(self):
        """A ~200 day range needs 3 chunks at 90 days each - verifies both
        that results get concatenated and that the pacing delay is called
        the right number of times (chunks - 1, no trailing sleep)."""
        # Exact chunk boundaries are TestChunkDateRange's job to verify;
        # this test only cares that N calls happen, in order, and that
        # their results get concatenated - so responses are keyed by call
        # order, not by guessing the chunker's exact date arithmetic.
        responses = [
            json.dumps({"timeline": [{"data": [{"date": "20240101T000000Z", "value": 1.0}]}]}),
            json.dumps({"timeline": [{"data": [{"date": "20240401T000000Z", "value": 2.0}]}]}),
            json.dumps({"timeline": [{"data": [{"date": "20240701T000000Z", "value": 3.0}]}]}),
        ]
        call_count = {"n": 0}

        def fake_get(url, sleep_fn=None):
            response = responses[call_count["n"]]
            call_count["n"] += 1
            return response

        import app.data.providers.gdelt as gdelt_module

        original = gdelt_module._get_with_backoff
        gdelt_module._get_with_backoff = fake_get
        try:
            sleeps: list[float] = []
            result = fetch_tone_timeline(
                "Test Co", date(2024, 1, 1), date(2024, 7, 5), sleep_fn=lambda s: sleeps.append(s), pace_seconds=1.0
            )
        finally:
            gdelt_module._get_with_backoff = original

        self.assertEqual(call_count["n"], 3)  # confirms 200 days needed exactly 3 chunks
        self.assertEqual(len(result), 3)
        self.assertEqual([r.tone for r in result], [1.0, 2.0, 3.0])
        # 3 chunks -> 2 pacing sleeps between them, not 3
        self.assertEqual(sleeps, [1.0, 1.0])


if __name__ == "__main__":
    unittest.main()
