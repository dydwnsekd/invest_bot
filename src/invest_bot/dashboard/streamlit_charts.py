from __future__ import annotations

from datetime import date, datetime, timedelta
from dataclasses import dataclass

import altair as alt
import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
except ImportError:  # pragma: no cover - exercised via fallback path when dependency is absent.
    go = None

try:
    from plotly.subplots import make_subplots
except ImportError:  # pragma: no cover - exercised via fallback path when dependency is absent.
    make_subplots = None


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
DEFAULT_RANGE_PRESET = "90d"
RANGE_PRESET_DAYS = {
    "30d": 30,
    "90d": 90,
    "180d": 180,
    "365d": 365,
    "all": None,
}


@dataclass(frozen=True, slots=True)
class RangeState:
    mode: str
    preset: str
    dates: tuple[date, date]
    min_date: date
    max_date: date


@dataclass(frozen=True, slots=True)
class RangePresetOption:
    key: str
    label: str


RANGE_PRESET_OPTIONS = (
    RangePresetOption("30d", "1개월"),
    RangePresetOption("90d", "3개월"),
    RangePresetOption("180d", "6개월"),
    RangePresetOption("365d", "1년"),
    RangePresetOption("all", "전체"),
)

TIMEFRAME_OPTIONS = (
    ("daily", "일봉"),
    ("weekly", "주봉"),
    ("monthly", "월봉"),
)
TIMEFRAME_LABELS = dict(TIMEFRAME_OPTIONS)
PROFESSIONAL_STOCK_DATASETS = {"daily_prices", "daily_prices_indicators"}
NORMALIZED_STOCK_COLUMN_MAP = {
    "stck_bsop_date": "date",
    "stck_oprc": "open",
    "stck_hgpr": "high",
    "stck_lwpr": "low",
    "stck_clpr": "close",
    "acml_vol": "volume",
}
FLOW_ROW_TITLE = "수급"


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
    working = frame.copy().rename(columns=NORMALIZED_STOCK_COLUMN_MAP)
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


def is_professional_stock_dataset(dataset_name: str, frame: pd.DataFrame) -> bool:
    if dataset_name not in PROFESSIONAL_STOCK_DATASETS:
        return False
    normalized = prepare_time_series_frame(frame, max_points=len(frame))
    return not normalized.empty and {"open", "high", "low", "close"}.issubset(normalized.columns)


def normalize_timeframe_key(timeframe: str | None) -> str:
    candidate = str(timeframe or "daily")
    if candidate in TIMEFRAME_LABELS:
        return candidate
    return "daily"


def aggregate_professional_chart_frame(frame: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    normalized = prepare_time_series_frame(frame, max_points=len(frame))
    if normalized.empty:
        return normalized

    resolved_timeframe = normalize_timeframe_key(timeframe)
    if resolved_timeframe == "daily":
        aggregated = normalized.copy()
    else:
        period = normalized["date"].dt.to_period("W-FRI" if resolved_timeframe == "weekly" else "M")
        group_keys = period.astype(str)
        aggregations: dict[str, str] = {"date": "last", "open": "first", "high": "max", "low": "min", "close": "last"}
        if "volume" in normalized.columns:
            aggregations["volume"] = "sum"
        for column in flow_series_columns(normalized):
            aggregations[column] = "sum"
        aggregated = (
            normalized.assign(_period_key=group_keys)
            .groupby("_period_key", sort=True, as_index=False)
            .agg(aggregations)
        )
    return recompute_technical_indicators(aggregated)


def recompute_technical_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    if result.empty or "close" not in result.columns:
        return result
    result["close"] = pd.to_numeric(result["close"], errors="coerce")
    for column in ("open", "high", "low", "volume", *flow_series_columns(result)):
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    result["ma_5"] = result["close"].rolling(window=5, min_periods=5).mean()
    result["ma_20"] = result["close"].rolling(window=20, min_periods=20).mean()
    result["ma_60"] = result["close"].rolling(window=60, min_periods=60).mean()
    result["rsi_14"] = calculate_rsi(result["close"], period=14)
    return result.sort_values("date").reset_index(drop=True)


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    relative_strength = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + relative_strength))
    rsi = rsi.mask((avg_gain > 0) & (avg_loss == 0), 100.0)
    rsi = rsi.mask((avg_gain == 0) & (avg_loss > 0), 0.0)
    rsi = rsi.mask((avg_gain == 0) & (avg_loss == 0), 50.0)
    return rsi


