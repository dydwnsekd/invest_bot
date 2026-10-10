# 시작·재시작 사전검증 기록

> OKF 종류: `evidence` · 상태: `historical` · 실행일: 2026-10-10

## 대상과 범위

- 기준 코드: 원본 main `b29c346` + 이번 작업 트리.
- 작업: [G02](../improvements/operations.md#g02).
- 기존 **운영·배포 안정화** 세션의 격리 구현 후 기존 **QA·독립 검증 체계 개선** 세션을 하나씩 실행하고 메인이 통합했다. 새 세션은 생성하지 않았다.
- 서비스 경계 검증은 임시 설정과 fake Docker를 사용했다. 운영 DB·환경 설정·실제 Docker 서비스의 build/down/up/run·수집·전송·배포는 실행하지 않았다.
- 기존 `.restart.sh.un~`는 보존한다. G07a 재시도·G07b 준비 확인은 별도 대기 작업이다.

## 변경 전 재현

메인이 현재 restart.sh를 임시 프로젝트의 공백 있는 경로에 복사하고 외부 cwd에서 fake Docker로 실행했다. build는42, 나머지 명령은0을 반환하도록 했다.

- 실제 호출: down → build → up -d db migrate scheduler web.
- build42 뒤에도 up이 호출되고 최종 종료코드는0이었다.
- Docker 호출의 cwd는 프로젝트 위치와 달랐다.
- fake executable만 호출했으며 실제 Docker 서비스에는 접근하지 않았다.

## 변경 내용

- [start.sh](../../../start.sh)·[restart.sh](../../../restart.sh): Bash 실패 중단·프로젝트 경로 고정, 스케줄 파일 존재 확인→Compose `config --quiet`→빌드→scheduler 이미지의 검사 전용 CLI→명시 서비스 시작. restart는 사전검증 통과 후 down한다. down 실패도 up으로 진행하지 않는다.
- [스케줄 설정과 CLI](../../../src/invest_bot/jobs/scheduled_collection.py): YAML 매핑·종목·경로·양의 정수·boolean을 검사한다. 문자열 `"false"`를 False로 해석하고 0·음수·실수·숫자 boolean을 거부한다. 구체적인 수용 정책은 [운영 가이드](../../tasks/07_operations_docs.md#스케줄-설정-수용-정책)에 있다.
- `--validate-config`는 파일을 읽고 검사한 뒤 종료한다. runner·수집·마스터 동기화·DB/네트워크 호출과 수집 로그 생성 없이 실행된다. 잘못된 YAML·파일·필드의 오류 메시지에 설정 내용을 넣지 않는다.
- 기존 `--once`·정상 반복 실행·수집 로그 의미는 보존했다. `stop.sh`, Compose, Dockerfile과 runner AST는 기준 HEAD와 동일하다. 의존성은 추가하지 않았다.
- [스케줄러 회귀](../../../tests/test_scheduled_collection.py), [스크립트 경계](../../../tests/test_operations_scripts.py), [실제 CLI 부작용 차단](../../../tests/test_schedule_validation_cli.py), [추가 경계 회귀](../../../tests/test_schedule_preflight_boundaries.py)를 원본에 반영했다.

## 담당 구현과 독립 검증

| 실행 주체 | 환경·검증 | 새 실행 결과 |
| --- | --- | --- |
| 운영 세션 | 원본 `b29c346`을 임시 복사, G02 세 파일의 담당 테스트 | 83 passed |
| 운영 세션 | 같은 격리본의 기본 suite | 473 passed / 2 deselected |
| QA 세션 | 다른 임시 복사본의 담당 테스트 독립 재실행 | 83 passed |
| QA 세션 | 별도로 작성한 파일·기본 경로·추가 타입·서비스 경계 사례 | 36 passed |
| 메인 | 원본 통합 후 담당+추가 경계 회귀 | 118 passed in 18.45s |
| 메인 | 원본 기본 suite | 508 passed / 2 deselected / 6 warnings in 21.71s |

운영의 초기81개 회귀는 수정 전62 failed / 19 passed였다. 이후 `--once`·정상 반복 실행2개를 추가해 최종 담당 회귀는83개다. 메인도 수정 전 build42 뒤 up 호출·종료0을 독립 재현했다. 수정 후 같은 fake Docker에서 `config --quiet`→build까지만 호출하고42로 종료했다. 외부 cwd·공백 경로에서도 프로젝트 cwd였고 down/up은0회였다.

독립 QA는 기본 설정이 외부 cwd의 파일이 아닌 프로젝트 파일을 읽는 것을 확인했다. 잘못된 타입·잘못된 YAML·파일 누락·디렉터리 입력·UTF-8 오류가 실패로 종료됐다. CLI 하위 프로세스에 수집·마스터·runner·DB·network 호출 차단기를 설치하고 차단기 준비도 확인했으며, 감사 호출과 로그 생성은0회였다. 합성 자격값은 stdout/stderr에 노출되지 않았다. 실제 Docker의 진단 출력은 이 결과에 포함하지 않는다.

QA의 임시36개 중 Compose 문자열을 그대로 비교하는 정적 검사1개는 새 원본 회귀에 포함하지 않았고, 동작을 확인하는35개를 통합했다. 개별 수치의 실행 주체·대상을 구분하며 격리본 전체 테스트 수치를 원본 결과로 재사용하지 않는다.

### 원본 검증 명령

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest tests/test_scheduled_collection.py tests/test_operations_scripts.py tests/test_schedule_validation_cli.py tests/test_schedule_preflight_boundaries.py -q
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B scripts/run_tests.py --suite default -q
bash -n start.sh restart.sh stop.sh
git diff --check
```

원본의 현재 `config/collection_schedule.yaml`에도 검사 전용 CLI를 실행해 성공 문구와 종료0을 확인했다. 설정 내용을 출력하거나 변경하지 않았고 수집을 실행하지 않았다. `bash -n`·whitespace 검사도 통과했다.

변경 Python 파일의 AST 구문 검사와 변경 문서10개의 로컬 링크·anchor227개, 등록부의 고유 문서 ID55개를 확인했다. 별도 lint/typecheck 도구·설정은 프로젝트에 없어 실행하지 않았으며 구문 검사·독립 리뷰·동작 회귀로 검증했다.

### 미검증 범위와 검토 상태

실제 Docker build/run/down/up, 컨테이너 smoke, mount 쓰기 권한, 자격정보의 유효성, DB/API 연결, migration·web·scheduler의 기동 후 준비 상태와 원격 CI는 미검증이다. 사전검증 성공은 서비스 준비 완료를 의미하지 않는다. 후속 준비 확인은 G07b, 일시 수집 실패 후 대기는 G07a로 유지한다.

커밋·push·운영 재시작은 수행하지 않았다. G02 사전검증·실패 중단의 완료 조건은 독립 QA와 원본 로컬 회귀로 충족했다. 원본 기본 suite의 제외2개는 기존 opt-in 외부 네트워크·PostgreSQL 정책이며 경고6개는 기존 Alembic `path_separator` 설정 경고다. 변경은 커밋 전 검토 상태다.

## 실행 산출물

임시 산출물은 장기 보관 기준이 아니며 위 기록과 원본 회귀가 저장소의 증거다.

- 운영 구현: `/private/tmp/invest-bot-g02.eWgEDy/G02-report.md`, `G02.patch`.
- 독립 QA: `/private/tmp/invest-bot-g02-qa-20261010.5VTlsB/artifacts/G02-QA-report.md`, `g02-existing.xml`, `g02-independent.xml`.
- 메인 전후 fake Docker 호출: `/private/tmp/invest_bot_g02_baseline_9wkgb5ux/before_calls.jsonl`, `calls.jsonl`.
- 원본 기본 suite: `data/processed/test_reports/pytest_results.xml`, `pytest_command.txt` (ignored 실행 산출물).

## 관련 상태

이전 G01a·QA01 변경은 b29c346으로 커밋됐음을 확인했다. 원격 CI 조회는 GitHub CLI 미인증으로 결과를 가져오지 못했으므로 통과로 판단하지 않는다. G02는 해당 원격 CI 결과와 독립적인 작업이다.
