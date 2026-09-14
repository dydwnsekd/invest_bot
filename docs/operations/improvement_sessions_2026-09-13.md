# invest_bot 개선 작업 세션

## 공통 기준

- 작성일: 2026-09-13
- 통합 작업: `프로젝트 개선 방안 분석`
- 통합 작업 ID: `01a09a75-fc7c-7ec0-8296-aed358d3152c`
- 분석 기준 커밋: `9e54fe6f8a009cdb6adeb3b002d85422e33c1779` (`main`)
- 실행 방식: 전문 작업 5개를 별도 Codex worktree에서 시작한다. 각 작업은 시작 시 실제 HEAD를 기록한다.
- 이 문서와 공통 README/task 문서의 최종 통합은 통합 작업이 맡는다.
- 각 작업은 자신의 worktree에서만 수정한다. 원본 프로젝트의 설정, 데이터, 미등록 파일을 수정하거나 다른 작업의 변경을 되돌리지 않는다.
- 새 라이브러리 도입, 실제 주문, 운영 DB 마이그레이션, 원격 push/배포는 이번 1차 작업에 포함하지 않는다.
- 각 기능 작업은 해당 기능의 회귀 테스트도 소유한다. QA는 별도의 통합·환경 검증 파일을 소유한다.
- 각 작업은 검증된 변경을 로컬 커밋으로 남기고 커밋 ID, 변경 파일, 검증 결과, 통합 주의점을 최종 보고한다. 다른 작업의 결과를 임의로 merge/cherry-pick하지 않는다.

## 확인한 기준점 이슈

1. 원본에만 미등록 마이그레이션 `migrations/versions/20260703_000003_add_report_favorite_symbols.py`가 존재한다. 데이터 작업이 검토 후 자신의 worktree에 포함한다. revision은 `20260703_000003`, down_revision은 `20260612_000002`이며 `report_favorite_symbols` 테이블을 만든다. 다른 작업은 이 파일을 별도로 구현하지 않는다.
2. 미등록 마이그레이션을 포함한 임시 복사본에서 전체 테스트 결과는 `340 passed, 2 failed`였다. 두 실패는 DB 초기화의 종목 마스터 다운로드가 네트워크 제한으로 실패한 경우다. 임시 종목 마스터 fixture를 제공한 뒤 해당 두 테스트는 통과했다.
3. `tests/test_init_db_script.py`는 현재 프로젝트 설정 파일을 잠시 덮어쓴다. QA 작업이 임시 설정과 현재 Python 실행 파일을 사용하도록 격리한다. 원본 프로젝트에서 이 테스트를 실행하지 않는다.
4. 실제 운영 DB의 데이터 상태, 외부 API 응답, Docker 실행 결과와 사용자 화면의 지연 시간은 이번 분석에서 검증하지 않았다.

## 역할과 파일 소유권