def preset_days(preset: str) -> int | None:
    return RANGE_PRESET_DAYS.get(str(preset), RANGE_PRESET_DAYS[DEFAULT_RANGE_PRESET])


def resolve_range_state(
    frame: pd.DataFrame,
    *,
    key_prefix: str,
    session_state=None,
    default_preset: str = DEFAULT_RANGE_PRESET,
    selected_preset: str | None = None,
    selected_dates: tuple[date | datetime | pd.Timestamp | str, date | datetime | pd.Timestamp | str] | None = None,
) -> RangeState:
    session = st.session_state if session_state is None else session_state
    normalized = prepare_time_series_frame(frame, max_points=len(frame))
    if normalized.empty:
        raise ValueError("날짜 범위를 계산할 수 있는 시계열 데이터가 없습니다.")

    min_date = normalized["date"].min().date()
    max_date = normalized["date"].max().date()
    mode_key = f"{key_prefix}_range_mode"
    preset_key = f"{key_prefix}_range_preset"
    dates_key = f"{key_prefix}_range_dates"

    stored_mode = str(session.get(mode_key, "preset"))
    stored_preset = str(session.get(preset_key, default_preset))
    stored_dates = session.get(dates_key)

    if selected_dates is not None:
        resolved_dates = normalize_range_dates(selected_dates, min_date=min_date, max_date=max_date)
        mode = "custom"
        preset = stored_preset
    elif selected_preset is not None:
        preset = normalize_range_preset(selected_preset, default_preset=default_preset)
        resolved_dates = range_dates_for_preset(preset, min_date=min_date, max_date=max_date)
        mode = "preset"
    else:
        preset = normalize_range_preset(stored_preset, default_preset=default_preset)
        if stored_mode == "custom" and stored_dates is not None:
            resolved_dates = normalize_range_dates(stored_dates, min_date=min_date, max_date=max_date)
            mode = "custom"
        else:
            resolved_dates = range_dates_for_preset(preset, min_date=min_date, max_date=max_date)
            mode = "preset"

    session[mode_key] = mode
    session[preset_key] = preset
    session[dates_key] = resolved_dates
    return RangeState(mode=mode, preset=preset, dates=resolved_dates, min_date=min_date, max_date=max_date)


def normalize_range_preset(preset: str | None, *, default_preset: str = DEFAULT_RANGE_PRESET) -> str:
    candidate = str(preset or default_preset)
    if candidate in RANGE_PRESET_DAYS:
        return candidate
    return default_preset


def range_dates_for_preset(
    preset: str,
    *,
    min_date: date,
    max_date: date,
) -> tuple[date, date]:
    days = preset_days(preset)
    if days is None:
        return (min_date, max_date)
    start_date = max(min_date, max_date - timedelta(days=max(days - 1, 0)))
    return (start_date, max_date)


def normalize_range_dates(
    value: tuple[date | datetime | pd.Timestamp | str, date | datetime | pd.Timestamp | str] | list[date | datetime | pd.Timestamp | str],
    *,
    min_date: date,
    max_date: date,
) -> tuple[date, date]:
    if len(value) != 2:
        raise ValueError("조회 기간은 시작일과 종료일 2개 값이어야 합니다.")
    start_raw, end_raw = value
    start_date = clamp_date(coerce_to_date(start_raw), min_date=min_date, max_date=max_date)
    end_date = clamp_date(coerce_to_date(end_raw), min_date=min_date, max_date=max_date)
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    return (start_date, end_date)


def coerce_to_date(value: date | datetime | pd.Timestamp | str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"날짜로 해석할 수 없는 값입니다: {value!r}")
    return parsed.date()


