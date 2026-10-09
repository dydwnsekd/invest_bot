from __future__ import annotations

import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

from invest_bot.db.engine import build_session_factory, ensure_schema
from invest_bot.db.repositories import SqlAlchemyDatasetFrameRepository
from tests.dataset_frame_ordering_fixture import (
    assert_dataset_frame_ordering,
    seed_dataset_frame_ordering,
)


pytestmark = pytest.mark.postgresql


@pytest.fixture
def isolated_postgresql_repository() -> Iterator[tuple[SqlAlchemyDatasetFrameRepository, Engine]]:
    database_url = make_url(os.environ["QA_POSTGRESQL_URL"])
    assert database_url.get_backend_name() == "postgresql"
    assert database_url.host in {"127.0.0.1", "localhost", "postgres"}
    assert database_url.database is not None and database_url.database.endswith("_test")

    engine = create_engine(database_url, connect_args={"connect_timeout": 5}, future=True)
    schema_name = f"qa01_ordering_{uuid4().hex}"
    try:
        with engine.begin() as connection:
            connection.execute(CreateSchema(schema_name))
        try:
            # Keep every mapped table and foreign key out of public and other QA schemas.
            isolated_engine = engine.execution_options(schema_translate_map={None: schema_name})
            ensure_schema(isolated_engine)
            repository = SqlAlchemyDatasetFrameRepository(build_session_factory(isolated_engine))
            yield repository, isolated_engine
        finally:
            with engine.begin() as connection:
                connection.execute(DropSchema(schema_name, cascade=True))
    finally:
        engine.dispose()


def test_postgresql_dataset_frame_queries_preserve_null_fallback_and_tie_breaking(
    isolated_postgresql_repository: tuple[SqlAlchemyDatasetFrameRepository, Engine],
) -> None:
    repository, engine = isolated_postgresql_repository
    seed_dataset_frame_ordering(repository)

    assert_dataset_frame_ordering(repository)

    selects: list[str] = []

    def observe(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            selects.append(statement)

    event.listen(engine, "before_cursor_execute", observe)
    try:
        repository.list_latest(("market_reports", "daily_prices"))
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    assert len(selects) == 1
