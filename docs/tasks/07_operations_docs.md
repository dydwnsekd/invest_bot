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

## 시작·재시작 사전검증 (2026-10-10)

프로젝트 루트의 `start.sh`, `restart.sh`, `stop.sh`를 사용합니다. 세 스크립트는 자신의 디렉터리로 이동하므로 외부 작업 디렉터리와 공백 있는 프로젝트 경로에서도 같은 프로젝트를 대상으로 실행합니다.

| 명령 | 실행 순서 |
| --- | --- |
| `./start.sh` | 스케줄 파일 존재 확인 → `docker compose config --quiet` → `docker compose build` → 설정 검사 → `up -d db migrate scheduler web` |
| `./restart.sh` | 같은 사전검증 → `down` → `up -d db migrate scheduler web` |
| `./stop.sh` | `docker compose stop`으로 전체 서비스 정지 |

각 단계가 실패하면 해당 종료코드로 중단합니다. 사전검증 실패 시 `down`과 `up`을 실행하지 않으며, `down` 실패 시 `up`을 실행하지 않습니다. 시작도 이미지 빌드를 확인하므로 변경된 검사 코드가 사용됩니다. 호스트의 Python 가상환경은 이 스크립트의 실행 조건이 아닙니다.

설정 검사는 새로 빌드한 scheduler 이미지에서 다음 명령으로 실행합니다. `--no-deps`로 DB·migration을 시작하지 않습니다.

```bash
docker compose run --rm --no-deps scheduler python scripts/run_scheduled_collection.py --validate-config
```

Python 환경이 이미 준비된 경우 다음 명령으로 같은 검사를 수행할 수 있습니다. 경로를 생략하면 프로젝트의 `config/collection_schedule.yaml`을 읽습니다.

```bash
python scripts/run_scheduled_collection.py --validate-config
python scripts/run_scheduled_collection.py --config /path/to/schedule.yaml --validate-config
```

`--validate-config`는 설정과 종목 파일을 읽고 해석한 뒤 종료합니다. 수집기·마스터 동기화·runner 생성·DB/네트워크 연결·수집 로그 생성은 수행하지 않습니다. 성공 문구는 설정의 유효성을 뜻합니다. 자격정보의 유효성, 로그 경로의 쓰기 권한, 외부 연결과 서비스 준비 상태는 이 검사에서 확인하지 않으며 [G07b](../operations/improvements/operations.md#g07b)가 후속 작업입니다.

### 스케줄 설정 수용 정책

| 설정 | 수용하는 값 | 거부하는 값·조건 |
| --- | --- | --- |
| `days`, `interval_minutes` | 양의 정수 또는 ASCII 숫자로만 구성된 정수 문자열. 문자열 앞뒤 공백은 제거 | 0, 음수, 실수, boolean, null, 빈 문자열, 소수점·기호가 있는 문자열 |
| `run_on_startup` | YAML boolean 또는 대소문자·앞뒤 공백을 무시한 문자열 `true`/`false` | 숫자·null·목록·매핑과 그 밖의 문자열. 문자열 `"false"`는 False로 해석 |
| `symbols` | 쉼표로 구분한 문자열 또는 문자열·정수의 목록 | boolean·실수·중첩 목록·매핑. 종목 파일까지 합친 결과가 비면 오류 |
| `symbols_file` | 파일 경로 문자열 또는 생략·null | 다른 타입, 지정한 파일의 누락·읽기 실패·UTF-8 오류 |
| `log_path` | 공백만 있는 값이 아닌 경로 문자열 | 다른 타입·빈 문자열·공백 문자열 |

종목 파일과 로그의 상대경로는 스케줄 설정 파일의 디렉터리를 기준으로 해석합니다. 종목 중복 제거와 기본값(`days: 365`, `interval_minutes: 1440`, `run_on_startup: true`)은 유지합니다. 최상위 YAML은 매핑이어야 하며 파싱·설정 오류는 입력 내용을 출력하지 않는 필드별 메시지로 알립니다.

구현과 모의 검증 근거는 [G02 검증 기록](../operations/session_reports/2026-10-10_start_restart_preflight.md)에 있습니다. 실제 컨테이너 시작·재시작은 이번 작업에서 수행하지 않았습니다.

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
