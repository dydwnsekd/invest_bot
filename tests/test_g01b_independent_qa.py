"""Independent G01b numeric-date and storage compatibility boundaries."""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import Engine, event

from invest_bot.config.settings import AppSettings
from invest_bot.dashboard.service import DashboardDataService
from invest_bot.dashboard.streamlit_state import DashboardFrameLoader
from invest_bot.db.contracts import DatasetFrameRecord
from invest_bot.db.frame_storage import DbFrameStorage
from invest_bot.db.repositories import frame_to_json
from invest_bot.market.storage import CsvStorage
from tests.helpers import init_test_db


@pytest.fixture(autouse=True)
def deny_implicit_runtime_settings(monkeypatch):
    def denied(*_args, **_kwargs):
        pytest.fail("independent G01b must not read runtime configuration")
    monkeypatch.setattr(AppSettings, "from_file", denied)


@pytest.fixture
def storage(tmp_path):
    url = f"sqlite:///{tmp_path / 'independent-g01b.sqlite'}"
    init_test_db(url)
    store = DbFrameStorage(url)
    yield store
    store.repository.session_factory.kw["bind"].dispose()


def assert_saved_unchanged(storage, frame, expected, filename="005930_numeric.csv"):
    before = frame.copy(deep=True)
    attrs_before = deepcopy(frame.attrs)
    payload_before = frame_to_json(frame)
    storage.save("daily_prices", filename, frame)
    record = storage.repository.load("daily_prices", filename)
    assert record is not None
    assert record.as_of_date == expected
    assert record.row_count == len(frame)
    assert record.frame_json == payload_before
    pd.testing.assert_frame_equal(frame, before)
    assert frame.attrs == attrs_before
    assert storage.latest_filename("daily_prices", "005930") == filename
    assert storage.repository.list_latest(("daily_prices",))[0].filename == filename
    return record


@pytest.mark.parametrize("values", [
    pd.Series([20261002, 20261001], dtype="int64"),
    pd.Series([20261002., 20261001.], dtype="float64"),
    pd.Series(["20261002", "20261001"], dtype=object),
    pd.Series(["20261002.0", "20261001.00"], dtype=object),
    pd.Series([20261002, None], dtype="Int64"),
    pd.Series([20261002., None], dtype="Float64"),
    pd.Series([np.uint64(20261002), np.int32(20261001)], dtype=object),
    pd.Series([np.float64(20261002.), np.float32(20261002.)], dtype=object),
])
def test_actual_sqlite_representations_match_calendar_metadata_and_payload(storage, monkeypatch, values):
    frame = pd.DataFrame({"stck_bsop_date": values, "quantity": [0, -3]})
    frame.attrs = {"immutable": {"values": ["calendar", 0]}}
    assert_saved_unchanged(storage, frame, date(2026, 10, 2))
    # Input frame dtype is immutable, but the pre-existing table JSON decoder
    # normalizes object-wrapped numpy numbers. Compare the real old transport
    # rather than assigning G01b a new lossless-decoder requirement.
    with monkeypatch.context() as baseline:
        baseline.setattr(storage, "_resolve_as_of_date", legacy_as_of_date)
        storage.save("daily_prices", "005930_baseline_transport.csv", frame)
    pd.testing.assert_frame_equal(storage.load("daily_prices", "005930_numeric.csv"),
                                  storage.load("daily_prices", "005930_baseline_transport.csv"))


@pytest.mark.parametrize("scenario,expected", [
    ("first-valid-column", date(2026, 10, 2)),
    ("trade-fallback", date(2026, 10, 5)),
    ("kis-fallback", date(2026, 10, 7)),
    ("local-days", date(2026, 10, 3)),
])
def test_mixed_types_column_fallback_and_local_day_preserve_index_dtype_attrs(storage, scenario, expected):
    frame = pd.DataFrame({
        "date": pd.Series([None, "invalid", 20261002], dtype=object),
        "trade_date": pd.Series(["20261005.0", "bad", None], dtype=object),
        "stck_bsop_date": pd.Series([20261007., 20261001., None], dtype=object),
        "quantity": [0., -1., 2.],
    })
    if scenario in {"trade-fallback", "kis-fallback"}:
        frame["date"] = pd.Series([pd.NA, np.bool_(True), "bad"], dtype=object)
    if scenario == "kis-fallback":
        frame["trade_date"] = pd.Series([0, float("inf"), "20260230"], dtype=object)
    if scenario == "local-days":
        frame["date"] = pd.Series([np.datetime64("2026-10-01"), pd.Timestamp("2026-10-03 00:30+14:00"),
                                    "2026-10-02 23:30-12:00"], dtype=object)
    frame.index = pd.MultiIndex.from_tuples([("same", 2), ("other", 9), ("same", 2)], names=["label", "position"])
    frame.attrs = {"nested": {"do_not_change": [1, 0]}}
    assert_saved_unchanged(storage, frame, expected)


