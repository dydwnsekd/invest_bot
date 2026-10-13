"""Leader-authored G05a boundaries, separate from the implementation tests."""
from datetime import UTC, datetime

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from invest_bot.dashboard.service import DashboardDataService
from invest_bot.dashboard.streamlit_state import DashboardFrameLoader
from invest_bot.db.contracts import DatasetFrameRecord
from invest_bot.db.repositories import frame_to_json


def load_chart(price_dates, *, detail=None, summary=None, price_flow=None):
    price = pd.DataFrame({
        "date": price_dates, "open": 10, "high": 12, "low": 9, "close": 11,
        "volume": 100,
    })
    if price_flow:
        for column, values in price_flow.items():
            price[column] = values
    frames = {"daily_prices_indicators": price, "investor_daily": detail,
              "investor_daily_summary": summary}
    records = [DatasetFrameRecord(
        dataset=name, symbol="005930", filename=f"005930_{name}.csv",
        frame_json=frame_to_json(frame), row_count=len(frame),
        created_at=datetime(2026, 10, 13, tzinfo=UTC),
    ) for name, frame in frames.items() if frame is not None]
    service = DashboardDataService(raw_root="/virtual/raw", processed_root="/virtual/processed")

    def forbidden():
        pytest.fail("an explicit snapshot must not read backing storage")

    service.get_dataset_storage = forbidden
    result = DashboardFrameLoader(service, records).load_professional("005930")
    assert result is not None
    # Compare with the existing price loader to isolate investor alignment.
    baseline = DashboardFrameLoader(service, records[:1]).load_professional("005930")
    assert_frame_equal(result[["date", "open", "high", "low", "close", "volume"]],
                       baseline[["date", "open", "high", "low", "close", "volume"]])
    return result


@pytest.mark.parametrize("timezone", [None, "Asia/Seoul"])
@pytest.mark.parametrize("source", ["detail", "summary"])
def test_daily_observation_matches_price_timestamp_without_changing_price(timezone, source):
    dates = pd.date_range("2026-10-01 15:30", periods=2, tz=timezone)
    observations = pd.DataFrame({"date": ["2026-10-01", "2026-10-02"], "foreign_net": [0, -5]})
    result = load_chart(dates, **{source: observations})
    assert result["foreign_net"].tolist() == [0, -5]
    assert result.attrs["investor_flow_source"] == source


def test_daily_value_is_not_broadcast_to_multiple_prices_on_the_same_day():
    result = load_chart(pd.to_datetime(["2026-10-01 10:00", "2026-10-01 15:30", "2026-10-02"], format="mixed"),
                        summary=pd.DataFrame({"date": ["2026-10-01", "2026-10-02"], "foreign_net": [99, 7]}))
    assert result["foreign_net"].iloc[:2].isna().all()
    assert result["foreign_net"].iloc[2] == 7


@pytest.mark.parametrize("source", ["detail", "summary", None])
def test_chart_does_not_mix_flow_from_price_frame_with_selected_source(source):
    observations = pd.DataFrame({"date": ["2026-10-02"], "frgn_ntby_qty": [7]})
    result = load_chart(pd.date_range("2026-10-01", periods=2),
                        price_flow={"foreign_net": [999, 999], "personal_net": [999, 999]},
                        **({source: observations} if source else {}))
    assert "foreign_net" not in result and "personal_net" not in result
    if source:
        assert pd.isna(result.loc[0, "frgn_ntby_qty"])
        assert result.loc[1, "frgn_ntby_qty"] == 7
    else:
        assert result.attrs["investor_flow_source"] is None
        assert "수급 데이터 없음" in result.attrs["investor_flow_message"]


def test_chosen_detail_never_fills_missing_investors_or_dates_from_summary():
    result = load_chart(pd.date_range("2026-10-01", periods=3),
                        detail=pd.DataFrame({"date": ["2026-10-02"], "foreign_net": [0]}),
                        summary=pd.DataFrame({"date": ["2026-10-01", "2026-10-03"],
                                              "foreign_net": [999, 999], "personal_net": [999, 999]}))
    assert result.attrs["investor_flow_source"] == "detail"
    assert result["foreign_net"].isna().tolist() == [True, False, True]
    assert result.loc[1, "foreign_net"] == 0
    assert "personal_net" not in result


def test_future_observation_is_not_replaced_by_in_range_summary():
    result = load_chart(pd.date_range("2026-10-01", periods=2),
                        detail=pd.DataFrame({"date": ["2026-10-03"], "foreign_net": [99]}),
                        summary=pd.DataFrame({"date": ["2026-10-02"], "foreign_net": [7]}))
    assert result.attrs["investor_flow_source"] == "detail"
    assert result["foreign_net"].isna().all()
    assert "일치하지" in result.attrs["investor_flow_message"]
