"""Append-only record of every validation run — DECISIONS.md #8.

The gate is deliberately strict (VALIDATION_PROTOCOL.md), so the expected
outcome is that most candidates fail. Without this store, each failing run
would leave nothing behind except a verdict, and the next search would
start from zero. Here, the full numbers survive: a candidate that misses
one criterion narrowly can be found again later, and the accumulated log
is also what makes the multiple-testing accounting in K7 possible at all
(you cannot correct for how often you searched if you never wrote it down).

Append-only on purpose. Runs are never edited or deleted, including
embarrassing ones - a results log that gets tidied up after the fact is
exactly the failure mode VALIDATION_PROTOCOL.md's pre-registration exists
to prevent.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

DEFAULT_STORE = Path(__file__).resolve().parents[2] / "results" / "gate_runs.jsonl"


def _git_commit() -> Optional[str]:
    """Which code produced this result. Returns None outside a git checkout
    rather than raising - a missing commit hash degrades the record, it
    does not invalidate the run."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None if out.returncode == 0 else None


@dataclass(frozen=True)
class RunRecord:
    """One evaluation of one strategy on one dataset.

    `metrics` is intentionally an open dict rather than a fixed schema: the
    criteria in VALIDATION_PROTOCOL.md are being implemented incrementally
    (K2 first, then K3-K7), and a rigid schema would either have to be
    guessed up front or force a migration of past records each time one
    lands. Provenance - what was run, on what data, with which code - is
    typed, because that is what later readers need to trust a row.
    """

    strategy: str
    strategy_params: dict[str, Any]
    symbols: list[str]
    data_start: str
    data_end: str
    timeframe: str
    data_source: str  # e.g. "alpaca/iex" - feed matters, see VALIDATION_PROTOCOL.md
    engine: str  # "paper" (the real rules) or "reference" (cross-check oracle)
    metrics: dict[str, Any]
    verdict: Optional[str] = None  # "PASS"/"FAIL"/None while criteria are incomplete
    note: str = ""
    recorded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    git_commit: Optional[str] = field(default_factory=_git_commit)


def record_run(record: RunRecord, store: Path = DEFAULT_STORE) -> None:
    store.parent.mkdir(parents=True, exist_ok=True)
    with store.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def load_runs(store: Path = DEFAULT_STORE) -> list[dict[str, Any]]:
    if not store.exists():
        return []
    return [json.loads(line) for line in store.read_text(encoding="utf-8").splitlines() if line.strip()]