@pytest.mark.parametrize("invalid", [0, "0", np.bool_(False), np.bool_(True), np.inf, -np.inf, "2026102", "20261002.25"])
def test_invalid_numeric_date_does_not_become_epoch_or_change_actual_zero_payload(storage, invalid):
    frame = pd.DataFrame({"date": pd.Series([invalid, pd.NA], dtype=object), "quantity": [0, -1]})
    record = assert_saved_unchanged(storage, frame, None)
    assert '"quantity":0' in record.frame_json
    assert storage.load("daily_prices", "005930_numeric.csv")["quantity"].tolist() == [0, -1]


@pytest.mark.parametrize("representation", ["integer", "float", "string", "float-string"])
def test_csv_roundtrip_then_sqlite_uses_same_local_day(storage, tmp_path, representation):
    values = {"integer": [20261002, 20261001], "float": [20261002., 20261001.],
              "string": ["20261002", "20261001"], "float-string": ["20261002.0", "20261001.0"]}[representation]
    csv = CsvStorage(tmp_path / "synthetic-csv")
    csv.save("daily_prices", "005930_source.csv", pd.DataFrame({"stck_bsop_date": values, "quantity": [0, -1]}))
    loaded = csv.load("daily_prices", "005930_source.csv")
    assert_saved_unchanged(storage, loaded, date(2026, 10, 2))


def legacy_as_of_date(frame):
    """Exact method body from main 1e73d60, whole source SHA256 83910b37... .

    Baseline blob was read and hashed in QA-baseline-frame-storage.log, not
    inferred from the proposed parser. This reference does no file/DB access.
    """
    if frame.empty:
        return None
    for column in ("date", "trade_date", "stck_bsop_date"):
        if column not in frame.columns:
            continue
        parsed = pd.to_datetime(frame[column], errors="coerce")
        latest = parsed.max()
        if pd.isna(latest):
            continue
        return latest.date()
    return None


@pytest.mark.parametrize("bad_cell", [
    pytest.param([], id="empty-list"),
    pytest.param(["bad", "worse"], id="multi-list"),
    pytest.param(np.array([], dtype=object), id="empty-array"),
    pytest.param(np.array(["bad", "worse"]), id="multi-array"),
    pytest.param({"bad": "date"}, id="dict"),
    pytest.param(("bad", "worse"), id="tuple"),
    pytest.param(np.array([None]), id="single-null-array"),
])
@pytest.mark.parametrize("fallback", [False, True], ids=["valid-row-same-column", "next-column-fallback"])
def test_legacy_serializable_container_noise_does_not_abort_actual_sqlite_save(storage, monkeypatch, bad_cell, fallback):
    frame = pd.DataFrame({"date": pd.Series([bad_cell, None if fallback else "2026-10-02"], dtype=object),
                          "trade_date": ["2026-10-04", "2026-10-03"], "quantity": [0, -1]})
    expected = date(2026, 10, 4) if fallback else date(2026, 10, 2)
    assert legacy_as_of_date(frame) == expected
    before = frame.copy(deep=True)
    payload = frame_to_json(frame)  # actual supported serializer, no coercion stub
    with monkeypatch.context() as baseline:
        baseline.setattr(storage, "_resolve_as_of_date", legacy_as_of_date)
        storage.save("market_reports", "005930_baseline.csv", frame)
    baseline_record = storage.repository.load("market_reports", "005930_baseline.csv")
    assert baseline_record.as_of_date == expected
    assert baseline_record.frame_json == payload
    baseline_loaded = storage.load("market_reports", "005930_baseline.csv")
    assert baseline_loaded["quantity"].tolist() == [0, -1]
    assert len(baseline_loaded) == 2
    # The proposed implementation must retain baseline's skip/coerce behavior.
    storage.save("market_reports", "005930_candidate.csv", frame)
    candidate = storage.repository.load("market_reports", "005930_candidate.csv")
    assert candidate.as_of_date == expected
    assert candidate.frame_json == payload
    pd.testing.assert_frame_equal(frame, before)


