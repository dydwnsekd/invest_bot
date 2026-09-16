# Task 07. Operations And Docs

## 목표

프로젝트 문서와 운영 안내를 정리해 작업 연속성과 운영 효율을 높인다.

## 완료된 항목

- [x] `README.md` 기본 정리
- [x] `agent.md` 프로젝트 가이드 작성
- [x] project skill 초안 작성
- [x] task 문서 구조 작성
- [x] 지표 설명 가이드 작성
- [x] 시장 리포트 설명 가이드 작성
- [x] 세션 분리 원칙 및 새 세션 프롬프트 문서 작성
- [x] DB 마이그레이션 준비 문서 작성 (`ERD`, `docker-compose` 초안 검토, repository interface 제안 포함)
- [x] Discord 리포트 전달 변경사항 문서 반영
- [x] 저장소 전용 OKF 지식 구조 및 task 문서 갱신 규칙 정의 ([OKF 규약](../../OKF.md))

## 남은 항목

- [ ] 수집/분석/대시보드 운영 가이드
- [x] 공유 runtime 로그 확인 가이드
- [ ] 릴리즈/배포 방식 정리

## 실행 경계와 로그 확인 (2026-09-15)

- 스키마만 적용: `python scripts/init_db.py --mode migrate-only`
- 마스터 동기화까지 실행: `python scripts/init_db.py --mode full`
- 모드 우선순위: CLI → `INVEST_BOT_INIT_MODE` → 기본 `full`
- Compose의 `migrate`는 `migrate-only`로 실행합니다. scheduler는 수집 전에 기존 마스터 동기화를 계속 수행합니다.
- full 모드에서 마스터 다운로드가 실패하더라도 `database migration complete`가 출력됐다면 스키마 적용은 완료된 상태입니다.

스케줄 설정의 `log_path`는 설정 파일의 디렉터리를 기준으로 해석합니다. 예시값 `../.runtime/logs/collection_scheduler.log`를 사용하면 config 밖의 runtime 경로에 기록합니다. 기존 사용자 설정은 자동 변경하지 않으므로 예전 `logs/...` 값이 있으면 새 경로로 갱신해야 합니다.

Compose의 호스트 경로는 `INVEST_BOT_RUNTIME_DIR` 또는 기본 `.docker/runtime`입니다. scheduler는 이 경로에 쓰고 web은 같은 경로를 읽습니다. 다음 명령은 기본 호스트 경로의 최근 이벤트를 확인합니다.

```bash
tail -n 20 .docker/runtime/logs/collection_scheduler.log
```

로컬 Python 실행의 기본 경로는 `.runtime/logs/collection_scheduler.log`입니다. 로그에는 `collection_started`, `collection_finished`, `collection_failed`, `collection_waiting` 이벤트가 기록됩니다. 수집 전처리나 수집기 예외는 `collection_failed`의 `failed_at`, `error_type`, `error`로 확인합니다. 재시작해도 기존 파일에 이어 기록하며 자동 로그 순환은 아직 제공하지 않습니다.

기본 테스트와 별도 PostgreSQL 검증은 `scripts/run_tests.py --suite default|postgresql`로 구분합니다. 컨테이너 이미지 빌드·서비스 기동 검증과 단위 테스트 통과 여부는 별도로 기록합니다.

## 이번 세션 문서 갱신 요약 (2026-07-06)

- `README.md`
  - Discord 리포트 전달 1차 범위 추가
  - batch/full-pipeline only, plain-text only, non-blocking failure 정책 반영
- `docs/analysis/market_report_guide.md`
  - Discord 전달 동작과 `sent` / `skipped` / `failed` 상태 설명 추가
  - Discord 메시지에 포함되는 필드 그룹 정리
- `docs/tasks/04_dashboard.md`
  - 작업 실행 탭의 Discord warning/success/error 집계 규칙 추가
  - settings 1회 생성/주입과 warning feedback branch 반영

## 관련 파일

- [`README.md`](../../README.md)
- [`agent.md`](../../agent.md)
- [`codex_session_prompts.md`](../operations/codex_session_prompts.md)
- [`SKILL.md`](../../skills/invest-bot-reference-reader/SKILL.md)
- [`indicator_guide.md`](../analysis/indicator_guide.md)
- [`market_report_guide.md`](../analysis/market_report_guide.md)
- [`db_migration_plan.md`](../operations/db_migration_plan.md)
