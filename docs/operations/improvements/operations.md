# 운영 개선 작업

> OKF 종류: `plan` · 상태: `proposed` · 기준: 2026-10-05, main `1bd1dfa`

담당 세션은 **운영·배포 안정화**다. 이전 작업은 [9월 보고서](../session_reports/2026-09-13_operations.md), 전체 실행 순서는 [작업 색인](README.md)을 따른다.

| ID | 우선순위 | 작업 | 상태 |
| --- | --- | --- | --- |
| G02 | P1 | 시작·재시작 사전검증과 실패 중단 | 완료 |
| G07a | P2 | 스케줄러 실패 후 대기 | 대기 |
| G07b | P2 | 시작 후 실제 준비 확인 | 대기 |

<a id="g02"></a>
## G02 — 시작·재시작 사전검증과 실패 중단

- **우선순위:** P1 · **상태:** 완료 · **선행:** 없음.
- **근거:** 10월 5일 검토 당시 [restart.sh](../../../restart.sh)는 경로 고정·실패 중단 없이 down→build→up을 실행했다. build42 mock에서 up 실행·최종코드0을 재현했다. 당시 [start.sh](../../../start.sh)는 설정 파일 존재만 확인했고 [schedule 로더](../../../src/invest_bot/jobs/scheduled_collection.py)는 문자열 `"false"`를 True로 해석했다.
- **작업:** 프로젝트 경로·실패 종료를 고정하고 서비스 중단 전에 Compose·스케줄 설정·빌드를 확인한다. 숫자·boolean 타입의 수용/거부 정책을 명시한다.
- **완료 조건:** 다른 디렉터리에서도 같은 프로젝트를 대상으로 한다. 설정/빌드 실패는 down/up0회와 비정상 종료다. 빈 종목·잘못된 숫자·문자열 boolean을 사전에 차단하거나 명시한 변환 정책으로 처리한다. 자격정보를 출력하지 않는다.
- **검증 경로:** [스케줄러 테스트](../../../tests/test_scheduled_collection.py), 임시 PATH의 Docker mock을 이용한 스크립트 경계 회귀. 모의 검사에서 실제 서비스·DB를 중단하지 않는다.
- **구현:** 두 스크립트의 프로젝트 경로·실패 종료를 고정하고 Compose 확인→빌드→scheduler 이미지의 `--validate-config` 검사 후 시작하도록 변경했다. restart만 검사 통과 후 down한다. 양의 정수·숫자 문자열과 boolean·문자열 true/false를 명시적으로 해석하며 형식·파일 오류를 입력 내용 없는 메시지로 처리한다. [현재 실행·설정 정책](../../tasks/07_operations_docs.md#시작재시작-사전검증-2026-10-10).
- **독립 QA:** 2026-10-10, 원본 main `b29c346` + G02를 격리 복사해 기존 회귀83개·추가 경계36개를 새로 실행, 모두 통과했다. QA 추가 회귀 중 실제 동작을 검사하는35개를 [원본 경계 테스트](../../../tests/test_schedule_preflight_boundaries.py)에 통합했다. [검증 기록](../session_reports/2026-10-10_start_restart_preflight.md).
- **원본 검증:** 2026-10-10, main `b29c346` + G02 미커밋 작업 트리, Python 3.13. 관련 회귀118 passed, `scripts/run_tests.py --suite default -q`는508 passed / 2 deselected다. 현재 스케줄 파일의 검사 전용 CLI도 종료0이며 Bash·Python 구문·whitespace 검사를 통과했다. fake Docker의 build42는42로 종료하고 down/up0회를 유지한다.
- **미검증 범위:** 실제 Docker 실행·mount 권한·외부 연결·기동 후 준비 상태·원격 CI. G07a/G07b는 별도 대기다. G02의 사전검증·실패 중단 완료 조건은 모의·로컬 회귀로 충족했고 코드는 `7fb6435`로 main에 반영됐다. 코드 반영을 실제 컨테이너 기동·운영 배포 확인으로 해석하지 않는다.

<a id="g07a"></a>
## G07a — 스케줄러 실패 후 대기

- **우선순위:** P2 · **상태:** 대기 · **선행:** G02의 설정 오류 구분.
- **근거:** [scheduled_collection:101](../../../src/invest_bot/jobs/scheduled_collection.py)는 기록 후 예외를 다시 던지고 run_forever가 처리하지 않는다. [Compose](../../../docker-compose.yml)는 unless-stopped로 재시작하고 시작 즉시 실행이 가능하다. 마스터 동기화 실패를 주입한 두 번의 모의 프로세스 시작에서 실패2회·sleep0회를 재현했다.
- **작업:** 영구 설정 오류와 일시 수집 예외를 구분하고 runner 내부의 대기·재시도 정책을 명시한다. 종목별 실패가 정상 결과로 반환되는 경우와도 구분한다.
- **완료 조건:** fake clock으로 실패→대기→성공이 프로세스 재시작 없이 이어진다. 영구 설정 오류는 반복 재시도하지 않고 --once 실패 종료는 유지한다. 기존 최근 실패 표시·후속 성공 기록도 보존한다.
- **검증 경로:** [스케줄러 회귀](../../../tests/test_scheduled_collection.py), 예외·종목별 일부 실패·성공 fixture. 실제1440분 대기는 테스트하지 않는다.

<a id="g07b"></a>
## G07b — 시작 후 실제 준비 확인

- **우선순위:** P2 · **상태:** 대기 · **선행:** G02.
- **근거:** start는 up -d 뒤 확인 없이 끝난다. [Compose:13](../../../docker-compose.yml)의 healthcheck는 DB에만 있다. web은 [dashboard 실행기:48](../../../scripts/run_streamlit_dashboard.py)의 초기 마스터 동기화 이후 서버를 시작한다. 시작 명령 성공만으로 web·scheduler 준비를 보장할 수 없다.
- **작업:** 제한 시간 안에 migration 종료 결과·web 응답·scheduler 안정 여부를 확인하고 실패 원인을 구분한다.
- **완료 조건:** 지연 성공, migration 실패, web 초기화 실패, scheduler 반복 종료, 시간 초과를 mock으로 검증한다. 실패는 원인과 비정상 종료를 제공한다. 정적/모의 확인과 실제 컨테이너 smoke를 별도로 기록한다.
- **검증 경로:** 시작 스크립트 경계 회귀·격리 환경의 준비 상태 mock. 실제 재시작은 기능 수정 완료와 별개의 운영 반영 단계다.

## 남은 확인과 실행 기록

2026-10-17 지식 갱신: Git 제외 설정과 관련 문서3개가 `efdc607`로 main에 반영된 것을 확인했다. 검증한 보완은 더 이상 미커밋 잔여 작업이 아니며 관리 경계는 [운영 가이드](../../tasks/07_operations_docs.md#git-관리-경계-2026-10-17)에서 확인한다. 이후 commit·push는 [사용자의 명시적 요청](../../../agent.md#커밋과-push)이 있을 때만 수행한다. 아래 제외94·유지44·관련6개 결과는 해당 커밋 후보의 당시 기록이며, 이번 문서 갱신으로 운영 DB/API·Docker·배포·원격 CI를 새로 검증하지 않았다.

2026-10-17 Git 제외 설정 커밋 검증: main `310a8bb`의 추적 파일과 이번 3파일 변경만 담은 격리본에서 재검증했다. 전역·시스템 Git 설정을 배제한 별도 임시 저장소에서 제외 경로94개와 유지 경로44개를 통과했고, 현재 추적246파일 중 제외 규칙 대상은0개다. 설정 예시·Streamlit 테마·SVG·소스·테스트·마이그레이션은 계속 관리한다. `tests/test_db_migration_artifacts.py` 6 passed, 관련 문서의 로컬 링크·공백 검사를 확인했다. 실제 설정·편집기 백업은 변경하지 않고 사용자 요청에 따라 Git 제외 설정과 관련 문서만 별도 커밋·push 대상으로 묶었다. 10월14일 수치는 당시 검증 기록으로 보존한다. Git 이력 전체의 비밀값 감사·실제 DB/API·이미지 빌드·서비스 재시작은 수행하지 않았으며 G07a/G07b 상태는 유지한다.

2026-10-14 Git 제외 보완: 사용자 요청으로 [.gitignore](../../../.gitignore)에 환경 설정 변형·인증 캐시·Streamlit secrets·개인 키·로컬 DB/덤프·편집기 백업·실행 기록·이미지 제외를 추가했다. 기존 `data/` 및 개별 보고서 제외를 보존했다. `git check-ignore --no-index`의 제외 경로73개와 유지할 소스/예시/문서33개를 통과했고, 현재 추적232파일 중 ignore 대상은0개다. `.restart.sh.un~`는 파일을 지우지 않고 제외했으며 설정 예시·Streamlit 테마·소스·테스트는 계속 추적된다. [설정 안내](../../../README.md#설정-파일)를 갱신했다. 실제 키 값을 출력하지 않았고 Git 이력 전체의 비밀값 감사·이미지 빌드·서비스 재시작·커밋·push는 수행하지 않았다. G07a/G07b 상태는 변경하지 않는다.

2026-10-05: 세 후보는 코드와 메모리/mock으로 검토했고 운영 컨테이너를 새로 조회하거나 변경하지 않았다. 수집 주기는 실행 종료 후 interval 대기다. timezone 없는 datetime.now()와 Compose의 TZ 미지정만으로 실제 UTC/KST를 이번 검토에서 확정하지 않았다. 로그 시각 정책은 후속 확인 항목이며 독립 구현 작업으로 아직 선정하지 않았다. 진행 시 [색인의 갱신 규칙](README.md)을 따른다.


2026-10-10: 원본 main `b29c346` 기준으로 기존 운영 세션에서 G02 격리 구현을 시작했다. Docker mock과 임시 설정만 사용하고 실제 서비스/환경 설정을 변경하지 않는다. 구현 종료 후 기존 QA 세션을 순차 실행하고 메인이 원본 통합·문서 갱신을 담당한다.

2026-10-10: 운영 세션의 6개 파일 패치와 QA의 추가 경계 회귀를 원본에 반영했다. 운영→QA를 순차 실행했고 원본 관련 회귀118 passed, 기본 suite508 passed / 2 deselected로 G02를 완료 처리했다. 실제 Docker·재시작·commit/push는 수행하지 않았다. 상세 대상·명령·제약은 [검증 기록](../session_reports/2026-10-10_start_restart_preflight.md)에 있다.

2026-10-10 후속 확인: G02 변경이 `7fb6435`로 main에 커밋된 것을 확인했다. 에이전트가 커밋·push·운영 재시작을 실행한 것은 아니며 앞선 로컬 검증·실제 Docker 미검증 범위는 그대로다.

2026-10-11 Docker 설정 제외 보완: 사용자 요청으로 기존 운영 세션의 작은 패치를 원본에 통합했다. [.dockerignore](../../../.dockerignore)에 실제 `config/kis_credentials.yaml`과 `config/collection_schedule.yaml`을 추가해 기존 `.env`·`config/app.yaml`과 함께 빌드에서 제외한다. 예시 파일 포함·별도 Dockerfile ignore 미존재·공백을 정적으로 확인했고 `tests/test_db_migration_artifacts.py::test_dockerignore_excludes_runtime_secret_files`는1 passed다. [설정 안내](../../../README.md#설정-파일)를 갱신했다. 실제 키 조회·이미지 빌드·재시작·커밋·push는 하지 않았다. 변경은 다음 이미지 빌드부터 적용되며 기존 이미지의 인증 파일 제거를 검증한 결과는 아니다. G07a/G07b는 대기를 유지한다.

2026-10-11 커밋 반영: 사용자 요청으로 위 Docker 제외 규칙과 G03 소스·회귀·관련 문서를 이 문서를 포함한 main 커밋에 묶는다. 실제 설정 파일과 기존 백업 파일은 커밋에서 제외하며 이미지 빌드·재시작·배포는 실행하지 않는다. 검증 수치는 각 변경의 실행 시점과 범위를 따른다.
