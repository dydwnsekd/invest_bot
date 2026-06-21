# invest_bot repository interfaces for DB ownership

## Purpose

이 문서는 현재 코드 기준 repository contract를 **reference / facts / artifacts** 책임 관점에서 정리한다. 구체적인 메서드 시그니처는 `src/invest_bot/db/contracts.py`를 canonical source로 본다.

## Repository classes

### `StockRepository`

**Responsibility**
- canonical 종목 reference 접근 계층
- 사용자 종목 검색/선택/표시의 source인 `symbols`를 읽는 계층

**Mutation policy**
- 일반 사용자 조회 경로에서는 write 금지
- 종목 마스터 sync/관리성 reference refresh에서만 write 허용

**Current contract**
- `upsert(record: StockRecord) -> None`
- `get_by_symbol(symbol: str) -> StockRecord | None`
- `list_all() -> Sequence[StockRecord]`

### `DailyPriceRepository`

**Responsibility**
- 일봉 가격 fact 저장/조회

**Mutation policy**
- 수집/배치 실행만 write 가능
- 조회는 read-only

**Current contract**
- `replace_for_symbol(symbol: str, records: Sequence[DailyPriceRecord]) -> None`
- `list_for_symbol(symbol: str, limit: int | None = None) -> Sequence[DailyPriceRecord]`
- `latest_trade_date(symbol: str) -> date | None`

### `InvestorDailyRepository`

**Responsibility**
- 투자자 수급 fact 저장/조회

**Mutation policy**
- 수집/배치 실행만 write 가능
- 조회는 read-only

**Current contract**
- `replace_for_symbol(symbol: str, records: Sequence[InvestorDailyRecord]) -> None`
- `list_for_symbol(symbol: str, limit: int | None = None) -> Sequence[InvestorDailyRecord]`
- `latest_trade_date(symbol: str) -> date | None`

### `DatasetFrameRepository`

**Responsibility**
- raw/derived DataFrame snapshot 저장소
- canonical reference를 대체하지 않는 artifact store

**Mutation policy**
- dataset 종류에 따라 실행 액션만 write 가능
- 사용자 조회는 read-only
- 특히 `dataset='stock_info'`는 사용자 종목 lookup source가 아니다

**Current contract**
- `save(record: DatasetFrameRecord) -> None`
- `load(dataset: str, filename: str) -> DatasetFrameRecord | None`
- `latest_for_symbol(dataset: str, symbol: str) -> DatasetFrameRecord | None`
- `list_latest(datasets: Sequence[str]) -> Sequence[DatasetFrameRecord]`

### `StockInfoSnapshotRepository`

**Responsibility**
- legacy stock_info snapshot 저장소

**Current status**
- 현재 제품 정책 기준 직접 가치가 낮다.
- canonical 종목 lookup source가 아니다.
- 후속 단계에서 제거 후보로 다룬다.

## Compatibility rules

- Constructor injection은 유지한다.
- Symbol normalization은 중앙화하고 6자리 zero-padding을 보존한다.
- Missing data path는 low-level DB exception 대신 empty result 또는 domain error로 반환한다.
- 사용자 조회 경로와 write path는 분리한다.

## Recommended direction

1. 사용자 종목 검색/선택/표시는 `StockRepository`만 사용한다.
2. `DatasetFrameRepository`는 raw/derived snapshot 용도로만 유지한다.
3. `StockInfoSnapshotRepository`는 제거 또는 완전 비사용화 후보로 본다.
4. canonical reference 변경은 종목 마스터 sync 경로에서만 허용한다.
