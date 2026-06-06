# DB Migration Plan: ERD, Docker Compose Draft, and Repository Interfaces

## 목적

현재 `invest_bot` 는 CSV 파일 기반으로 데이터를 저장합니다. 이 문서는 Postgres 기반 저장소로 옮기기 전에 필요한 설계 결정을 하나로 정리한 구현 준비 문서입니다.

범위:

- 현재 코드 기준 데이터 흐름 검토
- 1차 도입용 ERD 확정안
- `docker-compose.yml` 초안 검토 결과
- 저장소(Repository) 인터페이스 경계 제안
- 팀 구현 순서와 위험요인 정리

비범위:

- 실제 Alembic 마이그레이션 작성
- SQLAlchemy/DB 드라이버 도입
- CSV 저장 로직 제거

## 현재 상태 요약

현재 코드에서 확인되는 사실:

- 수집 원천은 `DomesticStockDataCollector` 와 `MarketDataCollector` 입니다.
- 영속화는 `CsvStorage` 가 담당합니다.
- 종목 마스터는 `StockMasterRepository` 가 CSV 파일로 관리합니다.
- 대시보드/분석/리포트는 저장된 CSV 파일을 다시 읽는 구조입니다.
- `docker-compose.yml` 에는 `db`, `migrate`, `scheduler`, `web`, `collector` 서비스 초안이 있습니다.
- 그러나 현재 저장소에는 Alembic 설정, DB 모델, SQLAlchemy 계층, Postgres 드라이버 의존성이 없습니다.

따라서 현재 `docker-compose.yml` 의 `migrate` 서비스는 설계 초안이며, 아직 실행 가능한 배포 단위는 아닙니다.

## 현재 코드에서 보이는 데이터 경계

### 수집 계층

- `MarketDataCollector.collect_daily_prices`
- `MarketDataCollector.collect_stock_info`
- `MarketDataCollector.collect_investor_daily`

### 저장 계층

- `CsvStorage.save`
- `StockMasterRepository.load_entries`
- `StockMasterRepository.write_entries`
- `StockMasterRepository.ensure_updated`

### 후처리 계층

- `DailyPriceAnalyzer`
- `GoldenCrossSignalGenerator`
- `MarketReportGenerator`
- `SymbolLookup`

이 구조를 기준으로 보면 1차 DB 마이그레이션은 **도메인 로직을 유지하고 저장 구현만 교체 가능한 형태**가 가장 안전합니다.

## 1차 ERD 확정안

1차 목표는 현재 CSV 산출물과 1:1 대응되는 핵심 테이블만 먼저 도입하는 것입니다.

```text
stocks
  id PK
  symbol UNIQUE
  symbol_name
  market
  created_at
  updated_at

stock_infos
  id PK
  stock_id FK -> stocks.id
  as_of_date NULL
  payload_json
  created_at

daily_price_batches
  id PK
  stock_id FK -> stocks.id
  source
  start_date
  end_date
  created_at
  UNIQUE(stock_id, start_date, end_date)

daily_prices
  id PK
  stock_id FK -> stocks.id
  trade_date
  open
  high
  low
  close
  volume
  turnover NULL
  batch_id FK -> daily_price_batches.id NULL
  created_at
  UNIQUE(stock_id, trade_date)

investor_daily_summaries
  id PK
  stock_id FK -> stocks.id
  trade_date
  foreign_net
  institutional_net
  personal_net
  payload_json
  created_at
  UNIQUE(stock_id, trade_date)

daily_price_indicators
  id PK
  stock_id FK -> stocks.id
  trade_date
  ma_5 NULL
  ma_20 NULL
  ma_60 NULL
  volume_ma_5 NULL
  rsi_14 NULL
  created_at
  UNIQUE(stock_id, trade_date)

golden_cross_signals
  id PK
  stock_id FK -> stocks.id
  trade_date
  signal
  signal_reason
  prev_ma_5 NULL
  prev_ma_20 NULL
  ma_5 NULL
  ma_20 NULL
  created_at
  UNIQUE(stock_id, trade_date)

market_reports
  id PK
  stock_id FK -> stocks.id
  trade_date
  trend_state
  rsi_state
  volume_state
  investor_flow
  final_opinion
  summary
  payload_json
  created_at
  UNIQUE(stock_id, trade_date)
```