def clamp_date(value: date, *, min_date: date, max_date: date) -> date:
    if value < min_date:
        return min_date
    if value > max_date:
        return max_date
    return value


def apply_time_window(
    frame: pd.DataFrame,
    range_dates: tuple[date | datetime | pd.Timestamp | str, date | datetime | pd.Timestamp | str],
) -> pd.DataFrame:
    normalized = prepare_time_series_frame(frame, max_points=len(frame))
    if normalized.empty:
        return normalized
    min_date = normalized["date"].min().date()
    max_date = normalized["date"].max().date()
    start_date, end_date = normalize_range_dates(range_dates, min_date=min_date, max_date=max_date)
    mask = normalized["date"].dt.date.between(start_date, end_date)
    return normalized.loc[mask].reset_index(drop=True)


def infer_date_column(frame: pd.DataFrame) -> str | None:
    for column in ("date", "stck_bsop_date"):
        if column in frame.columns:
            return column
    return None


def flow_series_columns(frame: pd.DataFrame) -> list[str]:
    columns: list[str] = []
    for column in ("foreign_net", "institutional_net", "personal_net", "frgn_ntby_qty", "orgn_ntby_qty", "prsn_ntby_qty"):
        if column in frame.columns and pd.to_numeric(frame[column], errors="coerce").notna().any():
            columns.append(column)
    return columns


def render_chart_selector(
    frame: pd.DataFrame,
    *,
    dataset_name: str,
    key_prefix: str,
    height: int = 280,
) -> None:
    if is_professional_stock_dataset(dataset_name, frame):
        if preferred_chart_library() == "plotly" and go is not None and make_subplots is not None:
            _render_professional_chart_selector(frame, key_prefix=key_prefix, height=height)
            return
        st.info("전문가용 주가 차트를 그리려면 Plotly가 필요해 기본 차트로 대신 보여드립니다.")

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
    selected_preset, selected_dates = render_range_controls(frame, key_prefix=key_prefix)
    range_state = resolve_range_state(
        frame,
        key_prefix=key_prefix,
        selected_preset=selected_preset,
        selected_dates=selected_dates,
    )
    filtered_frame = apply_time_window(frame, range_state.dates)
    st.caption(
        f"조회 기간: {range_state.dates[0].isoformat()} ~ {range_state.dates[1].isoformat()}"
    )
    chart = build_chart(filtered_frame, selected_key, height=height, library=preferred_chart_library())
    if chart is None:
        st.info("선택한 차트를 그리기 위한 컬럼이 부족합니다.")
        return
    render_chart(chart, key_prefix=key_prefix)


def _render_professional_chart_selector(
    frame: pd.DataFrame,
    *,
    key_prefix: str,
    height: int,
) -> None:
    selected_preset, selected_dates = render_range_controls(frame, key_prefix=key_prefix)
    timeframe_keys = [key for key, _label in TIMEFRAME_OPTIONS]
    timeframe_key = st.radio(
        "봉 기준",
        options=timeframe_keys,
        index=0,
        format_func=lambda key: TIMEFRAME_LABELS[key],
        horizontal=True,
        key=f"{key_prefix}_timeframe",
    )
    range_state = resolve_range_state(
        frame,
        key_prefix=key_prefix,
        selected_preset=selected_preset,
        selected_dates=selected_dates,
    )
    filtered_frame = apply_time_window(frame, range_state.dates)
    aggregated = aggregate_professional_chart_frame(filtered_frame, timeframe_key)
    st.caption(f"조회 기간: {range_state.dates[0].isoformat()} ~ {range_state.dates[1].isoformat()}")
    if aggregated.empty:
        st.info("선택한 기간에 표시할 차트 데이터가 없습니다.")
        return
    if not flow_series_columns(aggregated):
        st.caption("수급 데이터 없음")
    chart = build_professional_plotly_chart(aggregated, timeframe=timeframe_key, height=height)
    if chart is None:
        st.info("전문가용 차트를 그리기 위한 컬럼이 부족합니다.")
        return
    render_chart(chart, key_prefix=key_prefix)


