"""Transparent ways to combine normalized strategy signals for backtesting."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Mapping

import pandas as pd


COMBINATION_MODE_AND = "and"
COMBINATION_MODE_OR = "or"
COMBINATION_MODE_WEIGHTED = "weighted"
COMBINATION_MODES = (COMBINATION_MODE_AND, COMBINATION_MODE_OR, COMBINATION_MODE_WEIGHTED)
COMBINATION_MODE_LABELS = {
    COMBINATION_MODE_AND: "전략 합의 (AND)",
    COMBINATION_MODE_OR: "하나라도 충족 (OR)",
    COMBINATION_MODE_WEIGHTED: "가중치 합산",
}


@dataclass(frozen=True, slots=True)
class BacktestCombinationSettings:
    mode: str
    weights: Mapping[str, float]

    @property
    def strategy_id(self) -> str:
        return f"combination-{self.mode}"

    @property
    def strategy_name(self) -> str:
        return COMBINATION_MODE_LABELS[self.mode]

    def as_json(self) -> str:
        return json.dumps({"mode": self.mode, "weights": dict(self.weights)}, ensure_ascii=False, sort_keys=True)

    def summary(self) -> str:
        if self.mode == COMBINATION_MODE_AND:
            return "AND: 모든 전략이 같은 매수 또는 매도일 때만 신호, 그 외 관망"
        if self.mode == COMBINATION_MODE_OR:
            return "OR: 한 전략이라도 같은 방향일 때 신호, 매수·매도 충돌 시 관망"
        weights = " · ".join(f"{strategy_id} {weight:g}" for strategy_id, weight in self.weights.items())
        return f"가중치: 매수는 +, 매도는 -로 합산하며 0점은 관망 · {weights}"


def resolve_backtest_combination_settings(
    strategy_ids: list[str],
    mode: str = COMBINATION_MODE_AND,
    weights: Mapping[str, object] | None = None,
) -> BacktestCombinationSettings:
    selected_ids = list(dict.fromkeys(strategy_ids))
    if len(selected_ids) < 2:
        raise ValueError("복수 전략 조합에는 전략을 두 개 이상 선택해 주세요.")
    if mode not in COMBINATION_MODES:
        raise ValueError("지원하지 않는 조합 방식입니다.")
    raw_weights = weights or {}
    unknown = sorted(set(raw_weights).difference(selected_ids))
    if unknown:
        raise ValueError(f"선택하지 않은 전략의 가중치가 포함되어 있습니다: {', '.join(unknown)}")
    resolved_weights: dict[str, float] = {}
    for strategy_id in selected_ids:
        raw_value = raw_weights.get(strategy_id, 1.0)
        if raw_value is None or str(raw_value).strip() == "":
            raise ValueError(f"{strategy_id} 전략 가중치를 입력해 주세요.")
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"{strategy_id} 전략 가중치는 숫자로 입력해 주세요.") from error
        if not 0.1 <= value <= 3.0:
            raise ValueError(f"{strategy_id} 전략 가중치는 0.1~3.0 범위로 입력해 주세요.")
        resolved_weights[strategy_id] = value
    return BacktestCombinationSettings(mode=mode, weights=resolved_weights)


def combine_strategy_signal_rows(
    signal_frames: Mapping[str, pd.DataFrame],
    settings: BacktestCombinationSettings,
) -> pd.DataFrame:
    selected_ids = list(settings.weights)
    if set(selected_ids) != set(signal_frames):
        raise ValueError("선택한 모든 전략의 신호가 준비되어야 조합할 수 있습니다.")

    merged: pd.DataFrame | None = None
    for strategy_id in selected_ids:
        frame = signal_frames[strategy_id]
        required_columns = {"date", "close", "signal"}
        if not required_columns.issubset(frame.columns):
            raise ValueError(f"{strategy_id} 전략 신호에 날짜·종가·신호가 부족합니다.")
        normalized = frame[["date", "close", "signal"]].copy()
        normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
        normalized = normalized.dropna(subset=["date", "close"]).sort_values("date").drop_duplicates("date", keep="last")
        normalized["signal"] = normalized["signal"].fillna("hold").astype(str).str.lower()
        normalized = normalized.rename(columns={"close": f"close_{strategy_id}", "signal": f"signal_{strategy_id}"})
        merged = normalized if merged is None else merged.merge(normalized, on="date", how="inner", validate="one_to_one")

    if merged is None or merged.empty:
        raise ValueError("선택한 전략이 함께 평가할 공통 거래일이 없습니다.")

    signal_columns = [f"signal_{strategy_id}" for strategy_id in selected_ids]
    merged["signal"] = merged.apply(
        lambda row: _combine_signal([str(row[column]) for column in signal_columns], settings),
        axis=1,
    )
    merged["combination_score"] = merged.apply(
        lambda row: _weighted_score([str(row[column]) for column in signal_columns], settings),
        axis=1,
    )
    merged["component_signals"] = merged.apply(
        lambda row: " · ".join(f"{strategy_id}: {row[f'signal_{strategy_id}']}" for strategy_id in selected_ids),
        axis=1,
    )
    merged["signal_reason"] = merged.apply(
        lambda row: f"{settings.summary()} / {row['component_signals']}",
        axis=1,
    )
    merged["close"] = merged[f"close_{selected_ids[0]}"]
    merged["strategy_id"] = settings.strategy_id
    merged["strategy_name"] = settings.strategy_name
    return merged[["date", "close", "signal", "signal_reason", "strategy_id", "strategy_name", "combination_score", "component_signals"]].copy()


def _combine_signal(signals: list[str], settings: BacktestCombinationSettings) -> str:
    normalized = [signal if signal in {"buy", "sell", "hold"} else "hold" for signal in signals]
    if settings.mode == COMBINATION_MODE_AND:
        return "buy" if all(signal == "buy" for signal in normalized) else "sell" if all(signal == "sell" for signal in normalized) else "hold"
    if settings.mode == COMBINATION_MODE_OR:
        has_buy = "buy" in normalized
        has_sell = "sell" in normalized
        return "buy" if has_buy and not has_sell else "sell" if has_sell and not has_buy else "hold"
    score = _weighted_score(normalized, settings)
    return "buy" if score > 0 else "sell" if score < 0 else "hold"


def _weighted_score(signals: list[str], settings: BacktestCombinationSettings) -> float:
    score = 0.0
    for strategy_id, signal in zip(settings.weights, signals, strict=True):
        if signal == "buy":
            score += settings.weights[strategy_id]
        elif signal == "sell":
            score -= settings.weights[strategy_id]
    return score
