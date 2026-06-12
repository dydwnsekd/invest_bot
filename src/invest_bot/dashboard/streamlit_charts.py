from __future__ import annotations

from dataclasses import dataclass

import altair as alt
import pandas as pd
import streamlit as st


@dataclass(frozen=True, slots=True)
class ChartPreset:
    key: str
    label: str
    description: str


CHART_PRESETS = {
    "close_ma": ChartPreset(
        key="close_ma",
        label="가격 + 이동평균선",
        description="종가 흐름과 단기·중기 이동평균선의 정렬 상태를 함께 봅니다.",
    ),
    "candlestick": ChartPreset(
        key="candlestick",
        label="캔들스틱",
        description="하루 안에서 시가·고가·저가·종가가 어떻게 움직였는지 한 번에 봅니다.",
    ),
    "volume": ChartPreset(
        key="volume",
        label="거래량",
        description="가격 움직임에 거래가 실렸는지 확인할 때 적합합니다.",
    ),
    "rsi": ChartPreset(
        key="rsi",
        label="RSI",
        description="과열 구간과 과매도 구간을 70·30 기준선으로 빠르게 해석합니다.",
    ),
    "flow": ChartPreset(
        key="flow",
        label="투자자 수급",
        description="개인·외국인·기관의 순매수 방향을 비교해서 봅니다.",
    ),
    "close_only": ChartPreset(
        key="close_only",
        label="종가 추세",
        description="핵심 가격 흐름만 간단하게 보고 싶을 때 적합합니다.",
    ),
}

SERIES_LABELS = {
    "close": "종가",
    "ma_5": "5일선",
    "ma_20": "20일선",
    "ma_60": "60일선",
    "volume": "거래량",
    "rsi_14": "RSI 14",
    "foreign_net": "외국인 순매수",
    "institutional_net": "기관 순매수",
    "personal_net": "개인 순매수",
    "frgn_ntby_qty": "외국인 순매수",
    "orgn_ntby_qty": "기관 순매수",
    "prsn_ntby_qty": "개인 순매수",
}

PRICE_COLOR_DOMAIN = ["종가", "5일선", "20일선", "60일선"]
PRICE_COLOR_RANGE = ["#0f766e", "#f59e0b", "#dc2626", "#7c3aed"]
FLOW_COLOR_DOMAIN = ["외국인 순매수", "기관 순매수", "개인 순매수"]
FLOW_COLOR_RANGE = ["#2563eb", "#059669", "#f97316"]


def available_chart_presets(dataset_name: str, frame: pd.DataFrame) -> list[ChartPreset]:
    normalized = prepare_time_series_frame(frame)
    if normalized.empty:
        return []

    columns = set(normalized.columns)
    presets: list[ChartPreset] = []

    if "close" in columns:
        presets.append(CHART_PRESETS["close_only"])
    if {"close", "ma_5", "ma_20"}.intersection(columns) and "close" in columns:
        presets.append(CHART_PRESETS["close_ma"])
    if {"open", "high", "low", "close"}.issubset(columns):
        presets.append(CHART_PRESETS["candlestick"])
    if "volume" in columns:
        presets.append(CHART_PRESETS["volume"])
    if "rsi_14" in columns:
        presets.append(CHART_PRESETS["rsi"])
    if flow_series_columns(normalized):
        presets.append(CHART_PRESETS["flow"])

    order = chart_priority_for_dataset(dataset_name)
    ranked = sorted(
        {preset.key: preset for preset in presets}.values(),
        key=lambda preset: order.index(preset.key) if preset.key in order else len(order),
    )
    return ranked


def default_chart_preset(dataset_name: str, presets: list[ChartPreset]) -> str:
    if not presets:
        return ""
    preferred_order = chart_priority_for_dataset(dataset_name)
    for key in preferred_order:
        if any(preset.key == key for preset in presets):
            return key
    return presets[0].key


def chart_priority_for_dataset(dataset_name: str) -> list[str]:
    if dataset_name in {"daily_prices", "daily_prices_indicators"}:
        return ["close_ma", "candlestick", "volume", "rsi", "close_only", "flow"]
    if dataset_name == "investor_daily":
        return ["flow", "close_only", "volume"]
    return ["close_ma", "candlestick", "volume", "rsi", "flow", "close_only"]


