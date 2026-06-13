# invest_bot DB-first schema

## Purpose

이 문서는 현재 `invest_bot`의 DB 중심 저장 구조를 설명한다. 애플리케이션과 migration은 `config/app.yaml`의 DB 설정을 기준으로 동작하며, 로컬 Docker Compose는 기본 PostgreSQL endpoint와 data mount를 제공한다.

## Tables

### `symbols`

- 종목 마스터 테이블
- PK: `symbol`
- 주요 컬럼: `symbol_name`, `market`, `is_active`, `created_at`, `updated_at`

### `daily_prices`

- 일봉 가격 정규화 테이블
- FK: `symbol -> symbols.symbol`
- Unique: `(symbol, trade_date)`
- 주요 컬럼: `open_price`, `high_price`, `low_price`, `close_price`, `volume`, `turnover`, `source_filename`, `collected_at`

### `stock_info_snapshots`

- 종목 기본정보 스냅샷 테이블
- FK: `symbol -> symbols.symbol`
- Unique: `(symbol, captured_at)`
- 주요 컬럼: `product_name`, `market_code`, `raw_payload`, `source_filename`

### `investor_daily`

- 투자자 수급 정규화 테이블
- FK: `symbol -> symbols.symbol`
- Unique: `(symbol, trade_date)`
- 주요 컬럼: `foreign_net_qty`, `institutional_net_qty`, `personal_net_qty`, `raw_payload`, `source_filename`, `collected_at`

### `dataset_frames`

- 분석/리포트/백테스트 및 raw snapshot을 DataFrame 단위로 저장하는 범용 스냅샷 테이블
- FK: `symbol -> symbols.symbol` (`NULL` 가능)
- Unique: `(dataset, filename)`
- 주요 컬럼: `dataset`, `filename`, `as_of_date`, `row_count`, `frame_json`, `created_at`, `updated_at`
- 예시 dataset:
  - `daily_prices`
  - `daily_prices_summary`
  - `stock_info`
  - `investor_daily`
  - `investor_daily_summary`
  - `daily_prices_indicators`
  - `golden_cross_signals`
  - `market_reports`
  - `backtest_trades`
  - `backtest_summaries`

## Read/write boundary

- 수집 단계:
  - raw DataFrame snapshot은 기본적으로 `dataset_frames`에 저장
  - 정규화 가능한 핵심 수집 데이터는 `enable_db_write=true`일 때만 `daily_prices`, `stock_info_snapshots`, `investor_daily`에도 함께 저장
- 분석 단계:
  - 지표, 시그널, 리포트, 백테스트 결과는 `dataset_frames`에 저장
- 대시보드 단계:
  - 최신 preview와 보고서는 `dataset_frames`를 기준으로 조회
  - 종목명 매핑은 최신 `stock_info` snapshot을 우선 사용하되, DB 연결이나 snapshot 조회가 실패하면 종목 마스터/로컬 파일로 폴백한다

## Runtime rules

- `DbFrameStorage`와 `SqlAlchemyMarketDataWriter`는 런타임에 스키마를 생성하지 않는다.
- 스키마 생성과 업그레이드는 [scripts/init_db.py](/Users/yongjun/PycharmProjects/invest_bot/scripts/init_db.py) 및 Alembic migration이 전담한다.
- 대시보드 helper는 새 `DashboardDataService()`를 내부에서 만들지 않고, 호출자가 넘긴 서비스/스토리지를 그대로 사용해야 한다.

## Endpoint configuration

DB endpoint는 `config/app.yaml`에서 관리한다.

- `database_url`가 비어 있지 않으면 그 값을 그대로 사용
- `database_url`가 비어 있으면 `db_host`, `db_port`, `db_name`, `db_user`, `db_password`를 조합
- Docker Compose를 쓸 때도 앱 컨테이너는 동일한 `config/app.yaml`을 읽는다

## Initialization

- DB 초기화 스크립트: [scripts/init_db.py](/Users/yongjun/PycharmProjects/invest_bot/scripts/init_db.py)
- 내부 동작:
  - Alembic migration 실행
  - 기존 bootstrap schema가 있으면 stamp 후 head까지 upgrade
  - 이후 collector, analyzer, dashboard는 이미 준비된 스키마에만 연결한다

## Persistence

로컬 Docker 환경에서는 PostgreSQL data dir를 host path로 mount 한다.

- 기본 host path: `./.docker/postgres`
- Docker Compose override: `INVEST_BOT_DB_DATA_DIR`

따라서 `docker compose down` 후 다시 `docker compose up` 하더라도 volume path를 유지하면 이전 수집/분석 데이터가 남는다.

## Relationship image

- SVG: [db_schema.svg](/Users/yongjun/PycharmProjects/invest_bot/docs/architecture/db_schema.svg)
