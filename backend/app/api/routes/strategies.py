"""GET /api/strategies — backs the frontend's strategy list panel."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.registry import STRATEGY_REGISTRY
from app.api.schemas import StrategyOut

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


@router.get("", response_model=list[StrategyOut])
def list_strategies() -> list[StrategyOut]:
    return [
        StrategyOut(name=info.name, description=info.description, validated=info.validated, gate_note=info.gate_note)
        for info in STRATEGY_REGISTRY.values()
    ]
