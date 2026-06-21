# invest_bot DB schema and ownership

## Purpose

이 문서는 현재 `invest_bot`의 DB 스키마와 **테이블 책임**, **사용자 액션에 의한 변경 허용 여부**, **컬럼 의미**, **기능별 source of truth**를 정리하는 canonical 문서다. 구현/리팩터링/마이그레이션 판단은 이 문서를 우선 기준으로 삼는다.

## Global rules

- 사용자 Web 조회(검색, 선택, 단건 확인, 미리보기)는 **read-only**다.
- canonical 종목 reference는 `symbols`다.
- `symbols`는 **종목 마스터 동기화**에서만 갱신한다.
- 수집/분석/리포트 실행은 fact/artifact 테이블만 갱신할 수 있다.
- raw API 응답이나 fallback 응답은 canonical 종목명 source가 아니다.

## Table classes

| Class | Tables | Meaning |
| --- | --- | --- |
| Canonical reference | `symbols` | 사용자 조회와 표시의 정답 데이터 |
| Collected facts | `daily_prices`, `investor_daily` | 수집된 정규화 사실 데이터 |
| Snapshots / artifacts | `dataset_frames` | raw snapshot 및 분석/리포트 산출물 저장소 |
| Deprecated candidate | `stock_info_snapshots` | 현재 제품 기준 직접 가치가 낮고 제거 후보인 테이블 |

## Tables

### `symbols`

**Role**
- 종목코드 ↔ 종목명 ↔ 시장의 canonical reference table
- 사용자 종목 검색/선택/표시의 단일 source of truth
- 다른 도메인 테이블의 FK 기준점

**Can user actions mutate it?**
- **No**
- 사용자 조회, 화면 진입, 종목 검색, 미리보기, 리포트 열람으로 변경되면 안 된다.
- 종목 마스터 sync 또는 관리자성 reference refresh 작업에서만 변경된다.

**Columns**

| Column | Meaning |
| --- | --- |
| `symbol` | canonical 종목코드. PK. zero-padded code 사용 |
| `symbol_name` | canonical 종목명. UI 표시명/검색명 |
| `market` | 시장 구분(KOSPI/KOSDAQ 등) |
| `is_active` | 표시/사용 가능 여부 |
| `created_at` | row 최초 생성 시각 |
| `updated_at` | reference metadata 마지막 갱신 시각 |

**Source of truth / notes**
- 종목명 lookup은 항상 `symbols.symbol_name` 기준으로 해석한다.
- raw `stock_info` 응답이나 fallback 값으로 `symbol_name`를 덮어쓰면 안 된다.

### `daily_prices`

**Role**
- 종목별 일봉 가격의 정규화 fact table
- 지표 계산과 분석의 기본 입력 데이터

**Can user actions mutate it?**
- **Yes, but only execution actions**
- `데이터 수집`, `전체 파이프라인`, scheduler/collector batch는 갱신 가능
- 단순 조회/탐색으로는 변경되면 안 된다.

**Columns**

| Column | Meaning |
| --- | --- |
| `id` | surrogate PK |
| `symbol` | `symbols.symbol` FK |
| `trade_date` | 거래일 |
| `open_price` | 시가 |
| `high_price` | 고가 |
| `low_price` | 저가 |
| `close_price` | 종가 |
| `volume` | 거래량 |
| `turnover` | 거래대금/회전 관련 값 |
| `source_filename` | 원본 파일/스냅샷 추적용 메타 |
| `collected_at` | 실제 수집 시각 |

**Source of truth / notes**
- 가격 fact의 canonical store다.
- preview/UI가 `dataset_frames.daily_prices`를 보여주더라도 정규화 truth는 `daily_prices`다.

### `investor_daily`

**Role**
- 종목별 투자자 수급 정규화 fact table

**Can user actions mutate it?**
- **Yes, but only execution actions**
- 수집/배치 실행만 갱신 가능
- 단순 조회/탐색으로는 변경되면 안 된다.

**Columns**

| Column | Meaning |
| --- | --- |
| `id` | surrogate PK |
| `symbol` | `symbols.symbol` FK |
| `trade_date` | 기준 거래일 |
| `foreign_net_qty` | 외국인 순매수 수량 |
| `institutional_net_qty` | 기관 순매수 수량 |
| `personal_net_qty` | 개인 순매수 수량 |
| `raw_payload` | 정규화 전 원본 수급 payload |
| `source_filename` | 원본 파일/스냅샷 추적용 메타 |
| `collected_at` | 실제 수집 시각 |

**Source of truth / notes**
- 수급 fact의 canonical store다.

### `dataset_frames`

**Role**
- DataFrame 단위 snapshot/artifact 저장소
- CSV 기반 raw/processed 산출물을 DB로 유지하는 범용 테이블
- canonical reference나 canonical facts를 대체하지 않는다.

**Can user actions mutate it?**
- **Partial**
- 조회는 read-only
- 실행 액션은 dataset 종류에 따라 갱신 가능