## ERD 설계 원칙

- `stocks` 를 모든 시계열 데이터의 기준 엔터티로 사용합니다.
- 원본 응답 전체 보존이 필요할 수 있으므로 초기 단계에서는 일부 테이블에 `payload_json` 을 허용합니다.
- 지표/신호/리포트는 재생성 가능하지만, 대시보드 응답 속도와 실행 이력 추적을 위해 1차 저장 대상으로 유지합니다.
- 현재 CSV 파일명이 암시하는 범위를 `stock_id + trade_date` 또는 `stock_id + 기간` 유니크 제약으로 치환합니다.

## Repository 인터페이스 제안

현재 코드와 가장 잘 맞는 경계는 “저장 구현만 교체 가능” 한 포트 형태입니다.

### 1. 종목 기준 정보

```python
class StockRepository(Protocol):
    def upsert_stock(self, symbol: str, symbol_name: str, market: str | None = None) -> StockRecord: ...
    def get_by_symbol(self, symbol: str) -> StockRecord | None: ...
    def search_by_name(self, name: str) -> list[StockRecord]: ...
```

### 2. 종목 마스터/심볼 조회

```python
class StockMasterRepositoryPort(Protocol):
    def load_entries(self) -> list[dict[str, str]]: ...
    def ensure_updated(self, force: bool = False) -> object: ...
```

비고:

- 기존 `StockMasterRepository` 는 이 포트를 그대로 만족하도록 유지할 수 있습니다.
- 이후 DB 구현체와 CSV 구현체를 병행해도 `SymbolLookup` 수정 범위를 최소화할 수 있습니다.

### 3. 일봉 데이터

```python
class DailyPriceRepository(Protocol):
    def upsert_prices(self, symbol: str, rows: list[dict[str, object]]) -> int: ...
    def list_prices(self, symbol: str, start_date: date | None = None, end_date: date | None = None) -> list[dict[str, object]]: ...
    def latest_price_date(self, symbol: str) -> date | None: ...
```

### 4. 투자자 수급 요약

```python
class InvestorFlowRepository(Protocol):
    def upsert_daily_summary(self, symbol: str, trade_date: date, payload: dict[str, object]) -> None: ...
    def get_daily_summary(self, symbol: str, trade_date: date) -> dict[str, object] | None: ...
```

### 5. 분석/신호/리포트 산출물

```python
class IndicatorRepository(Protocol):
    def replace_for_symbol(self, symbol: str, rows: list[dict[str, object]]) -> int: ...
    def list_for_symbol(self, symbol: str) -> list[dict[str, object]]: ...

class SignalRepository(Protocol):
    def replace_for_symbol(self, symbol: str, rows: list[dict[str, object]]) -> int: ...
    def list_for_symbol(self, symbol: str) -> list[dict[str, object]]: ...

class MarketReportRepository(Protocol):
    def upsert_report(self, symbol: str, trade_date: date, payload: dict[str, object]) -> None: ...
    def get_latest_report(self, symbol: str) -> dict[str, object] | None: ...
```

## 권장 구현 방식

### 단계 1. 포트 추출

- `CsvStorage` 직접 호출부를 바로 DB로 바꾸지 말고, 서비스 계층이 의존할 최소 포트를 먼저 정의합니다.
- 특히 아래 두 군데를 먼저 경계화하는 것이 안전합니다.
  - `MarketDataCollector` 저장 단계
  - `SymbolLookup` 의 종목명 조회 단계

### 단계 2. CSV 어댑터 유지

- 새 포트를 만족하는 CSV 어댑터를 먼저 붙여서 동작을 고정합니다.
- 이 단계에서는 기능 변화가 없어야 합니다.

### 단계 3. DB 어댑터 추가