def render_range_controls(
    frame: pd.DataFrame,
    *,
    key_prefix: str,
) -> tuple[str | None, tuple[date, date] | None]:
    current_state = resolve_range_state(frame, key_prefix=key_prefix)
    preset_options = [option.key for option in RANGE_PRESET_OPTIONS]
    preset_labels = {option.key: option.label for option in RANGE_PRESET_OPTIONS}
    preset_widget_key = f"{key_prefix}_range_preset_widget"
    date_widget_key = f"{key_prefix}_range_dates_widget"

    selected_preset = st.radio(
        "빠른 조회 기간",
        options=preset_options,
        index=preset_options.index(current_state.preset),
        format_func=lambda key: preset_labels[key],
        horizontal=True,
        key=preset_widget_key,
    )
    selected_dates = st.date_input(
        "직접 기간 선택",
        value=current_state.dates,
        min_value=current_state.min_date,
        max_value=current_state.max_date,
        key=date_widget_key,
    )

    normalized_selected_dates = tuple(selected_dates) if isinstance(selected_dates, (list, tuple)) and len(selected_dates) == 2 else current_state.dates
    if selected_preset != current_state.preset:
        st.session_state[date_widget_key] = range_dates_for_preset(
            selected_preset,
            min_date=current_state.min_date,
            max_date=current_state.max_date,
        )
        return (selected_preset, None)
    if normalized_selected_dates != current_state.dates:
        return (None, normalized_selected_dates)
    return (None, None)


def preferred_chart_library() -> str:
    return "plotly" if go is not None else "altair"


def render_chart(chart, *, key_prefix: str) -> None:
    if preferred_chart_library() == "plotly" and go is not None:
        st.plotly_chart(chart, use_container_width=True, key=f"{key_prefix}_plotly_chart")
        return
    st.altair_chart(chart, use_container_width=True)


def build_chart(frame: pd.DataFrame, chart_type: str, *, height: int = 280, library: str | None = None):
    normalized = prepare_time_series_frame(frame, max_points=len(frame))
    if normalized.empty:
        return None
    resolved_library = library or preferred_chart_library()
    if resolved_library == "plotly" and go is not None:
        return build_plotly_chart(normalized, chart_type, height=height)
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