**Columns**

| Column | Meaning |
| --- | --- |
| `id` | surrogate PK |
| `dataset` | dataset 종류 (`daily_prices`, `market_reports` 등) |
| `filename` | dataset 내부 고유 snapshot key |
| `symbol` | 관련 종목 (`symbols.symbol` FK, nullable) |
| `as_of_date` | 데이터 기준일 |
| `row_count` | frame row 수 |
| `frame_json` | 전체 DataFrame payload |
| `created_at` | snapshot 최초 저장 시각 |
| `updated_at` | 같은 key 재저장 시 갱신 시각 |

**Dataset-level policy**

| Dataset group | Examples | Mutation policy | Notes |
| --- | --- | --- | --- |
| Raw collection snapshots | `daily_prices`, `daily_prices_summary`, `investor_daily`, `investor_daily_summary` | 수집/배치 실행만 갱신 가능 | 사실 데이터의 snapshot일 뿐 canonical fact는 아님 |
| Derived artifacts | `daily_prices_indicators`, `golden_cross_signals`, `market_reports`, `backtest_trades`, `backtest_summaries` | 분석/리포트/백테스트 실행에서만 갱신 가능 | 실행 산출물 저장소 |
| Raw stock info snapshot | `stock_info` | **사용자 조회로는 갱신 금지** | canonical 종목명 source가 아님 |

**Source of truth / notes**
- `dataset_frames.stock_info`는 사용자 종목 검색/선택 source로 사용하면 안 된다.
- `dataset_frames`는 artifact store이며, reference table인 `symbols`와 역할을 분리한다.

### `stock_info_snapshots`

**Role**
- stock_info 원본 응답 이력 저장용으로 설계된 테이블
- 현재 제품 기능 기준 직접 사용처가 약하고 제거 후보로 본다.

**Can user actions mutate it?**
- **No**가 정책상 맞다.
- 사용자 조회/탐색과 연결되면 안 된다.

**Columns**

| Column | Meaning |
| --- | --- |
| `id` | surrogate PK |
| `symbol` | `symbols.symbol` FK |
| `captured_at` | 응답 캡처 시각 |
| `product_name` | 조회 당시 응답 종목명 |
| `market_code` | 조회 당시 응답 시장코드 |
| `raw_payload` | 원본 stock_info payload |
| `source_filename` | 연계 source 추적 메타 |

**Source of truth / notes**
- canonical 종목명 source가 아니다.
- 현재 정책 기준에서는 제거 대상 후보로 문서화한다.

## User action boundary

### Read-only user actions
- 종목 검색
- 종목 선택
- 화면 진입
- 미리보기/차트/리포트 열람
- 단건 종목 정보 확인

이때 변경되면 안 되는 테이블:
- `symbols`
- `daily_prices`
- `investor_daily`
- `dataset_frames`
- `stock_info_snapshots`

### Mutating execution actions
- 데이터 수집
- 전체 파이프라인 실행
- 지표 계산
- 신호 생성
- 리포트 생성
- 백테스트 실행

이때 변경 가능한 테이블:
- `daily_prices`
- `investor_daily`
- 관련 `dataset_frames` raw/processed dataset

이때도 변경되면 안 되는 테이블:
- `symbols`
- `stock_info_snapshots`
- 사용자 조회에서 생성된 `dataset_frames.stock_info`

## Source of truth by feature

| Feature | Source of truth |
| --- | --- |
| 종목 검색 / 종목 선택 / 표시명 | `symbols` |
| 가격 fact | `daily_prices` |
| 수급 fact | `investor_daily` |
| 지표 / 신호 / 리포트 / 백테스트 결과 | `dataset_frames` processed datasets |
| raw stock_info 응답 | canonical source 아님; 비저장 또는 분리된 raw snapshot 취급 |

## Runtime rules

- `DbFrameStorage`와 `SqlAlchemyMarketDataWriter`는 런타임에 스키마를 생성하지 않는다.
- 스키마 생성과 업그레이드는 [scripts/init_db.py](/Users/yongjun/PycharmProjects/invest_bot/scripts/init_db.py) 및 Alembic migration이 전담한다.
- 대시보드 helper는 새 `DashboardDataService()`를 내부에서 만들지 않고, 호출자가 넘긴 서비스/스토리지를 그대로 사용해야 한다.

## Endpoint configuration

DB endpoint는 `config/app.yaml`에서 관리한다.

- `database_url`가 비어 있지 않으면 그 값을 그대로 사용
- `database_url`가 비어 있으면 `db_host`, `db_port`, `db_name`, `db_user`, `db_password`를 조합
- Docker Compose를 쓸 때도 앱 컨테이너는 동일한 `config/app.yaml`을 읽는다
- `db_host_docker`가 비어 있지 않고 `INVEST_BOT_APP_ROLE`이 `migrate`, `scheduler`, `web`, `collector` 중 하나이면 컨테이너 내부에서는 `db_host_docker`를 우선 사용한다

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
