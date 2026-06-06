# DB Migration Change Report - 2026-06-06

이 문서는 commit 전에 현재 세션에서 반영한 DB migration 정비 결과를 기능별로 요약한 보고서다.

## 1. DB bootstrap 실행 경로 정정

변경사항:

- `migrate` 컨테이너가 draft report 대신 실제 schema bootstrap을 수행하도록 정리했다.
- downstream 서비스가 `migrate` 성공 후 시작되도록 compose 의존 관계를 복구했다.

대상 파일:

- `docker-compose.yml`
- `src/invest_bot/db/bootstrap.py`
- `src/invest_bot/db/engine.py`

파일 내용 요약:

- `docker-compose.yml`
  - `migrate`에 `DATABASE_URL`을 주입한다.
  - `scheduler`, `web`, `collector`는 `migrate: service_completed_successfully`를 기다린다.
- `src/invest_bot/db/bootstrap.py`
  - `build_readiness_report()`는 check-only 보고서를 만든다.
  - `bootstrap_database()`는 engine 생성 후 등록된 ORM table을 `create_all()`로 bootstrap 한다.
- `src/invest_bot/db/engine.py`
  - `build_engine()`, `build_session_factory()`, `ensure_schema()`를 추가했다.

## 2. DB URL contract 정합화

변경사항:

- 설정과 migration helper가 모두 `postgresql+psycopg://`를 사용하도록 맞췄다.
- `DATABASE_URL`이 직접 주어진 경우 `AppSettings`가 이를 우선 사용한다.

대상 파일:

- `src/invest_bot/config/settings.py`
- `src/invest_bot/db/__init__.py`

파일 내용 요약:

- `settings.py`
  - `database_url` property가 `DATABASE_URL` 우선, 없으면 `postgresql+psycopg://...` 조합을 반환한다.
- `db/__init__.py`
  - `Base`, `build_database_url`을 외부 import surface에 다시 노출한다.

## 3. investor_daily schema 정정

변경사항:

- 새 DB 초안이 현재 리포트 생성 로직이 소비하는 요약형 투자자 수급 구조와 맞도록 되돌렸다.
- 중복 수집 회피 구현을 위한 `latest_trade_date()` repository contract를 추가했다.

대상 파일:

- `src/invest_bot/db/contracts.py`
- `src/invest_bot/db/models.py`

파일 내용 요약:

- `contracts.py`
  - `InvestorDailyRecord`는 `foreign_net_qty`, `institutional_net_qty`, `personal_net_qty`를 가진다.
  - `DailyPriceRepository`, `InvestorDailyRepository`에 `latest_trade_date()`를 추가했다.
- `models.py`
  - `investor_daily` 테이블은 `symbol + trade_date` unique 제약 아래 요약형 순매수 수량 컬럼을 저장한다.
  - `raw_payload` 컬럼으로 원본 보관 여지를 남겼다.

## 4. Python 가상환경 및 테스트 지침 추가

변경사항:

- repo 내부 `.venv` 기준 실행 규칙을 문서화했다.
- targeted test -> full test 순서를 명시했다.

대상 파일:

- `README.md`
- `docs/operations/db_migration_plan.md`
- `docs/operations/python_runtime_and_test_guide.md`

파일 내용 요약:

- `README.md`
  - macOS/Linux 기준 `.venv` 생성과 `.venv/bin/python -m pytest` 실행 예시를 추가했다.
- `db_migration_plan.md`
  - bootstrap 현황, `.venv` 기반 검증 명령, markdown 선전달 규칙을 추가했다.
- `python_runtime_and_test_guide.md`
  - 환경 생성, 테스트 순서, 대시보드용 결과 갱신, commit 전 보고 규칙을 분리 정리했다.

## 5. Docker 대시보드 바인딩 수정

변경사항:

- Docker 환경에서 HTML 대시보드가 `127.0.0.1` 대신 `0.0.0.0`에 바인딩되도록 수정했다.

대상 파일:

- `src/invest_bot/dashboard/server.py`
- `tests/test_dashboard_server.py`

파일 내용 요약:

- `server.py`
  - `INVEST_BOT_DASHBOARD_HOST`, `INVEST_BOT_DASHBOARD_PORT`를 읽어 실제 bind address를 결정한다.
- `test_dashboard_server.py`
  - env 값이 bind address에 반영되는지 검증한다.

## 6. 관련 테스트 기대값 정리

변경사항:

- bootstrap/compose/settings 관련 테스트 기대값을 현재 설계에 맞게 조정했다.

대상 파일:

- `tests/test_db_migration_artifacts.py`
- `tests/test_db_bootstrap.py`
- `tests/test_settings.py`

파일 내용 요약:

- compose 테스트는 `invest_bot.db.bootstrap --json`과 `migrate` 의존 관계를 검증한다.
- bootstrap 테스트는 check-only 보고서가 `applied=False`와 빈 table 목록을 반환하는지 확인한다.
- settings 테스트는 `postgresql+psycopg://` URL과 `DATABASE_URL` 우선 규칙을 검증한다.

## Validation

- `.venv`를 Python 3.13 기준으로 다시 생성했다.
- `.venv/bin/python -m py_compile`로 변경한 Python 파일의 구문을 검증했다.
- 전체 테스트 스위트 `44 passed`를 확인했다.

## Known gaps

- Alembic revision history와 DB-backed repository 구현은 아직 남아 있다.
- 현재 런타임의 핵심 데이터 저장 경로는 여전히 CSV 기반이다.
