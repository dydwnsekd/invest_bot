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
- [x] 민감 설정·인증 캐시·로컬 DB·백업·이미지·연구 산출물의 Git 제외 규칙 (`efdc607`)
- [x] 스케줄러 일시 실패 후 기존 간격 대기·시도 상한 ([G07a](../operations/improvements/operations.md#g07a))

## 남은 항목

- [ ] 수집/분석/대시보드 운영 가이드
- [x] 공유 runtime 로그 확인 가이드
- [ ] 릴리즈/배포 방식 정리
- [ ] 시작 후 실제 준비 확인 ([G07b](../operations/improvements/operations.md#g07b))

## 스케줄러 실패 후 대기 (2026-10-29)

[G07a](../operations/improvements/operations.md#g07a)를 완료했다. 기준은 main `893d0e6` + 미커밋 후보이며 실제 설정을 제외한 추적 파일 격리본에서 기존 운영 → 기존 QA → 메인 최종 통합을 순차 수행했다. 신규 기능154개·독립68개, 관련347 passed와 기본1322 passed / 2 deselected / 36 warnings다.

### 실행 정책

- 주기 실행의 일시적인 마스터 동기화·수집 예외는 `collection_failed`로 기록한다. 다음 시도가 있으면 `collection_waiting`을 기록하고 기존 `interval_minutes × 60`초를 기다린 뒤 같은 프로세스에서 다시 실행한다. 실행 종료부터 대기하며 별도 재시도 주기나 새 YAML 항목은 추가하지 않는다.
- `run_on_startup: false`는 첫 실행 전에도 같은 간격을 기다린다. `--max-runs`와 `run_forever()` 반환값은 **성공과 재시도 가능한 실패를 포함한 시도 횟수**다. 마지막 시도로 상한에 도달하면 추가 대기하지 않고 종료한다. `--max-runs 0`은 수집·대기0회이며 음수 CLI 값도 기존처럼0으로 제한한다. 제한 실행의 정상 종료는 모든 수집의 성공을 뜻하지 않는다.
- 수집기가 반환한 종목별 일부/전체 실패 dict는 기존 `collection_finished` 결과로 기록한다. 예외 복구 경로로 다시 실행하지 않으며 `failed_count`를 확인해야 한다. `load_schedule_status().total_logged_runs`도 기존대로 완료 이벤트 수이고 시도 횟수와 다르다. 최근 실패·오류는 후속 성공 뒤에도 유지하며 최근 성공은 별도로 갱신한다.
- `run_once()`와 `--once`의 실패는 원래 예외와 비정상 종료를 유지한다. `--validate-config`는 스케줄/종목 파일만 검사하며 수집·마스터 동기화·DB/네트워크 연결·수집 로그 생성은 수행하지 않는다.
- 시계·대기·로그 처리 오류와 `KeyboardInterrupt`/`SystemExit`는 복구 대상으로 삼키지 않는다. 실패 로그 기록 자체가 실패해도 전파한다.

### 오류 구분과 범위

예외의 타입·HTTP 상태·DB 연결 무효화 표식을 사용하며 메시지 문자열로 재시도 여부를 추측하지 않는다. HTTP408·429·5xx는 대기 후 재시도하고, 인증/요청 오류를 포함한 나머지 HTTP 상태와 응답 없는 `requests.HTTPError`는 전파한다. 일반 `RuntimeError`는 정확한 타입만 허용하므로 `RecursionError`·`NotImplementedError` 같은 하위 프로그래밍 오류를 재시도하지 않는다.

DB는 SQLAlchemy pool timeout과 `connection_invalidated=True`인 `OperationalError`만 허용한다. 그 밖의 `OperationalError`는 일시 장애인지 인증·설정 오류인지 추정하지 않고 중단한다. 내장 timeout/connection 오류와 requests timeout/connection 오류(SSL 제외), urllib `URLError`(파일/권한·입력 타입·SSL 사유 제외)를 허용한다. 입력·파일/권한·알 수 없는 오류는 전파한다. 통신 오류의 세부 허용 경계는 [구현](../../src/invest_bot/jobs/scheduled_collection.py)과 [회귀](../../tests/test_scheduled_collection.py)를 따른다.

실제 API/토큰·DB·장시간 대기·Docker·서비스 재시작·배포·원격 CI는 검증 범위 밖이다. Compose의 기존 `restart: unless-stopped`는 유지하므로, 영구 오류로 종료된 프로세스는 외부 supervisor가 다시 실행할 수 있다. 이번 변경은 runner 내부의 일시 실패 대기를 보장하며, 기동 후 준비 확인은 별도 [G07b](../operations/improvements/operations.md#g07b)다.

### 검증 기록

- **운영 RED/GREEN:** 구현 전 복구 회귀19 failed / 145 passed를 확인했다. 최종 관련279개(기존125 + 신규154)는 모두 통과했다. 일반 wrapped `ssl.SSLError`는 제외 조건이 없는 후보에서2 failed / 2 passed, 보완 후 GREEN이다. 인증서 오류는 기존 ValueError 조건에서도 중단됐으므로 실패 사례로 소급 계산하지 않는다.
- **독립 QA:** 새 격리본에서 기존279개를 새로 실행하고, 실제 runner·main·JSONL·상태 consumer를 연결한68개를 더해347 passed / failure·error·skip0으로 지정 범위를 승인했다. 최초 QA 실행64 passed / 4 failed / 4 teardown errors는 slotted instance에 logger를 주입한 QA fixture 오류였다. QA 소유 테스트의 클래스 patch만 보정했고 제품/기능 회귀는 수정하지 않았다. 원래 실패 로그/XML은 보존했다.
- **메인 최종 후보:** QA 승인 소스/독립 테스트를 통합한 새 격리본에서 기본1322 passed / 2 deselected / 36 warnings, 종료0(40.77초)이다. XML에도1322 cases·failure/error/skip0이며 독립68개가 포함됐다. 경고는 기존 pandas 날짜 파싱·JSON roundtrip과 Alembic 설정 경로이며 이번 변경에서 숨기지 않았다. PostgreSQL 등 별도 suite 대상2개는 기본 선택에서 제외돼 실제 검증을 뜻하지 않는다.
- **격리·경계:** Python3.13.13, `env -i`의 최소 PATH·TMPDIR·bytecode 비활성화와 기본 네트워크 차단 fixture를 유지했다. 관련/기본 검증마다 별도 cache·basetemp를 지정했다. 운영은263입력 중 소유2개만 변경했고 QA는263입력을 모두 보존하며 독립 테스트만 추가했다. 최종 제품1개·테스트2개는 운영/QA/메인 후보의 SHA-256을 대조했다. 최종 전체 suite 이후 변경은 문서만 반영한다.

아래는 관련 검증의 정확한 대상과 기본 suite 선택이다. cwd는 실제 설정·운영 데이터가 없는 격리본이며 실행용 Python은 원본 가상환경의 절대경로를 사용했다. 생성 보고서는 격리본의 `data/processed/test_reports/`에만 남긴다.

```sh
python -B -m pytest tests/test_scheduled_collection.py tests/test_schedule_validation_cli.py \
  tests/test_schedule_preflight_boundaries.py tests/test_operations_scripts.py \
  tests/test_streamlit_dashboard.py::test_overview_surfaces_latest_collection_failure_even_when_failed_count_is_zero \
  tests/test_streamlit_dashboard.py::test_overview_retains_failure_until_a_later_run_finishes \
  tests/test_streamlit_dashboard.py::test_overview_does_not_reuse_old_exception_after_new_completion \
  tests/test_streamlit_dashboard.py::test_overview_uses_log_order_when_run_timestamps_tie \
  tests/test_g07a_independent_qa.py -q --tb=short
python -B scripts/run_tests.py --suite default -q --tb=short
```

최종 Python3파일의 AST/compile과 공백 검사를 통과했다. 관리 Markdown57개·로컬 링크737개·문서 ID57개·개념12개/관계14개의 누락·중복·잘못된 참조는0개다. 실제 설정4개·편집기 백업·HEAD·Git index를 보존했고 관련 없는 추적 파일 변경도0개다. 실제 TLS/DNS 복구·KIS/토큰·운영 DB/PG·Docker·재시작·CI·배포는 이 결과로 확인되지 않으며 commit·push는 수행하지 않았다. 다음 구현 후보는 G07b다.

## Git 관리 경계 (2026-10-17)

Git 제외 규칙은 [.gitignore](../../.gitignore), 실행 설정 설명은 [README](../../README.md#설정-파일)를 따른다. `efdc607`은 실제 설정의 로컬 변형·토큰 캐시·Streamlit secrets·개인 키·로컬 DB/덤프·편집기 백업·로그·이미지를 제외한다. `data/` 아래 가격·수급·백테스트 CSV/JSON·생성 HTML은 계속 제외하며, 10월13일 로컬 검증 보고서4개도 제외한다. 재현할 코드·테스트·설정 예시·`.streamlit/config.toml`·SVG는 계속 추적한다.

경로를 바꾸거나 새 파일을 추가할 때는 `git check-ignore -v --no-index <파일 경로>`로 확인한다. `.gitignore`는 이미 추적 중인 파일이나 과거 Git 이력을 제거하지 않는다. 이번 규칙 검증은 Git 이력 전체의 비밀값 감사를 수행했다는 뜻이 아니다.

10월17일 커밋 후보에서 전역·시스템 설정을 배제한 제외94개·유지44개 경로 검사, 당시 추적246파일의 제외 대상0개, 설정·배포 파일 관련 테스트6개를 확인했다. 세부 증거는 [운영 작업 기록](../operations/improvements/operations.md#남은-확인과-실행-기록)에 있다. 실제 설정·백업의 내용은 변경하지 않았다.

새 변경의 commit·push는 [사용자의 명시적 요청 규칙](../../agent.md#커밋과-push)을 따른다. 구현·문서 갱신·검증 완료를 자동 commit·push로 연결하지 않는다.

## 유튜브 요약 로컬 저장 (2026-10-19)

- **상태·범위:** 프로젝트 아래 `research/youtube/summaries/`를 만들고 [.gitignore](../../.gitignore)에 해당 폴더 전체 제외를 추가했다. 개인 `youtube-market-brief` 스킬의 저장 규칙과 `market-brief-strategy`의 파일 입력 경로를 연결했다. 이후 `youtube-transcript-api==1.2.4` 기본 경로와 `yt-dlp==2026.8.19` 자막 전용 보조 경로를 내장 수집기에 추가했다. 개인 스킬과 도구 전용 `.venv`는 `~/.codex/skills/`에 설치되며 이 저장소의 추적 파일이 아니다. 프로젝트 의존성은 변경하지 않았다.
- **저장 계약:** Markdown, `게시일_영상ID_요약생성시각.md`, 한국 시간 생성 시각, 미확인 게시일 `undated`, 기존 파일 보존. 영상 게시일·원래 정보 기준일·요약 작성일과 출처·자막 범위를 분리해 보존한다. 날짜 가중치는 전략 실행 때 다시 계산한다. 원문 확보에 실패한 내용을 요약 파일로 만들지 않는다.
- **중복 저장 방지:** 개인 스킬의 `summary_registry.py lookup/save/rebuild`와 사전 조회 지침을 추가했다. `research/youtube/summaries/summarized_videos.json`에 영상 ID별 정규 링크·대표 요약·기존 버전을 기록한다. 링크 형식·시작 시각이 달라도 기존 영상은 원문 수집·모델 실행 없이 기존 요약을 반환한다. 저장 직전 파일 잠금 안에서 재확인해 동시 요청도 파일 하나만 생성한다. 명시적 재요약에만 `--refresh`를 사용하고 기존 파일을 보존한다. 목록은 기존 Markdown을 기준으로 재구성하며 잘못된 메타데이터는 신규로 오인하지 않고 오류로 중단한다. 기존 두 파일은 변경 없이 영상1개·버전2개로 등록했고 최신 전체 요약을 대표로 선택했다. 기록·잠금 파일도 기존 폴더 제외 규칙에 포함된다.
- **출연자 비교:** 요약·전략 스킬 모두 출연자별 의견·질문·호응·제3자 인용을 나누고 공통점·명시적 상충·전제/기간 차이·입장 미확인을 비교한다. 같은 영상의 새 요약 버전을 저장하면서 기존 버전·날짜·주장 ID·미국채 단위 정정·불확실성을 보존했다. 자막에 화자 라벨이 없어 실제 영상의 이름별 귀속은 문맥 기준이며 별도 음성 대조는 하지 않았다. 가상4사례(동일 기간 반대 전망, 단기/장기 구분, 질문/인용, 귀속 불명)의 독립 읽기 전용 검증과 두 스킬 구조·참조·새 파일 Git 제외 검사를 통과했다. 날짜 가중치 계산 규칙은 변경하지 않았다.
- **실행 모델 요구:** 두 스킬의 본문 작업과 UI 기본 프롬프트에 `gpt-6-luna`를 지정했다. 현재 실행이 Luna로 확인되면 직접 수행하고, 그 외에는 공식 CLI의 명시적 모델 인자로 넘긴다. 기본 native 역할 호출은 설치된 역할 제한으로 거부되어 사용하지 않는다. 2026-10-19 CLI0.147.0의 읽기 전용 최소 호출도 ChatGPT 계정에서 모델 미지원(HTTP400)으로 종료1이었다. 설정·구조 검증과 실제 실행 가능 여부를 구분하며 자동 전환·성공을 주장하지 않는다. Luna 불가 시 다른 모델로 대체하지 않으며 일반 채팅·프로젝트 전역 모델은 변경하지 않았다.
- **중복 기능 검증:** 중복 도구11개(링크 변형, 기존 버전 이관, 누락·손상·오래된 목록 복구, 명시적 재요약, 동시 저장, 저장 후 목록 쓰기 실패 복구, 잘못된 메타데이터, ID 없는 자막 등)와 기존 수집기11개, 총22개를 설치된 스킬 전용 환경에서 통과했다. 실제 두 링크 조회는 기존 파일을 반환했고 SHA-256·파일 수 비교로 기존 두 요약 보존과 추가 생성 없음을 확인했다. 두 스킬 구조 검사와 문서/설정 계약6개도 통과했다. 새 영상의 Luna 생성 실행은 이번 검증 범위가 아니다.
- **기존 저장·수집 검증:** 실제 폴더의 임시 파일 쓰기·재조회·삭제, 중첩 Markdown/JSON을 포함한 제외4경로·유지4경로, Git 상태 제외 및 추적 파일 부재, 두 스킬 구조·참조 검증을 통과했다. `tests/test_db_migration_artifacts.py`는6 passed다. 후속 수집기 회귀11개와 실제 영상 `iY__Rhqbgb8`의 두 자막 경로 각각1316구간(0.734~2574.905초), 날짜 메타데이터와 완성 요약의 저장·재조회·Git 제외를 확인했다. 원문 캐시는 `.tmp/youtube-market-brief/`에 보관한다. 결과는 [운영 기록](../operations/improvements/operations.md#남은-확인과-실행-기록)에 남겼다.
- **미검증:** 자막 없는 영상·다른 접근 제한·향후 YouTube 변경·전사 모델, 최신 금융 자료를 이용한 전략 생성. 영상 속 경제지표와 전망의 현재 진위는 검증하지 않았다. 기존 개선 순서·서비스·DB·배포·커밋·push는 변경하지 않는다.

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