def test_actual_repository_retains_legacy_null_priority_and_created_id_ties(storage):
    frame = pd.DataFrame({"stck_bsop_date": [20261002], "quantity": [0]})
    storage.save("market_reports", "005930_numeric.csv", frame)
    numeric = storage.repository.load("market_reports", "005930_numeric.csv")
    assert numeric.as_of_date == date(2026, 10, 2)
    tied = datetime(2099, 1, 1, tzinfo=UTC)
    storage.repository.save(DatasetFrameRecord("market_reports", "005930_legacy_null.csv", frame_to_json(pd.DataFrame()), 0,
                                               datetime(2100, 1, 1, tzinfo=UTC), "005930", None))
    for name in ("005930_tie_first.csv", "005930_tie_winner.csv"):
        storage.repository.save(DatasetFrameRecord("market_reports", name, numeric.frame_json, 1, tied, "005930", numeric.as_of_date))
    for name in ("000660_null_first.csv", "000660_null_winner.csv"):
        storage.repository.save(DatasetFrameRecord("market_reports", name, numeric.frame_json, 1, tied, "000660", None))
    assert storage.latest_filename("market_reports", "005930") == "005930_tie_winner.csv"
    assert storage.repository.latest_for_symbol("market_reports", "660").filename == "000660_null_winner.csv"
    latest = {record.symbol: record for record in storage.repository.list_latest(("market_reports",))}
    assert latest["005930"].filename == "005930_tie_winner.csv"
    assert latest["000660"].filename == "000660_null_winner.csv"
    ordered = storage.repository.list_for_dataset("market_reports")
    assert ordered[0].filename == "005930_tie_winner.csv"
    assert ordered[1].filename == "005930_tie_first.csv"
    # New metadata extraction did not rewrite pre-existing NULL snapshots.
    assert storage.repository.load("market_reports", "005930_legacy_null.csv").as_of_date is None


def test_numeric_metadata_snapshot_selection_then_actual_consumers_add_no_select(storage, monkeypatch):
    storage.save("daily_prices", "005930_prices.csv", pd.DataFrame({
        "stck_bsop_date": [20261001, 20261002], "stck_oprc": [10, 11], "stck_hgpr": [12, 13],
        "stck_lwpr": [9, 10], "stck_clpr": [11, 12], "acml_vol": [100, 200]}))
    storage.save("investor_daily_summary", "005930_summary.csv", pd.DataFrame({"stck_bsop_date": [20261001, 20261002], "foreign_net": [0, -3]}))
    storage.repository.save(DatasetFrameRecord("investor_daily_summary", "005930_legacy_empty.csv", frame_to_json(pd.DataFrame()), 0,
                                               datetime(2100, 1, 1, tzinfo=UTC), "005930", None))
    service = DashboardDataService(dataset_storage=storage)
    monkeypatch.setattr(service, "_load_symbol_name_map", lambda: {})
    selects = []
    def observe(conn, _cursor, statement, *_args):
        if str(conn.engine.url) == storage.database_url and statement.lstrip().upper().startswith("SELECT"):
            selects.append(statement)
    event.listen(Engine, "before_cursor_execute", observe)
    try:
        snapshot = service.build_snapshot()
        assert len(selects) == 1  # only name provider is stubbed, real batched SELECT
        summary = next(record for record in snapshot.latest_records if record.dataset == "investor_daily_summary")
        assert summary.filename == "005930_summary.csv" and summary.as_of_date == date(2026, 10, 2)
        selects.clear()
        loader = DashboardFrameLoader(service, snapshot.latest_records)
        chart = loader.load_professional("005930")
        assert chart["foreign_net"].tolist() == [0, -3]
        assert chart["close"].tolist() == [11, 12]
        loader.load_professional("005930")
        for preview in snapshot.raw_previews:
            loader.read_preview(preview)
        assert selects == []
    finally:
        event.remove(Engine, "before_cursor_execute", observe)
