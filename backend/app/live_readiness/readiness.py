"""Controlled Live Test readiness check — ROADMAP.md Abschnitt 19, Phase
11: "Erst nach Klärung PDT/Kontogröße, sehr kleines Kapital."

This module produces a go/no-go CHECKLIST for a human to review before
risking real money. It does not, and must never, submit a real order or
connect to a real broker itself — see PHASE11_NOTES.md for why that
boundary is drawn here rather than left as "the next small step". Modeled
on app/validation/gate.py's PASS/FAIL/NOT_AUTOMATED honesty pattern:
several of these checks genuinely cannot be automated from this codebase
alone (verified broker connectivity, a human's actual authorization to
risk their own money), and are reported as such rather than silently
skipped or assumed passing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from app.forward_test.session import ForwardTestStatus
from app.signals.risk import DailyLossGuard

Status = Literal["PASS", "FAIL", "NOT_AUTOMATED"]


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    status: Status
    detail: str


@dataclass(frozen=True)
class ReadinessReport:
    checks: list[ReadinessCheck]

    @property
    def passed(self) -> bool:
        return not any(c.status == "FAIL" for c in self.checks)

    @property
    def fully_automated(self) -> bool:
        return not any(c.status == "NOT_AUTOMATED" for c in self.checks)


@dataclass(frozen=True)
class LiveTestConstraints:
    """DECISIONS.md #6: `account_type`/`max_capital` here are DEFAULTS
    applied because the user was asked individually and answered "keine
    Präferenz" on all three Phase 11 questions (account structure,
    capital, News-Filter-first) - unlike #4/#5/#7, these were never
    actively picked from the options offered, only left to this
    codebase's own recommendation. Must be reconfirmed with the user
    before any real capital is actually committed - see PHASE11_NOTES.md.

    `account_type="cash"` avoids the PDT rule entirely (a cash account is
    not subject to it - PDT is a margin-account regulation), which matters
    here because every strategy in this codebase is intraday by design
    (DECISIONS.md #2) and would otherwise almost certainly trigger PDT
    classification within days. `max_position_pct_of_capital` is a second,
    independent cap on top of risk-based position sizing
    (app/signals/risk.py's `position_size`) - Phase 9 found that pure
    risk-based sizing can request a position costing far more than total
    equity when the stop is tight relative to price (PHASE9_NOTES.md);
    this cap exists so that a single small live account cannot repeat
    that with real money, even though `Portfolio`'s buying-power check
    (app/paper/portfolio.py) already rejects orders it can't afford.
    """

    account_type: Literal["cash", "margin"] = "cash"
    max_capital: float = 750.0
    max_position_pct_of_capital: float = 0.25


def evaluate_live_readiness(
    *,
    forward_test_status: Optional[ForwardTestStatus],
    daily_loss_guard: Optional[DailyLossGuard],
    news_filter_wired: bool,
    constraints: LiveTestConstraints,
    broker_connectivity_verified: bool = False,
) -> ReadinessReport:
    checks: list[ReadinessCheck] = []

    if forward_test_status is None:
        checks.append(ReadinessCheck("forward_test_confirmed", "FAIL", "no forward test has been run"))
    else:
        checks.append(
            ReadinessCheck(
                "forward_test_confirmed",
                "PASS" if forward_test_status.ready_for_review else "FAIL",
                f"{forward_test_status.metrics.trade_count} trades over "
                f"{forward_test_status.elapsed_days:.1f} days "
                f"(criteria: trades_met={forward_test_status.trades_criterion_met}, "
                f"days_met={forward_test_status.days_criterion_met})",
            )
        )

    checks.append(
        ReadinessCheck(
            "pdt_safe_account",
            "PASS" if constraints.account_type == "cash" or constraints.max_capital >= 25_000 else "FAIL",
            f"account_type={constraints.account_type}, max_capital={constraints.max_capital:.2f} - "
            "cash accounts are not subject to the PDT rule; a margin account needs >= $25,000 "
            "equity to day-trade without restriction",
        )
    )

    checks.append(
        ReadinessCheck(
            "daily_loss_kill_switch_configured",
            "PASS" if daily_loss_guard is not None else "FAIL",
            "DailyLossGuard instance provided" if daily_loss_guard is not None else "no DailyLossGuard configured",
        )
    )

    checks.append(
        ReadinessCheck(
            "news_earnings_filter_wired",
            "PASS" if news_filter_wired else "FAIL",
            "PaperTradingEngine configured with an EarningsCalendarProvider"
            if news_filter_wired
            else "no pre-trade earnings/volatility filter configured - see app/signals/news_filter.py",
        )
    )

    checks.append(
        ReadinessCheck(
            "broker_connectivity_verified",
            "PASS" if broker_connectivity_verified else "NOT_AUTOMATED",
            "cannot be verified from this codebase/sandbox - Alpaca is network-blocked here, "
            "see PHASE3_NOTES.md - must be verified manually with real credentials outside it",
        )
    )

    checks.append(
        ReadinessCheck(
            "human_sign_off",
            "NOT_AUTOMATED",
            "no amount of code can substitute for the user explicitly authorizing real capital "
            "to be put at risk - this is not a check this codebase can pass on anyone's behalf",
        )
    )

    return ReadinessReport(checks=checks)