- SQLAlchemy 모델/세션/리포지토리 구현체를 추가합니다.
- CSV 어댑터와 같은 테스트 계약을 재사용합니다.

### 단계 4. 마이그레이션/부트스트랩

- Alembic 초기 리비전 생성
- `stocks`, `daily_prices`, `investor_daily_summaries` 부터 생성
- 필요 시 CSV -> DB 백필 스크립트 추가

### 단계 5. 런타임 전환

- 수집기는 DB 저장을 기본값으로 전환
- 분석/신호/리포트 로더도 DB 우선 조회로 전환
- CSV 저장은 임시 fallback 또는 export 기능으로 축소

## docker-compose 초안 검토

현재 `docker-compose.yml` 의 장점:

- Postgres 서비스 정의가 단순하고 충분히 명확합니다.
- `migrate` 완료 후 `scheduler`, `web`, `collector` 가 시작되도록 의존성이 잘 분리돼 있습니다.
- 앱 역할(`INVEST_BOT_APP_ROLE`) 을 환경변수로 구분한 방향은 유지 가치가 있습니다.

현재 보완이 필요한 점:

1. `alembic` 실행 기반이 아직 저장소에 없습니다.
2. DB 드라이버/ORM 의존성이 `requirements.txt` 에 없습니다.
3. 애플리케이션 설정(`AppSettings`) 이 DB 접속 정보를 아직 읽지 않습니다.
4. `scheduler`, `web`, `collector` 는 여전히 CSV 기반 코드 경로를 실행합니다.
5. `.env` 의 DB 변수와 실제 런타임 설정 객체가 연결돼 있지 않습니다.

결론:

- `docker-compose.yml` 은 **버릴 초안은 아니지만, 구현 선행조건이 충족되기 전까지는 문서상 draft 상태**로 두는 것이 맞습니다.

## 팀 구현 순서

1. DB 설정 모델 추가 (`AppSettings` 확장)
2. Repository Protocol 정의
3. CSV 어댑터를 Protocol 기반으로 정렬
4. SQLAlchemy + DB 드라이버 + Alembic 도입
5. 초기 테이블 마이그레이션 생성
6. `stocks`, `daily_prices`, `investor_daily_summaries` 저장 경로 전환
7. `SymbolLookup` 를 DB/CSV 혼합 조회로 전환
8. 분석/신호/리포트 저장소 전환
9. 선택적으로 CSV 백필/내보내기 스크립트 추가
10. 마지막에 `docker-compose` 를 실제 운영 경로로 승격

## 구현 전 체크리스트

- [ ] DB 라이브러리 선정 (`sqlalchemy`, `psycopg`)
- [ ] Alembic 디렉터리 생성
- [ ] 환경변수 -> 설정 객체 매핑 추가
- [ ] Repository Protocol 및 계약 테스트 추가
- [ ] CSV 어댑터 회귀 테스트 유지
- [ ] 첫 마이그레이션 대상 테이블 범위 확정
- [ ] 대시보드/배치 작업의 읽기 경로 전환 순서 확정

## 위험요인

- 현재 분석/리포트 로직은 파일명과 디렉터리 구조에 의존하는 부분이 있습니다.
- `SymbolLookup` 는 CSV 종목정보와 종목 마스터를 병합 조회하므로, DB 이전 시 동일한 우선순위 정책을 보존해야 합니다.
- 원본 KIS 응답 컬럼명과 정규화 컬럼명이 혼재하므로, 테이블 컬럼을 과도하게 먼저 정규화하면 회귀 위험이 커집니다.

## 권장 결론

이 작업의 1차 목표는 “CSV 제거” 가 아니라 아래 두 가지입니다.

1. 현재 수집/분석 흐름을 깨지 않는 DB 경계 정의
2. 실제 구현이 가능한 최소 ERD + 리포지토리 계약 확정

즉, 다음 구현자는 이 문서를 기준으로 **설정 -> Protocol -> CSV 어댑터 고정 -> DB 어댑터 추가 -> Alembic 연결** 순서로 진행하는 것이 가장 안전합니다.
