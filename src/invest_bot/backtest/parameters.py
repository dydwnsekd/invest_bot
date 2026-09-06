"""Supported, bounded experimental settings for backtest strategies."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True, slots=True)
class BacktestParameterDefinition:
    key: str
    label: str
    description: str
    default: float
    minimum: float
    maximum: float
    step: float


STRATEGY_PARAMETER_DEFINITIONS: Mapping[str, tuple[BacktestParameterDefinition, ...]] = {
    "golden-cross": (
        BacktestParameterDefinition("short_window", "단기 이동평균 기간", "짧은 기간 평균이 긴 기간 평균을 상향·하향 돌파할 때 신호를 냅니다.", 5, 2, 30, 1),
        BacktestParameterDefinition("long_window", "장기 이동평균 기간", "단기 평균과 비교할 더 긴 추세 기준입니다.", 20, 3, 120, 1),
    ),
    "rsi": (
        BacktestParameterDefinition("buy_threshold", "매수 RSI 기준", "RSI가 이 값 이하일 때 매수 신호를 냅니다.", 30, 5, 45, 1),
        BacktestParameterDefinition("sell_threshold", "매도 RSI 기준", "RSI가 이 값 이상일 때 매도 신호를 냅니다.", 70, 55, 95, 1),
    ),
    "mean-reversion": (
        BacktestParameterDefinition("buy_ratio", "매수 기준 비율", "종가/20일선 비율이 이 값 이하일 때 매수 신호를 냅니다.", 0.97, 0.80, 0.99, 0.01),
        BacktestParameterDefinition("sell_ratio", "매도 기준 비율", "종가/20일선 비율이 이 값 이상일 때 매도 신호를 냅니다.", 1.03, 1.01, 1.20, 0.01),
    ),
    "disparity": (
        BacktestParameterDefinition("buy_below", "매수 이격도 기준", "이격도가 이 값 이하일 때 매수 신호를 냅니다.", 97, 80, 99, 1),
        BacktestParameterDefinition("sell_above", "매도 이격도 기준", "이격도가 이 값 이상일 때 매도 신호를 냅니다.", 103, 101, 120, 1),
    ),
    "momentum": (
        BacktestParameterDefinition("buy_above", "매수 모멘텀 기준", "모멘텀이 이 값 이상일 때 매수 신호를 냅니다.", 10, 1, 40, 1),
        BacktestParameterDefinition("sell_below", "매도 모멘텀 기준", "모멘텀이 이 값 이하일 때 매도 신호를 냅니다.", -10, -40, -1, 1),
    ),
}


def list_backtest_parameter_definitions(strategy_id: str) -> tuple[BacktestParameterDefinition, ...]:
    return STRATEGY_PARAMETER_DEFINITIONS.get(strategy_id, ())


def default_backtest_parameters(strategy_id: str) -> dict[str, float]:
    return {definition.key: definition.default for definition in list_backtest_parameter_definitions(strategy_id)}


def resolve_backtest_parameters(
    strategy_id: str,
    values: Mapping[str, object] | None = None,
) -> dict[str, float]:
    definitions = list_backtest_parameter_definitions(strategy_id)
    supplied = values or {}
    known_keys = {definition.key for definition in definitions}
    unknown = sorted(set(supplied).difference(known_keys))
    if unknown:
        raise ValueError(f"{strategy_id} 전략에서 지원하지 않는 설정입니다: {', '.join(unknown)}")

    resolved = default_backtest_parameters(strategy_id)
    for definition in definitions:
        if definition.key not in supplied:
            continue
        raw_value = supplied[definition.key]
        if raw_value is None or str(raw_value).strip() == "":
            raise ValueError(f"{definition.label} 값을 입력해 주세요.")
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"{definition.label}은 숫자로 입력해 주세요.") from error
        if not isfinite(value) or not definition.minimum <= value <= definition.maximum:
            raise ValueError(f"{definition.label}은 {definition.minimum:g}~{definition.maximum:g} 범위로 입력해 주세요.")
        resolved[definition.key] = value

    _validate_parameter_relationships(strategy_id, resolved)
    return resolved


def is_default_backtest_parameters(strategy_id: str, values: Mapping[str, object] | None = None) -> bool:
    return resolve_backtest_parameters(strategy_id, values) == default_backtest_parameters(strategy_id)


def format_backtest_parameters(strategy_id: str, values: Mapping[str, object] | None = None) -> str:
    resolved = resolve_backtest_parameters(strategy_id, values)
    definitions = list_backtest_parameter_definitions(strategy_id)
    if not definitions:
        return "조절 가능한 실험 설정 없음"
    return " · ".join(f"{definition.label} {resolved[definition.key]:g}" for definition in definitions)


def _validate_parameter_relationships(strategy_id: str, values: Mapping[str, float]) -> None:
    if strategy_id == "golden-cross":
        if not values["short_window"].is_integer() or not values["long_window"].is_integer():
            raise ValueError("이동평균 기간은 정수로 입력해 주세요.")
        if values["short_window"] >= values["long_window"]:
            raise ValueError("단기 이동평균 기간은 장기 이동평균 기간보다 짧아야 합니다.")
    if strategy_id in {"rsi", "mean-reversion", "disparity"}:
        buy_key, sell_key = {
            "rsi": ("buy_threshold", "sell_threshold"),
            "mean-reversion": ("buy_ratio", "sell_ratio"),
            "disparity": ("buy_below", "sell_above"),
        }[strategy_id]
        if values[buy_key] >= values[sell_key]:
            raise ValueError("매수 기준은 매도 기준보다 낮아야 합니다.")
    if strategy_id == "momentum" and values["sell_below"] >= values["buy_above"]:
        raise ValueError("매도 모멘텀 기준은 매수 모멘텀 기준보다 낮아야 합니다.")
