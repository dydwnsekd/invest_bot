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
- **미검증 범위:** 실제 Docker 실행·mount 권한·외부 연결·기동 후 준비 상태·원격 CI. G07a/G07b는 별도 대기다. G02의 사전검증·실패 중단 완료 조건은 모의·로컬 회귀로 충족했고 커밋·운영 반영은 수행하지 않았다.

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

2026-10-05: 세 후보는 코드와 메모리/mock으로 검토했고 운영 컨테이너를 새로 조회하거나 변경하지 않았다. 수집 주기는 실행 종료 후 interval 대기다. timezone 없는 datetime.now()와 Compose의 TZ 미지정만으로 실제 UTC/KST를 이번 검토에서 확정하지 않았다. 로그 시각 정책은 후속 확인 항목이며 독립 구현 작업으로 아직 선정하지 않았다. 진행 시 [색인의 갱신 규칙](README.md)을 따른다.


2026-10-10: 원본 main `b29c346` 기준으로 기존 운영 세션에서 G02 격리 구현을 시작했다. Docker mock과 임시 설정만 사용하고 실제 서비스/환경 설정을 변경하지 않는다. 구현 종료 후 기존 QA 세션을 순차 실행하고 메인이 원본 통합·문서 갱신을 담당한다.

2026-10-10: 운영 세션의 6개 파일 패치와 QA의 추가 경계 회귀를 원본에 반영했다. 운영→QA를 순차 실행했고 원본 관련 회귀118 passed, 기본 suite508 passed / 2 deselected로 G02를 완료 처리했다. 실제 Docker·재시작·commit/push는 수행하지 않았다. 상세 대상·명령·제약은 [검증 기록](../session_reports/2026-10-10_start_restart_preflight.md)에 있다.
