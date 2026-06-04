# Codex Session Prompts

새로운 Codex 세션에서도 빠르게 프로젝트 상태를 파악하고 이어서 작업할 수 있도록, 역할별 시작 프롬프트 예시를 정리한 문서입니다.

## 공통 시작 규칙

새 세션에서는 먼저 아래 문서를 읽고 시작하는 것을 권장합니다.

1. [`README.md`](/C:/Users/user/PycharmProjects/invest_bot/README.md)
2. [`agent.md`](/C:/Users/user/PycharmProjects/invest_bot/agent.md)
3. [`docs/tasks/00_summary.md`](/C:/Users/user/PycharmProjects/invest_bot/docs/tasks/00_summary.md)
4. 자신의 작업 범위와 관련된 task 문서

공통적으로 요청하면 좋은 항목:

- 현재 완료된 것
- 아직 미완료인 것
- 관련 파일
- 실행/검증 명령
- 오늘 이어서 할 수 있는 다음 작업

## 1. 백엔드 세션 프롬프트

```text
현재 저장소의 백엔드 개발 현황을 파악해줘.
특히 데이터 수집, 지표 계산, 전략 신호, 백테스트, 시장 리포트 기준으로
1) 완료된 것
2) 미완료 항목
3) 관련 파일
4) 바로 실행 가능한 검증 명령
을 정리한 뒤, 오늘 이어서 할 수 있는 백엔드 작업 3개를 우선순위와 함께 제안해줘.

문서는 README.md, agent.md, docs/tasks/00_summary.md, docs/tasks/02_data_collection.md,
docs/tasks/03_analysis.md, docs/tasks/05_strategy_backtest.md를 먼저 참고해.
```

## 2. 프론트엔드 세션 프롬프트

```text
현재 저장소의 프론트엔드(Streamlit/대시보드) 개발 현황을 파악해줘.
특히 개요/실행/데이터/리포트/테스트 탭 기준으로
1) 현재 구현 상태
2) 남은 UX 이슈
3) 관련 파일
4) 직접 확인 가능한 실행 명령
을 정리하고, 다음 UI 작업 후보 3개를 제안해줘.

문서는 README.md, agent.md, docs/tasks/00_summary.md, docs/tasks/04_dashboard.md를 먼저 참고해.
```

## 3. 전략·백테스트 세션 프롬프트

```text
현재 저장소의 전략/백테스트 개발 현황을 파악해줘.
특히 골든크로스 전략, 신호 생성, 백테스트 초안, 성능 지표 기준으로
1) 구현된 전략
2) 백테스트 현재 규칙
3) 부족한 비교 요소
4) 다음에 추가할 전략 후보
를 정리해줘.

문서는 README.md, agent.md, docs/tasks/05_strategy_backtest.md,
docs/strategies/00_summary.md, docs/analysis/indicator_guide.md를 먼저 참고해.
```

## 4. 운영·수집 세션 프롬프트

```text
현재 저장소의 운영/수집 개발 현황을 파악해줘.
특히 다중 종목 배치 수집, 정기 수집 스케줄링, 수집 로그, 설정 파일 기준으로
1) 구현된 것
2) 아직 없는 운영 기능
3) 관련 파일
4) 바로 실행 가능한 운영 검증 명령
을 정리한 뒤, 수집 안정성을 높이기 위한 다음 작업 3개를 제안해줘.

문서는 README.md, agent.md, docs/tasks/02_data_collection.md, docs/tasks/07_operations_docs.md를 먼저 참고해.
```

## 5. 통합 세션 프롬프트

```text
현재 저장소에서 백엔드 기능과 대시보드 연결 상태를 파악해줘.
특히 데이터 수집 → 지표 계산 → 신호 생성 → 시장 리포트 → 백테스트 결과 표시 흐름 기준으로
1) 화면에서 바로 가능한 것
2) 터미널 실행이 필요한 것
3) 아직 연결되지 않은 것
4) 관련 파일
을 정리해줘.

문서는 README.md, agent.md, docs/tasks/00_summary.md, docs/tasks/04_dashboard.md,
docs/tasks/05_strategy_backtest.md를 먼저 참고해.
```
