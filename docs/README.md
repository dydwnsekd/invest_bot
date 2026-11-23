# invest_bot 지식 홈

이 문서는 프로젝트 지식의 시작점이다. 분류 규칙은 [OKF](../OKF.md), 모든 문서의 용도와 상태는 [등록부](knowledge/catalog.md)에 있다.

처음 프로젝트를 이해하려면 [프로젝트·OKF HTML 안내서](project-guide.html)를 읽는다. 2026-11-22 기준으로 전체 흐름·최초 실행·화면별 사용법·설정/로그·최근 개선·남은 작업·OKF 읽는 법과 검색 가능한 문서 목록을 담은 설명용 자료다. 표지와11개 주제를12개 페이지로 구분해 선택한 주제만 보여 주며 이전/다음과 목차로 이동한다. 문서 목록은8개씩 표시하고 검색/상태 필터를 적용한다.

## 질문에 따라 읽기

| 궁금한 내용 | 현재 진입점 |
| --- | --- |
| 프로젝트 실행·설정 | [프로젝트 README](../README.md) |
| 작업 규칙·새 세션 시작 | [agent 가이드](../agent.md) |
| 데이터와 기능의 관계 | [개념 지도](knowledge/concepts.md) |
| 현재 완료·대기 항목 | [task 요약](tasks/00_summary.md) |
| 다음 개선 작업·우선순위·역할별 상태 | [개선 작업 색인](operations/improvements/README.md)과 역할별 작업 문서 |
| 기존 역할별 작업을 어디서 이어갈지 | [개선 작업 추적](operations/improvement_sessions_2026-09-13.md) |
| 화면과 사용자 동작의 설계 기준 | [DESIGN](../DESIGN.md) |
| 지표·리포트 값의 의미 | [지표 가이드](analysis/indicator_guide.md), [리포트 가이드](analysis/market_report_guide.md) |
| 구현된 전략과 백테스트 규칙 | [전략·백테스트 현황](tasks/05_strategy_backtest.md) |
| 명시적 기간의 가격·수급 보충 수집 | [장기 보충 수집과 검증 범위](tasks/02_data_collection.md#장기-보충-수집-2026-10-13) |
| 전략별 매수 후 보유 비교·슬라이딩 혼합 연구 | [현재 백테스트 workflow](tasks/05_strategy_backtest.md#현재-백테스트-workflow) |
| 민감 설정·로컬 산출물의 Git 제외 | [Git 관리 경계](tasks/07_operations_docs.md#git-관리-경계-2026-10-17) |
| DB의 현재 구현과 문서 차이 | [개념 지도: 저장 경계](knowledge/concepts.md#저장-경계와-알려진-문서-차이) |
| 테스트 실행 방법 | [Python·테스트 가이드](operations/python_runtime_and_test_guide.md) |
| 초기화 모드와 운영 로그 | [운영 가이드](tasks/07_operations_docs.md) |
| 설계 선택의 이유 | [OKF 도입 결정](decisions/0001-local-okf.md) |
| 예전 보고서·계획 | [기록 보관 안내](archive/README.md) |

## 읽는 순서

처음 들어오면 프로젝트 README → 이 문서 → 개념 지도 → 담당 주제의 문서 순서로 읽는다. 작업 질문·재개 시 개선 작업 색인과 담당 역할 문서에서 우선순위·상태·완료 조건을 먼저 읽는다. task 요약의 기존 완료 범위와 관련 코드·테스트를 대조한다.

등록부에서 `proposed`인 문서는 아직 구현되지 않은 내용을 포함한다. `historical` 문서의 미완료 목록은 최신 task를 덮어쓰지 않는다. `review-required` 문서는 알려진 차이를 먼저 읽는다.

## 현재 기준 (2026-11-22)

T06d에서 KIS 모의 전용 주문·조회와 분리 SQLite 원장의 오프라인 경계를 구현했다. 실제 모의 계좌 연결 전 확인할 내용을 [Task06](tasks/06_trading_risk.md#t06d-kis-모의-주문과-체결-확인)에 정리했다. [개선 순서](operations/improvements/README.md)

## 현재 기준 (2026-11-21)

T06c에서 가상 주문의 상태·예약·결과 확인 정보를 전용 SQLite에 보존한다. 임시 DB로 재시작과 여러 프로세스의 경합을 검증했다. [현재 사용 범위](tasks/06_trading_risk.md#t06c-주문-원장과-결과-불명-복구), [개선 순서](operations/improvements/README.md)

## 현재 기준 (2026-11-18)

main `0c909fd`에 설계가 반영됐고 이번에는 T06b의 순수 주문 검증·한 인스턴스 메모리 예약/중복·명시 가상 결과 처리를 구현했다. [현재 공개 함수와 제약](tasks/06_trading_risk.md#t06b-공개-api와-구현-범위), [진행 상태](tasks/00_summary.md#현재-상태-2026-11-18), [개선 순서](operations/improvements/README.md)를 따른다. 기능79개·독립55개·메인 최종 관련150개/기본2138개와 금지 부작용 차단 smoke를 통과했다. 다음 구현은 T06c의 영속 원장·예약·복구다. 실제 KIS 모의 계좌/인증·체결·영속 원장·재시작/동시성은 후속이고 아래 날짜별 기록은 당시 상태다.

## 현재 기준 (2026-11-17)

main `6595f67`에 QA04 완료 문서가 반영됐고 이번에는 [Task06 모의 주문·리스크 설계](tasks/06_trading_risk.md)의 T06a를 완료했다. 기존 퀀트 자문·메인 보완·QA 문서 승인 후 다음 구현을 T06b 외부 호출 없는 검증/가상 실행으로 정리했다. 이후 영속 원장·예약·대사(T06c) → 모의 전용 어댑터(T06d) 순서이며 기능·실제 API 연결은 미구현이다. 이번 문서는 커밋 전이다. [현재 요약](tasks/00_summary.md#현재-상태-2026-11-17)과 [작업 색인](operations/improvements/README.md)을 따른다. 아래 날짜별 상태는 당시 기록이다.

## 현재 기준 (2026-11-16)

main `b34219f`의 원격 CI에서 기본2004개와 PostgreSQL2개가 모두 통과해 QA04를 완료했다. 기존 개선 항목의 지정 범위는 완료이며, 다음 개발 후보인 주문·리스크는 범위·설계부터 정할 미착수 계획이다. 오늘은 코드 변경 없이 완료 기록·문서·HTML만 갱신했고 커밋 전이다. [현재 요약](tasks/00_summary.md#현재-상태-2026-11-16)·[동일 SHA의 실제 CI 로그와 한계](operations/improvements/qa.md#qa04)·[작업 색인](operations/improvements/README.md)을 따른다. 아래 날짜별 상태는 당시 기록이다.

## 현재 기준 (2026-11-15)

main `c86b0f6` + QA04 후속 검토 작업본이다. CI의 새 SQL 계측3실패를 Linux에서 재현해 URL 표시 문자열 비교를 보완했다. 후속 기본은 Mac2004개·Linux2004개이며 수정 후 원격 GitHub 결과는 아직 없다. [현재 요약](tasks/00_summary.md#현재-상태-2026-11-15)·[후속 검증과 환경 차이](operations/improvements/qa.md#qa04)·[작업 색인](operations/improvements/README.md)을 따른다. 아래 날짜별 상태는 당시 기록이다.

## 현재 기준 (2026-11-13)

main `7b42920` + QA04 검토 작업본이다. G01a·QA01 원격 PostgreSQL2개 성공과 별도 임시 DB2개 재검증을 확인했다. 기본 CI의 OS 임시 경로 문제를 QA04로 분리해 로컬 기본1998개를 통과했다. 새 SHA 원격 재검증은 대기이며 커밋 전이다. [현재 요약](tasks/00_summary.md#현재-상태-2026-11-13)·[검증 근거와 한계](operations/improvements/qa.md#qa04)·[작업 색인](operations/improvements/README.md)을 따른다. 아래 날짜별 커밋 전/대기 표시는 당시 기록이다.

## 현재 기준 (2026-11-10)

main `66dbfed` + G08d 검토 작업본 기준이다. 자동 차트 배치/실제 크기 변경·글자 하한 보완과 독립12개·기본1994개 검증을 마쳤다. [현재 요약](tasks/00_summary.md#현재-상태-2026-11-10)·[변경·검증 한계](tasks/04_dashboard.md#자동-반응형-차트-2026-11-10)·[작업 색인](operations/improvements/README.md)을 따른다. 기존 G06c 문서 변경을 보존했으며 현재 G08d 기능/문서는 커밋 전이다. 원격 CI 대기와 실제 운영 검증을 별도로 구분한다.

## 현재 기준 (2026-11-09)

main `7c305c6` + G06c 검토 작업본 기준이다. 다중 카드 HTML·헤더/필터·390px 준비/결과 배치와 독립10개·기본1947개 검증을 마쳤다. [현재 요약](tasks/00_summary.md#현재-상태-2026-11-09)·[실제 화면·검증 한계](tasks/04_dashboard.md#헤더카드필터-배치-2026-11-09)·[작업 색인](operations/improvements/README.md)을 따른다. G08c는 코드/문서가 반영됐고 G06c는 커밋 전이다. 다음 기능은 G08d이며 과거 수치는 날짜별 증거로 구분한다.

## 현재 기준 (2026-11-08)

main `7c6dfe5` + 미커밋 G08c를 검증했다. 구성별 설정/출처 기록·명시 저장·새 service 이력 재조회, CSV 종목코드와 지표 출처 안내를 보완했다. 독립19개·관련431개·기본1921개, 실제 가상 앱과 손상 이력 보완 검증을 마쳤다. [현재 요약](tasks/00_summary.md#현재-상태-2026-11-08)·[저장/호환 계약](tasks/05_strategy_backtest.md#조합-설정-저장재로드-2026-11-08)·[개선 색인](operations/improvements/README.md)을 따른다. HTML도 현재 내용으로 갱신하며12페이지·문서 목록 분할을 유지한다. 다음 기능은 G06c이며 실제 운영·원격 CI 검증과 구분한다.

## 현재 기준 (2026-11-05)

main `cf261a9` + 미커밋 G08b를 검증했다. 준비용 선택과 실제 입력 범위·일봉 수, 실행 기록 고정·구형 이력 안내를 구현했다. 신규 기능33개·독립20개, 관련349개·기본1872개와 메인의 실제 가상 앱 화면 검증을 마쳤다. [현재 요약](tasks/00_summary.md#현재-상태-2026-11-05)·[계산/저장 계약](tasks/05_strategy_backtest.md#백테스트-입력-범위-2026-11-05)·[개선 색인](operations/improvements/README.md)을 따른다. HTML도 현재 내용으로 갱신하며12페이지와 문서 목록 분할을 유지한다. 다음 기능은 G08c·QA03이며 실제 API/운영 데이터·배포·원격 CI 검증과 구분한다.

## 지난 기준 (2026-11-03)

기준 HEAD는 main `c1b7810`이다. G08a 코드는 이 커밋에 반영됐으며 관련 Markdown과 HTML은 현재 검토 작업본이다. QA02 코드 `6607de7`·문서 `09bfcd7`, 연구 보고서 갱신 코드 `3fbbca7`·문서 `1e73d60`까지 반영됐다. G01b 코드 `3de986c`·문서 `893d0e6`까지 반영됐고 G07a 스케줄러 실패 후 대기도 코드 `00c5a9f`·문서 `74137bd`로 반영됐다. 관련347개·기본1322개는10월29일 검증 기록이며 G07b 시작 후 준비 확인도 코드 `41b7a68`·문서 `8d11305`로 반영됐다. 관련341개·기본1593개는10월31일 검증 기록이며 G08a 일반 일봉 수집의 요청 기간 확보도 독립 QA·기본1819개로 검증을 마쳤고 코드는 `c1b7810`에 반영됐다. 다음 기능 후보는 G08b 백테스트 실제 입력 범위다. 상태 대비·라벨 크기·포커스·아이콘은 [대시보드 계약](tasks/04_dashboard.md#상태-텍스트-대비와-라벨-크기-2026-10-22), 검증 범위는 [현재 작업 요약](tasks/00_summary.md#지난-상태-2026-11-03)을 따른다. G01b·G07a 검증 결과와 다음 순서는 [개선 작업 색인](operations/improvements/README.md)에서 관리한다. 보충 수집 CLI와 슬라이딩 혼합 연구의 반영을 일반 수집 G08a나 대시보드 조합 재로드 G08c의 완료로 해석하지 않는다.

테스트 수치·운영 데이터·브라우저·배포 확인은 기록된 날짜와 범위에 한정한다. HTML 안내서를 현재 코드와 예시 설정을 대조해 다시 구성했다. 1819개는 G08a 기능의 검증 기록이며 이번 HTML 변경은 링크·구조·스크립트를 별도로 확인한다. 실제 브라우저 미리보기는 로컬 파일 접근 정책으로 미확인이다. commit·push는 [명시적 요청 규칙](../agent.md#커밋과-push)에 따른다.

## 구조

```text
OKF.md                     저장소 내부 지식 규약
docs/README.md             질문별 탐색
docs/knowledge/            문서 등록부, 개념과 관계, 작성 양식
docs/decisions/            설계 판단과 이유
docs/archive/README.md     기존 위치에 보존한 과거 기록 안내
docs/analysis/             지표·리포트 의미
docs/architecture/         구조·계약·설계안 (상태는 등록부 참조)
docs/operations/           운영·작업 인계·검증 기록
docs/strategies/            전략 후보·설계 배경
docs/tasks/                 현재 기능 상태와 잔여 작업
```

폴더 이름만으로 최신성이나 완료 여부를 판단하지 않는다. 특히 `docs/strategies`의 후보 검토와 `docs/tasks/05_strategy_backtest.md`의 구현 현황을 구분한다.
