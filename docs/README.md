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
| 기존 역할별 작업을 어디서 이어갈지 | [개선 작업 추적](operations/improvement_sessions_2026-09-13.md) |
| 화면과 사용자 동작의 설계 기준 | [DESIGN](../DESIGN.md) |
| 지표·리포트 값의 의미 | [지표 가이드](analysis/indicator_guide.md), [리포트 가이드](analysis/market_report_guide.md) |
| 구현된 전략과 백테스트 규칙 | [전략·백테스트 현황](tasks/05_strategy_backtest.md) |
| DB의 현재 구현과 문서 차이 | [개념 지도: 저장 경계](knowledge/concepts.md#저장-경계와-알려진-문서-차이) |
| 테스트 실행 방법 | [Python·테스트 가이드](operations/python_runtime_and_test_guide.md) |
| 초기화 모드와 운영 로그 | [운영 가이드](tasks/07_operations_docs.md) |
| 설계 선택의 이유 | [OKF 도입 결정](decisions/0001-local-okf.md) |
| 예전 보고서·계획 | [기록 보관 안내](archive/README.md) |

## 읽는 순서

처음 들어오면 프로젝트 README → 이 문서 → 개념 지도 → 담당 주제의 문서 순서로 읽는다. 작업을 재개할 때는 task 요약에서 완료·대기를 확인한 후 관련 코드와 테스트를 확인한다.

등록부에서 `proposed`인 문서는 아직 구현되지 않은 내용을 포함한다. `historical` 문서의 미완료 목록은 최신 task를 덮어쓰지 않는다. `review-required` 문서는 알려진 차이를 먼저 읽는다.

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
