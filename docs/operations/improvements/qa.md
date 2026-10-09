# QA 개선 작업

> OKF 종류: `plan` · 상태: `proposed` · 기준: 2026-10-05, main `1bd1dfa`

담당 세션은 **QA·독립 검증 체계 개선**이다. 이전 결과는 [9월 보고서](../session_reports/2026-09-13_qa.md), 현재 순서는 [작업 색인](README.md)을 따른다. QA는 기능 구현을 중복 소유하지 않고 검증 공백·환경·CI·독립 완료 판정을 맡는다.

| ID | 우선순위 | 작업 | 상태 |
| --- | --- | --- | --- |
| QA01 | P1 | SQLite·PostgreSQL 최신 정렬과 CI | 검증 대기 |
| QA02 | P1 | 실제 renderer 호출 경계·조회·브라우저 | 대기 |
| QA03 | P2 | 실제 조합 artifact 저장·재로드 | 대기 |

<a id="qa01"></a>
## QA01 — SQLite·PostgreSQL 최신 정렬과 CI

- **우선순위:** P1 · **상태:** 검증 대기 · **연결:** [G01a](data.md#g01a)의 완료 판정 전. fixture·기대값은 수정 전 준비할 수 있다.
- **근거:** 10월 5일 검토 당시 [PostgreSQL 테스트:24](../../../tests/integration/test_postgresql_migrations.py)는 migration·테이블·revision만 검사하고 [CI:52](../../../.github/workflows/tests.yml)도 이 파일만 선택한다. [SQLite 회귀](../../../tests/test_dataset_frame_list_latest_batch.py)는 같은 종목의 dated/NULL 경쟁을 다루지 않는다. 따라서 기존 CI 성공은 운영에서 확인한 정렬 결함의 수정 증거가 아니다.
- **작업:** 데이터 담당의 repository 회귀와 격리 PostgreSQL 환경·CI 실행을 연결한다. 기능 테스트 파일의 소유권은 데이터 담당에게 두고 QA의 통합 파일·workflow는 QA가 담당한다.
- **완료 조건:** 같은 fixture로 세 조회 메서드의 dated/NULL·동률 id·NULL fallback 기대값을 양쪽 DB에서 검증한다. PostgreSQL CI가 해당 테스트를 실제 실행한 결과가 있다. 실행하지 못한 DB는 미검증으로 남긴다.
- **증거:** HEAD/작업 트리·임시 DB 종류·선택한 테스트·명령·결과·운영 DB 미사용을 기록한다. skip/xfail로 실패를 숨기지 않는다.

<a id="qa02"></a>
## QA02 — 실제 renderer 호출 경계·조회·브라우저

- **우선순위:** P1 · **상태:** 대기 · **연결:** [G05a·G05b·G06a·G06b](dashboard.md)의 해당 수정마다 확인.
- **근거:** [홈 테스트:3387](../../../tests/test_streamlit_dashboard.py)는 실제 renderer를 교체하고 [AppTest:2988](../../../tests/test_streamlit_dashboard.py)는 차트 loader를 교체한다. [차트 테스트](../../../tests/test_dashboard_snapshot_frame_loader.py)는 summary만 유효한 운영 형태를 다루지 않는다. [조회 회귀:51](../../../tests/test_watchlist_snapshot_queries.py)는 snapshot 생성 후 추가0회만 증명한다.
- **작업:** 실제 홈·리포트·관심종목 renderer를 사용하는 summary-only fixture와 수집·분석·리포트 생성·Discord 경계 spy를 연결한다. 계산·생성 함수는 mock하되 화면 조립은 검증 대상에서 제거하지 않는다. 역할 소유 테스트의 추가는 대시보드 담당과 조정한다.
- **완료 조건:** 검색·선택·탭 왕복에서 실행/전송0회, 실제 관측일 수급 연결, 상태 날짜 구분을 검증한다. 전체 rerun과 snapshot 이후 조회를 별도로 측정하고 후자의 추가 SELECT0회를 유지한다. G06a 클릭 mock의 기존 호출·부분 실패도 확인한다.
- **브라우저 판정:** 대비·390px 겹침·포커스는 AppTest 성공으로 대체하지 않는다. 같은 fixture의 1920×958·390×844 화면을 실제 브라우저에서 확인하고 캡처·관찰을 기록한다.

<a id="qa03"></a>
## QA03 — 실제 조합 artifact 저장·재로드

- **우선순위:** P2 · **상태:** 대기 · **연결:** [G08c](quant.md#g08c)의 완료 판정 전, G03·G04 완료 이후.
- **근거:** [사용자 설정 테스트:448](../../../tests/test_streamlit_backtest.py)는 단일 RSI의 메모리 결과, [이력 테스트:679](../../../tests/test_streamlit_backtest.py)는 수작업한 단일 전략 fixture를 사용한다. 실제 조합 출력→저장→재로드로 설정과 성과 보존을 증명하지 않는다.
- **작업:** RSI40/60을 포함한 실제 조합 출력을 임시 artifact에 저장하고 새 service에서 재로드하는 왕복 회귀를 기능 담당과 연결한다. 운영 artifact를 덮어쓰지 않는다.
- **완료 조건:** 구성 전략 설정·방식·가중치·입력 provenance·거래·최종자산·MDD를 저장 전후 비교한다. 중복 날짜는 G03 정책을 적용하고, 기존 artifact의 호환/미지원 정책도 확인한다.
- **검증 경로:** [persistence 회귀](../../../tests/test_backtest_persistence.py), [조합](../../../tests/test_backtest_combination.py), [대시보드 백테스트](../../../tests/test_streamlit_backtest.py). 실제 생성 결과를 사용했는지 명시한다.

## 실행 기록

2026-10-05: 원본 main과 통합 계획을 독립적으로 읽어 세 검증 공백을 확인했다. QA 세션의 이번 검토에서는 파일 변경·테스트 실행·운영 호출을 수행하지 않았다. 세 작업은 완료된 QA 결과가 아니라 앞으로 보완할 항목이다. 진행 시 [색인의 갱신 규칙](README.md)을 따른다.


2026-10-09 최종 결과: QA01의 독립 코드 리뷰·로컬 DB 검증을 완료했다. [신규 PostgreSQL 정렬 테스트](../../../tests/integration/test_postgresql_dataset_frame_ordering.py)는 localhost/테스트 DB 보호와 UUID 스키마 격리·정리를 적용한다. CI 실행 대상을 tests/integration으로 연결했고 같은 실행 명령이 2개를 선택·통과했다. 수정 전 HEAD repository를 복원하면 같은 회귀가 예상한 1 failed이며, 통과·실패 뒤 QA 스키마도 정리됐다. 원본 통합 후 기본 suite 398 passed / 2 deselected, PostgreSQL 2 passed. 원격 GitHub Actions는 커밋 전이라 미실행이며 QA01 상태는 **검증 대기**다. [검증 기록](../session_reports/2026-10-09_latest_snapshot_ordering.md). 임시 DB 제거 확인 완료.
