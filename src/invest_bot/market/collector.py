from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CollectionRequest:
    symbol: str
    timeframe: str = "1d"
    limit: int = 100


class MarketDataCollector:
    """Placeholder collector to be connected to reference-based API wrappers."""

    def collect(self, request: CollectionRequest) -> dict[str, str | int]:
        return {
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "limit": request.limit,
            "status": "pending_reference_integration",
        }
