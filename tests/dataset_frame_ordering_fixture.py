from __future__ import annotations

from datetime import UTC, date, datetime

from invest_bot.db.contracts import DatasetFrameRecord
from invest_bot.db.repositories import SqlAlchemyDatasetFrameRepository


def seed_dataset_frame_ordering(repository: SqlAlchemyDatasetFrameRepository) -> None:
    """Seed the same ordering cases in an isolated SQLite or PostgreSQL DB."""
    rows = [
        ("market_reports", "dated_old.csv", "005930", date(2026, 9, 20), "2026-10-08T00:00:00"),
        ("market_reports", "dated_early.csv", "005930", date(2026, 9, 21), "2026-09-21T00:00:00"),
        ("market_reports", "dated_tie_first.csv", "005930", date(2026, 9, 21), "2026-09-22T00:00:00"),
        ("market_reports", "dated_winner.csv", "005930", date(2026, 9, 21), "2026-09-22T00:00:00"),
        ("market_reports", "null_newer.csv", "005930", None, "2026-10-09T00:00:00"),
        ("market_reports", "null_only_old.csv", "000660", None, "2026-10-04T00:00:00"),
        ("market_reports", "null_only_tie_first.csv", "000660", None, "2026-10-05T00:00:00"),
        ("market_reports", "null_only_winner.csv", "000660", None, "2026-10-05T00:00:00"),
        ("market_reports", "no_symbol_a.csv", "", None, "2026-10-03T00:00:00"),
        ("market_reports", "no_symbol_b.csv", "", None, "2026-10-02T00:00:00"),
        ("daily_prices", "daily_old.csv", "005930", date(2026, 9, 19), "2026-10-10T00:00:00"),
        ("daily_prices", "daily_winner.csv", "005930", date(2026, 9, 20), "2026-09-20T00:00:00"),
        ("stock_info", "excluded.csv", "005380", date(2026, 9, 21), "2026-09-21T00:00:00"),
    ]
    for dataset, filename, symbol, as_of_date, created_at in rows:
        repository.save(DatasetFrameRecord(
            dataset=dataset,
            filename=filename,
            symbol=symbol,
            as_of_date=as_of_date,
            created_at=datetime.fromisoformat(created_at).replace(tzinfo=UTC),
            frame_json=f'{{"filename":"{filename}"}}',
            row_count=0 if filename == "null_newer.csv" else 1,
        ))


def assert_dataset_frame_ordering(repository: SqlAlchemyDatasetFrameRepository) -> None:
    """Verify all three queries against explicit, DB-independent expectations."""
    dated = repository.latest_for_symbol("market_reports", "5930")
    assert dated is not None and dated.filename == "dated_winner.csv"
    assert dated.as_of_date == date(2026, 9, 21)
    assert dated.row_count == 1
    assert dated.frame_json == '{"filename":"dated_winner.csv"}'
    fallback = repository.latest_for_symbol("market_reports", "660")
    assert fallback is not None and fallback.filename == "null_only_winner.csv"
    assert fallback.as_of_date is None
    assert repository.latest_for_symbol("market_reports", "999999") is None

    market = repository.list_for_dataset("market_reports")
    assert [record.filename for record in market] == [
        "dated_winner.csv", "dated_tie_first.csv", "dated_early.csv", "dated_old.csv",
        "null_newer.csv", "null_only_winner.csv", "null_only_tie_first.csv", "null_only_old.csv",
        "no_symbol_a.csv", "no_symbol_b.csv",
    ]
    assert [record.filename for record in repository.list_for_dataset("daily_prices")] == [
        "daily_winner.csv", "daily_old.csv",
    ]
    assert repository.list_for_dataset("missing") == []

    expected_latest = [
        ("market_reports", "dated_winner.csv"),
        ("market_reports", "null_only_winner.csv"),
        ("market_reports", "no_symbol_a.csv"),
        ("market_reports", "no_symbol_b.csv"),
        ("daily_prices", "daily_winner.csv"),
    ]
    latest = repository.list_latest(("market_reports", "daily_prices"))
    assert [(record.dataset, record.filename) for record in latest] == expected_latest
    assert [record.symbol for record in latest[2:4]] == ["", ""]
    assert repository.list_latest(()) == []
    repeated = repository.list_latest(("daily_prices", "market_reports", "daily_prices"))
    assert [(record.dataset, record.filename) for record in repeated] == [
        expected_latest[-1], *expected_latest[:-1], expected_latest[-1],
    ]
