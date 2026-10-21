# invest_bot 지식 홈

이 문서는 프로젝트 지식의 시작점이다. 분류 규칙은 [OKF](../OKF.md), 모든 문서의 용도와 상태는 [등록부](knowledge/catalog.md)에 있다.

처음 프로젝트를 이해하려면 [프로젝트·OKF HTML 안내서](project-guide.html)를 읽는다. 전체 데이터 흐름, 기능 상태, OKF 읽는 법과 검색 가능한 문서 목록을 담은 설명용 자료다.

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

## 현재 기준 (2026-10-19)

기준 HEAD는 main `9867d48`이며 G05b까지 반영됐다. G06a는 원본 작업 트리에서 구현·검증을 마친 커밋 전 상태다. 원본·판단 날짜와 생성·전송 사전 안내는 [대시보드 계약](tasks/04_dashboard.md#생성전송-범위-안내-2026-10-19), 검증 범위는 [현재 작업 요약](tasks/00_summary.md#현재-상태-2026-10-19)을 따른다. 다음 기능은 G06b이며 순서는 [개선 작업 색인](operations/improvements/README.md)에서 관리한다. 보충 수집 CLI와 슬라이딩 혼합 연구의 반영을 일반 수집 G08a나 대시보드 조합 재로드 G08c의 완료로 해석하지 않는다.

테스트 수치·운영 데이터·브라우저·배포 확인은 기록된 날짜와 범위에 한정한다. HTML 안내서는 작성 시점의 설명 자료이며 이번 Markdown 갱신으로 다시 생성하지 않았다. commit·push는 [명시적 요청 규칙](../agent.md#커밋과-push)에 따른다.

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