def prepare_time_series_frame(frame: pd.DataFrame, max_points: int = 90) -> pd.DataFrame:
    working = frame.copy()
    date_column = infer_date_column(working)
    if date_column is None:
        return pd.DataFrame()

    working["date"] = pd.to_datetime(working[date_column], errors="coerce")
    working = working.dropna(subset=["date"]).sort_values("date")
    if working.empty:
        return working

    for column in working.columns:
        if column == "date":
            continue
        try:
            working[column] = pd.to_numeric(working[column])
        except (TypeError, ValueError):
            continue
    return working.tail(max_points).reset_index(drop=True)


def infer_date_column(frame: pd.DataFrame) -> str | None:
    for column in ("date", "stck_bsop_date"):
        if column in frame.columns:
            return column
    return None


def flow_series_columns(frame: pd.DataFrame) -> list[str]:
    columns: list[str] = []
    for column in ("foreign_net", "institutional_net", "personal_net", "frgn_ntby_qty", "orgn_ntby_qty", "prsn_ntby_qty"):
        if column in frame.columns:
            columns.append(column)
    return columns


def render_chart_selector(
    frame: pd.DataFrame,
    *,
    dataset_name: str,
    key_prefix: str,
    height: int = 280,
) -> None:
    presets = available_chart_presets(dataset_name, frame)
    if not presets:
        st.caption("이 데이터셋은 현재 차트로 해석할 수 있는 날짜·수치 컬럼이 충분하지 않습니다.")
        return

    preset_by_key = {preset.key: preset for preset in presets}
    default_key = default_chart_preset(dataset_name, presets)
    selected_key = st.selectbox(
        "차트 유형",
        options=[preset.key for preset in presets],
        index=[preset.key for preset in presets].index(default_key),
        format_func=lambda key: preset_by_key[key].label,
        key=f"{key_prefix}_chart_type",
    )
    st.caption(preset_by_key[selected_key].description)
    chart = build_chart(frame, selected_key, height=height)
    if chart is None:
        st.info("선택한 차트를 그리기 위한 컬럼이 부족합니다.")
        return
    st.altair_chart(chart, use_container_width=True)


def build_chart(frame: pd.DataFrame, chart_type: str, *, height: int = 280) -> alt.Chart | alt.LayerChart | None:
    normalized = prepare_time_series_frame(frame)
    if normalized.empty:
        return None
    if chart_type == "close_only":
        return build_price_line_chart(normalized, ["close"], height=height)
    if chart_type == "close_ma":
        columns = [column for column in ("close", "ma_5", "ma_20", "ma_60") if column in normalized.columns]
        return build_price_line_chart(normalized, columns, height=height)
    if chart_type == "candlestick":
        return build_candlestick_chart(normalized, height=height)
    if chart_type == "volume":
        return build_volume_chart(normalized, height=height)
    if chart_type == "rsi":
        return build_rsi_chart(normalized, height=height)
    if chart_type == "flow":
        return build_flow_chart(normalized, height=height)
    return None


def build_price_line_chart(frame: pd.DataFrame, columns: list[str], *, height: int) -> alt.Chart | None:
    columns = [column for column in columns if column in frame.columns]
    if not columns:
        return None
    chart_data = frame[["date", *columns]].melt("date", var_name="series", value_name="value").dropna(subset=["value"])
    if chart_data.empty:
        return None
    chart_data["series_label"] = chart_data["series"].map(lambda column: SERIES_LABELS.get(column, column))
    return (
        alt.Chart(chart_data)
        .mark_line(point=True, strokeWidth=2)
        .encode(
            x=alt.X("date:T", title="날짜"),
            y=alt.Y("value:Q", title="가격"),
            color=alt.Color(
                "series_label:N",
                title="지표",
                scale=alt.Scale(domain=PRICE_COLOR_DOMAIN, range=PRICE_COLOR_RANGE),
            ),
            tooltip=[
                alt.Tooltip("date:T", title="날짜"),
                alt.Tooltip("series_label:N", title="지표"),
                alt.Tooltip("value:Q", title="값", format=","),
            ],
        )
        .properties(height=height)
    )