def build_professional_plotly_chart(frame: pd.DataFrame, *, timeframe: str = "daily", height: int = 560):
    if go is None or make_subplots is None:
        return None
    required = {"date", "open", "high", "low", "close", "rsi_14"}
    if not required.issubset(frame.columns):
        return None

    chart_data = frame.sort_values("date").reset_index(drop=True)
    flow_columns = flow_series_columns(chart_data)
    has_volume = "volume" in chart_data.columns and pd.to_numeric(chart_data["volume"], errors="coerce").notna().any()
    row_titles = [
        f"가격 ({TIMEFRAME_LABELS[normalize_timeframe_key(timeframe)]})",
        "거래량" if has_volume else "거래량 없음",
        "RSI 14",
    ]
    if flow_columns:
        row_titles.append(FLOW_ROW_TITLE)
    row_count = 4 if flow_columns else 3
    row_heights = [0.5, 0.18, 0.18] + ([0.14] if flow_columns else [])
    figure = make_subplots(
        rows=row_count,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
        subplot_titles=row_titles,
    )
    figure.add_trace(
        go.Candlestick(
            x=chart_data["date"],
            open=chart_data["open"],
            high=chart_data["high"],
            low=chart_data["low"],
            close=chart_data["close"],
            name="캔들",
            increasing_line_color="#dc2626",
            decreasing_line_color="#2563eb",
            hovertemplate=None,
        ),
        row=1,
        col=1,
    )
    palette = dict(zip(PRICE_COLOR_DOMAIN, PRICE_COLOR_RANGE, strict=False))
    for column in ("ma_5", "ma_20", "ma_60"):
        if column not in chart_data.columns:
            continue
        figure.add_trace(
            go.Scatter(
                x=chart_data["date"],
                y=chart_data[column],
                mode="lines",
                name=SERIES_LABELS.get(column, column),
                line=dict(width=2, color=palette.get(SERIES_LABELS.get(column, column))),
                hovertemplate="%{x|%Y-%m-%d}<br>%{fullData.name}: %{y:,.0f}<extra></extra>",
            ),
            row=1,
            col=1,
        )
    if has_volume:
        figure.add_trace(
            go.Bar(
                x=chart_data["date"],
                y=pd.to_numeric(chart_data["volume"], errors="coerce"),
                name="거래량",
                marker_color="#2563eb",
                hovertemplate="%{x|%Y-%m-%d}<br>거래량: %{y:,.0f}<extra></extra>",
            ),
            row=2,
            col=1,
        )
    figure.add_trace(
        go.Scatter(
            x=chart_data["date"],
            y=chart_data["rsi_14"],
            mode="lines",
            name="RSI 14",
            line=dict(width=2, color="#7c3aed"),
            hovertemplate="%{x|%Y-%m-%d}<br>RSI 14: %{y:.2f}<extra></extra>",
        ),
        row=3,
        col=1,
    )
    figure.add_hline(y=30, line_dash="dash", line_color="#9ca3af", row=3, col=1)
    figure.add_hline(y=70, line_dash="dash", line_color="#9ca3af", row=3, col=1)
    if flow_columns:
        palette = dict(zip(FLOW_COLOR_DOMAIN, FLOW_COLOR_RANGE, strict=False))
        for column in flow_columns:
            label = SERIES_LABELS.get(column, column)
            figure.add_trace(
                go.Scatter(
                    x=chart_data["date"],
                    y=chart_data[column],
                    mode="lines",
                    name=label,
                    line=dict(width=2, color=palette.get(label)),
                    hovertemplate="%{x|%Y-%m-%d}<br>%{fullData.name}: %{y:,.0f}<extra></extra>",
                ),
                row=4,
                col=1,
            )
        figure.add_hline(y=0, line_dash="dot", line_color="#9ca3af", row=4, col=1)

    figure.update_layout(
        height=height,
        hovermode="x unified",
        margin=dict(l=20, r=20, t=24, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(showspikes=True, spikemode="across", spikesnap="cursor", spikedash="solid", spikethickness=1, rangeslider=dict(visible=False)),
    )
    figure.update_yaxes(title_text="가격", row=1, col=1)
    figure.update_yaxes(title_text="거래량" if has_volume else "거래량 없음", row=2, col=1)
    figure.update_yaxes(title_text="RSI 14", range=[0, 100], row=3, col=1)
    if flow_columns:
        figure.update_yaxes(title_text="순매수", row=4, col=1)
    return figure


def build_plotly_chart(frame: pd.DataFrame, chart_type: str, *, height: int = 280):
    if chart_type == "close_only":
        return build_plotly_price_line_chart(frame, ["close"], height=height)
    if chart_type == "close_ma":
        columns = [column for column in ("close", "ma_5", "ma_20", "ma_60") if column in frame.columns]
        return build_plotly_price_line_chart(frame, columns, height=height)
    if chart_type == "candlestick":
        return build_plotly_candlestick_chart(frame, height=height)
    if chart_type == "volume":
        return build_plotly_volume_chart(frame, height=height)
    if chart_type == "rsi":
        return build_plotly_rsi_chart(frame, height=height)
    if chart_type == "flow":
        return build_plotly_flow_chart(frame, height=height)
    return None


def apply_plotly_interaction_layout(figure, *, height: int, yaxis_title: str) -> None:
    figure.update_layout(
        height=height,
        hovermode="x unified",
        margin=dict(l=20, r=20, t=16, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(
            title="날짜",
            showspikes=True,
            spikemode="across",
            spikesnap="cursor",
            spikedash="solid",
            spikethickness=1,
            rangeslider=dict(visible=False),
        ),
        yaxis=dict(title=yaxis_title),
    )


def build_plotly_price_line_chart(frame: pd.DataFrame, columns: list[str], *, height: int):
    columns = [column for column in columns if column in frame.columns]
    if not columns:
        return None
    figure = go.Figure()
    palette = dict(zip(PRICE_COLOR_DOMAIN, PRICE_COLOR_RANGE, strict=False))
    for column in columns:
        label = SERIES_LABELS.get(column, column)
        figure.add_trace(
            go.Scatter(
                x=frame["date"],
                y=frame[column],
                mode="lines+markers",
                name=label,
                line=dict(width=2, color=palette.get(label)),
                hovertemplate="%{x|%Y-%m-%d}<br>%{fullData.name}: %{y:,.0f}<extra></extra>",
            )
        )
    apply_plotly_interaction_layout(figure, height=height, yaxis_title="가격")
    return figure


def build_plotly_candlestick_chart(frame: pd.DataFrame, *, height: int):
    required = {"open", "high", "low", "close"}
    if not required.issubset(frame.columns):
        return None
    chart_data = frame[["date", "open", "high", "low", "close"]].dropna()
    if chart_data.empty:
        return None
    figure = go.Figure(
        data=[
            go.Candlestick(
                x=chart_data["date"],
                open=chart_data["open"],
                high=chart_data["high"],
                low=chart_data["low"],
                close=chart_data["close"],
                name="캔들",
                increasing_line_color="#dc2626",
                decreasing_line_color="#2563eb",
                hovertemplate=None,
            )
        ]
    )
    apply_plotly_interaction_layout(figure, height=height, yaxis_title="가격")
    return figure


def build_plotly_volume_chart(frame: pd.DataFrame, *, height: int):
    if "volume" not in frame.columns:
        return None
    chart_data = frame[["date", "volume"]].dropna()
    if chart_data.empty:
        return None
    figure = go.Figure(
        data=[
            go.Bar(
                x=chart_data["date"],
                y=chart_data["volume"],
                name="거래량",
                marker_color="#2563eb",
                hovertemplate="%{x|%Y-%m-%d}<br>거래량: %{y:,.0f}<extra></extra>",
            )
        ]
    )
    apply_plotly_interaction_layout(figure, height=height, yaxis_title="거래량")
    return figure


def build_plotly_rsi_chart(frame: pd.DataFrame, *, height: int):
    if "rsi_14" not in frame.columns:
        return None
    chart_data = frame[["date", "rsi_14"]].dropna()
    if chart_data.empty:
        return None
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=chart_data["date"],
            y=chart_data["rsi_14"],
            mode="lines+markers",
            name="RSI 14",
            line=dict(width=2, color="#7c3aed"),
            hovertemplate="%{x|%Y-%m-%d}<br>RSI 14: %{y:.2f}<extra></extra>",
        )
    )
    for level, label in ((30, "과매도 기준"), (70, "과열 기준")):
        figure.add_hline(y=level, line_dash="dash", line_color="#9ca3af", annotation_text=label, annotation_position="top left")
    apply_plotly_interaction_layout(figure, height=height, yaxis_title="RSI 14")
    figure.update_yaxes(range=[0, 100])
    return figure


def build_plotly_flow_chart(frame: pd.DataFrame, *, height: int):
    columns = flow_series_columns(frame)
    if not columns:
        return None
    figure = go.Figure()
    palette = dict(zip(FLOW_COLOR_DOMAIN, FLOW_COLOR_RANGE, strict=False))
    for column in columns:
        label = SERIES_LABELS.get(column, column)
        figure.add_trace(
            go.Scatter(
                x=frame["date"],
                y=frame[column],
                mode="lines+markers",
                name=label,
                line=dict(width=2, color=palette.get(label)),
                hovertemplate="%{x|%Y-%m-%d}<br>%{fullData.name}: %{y:,.0f}<extra></extra>",
            )
        )
    apply_plotly_interaction_layout(figure, height=height, yaxis_title="순매수")
    figure.add_hline(y=0, line_dash="dot", line_color="#9ca3af")
    return figure


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
