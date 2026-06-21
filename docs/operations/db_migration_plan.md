# invest_bot DB ownership and migration plan

이 문서는 현재 DB 구조를 **reference / facts / artifacts**로 다시 구분하고, 사용자 조회와 실행 액션의 write boundary를 고정하기 위한 운영 계획이다.

## Current ownership policy

- `symbols`는 canonical 종목 reference table이다.
- 사용자 Web 조회(검색/선택/미리보기/단건 조회)는 완전 read-only다.
- 수집/분석/리포트 실행만 fact/artifact 테이블을 갱신할 수 있다.
- `dataset_frames.stock_info`는 canonical 종목명 source가 아니다.
- `stock_info_snapshots`는 제거 후보다.

## Table responsibility summary

| Table | Class | User-driven mutation allowed? | Notes |
| --- | --- | --- | --- |
| `symbols` | Canonical reference | No | 종목 마스터 sync만 갱신 |
| `daily_prices` | Collected facts | Yes, execution only | 수집/배치 실행 전용 |
| `investor_daily` | Collected facts | Yes, execution only | 수집/배치 실행 전용 |
| `dataset_frames` | Artifacts / snapshots | Yes, execution only | dataset별 정책 분리 필요 |
| `stock_info_snapshots` | Deprecated candidate | No | 제거 후보 |

## Immediate cleanup targets

### 1. Lookup source normalization
- 종목 검색/선택/표시는 `symbols` 단일 source로 고정
- `SymbolLookup`, dashboard symbol-name map, report symbol-name fallback 정리

### 2. Read/write path split
- 사용자 조회에서 DB/file write가 일어나지 않도록 경로 분리
- 실행 액션만 `daily_prices`, `investor_daily`, processed `dataset_frames`를 갱신

### 3. `stock_info` responsibility reduction
- `dataset_frames.stock_info`는 raw snapshot 또는 제거 대상으로 축소
- `stock_info` raw 응답은 canonical source에서 제외

### 4. `stock_info_snapshots` deprecation
- 코드/문서/마이그레이션에서 제거 준비
- 필요 시 중간 단계에서는 비사용화 후 drop migration 적용

## Migration sequence

### Phase 1 — Documentation freeze
- `db_schema.md`를 canonical 문서로 고정
- ERD/plan/repository 문서를 현재 정책 기준으로 맞춤

### Phase 2 — Read-only lookup enforcement
- 사용자 조회 경로에서 write 제거
- 종목 lookup source를 `symbols`로 단일화

### Phase 3 — Snapshot policy cleanup
- `dataset_frames.stock_info` 의존 제거 또는 역할 축소
- `generate_market_report` 등 raw stock_info 우선 경로 정리

### Phase 4 — Schema cleanup
- `stock_info_snapshots` 제거 migration 추가
- 관련 repository / contract / tests 정리

## Risks and guardrails

1. **Canonical contamination risk**
   - raw stock_info/fallback 값으로 `symbols`를 갱신하면 안 된다.

2. **Lookup regression risk**
   - `symbols` 단일 source 전환 시 UI lookup/search test를 먼저 보강해야 한다.

3. **Artifact overloading risk**
   - `dataset_frames`는 편의 저장소일 뿐 reference/fact 역할을 넘겨받으면 안 된다.

4. **Migration mismatch risk**
   - 문서의 정책 변경 후 실제 migration/model/repository 반영 순서를 어기면 문서와 구현이 다시 어긋난다.

## Acceptance criteria

- 어떤 문서에도 사용자 조회가 `symbols`를 갱신한다고 읽히지 않는다.
- 어떤 문서에도 `dataset_frames.stock_info`가 canonical 종목명 source라고 읽히지 않는다.
- 후속 구현자는 `symbols`, `daily_prices`, `investor_daily`, `dataset_frames`, `stock_info_snapshots`의 역할과 write boundary를 문서만 보고 결정할 수 있다.
