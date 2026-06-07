# DB Write Path Change Report - 2026-06-07

이 문서는 commit 전에 `invest_bot`의 DB write path 구현 변경사항과 검증 결과를 정리한 markdown-first 보고서다.

## 1. Collector dual-write path 추가

변경사항:

- `MarketDataCollector`가 기존 CSV 저장을 유지하면서 선택적으로 DB write를 함께 수행할 수 있게 했다.
- `INVEST_BOT_ENABLE_DB_WRITE`가 켜진 경우 기본 SQLAlchemy writer를 자동 구성하도록 연결했다.

대상 파일:

- `src/invest_bot/market/collector.py`
- `src/invest_bot/market/repositories.py`
- `src/invest_bot/config/settings.py`

핵심 내용:

- 기존 `DatasetStorage.save(...) -> SavedDataset` 경계는 유지했다.
- 새 `MarketDataWriter` protocol을 통해 DB write를 collector save 단계에 붙였다.
- CSV 산출물(`daily_prices*`, `stock_info`, `investor_daily*`)은 그대로 유지해 read-path migration 전환 전 호환성을 보존했다.

## 2. SQLAlchemy-backed DB write repository 구현

변경사항:

- symbols, daily_prices, stock_info_snapshots, investor_daily write path를 위한 SQLAlchemy repository/engine/writer를 추가했다.
- 동일 symbol/trade_date 재수집 시 row를 중복 생성하지 않고 update 하도록 구현했다.

대상 파일:

- `src/invest_bot/db/engine.py`
- `src/invest_bot/db/repositories.py`
- `src/invest_bot/db/write_path.py`
- `src/invest_bot/db/contracts.py`
- `src/invest_bot/db/models.py`
- `src/invest_bot/db/__init__.py`

핵심 내용:

- `latest_trade_date()` contract를 `DailyPriceRepository`, `InvestorDailyRepository`에 추가했다.
- `StockInfoSnapshotRecord` / repository contract를 추가했다.
- `SqlAlchemyMarketDataWriter`가 raw KIS-style DataFrame을 DB record로 정규화한다.
- symbol 코드는 6자리 zero-padding을 유지한다.

## 3. Schema / migration / compose contract 정합화

변경사항:

- investor_daily / stock_info snapshot schema를 현재 migration 문서와 write-path 설계에 맞게 정렬했다.
- DB bootstrap readiness report의 ERD 경로를 실제 문서 위치와 맞췄다.
- compose migrate/service dependency contract를 테스트 기대값과 맞췄다.

대상 파일:

- `migrations/versions/20260606_000001_create_initial_schema.py`
- `src/invest_bot/db/bootstrap.py`
- `docker-compose.yml`

핵심 내용:

- `migrate`는 `alembic upgrade head` 실행으로 맞췄다.
- `scheduler`, `web`, `collector`는 `migrate` 성공 이후 시작되도록 compose 의존 관계를 명시했다.
- compose `env_file`은 `.env` 기준으로 정렬했다.

## 4. 검증 추가

변경사항:

- DB dual-write와 duplicate protection regression test를 추가했다.
- settings의 `DATABASE_URL` 우선 규칙과 DB write enable flag를 검증한다.

대상 파일:

- `tests/test_db_write_path.py`
- `tests/test_settings.py`

핵심 내용:

- CSV side artifact가 유지되는지와 DB row가 실제 생성되는지를 함께 검증한다.
- 동일 일자 재수집 시 중복 대신 update 되는지를 검증한다.
- DB contract export surface(`Base`, `build_database_url`) regression도 유지했다.

## Verification

- `python3 -m py_compile src/invest_bot/config/settings.py src/invest_bot/db/__init__.py src/invest_bot/db/bootstrap.py src/invest_bot/db/contracts.py src/invest_bot/db/engine.py src/invest_bot/db/models.py src/invest_bot/db/repositories.py src/invest_bot/db/write_path.py src/invest_bot/market/collector.py src/invest_bot/market/repositories.py tests/test_settings.py tests/test_db_write_path.py tests/test_domestic_stock_collector.py tests/test_db_bootstrap.py tests/test_db_migration_artifacts.py tests/test_db_migration_scaffold.py` → PASS
- `.venv/bin/python -m pytest tests/test_settings.py tests/test_db_write_path.py tests/test_domestic_stock_collector.py tests/test_db_bootstrap.py tests/test_db_migration_scaffold.py tests/test_db_migration_artifacts.py` → PASS (`19 passed`)
- `.venv/bin/python -m pytest` → PASS (`46 passed`)

## Remaining risks

- read path는 여전히 CSV 기반이므로 DB-only runtime은 아직 완성되지 않았다.
- compose/Alembic 실행은 로컬 unit test 수준으로만 검증했고, 실제 `docker compose up db migrate web` smoke는 이번 worker 범위에서 수행하지 않았다.
