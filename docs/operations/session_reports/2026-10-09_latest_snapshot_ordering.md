# 최신 snapshot 정렬 수정·검증 기록

> OKF 종류: `evidence` · 상태: `historical` · 실행일: 2026-10-09

## 대상과 작업 경계

- 원본 코드 기준: main `4d4fd9b` + 이번 미커밋 작업 트리.
- 작업: [G01a](../improvements/data.md#g01a), [QA01](../improvements/qa.md#qa01).
- 기존 데이터 세션의 격리 구현 후 QA 세션을 순차 실행했다. 원본 통합·상태 갱신은 메인이 담당한다.
- 운영 DB·설정·실제 수집·Discord·배포는 사용하거나 변경하지 않았다. 기존 미등록 `.restart.sh.un~`를 보존했다.

## 수정 내용

[repository](../../../src/invest_bot/db/repositories.py)의 latest_for_symbol/list_latest/list_for_dataset을 관측일 내림차순 NULL 마지막 → 생성시각 내림차순 → id 내림차순으로 통일했다. 정상 날짜끼리의 선택·동률·NULL-only fallback·반환 순서와 목록 한 SELECT는 유지한다. G01b 숫자형 날짜 변환과 G05a 차트 수급 연결은 이번 범위에 포함하지 않는다.

[공통 fixture](../../../tests/dataset_frame_ordering_fixture.py)는 같은 행과 명시한 기대값을 양쪽 DB에서 사용한다. [SQLite 회귀](../../../tests/test_dataset_frame_list_latest_batch.py)는 날짜/NULL 경쟁·동률 id·NULL fallback·filename fallback·여러 dataset/반복 dataset 반환·단일 SELECT를 검사한다. SQL 문자열 형태만 맞추는 격리본 테스트는 최종 변경에서 제외하고 실제 PostgreSQL 행 선택 회귀로 대체한다.

## 메인의 PostgreSQL 변경 전후 재현

로컬 PostgreSQL17-alpine 임시 컨테이너의 `invest_bot_g01a_test` DB, 별도 `g01a_baseline` 스키마를 사용했다. 운영 DB URL이나 설정 파일은 사용하지 않았다. 테스트 두 행은 관측일10/02·30행의 dated.csv와 기준일 NULL·0행의 null.csv다. 수정 전후 같은 행으로 비교했다.

| 조회 | 수정 전 | 수정 후 |
| --- | --- | --- |
| latest_for_symbol | null.csv, NULL, 0행 | dated.csv, 2026-10-02, 30행 |
| list_latest | null.csv | dated.csv |
| list_for_dataset | null.csv → dated.csv | dated.csv → null.csv |

## 검증 명령과 결과

원본 `.venv` Python으로 실행했다. 임시 DB의 localhost 연결은 sandbox의 네트워크 제한 때문에 해당 DB로만 연결하는 명령에 escalation을 사용했다.

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest tests/test_dataset_frame_list_latest_batch.py tests/test_watchlist_snapshot_queries.py tests/test_dashboard_snapshot_frame_loader.py tests/test_db_frame_storage.py -q
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B scripts/run_tests.py --suite default -q
# QA_POSTGRESQL_URL에는 임시 localhost 테스트 DB만 지정
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B scripts/run_tests.py --suite postgresql tests/integration -q
```

- 원본 통합 후 표적 회귀: 9 passed.
- 최종 통합본 기본 suite: 398 passed, 2 deselected. 기존 Alembic 설정 경고6건. 추가 PostgreSQL 회귀가 opt-in으로 기본 suite에서 제외됨을 확인했다.
- 최종 통합본의 CI와 같은 PostgreSQL 선택 명령: migration과 정렬 회귀 2 passed, 기존 Alembic 경고2건.
- Python AST4개 파일·workflow YAML 정적 검사와 git diff --check 통과. 별도 lint/typecheck 설정·도구는 이 저장소에 정의돼 있지 않다.

## QA01 독립 검증과 CI 연결

[신규 PostgreSQL 회귀](../../../tests/integration/test_postgresql_dataset_frame_ordering.py)는 localhost와 *_test DB만 수용하고 UUID 이름의 별도 스키마를 생성·정리한다. 같은 공통 fixture와 기대값을 적용하며 실제 list_latest SELECT1회도 검사한다. [CI](../../../.github/workflows/tests.yml)는 PostgreSQL 대상 경로를 tests/integration으로 바꿔 migration과 새 정렬 회귀를 모두 선택한다.

QA는 원본을 복사한 격리본에서 표적 SQLite9 passed, CI collect2개, 같은 CI 명령의 PostgreSQL2 passed를 확인했다. baseline repository가 수정 전 HEAD와 같은 해시임을 확인한 뒤 같은 PostgreSQL 회귀의 예상한 1 failed를 재현했다. 실패는 NULL record 선점에 대한 행 선택 assertion이다. 통과·실패 뒤 QA 스키마 잔여가 없음을 확인했다. 독립 리뷰의 차단 결함은 없었다. 원본 통합 후 메인이 동일 CI 명령을 다시 실행해 2 passed를 확인했다.

## 환경 정리

검증 후 이번 작업에서 만든 임시 PostgreSQL 컨테이너를 정지했다. --rm에 의해 임시 DB와 컨테이너가 제거됐고, 이름으로 조회한 목록이 비어 있음을 확인했다. 운영 서비스는 정리 대상에 포함하지 않았다. 데이터·QA 세션은 둘 다 완료 후 idle이다.

## 남은 범위

이번 변경은 커밋 전이다. 실제 원격 GitHub Actions 결과와 운영 재배포 이후 화면은 미검증이며 로컬 검증과 구분한다. 구현·독립 로컬 QA는 통과했으나 원격 CI 성공을 완료 조건으로 두었으므로 G01a·QA01은 검증 대기로 기록한다. 커밋 후 실제 GitHub Actions가 새 회귀를 선택·통과했는지 확인하면 완료로 갱신한다.

## 관계

- 다음 작업·현재 상태: [개선 작업 색인](../improvements/README.md).
- 배경: [10월 5일 통합 계획](../improvement_plan_2026-10-05.md).
- 현재 제품 범위: [task 요약](../../tasks/00_summary.md).