def build_candlestick_chart(frame: pd.DataFrame, *, height: int) -> alt.LayerChart | None:
    required = {"open", "high", "low", "close"}
    if not required.issubset(frame.columns):
        return None
    chart_data = frame[["date", "open", "high", "low", "close"]].dropna()
    if chart_data.empty:
        return None
    chart_data = chart_data.assign(direction=chart_data.apply(lambda row: "상승" if row["close"] >= row["open"] else "하락", axis=1))
    rules = (
        alt.Chart(chart_data)
        .mark_rule()
        .encode(
            x=alt.X("date:T", title="날짜"),
            y=alt.Y("low:Q", title="가격"),
            y2="high:Q",
            color=alt.Color("direction:N", scale=alt.Scale(domain=["상승", "하락"], range=["#dc2626", "#2563eb"]), title="방향"),
            tooltip=[
                alt.Tooltip("date:T", title="날짜"),
                alt.Tooltip("open:Q", title="시가", format=","),
                alt.Tooltip("high:Q", title="고가", format=","),
                alt.Tooltip("low:Q", title="저가", format=","),
                alt.Tooltip("close:Q", title="종가", format=","),
            ],
        )
    )
    bars = (
        alt.Chart(chart_data)
        .mark_bar(size=7)
        .encode(
            x="date:T",
            y="open:Q",
            y2="close:Q",
            color=alt.Color("direction:N", scale=alt.Scale(domain=["상승", "하락"], range=["#dc2626", "#2563eb"]), legend=None),
        )
    )
    return alt.layer(rules, bars).properties(height=height)


def build_volume_chart(frame: pd.DataFrame, *, height: int) -> alt.Chart | None:
    if "volume" not in frame.columns:
        return None
    chart_data = frame[["date", "volume"]].dropna()
    if chart_data.empty:
        return None
    return (
        alt.Chart(chart_data)
        .mark_bar(color="#2563eb")
        .encode(
            x=alt.X("date:T", title="날짜"),
            y=alt.Y("volume:Q", title="거래량"),
            tooltip=[
                alt.Tooltip("date:T", title="날짜"),
                alt.Tooltip("volume:Q", title="거래량", format=","),
            ],
        )
        .properties(height=height)
    )


def build_rsi_chart(frame: pd.DataFrame, *, height: int) -> alt.LayerChart | None:
    if "rsi_14" not in frame.columns:
        return None
    chart_data = frame[["date", "rsi_14"]].dropna()
    if chart_data.empty:
        return None
    base = alt.Chart(chart_data).encode(x=alt.X("date:T", title="날짜"))
    line = base.mark_line(color="#7c3aed", strokeWidth=2).encode(
        y=alt.Y("rsi_14:Q", title="RSI 14", scale=alt.Scale(domain=[0, 100])),
        tooltip=[
            alt.Tooltip("date:T", title="날짜"),
            alt.Tooltip("rsi_14:Q", title="RSI 14", format=".2f"),
        ],
    )
    thresholds = pd.DataFrame({"level": [30, 70], "label": ["과매도 기준", "과열 기준"]})
    rules = (
        alt.Chart(thresholds)
        .mark_rule(strokeDash=[6, 4], color="#9ca3af")
        .encode(y="level:Q", tooltip=[alt.Tooltip("label:N", title="기준"), alt.Tooltip("level:Q", title="값")])
    )
    return alt.layer(line, rules).properties(height=height)


def build_flow_chart(frame: pd.DataFrame, *, height: int) -> alt.Chart | None:
    columns = flow_series_columns(frame)
    if not columns:
        return None
    chart_data = frame[["date", *columns]].melt("date", var_name="series", value_name="value").dropna(subset=["value"])
    if chart_data.empty:
        return None
    chart_data["series_label"] = chart_data["series"].map(lambda column: SERIES_LABELS.get(column, column))
    return (
        alt.Chart(chart_data)
        .mark_line(point=True, strokeWidth=2)
        .encode(
            x=alt.X("date:T", title="날짜"),
            y=alt.Y("value:Q", title="순매수"),
            color=alt.Color(
                "series_label:N",
                title="주체",
                scale=alt.Scale(domain=FLOW_COLOR_DOMAIN, range=FLOW_COLOR_RANGE),
            ),
            tooltip=[
                alt.Tooltip("date:T", title="날짜"),
                alt.Tooltip("series_label:N", title="주체"),
                alt.Tooltip("value:Q", title="값", format=","),
            ],
        )
        .properties(height=height)
    )
