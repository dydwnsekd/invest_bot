from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import Engine, event

from invest_bot.db.contracts import DatasetFrameRecord
from invest_bot.db.frame_storage import DbFrameStorage
from tests.helpers import init_test_db


def test_list_latest_uses_one_query_and_preserves_dataset_and_record_order(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'latest_batch.db'}"
    init_test_db(database_url)
    repository = DbFrameStorage(database_url).repository

    def save(dataset, filename, symbol, as_of, created):
        repository.save(DatasetFrameRecord(
            dataset=dataset, filename=filename, symbol=symbol, as_of_date=as_of,
            created_at=datetime.fromisoformat(created).replace(tzinfo=UTC),
            frame_json=f'{{"filename":"{filename}"}}', row_count=1,
        ))

    save("market_reports", "older_date.csv", "005930", date(2026, 9, 20), "2026-09-24T00:00:00")
    save("market_reports", "older_created.csv", "005930", date(2026, 9, 21), "2026-09-21T00:00:00")
    save("market_reports", "older_id.csv", "005930", date(2026, 9, 21), "2026-09-22T00:00:00")
    save("market_reports", "winner.csv", "005930", date(2026, 9, 21), "2026-09-22T00:00:00")
    save("market_reports", "null_symbol_a.csv", "", None, "2026-09-23T00:00:00")
    save("market_reports", "null_symbol_b.csv", "", None, "2026-09-22T00:00:00")
    save("daily_prices", "daily_old.csv", "000660", date(2026, 9, 19), "2026-09-24T00:00:00")
    save("daily_prices", "daily_new.csv", "000660", date(2026, 9, 20), "2026-09-20T00:00:00")
    save("stock_info", "excluded.csv", "005380", date(2026, 9, 21), "2026-09-21T00:00:00")

    selects = []

    def observe(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            selects.append(statement)

    event.listen(Engine, "before_cursor_execute", observe)
    try:
        records = repository.list_latest(("market_reports", "daily_prices"))
    finally:
        event.remove(Engine, "before_cursor_execute", observe)
    assert len(selects) == 1
    assert [(r.dataset, r.filename) for r in records] == [
        ("market_reports", "winner.csv"),
        ("market_reports", "null_symbol_a.csv"),
        ("market_reports", "null_symbol_b.csv"),
        ("daily_prices", "daily_new.csv"),
    ]
    assert records[0].symbol == "005930"
    assert records[0].as_of_date == date(2026, 9, 21)
    assert records[0].frame_json == '{"filename":"winner.csv"}'

    assert repository.list_latest(()) == []
    duplicated = repository.list_latest(("daily_prices", "market_reports", "daily_prices"))
    assert [r.dataset for r in duplicated] == [
        "daily_prices", "market_reports", "market_reports", "market_reports", "daily_prices",
    ]
