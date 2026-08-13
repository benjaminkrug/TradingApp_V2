"""Pydantic response models for the API layer (app/api/routes/*)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class StrategyOut(BaseModel):
    name: str
    description: str
    validated: bool
    gate_note: str


class SignalOut(BaseModel):
    symbol: str
    strategy_name: str
    entry: float
    stop: float
    target: float
    risk_reward: float
    shares: float
    score: Optional[float]
    confidence: str
    relative_volume: Optional[float]
    rationale: list[str]
    data_source: str
    account_equity: float
    risk_pct: float


class DashboardOut(BaseModel):
    universe_size: int
    strategy_count: int
    validated_strategy_count: int
    signal_count: int
    data_source: str
    notes: list[str]


class TradeJournalEntryOut(BaseModel):
    id: str
    symbol: str
    opened_at: str
    closed_at: Optional[str]
    pnl: Optional[float]


class TradeJournalOut(BaseModel):
    entries: list[TradeJournalEntryOut]
    note: str


class BarOut(BaseModel):
    timestamp: str  # ISO 8601, tz-aware
    open: float
    high: float
    low: float
    close: float
    volume: float
