# 데이터 개선 작업

> OKF 종류: `plan` · 상태: `proposed` · 기준: 2026-10-05, main `1bd1dfa`

담당 세션은 **데이터 수집·저장 개선**이다. 이번 검토 결과를 바탕으로 다음 작업을 관리한다. 이전 구현·검증은 [9월 보고서](../session_reports/2026-09-13_data.md)에 있고, 현재 실행 순서는 [작업 색인](README.md)에 있다.

| ID | 우선순위 | 작업 | 상태 |
| --- | --- | --- | --- |
| G01a | P1 | 최신 snapshot NULL 정렬 | 검증 대기 |
| G01b | P2 | 숫자형 snapshot 날짜 정규화 | 완료 (main 반영: `3de986c`·`893d0e6`) |
| G08a | P2 | 요청한 일봉 수집 기간 확보 | 대기 |

<a id="g01a"></a>
## G01a — 최신 snapshot NULL 정렬

- **우선순위:** P1 · **상태:** 검증 대기 · **선행:** 없음 · **연결:** [QA01](qa.md#qa01).
- **근거:** 10월 5일 검토 당시 [repository:237·263](../../../src/invest_bot/db/repositories.py)의 날짜 내림차순에 NULL 위치가 명시되지 않았다. 10월 5일 메인의 운영 PostgreSQL 읽기 전용 비교에서 삼성전자·SK하이닉스의 오래된 NULL·0행 수급 snapshot이 선택됐다. NULL을 뒤로 보내면 두 종목의 10월 2일·30행 snapshot이 선택됐다. 실제 조회 결함을 확인했으며 데이터는 수정하지 않았다.
- **작업:** `latest_for_symbol`, `list_latest`, `list_for_dataset`의 최신 관측일 우선·NULL fallback·동률 선택 계약을 일치시킨다. 실패/빈 수집 이력의 표시와 유효 데이터 선택을 혼동하지 않는다.
- **완료 조건:** 같은 synthetic fixture를 임시 SQLite와 격리 PostgreSQL에 넣어 dated/NULL 경쟁, 날짜·생성시간 동률의 id 선택, NULL만 있는 fallback을 명시한 기대값과 비교한다. 세 메서드가 일치하고 PostgreSQL CI가 새 회귀를 실제 선택해야 한다. snapshot 이후 추가 조회0회 계약도 보존한다.
- **검증 경로:** [최신 목록 회귀](../../../tests/test_dataset_frame_list_latest_batch.py), [조회 횟수 회귀](../../../tests/test_watchlist_snapshot_queries.py), [현재 PostgreSQL migration 테스트](../../../tests/integration/test_postgresql_migrations.py), [CI](../../../.github/workflows/tests.yml). 10월 5일 기존 PostgreSQL 테스트는 migration 검증만 했다. 10월 9일 [정렬 회귀](../../../tests/integration/test_postgresql_dataset_frame_ordering.py)를 추가하고 CI에 연결했다. PostgreSQL 미실행은 통과로 기록하지 않는다.

<a id="g01b"></a>
## G01b — 숫자형 snapshot 날짜 정규화

- **우선순위:** P2 · **상태:** 완료 (코드 `3de986c`·문서 `893d0e6`, 검증일 2026-10-27) · **선행:** G01a 구현·로컬 검증 이후 별도 수정. G01a·QA01 원격 CI는 검증 대기를 유지한다.
- **착수 (2026-10-27):** main `1e73d60`의 추적 파일만 격리해 기존 데이터 세션을 재사용한다. 기존 날짜 파서의 범위를 대조하고 DB snapshot 기준일 추출만 수정한다. 데이터 구현 종료 후 독립 QA를 순차 실행하며 실제 설정·API·운영 DB·기존 저장 데이터 재쓰기·commit·push는 사용하지 않는다.
- **구현 후 QA 착수:** 데이터 세션의 기능2파일을 원본과 새 QA 격리본에 통합했다. 수정 전23 failed / 30 passed, 수정 후53 passed(신규49개), 기존 CSV·데이터·대시보드 소비자188 passed다. 이후 기존 QA 세션에서 별도 경계·SQLite 저장/조회·무효 입력 호환성을 검증했다. 다음은 당시 부분 결과와 후속 보완 기록이다.
- **독립 QA 후 보완:** 기존 관련241개는 통과했으나 신규 독립40개를 더한 합산에서273 passed / 8 failed였다. 기존 코드에서 저장 가능했던 무효 list/ndarray 날짜가 새 `pd.isna` guard에서 예외를 내는 회귀를 실제 SQLite로 확인했다. QA의 기존 JSON dtype 기대값2개는 기준 코드의 roundtrip과 비교하도록 QA 파일만 보정했고 최초 실패 로그도 보존했다. QA 종료 후 데이터 세션에서 비스칼라 입력 guard를 최소 보완했다. 당시 실패를 보완 후 통과 결과로 덮어쓰지 않고 보존한다.
- **보완 후 QA 재개:** 데이터 담당이 비스칼라 값을 결측 판정 전에 건너뛰는 guard2줄을 추가했다. 담당의 보완 전 독립32 passed / 8 failed, 보완 후 합산281 passed를 확인하고 원본·QA 격리본에 동일 source를 동기화했다. 기존 기능 테스트·독립 QA 파일은 보존했으며, 데이터 세션 종료 후 QA가 새 manifest262개 기준으로 독립 재검증했다.
- **근거:** 10월5일 검토 당시 [frame_storage:80](../../../src/invest_bot/db/frame_storage.py)의 자동 날짜 변환은 문자열 `20261002`와 정수·실수의 해석이 달랐다. 데이터 세션의 메모리 probe에서 숫자형 값이 1970년으로 해석됐다. [당시 회귀](../../../tests/test_db_frame_storage.py)는 문자열 사례만 다뤘다. 실제 운영의 숫자형 저장 발생 여부는 이번 검토로 확인하지 않았다.
- **작업:** 기존 날짜 유틸리티를 확인하고 YYYYMMDD 정수·실수·문자열의 해석을 통일한다. 결측·잘못된 날짜 정책을 명시한다.
- **완료 조건:** 세 표현이 모두 `2026-10-02`이고 결측·잘못된 값도 정한 정책대로 처리된다. DB 기준일 추출과 기존 CSV 날짜 회귀를 보존한다. G01a와 한 변경으로 묶지 않는다.
- **반영 결과·정책:** DB metadata 전용 scalar parser로 정수·정수값 실수·문자열·`.0` 문자열을 같은 날짜로 읽고 현지 날짜·혼합 타입을 보존한다. 비스칼라·무효 숫자/날짜·결측은 건너뛰고 첫 유효 컬럼의 최댓값을 사용한다. 원본/JSON·행 수·NULL 정렬은 바꾸지 않는다. [현재 입력 계약](../../tasks/02_data_collection.md#snapshot-기준일-날짜-계약-2026-10-27)을 따른다.
- **최종 검증:** 독립 신규40개 전체와 기존241개를 합친281 passed, 메인의 최종 소스 격리 후보 기본1100 passed / 2 deselected / 36 warnings. 신규 기능 회귀49개도 포함한다. QA의 수정 manifest262개 시작·종료 일치, 제품·기능/독립 테스트의 원본/데이터/QA/기본 후보 해시 일치를 확인했다. AST·문법·whitespace와 문서 연결 검사를 통과했다. 별도 QA가 지정 범위를 승인했으며 기존 세션은 idle이다.
- **검증 경로:** [frame 저장 테스트](../../../tests/test_db_frame_storage.py), [독립 저장·호환성 QA](../../../tests/test_g01b_independent_qa.py), 기존 CSV·데이터·대시보드 소비자. [명령·단계별 결과·경고와 한계](../../tasks/02_data_collection.md#snapshot-기준일-날짜-계약-2026-10-27)를 따른다.
- **남은 범위:** 실제 운영의 숫자형 저장 발생/기존 기준일·PostgreSQL·원격 CI·수집/API·운영 DB·배포는 미검증이다. 과거1970년/NULL metadata의 자동 수선이나 migration은 하지 않았다. G01a·QA01 원격 CI 상태는 그대로 유지하며 commit·push는 수행하지 않았다.

<a id="g08a"></a>
## G08a — 요청한 일봉 수집 기간 확보

- **우선순위:** P2 · **상태:** 대기 · **선행:** 별도 보충 수집에서 확인한 구간 요청을 일반 수집에 적용할 계약과 정당한 짧은 범위 처리 정책 정리.
- **근거:** 10월5일 검토에서 [일봉 조회](../../../src/invest_bot/market/domestic_stock.py)는 한 번 요청하며 [collector](../../../src/invest_bot/market/collector.py)는 최소 행수만 검사했다. 365일 요청에 100행을 반환하는 stub에서 호출1회로 끝났다. 10월13일 별도 보충 수집에서는 호출당100건과 과거 요청일 이동을 확인했고 `c1c55cd`로 반영했다. 현재 일반 collector는 이 [보충 수집 경로](../../../src/invest_bot/jobs/backfill_history.py)를 사용하지 않으므로 문제 전체가 해결된 것은 아니다.
- **작업:** 별도 경로에서 확인한 요청 계약을 일반 수집·대시보드·스케줄러에 적용할 범위를 정하고 필요한 구간을 추가 조회한다. 요청 기간·실제 확보 기간·정당한 짧은 범위·미충족 수집을 구분한다.
- **완료 조건:** 여러 응답 fixture의 합치기·중복 제거·빈 응답·진행 없는 응답 종료를 검증한다. 신규 상장·휴장 등 정당한 짧은 범위와 미충족 수집을 구분하고 실제 확보 범위를 결과에 표시한다. 성공 여부를 단순 365행 수로 판단하지 않는다.
- **검증 경로:** [수집 테스트](../../../tests/test_domestic_stock_collector.py)와 collector 회귀. 실제 외부 API 호출은 fixture 검증과 구분해 기록한다.

## 다른 역할에 넘긴 발견

날짜 없는 `investor_daily`와 유효 `investor_daily_summary` fixture에서 차트 수급이 누락되는 경로도 재현했다. 구현 소유권은 대시보드의 [G05a](dashboard.md#g05a)이며 이 문서에 별도 작업으로 중복 등록하지 않는다. summary 사용 자체를 잘못된 저장 계약으로 취급하지 않는다. 기존 수급 다중행·잘못된 값 처리·부분 저장 개선은 이번 신규 후보에서 제외했다.

## 실행 기록

2026-10-27 G01b 완료: main `1e73d60`에서 데이터→QA→데이터 보완→QA→메인 통합을 순차 수행했다. 최초 기능23 failed / 30 passed, 최초 독립 합산273 passed / 8 failed를 보존하고 무효 container 저장 회귀를 guard2줄로 보완했다. 독립40개·합산281개와 최종 격리 후보 기본1100 passed / 2 deselected / 36 warnings가 통과했다. 새 저장 metadata의 표현·컬럼·local day/불변성 계약과 SQLite 최신 조회·CSV·snapshot 이후 추가 SELECT0회를 확인했다. 기능2파일·독립 QA1파일·관련 문서는 커밋 전이다. [정책·증거](../../tasks/02_data_collection.md#snapshot-기준일-날짜-계약-2026-10-27). 다음 기능 후보는 G07a이며 기존 DB 자료·G01a/QA01 원격 CI는 변경하지 않았다.

2026-10-17 지식 갱신: 보충 수집의 반영 커밋 `c1c55cd`와 일반 collector의 단일 요청 경로를 대조했다. G08a는 명시적 보충 수집 CLI와 구분해 대기를 유지하며, G01a·QA01 원격 CI와 G01b 상태도 바꾸지 않았다. 아래 수집·테스트 수치는 각 날짜의 기록이다.

2026-10-15 기능별 커밋: 사용자 요청으로 명시적 기간 보충 수집 코드2개·테스트1개·관련 문서4개만 main에 반영했다. 다른 미커밋 연구 기능을 제외한 커밋 후보 격리본에서 전용26 passed, 기본858 passed / 2 deselected / 32 warnings를 새로 확인했고, 실제 CLI help0·잘못된 기간2와 소스 구문·문서 링크를 검증했다. 실제 API/운영 DB를 재실행하지 않았으며 설정·수집 데이터·검증 보고서·백업·Git 제외 변경은 커밋에 포함하지 않았다. G08a와 원격 CI 상태는 유지한다.

2026-10-13 사용자 요청에 따른 별도 장기 보충 수집: `jobs/backfill_history.py`와 `scripts/run_historical_collection.py`를 추가해 기존 16종목의 2년 가격·수급을 구간별로 조회하고 별도 history snapshot, 정규화 DB 행, 지표·신호·리포트를 갱신했다. KIS 공식 일봉 API의 호출당100건을 확인했고 과거 요청일 이동은 실제 API로 검증했다. 기존 원본 snapshot을 보존하며 서비스 재시작·이미지 교체·Discord 전송은 하지 않았다. 수집 16개 성공/0개 실패, 추가 경계 회귀19개와 기본851개/2 deselected를 통과했다. 시작 구간과 DB 재조회 검증의 최종 근거는 [수집 검증 기록](../../tasks/02_data_collection.md#보충-수집-검증-범위)을 따른다.

이 변경은 명시적 보충 수집 경로다. 기존 일반 수집·대시보드·스케줄러에는 연결하지 않았고, 신규 상장의 정당한 짧은 범위 구분을 포함한 G08a의 전체 완료 조건을 충족한 것은 아니므로 G08a 상태는 대기를 유지한다. 향후 일반 수집은 더 짧은 최신 snapshot을 만들 수 있으며 장기 snapshot은 별도 파일명으로 남는다.

2026-10-13 최종 검증:16종목 모두 초기31일 구간의 독립 조회를 통과했고 새 snapshot 중복0·확정 가격일 대비 누락 수급일0이다. 기존 수급값NULL 이력4행을 보존하며 실제 관측 수급의 정규화 DB 개수와 snapshot이 일치함을 재조회했다. 추가 숫자/거래정지 경계 검사 후 회귀26개·기본858개/2 deselected, 문서 링크·등록부ID·whitespace·HTML·ZIP·실제CSV 다운로드 확인을 완료했다. G08a 전체 상태는 대기를 유지한다.

2026-10-05: 검토 완료, 신규 구현 없음. 데이터 세션은 메모리 fixture만 사용했고 운영 DB·외부 API를 호출하지 않았다. G01a의 운영 SQL 비교는 메인의 별도 검증이다. 각 작업 진행 시 [색인의 갱신 규칙](README.md)을 따라 이 항목에 기록한다.


2026-10-09: 원본 main `4d4fd9b`를 기준으로 기존 데이터 세션의 격리 복사본에서 G01a 구현 시작. 메인은 원본 통합과 상태 문서를 담당하고, QA01은 데이터 작업 종료 후 순차 실행한다. 커밋·배포는 수행하지 않는다.

2026-10-09: 데이터 세션의 격리본 구현을 원본에 반영했다. 세 조회의 NULL 정렬을 명시하고 DB 공통 행 선택 fixture를 추가했다. SQL 문자열 형태만 검사하는 격리본 테스트는 실제 PostgreSQL 행 선택 회귀로 대체한다. QA01 독립 검증 대기.

2026-10-09 최종 결과: G01a 구현·로컬 검증 완료, 원격 CI 확인 전이라 상태는 **검증 대기**다. 기본 suite 398 passed / 2 deselected, PostgreSQL migration·공통 정렬 회귀 2 passed. QA는 같은 회귀가 수정 전 코드에서 실패하는 것을 확인했고 차단 결함을 발견하지 않았다. 임시 PostgreSQL은 제거됐다. [검증 기록](../session_reports/2026-10-09_latest_snapshot_ordering.md). 커밋·운영 재배포·원격 GitHub Actions는 미실행이다. 커밋 후 새 PostgreSQL 회귀가 포함된 CI 성공을 확인하면 완료로 갱신한다.

2026-10-10: G01a·QA01 관련 변경이 main `b29c346`으로 커밋된 것을 확인했다. 원격 CI 조회는 로컬 GitHub CLI 미인증으로 실행되지 않아 성공 여부 미확인이다. 검증 대기 상태를 유지하며 독립적인 G02를 진행한다.
