from __future__ import annotations

from datetime import UTC, date, datetime

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from invest_bot.dashboard import streamlit_charts as charts
from invest_bot.dashboard import streamlit_actions as actions
from invest_bot.dashboard.service import DashboardDataService
from invest_bot.dashboard.streamlit_state import DashboardFrameLoader
from invest_bot.db.contracts import DatasetFrameRecord
from invest_bot.db.repositories import frame_to_json
from invest_bot.market.storage import CsvStorage


@pytest.fixture(autouse=True)
def forbid_execution_during_chart_reads(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("chart reads must not collect, analyse, generate or send")

    for name in (
        "run_collect_action", "run_full_pipeline_action", "run_market_report_batch_action",
        "run_batch_symbol_action", "generate_indicators_for_symbol",
        "generate_golden_cross_signals_for_symbol", "generate_market_report_for_symbol",
    ):
        monkeypatch.setattr(actions, name, forbidden)


def prices():
    return pd.DataFrame([
        {"date": day, "open": 99, "high": 102, "low": 98, "close": 100 + index, "volume": 1000}
        for index, day in enumerate(pd.date_range("2026-10-01", periods=2))
    ])


def record(dataset, frame, symbol="005930", filename=None):
    return DatasetFrameRecord(
        dataset=dataset, filename=filename or f"{symbol}_{dataset}.csv", symbol=symbol,
        frame_json=frame_to_json(frame), row_count=len(frame), created_at=datetime(2026, 10, 3, tzinfo=UTC),
    )


def loader_for(detail=None, summary=None):
    records = [record("daily_prices_indicators", prices())]
    for dataset, frame in (("investor_daily", detail), ("investor_daily_summary", summary)):
        if frame is not None:
            records.append(record(dataset, frame))
    # Explicit snapshot reads must not consult any backing storage.
    service = DashboardDataService(raw_root="/virtual/raw", processed_root="/virtual/processed")
    return DashboardFrameLoader(service, records)


@pytest.mark.parametrize("detail", [
    None, pd.DataFrame(), pd.DataFrame([{"foreign_net": 999}]),
    pd.DataFrame([{"date": "invalid", "foreign_net": 999}]),
    pd.DataFrame([{"date": "2026-10-02", "foreign_net": None}]),
    pd.DataFrame([{"date": "2026-10-02", "unrelated": 999}]),
    pd.DataFrame([{"date": "2026-10-02", "foreign_net": "bad"}]),
    pd.DataFrame([{"date": "2026-10-02", "foreign_net": float("inf")}]),
])
def test_summary_fallback_uses_its_own_dates_and_values(detail):
    summary = pd.DataFrame([{"stck_bsop_date": "20261002", "frgn_ntby_qty": "12", "orgn_ntby_qty": "0"}])
    result = loader_for(detail, summary).load_professional("005930")
    assert result is not None
    assert result.attrs["investor_flow_source"] == "summary"
    assert result.loc[1, "frgn_ntby_qty"] == 12
    assert result.loc[1, "orgn_ntby_qty"] == 0
    assert pd.isna(result.loc[0, "frgn_ntby_qty"])
    assert "foreign_net" not in result
    assert_frame_equal(result[prices().columns], prices())


@pytest.mark.parametrize("date_alias", ["date", "trade_date", "stck_bsop_date"])
@pytest.mark.parametrize("value_alias", ["foreign_net", "frgn_ntby_qty"])
def test_summary_mixed_date_formats_numeric_strings_zero_and_partial_values(date_alias, value_alias):
    summary = pd.DataFrame([
        {date_alias: 20261001, value_alias: "0", "institutional_net": None},
        {date_alias: pd.Timestamp("2026-10-02"), value_alias: "-3.5", "institutional_net": "4"},
        {date_alias: "2026-10-03", value_alias: 999, "institutional_net": 999},
    ])
    result = loader_for(summary=summary).load_professional("005930")
    assert result is not None
    assert result[value_alias].tolist() == [0, -3.5]
    assert pd.isna(result.loc[0, "institutional_net"])
    assert result.loc[1, "institutional_net"] == 4
    assert "personal_net" not in result


def test_valid_detail_is_authoritative_without_summary_gap_filling():
    detail = pd.DataFrame([{"trade_date": "2026-10-01", "foreign_net": 0, "personal_net": None}])
    summary = pd.DataFrame([
        {"date": "2026-10-01", "foreign_net": 999, "personal_net": 50},
        {"date": "2026-10-02", "foreign_net": 999, "personal_net": 50},
    ])
    result = loader_for(detail, summary).load_professional("005930")
    assert result is not None
    assert result.attrs["investor_flow_source"] == "detail"
    assert result.loc[0, "foreign_net"] == 0
    assert pd.isna(result.loc[1, "foreign_net"])
    assert "personal_net" not in result


def test_aliases_coalesce_only_within_the_selected_source_and_observation():
    summary = pd.DataFrame([
        {"date": "2026-10-01", "foreign_net": "0", "frgn_ntby_qty": 999, "orgn_ntby_qty": "-2", "prsn_ntby_qty": "2"},
        {"date": "2026-10-02", "foreign_net": None, "frgn_ntby_qty": "3", "orgn_ntby_qty": None, "prsn_ntby_qty": "-3"},
    ])
    result = loader_for(summary=summary).load_professional("005930")
    assert result is not None
    assert result["foreign_net"].tolist() == [0, 3]
    assert "frgn_ntby_qty" not in result
    assert result["prsn_ntby_qty"].tolist() == [2, -3]
    assert pd.isna(result.loc[1, "orgn_ntby_qty"])


@pytest.mark.parametrize("summary", [
    None, pd.DataFrame(), pd.DataFrame([{"foreign_net": 5}]),
    pd.DataFrame([{"date": "2026-02-30", "foreign_net": 5}]),
    pd.DataFrame([{"date": "2026-10-02"}]),
    pd.DataFrame([{"date": "2026-10-02", "foreign_net": None}]),
])
def test_invalid_sources_never_date_or_broadcast_undated_detail(summary):
    detail = pd.DataFrame([{"foreign_net": 100}, {"foreign_net": 200}])
    result = loader_for(detail, summary).load_professional("005930")
    assert result is not None
    assert charts.flow_series_columns(result) == []
    assert result.attrs["investor_flow_source"] is None
    assert "수급 데이터 없음" in result.attrs["investor_flow_message"]
    assert_frame_equal(result, prices())


def test_values_with_invalid_dates_cannot_make_a_source_usable():
    detail = pd.DataFrame([
        {"date": "bad", "foreign_net": 100},
        {"date": "2026-10-02", "foreign_net": None},
    ])
    result = loader_for(detail, pd.DataFrame([{"date": "2026-10-02", "foreign_net": 8}])).load_professional("005930")
    assert result is not None and result.loc[1, "foreign_net"] == 8
    assert result.attrs["investor_flow_source"] == "summary"


@pytest.mark.parametrize("invalid_date", ["2026", "2026-10", 0, "20260230", "20261002.5"])
def test_incomplete_or_invalid_dates_do_not_invent_an_observation_day(invalid_date):
    base = prices()
    base["date"] = pd.to_datetime(["2026-01-01", "2026-10-01"])
    records = [record("daily_prices_indicators", base), record("investor_daily_summary", pd.DataFrame([
        {"date": invalid_date, "foreign_net": 10},
    ]))]
    result = DashboardFrameLoader(DashboardDataService(raw_root="/virtual/raw"), records).load_professional("005930")
    assert result is not None
    assert charts.flow_series_columns(result) == []
    assert result.attrs["investor_flow_source"] is None


def test_date_alias_priority_valid_row_fallback_and_civil_day():
    summary = pd.DataFrame([
        {"date": "invalid", "trade_date": "2026-10-01T23:30:00-09:00", "stck_bsop_date": "20261002", "foreign_net": 10},
        {"date": "2026-10-02", "trade_date": "2026-10-01", "foreign_net": 20},
    ])
    result = loader_for(summary=summary).load_professional("005930")
    assert result is not None and result["foreign_net"].tolist() == [10, 20]


@pytest.mark.parametrize("blank_payload", ["", "  "])
def test_explicit_snapshot_missing_summary_and_blank_payload_do_not_read_storage(monkeypatch, blank_payload):
    service = DashboardDataService(raw_root="/virtual/raw", processed_root="/virtual/processed")

    def forbidden(*args, **kwargs):
        pytest.fail("snapshot omissions/blank payloads must not query storage")

    monkeypatch.setattr(service, "get_dataset_storage", forbidden)
    blank = DatasetFrameRecord(
        dataset="investor_daily", filename="005930_detail.csv", symbol="005930",
        frame_json=blank_payload, row_count=0, created_at=datetime(2026, 10, 3, tzinfo=UTC),
    )
    records = [record("daily_prices_indicators", prices()), blank]
    result = DashboardFrameLoader(service, records).load_professional("005930")
    assert result is not None and charts.flow_series_columns(result) == []
    records.append(record("investor_daily_summary", pd.DataFrame([{"date": "2026-10-02", "foreign_net": 3}])))
    result = DashboardFrameLoader(service, records).load_professional("005930")
    assert result is not None and result.loc[1, "foreign_net"] == 3


def test_normal_detail_keeps_ohlcv_and_nested_attrs_immutable(monkeypatch):
    base = prices()
    base.attrs["origin"] = {"labels": ["unchanged"]}
    detail = pd.DataFrame([
        {"date": "2026-10-01", "frgn_ntby_qty": 10, "orgn_ntby_qty": -5, "prsn_ntby_qty": -5},
        {"date": "2026-10-02", "frgn_ntby_qty": 12, "orgn_ntby_qty": -6, "prsn_ntby_qty": -6},
    ])
    before_base, before_detail = base.copy(deep=True), detail.copy(deep=True)

    class Storage:
        root_dir = "/virtual/raw"

        def latest_filename(self, dataset, symbol):
            assert dataset != "investor_daily_summary", "valid detail must not trigger summary lookup"
            return dataset

        def load(self, dataset, filename):
            return base if dataset == "daily_prices_indicators" else detail

    result = DashboardFrameLoader(DashboardDataService(dataset_storage=Storage())).load_professional("005930")
    assert result is not None
    expected = prices().merge(detail.assign(date=pd.to_datetime(detail["date"])), on="date", how="left")
    assert_frame_equal(result, expected, check_dtype=False)
    expected_chart = charts.build_professional_plotly_chart(
        charts.aggregate_professional_chart_frame(expected, "daily"), height=charts.PROFESSIONAL_CHART_MIN_HEIGHT,
    )
    actual_chart = render_screen(monkeypatch, result).figures[0]
    assert actual_chart.to_json() == expected_chart.to_json()
    result.attrs["origin"]["labels"].append("changed")
    result.loc[0, "close"] = -1
    result.loc[0, "frgn_ntby_qty"] = -1
    assert_frame_equal(base, before_base)
    assert_frame_equal(detail, before_detail)
    assert base.attrs == before_base.attrs


def test_nonoverlapping_valid_detail_is_not_replaced_by_summary():
    detail = pd.DataFrame([{"date": "2026-11-02", "foreign_net": 10}])
    summary = pd.DataFrame([{"date": "2026-10-02", "foreign_net": 999}])
    result = loader_for(detail, summary).load_professional("005930")
    assert result is not None
    assert charts.flow_series_columns(result) == []
    assert result.attrs["investor_flow_source"] == "detail"
    assert "일치하지" in result.attrs["investor_flow_message"]


def test_file_mode_caches_reads_preserves_inputs_and_refreshes_next_request(tmp_path, monkeypatch):
    raw = CsvStorage(tmp_path / "raw")
    processed = CsvStorage(tmp_path / "processed")
    processed.save("daily_prices_indicators", "005930_prices.csv", prices())
    raw.save("investor_daily", "005930_detail.csv", pd.DataFrame([{"foreign_net": 999}]))
    raw.save("investor_daily_summary", "005930_summary.csv", pd.DataFrame([{"date": "2026-10-02", "foreign_net": 7}]))
    service = DashboardDataService(raw_root=raw.root_dir, processed_root=processed.root_dir)
    reads = []
    original_read = pd.read_csv

    def read(*args, **kwargs):
        reads.append(str(args[0]))
        return original_read(*args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", read)
    loader = DashboardFrameLoader(service)
    first = loader.load_professional("005930")
    assert first is not None
    before = first.copy(deep=True)
    first.loc[1, "foreign_net"] = -1
    first.attrs["investor_flow_source"] = "changed"
    repeated = loader.load_professional("005930")
    assert repeated is not None
    assert_frame_equal(repeated, before)
    assert repeated.attrs == before.attrs
    assert len(reads) == 3
    raw.save("investor_daily_summary", "005930_summary.csv", pd.DataFrame([{"date": "2026-10-02", "foreign_net": 9}]))
    assert loader.load_professional("005930").loc[1, "foreign_net"] == 7
    assert DashboardFrameLoader(service).load_professional("005930").loc[1, "foreign_net"] == 9
    assert len(reads) == 6


class ChartScreen:
    def __init__(self, selected_dates=None, timeframe="daily"):
        self.session_state = {}
        self.captions = []
        self.figures = []
        self.selected_dates = selected_dates
        self.timeframe = timeframe

    def caption(self, text):
        self.captions.append(text)

    def info(self, text):
        self.captions.append(text)

    def radio(self, label, options, index=0, **kwargs):
        if label == "봉 기준":
            return self.timeframe
        return options[index]

    def plotly_chart(self, figure, **kwargs):
        self.figures.append(figure)


def render_screen(monkeypatch, frame, selected_dates=None, timeframe="daily"):
    screen = ChartScreen(selected_dates, timeframe)
    monkeypatch.setattr(charts, "st", screen)
    # Only the range input is fixed. The real selector, aggregation, builder and renderer run.
    monkeypatch.setattr(charts, "render_range_controls", lambda *args, **kwargs: (None, selected_dates))
    charts.render_chart_selector(frame, dataset_name="daily_prices_indicators", key_prefix="summary")
    assert len(screen.figures) == 1
    return screen


def test_real_chart_renders_summary_panel_without_changing_price_spec(monkeypatch):
    frame = loader_for(summary=pd.DataFrame([{"date": "2026-10-02", "foreign_net": "0"}])).load_professional("005930")
    screen = render_screen(monkeypatch, frame)
    figure = screen.figures[0]
    assert "요약" in " ".join(screen.captions)
    flow = next(trace for trace in figure.data if trace.name == "외국인 순매수")
    assert pd.isna(flow.y[0]) and flow.y[1] == 0
    assert flow.yaxis == "y4"
    price = next(trace for trace in figure.data if trace.type == "candlestick")
    assert list(price.close) == prices()["close"].tolist()
    assert figure.layout.hovermode == "x unified"


@pytest.mark.parametrize("summary, selected_dates, expected", [
    (None, None, "관측일"),
    (pd.DataFrame([{"date": "2026-11-02", "foreign_net": 10}]), None, "일치하지"),
    (pd.DataFrame([{"date": "2026-10-02", "foreign_net": 10}]), (date(2026, 10, 1), date(2026, 10, 1)), "조회 기간"),
])
def test_real_chart_explains_missing_or_nonoverlapping_flow(monkeypatch, summary, selected_dates, expected):
    frame = loader_for(pd.DataFrame([{"foreign_net": 999}]), summary).load_professional("005930")
    screen = render_screen(monkeypatch, frame, selected_dates)
    assert expected in " ".join(screen.captions)
    assert not any(trace.name == "외국인 순매수" for trace in screen.figures[0].data)


def test_period_aggregation_keeps_unobserved_flow_null(monkeypatch):
    base = prices()
    base["date"] = pd.to_datetime(["2026-09-30", "2026-10-02"])
    records = [record("daily_prices_indicators", base), record("investor_daily_summary", pd.DataFrame([
        {"date": "2026-10-02", "foreign_net": 0},
    ]))]
    frame = DashboardFrameLoader(DashboardDataService(raw_root="/virtual/raw"), records).load_professional("005930")
    assert frame is not None
    before = frame.copy(deep=True)
    screen = render_screen(monkeypatch, frame, timeframe="monthly")
    flow = next(trace for trace in screen.figures[0].data if trace.name == "외국인 순매수")
    assert pd.isna(flow.y[0]) and flow.y[1] == 0
    assert_frame_equal(frame, before)
    assert frame.attrs == before.attrs


def test_explicit_empty_snapshot_is_authoritative(monkeypatch):
    service = DashboardDataService(raw_root="/virtual/raw", processed_root="/virtual/processed")

    def forbidden(*args, **kwargs):
        pytest.fail("an explicit snapshot must not read backing storage")

    monkeypatch.setattr(service, "get_dataset_storage", forbidden)
    assert DashboardFrameLoader(service, ()).load_professional("005930") is None
