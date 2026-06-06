# Next Steps And OMX Handoff - 2026-06-07

이 문서는 현재 `invest_bot` 상태를 기준으로 다음 구현 우선순위와 OMX 실행 프롬프트를 정리한 handoff 문서다.

## Current baseline

- 핵심 수집/분석/신호/리포트 파이프라인은 아직 CSV 저장 경로를 사용한다.
- Docker `db` / `migrate` / `web` 실행은 가능하다.
- `migrate`는 현재 Alembic revision 실행이 아니라 SQLAlchemy `create_all()` bootstrap 단계다.
- HTML 대시보드는 Docker에서 `0.0.0.0:8000`으로 바인딩되고 호스트에서는 `127.0.0.1:8000`으로 접근 가능하다.
- 로컬 Python 기준은 repo 내부 `.venv` + Python 3.13이다.
- 검증 기준 최신 상태는 전체 테스트 `44 passed`다.

## Recommended work order

### 1. DB write path implementation

목표:

- collector가 더 이상 CSV만 쓰지 않고 DB table에도 실제 데이터를 적재하게 만든다.

우선 대상:

- `symbols`
- `daily_prices`
- `stock_info_snapshots`
- `investor_daily`

핵심 작업:

- SQLAlchemy repository 구현체 추가
- collector write path를 repository 경유로 분리
- CSV 유지 여부를 옵션 또는 dual-write로 결정
- `latest_trade_date()` + unique constraint + upsert로 중복 수집 방지 구현

완료 기준:

- 최소 1개 종목 수집 시 DB row가 실제로 생성된다.
- 동일 일자 재수집 시 중복 row가 생기지 않는다.
- 기존 CSV 기반 테스트를 깨지지 않게 유지하거나 parity 테스트로 대체한다.

### 2. Alembic migration introduction

목표:

- `create_all()` bootstrap을 revision 기반 schema 관리로 교체한다.

핵심 작업:

- `alembic.ini` 추가
- migration env 구성
- 초기 revision 생성
- `migrate` service를 Alembic upgrade 실행으로 전환

완료 기준:

- 빈 Postgres에 대해 `docker compose up db migrate` 또는 동등한 명령으로 schema 생성 가능
- revision history가 repo에 남는다
- bootstrap-only 로직은 제거하거나 check-only 진단용으로 축소된다

### 3. Read path migration

목표:

- 대시보드/리포트/백테스트가 파일 탐색 대신 DB query를 사용할 수 있게 한다.

핵심 작업:

- dashboard query repository 추가
- report generator / backtest loader read path 교체
- CSV는 export 또는 fallback artifact로만 유지

완료 기준:

- DB에만 있는 데이터로 대시보드와 리포트가 동작한다
- 로컬 파일 부재 시에도 기본 조회 기능이 유지된다

### 4. Operations hardening

목표:

- 실제 운영 형태에 가까운 안정성 작업을 추가한다.

핵심 작업:

- health endpoint 또는 `HEAD /` 지원
- scheduler / web / collector compose 실행 검증
- `.env` / `config/*.yaml` 운영 규칙 문서화
- Docker volume / DB 초기화 / 재기동 절차 정리

완료 기준:

- 운영자가 `docker compose` 기준으로 재현 가능한 실행 절차를 문서만 보고 수행할 수 있다

## Recommended execution lane

현재는 아래 순서가 가장 효율적이다.

1. `DB write path implementation`
2. `Alembic migration introduction`
3. `Read path migration`
4. `Operations hardening`

이 순서를 권장하는 이유:

- write path가 먼저 있어야 DB 전환의 실질 가치가 생긴다
- Alembic은 schema를 고정할 가치가 생긴 다음에 붙이는 편이 수정 비용이 적다
- read path는 write path 안정화 뒤에 옮겨야 디버깅 범위가 줄어든다

## OMX execution guidance

### Recommended mode

- 설계 확인만 필요하면 `$plan`
- 구현을 바로 진행하려면 `$team` 또는 `$ralph`
- 현재 작업은 shared file이 많고 persistence/collector/dashboard/test lane이 갈리므로 `$team`이 더 적합하다

### Recommended pre-read

OMX 세션에서 먼저 아래 문서를 읽게 하는 것이 좋다.

- `README.md`
- `docs/operations/db_migration_plan.md`
- `docs/operations/db_migration_change_report_2026-06-06.md`
- `docs/operations/python_runtime_and_test_guide.md`
- `docs/architecture/repository_interfaces.md`

### Recommended OMX prompt for planning

```text
$plan 현재 invest_bot은 Docker db/migrate/web는 뜨지만 핵심 수집/분석/리포트 저장은 아직 CSV 기반이다.
다음 목표는 DB write path 구현을 1순위로 진행하는 것이다.

반드시 아래 문서를 먼저 읽고 현재 코드 상태와 충돌 없는 실행 계획을 만들어라.
- README.md
- docs/operations/db_migration_plan.md
- docs/operations/db_migration_change_report_2026-06-06.md
- docs/operations/python_runtime_and_test_guide.md
- docs/architecture/repository_interfaces.md

계획에는 반드시 아래를 포함해라.
1. 구현 순서
2. shared file 충돌 위험
3. DB schema / repository / collector / tests 분해
4. 중복 수집 방지 구현 방식
5. 검증 명령
```

### Recommended OMX prompt for team execution

```text
$team 4 "Implement DB write path for invest_bot before read-path migration.
Read README.md, docs/operations/db_migration_plan.md, docs/operations/db_migration_change_report_2026-06-06.md, docs/operations/python_runtime_and_test_guide.md, and docs/architecture/repository_interfaces.md first.

Deliverables:
1. SQLAlchemy-backed repositories for symbols, daily_prices, stock_info_snapshots, and investor_daily
2. collector integration through repository boundaries
3. duplicate-collection protection using latest_trade_date + unique constraint + upsert
4. targeted tests plus full pytest verification
5. markdown change report instead of commit"
```

### Recommended OMX CLI commands

tmux 기반 OMX CLI에서 실행:

```bash
omx --tmux
```

계획 수립:

```bash
omx ask '$plan 현재 invest_bot의 다음 우선 작업은 DB write path 구현이다. README.md와 docs/operations/db_migration_plan.md를 먼저 읽고 실행 계획을 정리해라.'
```

팀 실행:

```bash
omx ask '$team 4 "Implement DB write path for invest_bot before read-path migration. Read README.md, docs/operations/db_migration_plan.md, docs/operations/db_migration_change_report_2026-06-06.md, docs/operations/python_runtime_and_test_guide.md, and docs/architecture/repository_interfaces.md first."'
```

### Recommended role split for `$team`

- `architect`: DB write path 경계 확정, repository/ORM shape 검토
- `executor`: repository 구현과 collector integration
- `test-engineer`: targeted tests, full pytest, duplicate-collection regression
- `verifier`: compose/runtime/manual verification, 문서/코드 일치 여부 점검

## Verification checklist for the next lane

- `.venv/bin/python -m pytest` 전체 통과
- DB row insert 확인
- 동일 종목/동일 일자 재수집 시 중복 미발생 확인
- `docker compose up --build db migrate web` 이후 대시보드 접근 확인
- 변경 결과를 markdown 문서로 먼저 정리

## Stop conditions

다음 작업은 아래 상태가 되면 멈추고 보고하면 된다.

- 최소 1개 write path가 실제 DB 적재로 동작
- 중복 수집 방지 검증 완료
- 테스트 및 실행 검증 증거 확보
- 문서가 변경된 코드 상태와 동기화됨