| 작업 | 역할 | 소유 범위 | 1차 목표 |
| --- | --- | --- | --- |
| 데이터 수집·저장 개선 | executor | `src/invest_bot/clients/`, `src/invest_bot/market/`, `src/invest_bot/db/`, `migrations/`, `src/invest_bot/jobs/collect_market_data.py`, 관련 데이터 단위 테스트 | 마이그레이션 누락 해소, 수급 다중 행 보존, 종목 메타데이터 보존, 부분 저장 상태의 정확성 |
| 퀀트·백테스트·리포트 개선 | executor | `src/invest_bot/backtest/`, `src/invest_bot/strategy/`, 지표·신호·백테스트·시장 리포트 job, 관련 단위 테스트 | 일별 평가금액 기준 MDD, 리포트 기준일 일관성 |
| 대시보드 구조·조회 개선 | designer/executor | `src/invest_bot/dashboard/`, `streamlit_app.py`, 대시보드 관련 단위/AppTest 테스트 | 조회 비용 측정과 반복 조회 축소, 동작을 보존하는 책임 분리 |
| 운영·배포 안정화 | executor | `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `config/*.example`, `scripts/` 중 `run_tests.py` 제외, `src/invest_bot/jobs/scheduled_collection.py`, 운영 관련 단위 테스트 | 쓰기 가능한 로그 경로, migration과 마스터 초기화 분리, 시작·재시작 검증 |
| QA·독립 검증 체계 개선 | test-engineer/verifier | `tests/conftest.py`, `tests/helpers.py`, `tests/test_init_db_script.py`, 신규 독립 통합 테스트, `pytest.ini`, `scripts/run_tests.py`, `.github/workflows/` | 설정·네트워크 격리, 기존 의존성을 이용한 CI와 회귀 검증 |

운영 작업은 `tests/test_init_db_script.py`를 수정하지 않고 QA 작업에 필요한 실행 계약을 보고한다. QA 작업은 기능 작업이 소유한 테스트 파일을 변경하지 않는다. 대시보드 작업은 백테스트 수식과 DB repository를 수정하지 않는다. 퀀트 작업은 대시보드 모듈을 수정하지 않고 필요한 연결 변경을 통합 작업에 보고한다.

## 완료 조건

- 데이터: 여러 날짜의 수급이 모두 보존되고 빈 응답이 정상 fact로 생성되지 않는다. 수집으로 기존 종목명·시장 구분이 손상되지 않는다. 일부 저장 후 실패한 경우 실제 저장 상태가 실행 결과에 반영된다. 신규/기존 스키마 마이그레이션을 임시 DB에서 검증한다.
- 퀀트: 보유 중 `100 → 50 → 100`인 사례의 일별 MDD는 50%이며 요약과 일치한다. 첫 손실 거래도 초기자산을 기준으로 낙폭에 포함한다. 리포트에는 선택 기준일보다 미래의 값이 포함되지 않고 역순·결측·서로 다른 날짜의 입력이 명시적으로 처리된다.
- 대시보드: 수정 전후 동일 fixture에서 조회 횟수와 실행 시간을 기록한다. 현재 UX, 홈/관심종목의 조회 전용 동작, 탭 왕복 설정, 기존 저장 이력 해석을 보존한다. 저장 후 갱신된 값이 보이도록 캐시 수명이나 무효화 범위를 명시한다.
- 운영: 기본 예시 설정의 로그가 읽기 전용 config 아래에 쓰이지 않는다. migration만 검증할 수 있고 외부 종목 마스터가 실패해도 스키마 결과를 구분할 수 있다. Docker 검증이 불가능하면 정적 검증과 실행 미검증 범위를 구분한다.
- QA: 기본 테스트가 원본 설정·운영 DB·실제 네트워크에 의존하지 않는다. 실패를 skip/xfail로 숨기지 않는다. 데이터/퀀트의 알려진 결함은 기존 기준점 실패와 기능 변경 후 통과를 구분해 기록한다. PostgreSQL 검증을 실제 실행하지 못하면 통과로 보고하지 않는다.

## 작업 결과 문서

각 작업은 자신의 worktree에 `docs/operations/session_reports/2026-09-13_<data|quant|dashboard|operations|qa>.md` 한 개를 작성한다. 해당 문서는 작업별 전용 파일이며 공통 README·DESIGN·task 요약 변경 제안도 여기에 기록한다.

## 진행 순서

1. 동일 기준점에서 다섯 전문 작업을 시작한다.
2. 각 작업은 독립적으로 진행 가능한 수정과 검증을 마친다.
3. 통합 작업에서 데이터 마이그레이션, QA 환경, 운영, 퀀트, 대시보드 변경의 의존성을 확인하고 통합 순서를 확정한다.
4. 통합 후 전체 테스트와 연결 경계 검증을 수행하고 공통 문서를 갱신한다.

## 생성된 작업

생성 결과 확인 후 작업 ID와 시작 상태를 기록한다.
