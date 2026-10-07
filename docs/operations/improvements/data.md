# 데이터 개선 작업

> OKF 종류: `plan` · 상태: `proposed` · 기준: 2026-10-05, main `1bd1dfa`

담당 세션은 **데이터 수집·저장 개선**이다. 이번 검토 결과를 바탕으로 다음 작업을 관리한다. 이전 구현·검증은 [9월 보고서](../session_reports/2026-09-13_data.md)에 있고, 현재 실행 순서는 [작업 색인](README.md)에 있다.

| ID | 우선순위 | 작업 | 상태 |
| --- | --- | --- | --- |
| G01a | P1 | 최신 snapshot NULL 정렬 | 대기 |
| G01b | P2 | 숫자형 snapshot 날짜 정규화 | 대기 |
| G08a | P2 | 요청한 일봉 수집 기간 확보 | 대기 |

<a id="g01a"></a>
## G01a — 최신 snapshot NULL 정렬

- **우선순위:** P1 · **상태:** 대기 · **선행:** 없음 · **연결:** [QA01](qa.md#qa01).
- **근거:** [repository:237·263](../../../src/invest_bot/db/repositories.py)의 날짜 내림차순에 NULL 위치가 명시되지 않았다. 10월 5일 메인의 운영 PostgreSQL 읽기 전용 비교에서 삼성전자·SK하이닉스의 오래된 NULL·0행 수급 snapshot이 선택됐다. NULL을 뒤로 보내면 두 종목의 10월 2일·30행 snapshot이 선택됐다. 실제 조회 결함을 확인했으며 데이터는 수정하지 않았다.
- **작업:** `latest_for_symbol`, `list_latest`, `list_for_dataset`의 최신 관측일 우선·NULL fallback·동률 선택 계약을 일치시킨다. 실패/빈 수집 이력의 표시와 유효 데이터 선택을 혼동하지 않는다.
- **완료 조건:** 같은 synthetic fixture를 임시 SQLite와 격리 PostgreSQL에 넣어 dated/NULL 경쟁, 날짜·생성시간 동률의 id 선택, NULL만 있는 fallback을 명시한 기대값과 비교한다. 세 메서드가 일치하고 PostgreSQL CI가 새 회귀를 실제 선택해야 한다. snapshot 이후 추가 조회0회 계약도 보존한다.
- **검증 경로:** [최신 목록 회귀](../../../tests/test_dataset_frame_list_latest_batch.py), [조회 횟수 회귀](../../../tests/test_watchlist_snapshot_queries.py), [현재 PostgreSQL migration 테스트](../../../tests/integration/test_postgresql_migrations.py), [CI](../../../.github/workflows/tests.yml). 현재 PostgreSQL 테스트는 migration 검증이므로 repository 회귀를 추가해야 한다. PostgreSQL 미실행은 통과로 기록하지 않는다.

<a id="g01b"></a>
## G01b — 숫자형 snapshot 날짜 정규화

- **우선순위:** P2 · **상태:** 대기 · **선행:** G01a 다음 별도 수정.
- **근거:** [frame_storage:80](../../../src/invest_bot/db/frame_storage.py)의 자동 날짜 변환은 문자열 `20261002`와 정수·실수의 해석이 다르다. 데이터 세션의 메모리 probe에서 숫자형 값이 1970년으로 해석됐다. [기존 회귀](../../../tests/test_db_frame_storage.py)는 문자열 사례만 다룬다. 실제 운영의 숫자형 저장 발생 여부는 이번 검토로 확인하지 않았다.
- **작업:** 기존 날짜 유틸리티를 확인하고 YYYYMMDD 정수·실수·문자열의 해석을 통일한다. 결측·잘못된 날짜 정책을 명시한다.
- **완료 조건:** 세 표현이 모두 `2026-10-02`이고 결측·잘못된 값도 정한 정책대로 처리된다. DB 기준일 추출과 기존 CSV 날짜 회귀를 보존한다. G01a와 한 변경으로 묶지 않는다.
- **검증 경로:** [frame 저장 테스트](../../../tests/test_db_frame_storage.py)와 관련 날짜 파서·CSV 테스트. 역할별 검증 기록에 실제 실행한 대상을 적는다.

<a id="g08a"></a>
## G08a — 요청한 일봉 수집 기간 확보

- **우선순위:** P2 · **상태:** 대기 · **선행:** 현재 endpoint의 조회 제한·다음 구간 요청 계약 확인.
- **근거:** [일봉 조회:43](../../../src/invest_bot/market/domestic_stock.py)는 한 번 요청하며 [collector:176](../../../src/invest_bot/market/collector.py)는 최소 행수를 검사한다. 365일 요청에 100행을 반환하는 stub에서 호출1회로 끝났다. 이전 운영 관측도 100행이었지만 API 제한과 연속 조회 방법은 아직 확인하지 않았다.
- **작업:** 공식 endpoint 자료를 확인한 뒤 필요한 구간을 추가 조회하고 거래일 중복을 제거한다. 요청 기간과 실제 확보 기간을 구분한다.
- **완료 조건:** 여러 응답 fixture의 합치기·중복 제거·빈 응답·진행 없는 응답 종료를 검증한다. 신규 상장·휴장 등 정당한 짧은 범위와 미충족 수집을 구분하고 실제 확보 범위를 결과에 표시한다. 성공 여부를 단순 365행 수로 판단하지 않는다.
- **검증 경로:** [수집 테스트](../../../tests/test_domestic_stock_collector.py)와 collector 회귀. 실제 외부 API 호출은 fixture 검증과 구분해 기록한다.

## 다른 역할에 넘긴 발견

날짜 없는 `investor_daily`와 유효 `investor_daily_summary` fixture에서 차트 수급이 누락되는 경로도 재현했다. 구현 소유권은 대시보드의 [G05a](dashboard.md#g05a)이며 이 문서에 별도 작업으로 중복 등록하지 않는다. summary 사용 자체를 잘못된 저장 계약으로 취급하지 않는다. 기존 수급 다중행·잘못된 값 처리·부분 저장 개선은 이번 신규 후보에서 제외했다.

## 실행 기록

2026-10-05: 검토 완료, 신규 구현 없음. 데이터 세션은 메모리 fixture만 사용했고 운영 DB·외부 API를 호출하지 않았다. G01a의 운영 SQL 비교는 메인의 별도 검증이다. 각 작업 진행 시 [색인의 갱신 규칙](README.md)을 따라 이 항목에 기록한다.

