# 2026-09-13 운영·배포 안정화 결과

## 작업 기준

- 시작 HEAD: `c96894e6929d303d90f3b06543db66913e37084a`
- 분석 기준: `9e54fe6f8a009cdb6adeb3b002d85422e33c1779`
- 작업 브랜치: `codex/operations-runtime-boundaries`
- 작업 경로: `/Users/yongjun/.codex/worktrees/fdb1/invest_bot`
- 원본 프로젝트와 운영 DB, 외부 API, Discord, 주문, 배포는 변경하거나 실행하지 않았다.

## 구현 결과

### 스케줄 로그 경계

- 기본 스케줄 로그를 `config` 밖의 `../.runtime/logs/collection_scheduler.log`로 옮겼다.
- Compose는 호스트 `${INVEST_BOT_RUNTIME_DIR:-./.docker/runtime}`를 scheduler에 쓰기 가능으로, web에 읽기 전용으로 같은 `/app/.runtime` 경로에 마운트한다.
- 따라서 scheduler 재시작 뒤에도 호스트 bind mount의 JSONL 로그가 유지되고, web의 기존 `load_schedule_status()`가 같은 설정과 경로로 읽는다.
- 수집 전처리 또는 수집기가 실패하면 `collection_failed` 이벤트에 시각, 예외 타입, 메시지를 남기고 원래 예외를 다시 발생시킨다. 시작 이벤트와 실패 이벤트가 함께 보존된다.
- 새 runner가 같은 로그에 이어 쓰는 재시작 시나리오와 status reader의 성공·실패 해석을 단위 테스트로 고정했다.

### DB 초기화 경계

- `scripts/init_db.py --mode migrate-only`는 Alembic migration만 수행하며 `sync_stock_master()`를 호출하지 않는다.
- `scripts/init_db.py --mode full`은 기존처럼 migration 뒤 `sync_stock_master(force_refresh=True)`를 수행한다.
- 인자가 없으면 `INVEST_BOT_INIT_MODE`를 읽고, 환경변수도 없으면 기존 호환을 위해 `full`을 사용한다.
- 잘못된 환경변수 값은 migration 전에 argparse 오류로 종료한다.
- Compose의 `migrate` 서비스는 기존 command와 `service_completed_successfully` 의존 계약을 유지하면서 `INVEST_BOT_INIT_MODE=migrate-only`를 사용한다.
- migration 완료 메시지를 master sync 전에 출력하므로 full 모드에서 외부 master가 실패하더라도 스키마 성공 여부를 실행 로그에서 구분할 수 있다.

QA가 사용할 계약:

```text
CLI: python scripts/init_db.py --mode migrate-only
환경변수: INVEST_BOT_INIT_MODE=migrate-only
우선순위: 명시적 --mode > INVEST_BOT_INIT_MODE > full
허용값: migrate-only, full
```

QA 소유 `tests/test_init_db_script.py`는 수정하지 않았다. 해당 테스트는 환경에 `INVEST_BOT_INIT_MODE=migrate-only`를 전달하거나 CLI에 `--mode migrate-only`를 추가하면 종목 마스터 네트워크와 분리할 수 있다.

### Docker build context

- `.dockerignore`에 `.docker`, `.runtime`, `data`, `logs`를 추가해 PostgreSQL 데이터와 런타임 산출물이 이미지 build context로 들어가지 않게 했다.
- Dockerfile이나 dependency 집합은 변경하지 않았다.

## 변경 파일

- `.dockerignore`
- `config/collection_schedule.yaml.example`
- `docker-compose.yml`
- `scripts/init_db.py`
- `src/invest_bot/jobs/scheduled_collection.py`
- `tests/test_db_migration_artifacts.py`
- `tests/test_init_db_modes.py`
- `tests/test_scheduled_collection.py`
- `docs/operations/session_reports/2026-09-13_operations.md`

## 검증

- `PYTHONPATH=src /Users/yongjun/PycharmProjects/invest_bot/.venv/bin/python -m pytest tests/test_scheduled_collection.py tests/test_db_migration_artifacts.py tests/test_init_db_modes.py -q`
  - `19 passed in 0.37s`
- `INVEST_BOT_DATABASE_URL=sqlite+pysqlite:////tmp/invest-bot-operations.5hE4t1/migration-only.db INVEST_BOT_INIT_MODE=migrate-only PYTHONPATH=src /Users/yongjun/PycharmProjects/invest_bot/.venv/bin/python scripts/init_db.py`
  - exit 0; Alembic `20260612_000002`까지 적용
  - `database migration complete`
  - `stock master sync skipped (migration-only mode)`
- `docker compose config --no-env-resolution`
  - exit 0; migrate mode, scheduler RW volume, web RO volume, 기존 depends_on 조건 확인
- `PYTHONPATH=src /Users/yongjun/PycharmProjects/invest_bot/.venv/bin/python -m compileall -q scripts/init_db.py src/invest_bot/jobs/scheduled_collection.py tests/test_init_db_modes.py tests/test_scheduled_collection.py tests/test_db_migration_artifacts.py`
  - exit 0
- `PYTHONPATH=src .venv/bin/python -m pytest -q`
  - `348 passed, 2 failed in 2.35s`
  - 두 실패는 기존 QA 소유 `tests/test_init_db_script.py`가 기본 full 모드로 외부 종목 마스터를 다운로드하다 네트워크 이름 해석에 실패한 알려진 기준점 이슈다.
- `docker build -t invest-bot-operations-check:local .`
  - Docker daemon 접근 후 base image `python:3.13-slim` metadata 조회 단계에서 `DeadlineExceeded`로 실패했다.
  - 서비스나 DB는 기동하지 않았다. Compose 구조와 build-context 제외 규칙은 정적 검증했지만 완전한 이미지 빌드는 네트워크 제약으로 미검증이다.
- Ruff는 공유 가상환경에 설치되어 있지 않아 실행하지 못했다(`No module named ruff`). 새 dependency는 추가하지 않았다.

## 통합 계약과 남은 작업

- 데이터 역할: `master_sync` 변경은 필요 없다. migration-only 경계가 호출 자체를 차단한다. 데이터 역할의 `20260703_000003` 마이그레이션이 통합되면 임시 DB 검증의 head도 함께 올라가야 한다.
- QA 역할: `tests/test_init_db_script.py`의 subprocess에 위 migration-only CLI 또는 환경변수 계약을 적용하고, 현재 Python/설정 격리를 함께 처리해야 한다.
- 통합 문서: README와 운영 가이드에는 runtime bind mount, 로그 위치, 두 init mode, migration 성공과 master sync 실패의 구분을 반영하는 것이 좋다.
- 운영 전 확인: 실제 registry 접근 가능한 환경에서 이미지 build를 다시 실행하고, 별도 테스트 DB로 Compose `migrate` 종료 코드와 scheduler/web의 공유 로그 권한을 smoke test해야 한다.
